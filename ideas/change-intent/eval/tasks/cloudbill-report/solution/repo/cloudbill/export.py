"""Reading billing export files: one row at a time, never the whole file.

``read_export`` yields a ``LineItem`` for every row it can use and a ``Reject`` for every row it cannot.
Formatting a person would read the same way is accepted (surrounding whitespace, letter case in the line
item type and column names, thousands separators, a leading ``$``, accounting-style parentheses); a row
is rejected only for the reasons in ``REASONS``. A file that is not a billing export at all raises
``ExportError``.
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterator

REQUIRED = ("line_item_id", "account_id", "service", "usage_start", "unblended_cost", "currency", "line_item_type")
CHARGE_KINDS = ("usage", "tax", "fee")
CREDIT_KINDS = ("credit", "refund")
KINDS = CHARGE_KINDS + CREDIT_KINDS

csv.field_size_limit(16 * 1024 * 1024)  # one pathological description must not abort a 2 GB run


class ExportError(Exception):
    """An input file cannot be used at all (missing, unreadable, or not a billing export)."""


@dataclass(slots=True)
class LineItem:
    line_item_id: str
    account_id: str
    account_name: str
    service: str  # as exported, whitespace stripped; grouping uses service.lower()
    resource_id: str
    usage_date: date  # UTC date of usage_start
    usage_start: str  # UTC, ISO 8601, for choosing the current account name
    last_updated: str  # UTC, ISO 8601, "" when absent; decides restatements
    kind: str  # one of KINDS
    cost: Decimal
    tags: tuple  # ((key, value), ...) for the tags this row has a non-blank value for
    order: tuple  # (file index, start line): input order, the restatement tie-break

    @property
    def is_credit(self) -> bool:
        return self.kind in CREDIT_KINDS

    def tag(self, key: str) -> str | None:
        for k, v in self.tags:
            if k == key:
                return v
        return None


@dataclass(frozen=True, slots=True)
class Reject:
    file: str
    line: int
    reason: str


_THOUSANDS = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")
_STAMPS: dict[str, tuple[date, str] | None] = {}  # timestamp text -> (UTC day, UTC ISO); exports repeat them


def parse_money(text: str) -> Decimal | None:
    """A cost as a person would read it: "1,234.5600", " 12.34 ", "$5", "(3.20)". None if it is not a number."""
    s = text.strip()
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1].strip()
    if s.startswith("-$"):
        s = "-" + s[2:]
    s = s.removeprefix("$")
    if _THOUSANDS.match(s):
        s = s.replace(",", "")
    try:
        value = Decimal(s)
    except InvalidOperation:
        return None
    if not value.is_finite():
        return None
    return -value if negative else value


def parse_timestamp(text: str) -> datetime | None:
    """ISO 8601 with or without a zone (no zone means UTC), as an aware UTC datetime; None if unusable."""
    s = text.strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _stamp(text: str) -> tuple[date, str] | None:
    """parse_timestamp, cached: an hourly export has a few hundred distinct timestamps a month."""
    hit = _STAMPS.get(text, False)
    if hit is not False:
        return hit
    dt = parse_timestamp(text)
    value = (dt.date(), sys.intern(dt.isoformat())) if dt else None
    if len(_STAMPS) > 50_000:  # bounded whatever the export looks like
        _STAMPS.clear()
    _STAMPS[text] = value
    return value


def _rows(path: Path) -> Iterator[tuple[int, list[str]]]:
    """(start line, fields) for every non-blank record, header included. Start lines count physical lines,
    so a description with embedded newlines does not shift the numbers of later rows."""
    try:
        fh = open(path, encoding="utf-8-sig", errors="replace", newline="")
    except OSError as exc:
        raise ExportError(f"{path}: cannot open ({exc.strerror or exc})") from None
    with fh:
        reader = csv.reader(fh)
        start = 1
        try:
            for fields in reader:
                if fields:
                    yield start, fields
                start = reader.line_num + 1
        except csv.Error as exc:
            raise ExportError(f"{path}: not readable as CSV near line {start} ({exc})") from None
        except OSError as exc:
            raise ExportError(f"{path}: read failed ({exc.strerror or exc})") from None


def read_export(path: str | Path, file_index: int = 0) -> Iterator[LineItem | Reject]:
    path = Path(path)
    if path.is_dir():
        raise ExportError(f"{path}: is a directory, not an export file")
    rows = _rows(path)
    header = next(rows, None)
    if header is None:
        raise ExportError(f"{path}: empty file, not a billing export")
    names = [h.strip().lower() for h in header[1]]
    missing = [c for c in REQUIRED if c not in names]
    if missing:
        raise ExportError(f"{path}: not a billing export (missing column{'s' if len(missing) > 1 else ''}: {', '.join(missing)})")
    col = {name: i for i, name in enumerate(names)}
    tag_cols = [(sys.intern(name[4:]), i) for i, name in enumerate(names) if name.startswith("tag:") and len(name) > 4]
    i_id, i_acct, i_svc, i_start, i_cost, i_cur, i_kind = (col[c] for c in REQUIRED)
    i_name, i_res, i_upd = col.get("account_name"), col.get("resource_id"), col.get("last_updated")
    width = len(names)
    shown = str(path)
    intern = sys.intern

    for line, f in rows:
        if len(f) != width:
            yield Reject(shown, line, f"expected {width} fields, found {len(f)}")
            continue
        line_item_id = f[i_id].strip()
        if not line_item_id:
            yield Reject(shown, line, "no line item id")
            continue
        start = _stamp(f[i_start])
        if start is None:
            yield Reject(shown, line, f"usage start is missing or not a timestamp: {f[i_start].strip()!r}")
            continue
        cost = parse_money(f[i_cost])
        if cost is None:
            yield Reject(shown, line, f"cost is not a number: {f[i_cost].strip()!r}")
            continue
        currency = f[i_cur].strip().upper()
        if currency != "USD":
            yield Reject(shown, line, f"currency is {currency or 'blank'}, only USD is accepted")
            continue
        kind = f[i_kind].strip().lower()
        if kind not in KINDS:
            yield Reject(shown, line, f"unknown line item type: {f[i_kind].strip()!r}")
            continue
        updated = _stamp(f[i_upd]) if i_upd is not None else None
        tags = tuple((k, intern(v)) for k, i in tag_cols if (v := f[i].strip()))
        yield LineItem(
            line_item_id=line_item_id,
            account_id=intern(f[i_acct].strip()),
            account_name=intern(f[i_name].strip()) if i_name is not None else "",
            service=intern(f[i_svc].strip()),
            resource_id=intern(f[i_res].strip()) if i_res is not None else "",
            usage_date=start[0],
            usage_start=start[1],
            last_updated=updated[1] if updated else "",
            kind=intern(kind),
            cost=cost,
            tags=tags,
            order=(file_index, line),
        )
