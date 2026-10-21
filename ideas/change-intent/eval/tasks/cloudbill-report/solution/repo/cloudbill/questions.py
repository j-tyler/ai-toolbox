"""The review questions, each a single pass over resolved line items.

Every function takes an iterable of ``LineItem`` (already restricted to the date range) and returns rows
as dicts of plain values, money as exact ``Decimal``. State is per group or per day, never per row, and
no result depends on the order the items arrive in, so the same export gives the same answer however it
was read.
"""

from __future__ import annotations

import calendar
from collections import Counter
from datetime import date
from decimal import Decimal
from typing import Callable, Iterable

from .export import LineItem

ZERO = Decimal(0)
PCT = Decimal("0.01")


def key_function(by: str) -> Callable[[LineItem], str | None]:
    """What a row is grouped by. ``None`` is the group of rows with no value (untagged, no resource)."""
    if by == "account":
        return lambda it: it.account_id or None
    if by == "service":
        return lambda it: it.service.lower() or None
    if by == "resource":
        return lambda it: it.resource_id or None
    if by.startswith("tag:") and len(by) > 4:
        tag = by[4:].lower()
        return lambda it: it.tag(tag)
    raise ValueError(f"cannot group by {by!r}")


def sort_key(key: str | None) -> tuple:
    return (key is None, key or "")


class Labels:
    """How a group is shown: a service by its most common spelling (ties: the alphabetically first), an
    account with the name on its most recent usage (ties: the alphabetically last name)."""

    def __init__(self, by: str | None):
        self.by = by
        self.spellings: dict[str | None, Counter] = {}
        self.names: dict[str | None, tuple[str, str]] = {}

    def see(self, key: str | None, item: LineItem) -> None:
        if self.by == "service":
            self.spellings.setdefault(key, Counter())[item.service] += 1
        elif self.by == "account":
            candidate = (item.usage_start, item.account_name)
            if candidate > self.names.get(key, ("", "")):
                self.names[key] = candidate

    def label(self, key: str | None) -> str | None:
        if key is not None and self.by == "service":
            return min(self.spellings[key].items(), key=lambda kv: (-kv[1], kv[0]))[0]
        return key

    def name(self, key: str | None) -> str:
        return self.names.get(key, ("", ""))[1]


def _groups(items: Iterable[LineItem], by: str):
    keyf, labels = key_function(by), Labels(by)
    groups: dict[str | None, list[Decimal]] = {}
    for it in items:
        k = keyf(it)
        labels.see(k, it)
        g = groups.get(k)
        if g is None:
            g = groups[k] = [ZERO, ZERO]
        g[it.is_credit] += it.cost
    return groups, labels


def costs(items: Iterable[LineItem], by: str) -> tuple[list[dict], dict]:
    groups, labels = _groups(items, by)
    rows = []
    total = [ZERO, ZERO]
    for k in sorted(groups, key=sort_key):
        charges, credits = groups[k]
        total[0] += charges
        total[1] += credits
        row: dict = {"key": labels.label(k)}
        if by == "account":
            row["name"] = labels.name(k)
        row.update(charges=charges, credits=credits, net=charges + credits)
        rows.append(row)
    return rows, {"charges": total[0], "credits": total[1], "net": total[0] + total[1]}


def top(items: Iterable[LineItem], by: str, n: int) -> list[dict]:
    groups, labels = _groups(items, by)
    ranked = sorted(groups, key=lambda k: (-(groups[k][0] + groups[k][1]), sort_key(k)))
    return [{"key": labels.label(k), "net": groups[k][0] + groups[k][1]} for k in ranked[:n]]


def daily(items: Iterable[LineItem]) -> list[dict]:
    days: dict[date, list[Decimal]] = {}
    for it in items:
        d = days.get(it.usage_date)
        if d is None:
            d = days[it.usage_date] = [ZERO, ZERO]
        d[it.is_credit] += it.cost
    return [{"date": day.isoformat(), "charges": c, "credits": r, "net": c + r} for day, (c, r) in sorted(days.items())]


def untagged(items: Iterable[LineItem], tag: str) -> list[dict]:
    tag = tag.lower()
    accounts: dict[str, list[Decimal]] = {}
    for it in items:
        a = accounts.get(it.account_id)
        if a is None:
            a = accounts[it.account_id] = [ZERO, ZERO]
        if it.tag(tag) is None:
            a[0] += it.cost
        a[1] += it.cost
    return [{"key": k, "untagged": u, "net": n} for k, (u, n) in sorted(accounts.items())]


def credits(items: Iterable[LineItem]) -> list[dict]:
    accounts: dict[str, list[Decimal]] = {}
    for it in items:
        if it.is_credit:
            a = accounts.get(it.account_id)
            if a is None:
                a = accounts[it.account_id] = [ZERO, ZERO]
            a[it.kind == "refund"] += it.cost
    return [{"key": k, "credit": c, "refund": r, "credits": c + r} for k, (c, r) in sorted(accounts.items())]


def _months(first: date, last: date) -> list[tuple[int, int]]:
    out, (y, m) = [], (first.year, first.month)
    while (y, m) <= (last.year, last.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _month_last_day(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def mom(items: Iterable[LineItem], by: str | None) -> list[dict]:
    """Every month between the first and last day in the data, for every group; a month the data does
    not cover from its first to its last day is ``partial``. Change is against the previous calendar
    month; the percentage is relative to the size of the previous month's net."""
    keyf = key_function(by) if by else (lambda it: None)
    labels = Labels(by)
    nets: dict[tuple, Decimal] = {}
    first = last = None
    for it in items:
        k = keyf(it)
        labels.see(k, it)
        slot = (k, it.usage_date.year, it.usage_date.month)
        nets[slot] = nets.get(slot, ZERO) + it.cost
        d = it.usage_date
        if first is None or d < first:
            first = d
        if last is None or d > last:
            last = d
    if first is None:
        return []
    rows = []
    for k in sorted({s[0] for s in nets}, key=sort_key):
        previous = None
        for y, m in _months(first, last):
            net = nets.get((k, y, m), ZERO)
            change = None if previous is None else net - previous
            pct = None if previous is None or previous == 0 else (change * 100 / abs(previous)).quantize(PCT)
            row: dict = {"key": labels.label(k)} if by else {}
            row.update(month=f"{y:04d}-{m:02d}", net=net, change=change, change_pct=pct,
                       partial=first > date(y, m, 1) or last < _month_last_day(y, m))
            rows.append(row)
            previous = net
    return rows


def percentile(sorted_values: list[Decimal], q: int) -> Decimal:
    """Linear interpolation between closest ranks (the spreadsheet PERCENTILE.INC rule), q in 0..100."""
    pos = Decimal(q) * (len(sorted_values) - 1) / 100
    lo = int(pos)
    if lo + 1 >= len(sorted_values):
        return sorted_values[-1]
    return sorted_values[lo] + (sorted_values[lo + 1] - sorted_values[lo]) * (pos - lo)


def daily_stats(items: Iterable[LineItem]) -> list[dict]:
    """Per account, over the days on which it has any line: the median and 90th percentile of daily net."""
    accounts: dict[str, dict[date, Decimal]] = {}
    for it in items:
        days = accounts.get(it.account_id)
        if days is None:
            days = accounts[it.account_id] = {}
        days[it.usage_date] = days.get(it.usage_date, ZERO) + it.cost
    rows = []
    for k, days in sorted(accounts.items()):
        values = sorted(days.values())
        rows.append({"key": k, "days": len(values), "median": percentile(values, 50), "p90": percentile(values, 90)})
    return rows
