import csv
import io
import subprocess
import sys
from pathlib import Path

import pytest

QUESTIONS = [["costs", "--by", "service"], ["costs", "--by", "account"], ["costs", "--by", "tag:team"], ["daily"],
             ["top", "--by", "resource", "-n", "2"], ["untagged", "--tag", "team"], ["credits"], ["mom"],
             ["mom", "--by", "service"], ["daily-stats"], ["rejects"]]


@pytest.fixture
def two_months(write_export):
    aug = write_export([
        {"unblended_cost": "1,200.5000", "tag:team": "data", "account_id": "012345678901"},
        {"unblended_cost": "-200.0000", "line_item_type": "Credit"},
        {"unblended_cost": "#VALUE!"},
        {"usage_start": "2026-08-31T23:00:00Z", "unblended_cost": "10", "line_item_id": "late"},
    ], name="aug.csv", bom=True)
    sep = write_export([
        {"usage_start": "2026-09-02T00:00:00Z", "unblended_cost": "50", "service": "COMPUTE ENGINE"},
        {"usage_start": "2026-08-31T23:00:00Z", "unblended_cost": "12", "line_item_id": "late",
         "last_updated": "2026-09-05T00:00:00Z"},
    ], name="sep.csv")
    return aug, sep


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: " ".join(q))
def test_every_question_in_every_format_counts_rejects(run, run_json, two_months, question):
    doc = run_json(*question, *two_months)
    assert doc["rejected_rows"] == 1
    code, text, _ = run(*question, *two_months)
    assert code == 0 and "rejected rows: 1" in text
    code, out, _ = run(*question, "--format", "csv", *two_months)
    assert code == 0 and out.rstrip().endswith("# rejected_rows: 1")
    header = next(csv.reader(io.StringIO(out)))
    assert header == list(doc["rows"][0]) if doc["rows"] else header


def test_costs_json(run_json, two_months):
    doc = run_json("costs", "--by", "account", *two_months)
    assert doc["rows"] == [
        {"key": "012345678901", "name": "acct-one", "charges": 1200.5, "credits": 0.0, "net": 1200.5},
        {"key": "111111111111", "name": "acct-one", "charges": 62.0, "credits": -200.0, "net": -138.0},
    ]
    assert doc["total"] == {"charges": 1262.5, "credits": -200.0, "net": 1062.5}


def test_date_range_is_inclusive_utc_days(run_json, two_months):
    doc = run_json("daily", "--from", "2026-08-31", "--to", "2026-09-02", *two_months)
    assert [(r["date"], r["net"]) for r in doc["rows"]] == [("2026-08-31", 12.0), ("2026-09-02", 50.0)]


def test_mom_flags_the_partial_month(run_json, two_months):
    rows = run_json("mom", *two_months)["rows"]
    assert [(r["month"], r["partial"]) for r in rows] == [("2026-08", False), ("2026-09", True)]


def test_rejects_name_file_and_line(run_json, two_months):
    rows = run_json("rejects", *two_months)["rows"]
    assert [(Path(r["file"]).name, r["line"]) for r in rows] == [("aug.csv", 4)]
    assert "#VALUE!" in rows[0]["reason"]


def test_output_is_deterministic_and_independent_of_file_order(run, two_months):
    aug, sep = two_months
    for fmt in ("text", "json", "csv"):
        first = run("costs", "--by", "service", "--format", fmt, aug, sep)
        assert first == run("costs", "--by", "service", "--format", fmt, aug, sep)
        assert first == run("costs", "--by", "service", "--format", fmt, sep, aug)


def test_exit_codes(run, two_months, tmp_path):
    other = tmp_path / "budget.csv"
    other.write_text("team,limit\nweb,10\n")
    code, out, err = run("costs", "--by", "service", other)
    assert (code, out) == (1, "") and "not a billing export" in err
    code, out, err = run("daily", tmp_path / "nope.csv")
    assert (code, out) == (1, "") and "nope.csv" in err
    for argv in (["costs", "--by", "region", *two_months], ["daily", "--from", "2026-13-01", *two_months],
                 ["daily", "--from", "2026-09-02", "--to", "2026-09-01", *two_months], ["top", "--by", "service", "-n", "0", *two_months],
                 ["forecast", *two_months]):
        with pytest.raises(SystemExit) as exc:
            run(*argv)
        assert exc.value.code == 2


def test_module_entry_point(two_months):
    proc = subprocess.run([sys.executable, "-m", "cloudbill", "top", "--by", "service", "-n", "1", *map(str, two_months)],
                          capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1])
    assert proc.returncode == 0, proc.stderr
    assert "Compute Engine" in proc.stdout and "1,062.50" in proc.stdout


def test_sample_answers(run_json):
    sample = sorted((Path(__file__).resolve().parents[1] / "sample").glob("*.csv"))
    assert len(sample) == 2
    doc = run_json("costs", "--by", "service", *sample)
    assert sum(r["net"] for r in doc["rows"]) == pytest.approx(doc["total"]["net"])
    assert doc["rejected_rows"] == len(run_json("rejects", *sample)["rows"]) > 0
