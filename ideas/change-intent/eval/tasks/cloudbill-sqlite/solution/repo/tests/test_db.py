import json
import sqlite3
from pathlib import Path

import pytest

from cloudbill import db

QUESTIONS = [["costs", "--by", "service"], ["costs", "--by", "account"], ["daily"], ["top", "--by", "resource"],
             ["untagged", "--tag", "team"], ["credits"], ["mom", "--by", "account"], ["daily-stats"], ["rejects"]]


@pytest.fixture
def months(write_export):
    aug = write_export([{"unblended_cost": "10", "line_item_id": "x"}, {"unblended_cost": "#VALUE!"},
                        {"unblended_cost": "4", "tag:team": "web"}], name="aug.csv", bom=True)
    sep = write_export([{"usage_start": "2026-09-03T00:00:00Z", "unblended_cost": "7"},
                        {"unblended_cost": "12", "line_item_id": "x", "last_updated": "2026-09-04T00:00:00Z"}], name="sep.csv")
    return aug, sep


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: " ".join(q))
def test_database_answers_match_file_answers_byte_for_byte(run, months, tmp_path, question):
    store = tmp_path / "bill.db"
    assert run("load", "--db", store, *months)[0] == 0
    for fmt in ("text", "json", "csv"):
        assert run(*question, "--format", fmt, "--db", store) == run(*question, "--format", fmt, *months)


def test_load_twice_changes_nothing(run, run_json, months, tmp_path):
    store = tmp_path / "bill.db"
    run("load", "--db", store, *months)
    before = (run("costs", "--by", "service", "--db", store), run("rejects", "--db", store))
    again = run_json("load", "--db", store, *months)
    assert [r["status"] for r in again["rows"]] == ["already loaded", "already loaded"]
    assert (run("costs", "--by", "service", "--db", store), run("rejects", "--db", store)) == before
    assert len(run_json("files", "--db", store)["rows"]) == 2


def test_restatement_wins_whichever_file_is_loaded_first(run_json, months, tmp_path):
    aug, sep = months
    for order in ((aug, sep), (sep, aug)):
        store = tmp_path / f"{order[0].stem}.db"
        run_json("load", "--db", store, *order)
        assert run_json("costs", "--by", "service", "--db", store)["total"]["net"] == 23.0


def test_incremental_load_adds_a_month(run_json, months, tmp_path):
    aug, sep = months
    store = tmp_path / "bill.db"
    run_json("load", "--db", store, aug)
    assert [r["month"] for r in run_json("mom", "--db", store)["rows"]] == ["2026-08"]
    run_json("load", "--db", store, sep)
    assert run_json("mom", "--db", store) == run_json("mom", aug, sep)


def test_files_listing_records_provenance(run_json, months, tmp_path):
    store = tmp_path / "bill.db"
    run_json("load", "--db", store, *months)
    rows = run_json("files", "--db", store)["rows"]
    assert [(Path(r["path"]).name, r["rows"], r["rejected"]) for r in rows] == [("aug.csv", 2, 1), ("sep.csv", 2, 0)]
    assert rows[0]["sha256"] == db.sha256_of(months[0])
    with sqlite3.connect(store) as conn:
        assert conn.execute("SELECT f.path FROM line_items i JOIN files f USING (file_id) WHERE line_item_id = 'x'").fetchone()[0].endswith("sep.csv")


def test_a_failed_load_loads_nothing(run, run_json, months, tmp_path):
    store = tmp_path / "bill.db"
    bad = tmp_path / "notes.csv"
    bad.write_text("just,some\nnotes,here\n")
    code, out, err = run("load", "--db", store, months[0], bad)
    assert (code, out) == (1, "") and "not a billing export" in err
    assert run_json("files", "--db", store)["rows"] == []


def test_schema_file_builds_the_database(tmp_path, run_json, months):
    store = tmp_path / "fresh.db"
    with sqlite3.connect(store) as conn:
        conn.executescript(db.SCHEMA.read_text())
        conn.executescript(db.SCHEMA.read_text())  # applying twice is harmless
    run_json("load", "--db", store, *months)
    assert json.dumps(run_json("costs", "--by", "service", "--db", store)) == json.dumps(run_json("costs", "--by", "service", *months))


def test_database_mistakes(run, months, tmp_path):
    code, out, err = run("daily", "--db", tmp_path / "missing.db")
    assert (code, out) == (1, "") and "no such database" in err
    other = tmp_path / "other.db"
    sqlite3.connect(other).execute("CREATE TABLE t (x)").connection.close()
    assert run("daily", "--db", other)[0] == 1
    for argv in (["daily"], ["daily", "--db", other, *months]):
        with pytest.raises(SystemExit) as exc:
            run(*argv)
        assert exc.value.code == 2
