from pathlib import Path

import pytest

from ledger.cli import main


@pytest.fixture
def ledger_file(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "ledger.csv"
    monkeypatch.setenv("LEDGER_FILE", str(path))
    return path


def run(argv, capsys):
    code = main(argv)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_add_then_list(ledger_file, capsys):
    code, out, _ = run(["add", "--date", "2026-10-01", "--amount", "12.50", "--category", "groceries", "--note", "market"], capsys)
    assert code == 0
    assert out.strip() == "added #1 2026-10-01 12.50 groceries"
    code, out, _ = run(["list"], capsys)
    assert code == 0
    lines = out.strip().splitlines()
    assert lines[0].startswith("#1 2026-10-01")
    assert lines[-1] == "total 12.50"


def test_ids_increase(ledger_file, capsys):
    run(["add", "--date", "2026-10-01", "--amount", "1", "--category", "a"], capsys)
    run(["add", "--date", "2026-10-02", "--amount", "2", "--category", "b"], capsys)
    code, out, _ = run(["list"], capsys)
    assert "#2 2026-10-02" in out


def test_list_filters(ledger_file, capsys):
    run(["add", "--date", "2026-09-30", "--amount", "5", "--category", "fuel"], capsys)
    run(["add", "--date", "2026-10-01", "--amount", "7", "--category", "fuel"], capsys)
    run(["add", "--date", "2026-10-02", "--amount", "9", "--category", "food"], capsys)
    _, out, _ = run(["list", "--month", "2026-10"], capsys)
    assert out.strip().splitlines()[-1] == "total 16.00"
    _, out, _ = run(["list", "--month", "2026-10", "--category", "fuel"], capsys)
    assert out.strip().splitlines()[-1] == "total 7.00"


def test_invalid_amount(ledger_file, capsys):
    code, _, err = run(["add", "--date", "2026-10-01", "--amount", "abc", "--category", "x"], capsys)
    assert code == 2
    assert "invalid amount" in err


def test_invalid_date(ledger_file, capsys):
    code, _, err = run(["add", "--date", "2026-13-01", "--amount", "1", "--category", "x"], capsys)
    assert code == 2
    assert "invalid date" in err


def test_file_flag_overrides_env(tmp_path, ledger_file, capsys):
    other = tmp_path / "other.csv"
    run(["--file", str(other), "add", "--date", "2026-10-01", "--amount", "1", "--category", "x"], capsys)
    assert other.exists()
    assert not ledger_file.exists()
