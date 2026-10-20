"""Recurring rules and their idempotent materialisation into transactions.

Rules live in ``recurring.csv`` next to the ledger file:
``id,amount_cents,category,note,every,start,until,applied_through``.
``applied_through`` is the last date for which occurrences were created, so a
later ``apply`` only creates occurrences after it.
"""

from __future__ import annotations

import calendar
import csv
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

from ledger import store
from ledger.model import Transaction

FIELDS = ["id", "amount_cents", "category", "note", "every", "start", "until", "applied_through"]
EVERY = ("monthly", "weekly")


@dataclass(frozen=True)
class Rule:
    id: int
    amount_cents: int
    category: str
    note: str
    every: str
    start: date
    until: date | None
    applied_through: date | None


def recurring_path(ledger_file: Path) -> Path:
    return ledger_file.parent / "recurring.csv"


def _opt_date(text: str) -> date | None:
    return date.fromisoformat(text) if text else None


def load(path: Path) -> list[Rule]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [
            Rule(
                id=int(r["id"]),
                amount_cents=int(r["amount_cents"]),
                category=r["category"],
                note=r.get("note", "") or "",
                every=r["every"],
                start=date.fromisoformat(r["start"]),
                until=_opt_date(r.get("until", "")),
                applied_through=_opt_date(r.get("applied_through", "")),
            )
            for r in csv.DictReader(fh)
        ]


def save(path: Path, rules: list[Rule]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for r in rules:
            writer.writerow(
                {
                    "id": r.id,
                    "amount_cents": r.amount_cents,
                    "category": r.category,
                    "note": r.note,
                    "every": r.every,
                    "start": r.start.isoformat(),
                    "until": r.until.isoformat() if r.until else "",
                    "applied_through": r.applied_through.isoformat() if r.applied_through else "",
                }
            )


def add_rule(path: Path, amount_cents: int, category: str, note: str, every: str, start: date, until: date | None) -> Rule:
    if every not in EVERY:
        raise ValueError(f"unsupported schedule: {every}")
    rules = load(path)
    rule = Rule(max((r.id for r in rules), default=0) + 1, amount_cents, category, note, every, start, until, None)
    rules.append(rule)
    save(path, rules)
    return rule


def _add_months(start: date, months: int) -> date:
    """``start`` shifted by ``months`` whole months, clamped to the month's end."""
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def occurrences(rule: Rule, through: date) -> list[date]:
    """Every occurrence of ``rule`` from its start through ``through``."""
    end = min(through, rule.until) if rule.until else through
    out: list[date] = []
    n = 0
    while True:
        d = _add_months(rule.start, n) if rule.every == "monthly" else rule.start + timedelta(weeks=n)
        if d > end:
            return out
        out.append(d)
        n += 1


def apply(rules_path: Path, ledger_file: Path, through: date) -> int:
    rules = load(rules_path)
    txns = store.load(ledger_file)
    created = 0
    new_rules = []
    for rule in rules:
        due = [d for d in occurrences(rule, through) if rule.applied_through is None or d > rule.applied_through]
        for d in due:
            txns.append(Transaction(store.next_id(txns), d, rule.amount_cents, rule.category, rule.note))
            created += 1
        high_water = max([rule.applied_through or date.min, through])
        new_rules.append(replace(rule, applied_through=high_water if high_water != date.min else None))
    store.save(ledger_file, txns)
    save(rules_path, new_rules)
    return created
