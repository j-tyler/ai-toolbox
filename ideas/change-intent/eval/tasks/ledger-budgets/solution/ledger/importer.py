"""Import transactions from a bank CSV export with duplicate detection."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ledger import store
from ledger.model import Transaction
from ledger.money import parse_amount


class ImportError_(ValueError):
    """Raised when the import file cannot be used; the ledger is left untouched."""


@dataclass(frozen=True)
class ImportResult:
    imported: int
    skipped: int


def _fingerprint(d: date, amount_cents: int, note: str) -> tuple[str, int, str]:
    return (d.isoformat(), amount_cents, note)


def import_file(
    ledger_file: Path,
    source: Path,
    date_col: str,
    amount_col: str,
    note_col: str | None,
    category: str,
    date_format: str | None,
    negate: bool,
) -> ImportResult:
    try:
        with source.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            for col in [date_col, amount_col] + ([note_col] if note_col else []):
                if col not in header:
                    raise ImportError_(f"column {col!r} not found in {source}")
            rows = list(reader)
    except OSError as exc:
        raise ImportError_(str(exc)) from exc

    txns = store.load(ledger_file)
    seen = {_fingerprint(t.date, t.amount_cents, t.note) for t in txns}
    imported = skipped = 0
    for row in rows:
        raw_date = row[date_col].strip()
        d = datetime.strptime(raw_date, date_format).date() if date_format else date.fromisoformat(raw_date)
        cents = parse_amount(row[amount_col])
        if negate:
            cents = -cents
        note = (row[note_col] or "").strip() if note_col else ""
        key = _fingerprint(d, cents, note)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        txns.append(Transaction(store.next_id(txns), d, cents, category, note))
        imported += 1
    store.save(ledger_file, txns)
    return ImportResult(imported, skipped)
