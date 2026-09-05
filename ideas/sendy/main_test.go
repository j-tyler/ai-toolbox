package main

import (
	"bytes"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func isolated(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	t.Setenv("HOME", dir)
	old, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	if err = os.Chdir(dir); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := os.Chdir(old); err != nil {
			t.Fatal(err)
		}
	})
	return dir
}
func call(t *testing.T, input string, args ...string) (int, string, string) {
	t.Helper()
	var out, stderr bytes.Buffer
	code := run(args, strings.NewReader(input), &out, &stderr)
	return code, out.String(), stderr.String()
}
func mustCall(t *testing.T, input string, args ...string) string {
	t.Helper()
	code, out, err := call(t, input, args...)
	if code != 0 {
		t.Fatalf("%v: exit %d: %s", args, code, err)
	}
	return out
}
func put(t *testing.T, path, value string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(value), 0600); err != nil {
		t.Fatal(err)
	}
}
func checkError(t *testing.T, err error, fragment string) {
	t.Helper()
	if err == nil || !strings.Contains(err.Error(), fragment) {
		t.Fatalf("wanted %q, got %v", fragment, err)
	}
}
func testStore(t *testing.T) *store {
	t.Helper()
	s, err := openStore()
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { s.db.Close() })
	return s
}
func ready(t *testing.T, s *store, ids []string) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for {
		snap, err := s.snapshot(ids)
		if err != nil {
			t.Fatal(err)
		}
		if len(snap.Pending) == 0 {
			return
		}
		if time.Now().After(deadline) {
			t.Fatal("submission never became ready")
		}
		time.Sleep(time.Millisecond)
	}
}

type brokenIO struct{}

func (brokenIO) Read([]byte) (int, error)  { return 0, errors.New("read failed") }
func (brokenIO) Write([]byte) (int, error) { return 0, errors.New("write failed") }

func TestArguments(t *testing.T) {
	isolated(t)
	cases := [][]string{
		{}, {"bogus"}, {"--version", "extra"}, {"create"}, {"create", "1", "2"}, {"create", "0"}, {"create", "-1"}, {"create", "+1"}, {"create", "1.0"}, {"create", "999999999999999999999"},
		{"submit"}, {"reply"}, {"submit", "Z12"}, {"reply", "a1"}, {"submit", "a001"}, {"submit", "a1000", "text"}, {"submit", "a1000", "--set", "x=y"}, {"submit", "a1000", "--template"}, {"submit", "a1000", "--set"}, {"submit", "a1000", "--template", ""}, {"submit", "a1000", "--template", "x", "--template", "x"}, {"submit", "a1000", "--timeout", "1"},
		{"wait"}, {"wait", "a1000", "--timeout", "0"}, {"wait", "a1000", "--timeout", "9223372036854775807"}, {"wait", "a1000", "a1000", "--timeout", "1"}, {"wait", "a1000", "--timeout", "1.2"}, {"wait", "a1000", "--timeout", "-2"}, {"wait", "a1000", "--timeout", "1", "extra"},
		{"close"}, {"close", "a1000", "a1000"}, {"close", "../a1000"},
		{"template"}, {"template", "validate", "--set", "a=b"}, {"template", "render"}, {"template", "render", "x", "--template", "x"}, {"template", "render", "x", "extra"},
	}
	for _, args := range cases {
		code, out, err := call(t, "result", args...)
		if code != 1 || out != "" || !strings.HasPrefix(err, "sendy: ") {
			t.Errorf("args %v: (%d,%q,%q)", args, code, out, err)
		}
	}
	if _, err := os.Stat(filepath.Join(os.Getenv("HOME"), ".sendy")); !os.IsNotExist(err) {
		t.Errorf("argument validation changed state: %v", err)
	}
	if out := mustCall(t, "", "--version"); out != "sendy "+version+"\n" {
		t.Fatal(out)
	}
	if got := mustCall(t, "", "create", "0002"); got != "a1000 a1001\n" {
		t.Fatal(got)
	}
	for _, input := range []string{"", string([]byte{0xff})} {
		code, out, err := call(t, input, "submit", "a1000")
		if code != 1 || out != "" || !strings.Contains(err, "message must") {
			t.Fatal(code, out, err)
		}
	}
	checkError(t, execute([]string{"submit", "a1000"}, brokenIO{}, io.Discard), "read failed")
	for _, args := range [][]string{{"--version"}, {"create", "1"}, {"wait", "a1000", "--timeout", "1"}} {
		if args[0] == "wait" {
			mustCall(t, "", "close", "a1000")
		}
		checkError(t, execute(args, strings.NewReader(""), brokenIO{}), "write failed")
	}
}

func TestConversationRounds(t *testing.T) {
	isolated(t)
	s := testStore(t)
	ids, err := s.create(3)
	if err != nil {
		t.Fatal(err)
	}
	checkError(t, s.reply(ids[0], "early"), "no result")
	checkError(t, s.reply("z1099", "missing"), "unknown")
	if _, err = s.submit("z1099", "missing"); err == nil {
		t.Fatal("unknown submit succeeded")
	}
	if _, err = s.snapshot([]string{"z1099"}); err == nil {
		t.Fatal("unknown wait succeeded")
	}
	original := "  result\n\"quoted\"\\$100\x00世界"
	for round := 1; round <= 4; round++ {
		done := make(chan struct{})
		var code int
		var out, diag string
		go func() { code, out, diag = call(t, original, "submit", ids[0]); close(done) }()
		ready(t, s, ids[:1])
		select {
		case <-done:
			t.Fatal("submit did not block")
		default:
		}
		again, err := s.snapshot(ids[:1])
		if err != nil || again.Results[0].Message != original {
			t.Fatal(again, err)
		}
		if _, err = s.submit(ids[0], "duplicate"); err == nil {
			t.Fatal("second submit accepted")
		}
		for i := 0; i < 2; i++ {
			text := mustCall(t, "", "wait", ids[0], "--timeout", "1")
			if !strings.Contains(text, `"status":"ready"`) {
				t.Fatal(text)
			}
		}
		next := "next = {{.literal}}\n\x00世界"
		mustCall(t, next, "reply", ids[0])
		select {
		case <-done:
		case <-time.After(5 * time.Second):
			t.Fatal("reply failed to release submit")
		}
		if code != 0 || out != next || diag != "" {
			t.Fatal(code, out, diag)
		}
		snap, err := s.wait(ids[:1], time.Now().Add(2*time.Millisecond))
		if err != nil || snap.Status != "timeout" || len(snap.Results) != 0 {
			t.Fatal(snap, err)
		}
	}
	// Unknown IDs cannot partially close a valid conversation.
	checkError(t, s.close([]string{ids[0], "z1099"}), "unknown")
	snap, err := s.snapshot(ids[:1])
	if err != nil || len(snap.Closed) > 0 {
		t.Fatal(snap, err)
	}
	r, err := s.submit(ids[0], "final")
	if err != nil {
		t.Fatal(err)
	}
	if err = s.close(ids[:2]); err != nil {
		t.Fatal(err)
	}
	if _, err = s.awaitReply(ids[0], r); !errors.Is(err, errClosed) {
		t.Fatal(err)
	}
	code, out, diag := call(t, "later", "submit", ids[0])
	if code != 2 || out != "" || (!strings.HasPrefix(diag, "sendy: conversation closed\n") || !strings.Contains(diag, "End the child session")) {
		t.Fatal(code, out, diag)
	}
	code, out, diag = call(t, "later", "reply", ids[0])
	if code != 1 || out != "" {
		t.Fatal(code, out, diag)
	}
	mustCall(t, "", "close", ids[0], ids[1])
	// Accepted replies survive closure, even when a later round exists.
	r, err = s.submit(ids[2], "one")
	if err != nil {
		t.Fatal(err)
	}
	if err = s.reply(ids[2], "accepted"); err != nil {
		t.Fatal(err)
	}
	r2, err := s.submit(ids[2], "two")
	if err != nil {
		t.Fatal(err)
	}
	if err = s.reply(ids[2], "second"); err != nil {
		t.Fatal(err)
	}
	if err = s.close(ids[2:]); err != nil {
		t.Fatal(err)
	}
	for round, want := range map[submission]string{r: "accepted", r2: "second"} {
		got, err := s.awaitReply(ids[2], round)
		if err != nil || got != want {
			t.Fatal(got, err)
		}
	}
	snap, err = s.snapshot([]string{ids[2], ids[0], ids[1]})
	if err != nil || strings.Join(snap.Closed, " ") != "a1002 a1000 a1001" || snap.Status != "ready" {
		t.Fatal(snap, err)
	}
}

func TestSnapshotOrderAndWake(t *testing.T) {
	isolated(t)
	s := testStore(t)
	ids, err := s.create(5)
	if err != nil {
		t.Fatal(err)
	}
	for _, id := range []string{ids[0], ids[3]} {
		if _, err = s.submit(id, id); err != nil {
			t.Fatal(err)
		}
	}
	if err = s.close(ids[2:3]); err != nil {
		t.Fatal(err)
	}
	snap, err := s.wait([]string{ids[4], ids[3], ids[2], ids[1], ids[0]}, time.Now().Add(time.Millisecond))
	if err != nil || snap.Status != "timeout" || strings.Join(snap.Pending, " ") != "a1004 a1001" || snap.Results[0].ID != "a1003" || snap.Results[1].ID != "a1000" || strings.Join(snap.Closed, " ") != "a1002" {
		t.Fatal(snap, err)
	}
	done := make(chan error, 1)
	go func() { _, err := s.wait(ids, time.Now().Add(time.Second)); done <- err }()
	time.Sleep(30 * time.Millisecond)
	if err = s.close([]string{ids[1], ids[4]}); err != nil {
		t.Fatal(err)
	}
	if err = <-done; err != nil {
		t.Fatal(err)
	}
}

func TestCapacity(t *testing.T) {
	isolated(t)
	s := testStore(t)
	if _, err := s.create(idCapacity + 1); err == nil {
		t.Fatal("capacity overrun")
	}
	seedIDs(t, s, idCapacity-2, time.Now())
	if _, err := s.create(3); err == nil {
		t.Fatal("partial capacity overrun")
	}
	ids, err := s.create(2)
	if err != nil || strings.Join(ids, " ") != "z9998 z9999" {
		t.Fatal(len(ids), err)
	}
	if err = s.close(ids); err != nil {
		t.Fatal(err)
	}
	if _, err = s.create(1); err == nil {
		t.Fatal("reused closed ID")
	}
}

func TestStorageErrors(t *testing.T) {
	dir := isolated(t)
	t.Setenv("HOME", "")
	if _, err := openStore(); err == nil {
		t.Fatal("missing home accepted")
	}
	t.Setenv("HOME", dir)
	put(t, filepath.Join(dir, ".sendy"), "file")
	if _, err := openStore(); err == nil {
		t.Fatal("file as directory accepted")
	}
	os.Remove(filepath.Join(dir, ".sendy"))
	path := filepath.Join(dir, ".sendy", "conversations.db")
	if err := os.MkdirAll(path, 0700); err != nil {
		t.Fatal(err)
	}
	if _, err := openStore(); err == nil {
		t.Fatal("directory as DB accepted")
	}
	os.Remove(path)
	put(t, path, "not a SQLite database")
	if _, err := openStore(); err == nil {
		t.Fatal("corrupt database accepted")
	}
	os.Remove(path)
	s := testStore(t)
	s.db.Close()
	if _, err := s.create(1); err == nil {
		t.Fatal("closed DB create")
	}
	if _, err := s.submit("a1000", "x"); err == nil {
		t.Fatal("closed DB submit")
	}
	if err := s.reply("a1000", "x"); err == nil {
		t.Fatal("closed DB reply")
	}
	if err := s.close([]string{"a1000"}); err == nil {
		t.Fatal("closed DB close")
	}
	if _, err := s.snapshot([]string{"a1000"}); err == nil {
		t.Fatal("closed DB snapshot")
	}
	if _, err := s.awaitReply("a1000", submission{round: 1}); err == nil {
		t.Fatal("closed DB await")
	}
	code, out, diag := call(t, "", "wait", "z1099", "--timeout", "1")
	if code != 1 || out != "" || !strings.Contains(diag, "unknown") {
		t.Fatal(code, out, diag)
	}
	// SQL triggers exercise real transactional write failures and rollback behavior.
	s = testStore(t)
	ids, err := s.create(1)
	if err != nil {
		t.Fatal(err)
	}
	_, err = s.db.Exec(`CREATE TRIGGER block_update BEFORE UPDATE ON conversations BEGIN SELECT RAISE(ABORT, 'blocked update'); END`)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = s.submit(ids[0], "x"); err == nil {
		t.Fatal("trigger did not fail submit")
	}
	if err = s.close(ids); err == nil {
		t.Fatal("trigger did not fail close")
	}
	s.db.Exec(`DROP TRIGGER block_update`)
	round, err := s.submit(ids[0], "x")
	if err != nil {
		t.Fatal(err)
	}
	s.db.Exec(`CREATE TRIGGER block_update BEFORE UPDATE ON conversations BEGIN SELECT RAISE(ABORT, 'blocked update'); END`)
	if err = s.reply(ids[0], "x"); err == nil {
		t.Fatal("trigger did not fail reply")
	}
	s.db.Exec(`DROP TRIGGER block_update`)
	s.db.Exec(`CREATE TRIGGER block_reply BEFORE INSERT ON replies BEGIN SELECT RAISE(ABORT, 'blocked reply'); END`)
	if err = s.reply(ids[0], "x"); err == nil {
		t.Fatal("reply insert should fail")
	}
	s.db.Exec(`DROP TRIGGER block_reply`)
	if err = s.reply(ids[0], "ok"); err != nil {
		t.Fatal(err)
	}
	if _, err = s.awaitReply(ids[0], round); err != nil {
		t.Fatal(err)
	}
	s.db.Exec(`CREATE TRIGGER block_create BEFORE INSERT ON conversations BEGIN SELECT RAISE(ABORT, 'blocked create'); END`)
	if _, err = s.create(1); err == nil {
		t.Fatal("create insert should fail")
	}
}

func TestOperationalFailures(t *testing.T) {
	dir := isolated(t)
	put(t, filepath.Join(dir, ".sendy"), "not a directory")
	checkError(t, execute([]string{"create", "1"}, strings.NewReader(""), io.Discard), "not a directory")
	if err := os.Remove(filepath.Join(dir, ".sendy")); err != nil {
		t.Fatal(err)
	}
	s := testStore(t)
	if _, err := s.db.Exec(`DROP TABLE conversations`); err != nil {
		t.Fatal(err)
	}
	if _, err := s.create(1); err == nil {
		t.Fatal("missing table not reported")
	}
	// A removed working directory is a real template lookup failure.
	gone := filepath.Join(dir, "gone")
	if err := os.Mkdir(gone, 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.Chdir(gone); err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(gone); err != nil {
		t.Fatal(err)
	}
	if err := validateTemplates(); err == nil {
		t.Fatal("deleted cwd not reported")
	}
}
