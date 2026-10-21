"""The SQLite store behind every answer.

``load`` reads export files row by row (``export.read_export``) and upserts them into the database
described by ``schema.sql``: a restatement replaces the stored line item only when it is newer
(``last_updated``, then file and line), so the database always holds the current version of every line
item whatever order the files arrive in. A file is identified by the SHA-256 of its bytes, so loading
it again changes nothing. One ``load`` is one transaction: a file that cannot be used rolls back the
whole command.

Questions read the current line items back with ``items`` and are answered by the same code as before
(``questions.py``); costs are exact decimal text, so the answers match the export to the last digit.
Answering straight from files loads them into a temporary database first, which is why the two give
byte-identical output.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterator

from .export import ExportError, LineItem, Reject, read_export

SCHEMA = Path(__file__).with_name("schema.sql")
BATCH = 2000

UPSERT = """
INSERT INTO line_items (line_item_id, file_id, line, account_id, account_name, service, resource_id,
                        usage_date, usage_start, last_updated, kind, cost, tags)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (line_item_id) DO UPDATE SET
    file_id = excluded.file_id, line = excluded.line, account_id = excluded.account_id,
    account_name = excluded.account_name, service = excluded.service, resource_id = excluded.resource_id,
    usage_date = excluded.usage_date, usage_start = excluded.usage_start, last_updated = excluded.last_updated,
    kind = excluded.kind, cost = excluded.cost, tags = excluded.tags
WHERE (excluded.last_updated, excluded.file_id, excluded.line)
    > (line_items.last_updated, line_items.file_id, line_items.line)
"""


class DatabaseError(ExportError):
    """The database cannot be used (missing, or not a cloudbill database). Exit code 1, like a bad file."""


def connect(path: str | Path, create: bool = False) -> sqlite3.Connection:
    path = Path(path)
    if not create and not path.is_file():
        raise DatabaseError(f"{path}: no such database (load export files into it with `cloudbill load`)")
    try:
        conn = sqlite3.connect(path, isolation_level=None)
        if create:
            conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        version = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"{path}: not a cloudbill database ({exc})") from None
    if version is None:
        raise DatabaseError(f"{path}: not a cloudbill database (no schema version)")
    return conn


def temporary() -> tuple[sqlite3.Connection, str]:
    """A throwaway database on disk (not in memory: a 2 GB export must not end up in RAM)."""
    fd, name = tempfile.mkstemp(prefix="cloudbill-", suffix=".sqlite")
    os.close(fd)
    os.unlink(name)
    conn = connect(name, create=True)
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    return conn, name


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                digest.update(block)
    except OSError as exc:
        raise ExportError(f"{path}: cannot open ({exc.strerror or exc})") from None
    return digest.hexdigest()


def _record(item: LineItem, file_id: int) -> tuple:
    return (item.line_item_id, file_id, item.order[1], item.account_id, item.account_name, item.service, item.resource_id,
            item.usage_date.isoformat(), item.usage_start, item.last_updated, item.kind, str(item.cost),
            json.dumps(dict(item.tags), sort_keys=True, ensure_ascii=False))


def load(conn: sqlite3.Connection, paths: list[str | Path]) -> list[dict]:
    """Load files in order, in one transaction. Returns one result per file given."""
    results = []
    loaded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn.execute("BEGIN IMMEDIATE")
    try:
        for given in paths:
            path = Path(given)
            if path.is_dir():
                raise ExportError(f"{path}: is a directory, not an export file")
            digest = sha256_of(path)
            known = conn.execute("SELECT path FROM files WHERE sha256 = ?", (digest,)).fetchone()
            if known:
                results.append({"file": str(given), "sha256": digest, "status": "already loaded", "rows": 0, "rejected": 0})
                continue
            file_id = conn.execute("INSERT INTO files (path, sha256, loaded_at, row_count, rejected_count) VALUES (?, ?, ?, 0, 0)",
                                   (str(given), digest, loaded_at)).lastrowid
            good, bad = [], []
            n_good = n_bad = 0
            for row in read_export(path, file_id):
                if isinstance(row, Reject):
                    bad.append((file_id, row.line, row.reason))
                    n_bad += 1
                else:
                    good.append(_record(row, file_id))
                    n_good += 1
                if len(good) >= BATCH:
                    conn.executemany(UPSERT, good)
                    good.clear()
            conn.executemany(UPSERT, good)
            conn.executemany("INSERT INTO rejects (file_id, line, reason) VALUES (?, ?, ?)", bad)
            conn.execute("UPDATE files SET row_count = ?, rejected_count = ? WHERE file_id = ?", (n_good, n_bad, file_id))
            results.append({"file": str(given), "sha256": digest, "status": "loaded", "rows": n_good, "rejected": n_bad})
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return results


_DAYS: dict[str, date] = {}


def items(conn: sqlite3.Connection, date_from: date | None = None, date_to: date | None = None) -> Iterator[LineItem]:
    """The current version of every line item, optionally limited to UTC usage days (inclusive)."""
    sql = ("SELECT line_item_id, account_id, account_name, service, resource_id, usage_date, usage_start, last_updated,"
           " kind, cost, tags, file_id, line FROM line_items")
    where, params = [], []
    if date_from:
        where.append("usage_date >= ?")
        params.append(date_from.isoformat())
    if date_to:
        where.append("usage_date <= ?")
        params.append(date_to.isoformat())
    if where:
        sql += " WHERE " + " AND ".join(where)
    intern = sys.intern
    for r in conn.execute(sql, params):
        day = _DAYS.get(r[5])
        if day is None:
            day = _DAYS[r[5]] = date.fromisoformat(r[5])
        tags = tuple((intern(k), intern(v)) for k, v in json.loads(r[10]).items()) if r[10] != "{}" else ()
        yield LineItem(line_item_id=r[0], account_id=intern(r[1]), account_name=intern(r[2]), service=intern(r[3]),
                       resource_id=intern(r[4]), usage_date=day, usage_start=intern(r[6]), last_updated=r[7],
                       kind=intern(r[8]), cost=Decimal(r[9]), tags=tags, order=(r[11], r[12]))


def rejects(conn: sqlite3.Connection) -> list[Reject]:
    return [Reject(p, line, reason) for p, line, reason in conn.execute(
        "SELECT f.path, r.line, r.reason FROM rejects r JOIN files f USING (file_id) ORDER BY r.file_id, r.line")]


def files(conn: sqlite3.Connection) -> list[dict]:
    return [{"path": p, "sha256": s, "loaded_at": t, "rows": n, "rejected": b} for p, s, t, n, b in conn.execute(
        "SELECT path, sha256, loaded_at, row_count, rejected_count FROM files ORDER BY file_id")]
