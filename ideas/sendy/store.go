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

const idCapacity = 26 * 9000
const retention = 14 * 24 * time.Hour
const replyHeartbeatInterval = time.Minute

type store struct{ db *sql.DB }
type submission struct {
	round      int
	generation string
}
type conversation struct {
	closed bool
	submission
	message sql.NullString
}
type result struct {
	ID      string `json:"id"`
	Message string `json:"message"`
}
type snapshot struct {
	Status      string   `json:"status"`
	Results     []result `json:"results"`
	Pending     []string `json:"pending"`
	Closed      []string `json:"closed"`
	generations map[string]string
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
	s := &store{db}
	if err = s.initialize(); err == nil {
		err = s.cleanup(time.Now())
	}
	if err != nil {
		db.Close()
		return nil, err
	}
	return s, nil
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
	if count > idCapacity-len(used) {
		return nil, fmt.Errorf("not enough unused IDs: requested %d, available %d", count, idCapacity-len(used))
	}
	ids := make([]string, 0, count)
	for n := 0; len(ids) < count; n++ {
		id := fmt.Sprintf("%c%d", 'a'+n/9000, 1000+n%9000)
		if !used[id] {
			if _, err = tx.Exec(`INSERT INTO conversations(id,last_used,generation) VALUES(?,unixepoch(),lower(hex(randomblob(16))))`, id); err != nil {
				return nil, err
			}
			ids = append(ids, id)
		}
	}
	return ids, tx.Commit()
}

func state(tx *sql.Tx, id string) (c conversation, err error) {
	err = tx.QueryRow(`SELECT closed,round,result,generation FROM conversations WHERE id=?`, id).Scan(&c.closed, &c.round, &c.message, &c.generation)
	if errors.Is(err, sql.ErrNoRows) {
		err = fmt.Errorf("unknown conversation %q", id)
	}
	if err == nil {
		err = touch(tx, id)
	}
	return
}

func touch(tx *sql.Tx, id string) error {
	// Explicit operations and heartbeat transactions record activity. At most
	// one timestamp write per ID per second.
	_, err := tx.Exec(`UPDATE conversations SET last_used=unixepoch() WHERE id=? AND last_used<unixepoch()`, id)
	return err
}

func (s *store) submit(id, message string) (submission, error) {
	tx, err := s.db.Begin()
	if err != nil {
		return submission{}, err
	}
	defer tx.Rollback()
	c, err := state(tx, id)
	if err != nil {
		return submission{}, err
	}
	if c.closed {
		return submission{}, errClosed
	}
	if c.message.Valid {
		return submission{}, fmt.Errorf("conversation %s already has an outstanding submission", id)
	}
	c.round++
	_, err = tx.Exec(`UPDATE conversations SET round=?,result=? WHERE id=?`, c.round, message, id)
	if err != nil {
		return submission{}, err
	}
	return c.submission, tx.Commit()
}

func (s *store) reply(id, message string) error {
	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	c, err := state(tx, id)
	if err != nil {
		return err
	}
	if c.closed {
		return errClosed
	}
	if !c.message.Valid {
		return fmt.Errorf("conversation %s has no result ready for a reply", id)
	}
	if _, err = tx.Exec(`INSERT INTO replies(id,round,message) VALUES(?,?,?)`, id, c.round, message); err != nil {
		return err
	}
	if _, err = tx.Exec(`UPDATE conversations SET result=NULL WHERE id=?`, id); err != nil {
		return err
	}
	return tx.Commit()
}

func (s *store) readReply(id string, round submission) (string, bool, error) {
	var closed bool
	var generation string
	var message sql.NullString
	var heartbeatDue bool
	read := func(q interface{ QueryRow(string, ...any) *sql.Row }) error {
		err := q.QueryRow(`SELECT c.closed, c.generation, r.message, c.last_used<=unixepoch()-?
			FROM conversations c LEFT JOIN replies r ON r.id=c.id AND r.round=? WHERE c.id=?`,
			int64(replyHeartbeatInterval/time.Second), round.round, id).Scan(&closed, &generation, &message, &heartbeatDue)
		if errors.Is(err, sql.ErrNoRows) || (err == nil && generation != round.generation) {
			return expired(id)
		}
		return err
	}
	// Most 20 ms polls are read-only. Share the heartbeat timestamp across
	// processes so blocked submissions do not continually take the writer lock.
	if err := read(s.db); err != nil {
		return "", false, err
	}
	if heartbeatDue {
		tx, err := s.db.Begin()
		if err != nil {
			return "", false, err
		}
		defer tx.Rollback()
		// Cleanup may have recycled the ID after the first read. Recheck its
		// generation and reply inside the same transaction as the heartbeat.
		if err = read(tx); err != nil {
			return "", false, err
		}
		if heartbeatDue {
			if err = touch(tx, id); err != nil {
				return "", false, err
			}
		}
		if err = tx.Commit(); err != nil {
			return "", false, err
		}
	}
	// Accepted replies still take precedence over closure.
	if message.Valid {
		return message.String, true, nil
	}
	if closed {
		return "", false, errClosed
	}
	return "", false, nil
}

func expired(id string) error {
	return fmt.Errorf("conversation %q expired", id)
}

func (s *store) awaitReply(id string, round submission) (string, error) {
	for {
		message, ready, err := s.readReply(id, round)
		if err != nil || ready {
			return message, err
		}
		time.Sleep(20 * time.Millisecond)
	}
}

func (s *store) snapshot(ids []string) (snapshot, error) {
	out := snapshot{Status: "ready", Results: []result{}, Pending: []string{}, Closed: []string{}, generations: map[string]string{}}
	tx, err := s.db.Begin()
	if err != nil {
		return out, err
	}
	defer tx.Rollback()
	for _, id := range ids {
		c, e := state(tx, id)
		if e != nil {
			return out, e
		}
		out.generations[id] = c.generation
		if c.closed {
			out.Closed = append(out.Closed, id)
		} else if c.message.Valid {
			out.Results = append(out.Results, result{id, c.message.String})
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
	var generations map[string]string
	for {
		out, err := s.snapshot(ids)
		if err == nil {
			for id, generation := range generations {
				if out.generations[id] != generation {
					return out, expired(id)
				}
			}
			generations = out.generations
		}
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
		if _, err = state(tx, id); err != nil {
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
