package main

import (
	"bytes"
	"errors"
	"io"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestReplyTimeoutPreservesRoundAndRecovery(t *testing.T) {
	isolated(t)
	s := testStore(t)
	id := mustCall(t, "", "create", "1")[:5]
	round, err := s.submit(id, "original result")
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 2; i++ {
		resumed, err := s.currentSubmission(id)
		if err != nil || resumed != round {
			t.Fatal(resumed, err)
		}
		start := time.Now()
		got, err := s.awaitReply(id, resumed, start.Add(30*time.Millisecond))
		if got != "" || !errors.Is(err, errReplyTimeout) || time.Since(start) < 30*time.Millisecond || time.Since(start) > time.Second {
			t.Fatal(got, err, time.Since(start))
		}
		snap, err := s.snapshot([]string{id})
		if err != nil || len(snap.Results) != 1 || snap.Results[0].Message != "original result" || len(snap.Closed) != 0 {
			t.Fatal(snap, err)
		}
	}
	const reply = "reply\x00\r\n世界\n\n"
	if err := s.reply(id, reply); err != nil {
		t.Fatal(err)
	}
	// Already accepted replies are readable immediately and after close.
	if got, err := s.awaitReply(id, round, time.Now().Add(time.Second)); err != nil || got != reply {
		t.Fatal(got, err)
	}
	mustCall(t, "", "close", id)
	for i := 0; i < 2; i++ {
		var out, diag bytes.Buffer
		if code := run([]string{"receive", id, "--timeout", "1"}, brokenIO{}, &out, &diag); code != 0 || out.String() != reply || diag.Len() != 0 {
			t.Fatal(code, out.String(), diag.String())
		}
	}
}

func TestReplyTimeoutDuringHeartbeatContention(t *testing.T) {
	isolated(t)
	s := testStore(t)
	id := mustCall(t, "", "create", "1")[:5]
	round, err := s.submit(id, "original result")
	if err != nil {
		t.Fatal(err)
	}
	writer := testStore(t)
	execSQL(t, s, `UPDATE conversations SET last_used=unixepoch()-?`, int64(replyHeartbeatInterval/time.Second))
	tx, err := writer.db.Begin()
	if err != nil {
		t.Fatal(err)
	}
	defer tx.Rollback()

	// Keep the writer locked beyond the wait's deadline. Releasing it after the
	// assertion also lets a failing implementation finish without leaking work.
	done := make(chan error, 1)
	started := time.Now()
	go func() {
		_, err := s.awaitReply(id, round, started.Add(40*time.Millisecond))
		done <- err
	}()
	select {
	case err := <-done:
		if !errors.Is(err, errReplyTimeout) || time.Since(started) < 40*time.Millisecond {
			t.Fatal("wrong timeout result", err, time.Since(started))
		}
	case <-time.After(400 * time.Millisecond):
		if err := tx.Rollback(); err != nil {
			t.Fatal(err)
		}
		<-done
		t.Fatal("heartbeat contention exceeded the reply deadline")
	}
	if err := tx.Rollback(); err != nil {
		t.Fatal(err)
	}
	var busyTimeout int
	if err := s.db.QueryRow(`PRAGMA busy_timeout`).Scan(&busyTimeout); err != nil || busyTimeout != 10000 {
		t.Fatal("reply wait changed the store's lock timeout", busyTimeout, err)
	}
	snap, err := s.snapshot([]string{id})
	if err != nil || len(snap.Results) != 1 || snap.Results[0].Message != "original result" || len(snap.Closed) != 0 {
		t.Fatal(snap, err)
	}
	if err := writer.reply(id, "late reply"); err != nil {
		t.Fatal(err)
	}
	if got := mustCall(t, "", "receive", id, "--timeout", "1"); got != "late reply" {
		t.Fatal(got)
	}
}

func TestTimedReplyWaitRecoversFromHeartbeatContention(t *testing.T) {
	isolated(t)
	s := testStore(t)
	id := mustCall(t, "", "create", "1")[:5]
	round, err := s.submit(id, "result")
	if err != nil {
		t.Fatal(err)
	}
	writer := testStore(t)
	execSQL(t, s, `UPDATE conversations SET last_used=unixepoch()-?`, int64(replyHeartbeatInterval/time.Second))
	tx, err := writer.db.Begin()
	if err != nil {
		t.Fatal(err)
	}
	defer tx.Rollback()
	if _, err := tx.Exec(`INSERT INTO replies VALUES(?,?,'committed reply'); UPDATE conversations SET result=NULL WHERE id=?`, id, round.round, id); err != nil {
		t.Fatal(err)
	}
	done := make(chan error, 1)
	go func() {
		got, err := s.awaitReply(id, round, time.Now().Add(time.Second))
		if err == nil && got != "committed reply" {
			err = errors.New("received the wrong reply")
		}
		done <- err
	}()
	select {
	case err := <-done:
		t.Fatal("returned before the reply was committed", err)
	case <-time.After(40 * time.Millisecond):
	}
	if err := tx.Commit(); err != nil {
		t.Fatal(err)
	}
	if err := <-done; err != nil {
		t.Fatal(err)
	}
}

func TestReceiveSelectsLatestRoundWithoutConsuming(t *testing.T) {
	isolated(t)
	s := testStore(t)
	id := mustCall(t, "", "create", "1")[:5]
	if _, err := s.currentSubmission(id); err == nil {
		t.Fatal("receive accepted a conversation without a submission")
	}
	first, err := s.submit(id, "first")
	if err != nil {
		t.Fatal(err)
	}
	if err := s.reply(id, "first reply"); err != nil {
		t.Fatal(err)
	}
	if got := mustCall(t, "ignored stdin", "receive", id); got != "first reply" {
		t.Fatal(got)
	}
	second, err := s.submit(id, "second")
	if err != nil {
		t.Fatal(err)
	}
	selected, err := s.currentSubmission(id)
	if err != nil || selected != second || selected == first {
		t.Fatal(selected, err)
	}
	if _, err := s.awaitReply(id, selected, time.Now()); !errors.Is(err, errReplyTimeout) {
		t.Fatal("returned a stale reply", err)
	}
	// A call that selected an earlier round stays attached to it.
	if got, err := s.awaitReply(id, first, time.Time{}); err != nil || got != "first reply" {
		t.Fatal(got, err)
	}
	mustCall(t, "", "close", id)
	code, out, diag := call(t, "", "receive", id)
	if code != 2 || out != "" {
		t.Fatal(code, out, diag)
	}
	requireText(t, diag, "conversation closed", "End the child session")
}

func TestReceiveOutputFailureCanBeRecovered(t *testing.T) {
	isolated(t)
	s := testStore(t)
	id := mustCall(t, "", "create", "1")[:5]
	if _, err := s.submit(id, "result"); err != nil {
		t.Fatal(err)
	}
	if err := s.reply(id, "exact reply\n\n"); err != nil {
		t.Fatal(err)
	}
	var diag bytes.Buffer
	out := &partialWriter{}
	// Hide bytes.Buffer's promoted WriteString so io.WriteString exercises
	// the deliberately failing Write method instead of bypassing it.
	if code := run([]string{"receive", id}, brokenIO{}, struct{ io.Writer }{out}, &diag); code != 1 || out.Len() != 1 {
		t.Fatal(code)
	}
	requireText(t, diag.String(), "reply remains recorded", "sendy receive "+id)
	if got := mustCall(t, "", "receive", id); got != "exact reply\n\n" {
		t.Fatal(got)
	}
}

func TestTimeoutAndReceiveArgumentsBeforeInputOrStorage(t *testing.T) {
	home := isolated(t)
	for _, cmd := range []string{"submit", "receive"} {
		for _, value := range []string{"", "0", "-1", "+1", "1.5", "1m", "153722868", "999999999999999999999"} {
			var diag bytes.Buffer
			code := run([]string{cmd, "a1000", "--timeout", value}, brokenIO{}, io.Discard, &diag)
			if code != 1 {
				t.Fatal(cmd, value, code, diag.String())
			}
			requireText(t, diag.String(), "MINUTES")
		}
	}
	for _, args := range [][]string{
		{"receive"}, {"receive", "a1000", "a1001"}, {"receive", "a1000", "--timeout"},
		{"receive", "a1000", "--template", "foo"}, {"receive", "a1000", "--set", "a=b"},
		{"receive", "a1000", "--params-file", "foo"}, {"receive", "a1000", "--timeout", "1", "--timeout", "2"},
		{"submit", "a1000", "--timeout"}, {"submit", "a1000", "--timeout", "1", "--timeout", "2"},
		{"reply", "a1000", "--timeout", "1"}, {"template", "render", "foo", "--timeout", "1"},
	} {
		var diag bytes.Buffer
		if code := run(args, brokenIO{}, io.Discard, &diag); code != 1 {
			t.Fatal(args, code, diag.String())
		}
	}
	if _, err := os.Stat(filepath.Join(home, ".sendy")); !os.IsNotExist(err) {
		t.Fatal("invalid arguments touched storage", err)
	}
	for _, args := range [][]string{
		{"--timeout", "0002"},
		{"--timeout", "2", "--template", "x", "--set", "a=--timeout"},
		{"--template", "x", "--params-file", "--timeout", "--timeout", "2"},
	} {
		o, err := options(args, false, true)
		if err != nil || o.timeout != 2*time.Minute {
			t.Fatal(args, o, err)
		}
	}
}
