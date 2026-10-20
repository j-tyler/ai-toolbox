"""Budgets: a default limit per category plus optional per-month overrides.

Stored in ``budgets.csv`` next to the ledger file with columns
``category,month,limit_cents``. ``month`` is empty for the default limit.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ledger.model import Transaction

FIELDS = ["category", "month", "limit_cents"]


def budgets_path(ledger_file: Path) -> Path:
    return ledger_file.parent / "budgets.csv"


def load(path: Path) -> dict[tuple[str, str], int]:
    """Return ``{(category, month_or_empty): limit_cents}``."""
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        return {(r["category"], r["month"] or ""): int(r["limit_cents"]) for r in csv.DictReader(fh)}


def save(path: Path, budgets: dict[tuple[str, str], int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for (category, month), cents in sorted(budgets.items()):
            writer.writerow({"category": category, "month": month, "limit_cents": cents})


def set_limit(path: Path, category: str, limit_cents: int, month: str | None) -> None:
    budgets = load(path)
    budgets[(category, month or "")] = limit_cents
    save(path, budgets)


def limits_for_month(budgets: dict[tuple[str, str], int], month: str) -> dict[str, int]:
    """Resolve the effective limit per category for ``month``."""
    effective: dict[str, int] = {}
    for (category, bmonth), cents in budgets.items():
        if bmonth == "":
            effective.setdefault(category, cents)
    for (category, bmonth), cents in budgets.items():
        if bmonth == month:
            effective[category] = cents
    return effective


def spent_by_category(txns: list[Transaction], month: str) -> dict[str, int]:
    spent: dict[str, int] = {}
    for t in txns:
        if t.month == month:
            spent[t.category] = spent.get(t.category, 0) + t.amount_cents
    return spent


def status(budgets: dict[tuple[str, str], int], txns: list[Transaction], month: str) -> list[dict]:
    limits = limits_for_month(budgets, month)
    spent = spent_by_category(txns, month)
    rows = []
    for category in sorted(limits):
        limit = limits[category]
        used = spent.get(category, 0)
        rows.append(
            {
                "category": category,
                "limit_cents": limit,
                "spent_cents": used,
                "remaining_cents": limit - used,
                "over": used > limit,
            }
        )
    return rows
