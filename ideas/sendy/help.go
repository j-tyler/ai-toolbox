package main

import (
	"fmt"
	"io"
	"strings"
)

// Help runs before input, template, or storage access. Option values are data,
// even when they happen to be named --help or -h.
func helpRequest(args []string) (string, bool) {
	if len(args) == 0 {
		return "", false
	}
	if args[0] == "help" || args[0] == "--help" || args[0] == "-h" {
		// Explicit help accepts only a topic and help flags. Repeating a help
		// flag must not turn a valid topic into an unknown one.
		var topic []string
		for _, arg := range args[1:] {
			if arg != "--help" && arg != "-h" {
				topic = append(topic, arg)
			}
		}
		return strings.Join(topic, " "), true
	}
	for i := 1; i < len(args); i++ {
		switch args[i] {
		case "--template", "--set", "--timeout":
			i++
		case "--help", "-h":
			topic := args[0]
			if topic == "template" && len(args) > 1 && args[1] != "--help" && args[1] != "-h" {
				topic += " " + args[1]
			}
			return topic, true
		}
	}
	return "", false
}

type helpTopic struct {
	name string
	text string
}

// The overview includes the same command reference as topic help so an agent
// can discover the complete interface with a single call.
var helpTopics = []helpTopic{
	{"create", `Usage: sendy create COUNT
  Create COUNT conversations; COUNT is a positive decimal integer.
  Prints space-separated IDs followed by a newline and returns immediately.
  Each ID (for example k1007) belongs to one parent/child pair and is reused
  for successive rounds. Copy the returned IDs; do not invent them.
  The harness launches children and supplies their initial tasks. New
  conversations expect a child result; create does not launch an agent.
`},
	{"submit", `Usage: sendy submit ID < result.txt
       sendy submit ID --template NAME [--set KEY=VALUE ...]
  Child: record a result, then BLOCK until the parent replies or closes.
  There is NO timeout. Run in the foreground in a harness that honors blocking
  commands; backgrounding or returning control to the agent defeats waiting.
  On reply: print the exact instruction bytes (no added newline), exit 0,
  perform that instruction, and submit the next result using the same ID.
  On closure: leave stdout empty, report closure on stderr, exit 2, and end
  the child session. Only one submission may be outstanding per conversation.
  Do not resubmit after an interrupted submit: the result may already be
  recorded. Ask the parent to check and recover the conversation.
`},
	{"reply", `Usage: sendy reply ID < instruction.txt
       sendy reply ID --template NAME [--set KEY=VALUE ...]
  Parent: record the next instruction for an outstanding child submission.
  Returns immediately with empty stdout; does not wait for the child.
  A result must be ready. There is no unsolicited-instruction queue.
  Reply retires the previous result from future waits, so save it first.
  The instruction releases the particular submit call it answers.
`},
	{"wait", `Usage: sendy wait ID [ID ...] --timeout MINUTES
  Parent: wait until EVERY listed conversation has a result or is closed,
  or the deadline expires. MINUTES is a required positive decimal integer.
  IDs must be distinct. Prints one JSON object followed by a newline:
  {"status":"timeout","results":[{"id":"k1007","message":"result text"}],"pending":["m1002"],"closed":[]}
  All four fields are always present. Each ID occurs exactly once in results,
  pending, or closed; each array preserves request order. Status is "ready"
  when pending is empty, otherwise "timeout". Both statuses exit 0.
  A timeout does not cancel work or release children. Process ready results
  or wait again. Waiting never consumes results; reply or close retires them.
  Pending means no result yet, not proof that a child is healthy or progressing.
  Use the agent session system to contact a child that has not submitted.
`},
	{"close", `Usage: sendy close ID [ID ...]
  Parent: close distinct conversations and return immediately, stdout empty.
  Releases blocked submissions with exit 2 and discards pending results.
  An already accepted reply is still delivered; close cannot retract it.
  Does not kill an agent or interrupt work outside Sendy. A working child
  discovers closure at its next submit. Closing an already closed ID succeeds.
  An unknown ID fails without closing any of the listed conversations.
`},
	{"template render", `Usage: sendy template render NAME [--set KEY=VALUE ...]
  Print the exact rendered text without adding a newline. No message is sent.
  Useful for initial prompts when the harness accepts a prompt file.
`},
	{"template fields", `Usage: sendy template fields NAME
  Print required field names as a sorted, unique JSON array plus a newline.
  A fixed-text template returns []. Takes no options and sends no message.
`},
	{"template validate", `Usage: sendy template validate
  Check all project templates for valid names, syntax, and nonempty UTF-8.
  Takes no options or field values. Success has empty stdout and exit 0;
  failure reports diagnostics on stderr and exits 1. Sends no message.
  A missing template directory is an error; an existing empty one is valid.
`},
}

const helpIntro = `Sendy - local command-line message passing for parent-child AI workflows.

Usage: sendy COMMAND [ARGUMENTS]
       sendy help [COMMAND [SUBCOMMAND]]
       sendy --help | sendy -h
       sendy COMMAND [SUBCOMMAND] --help
       sendy --version

Parent creates IDs and launches children through its harness. Each child does
one task and submits its result, staying blocked until the parent replies with
the next task or closes. Parent wait collects results from one or more children.
Sendy supplies communication, not agent launching or scheduling.

COMMAND REFERENCE
`

const messageHelp = `MESSAGE INPUT AND FILES
  submit and reply read all stdin through EOF unless --template is supplied.
  Input must be nonempty UTF-8; bytes are preserved, including whitespace,
  CRLF/LF, quotes, and trailing newlines. Binary data must first be text-encoded.
  There is no message argument or input envelope. Use file redirection:
    sendy submit k1007 < result.json > next-task.txt
    sendy reply k1007 < instruction.txt
  For inline text, use a quoted heredoc delimiter to prevent shell expansion.
  wait wraps results in JSON; decode message to recover the original file:
    set -o pipefail
    sendy wait k1007 --timeout 60 |
      jq -e -j --arg id k1007 '.results[] | select(.id == $id) | .message' > received.json
  This example requires Bash and jq. Use the file only if the pipeline succeeds;
  redirection can truncate it on failure. Save and verify before replying.
  Compare sha256sum result.json received.json to check integrity.
  jq -r adds a newline; shell command substitution strips trailing newlines.
  Replies on submit stdout are raw text and need no JSON decoding.
`

const templateHelp = `TEMPLATES
  Run from the project root. Templates are direct regular files named NAME.txt
  in .sendy/templates/ under the current directory (no parent/global search).
  File presence is registration; there is no template add command. Names start
  with a lowercase letter or digit and contain only those, hyphens, or underscores.
  Text may contain simple Go-style fields such as {{.filename}}. Fields start
  with an ASCII letter or underscore and contain letters, digits, or underscores.
  Names and fields are case-sensitive. Loops, functions, conditionals, nested
  fields, and includes are unsupported. Fixed text needs no --set arguments.
  --template NAME occurs once on submit/reply and never reads or merges stdin.
  --set KEY=VALUE is repeatable; provide every required field exactly once.
  Empty values are allowed; missing, duplicate, and unexpected fields are errors.
  Split at the first equals sign; quote values with spaces using shell quoting:
    sendy reply k1007 --template review --set 'filename=design notes.md' --set name=Alice
  Values are inserted literally, without shell execution, recursive rendering,
  or JSON escaping. Use a serialized file on stdin for arbitrary JSON messages.
  No fields are automatic, including the conversation ID.
  Errors list expected fields and occur before sending or blocking. Discover
  fields with sendy template fields NAME, then correct arguments and retry.
`

const commonHelp = `EXIT CODES AND LOCAL STATE
  0  Success, including wait timeout. Inspect wait's JSON status and pending.
  1  Error. Diagnostics go to stderr and explain effects and recovery.
  2  submit observed closure. No instruction on stdout; end the child session.
  Help prints to stdout and exits 0 without reading stdin, opening the database,
  looking up templates, or changing state. Unknown help topics exit 1.
  --version prints the installed version and exits without accessing storage.
  Conversations use a shared local store at $HOME/.sendy/conversations.db,
  independent of working directory. Agents must share that local user/store.
  No database setup is required. Concurrent independent conversations are allowed.
  At first conversation use each UTC day, if more than half of the 234,000 IDs
  are stored, conversations unused for 14 days are deleted and IDs may be reused.
  Active submit/wait calls keep their conversations alive. Create new IDs after
  abandonment instead of addressing potentially reclaimed conversations.
  An interrupted wait can be repeated. An interrupted submit/reply may already
  have sent its message; check with the parent/child before retrying. Automatic
  reconnection is not provided. Do not delete active data to recover storage.

HELP
  sendy help and sendy --help show this full reference; -h is an alias.
  Use sendy help submit or sendy submit --help for a command reference.
  Use sendy help template render or sendy template render --help for a subcommand.
`

func writeHelp(topic string, out io.Writer) error {
	var b strings.Builder
	if topic == "" || topic == "help" {
		b.WriteString(helpIntro)
		for _, entry := range helpTopics {
			b.WriteString("\n" + entry.text)
		}
		b.WriteString("\n" + messageHelp + "\n" + templateHelp)
	} else {
		found := false
		for _, entry := range helpTopics {
			if entry.name == topic || (topic == "template" && strings.HasPrefix(entry.name, "template ")) {
				b.WriteString(entry.text + "\n")
				found = true
			}
		}
		if !found {
			return fmt.Errorf("unknown help topic %q. Run sendy help to list all commands. No command was executed; no message was sent", topic)
		}
		if topic == "submit" || topic == "reply" || topic == "wait" {
			b.WriteString(messageHelp + "\n")
		}
		if topic == "submit" || topic == "reply" || strings.HasPrefix(topic, "template") {
			b.WriteString(templateHelp + "\n")
		}
	}
	b.WriteString("\n" + commonHelp)
	if _, err := io.WriteString(out, b.String()); err != nil {
		return fmt.Errorf("%w\nHelp output may be incomplete. No state was changed. Fix the stdout destination or pipe, then run sendy help again", err)
	}
	return nil
}
