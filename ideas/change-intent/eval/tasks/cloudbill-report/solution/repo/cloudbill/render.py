"""Output in three formats. Money is exact until here.

* JSON: one object, ``rows`` plus ``rejected_rows`` (and ``total`` for ``costs``). Money is a number
  with the export's four decimal places; percentages have two. Keys keep the documented order.
* CSV: a header row of the same field names, one line per row, money with four decimals; the last line
  is ``# rejected_rows: N`` (a comment line, as most CSV readers can be told to skip).
* Text: a table for people, money rounded half-up to cents with thousands separators.
"""

from __future__ import annotations

import csv
import io
import json
from decimal import ROUND_HALF_UP, Decimal

Q4 = Decimal("0.0001")
CENT = Decimal("0.01")

FIELDS = {
    "costs": ["key", "charges", "credits", "net"],
    "daily": ["date", "charges", "credits", "net"],
    "top": ["key", "net"],
    "untagged": ["key", "untagged", "net"],
    "credits": ["key", "credit", "refund", "credits"],
    "mom": ["month", "net", "change", "change_pct", "partial"],
    "daily-stats": ["key", "days", "median", "p90"],
    "rejects": ["file", "line", "reason"],
}
TITLES = {
    "costs": "Cost by {by}", "daily": "Daily net cost", "top": "Top {n} by {by}", "untagged": "Spend without a {tag} tag",
    "credits": "Credits and refunds by account", "mom": "Month over month", "daily-stats": "Daily net cost per account",
    "rejects": "Rejected rows",
}
PERCENT_FIELDS = {"change_pct"}


def fields_for(question: str, rows: list[dict]) -> list[str]:
    fields = list(FIELDS[question])
    if rows and "name" in rows[0]:
        fields.insert(1, "name")
    if question == "mom" and rows and "key" in rows[0]:
        fields.insert(0, "key")
    return fields


def _json_value(field: str, value):
    if isinstance(value, Decimal):
        value = value.quantize(CENT if field in PERCENT_FIELDS else Q4)
        return float(value) if value else 0.0
    return value


def _csv_value(field: str, value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return f"{value.quantize(CENT if field in PERCENT_FIELDS else Q4):f}"
    return str(value)


def _money_text(value: Decimal) -> str:
    v = value.quantize(CENT, rounding=ROUND_HALF_UP)
    return f"{v + 0:,.2f}"  # + 0 turns -0.00 into 0.00


def _text_value(field: str, value, none_label: str) -> str:
    if field in ("key",) and value is None:
        return none_label
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "partial" if value else ""
    if field in PERCENT_FIELDS:
        return f"{value.quantize(CENT, rounding=ROUND_HALF_UP):+.2f}%"
    if isinstance(value, Decimal):
        return _money_text(value) if field not in ("days",) else str(value)
    return str(value)


def as_json(question: str, rows: list[dict], total: dict | None, rejected: int, meta: dict) -> str:
    fields = fields_for(question, rows)
    doc: dict = {"question": question, **meta, "rows": [{f: _json_value(f, r.get(f)) for f in fields} for r in rows]}
    if total is not None:
        doc["total"] = {k: _json_value(k, v) for k, v in total.items()}
    doc["rejected_rows"] = rejected
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def as_csv(question: str, rows: list[dict], rejected: int) -> str:
    fields = fields_for(question, rows)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(fields)
    for r in rows:
        w.writerow([_csv_value(f, r.get(f)) for f in fields])
    buf.write(f"# rejected_rows: {rejected}\n")
    return buf.getvalue()


def as_text(question: str, rows: list[dict], total: dict | None, rejected: int, meta: dict) -> str:
    fields = fields_for(question, rows)
    by = meta.get("by") or ""
    none_label = "(untagged)" if by.startswith("tag:") or question == "untagged" else "(none)"
    title = TITLES[question].format(by=by, n=meta.get("n", ""), tag=meta.get("tag", ""))
    span = f"{meta.get('from') or 'start'} to {meta.get('to') or 'end'}"
    header = [f.replace("_", " ") for f in fields]
    body = [[_text_value(f, r.get(f), none_label) for f in fields] for r in rows]
    if total is not None:
        body.append(["total"] + [""] * (len(fields) - 4) + [_money_text(total[k]) for k in ("charges", "credits", "net")])
    left = {i for i, f in enumerate(fields) if f in ("key", "name", "date", "month", "file", "reason")}
    widths = [max([len(header[i])] + [len(row[i]) for row in body]) for i in range(len(fields))]

    def line(cells: list[str]) -> str:
        return "  ".join(c.ljust(widths[i]) if i in left else c.rjust(widths[i]) for i, c in enumerate(cells)).rstrip()

    out = [f"{title}, {span}", ""]
    if body:
        out.append(line(header))
        out.extend(line(row) for row in body)
    else:
        out.append("(no rows)")
    out += ["", f"rejected rows: {rejected}" + (" (cloudbill rejects lists them)" if rejected and question != "rejects" else "")]
    return "\n".join(out) + "\n"
