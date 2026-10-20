"""CSV persistence for transactions.

The ledger file has a header row and one row per transaction:
``id,date,amount_cents,category,note``. Rows are kept in insertion order and
``id`` is a positive integer that increases by one for each new transaction.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from ledger.model import Transaction

FIELDS = ["id", "date", "amount_cents", "category", "note"]


def load(path: Path) -> list[Transaction]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = []
        for row in reader:
            rows.append(
                Transaction(
                    id=int(row["id"]),
                    date=date.fromisoformat(row["date"]),
                    amount_cents=int(row["amount_cents"]),
                    category=row["category"],
                    note=row.get("note", "") or "",
                )
            )
    return rows


def save(path: Path, txns: list[Transaction]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for t in txns:
            writer.writerow(
                {
                    "id": t.id,
                    "date": t.date.isoformat(),
                    "amount_cents": t.amount_cents,
                    "category": t.category,
                    "note": t.note,
                }
            )


def next_id(txns: list[Transaction]) -> int:
    return max((t.id for t in txns), default=0) + 1


def append(path: Path, txn_date: date, amount_cents: int, category: str, note: str) -> Transaction:
    txns = load(path)
    txn = Transaction(next_id(txns), txn_date, amount_cents, category, note)
    txns.append(txn)
    save(path, txns)
    return txn
