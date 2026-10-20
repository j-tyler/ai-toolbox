"""Command-line interface.

``main(argv)`` returns the process exit code and writes to ``sys.stdout``
and ``sys.stderr`` so it can be driven from tests without a subprocess.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from ledger import budget, importer, recurring, report, store
from ledger.money import MoneyError, format_cents, parse_amount


def ledger_path(args: argparse.Namespace) -> Path:
    if args.file:
        return Path(args.file)
    env = os.environ.get("LEDGER_FILE")
    return Path(env) if env else Path("ledger.csv")


def _month(text: str) -> str:
    try:
        date.fromisoformat(text + "-01")
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid month {text!r}, expected YYYY-MM")
    return text


def _date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date {text!r}, expected YYYY-MM-DD")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ledger", description="Track personal spending.")
    parser.add_argument("--file", help="ledger CSV path (default: $LEDGER_FILE or ./ledger.csv)")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="record a transaction")
    add.add_argument("--date", required=True, help="YYYY-MM-DD")
    add.add_argument("--amount", required=True, help="decimal amount, e.g. 12.50")
    add.add_argument("--category", required=True)
    add.add_argument("--note", default="")

    ls = sub.add_parser("list", help="list transactions")
    ls.add_argument("--month", help="YYYY-MM")
    ls.add_argument("--category")

    bud = sub.add_parser("budget", help="manage monthly budgets").add_subparsers(dest="budget_command", required=True)
    bset = bud.add_parser("set", help="set a category limit")
    bset.add_argument("category")
    bset.add_argument("amount")
    bset.add_argument("--month", type=_month, help="apply to this month only")
    bstat = bud.add_parser("status", help="show spending against limits")
    bstat.add_argument("--month", type=_month, required=True)
    bstat.add_argument("--format", choices=["text", "json"], default="text")

    rec = sub.add_parser("recur", help="recurring transactions").add_subparsers(dest="recur_command", required=True)
    radd = rec.add_parser("add")
    radd.add_argument("--amount", required=True)
    radd.add_argument("--category", required=True)
    radd.add_argument("--every", choices=list(recurring.EVERY), required=True)
    radd.add_argument("--start", type=_date, required=True)
    radd.add_argument("--until", type=_date)
    radd.add_argument("--note", default="")
    rec.add_parser("list")
    rapp = rec.add_parser("apply")
    rapp.add_argument("--through", type=_date, required=True)

    imp = sub.add_parser("import", help="import a bank CSV export")
    imp.add_argument("path")
    imp.add_argument("--date-col", required=True)
    imp.add_argument("--amount-col", required=True)
    imp.add_argument("--note-col")
    imp.add_argument("--category", default="imported")
    imp.add_argument("--date-format")
    imp.add_argument("--negate", action="store_true")
    imp.add_argument("--format", choices=["text", "json"], default="text")

    rep = sub.add_parser("report", help="monthly report")
    rep.add_argument("--month", type=_month, required=True)
    rep.add_argument("--format", choices=["text", "json"], default="text")

    return parser


def cmd_add(args: argparse.Namespace) -> int:
    try:
        txn_date = date.fromisoformat(args.date)
    except ValueError:
        print(f"error: invalid date {args.date!r}", file=sys.stderr)
        return 2
    try:
        cents = parse_amount(args.amount)
    except MoneyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    txn = store.append(ledger_path(args), txn_date, cents, args.category, args.note)
    print(f"added #{txn.id} {txn.date.isoformat()} {format_cents(txn.amount_cents)} {txn.category}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    txns = store.load(ledger_path(args))
    if args.month:
        txns = [t for t in txns if t.month == args.month]
    if args.category:
        txns = [t for t in txns if t.category == args.category]
    for t in sorted(txns, key=lambda t: (t.date, t.id)):
        note = f" {t.note}" if t.note else ""
        print(f"#{t.id} {t.date.isoformat()} {format_cents(t.amount_cents):>10} {t.category}{note}")
    total = sum(t.amount_cents for t in txns)
    print(f"total {format_cents(total)}")
    return 0


def cmd_budget(args: argparse.Namespace) -> int:
    ledger_file = ledger_path(args)
    path = budget.budgets_path(ledger_file)
    if args.budget_command == "set":
        try:
            cents = parse_amount(args.amount)
        except MoneyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        budget.set_limit(path, args.category, cents, args.month)
        suffix = f" for {args.month}" if args.month else ""
        print(f"budget {args.category} {format_cents(cents)}{suffix}")
        return 0
    rows = budget.status(budget.load(path), store.load(ledger_file), args.month)
    if args.format == "json":
        print(json.dumps(rows))
        return 0
    for r in rows:
        over = " OVER" if r["over"] else ""
        print(
            f"{r['category']} {format_cents(r['spent_cents'])}/{format_cents(r['limit_cents'])} "
            f"remaining {format_cents(r['remaining_cents'])}{over}"
        )
    return 0


def cmd_recur(args: argparse.Namespace) -> int:
    ledger_file = ledger_path(args)
    path = recurring.recurring_path(ledger_file)
    if args.recur_command == "add":
        try:
            cents = parse_amount(args.amount)
        except MoneyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        rule = recurring.add_rule(path, cents, args.category, args.note, args.every, args.start, args.until)
        print(f"recurring #{rule.id} {rule.every} from {rule.start.isoformat()} {format_cents(rule.amount_cents)} {rule.category}")
        return 0
    if args.recur_command == "list":
        for r in sorted(recurring.load(path), key=lambda r: r.id):
            until = f" until {r.until.isoformat()}" if r.until else ""
            note = f" {r.note}" if r.note else ""
            print(f"#{r.id} {r.every} from {r.start.isoformat()}{until} {format_cents(r.amount_cents)} {r.category}{note}")
        return 0
    created = recurring.apply(path, ledger_file, args.through)
    print(f"applied {created}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    try:
        result = importer.import_file(
            ledger_path(args),
            Path(args.path),
            args.date_col,
            args.amount_col,
            args.note_col,
            args.category,
            args.date_format,
            args.negate,
        )
    except (importer.ImportError_, MoneyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps({"imported": result.imported, "skipped": result.skipped}))
    else:
        print(f"imported {result.imported} skipped {result.skipped}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    ledger_file = ledger_path(args)
    data = report.monthly_report(store.load(ledger_file), budget.load(budget.budgets_path(ledger_file)), args.month)
    if args.format == "json":
        print(json.dumps(data))
        return 0
    for c in data["categories"]:
        limit = f" of {format_cents(c['limit_cents'])}" if c["limit_cents"] is not None else ""
        print(f"{c['category']} {format_cents(c['spent_cents'])}{limit}")
    print(f"total {format_cents(data['total_cents'])}")
    return 0


COMMANDS = {
    "add": cmd_add,
    "list": cmd_list,
    "budget": cmd_budget,
    "recur": cmd_recur,
    "import": cmd_import,
    "report": cmd_report,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return COMMANDS[args.command](args)
