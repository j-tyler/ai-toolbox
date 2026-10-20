import csv
from pathlib import Path

from conftest import add


def ledger_rows(workdir: Path):
    with (workdir / "ledger.csv").open(newline="") as fh:
        return list(csv.DictReader(fh))


def test_recur_add_prints_id_and_persists(workdir, run):
    code, out, err = run(["recur", "add", "--amount", "1200", "--category", "rent", "--every", "monthly", "--start", "2026-01-01", "--note", "flat"])
    assert code == 0, err
    assert out.strip().startswith("recurring #1")
    assert (workdir / "recurring.csv").exists()
    code, out, _ = run(["recur", "list"])
    assert code == 0
    assert out.strip().splitlines()[0].startswith("#1")


def test_recur_list_in_id_order(workdir, run):
    run(["recur", "add", "--amount", "1", "--category", "a", "--every", "weekly", "--start", "2026-01-01"])
    run(["recur", "add", "--amount", "2", "--category", "b", "--every", "monthly", "--start", "2026-01-01"])
    _, out, _ = run(["recur", "list"])
    lines = out.strip().splitlines()
    assert lines[0].startswith("#1") and lines[1].startswith("#2")


def test_apply_monthly_creates_each_occurrence(workdir, run):
    run(["recur", "add", "--amount", "1200", "--category", "rent", "--every", "monthly", "--start", "2026-01-05", "--note", "flat"])
    code, out, _ = run(["recur", "apply", "--through", "2026-04-10"])
    assert code == 0
    assert out.strip() == "applied 4"
    rows = ledger_rows(workdir)
    assert [r["date"] for r in rows] == ["2026-01-05", "2026-02-05", "2026-03-05", "2026-04-05"]
    assert {r["amount_cents"] for r in rows} == {"120000"}
    assert {r["category"] for r in rows} == {"rent"}
    assert {r["note"] for r in rows} == {"flat"}


def test_apply_is_idempotent(workdir, run):
    run(["recur", "add", "--amount", "10", "--category", "sub", "--every", "monthly", "--start", "2026-01-01"])
    run(["recur", "apply", "--through", "2026-03-01"])
    _, out, _ = run(["recur", "apply", "--through", "2026-03-01"])
    assert out.strip() == "applied 0"
    _, out, _ = run(["recur", "apply", "--through", "2026-02-01"])
    assert out.strip() == "applied 0"
    _, out, _ = run(["recur", "apply", "--through", "2026-05-01"])
    assert out.strip() == "applied 2"
    assert len(ledger_rows(workdir)) == 5


def test_apply_weekly(workdir, run):
    run(["recur", "add", "--amount", "5", "--category", "coffee", "--every", "weekly", "--start", "2026-03-02"])
    _, out, _ = run(["recur", "apply", "--through", "2026-03-23"])
    assert out.strip() == "applied 4"
    assert [r["date"] for r in ledger_rows(workdir)] == ["2026-03-02", "2026-03-09", "2026-03-16", "2026-03-23"]


def test_apply_respects_until(workdir, run):
    run(["recur", "add", "--amount", "5", "--category", "gym", "--every", "monthly", "--start", "2026-01-15", "--until", "2026-02-28"])
    _, out, _ = run(["recur", "apply", "--through", "2026-12-31"])
    assert out.strip() == "applied 2"


def test_apply_monthly_clamps_to_month_end(workdir, run):
    run(["recur", "add", "--amount", "9", "--category", "x", "--every", "monthly", "--start", "2026-01-31"])
    _, out, _ = run(["recur", "apply", "--through", "2026-04-30"])
    assert out.strip() == "applied 4"
    assert [r["date"] for r in ledger_rows(workdir)] == ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"]


def test_apply_does_not_touch_manual_entries(workdir, run):
    add(run, "2026-01-01", "10", "sub", "manual")
    run(["recur", "add", "--amount", "10", "--category", "sub", "--every", "monthly", "--start", "2026-01-01"])
    _, out, _ = run(["recur", "apply", "--through", "2026-01-31"])
    assert out.strip() == "applied 1"
    assert len(ledger_rows(workdir)) == 2
