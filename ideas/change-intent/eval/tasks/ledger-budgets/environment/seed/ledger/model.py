"""Core record types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Transaction:
    """One ledger entry. ``amount_cents`` is positive for spending."""

    id: int
    date: date
    amount_cents: int
    category: str
    note: str

    @property
    def month(self) -> str:
        return self.date.strftime("%Y-%m")
