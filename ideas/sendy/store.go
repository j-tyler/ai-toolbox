package main

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"time"

	"modernc.org/sqlite"
	"modernc.org/sqlite/lib"
)

var errClosed = errors.New("conversation closed")

type store struct{ db *sql.DB }
type result struct {
	ID      string `json:"id"`
	Message string `json:"message"`
}
type snapshot struct {
	Status  string   `json:"status"`
	Results []result `json:"results"`
	Pending []string `json:"pending"`
	Closed  []string `json:"closed"`
}

func openStore() (*store, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return nil, err
	}
	dir := filepath.Join(home, ".sendy")
	if err = os.MkdirAll(dir, 0700); err != nil {
		return nil, err
	}
	path := filepath.Join(dir, "conversations.db")
	// Create privately before SQLite opens it; SQLite's default file mode is broader.
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return nil, err
	}
	if err = f.Close(); err != nil {
		return nil, err
	}
	u := url.URL{Scheme: "file", Path: path}
	db, err := sql.Open("sqlite", u.String()+"?_pragma=busy_timeout(10000)&_txlock=immediate")
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(1)
	if err = enableWAL(db, 10*time.Second); err != nil {
		db.Close()
		return nil, err
	}
	for _, query := range []string{
		`CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, closed INTEGER NOT NULL DEFAULT 0, round INTEGER NOT NULL DEFAULT 0, result TEXT)`,
		`CREATE TABLE IF NOT EXISTS replies (id TEXT NOT NULL, round INTEGER NOT NULL, message TEXT NOT NULL, PRIMARY KEY(id,round))`,
	} {
		if _, err = db.Exec(query); err != nil {
			db.Close()
			return nil, err
		}
	}
	return &store{db}, nil
}

func enableWAL(db *sql.DB, timeout time.Duration) error {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	for {
		_, err := db.ExecContext(ctx, `PRAGMA journal_mode=WAL`)
		var sqliteErr *sqlite.Error
		// Concurrent first use can fail this pragma without invoking SQLite's
		// busy handler. Retry only initialization, never a message transaction.
		if !errors.As(err, &sqliteErr) || (sqliteErr.Code()&255 != sqlite3.SQLITE_BUSY && sqliteErr.Code()&255 != sqlite3.SQLITE_LOCKED) {
			return err
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(20 * time.Millisecond):
		}
	}
}

func (s *store) create(count int) ([]string, error) {
	tx, err := s.db.Begin()
	if err != nil {
		return nil, err
	}
	defer tx.Rollback()
	rows, err := tx.Query(`SELECT id FROM conversations`)
	if err != nil {
		return nil, err
	}
	used := map[string]bool{}
	for rows.Next() {
		var id string
		if err = rows.Scan(&id); err != nil {
			rows.Close()
			return nil, err
		}
		used[id] = true
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return nil, err
	}
	if count > 2600-len(used) {
		return nil, fmt.Errorf("not enough unused IDs: requested %d, available %d", count, 2600-len(used))
	}
	ids := make([]string, 0, count)
	for n := 0; len(ids) < count; n++ {
		id := fmt.Sprintf("%c%02d", 'a'+n/100, n%100)
		if !used[id] {
			if _, err = tx.Exec(`INSERT INTO conversations(id) VALUES(?)`, id); err != nil {
				return nil, err
			}
			ids = append(ids, id)
		}
	}
	return ids, tx.Commit()
}

func state(tx *sql.Tx, id string) (closed bool, round int, message sql.NullString, err error) {
	err = tx.QueryRow(`SELECT closed,round,result FROM conversations WHERE id=?`, id).Scan(&closed, &round, &message)
	if errors.Is(err, sql.ErrNoRows) {
		err = fmt.Errorf("unknown conversation %q", id)
	}
	return
}

func (s *store) submit(id, message string) (int, error) {
	tx, err := s.db.Begin()
	if err != nil {
		return 0, err
	}
	defer tx.Rollback()
	closed, round, previous, err := state(tx, id)
	if err != nil {
		return 0, err
	}
	if closed {
		return 0, errClosed
	}
	if previous.Valid {
		return 0, fmt.Errorf("conversation %s already has an outstanding submission", id)
	}
	round++
	_, err = tx.Exec(`UPDATE conversations SET round=?,result=? WHERE id=?`, round, message, id)
	if err != nil {
		return 0, err
	}
	return round, tx.Commit()
}

func (s *store) reply(id, message string) error {
	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	closed, round, previous, err := state(tx, id)
	if err != nil {
		return err
	}
	if closed {
		return errClosed
	}
	if !previous.Valid {
		return fmt.Errorf("conversation %s has no result ready for a reply", id)
	}
	if _, err = tx.Exec(`INSERT INTO replies(id,round,message) VALUES(?,?,?)`, id, round, message); err != nil {
		return err
	}
	if _, err = tx.Exec(`UPDATE conversations SET result=NULL WHERE id=?`, id); err != nil {
		return err
	}
	return tx.Commit()
}

func (s *store) awaitReply(id string, round int) (string, error) {
	for {
		var closed bool
		var message sql.NullString
		// One SQLite snapshot makes accepted replies take precedence over closure.
		err := s.db.QueryRow(`SELECT c.closed, r.message FROM conversations c
			LEFT JOIN replies r ON r.id=c.id AND r.round=? WHERE c.id=?`, round, id).Scan(&closed, &message)
		if err != nil {
			return "", err
		}
		if message.Valid {
			return message.String, nil
		}
		if closed {
			return "", errClosed
		}
		time.Sleep(20 * time.Millisecond)
	}
}

func (s *store) snapshot(ids []string) (snapshot, error) {
	out := snapshot{Status: "ready", Results: []result{}, Pending: []string{}, Closed: []string{}}
	tx, err := s.db.Begin()
	if err != nil {
		return out, err
	}
	defer tx.Rollback()
	for _, id := range ids {
		closed, _, message, e := state(tx, id)
		if e != nil {
			return out, e
		}
		if closed {
			out.Closed = append(out.Closed, id)
		} else if message.Valid {
			out.Results = append(out.Results, result{id, message.String})
		} else {
			out.Pending = append(out.Pending, id)
		}
	}
	if len(out.Pending) > 0 {
		out.Status = "timeout"
	}
	return out, tx.Commit()
}

func (s *store) wait(ids []string, deadline time.Time) (snapshot, error) {
	for {
		out, err := s.snapshot(ids)
		if err != nil || len(out.Pending) == 0 || !time.Now().Before(deadline) {
			return out, err
		}
		delay := time.Until(deadline)
		if delay > 20*time.Millisecond {
			delay = 20 * time.Millisecond
		}
		time.Sleep(delay)
	}
}

func (s *store) close(ids []string) error {
	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	for _, id := range ids {
		if _, _, _, err = state(tx, id); err != nil {
			return err
		}
	}
	for _, id := range ids {
		if _, err = tx.Exec(`UPDATE conversations SET closed=1,result=NULL WHERE id=?`, id); err != nil {
			return err
		}
	}
	return tx.Commit()
}
