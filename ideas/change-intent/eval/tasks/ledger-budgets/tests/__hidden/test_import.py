import csv
from pathlib import Path

from conftest import add


def write_csv(path: Path, header, rows):
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def ledger_rows(workdir: Path):
    with (workdir / "ledger.csv").open(newline="") as fh:
        return list(csv.DictReader(fh))


def test_import_basic(workdir, run):
    bank = workdir / "bank.csv"
    write_csv(bank, ["Date", "Amount", "Memo"], [["2026-10-01", "12.50", "MARKET"], ["2026-10-02", "3.20", "COFFEE"]])
    code, out, err = run(["import", str(bank), "--date-col", "Date", "--amount-col", "Amount", "--note-col", "Memo"])
    assert code == 0, err
    assert out.strip() == "imported 2 skipped 0"
    rows = ledger_rows(workdir)
    assert [(r["date"], r["amount_cents"], r["note"], r["category"]) for r in rows] == [
        ("2026-10-01", "1250", "MARKET", "imported"),
        ("2026-10-02", "320", "COFFEE", "imported"),
    ]


def test_import_category_and_negate_and_date_format(workdir, run):
    bank = workdir / "bank.csv"
    write_csv(bank, ["Posted", "Amt"], [["10/05/2026", "-45.00"]])
    code, out, _ = run(["import", str(bank), "--date-col", "Posted", "--amount-col", "Amt", "--category", "fuel", "--date-format", "%m/%d/%Y", "--negate"])
    assert code == 0
    assert out.strip() == "imported 1 skipped 0"
    rows = ledger_rows(workdir)
    assert rows[0]["date"] == "2026-10-05"
    assert rows[0]["amount_cents"] == "4500"
    assert rows[0]["category"] == "fuel"


def test_import_skips_duplicates_within_file(workdir, run):
    bank = workdir / "bank.csv"
    write_csv(bank, ["d", "a", "n"], [["2026-10-01", "5.00", "x"], ["2026-10-01", "5.00", "x"], ["2026-10-01", "5.00", "y"]])
    _, out, _ = run(["import", str(bank), "--date-col", "d", "--amount-col", "a", "--note-col", "n"])
    assert out.strip() == "imported 2 skipped 1"


def test_import_skips_duplicates_against_ledger(workdir, run):
    add(run, "2026-10-01", "5.00", "imported", "x")
    bank = workdir / "bank.csv"
    write_csv(bank, ["d", "a", "n"], [["2026-10-01", "5.00", "x"], ["2026-10-02", "5.00", "x"]])
    _, out, _ = run(["import", str(bank), "--date-col", "d", "--amount-col", "a", "--note-col", "n"])
    assert out.strip() == "imported 1 skipped 1"
    assert len(ledger_rows(workdir)) == 2


def test_import_json_output(workdir, run_json):
    bank = workdir / "bank.csv"
    write_csv(bank, ["d", "a"], [["2026-10-01", "5.00"], ["2026-10-01", "5.00"]])
    data = run_json(["import", str(bank), "--date-col", "d", "--amount-col", "a", "--format", "json"])
    assert data == {"imported": 1, "skipped": 1}


def test_import_missing_column_exits_2_and_leaves_ledger(workdir, run):
    add(run, "2026-10-01", "1", "a")
    before = ledger_rows(workdir)
    bank = workdir / "bank.csv"
    write_csv(bank, ["d", "a"], [["2026-10-01", "5.00"]])
    code, out, err = run(["import", str(bank), "--date-col", "Date", "--amount-col", "a"])
    assert code == 2
    assert err.strip() != ""
    assert ledger_rows(workdir) == before


def test_import_rerun_of_same_file_adds_nothing(workdir, run):
    bank = workdir / "bank.csv"
    write_csv(bank, ["d", "a", "n"], [["2026-10-01", "5.00", "x"], ["2026-10-02", "6.00", "y"]])
    run(["import", str(bank), "--date-col", "d", "--amount-col", "a", "--note-col", "n"])
    _, out, _ = run(["import", str(bank), "--date-col", "d", "--amount-col", "a", "--note-col", "n"])
    assert out.strip() == "imported 0 skipped 2"
