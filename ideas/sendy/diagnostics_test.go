package main

import (
	"bytes"
	"errors"
	"strings"
	"testing"
	"time"
)

func requireText(t *testing.T, text string, fragments ...string) {
	t.Helper()
	for _, fragment := range fragments {
		if !strings.Contains(text, fragment) {
			t.Errorf("missing %q in diagnostic:\n%s", fragment, text)
		}
	}
}

func TestRejectedCommandsExplainStateAndRecovery(t *testing.T) {
	isolated(t)
	s := testStore(t)
	ids, err := s.create(2)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := s.submit(ids[0], "earlier result"); err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		args  []string
		input string
		want  []string
	}{
		{[]string{"submit", ids[0]}, "duplicate", []string{"outstanding submission", "No message was sent.", "earlier submission remains recorded", "original submit call", "sendy wait " + ids[0]}},
		{[]string{"reply", ids[1]}, "too soon", []string{"No message was sent.", "no child result is currently recorded", "require an outstanding submission", "earlier reply may already have been accepted", "Check whether the child received it"}},
		{[]string{"close", ids[0], "z9999"}, "", []string{"unknown conversation", "operation was not performed", "No conversations were closed", "sendy create 1"}},
		{[]string{"submit", "z9999"}, "result", []string{"unknown conversation", "No message was sent.", "sendy create 1"}},
		{[]string{"submit", ids[1]}, "", []string{"message must not be empty", "No message was sent.", "stdin", "--template NAME"}},
		{[]string{"reply", ids[0]}, string([]byte{255}), []string{"valid UTF-8", "No message was sent.", "Convert the input"}},
		{[]string{"create", "234001"}, "", []string{"not enough unused IDs", "No conversations were created", "Request no more than the available count", "Closing does not free an ID immediately"}},
		{[]string{"wait", ids[1]}, "", []string{"Waiting stopped without returning results", "--timeout MINUTES"}},
		{[]string{"submit", "a00"}, "result", []string{"invalid conversation ID", "No message was sent.", "exact ID returned by sendy create"}},
		{[]string{"close", ids[0], ids[0]}, "", []string{"duplicate conversation ID", "No conversations were closed", "only once"}},
		{[]string{"submit", ids[1], "--template"}, "", []string{"requires a value", "No message was sent.", "--template NAME"}},
		{[]string{"create", "-1"}, "", []string{"positive decimal integer", "No conversations were created", "sendy create 1"}},
		{[]string{"bogus"}, "", []string{"unknown command", "No command was executed", "Choose a command"}},
		{[]string{"--version", "extra"}, "", []string{"No command was executed", "sendy --version (no other arguments)"}},
	} {
		code, out, diag := call(t, tc.input, tc.args...)
		if code != 1 || out != "" {
			t.Fatal(tc.args, code, out, diag)
		}
		requireText(t, diag, tc.want...)
	}
	snap, err := s.snapshot(ids)
	if err != nil || len(snap.Results) != 1 || snap.Results[0].Message != "earlier result" || len(snap.Closed) != 0 || len(snap.Pending) != 1 {
		t.Fatal("rejected commands changed earlier state", snap, err)
	}
	if err := s.reply(ids[0], "accepted instruction"); err != nil {
		t.Fatal(err)
	}
	_, _, diag := call(t, "duplicate reply", "reply", ids[0])
	requireText(t, diag, "earlier reply may already have been accepted", "No message was sent.")
	var reply string
	if err := s.db.QueryRow(`SELECT message FROM replies WHERE id=?`, ids[0]).Scan(&reply); err != nil || reply != "accepted instruction" {
		t.Fatal("duplicate reply changed accepted instruction", reply, err)
	}
}

func TestInputAndStorageFailuresAreUnsent(t *testing.T) {
	home := isolated(t)
	var diag bytes.Buffer
	code := run([]string{"submit", "a1000"}, brokenIO{}, &bytes.Buffer{}, &diag)
	if code != 1 {
		t.Fatal(code)
	}
	requireText(t, diag.String(), "read failed", "No message was sent.", "stdin file or pipe")
	put(t, home+"/.sendy", "not a directory")
	_, _, text := call(t, "result", "submit", "a1000")
	requireText(t, text, "not a directory", "No message was sent.", "Check HOME", "do not delete active conversation data")
}

func TestFailureAfterSubmitDoesNotClaimNothingWasSent(t *testing.T) {
	for _, outputFailure := range []bool{false, true} {
		t.Run(map[bool]string{false: "waiting", true: "stdout"}[outputFailure], func(t *testing.T) {
			isolated(t)
			s := testStore(t)
			ids, err := s.create(1)
			if err != nil {
				t.Fatal(err)
			}
			var diag bytes.Buffer
			done := make(chan int, 1)
			go func() {
				done <- run([]string{"submit", ids[0]}, strings.NewReader("recorded result"), brokenIO{}, &diag)
			}()
			ready(t, s, ids)
			if outputFailure {
				if err := s.reply(ids[0], "accepted reply"); err != nil {
					t.Fatal(err)
				}
			} else {
				execSQL(t, s, `DROP TABLE replies`)
			}
			select {
			case code := <-done:
				if code != 1 {
					t.Fatal(code)
				}
			case <-time.After(5 * time.Second):
				t.Fatal("submit did not report its failure")
			}
			text := diag.String()
			if strings.Contains(text, "No message was sent") {
				t.Fatal("diagnostic incorrectly claims unsent", text)
			}
			requireText(t, text, "Your result was recorded", "Do not")
			if outputFailure {
				requireText(t, text, "reply was accepted and read", "stdout may be incomplete", "ask the parent")
			} else {
				requireText(t, text, "before waiting stopped", "sendy wait "+ids[0], "no reply was returned")
				snap, err := s.snapshot(ids)
				if err != nil || snap.Results[0].Message != "recorded result" {
					t.Fatal(snap, err)
				}
			}
		})
	}
}

type partialWriter struct{ bytes.Buffer }

func (w *partialWriter) Write(b []byte) (int, error) {
	n, _ := w.Buffer.Write(b[:1])
	return n, errors.New("stdout unavailable")
}

func TestCreatedIDsSurvivePartialStdout(t *testing.T) {
	isolated(t)
	var out partialWriter
	var diag bytes.Buffer
	if code := run([]string{"create", "2"}, strings.NewReader(""), &out, &diag); code != 1 || out.Len() != 1 {
		t.Fatal(code, out.String(), diag.String())
	}
	requireText(t, diag.String(), "Conversations were created: a1000 a1001", "do not repeat create", "stdout")
	if strings.Contains(diag.String(), "No conversations were created") {
		t.Fatal(diag.String())
	}
	if n := storedCount(t, testStore(t)); n != 2 {
		t.Fatal(n)
	}
}

func TestReadOnlyOutputFailuresCanBeRetried(t *testing.T) {
	isolated(t)
	s := testStore(t)
	ids, err := s.create(1)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := s.submit(ids[0], "retained result"); err != nil {
		t.Fatal(err)
	}
	put(t, ".sendy/templates/plain.txt", "fixed text")
	for _, args := range [][]string{{"wait", ids[0], "--timeout", "1"}, {"template", "fields", "plain"}, {"template", "render", "plain"}, {"--version"}} {
		var diag bytes.Buffer
		if code := run(args, strings.NewReader(""), brokenIO{}, &diag); code != 1 {
			t.Fatal(args, code)
		}
		requireText(t, diag.String(), "stdout may be incomplete", "Fix the stdout destination")
		if strings.Contains(diag.String(), "No output was produced") {
			t.Fatal(diag.String())
		}
		mustCall(t, "", args...)
	}
}

func TestCommitFailureIsDistinguishedFromRejection(t *testing.T) {
	isolated(t)
	s := testStore(t)
	execSQL(t, s, `PRAGMA foreign_keys=ON;
		CREATE TABLE required_row(id INTEGER PRIMARY KEY);
		CREATE TABLE deferred_row(id INTEGER REFERENCES required_row(id) DEFERRABLE INITIALLY DEFERRED);`)
	tx, err := s.db.Begin()
	if err != nil {
		t.Fatal(err)
	}
	defer tx.Rollback()
	if _, err := tx.Exec(`INSERT INTO deferred_row VALUES(1)`); err != nil {
		t.Fatal(err)
	}
	var uncertain *commitError
	if err := commit(tx); !errors.As(err, &uncertain) || errors.Unwrap(uncertain) == nil {
		t.Fatal("commit error lost its cause or uncertainty", err)
	}
	for _, cmd := range []string{"create", "submit", "reply", "close"} {
		effect, recovery := unconfirmed(cmd, []string{"a1000"})
		requireText(t, effect, "could not confirm whether "+cmd+" was saved", "Do not assume nothing happened")
		if recovery == "" || strings.Contains(effect, "No message was sent") {
			t.Fatal(cmd, effect, recovery)
		}
	}
}
