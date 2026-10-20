"""Existing behaviour must be unchanged: these mirror the seed project's own tests."""
from ledger.money import format_cents, parse_amount


def test_add_then_list_unchanged(workdir, run):
    code, out, _ = run(["add", "--date", "2026-10-01", "--amount", "12.50", "--category", "groceries", "--note", "market"])
    assert code == 0
    assert out.strip() == "added #1 2026-10-01 12.50 groceries"
    code, out, _ = run(["list"])
    lines = out.strip().splitlines()
    assert lines[0].startswith("#1 2026-10-01")
    assert lines[-1] == "total 12.50"


def test_list_filters_unchanged(workdir, run):
    run(["add", "--date", "2026-09-30", "--amount", "5", "--category", "fuel"])
    run(["add", "--date", "2026-10-01", "--amount", "7", "--category", "fuel"])
    _, out, _ = run(["list", "--month", "2026-10", "--category", "fuel"])
    assert out.strip().splitlines()[-1] == "total 7.00"


def test_money_helpers_unchanged():
    assert parse_amount("12.5") == 1250
    assert format_cents(-307) == "-3.07"


def test_ledger_file_format_unchanged(workdir, run):
    run(["add", "--date", "2026-10-01", "--amount", "1.00", "--category", "a", "--note", "n"])
    text = (workdir / "ledger.csv").read_text()
    assert text.splitlines()[0] == "id,date,amount_cents,category,note"
    assert text.splitlines()[1] == "1,2026-10-01,100,a,n"
