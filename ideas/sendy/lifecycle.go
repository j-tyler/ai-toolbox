package main

import (
	"fmt"
	"time"
)

func (s *store) initialize() error {
	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	var version int
	if err = tx.QueryRow(`PRAGMA user_version`).Scan(&version); err != nil {
		return err
	}
	if version > 1 {
		return fmt.Errorf("unsupported conversation database version %d", version)
	}
	if version == 0 {
		// Serialize concurrent first use and roll back partial initialization.
		for _, query := range []string{
			`CREATE TABLE conversations (id TEXT PRIMARY KEY, closed INTEGER NOT NULL DEFAULT 0, round INTEGER NOT NULL DEFAULT 0, result TEXT, last_used INTEGER NOT NULL, generation TEXT NOT NULL)`,
			`CREATE TABLE replies (id TEXT NOT NULL, round INTEGER NOT NULL, message TEXT NOT NULL, PRIMARY KEY(id,round))`,
			`CREATE INDEX conversations_last_used ON conversations(last_used)`,
			`CREATE TABLE maintenance (singleton INTEGER PRIMARY KEY CHECK(singleton=1), last_cleanup_day TEXT NOT NULL)`,
			`INSERT INTO maintenance VALUES(1,'')`,
			`PRAGMA user_version=1`,
		} {
			if _, err = tx.Exec(query); err != nil {
				return err
			}
		}
	}
	return tx.Commit()
}

func (s *store) cleanup(now time.Time) error {
	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	var lastDay string
	if err = tx.QueryRow(`SELECT last_cleanup_day FROM maintenance WHERE singleton=1`).Scan(&lastDay); err != nil {
		return err
	}
	day := now.UTC().Format("2006-01-02")
	if lastDay >= day {
		return nil
	}
	var count int
	if err = tx.QueryRow(`SELECT count(*) FROM conversations`).Scan(&count); err != nil {
		return err
	}
	if count > idCapacity/2 {
		cutoff := now.Add(-retention).Unix()
		for _, query := range []string{
			`DELETE FROM replies WHERE id IN (SELECT id FROM conversations WHERE last_used<=?)`,
			`DELETE FROM conversations WHERE last_used<=?`,
		} {
			if _, err = tx.Exec(query, cutoff); err != nil {
				return err
			}
		}
	}
	if _, err = tx.Exec(`UPDATE maintenance SET last_cleanup_day=? WHERE singleton=1`, day); err != nil {
		return err
	}
	return tx.Commit()
}
