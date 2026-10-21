"""The SQLite migration, black box. The rest of this directory is the cloudbill-report hidden suite,
copied in by scripts/build_tasks.py; this task's config (hidden_answers_from = "database") makes it ask
every question of a database loaded from the files, so it is the database's correctness oracle. The
tests here check what is new: loading, provenance, the schema file, and that answers from files and from
the database are byte-identical."""
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

import billing_gen as g
import pytest
from conftest import CAP_MB, LARGE_ROWS, WORKSPACE, by_key, close, measured, run_tool

QUESTIONS = [
    ["costs", "--by", "account"], ["costs", "--by", "service"], ["costs", "--by", "tag:team"], ["daily"],
    ["daily", "--from", "2026-08-30", "--to", "2026-09-02"], ["top", "--by", "resource", "-n", "3"],
    ["untagged", "--tag", "team"], ["credits"], ["mom"], ["mom", "--by", "service"], ["daily-stats"], ["rejects"],
]


def load_json(cli, store, *files):
    code, out, err = cli("load", "--db", store, *files, "--format", "json")
    assert code == 0, f"load exited {code}: {err[-800:]}"
    return out


def files_rows(cli_json, store):
    return cli_json("files", "--db", store)["rows"]


@pytest.fixture(scope="module")
def loaded(scenario, tmp_path_factory):
    """The scenario's two files loaded, in command-line order, into one database."""
    d = tmp_path_factory.mktemp("db")
    store = d / "bill.db"
    code, _, err = run_tool(["load", "--db", store, *scenario[1]], d)
    assert code == 0, err[-800:]
    return store


@pytest.mark.parametrize("question", QUESTIONS, ids=[" ".join(q) for q in QUESTIONS])
def test_answers_from_the_database_are_byte_identical(scenario, loaded, cli, cli_files, question):
    for fmt in ("text", "json", "csv"):
        from_files = cli_files(*question, "--format", fmt, *scenario[1])
        assert from_files[0] == 0, from_files[2][-500:]
        assert cli(*question, "--format", fmt, "--db", loaded) == from_files, f"{fmt} differs between files and --db"


def dump(store) -> list[str]:
    with sqlite3.connect(store) as conn:
        return list(conn.iterdump())


def tables(conn) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")}


def test_schema_file_builds_a_working_database(tmp_path, scenario, loaded, cli, cli_json, cli_files_json):
    found = [p for p in WORKSPACE.rglob("schema.sql")
             if not {".git", "tests", ".eval", "__pycache__"} & set(p.relative_to(WORKSPACE).parts)]
    assert len(found) == 1, f"expected one schema.sql in the repository, found {[str(p) for p in found]}"
    store = tmp_path / "from-schema.db"
    with sqlite3.connect(store) as conn:
        conn.executescript(found[0].read_text(encoding="utf-8"))
        created = tables(conn)
    assert created, "schema.sql created no tables"
    load_json(cli, store, *scenario[1])
    assert cli_json("costs", "--by", "service", "--db", store) == cli_files_json("costs", "--by", "service", *scenario[1])
    with sqlite3.connect(loaded) as conn:  # a database the tool built itself uses no table the schema file lacks
        used = tables(conn)
    assert used <= created, f"tables the tool creates that schema.sql does not: {sorted(used - created)}"


def test_loading_the_same_file_again_changes_nothing(tmp_path, scenario, cli, cli_json):
    store = tmp_path / "bill.db"
    load_json(cli, store, *scenario[1])
    before = [cli(*q, "--format", "json", "--db", store) for q in (["costs", "--by", "account"], ["rejects"], ["mom"])]
    listed = files_rows(cli_json, store)
    contents = dump(store)
    load_json(cli, store, scenario[1][0])
    load_json(cli, store, *scenario[1])
    renamed = tmp_path / "copy-of-august.csv"
    shutil.copy(scenario[1][0], renamed)
    load_json(cli, store, renamed)  # the same contents under another name
    assert dump(store) == contents
    assert [cli(*q, "--format", "json", "--db", store) for q in (["costs", "--by", "account"], ["rejects"], ["mom"])] == before
    assert files_rows(cli_json, store) == listed and len(listed) == 2


def test_incremental_load_of_a_second_month(tmp_path, scenario, cli, cli_json, cli_files_json):
    exports, (aug, sep) = scenario
    store = tmp_path / "bill.db"
    load_json(cli, store, aug)
    assert cli_json("mom", "--db", store)["rows"] == cli_files_json("mom", aug)["rows"]
    load_json(cli, store, sep)
    assert cli_json("mom", "--by", "account", "--db", store) == cli_files_json("mom", "--by", "account", aug, sep)
    doc = cli_json("costs", "--by", "service", "--db", store)
    assert close(doc["total"]["net"], g.totals(exports, "service")[1]["net"])
    assert doc["rejected_rows"] == g.rejected_count(exports)


def test_restatement_across_files_whichever_is_loaded_first(tmp_path, scenario, cli, cli_json):
    exports, (aug, sep) = scenario
    groups, total = g.totals(exports, "account")
    for order in ((aug, sep), (sep, aug)):
        store = tmp_path / f"{order[0].stem}.db"
        for f in order:
            load_json(cli, store, f)
        rows = by_key(cli_json("costs", "--by", "account", "--db", store)["rows"])
        for k, exp in groups.items():
            assert close(rows[k]["net"], exp["net"]), f"{k} after loading {[p.name for p in order]}"


def test_files_listing_records_provenance(tmp_path, scenario, cli, cli_json):
    exports, paths = scenario
    store = tmp_path / "bill.db"
    load_json(cli, store, *paths)
    rows = files_rows(cli_json, store)
    assert [Path(str(r["path"])).name for r in rows] == [p.name for p in paths]
    for r, ex, p in zip(rows, exports, paths):
        assert r["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
        assert int(r["rows"]) == sum(1 for it in ex.items if not it.rejected), p.name
        assert int(r["rejected"]) == sum(1 for it in ex.items if it.rejected), p.name
        assert str(r["loaded_at"]).strip()


def test_a_failed_load_loads_nothing(tmp_path, scenario, cli, cli_json):
    aug, sep = scenario[1]
    store = tmp_path / "bill.db"
    notes = tmp_path / "notes.csv"
    notes.write_text("team,limit\nweb,100\n", encoding="utf-8")
    code, out, err = cli("load", "--db", store, aug, notes)
    assert code == 1 and out == "" and err.strip()
    if store.exists():
        assert files_rows(cli_json, store) == []
    load_json(cli, store, aug)
    contents = dump(store)
    code, out, err = cli("load", "--db", store, sep, notes)  # a usable file before the unusable one: still nothing
    assert code == 1 and out == "" and err.strip()
    assert dump(store) == contents and len(files_rows(cli_json, store)) == 1
    load_json(cli, store, *scenario[1])
    assert len(files_rows(cli_json, store)) == 2


def test_database_mistakes(tmp_path, scenario, cli, cli_files):
    code, out, err = cli("daily", "--db", tmp_path / "missing.db")
    assert code == 1 and out == "" and err.strip()
    other = tmp_path / "other.db"
    with sqlite3.connect(other) as conn:
        conn.execute("CREATE TABLE notes (body TEXT)")
    code, out, err = cli("daily", "--db", other)
    assert code == 1 and out == "" and err.strip()
    store = tmp_path / "bill.db"
    load_json(cli, store, *scenario[1])
    assert cli_files("daily", "--db", store, *scenario[1])[0] == 2
    assert cli_files("daily")[0] == 2


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="ru_maxrss units are Linux's")
def test_load_and_query_a_large_export_under_the_memory_cap(tmp_path, large):
    path, expected = large
    store = tmp_path / "large.db"
    code, peak_load, _, err = measured(tmp_path, "load", "--db", store, path)
    assert code == 0, err[-800:]
    code, peak_query, out, err = measured(tmp_path, "costs", "--by", "service", "--format", "json", "--db", store)
    assert code == 0, err[-800:]
    doc = json.loads(out)
    assert close(doc["total"]["net"], expected["total"]["net"]) and doc["rejected_rows"] == expected["rejected"]
    assert peak_load < CAP_MB, f"load peaked at {peak_load:.0f} MB on {LARGE_ROWS} rows; the brief allows {CAP_MB} MB"
    assert peak_query < CAP_MB, f"a question from the database peaked at {peak_query:.0f} MB; the brief allows {CAP_MB} MB"
