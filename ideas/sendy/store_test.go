package main

import (
	"context"
	"database/sql"
	"errors"
	"path/filepath"
	"testing"
	"time"
)

func TestWALInitializationContention(t *testing.T) {
	db, err := sql.Open("sqlite", filepath.Join(t.TempDir(), "locked.db")+"?_pragma=busy_timeout(1)")
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	db.SetMaxOpenConns(2)
	if _, err = db.Exec(`CREATE TABLE held (value TEXT)`); err != nil {
		t.Fatal(err)
	}
	reader, err := db.Begin()
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Rollback()
	var count int
	if err = reader.QueryRow(`SELECT count(*) FROM held`).Scan(&count); err != nil {
		t.Fatal(err)
	}
	// A real rollback-journal reader prevents switching the database to WAL.
	start := time.Now()
	if err = enableWAL(db, 5*time.Millisecond); !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("held reader should exhaust initialization deadline: %v", err)
	}
	if time.Since(start) > time.Second {
		t.Fatal("initialization retry exceeded its deadline")
	}
	done := make(chan error, 1)
	go func() { done <- enableWAL(db, time.Second) }()
	select {
	case err = <-done:
		t.Fatalf("initialization returned before the lock was released: %v", err)
	case <-time.After(50 * time.Millisecond):
	}
	if err = reader.Rollback(); err != nil {
		t.Fatal(err)
	}
	if err = <-done; err != nil {
		t.Fatal(err)
	}
	var mode string
	if err = db.QueryRow(`PRAGMA journal_mode`).Scan(&mode); err != nil || mode != "wal" {
		t.Fatalf("journal mode %q: %v", mode, err)
	}
}

func TestInitializationSchemaError(t *testing.T) {
	isolated(t)
	s := testStore(t)
	if _, err := s.db.Exec(`DROP TABLE conversations; CREATE INDEX conversations ON replies(id); PRAGMA user_version=0`); err != nil {
		t.Fatal(err)
	}
	if _, err := openStore(); err == nil {
		t.Fatal("conflicting schema should fail initialization")
	}
}
