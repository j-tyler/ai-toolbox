"""Money is stored as integer cents and never as floats."""

from __future__ import annotations

import re

_AMOUNT_RE = re.compile(r"^(-)?(\d+)(?:\.(\d{1,2}))?$")


class MoneyError(ValueError):
    """Raised when an amount string cannot be parsed."""


def parse_amount(text: str) -> int:
    """Parse a decimal string such as ``"12.5"`` or ``"-3.07"`` into cents.

    At most two fractional digits are accepted. Thousands separators are not.
    """
    cleaned = text.strip().replace("$", "")
    match = _AMOUNT_RE.match(cleaned)
    if not match:
        raise MoneyError(f"invalid amount: {text!r}")
    sign, whole, frac = match.groups()
    frac = (frac or "").ljust(2, "0")
    cents = int(whole) * 100 + int(frac)
    return -cents if sign else cents


def format_cents(cents: int) -> str:
    """Format cents as a decimal string with exactly two fractional digits."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"
