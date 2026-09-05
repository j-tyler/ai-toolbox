package main

import (
	"database/sql"
	"fmt"
	"strings"
)

// Preserve the underlying error for exit-code handling while supplying recovery
// advice for known failures. execute adds the effect appropriate to its stage.
type advisedError struct {
	error
	advice string
}

func (e *advisedError) Unwrap() error       { return e.error }
func advise(err error, advice string) error { return &advisedError{err, advice} }

// A failed commit is not evidence that a write was never saved. Distinguish it
// from a rejected/rolled-back operation so callers do not blindly send twice.
type commitError struct{ error }

func (e *commitError) Unwrap() error { return e.error }
func commit(tx *sql.Tx) error {
	if err := tx.Commit(); err != nil {
		return &commitError{err}
	}
	return nil
}

func usage(cmd string) string {
	switch cmd {
	case "create":
		return "Usage: sendy create COUNT (for example: sendy create 1)."
	case "submit", "reply":
		return fmt.Sprintf("Usage: sendy %s ID < message.txt, or sendy %s ID --template NAME [--set KEY=VALUE ...].", cmd, cmd)
	case "wait":
		return "Usage: sendy wait ID [ID ...] --timeout MINUTES (for example: sendy wait a1000 --timeout 5)."
	case "close":
		return "Usage: sendy close ID [ID ...]. Include each ID once."
	case "template":
		return "Usage: sendy template render NAME [--set KEY=VALUE ...] | template fields NAME | template validate."
	case "--version":
		return "Usage: sendy --version (no other arguments)."
	default:
		return "Choose a command: sendy create COUNT; sendy submit ID < result.txt; sendy reply ID < instruction.txt; sendy wait ID [ID ...] --timeout MINUTES; sendy close ID [ID ...]; sendy template render NAME [--set KEY=VALUE ...]; sendy template fields NAME; sendy template validate; sendy --version."
	}
}

func notApplied(cmd string) string {
	switch cmd {
	case "submit", "reply":
		return "No message was sent."
	case "create":
		return "No conversations were created by this invocation."
	case "close":
		return "No conversations were closed by this invocation."
	case "wait":
		return "Waiting stopped without returning results. This wait did not consume any results or send any messages."
	case "template":
		return "No output was produced. No message was sent; templates and conversations were not changed."
	default:
		return "No command was executed; no message was sent."
	}
}

const storageRecovery = "Check HOME, permissions and free disk space for $HOME/.sendy/conversations.db. If the database is busy, let the other operation finish. For an incompatible or damaged database, ask the project maintainer to repair it; do not delete active conversation data."
const templateRecovery = "Fix the named template file or its permissions, then run sendy template validate from the project root. Templates contain UTF-8 text and simple fields such as {{.filename}}. Use sendy template fields NAME to see required fields."

func unconfirmed(cmd string, ids []string) (string, string) {
	idList := strings.Join(ids, " ")
	effect := "The database commit failed; Sendy could not confirm whether " + cmd + " was saved. Do not assume nothing happened."
	switch cmd {
	case "create":
		return effect + " Attempted IDs: " + idList + ".", "Check these IDs with sendy wait " + idList + " --timeout 1 before creating more. " + storageRecovery
	case "submit":
		return effect, "Do not blindly resubmit. Ask the parent to check sendy wait " + idList + " --timeout 5 for the result and recover the conversation. " + storageRecovery
	case "reply":
		return effect, "The reply may already have been accepted. Confirm with the child before repeating it; sendy wait observes child results, not delivery of a reply. " + storageRecovery
	default: // close
		return effect, "Check the IDs with sendy wait " + idList + " --timeout 1. Repeating close with the same IDs is safe once the database is accessible. " + storageRecovery
	}
}
