"""Command-line interface.

``main(argv)`` returns the process exit code and writes to ``sys.stdout``
and ``sys.stderr`` so it can be driven from tests without a subprocess.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from ledger import store
from ledger.money import MoneyError, format_cents, parse_amount


def ledger_path(args: argparse.Namespace) -> Path:
    if args.file:
        return Path(args.file)
    env = os.environ.get("LEDGER_FILE")
    return Path(env) if env else Path("ledger.csv")


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


COMMANDS = {"add": cmd_add, "list": cmd_list}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return COMMANDS[args.command](args)
