#!/usr/bin/env python3
"""Focused real-process regressions; pass the path to a freshly built Sendy."""
import concurrent.futures
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading


def first_use(binary, env, trials=100):
    with tempfile.TemporaryDirectory(prefix="sendy-first-use-") as scratch:
        for trial in range(trials):
            trial_env = dict(env, HOME=str(Path(scratch) / str(trial)))
            barrier = threading.Barrier(2)

            def create(_):
                barrier.wait()
                return subprocess.run([str(binary), "create", "1"], env=trial_env,
                                      capture_output=True, timeout=15)

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                calls = list(pool.map(create, range(2)))
            assert all(p.returncode == 0 and not p.stderr for p in calls), (
                trial, [(p.returncode, p.stdout, p.stderr) for p in calls])
            assert {p.stdout for p in calls} == {b"a1000\n", b"a1001\n"}
    print(f"PASS: simultaneous first use, {trials} fresh stores / {trials * 2} processes", flush=True)


def special_templates(binary, env):
    with tempfile.TemporaryDirectory(prefix="sendy-special-templates-") as scratch:
        root = Path(scratch)
        directory = root / ".sendy/templates"
        directory.mkdir(parents=True)
        home = root / "home"
        template_env = dict(env, HOME=str(home))
        (directory / "valid.txt").write_text("regular {{.value}}")
        (directory / "linked.txt").symlink_to("valid.txt")
        (directory / "broken.txt").write_text("{{if .x}}")
        os.mkfifo(directory / "stream.txt")
        (directory / "indirect.txt").symlink_to("stream.txt")

        def run(*args, code=1):
            p = subprocess.run([str(binary), *args], cwd=root, env=template_env,
                               capture_output=True, timeout=2)
            assert p.returncode == code, (args, p.returncode, p.stdout, p.stderr)
            return p

        p = run("template", "validate")
        assert not p.stdout
        for name in (b"stream.txt", b"indirect.txt", b"broken.txt"):
            assert name in p.stderr, p.stderr
        assert p.stderr.count(b"expected a regular file") == 2, p.stderr
        for name in ("stream", "indirect"):
            for args in (("template", "render", name),
                         ("template", "fields", name),
                         ("submit", "a1000", "--template", name),
                         ("reply", "a1000", "--template", name)):
                p = run(*args)
                assert not p.stdout and b"expected a regular file" in p.stderr
        assert not home.exists(), "template failures opened the conversation store"
        p = run("template", "render", "linked", "--set", "value=works", code=0)
        assert p.stdout == b"regular works" and not p.stderr
        p = run("template", "fields", "linked", code=0)
        assert p.stdout == b'["value"]\n' and not p.stderr
        for name in ("stream", "indirect", "broken"):
            (directory / (name + ".txt")).unlink()
        assert not run("template", "validate", code=0).stdout
    print("PASS: FIFO and symlink diagnostics, aggregate validation, no store mutation", flush=True)


def template_fields(binary, env):
    with tempfile.TemporaryDirectory(prefix="sendy-fields-") as scratch:
        root = Path(scratch)
        home = root / "home"
        field_env = dict(env, HOME=str(home))
        directory = root / ".sendy/templates"

        def run(*args, cwd=root, code=0):
            p = subprocess.run([str(binary), "template", *args], cwd=cwd, env=field_env,
                               capture_output=True, timeout=2)
            assert p.returncode == code, (args, p.returncode, p.stdout, p.stderr)
            return p

        missing = run("fields", "review", code=1)
        assert not missing.stdout and b"project root" in missing.stderr
        assert missing.stderr == run("render", "review", code=1).stderr
        directory.mkdir(parents=True)
        (directory / "review.txt").write_text("{{.name}} {{ .filename }} {{.name}} {{.Z}} {{._x}} {{.a}}")
        (directory / "plain.txt").write_text("Fixed text.\n")
        before = {p.name: p.read_bytes() for p in directory.iterdir()}
        for name, expected in (("review", b'["Z","_x","a","filename","name"]\n'), ("plain", b"[]\n")):
            p = run("fields", name)
            assert p.stdout == expected and not p.stderr
        assert before == {p.name: p.read_bytes() for p in directory.iterdir()}
        for name in ("missing", "../review", "Review", ""):
            p = run("fields", name, code=1)
            assert not p.stdout and b"available templates: plain, review" in p.stderr
            assert p.stderr == run("render", name, code=1).stderr
        for source in (b"", b"\xff", b"line one\n{{.x", b"line one\n{{if .x}}yes{{end}}"):
            (directory / "invalid.txt").write_bytes(source)
            p = run("fields", "invalid", code=1)
            assert not p.stdout and b"invalid template" in p.stderr
            assert p.stderr == run("render", "invalid", code=1).stderr
        for args in (("fields",), ("fields", "review", "extra"),
                     ("fields", "review", "--set", "filename=x"),
                     ("fields", "review", "--template", "plain")):
            p = run(*args, code=1)
            assert not p.stdout and b"usage:" in p.stderr and b"template fields NAME" in p.stderr
        nested = root / "nested"
        nested.mkdir()
        p = run("fields", "review", cwd=nested, code=1)
        assert not p.stdout and b"project root" in p.stderr
        assert not home.exists(), "field discovery opened the conversation store"
    print("PASS: template fields JSON, sorting, duplicates, fixed text, diagnostics, arity, project lookup, no store mutation", flush=True)


def daily_cleanup(binary, env):
    with tempfile.TemporaryDirectory(prefix="sendy-cleanup-") as scratch:
        root = Path(scratch)
        home = root / "home"
        cleanup_env = dict(env, HOME=str(home))
        (root / ".sendy/templates").mkdir(parents=True)

        def run(*args):
            p = subprocess.run([str(binary), *args], cwd=root, env=cleanup_env,
                               capture_output=True, timeout=15)
            assert p.returncode == 0 and not p.stderr, (args, p.stdout, p.stderr)
            return p.stdout

        assert run("create", "1") == b"a1000\n"
        with sqlite3.connect(home / ".sendy/conversations.db") as db:
            db.executescript("""
                WITH RECURSIVE ids(n) AS (VALUES(1) UNION ALL SELECT n+1 FROM ids WHERE n<117000)
                INSERT INTO conversations(id,last_used,generation)
                SELECT char(97+n/9000)||printf('%04d',1000+n%9000),unixepoch(),printf('fixture-%d',n) FROM ids;
                UPDATE conversations SET last_used=unixepoch()-15*86400,closed=1 WHERE id='a1000';
                INSERT INTO replies VALUES('a1000',1,'discard this old reply');
                UPDATE maintenance SET last_cleanup_day='';
                CREATE TABLE checks(day TEXT);
                CREATE TRIGGER count_checks AFTER UPDATE ON maintenance BEGIN
                    INSERT INTO checks VALUES(NEW.last_cleanup_day);
                END;
            """)
            assert run("template", "validate") == b""
            assert db.execute("SELECT count(*) FROM checks").fetchone()[0] == 0
            barrier = threading.Barrier(8)

            def create(_):
                barrier.wait()
                return run("create", "1").strip()

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                ids = list(pool.map(create, range(8)))
            assert len(set(ids)) == 8 and b"a1000" in ids, ids
            assert db.execute("SELECT count(*) FROM checks").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM replies").fetchone()[0] == 0
            # Stale IDs introduced after the check survive until a later day.
            db.execute("UPDATE conversations SET last_used=0 WHERE id='a1001'")
            db.commit()
            run("create", "1")
            assert db.execute("SELECT last_used FROM conversations WHERE id='a1001'").fetchone() == (0,)
            assert db.execute("SELECT count(*) FROM checks").fetchone()[0] == 1
    print("PASS: concurrent daily cleanup runs once, reclaims IDs/replies, skips template commands", flush=True)


if __name__ == "__main__":
    binary = Path(sys.argv[1]).resolve()
    first_use(binary, os.environ)
    special_templates(binary, os.environ)
    template_fields(binary, os.environ)
    daily_cleanup(binary, os.environ)
