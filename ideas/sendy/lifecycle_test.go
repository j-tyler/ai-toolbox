package main

import (
	"database/sql"
	"errors"
	"path/filepath"
	"testing"
	"time"
)

// Populate the real namespace efficiently so capacity tests exercise the real
// threshold without hundreds of thousands of individual CLI calls.
func seedIDs(t *testing.T, s *store, count int, now time.Time) {
	t.Helper()
	execSQL(t, s, `WITH RECURSIVE ids(n) AS (VALUES(0) UNION ALL SELECT n+1 FROM ids WHERE n+1<?)
		INSERT INTO conversations(id,last_used,generation)
		SELECT char(97+n/9000)||printf('%04d',1000+n%9000),?,printf('fixture-%d',n) FROM ids`, count, now.Unix())
}

func execSQL(t *testing.T, s *store, query string, args ...any) {
	t.Helper()
	if _, err := s.db.Exec(query, args...); err != nil {
		t.Fatal(err)
	}
}

func storedCount(t *testing.T, s *store) int {
	t.Helper()
	var n int
	if err := s.db.QueryRow(`SELECT count(*) FROM conversations`).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func TestIDFormatAndLetterBoundary(t *testing.T) {
	isolated(t)
	s := testStore(t)
	ids, err := s.create(9001)
	if err != nil || len(ids) != 9001 || ids[0] != "a1000" || ids[8999] != "a9999" || ids[9000] != "b1000" {
		t.Fatal(len(ids), err)
	}
	seen := map[string]bool{}
	for _, id := range ids {
		if !idPattern.MatchString(id) || seen[id] {
			t.Fatalf("invalid or duplicated new ID %q", id)
		}
		seen[id] = true
	}
	for _, id := range []string{"k07", "a00", "z99", "a0000", "a0999", "a999", "a10000", "A1000", "11000", "a１２３４"} {
		checkError(t, identifiers([]string{id}), "four digits (1000–9999)")
	}
	if err := identifiers([]string{"a1000", "z9999"}); err != nil {
		t.Fatal(err)
	}
}

func TestDailyCleanupThreshold(t *testing.T) {
	isolated(t)
	s := testStore(t)
	now := time.Date(2030, 1, 2, 12, 0, 0, 0, time.UTC)
	seedIDs(t, s, idCapacity/2, now)
	execSQL(t, s, `UPDATE conversations SET last_used=? WHERE id='a1000'`, now.Add(-retention).Unix())
	if err := s.cleanup(now); err != nil {
		t.Fatal(err)
	}
	if n := storedCount(t, s); n != idCapacity/2 {
		t.Fatalf("cleanup ran at exactly 50%%: %d", n)
	}
	ids, err := s.create(1)
	if err != nil {
		t.Fatal(err)
	}
	execSQL(t, s, `UPDATE conversations SET last_used=? WHERE id=?`, now.Unix(), ids[0])
	// Crossing the threshold later in the day must not repeat the check.
	if err = s.cleanup(now.Add(time.Hour)); err != nil {
		t.Fatal(err)
	}
	if n := storedCount(t, s); n != idCapacity/2+1 {
		t.Fatalf("cleanup repeated on the same day: %d", n)
	}
	if err = s.cleanup(now.Add(24 * time.Hour)); err != nil {
		t.Fatal(err)
	}
	if n := storedCount(t, s); n != idCapacity/2 {
		t.Fatalf("next day's cleanup did not reclaim the idle ID: %d", n)
	}
	ids, err = s.create(1)
	if err != nil || ids[0] != "a1000" {
		t.Fatal("ID not reused", ids, err)
	}
}

func TestCleanupBoundariesAndRollback(t *testing.T) {
	isolated(t)
	s := testStore(t)
	now := time.Date(2030, 2, 3, 0, 0, 0, 0, time.UTC)
	seedIDs(t, s, idCapacity/2+1, now)
	cutoff := now.Add(-retention).Unix()
	execSQL(t, s, `UPDATE conversations SET last_used=?,result='abandoned result' WHERE id='a1000'`, cutoff)
	execSQL(t, s, `UPDATE conversations SET last_used=?,closed=1 WHERE id='a1001'`, cutoff-1)
	execSQL(t, s, `UPDATE conversations SET last_used=? WHERE id='a1002'`, cutoff+1)
	execSQL(t, s, `INSERT INTO replies VALUES('a1001',1,'old reply'),('a1002',1,'keep reply')`)
	execSQL(t, s, `CREATE TRIGGER block_delete BEFORE DELETE ON conversations BEGIN SELECT RAISE(ABORT,'blocked deletion'); END`)
	checkError(t, s.cleanup(now), "blocked deletion")
	var replies int
	if err := s.db.QueryRow(`SELECT count(*) FROM replies`).Scan(&replies); err != nil || replies != 2 {
		t.Fatal("reply deletion was not rolled back", replies, err)
	}
	execSQL(t, s, `DROP TRIGGER block_delete`)
	// A failed cleanup must not consume the day's attempt. Check UTC even when
	// this process's local date is the preceding day.
	if err := s.cleanup(now.In(time.FixedZone("west", -8*3600))); err != nil {
		t.Fatal(err)
	}
	if n := storedCount(t, s); n != idCapacity/2-1 {
		t.Fatal("incorrect age cutoff", n)
	}
	var reply, day string
	if err := s.db.QueryRow(`SELECT message FROM replies`).Scan(&reply); err != nil || reply != "keep reply" {
		t.Fatal(reply, err)
	}
	if err := s.db.QueryRow(`SELECT last_cleanup_day FROM maintenance`).Scan(&day); err != nil || day != "2030-02-03" {
		t.Fatal(day, err)
	}
	for _, id := range []string{"a1000", "a1001"} {
		_, err := s.wait([]string{id}, time.Now())
		checkError(t, err, "unknown conversation")
	}
}

func TestActivityProtectsBlockedConversations(t *testing.T) {
	isolated(t)
	s := testStore(t)
	now := time.Now()
	seedIDs(t, s, idCapacity/2+1, now)
	round, err := s.submit("a1000", "waiting for human approval")
	if err != nil {
		t.Fatal(err)
	}
	execSQL(t, s, `UPDATE conversations SET last_used=? WHERE id IN ('a1000','a1001','a1002')`, now.Add(-2*retention).Unix())
	if _, ready, err := s.readReply("a1000", round); err != nil || ready {
		t.Fatal(ready, err)
	}
	if snap, err := s.wait([]string{"a1001"}, time.Now()); err != nil || len(snap.Pending) != 1 {
		t.Fatal(snap, err)
	}
	execSQL(t, s, `UPDATE maintenance SET last_cleanup_day=''`)
	if err := s.cleanup(time.Now()); err != nil {
		t.Fatal(err)
	}
	if n := storedCount(t, s); n != idCapacity/2 {
		t.Fatal(n)
	}
	if err := s.reply("a1000", "approved after weeks"); err != nil {
		t.Fatal(err)
	}
	if got, err := s.awaitReply("a1000", round); err != nil || got != "approved after weeks" {
		t.Fatal(got, err)
	}
	if _, err := s.snapshot([]string{"a1001"}); err != nil {
		t.Fatal("wait did not keep its conversation alive", err)
	}
	if _, err := s.snapshot([]string{"a1002"}); err == nil {
		t.Fatal("abandoned conversation survived cleanup")
	}
}

func TestRecycledIDCannotDeliverUnrelatedReply(t *testing.T) {
	isolated(t)
	s := testStore(t)
	ids, err := s.create(1)
	if err != nil {
		t.Fatal(err)
	}
	old, err := s.submit(ids[0], "old result")
	if err != nil {
		t.Fatal(err)
	}
	execSQL(t, s, `DELETE FROM conversations`)
	_, err = s.awaitReply(ids[0], old)
	checkError(t, err, "expired")
	ids, err = s.create(1)
	if err != nil {
		t.Fatal(err)
	}
	current, err := s.submit(ids[0], "unrelated result")
	if err != nil || old.round != current.round || old.generation == current.generation {
		t.Fatal(old, current, err)
	}
	if err := s.reply(ids[0], "unrelated instruction"); err != nil {
		t.Fatal(err)
	}
	_, err = s.awaitReply(ids[0], old)
	checkError(t, err, "expired")
	if got, err := s.awaitReply(ids[0], current); err != nil || got != "unrelated instruction" {
		t.Fatal(got, err)
	}
}

func TestWaitRejectsRecycledID(t *testing.T) {
	isolated(t)
	s := testStore(t)
	ids, err := s.create(1)
	if err != nil {
		t.Fatal(err)
	}
	execSQL(t, s, `UPDATE conversations SET last_used=0`)
	done := make(chan error, 1)
	go func() { _, err := s.wait(ids, time.Now().Add(5*time.Second)); done <- err }()
	deadline := time.Now().Add(5 * time.Second)
	for {
		var touched int64
		if err := s.db.QueryRow(`SELECT last_used FROM conversations`).Scan(&touched); err != nil {
			t.Fatal(err)
		}
		if touched != 0 {
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("wait did not start")
		}
		time.Sleep(time.Millisecond)
	}
	execSQL(t, s, `UPDATE conversations SET generation='replacement',result='unrelated result'`)
	checkError(t, <-done, "expired")
}

func TestReopenPreservesConversationActivity(t *testing.T) {
	isolated(t)
	s := testStore(t)
	ids, err := s.create(1)
	if err != nil {
		t.Fatal(err)
	}
	round, err := s.submit(ids[0], "saved result")
	if err != nil {
		t.Fatal(err)
	}
	execSQL(t, s, `UPDATE conversations SET last_used=123`)
	other := testStore(t)
	var generation, message string
	var lastUsed int64
	if err := other.db.QueryRow(`SELECT last_used,generation,result FROM conversations WHERE id=?`, ids[0]).Scan(&lastUsed, &generation, &message); err != nil || lastUsed != 123 || generation != round.generation || message != "saved result" {
		t.Fatal(lastUsed, generation, message, err)
	}
}

func TestLifecycleStorageFailures(t *testing.T) {
	for _, test := range []struct {
		name  string
		setup string
		check func(*store) error
		want  string
	}{
		{"newer schema", `PRAGMA user_version=2`, (*store).initialize, "unsupported"},
		{"missing metadata", `DROP TABLE maintenance`, func(s *store) error { return s.cleanup(time.Now()) }, "no such table"},
		{"missing conversations", `UPDATE maintenance SET last_cleanup_day=''; DROP TABLE conversations`, func(s *store) error { return s.cleanup(time.Now()) }, "no such table"},
		{"failed day marker", `UPDATE maintenance SET last_cleanup_day=''; CREATE TRIGGER block_day BEFORE UPDATE ON maintenance BEGIN SELECT RAISE(ABORT,'blocked day'); END`, func(s *store) error { return s.cleanup(time.Now()) }, "blocked day"},
	} {
		t.Run(test.name, func(t *testing.T) {
			isolated(t)
			s := testStore(t)
			execSQL(t, s, test.setup)
			checkError(t, test.check(s), test.want)
			if _, err := openStore(); err == nil {
				t.Fatal("opening a broken store succeeded")
			}
		})
	}
	t.Run("closed database", func(t *testing.T) {
		isolated(t)
		s := testStore(t)
		s.db.Close()
		checkError(t, s.initialize(), "closed")
		checkError(t, s.cleanup(time.Now()), "closed")
	})
}

func TestInitializationFailureIsAtomic(t *testing.T) {
	home := isolated(t)
	path := filepath.Join(home, ".sendy", "conversations.db")
	put(t, path, "")
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	s := &store{db}
	execSQL(t, s, `CREATE TABLE maintenance(singleton INTEGER)`)
	checkError(t, s.initialize(), "already exists")
	var version, tables int
	if err := db.QueryRow(`PRAGMA user_version`).Scan(&version); err != nil || version != 0 {
		t.Fatal("failed initialization changed schema version", version, err)
	}
	if err := db.QueryRow(`SELECT count(*) FROM sqlite_master WHERE type='table' AND name IN ('conversations','replies')`).Scan(&tables); err != nil || tables != 0 {
		t.Fatal("failed initialization left partial tables", tables, err)
	}
	execSQL(t, s, `DROP TABLE maintenance`)
	if err := s.initialize(); err != nil {
		t.Fatal("initialization could not retry", err)
	}
	if ids, err := s.create(1); err != nil || ids[0] != "a1000" {
		t.Fatal(ids, err)
	}
}

func TestActivityIsTransactional(t *testing.T) {
	isolated(t)
	s := testStore(t)
	ids, err := s.create(1)
	if err != nil {
		t.Fatal(err)
	}
	for _, action := range []func() error{
		func() error { _, err := s.submit(ids[0], "result"); return err },
		func() error { return s.reply(ids[0], "next instruction") },
		func() error { return s.close(ids) },
	} {
		execSQL(t, s, `UPDATE conversations SET last_used=123`)
		if err := action(); err != nil {
			t.Fatal(err)
		}
		var used int64
		if err := s.db.QueryRow(`SELECT last_used FROM conversations`).Scan(&used); err != nil || used < time.Now().Add(-time.Minute).Unix() {
			t.Fatal("accepted command did not refresh activity", used, err)
		}
	}
	execSQL(t, s, `UPDATE conversations SET last_used=123`)
	checkError(t, s.close([]string{ids[0], "z9999"}), "unknown")
	var used int64
	if err := s.db.QueryRow(`SELECT last_used FROM conversations`).Scan(&used); err != nil || used != 123 {
		t.Fatal("failed command changed activity", used, err)
	}
}

func TestReplyActivityFailureDoesNotDeliverMessage(t *testing.T) {
	isolated(t)
	s := testStore(t)
	ids, err := s.create(1)
	if err != nil {
		t.Fatal(err)
	}
	round, err := s.submit(ids[0], "result")
	if err != nil {
		t.Fatal(err)
	}
	if err := s.reply(ids[0], "instruction"); err != nil {
		t.Fatal(err)
	}
	execSQL(t, s, `UPDATE conversations SET last_used=0;
		CREATE TRIGGER block_activity BEFORE UPDATE ON conversations BEGIN SELECT RAISE(ABORT,'blocked activity'); END;`)
	_, err = s.awaitReply(ids[0], round)
	checkError(t, err, "blocked activity")
	execSQL(t, s, `DROP TRIGGER block_activity`)
	if got, err := s.awaitReply(ids[0], round); err != nil || got != "instruction" {
		t.Fatal(got, err)
	}
	execSQL(t, s, `DROP TABLE replies`)
	_, err = s.awaitReply(ids[0], round)
	checkError(t, err, "no such table")
}

func TestRecentReplyPollsDoNotNeedWriterLock(t *testing.T) {
	isolated(t)
	s := testStore(t)
	ids, err := s.create(3)
	if err != nil {
		t.Fatal(err)
	}
	rounds := make([]submission, len(ids))
	for i, id := range ids {
		rounds[i], err = s.submit(id, "result")
		if err != nil {
			t.Fatal(err)
		}
	}
	if err := s.reply(ids[0], "committed reply"); err != nil {
		t.Fatal(err)
	}
	if err := s.close(ids[1:2]); err != nil {
		t.Fatal(err)
	}
	// Activity older than one second must still use the read-only path.
	execSQL(t, s, `UPDATE conversations SET last_used=unixepoch()-?`, int64(replyHeartbeatInterval/(2*time.Second)))
	writer := testStore(t)
	execSQL(t, s, `PRAGMA busy_timeout=25`)
	tx, err := writer.db.Begin()
	if err != nil {
		t.Fatal(err)
	}
	defer tx.Rollback()
	if _, err := tx.Exec(`INSERT INTO replies VALUES(?,?,?)`, ids[2], rounds[2].round, "uncommitted reply"); err != nil {
		t.Fatal(err)
	}
	// WAL readers can poll committed state while an unrelated writer holds the
	// single writer lock. No recent poll should need a write transaction.
	for i := 0; i < 10; i++ {
		if got, ready, err := s.readReply(ids[0], rounds[0]); err != nil || !ready || got != "committed reply" {
			t.Fatal("ready poll blocked on writer", got, ready, err)
		}
		if _, _, err := s.readReply(ids[1], rounds[1]); !errors.Is(err, errClosed) {
			t.Fatal("closed poll blocked on writer", err)
		}
		if got, ready, err := s.readReply(ids[2], rounds[2]); err != nil || ready || got != "" {
			t.Fatal("pending poll blocked or saw uncommitted reply", got, ready, err)
		}
	}
}

func TestReplyHeartbeatRefreshesOnceWhenDue(t *testing.T) {
	isolated(t)
	s := testStore(t)
	ids, err := s.create(1)
	if err != nil {
		t.Fatal(err)
	}
	round, err := s.submit(ids[0], "result")
	if err != nil {
		t.Fatal(err)
	}
	execSQL(t, s, `UPDATE conversations SET last_used=unixepoch()-?`, int64(replyHeartbeatInterval/time.Second))
	execSQL(t, s, `CREATE TABLE heartbeats(used INTEGER);
		CREATE TRIGGER count_heartbeats AFTER UPDATE OF last_used ON conversations
		BEGIN INSERT INTO heartbeats VALUES(NEW.last_used); END;`)
	for i := 0; i < 10; i++ {
		if got, ready, err := s.readReply(ids[0], round); err != nil || ready || got != "" {
			t.Fatal(got, ready, err)
		}
	}
	var count int
	var used int64
	if err := s.db.QueryRow(`SELECT count(*),max(used) FROM heartbeats`).Scan(&count, &used); err != nil || count != 1 || used < time.Now().Add(-time.Second).Unix() {
		t.Fatal("heartbeat was missed or repeated", count, used, err)
	}
}

func TestHeartbeatRechecksGenerationAfterWriterCommit(t *testing.T) {
	isolated(t)
	s := testStore(t)
	ids, err := s.create(1)
	if err != nil {
		t.Fatal(err)
	}
	round, err := s.submit(ids[0], "old result")
	if err != nil {
		t.Fatal(err)
	}
	execSQL(t, s, `UPDATE conversations SET last_used=0`)
	writer := testStore(t)
	tx, err := writer.db.Begin()
	if err != nil {
		t.Fatal(err)
	}
	defer tx.Rollback()
	// Keep the replacement uncommitted so a read-only poll sees the old,
	// heartbeat-due generation while its following transaction waits for us.
	if _, err := tx.Exec(`UPDATE conversations SET generation='replacement'; INSERT INTO replies VALUES(?,?,'unrelated reply')`, ids[0], round.round); err != nil {
		t.Fatal(err)
	}
	done := make(chan error, 1)
	go func() {
		_, _, err := s.readReply(ids[0], round)
		done <- err
	}()
	select {
	case err := <-done:
		t.Fatal("heartbeat did not wait for the writer", err)
	case <-time.After(20 * time.Millisecond):
	}
	if err := tx.Commit(); err != nil {
		t.Fatal(err)
	}
	checkError(t, <-done, "expired")
}
