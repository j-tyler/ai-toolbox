-- cloudbill database schema (version 1). `cloudbill load` applies it to a new database; applying it
-- again is harmless. Costs are stored as exact decimal text and summed in Python, so answers from the
-- database are the same, to the last digit, as answers from the export files.

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1');

-- One row per export file loaded, identified by the SHA-256 of its bytes: loading the same file again
-- is recognised and changes nothing.
CREATE TABLE IF NOT EXISTS files (
    file_id       INTEGER PRIMARY KEY,
    path          TEXT NOT NULL,
    sha256        TEXT NOT NULL UNIQUE,
    loaded_at     TEXT NOT NULL,           -- UTC, ISO 8601
    row_count     INTEGER NOT NULL,        -- usable rows in the file
    rejected_count INTEGER NOT NULL        -- rows that could not be used
);

-- The current version of every line item. A restatement (same id, later last_updated; on a tie the
-- later file and line) replaces the row in place; file_id and line say where the current version came
-- from.
CREATE TABLE IF NOT EXISTS line_items (
    line_item_id  TEXT PRIMARY KEY,
    file_id       INTEGER NOT NULL REFERENCES files (file_id),
    line          INTEGER NOT NULL,        -- physical line the row starts on
    account_id    TEXT NOT NULL,
    account_name  TEXT NOT NULL,
    service       TEXT NOT NULL,           -- as exported, whitespace stripped
    resource_id   TEXT NOT NULL,
    usage_date    TEXT NOT NULL,           -- UTC date of usage_start, YYYY-MM-DD
    usage_start   TEXT NOT NULL,           -- UTC, ISO 8601
    last_updated  TEXT NOT NULL,           -- UTC, ISO 8601, '' when absent
    kind          TEXT NOT NULL CHECK (kind IN ('usage', 'tax', 'fee', 'credit', 'refund')),
    cost          TEXT NOT NULL,           -- exact decimal
    tags          TEXT NOT NULL            -- JSON object of the non-blank tags
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS line_items_by_day ON line_items (usage_date);

-- Rows that could not be used, with the reason, so `rejects` works from the database too.
CREATE TABLE IF NOT EXISTS rejects (
    file_id       INTEGER NOT NULL REFERENCES files (file_id),
    line          INTEGER NOT NULL,
    reason        TEXT NOT NULL,
    PRIMARY KEY (file_id, line)
);
