package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/signal"
	"regexp"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unicode/utf8"
)

var version = "v0.2.0"
var idPattern = regexp.MustCompile(`^[a-z][1-9][0-9]{3}$`)
var decimal = regexp.MustCompile(`^[0-9]+$`)

func main() {
	// Return broken-pipe errors so diagnostics can report already-committed effects.
	signal.Ignore(syscall.SIGPIPE)
	os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}
func run(args []string, in io.Reader, out, diagnostics io.Writer) int {
	err := execute(args, in, out)
	if err == nil {
		return 0
	}
	fmt.Fprintln(diagnostics, "sendy: "+err.Error())
	if errors.Is(err, errClosed) && len(args) > 0 && (args[0] == "submit" || args[0] == "receive") {
		return 2
	}
	if errors.Is(err, errReplyTimeout) {
		return 3
	}
	return 1
}
func positive(value, label string) (int, error) {
	n, err := strconv.Atoi(value)
	if err != nil || !decimal.MatchString(value) || n <= 0 {
		return 0, fmt.Errorf("%s must be a positive decimal integer; received %q", label, value)
	}
	return n, nil
}
func identifiers(ids []string) error {
	if len(ids) == 0 {
		return errors.New("at least one conversation ID is required")
	}
	seen := map[string]bool{}
	for _, id := range ids {
		if !idPattern.MatchString(id) {
			return advise(fmt.Errorf("invalid conversation ID %q: expected one lowercase letter and four digits (1000–9999)", id), "Use the exact ID returned by sendy create. The parent can establish new IDs with sendy create 1; copy the returned ID instead of inventing one.")
		}
		if seen[id] {
			return advise(fmt.Errorf("duplicate conversation ID %q", id), "List each conversation ID only once, then retry the command.")
		}
		seen[id] = true
	}
	return nil
}
func validMessage(message string) error {
	if message == "" {
		return advise(errors.New("message must not be empty"), "Provide nonempty text on stdin, for example sendy submit ID < result.txt, or use --template NAME. If using a template, ensure its text and field values produce a nonempty message.")
	}
	if !utf8.ValidString(message) {
		return advise(errors.New("message must be valid UTF-8"), "Convert the input file or template field values to UTF-8 text, then retry. Binary data must be encoded as text before sending.")
	}
	return nil
}

type messageOptions struct {
	name       string
	sets       []string
	paramsFile string
	timeout    time.Duration
}

func timeoutDuration(value string) (time.Duration, error) {
	minutes, err := positive(value, "MINUTES")
	if err != nil {
		return 0, err
	}
	if uint64(minutes) > uint64((1<<63-1)/int64(time.Minute)) {
		return 0, fmt.Errorf("MINUTES is too large: maximum is %d", (1<<63-1)/int64(time.Minute))
	}
	return time.Duration(minutes) * time.Minute, nil
}

func options(args []string, render, allowTimeout bool) (messageOptions, error) {
	o := messageOptions{}
	for len(args) > 0 {
		flag := args[0]
		if flag != "--template" && flag != "--set" && flag != "--params-file" && !(allowTimeout && flag == "--timeout") {
			return o, fmt.Errorf("unexpected argument %q", flag)
		}
		if len(args) < 2 {
			return o, fmt.Errorf("%s requires a value", flag)
		}
		value := args[1]
		args = args[2:]
		if flag == "--timeout" {
			if o.timeout != 0 {
				return o, errors.New("--timeout must occur once")
			}
			var err error
			o.timeout, err = timeoutDuration(value)
			if err != nil {
				return o, err
			}
		} else if flag == "--template" {
			if render || o.name != "" {
				return o, errors.New("--template must occur once, on submit or reply")
			}
			if value == "" {
				return o, errors.New("--template requires a name")
			}
			o.name = value
		} else if flag == "--params-file" {
			if o.paramsFile != "" {
				return o, errors.New("--params-file must occur once")
			}
			if value == "" {
				return o, errors.New("--params-file requires a path")
			}
			o.paramsFile = value
		} else {
			o.sets = append(o.sets, value)
		}
	}
	if o.paramsFile != "" && len(o.sets) > 0 {
		return o, errors.New("--set and --params-file cannot be mixed")
	}
	if !render && o.name == "" && o.paramsFile != "" {
		return o, errors.New("--params-file requires --template")
	}
	if !render && o.name == "" && len(o.sets) > 0 {
		return o, errors.New("--set requires --template")
	}
	return o, nil
}

func execute(args []string, in io.Reader, out io.Writer) (err error) {
	if topic, requested := helpRequest(args); requested {
		return writeHelp(topic, out)
	}
	started := time.Now()
	cmd := ""
	if len(args) > 0 {
		cmd = args[0]
	}
	var ids []string
	submitted := false
	effect, recovery := notApplied(cmd), usage(cmd)
	defer func() {
		if err == nil {
			return
		}
		var advised *advisedError
		if errors.As(err, &advised) {
			recovery = advised.advice
		}
		var uncertain *commitError
		if errors.As(err, &uncertain) {
			effect, recovery = unconfirmed(cmd, ids)
		}
		if errors.Is(err, errClosed) {
			if submitted {
				effect = "Your result was recorded before the conversation closed. Closure discarded its pending result; no reply was returned."
			}
			recovery = "This conversation cannot accept more messages. End the child session; the parent must use sendy create 1 for any new conversation. Do not resubmit to this ID."
		}
		err = fmt.Errorf("%w\n%s\n%s", err, effect, recovery)
	}()
	if len(args) == 0 {
		return errors.New("a command is required")
	}
	args = args[1:]
	if cmd == "--version" && len(args) == 0 {
		effect = "The version was read, but stdout may be incomplete. No conversation data was changed."
		recovery = "Fix the stdout destination or pipe, then run sendy --version again."
		_, err := fmt.Fprintln(out, "sendy "+version)
		return err
	}
	if cmd == "template" {
		if len(args) == 1 && args[0] == "validate" {
			effect = "Template validation failed. No templates or conversations were changed; no message was sent."
			recovery = templateRecovery
			return validateTemplates()
		}
		if len(args) == 2 && args[0] == "fields" {
			recovery = templateRecovery
			_, fields, err := namedTemplate(args[1])
			if err != nil {
				return err
			}
			effect = "Template fields were read, but stdout may be incomplete. No message was sent; templates and conversations were not changed."
			recovery = "Fix the stdout destination or pipe, then repeat sendy template fields with the same name."
			return json.NewEncoder(out).Encode(fields)
		}
		if len(args) >= 2 && args[0] == "render" {
			o, err := options(args[2:], true, false)
			if err != nil {
				return err
			}
			recovery = templateRecovery
			message, err := renderTemplate(args[1], o.sets, o.paramsFile)
			if err != nil {
				return err
			}
			effect = "The template was rendered, but stdout may be incomplete. No message was sent; templates and conversations were not changed."
			recovery = "Fix the stdout destination or pipe, then repeat sendy template render with the same name and fields."
			_, err = io.WriteString(out, message)
			return err
		}
		return errors.New("usage: sendy template render NAME [--set KEY=VALUE ... | --params-file PATH] | template fields NAME | template validate")
	}
	var count int
	var message string
	var deadline time.Time
	var replyTimeout time.Duration
	switch cmd {
	case "create":
		if len(args) != 1 {
			return errors.New("usage: sendy create COUNT")
		}
		count, err = positive(args[0], "COUNT")
		if err != nil {
			return err
		}
	case "submit", "reply":
		if len(args) < 1 {
			return errors.New(commandUsage(cmd))
		}
		ids = args[:1]
		if err = identifiers(ids); err != nil {
			return err
		}
		o, e := options(args[1:], false, cmd == "submit")
		if e != nil {
			return e
		}
		replyTimeout = o.timeout
		if o.name != "" {
			recovery = templateRecovery
			message, err = renderTemplate(o.name, o.sets, o.paramsFile)
		} else {
			recovery = "Check that the stdin file or pipe can be read completely, then retry with nonempty UTF-8 text. Alternatively use --template NAME."
			var b []byte
			b, err = io.ReadAll(in)
			message = string(b)
		}
		if err != nil {
			return err
		}
		if err = validMessage(message); err != nil {
			return err
		}
	case "receive":
		if len(args) != 1 && (len(args) != 3 || args[1] != "--timeout") {
			return errors.New("usage: sendy receive ID [--timeout MINUTES]")
		}
		ids = args[:1]
		if len(args) == 3 {
			replyTimeout, err = timeoutDuration(args[2])
			if err != nil {
				return err
			}
		}
	case "wait":
		if len(args) < 3 || args[len(args)-2] != "--timeout" {
			return errors.New("usage: sendy wait ID [ID ...] --timeout MINUTES")
		}
		duration, e := timeoutDuration(args[len(args)-1])
		if e != nil {
			return e
		}
		deadline = started.Add(duration)
		ids = args[:len(args)-2]
	case "close":
		ids = args
	default:
		return fmt.Errorf("unknown command %q", cmd)
	}
	if cmd != "create" {
		if err = identifiers(ids); err != nil {
			return err
		}
	}
	recovery = storageRecovery
	s, err := openStore()
	if err != nil {
		return err
	}
	defer s.db.Close()
	switch cmd {
	case "create":
		ids, err = s.create(count)
		if err == nil {
			effect = "Conversations were created: " + strings.Join(ids, " ") + ". Their IDs could not be fully written to stdout."
			recovery = "Use the IDs listed above; do not repeat create to recover them. Fix the stdout destination or pipe before continuing."
			_, err = fmt.Fprintln(out, strings.Join(ids, " "))
		}
	case "submit", "receive":
		var round submission
		if cmd == "submit" {
			round, err = s.submit(ids[0], message)
			submitted = err == nil
		} else {
			round, err = s.currentSubmission(ids[0])
		}
		if err == nil {
			effect = "Waiting stopped without returning a reply. This receive did not submit work, discard a reply, or close the conversation."
			if submitted {
				effect = "Your result was recorded for " + ids[0] + " before waiting stopped. This wait did not cancel it, discard a reply, or close the conversation; no reply was returned."
			}
			recovery = "Do not submit the same result again. Resume waiting with sendy receive " + ids[0] + " [--timeout MINUTES]. " + storageRecovery
			if replyTimeout != 0 {
				deadline = time.Now().Add(replyTimeout)
			}
			message, err = s.awaitReply(ids[0], round, deadline)
			if errors.Is(err, errReplyTimeout) {
				recovery = "Investigate the missing reply, then resume waiting with sendy receive " + ids[0] + " [--timeout MINUTES]. Do not resubmit the same result."
			}
			if err == nil {
				effect = "The parent's reply was accepted and read, but stdout may be incomplete. The reply remains recorded."
				if submitted {
					effect = "Your result was recorded. " + effect
				}
				recovery = "Do not resubmit the completed work. Fix the stdout destination or pipe, then use sendy receive " + ids[0] + " to read the reply again before submitting the next result."
				_, err = io.WriteString(out, message)
			}
		}
	case "reply":
		err = s.reply(ids[0], message)
	case "close":
		err = s.close(ids)
	case "wait":
		var snap snapshot
		snap, err = s.wait(ids, deadline)
		if err == nil {
			effect = "Wait completed, but stdout may be incomplete. This wait did not consume any results or send any messages."
			recovery = "Fix the stdout destination or pipe, then repeat the same sendy wait command to read the current results."
			err = json.NewEncoder(out).Encode(snap)
		}
	}
	return err
}
