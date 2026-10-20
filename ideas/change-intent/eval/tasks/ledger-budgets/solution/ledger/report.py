"""Monthly report: spending per category against budget limits."""

from __future__ import annotations

from ledger.budget import limits_for_month, spent_by_category
from ledger.model import Transaction


def monthly_report(txns: list[Transaction], budgets: dict[tuple[str, str], int], month: str) -> dict:
    spent = spent_by_category(txns, month)
    limits = limits_for_month(budgets, month)
    categories = [
        {"category": c, "spent_cents": spent[c], "limit_cents": limits.get(c)} for c in sorted(spent)
    ]
    return {"month": month, "total_cents": sum(spent.values()), "categories": categories}
