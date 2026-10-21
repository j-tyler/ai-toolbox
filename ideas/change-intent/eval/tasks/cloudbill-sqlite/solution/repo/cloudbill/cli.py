"""Command line: ``python -m cloudbill <question> [options] (FILE... | --db PATH)``,
``python -m cloudbill load --db PATH FILE...`` and ``python -m cloudbill files --db PATH``.

Every answer comes from a SQLite database: the one named by ``--db``, or a temporary one the files are
loaded into first, so answering from files and from a database give byte-identical output.

Exit codes: 0 answered (rejected rows are reported, not fatal); 1 an input file or the database cannot
be used at all, with the reason on standard error and nothing on standard output; 2 a command-line
mistake.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from typing import Iterable, Iterator

from . import db, questions, render
from .export import ExportError, LineItem

GROUPINGS = "account|service|tag:<key>"


def _date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a date (YYYY-MM-DD): {text!r}") from None


def _positive(text: str) -> int:
    try:
        n = int(text)
    except ValueError:
        n = 0
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be a whole number of at least 1: {text!r}")
    return n


def _grouping(*allowed: str):
    def parse(text: str) -> str:
        value = text.strip()
        if value.lower() in allowed:
            return value.lower()
        if value.lower().startswith("tag:") and len(value) > 4:
            return "tag:" + value[4:].strip().lower()
        raise argparse.ArgumentTypeError(f"expected {'|'.join(allowed)}|tag:<key>, got {text!r}")
    return parse


def build_parser() -> argparse.ArgumentParser:
    fmt = argparse.ArgumentParser(add_help=False)
    fmt.add_argument("--format", choices=("text", "json", "csv"), default="text")
    common = argparse.ArgumentParser(add_help=False, parents=[fmt])
    common.add_argument("--from", dest="date_from", type=_date, metavar="YYYY-MM-DD", help="first usage day (UTC), inclusive")
    common.add_argument("--to", dest="date_to", type=_date, metavar="YYYY-MM-DD", help="last usage day (UTC), inclusive")
    common.add_argument("--db", metavar="PATH", help="answer from this database instead of files")
    common.add_argument("files", nargs="*", metavar="FILE", help="billing export CSV files")

    p = argparse.ArgumentParser(prog="cloudbill", description="Answers for the monthly cost review, from billing exports.")
    sub = p.add_subparsers(dest="question", required=True, metavar="QUESTION")
    q = sub.add_parser("costs", parents=[common], help="charges, credits and net per account, service or tag value")
    q.add_argument("--by", required=True, type=_grouping("account", "service"), metavar=GROUPINGS)
    sub.add_parser("daily", parents=[common], help="net cost per UTC day")
    q = sub.add_parser("top", parents=[common], help="the largest groups by net cost")
    q.add_argument("--by", required=True, type=_grouping("account", "service", "resource"), metavar="account|service|resource|tag:<key>")
    q.add_argument("-n", type=_positive, default=10, help="how many (default 10)")
    q = sub.add_parser("untagged", parents=[common], help="per account, the net cost with no value for a tag")
    q.add_argument("--tag", required=True, help="tag key, e.g. team")
    sub.add_parser("credits", parents=[common], help="credits and refunds per account")
    q = sub.add_parser("mom", parents=[common], help="month-over-month net cost and change")
    q.add_argument("--by", type=_grouping("account", "service"), metavar=GROUPINGS)
    sub.add_parser("daily-stats", parents=[common], help="median and 90th percentile of daily net cost per account")
    sub.add_parser("rejects", parents=[common], help="rows that could not be used, and why")
    q = sub.add_parser("load", parents=[fmt], help="load export files into a database (loading a file twice changes nothing)")
    q.add_argument("--db", required=True, metavar="PATH", help="database to load into; created if missing")
    q.add_argument("files", nargs="+", metavar="FILE")
    q = sub.add_parser("files", parents=[fmt], help="the files loaded into a database")
    q.add_argument("--db", required=True, metavar="PATH")
    return p


def in_range(items: Iterable[LineItem], date_from: date | None, date_to: date | None) -> Iterator[LineItem]:
    for it in items:
        if (date_from is None or it.usage_date >= date_from) and (date_to is None or it.usage_date <= date_to):
            yield it


def answer(args: argparse.Namespace, items: Iterable[LineItem], rejects: list) -> str:
    """Compute and render one question from resolved items and the rejected rows."""
    items = in_range(items, args.date_from, args.date_to)
    meta = {"from": args.date_from.isoformat() if args.date_from else None,
            "to": args.date_to.isoformat() if args.date_to else None}
    total = None
    q = args.question
    if q == "costs":
        meta["by"] = args.by
        rows, total = questions.costs(items, args.by)
    elif q == "daily":
        rows = questions.daily(items)
    elif q == "top":
        meta.update(by=args.by, n=args.n)
        rows = questions.top(items, args.by, args.n)
    elif q == "untagged":
        meta["tag"] = args.tag.strip().lower()
        rows = questions.untagged(items, meta["tag"])
    elif q == "credits":
        rows = questions.credits(items)
    elif q == "mom":
        meta["by"] = args.by
        rows = questions.mom(items, args.by)
    elif q == "daily-stats":
        rows = questions.daily_stats(items)
    else:
        rows = [{"file": r.file, "line": r.line, "reason": r.reason} for r in rejects]
    return _render(args.format, q, rows, total, len(rejects), meta)


def _render(fmt: str, q: str, rows: list[dict], total, rejected: int, meta: dict) -> str:
    if fmt == "json":
        return render.as_json(q, rows, total, rejected, meta)
    if fmt == "csv":
        return render.as_csv(q, rows, rejected)
    return render.as_text(q, rows, total, rejected, meta)


def run(args: argparse.Namespace) -> str:
    if args.question == "load":
        conn = db.connect(args.db, create=True)
        try:
            rows = db.load(conn, args.files)
        finally:
            conn.close()
        return _render(args.format, "load", rows, None, sum(r["rejected"] for r in rows), {"db": args.db})
    if args.question == "files":
        conn = db.connect(args.db)
        try:
            rows = db.files(conn)
        finally:
            conn.close()
        return _render(args.format, "files", rows, None, sum(r["rejected"] for r in rows), {"db": args.db})
    temp = None
    if args.db:
        conn = db.connect(args.db)
    else:
        conn, temp = db.temporary()
    try:
        if temp:
            db.load(conn, args.files)
        return answer(args, db.items(conn, args.date_from, args.date_to), db.rejects(conn))
    finally:
        conn.close()
        if temp:
            os.unlink(temp)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.question not in ("load", "files"):
        if bool(args.files) == bool(args.db):
            parser.error("give export files or --db PATH (one of them)")
        if args.date_from and args.date_to and args.date_from > args.date_to:
            parser.error("--from is after --to")
    try:
        output = run(args)
    except ExportError as exc:
        print(f"cloudbill: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(output)
    return 0
