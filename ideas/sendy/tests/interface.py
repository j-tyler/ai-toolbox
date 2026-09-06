#!/usr/bin/env python3
"""Real CLI/process + consuming-project setup acceptance test (includes a 60s wait).

Run from anywhere: python3 tests/interface.py. Needs Go, make, flock, Bash, jq, sha256sum.
Optional SENDY_COVERAGE_DIR records production binary coverage with go build -cover.
All conversations and installations live in temporary HOME/project directories.
"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

from regressions import broken_stdout, daily_cleanup, first_use, setup_diagnostics, special_templates, template_fields
from file_roundtrip import file_roundtrip

SOURCE = Path(__file__).resolve().parents[1]
CHILDREN = []


def checked(command, *, cwd, env, data=None, code=0, timeout=120):
    p = subprocess.run(command, cwd=cwd, env=env, input=data, capture_output=True, timeout=timeout)
    assert p.returncode == code, (command, p.returncode, p.stdout, p.stderr)
    return p


def main():
    with tempfile.TemporaryDirectory(prefix="sendy-interface-") as scratch:
        root = Path(scratch)
        project = root / "project"
        project.mkdir()
        env = dict(os.environ)
        for key in ("GOPATH", "GOCACHE"):
            env[key] = subprocess.check_output(["go", "env", key], text=True).strip()
        env["HOME"] = str(root / "home")
        env["SENDY_SOURCE"] = str(SOURCE)
        # Setup must disable cgo even when the caller enables it.
        env["CGO_ENABLED"] = "1"
        coverage = env.get("SENDY_COVERAGE_DIR")
        if coverage:
            Path(coverage).mkdir(parents=True, exist_ok=True)
            env["GOCOVERDIR"] = str(Path(coverage).resolve())
            env["GOFLAGS"] = (env.get("GOFLAGS", "") + " -cover").strip()
        (project / "tools").mkdir()
        for name in ("ensure-sendy", "sendy.version"):
            shutil.copy2(SOURCE / "tools" / name, project / "tools" / name)
        shutil.copy2(SOURCE / "Makefile", project / "Makefile")
        shutil.copytree(SOURCE / ".sendy", project / ".sendy")
        binary = project / ".tools/bin/sendy"
        templates_before = {p.name: p.read_bytes() for p in (project / ".sendy/templates").iterdir()}

        def setup(cwd=project, code=0, timeout=300):
            return checked(["make", "sendy"], cwd=cwd, env=env, code=code, timeout=timeout)

        def cli(*args, data=b"", code=0, cwd=project, timeout=10):
            return checked([str(binary), *args], cwd=cwd, env=env, data=data, code=code, timeout=timeout)

        def submit(id, message=b"child result", *args):
            p = subprocess.Popen([str(binary), "submit", id, *args], cwd=project, env=env,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            CHILDREN.append(p)
            p.stdin.write(message)
            p.stdin.close()
            p.stdin = None
            return p

        def receive(p, code=0):
            out, err = p.communicate(timeout=10)
            assert p.returncode == code, (p.returncode, out, err)
            return out, err

        def wait(*ids):
            return json.loads(cli("wait", *ids, "--timeout", "1").stdout)

        def unchanged_binary(before):
            st = binary.stat()
            assert (st.st_ino, st.st_mtime_ns, hashlib.sha256(binary.read_bytes()).hexdigest()) == before

        print("Building a consuming project with eight concurrent first-time setup processes...", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: setup(), range(8)))
        assert templates_before == {p.name: p.read_bytes() for p in (project / ".sendy/templates").iterdir()}
        build_info = checked(["go", "version", "-m", str(binary)], cwd=project, env=env).stdout
        assert b"\tbuild\tCGO_ENABLED=0\n" in build_info, build_info
        st = binary.stat()
        fingerprint = st.st_ino, st.st_mtime_ns, hashlib.sha256(binary.read_bytes()).hexdigest()
        first_use(binary, env)
        broken_stdout(binary, env)
        special_templates(binary, env)
        template_fields(binary, env)
        daily_cleanup(binary, env)
        setup_diagnostics(SOURCE, env)
        for name, expected in (("review", ["filename", "name"]), ("completion", ["filename"]), ("staged-review", [])):
            fields = cli("template", "fields", name)
            assert json.loads(fields.stdout) == expected and not fields.stderr
        assert not (Path(env["HOME"]) / ".sendy").exists(), "supplied template discovery opened the store"
        # Special template inputs must also fail setup promptly without replacement.
        fifo = project / ".sendy/templates/stream.txt"
        os.mkfifo(fifo)
        failed = setup(code=2, timeout=2)
        assert b"stream.txt" in failed.stderr and b"expected a regular file" in failed.stderr
        assert b"The executable is installed, but template setup did not complete" in failed.stderr
        unchanged_binary(fingerprint)
        fifo.unlink()
        assert cli("--version").stdout == b"sendy " + (project / "tools/sendy.version").read_bytes()
        # Help must return even while stdin stays open, without initializing storage.
        help_reference = cli("help")
        assert help_reference.stdout and not help_reference.stderr
        global_help_args = (("--help",), ("-h",), ("help", "--help"),
                            ("help", "-h"), ("--help", "--help"))
        for args in global_help_args + (("submit", "--help"), ("help", "submit", "--help"),
                                        ("template", "render", "--help")):
            p = subprocess.Popen([str(binary), *args], cwd=root, env=env,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            CHILDREN.append(p)
            # Drain stdout while leaving stdin open: a full help page may exceed
            # pipe capacity, so waiting before reading could deadlock the test.
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                output = pool.submit(p.stdout.read)
                try:
                    p.wait(timeout=5)
                finally:
                    if p.poll() is None:
                        p.kill()
                    p.stdin.close()
                text = output.result(timeout=5)
            assert p.returncode == 0 and text and p.stderr.read() == b"", args
            if args in global_help_args:
                assert text == help_reference.stdout
        assert not (Path(env["HOME"]) / ".sendy").exists(), "help opened the store"
        assert cli("template", "validate").stdout == b""
        rendered = cli("template", "render", "review", "--set", "filename=server.go", "--set", "name=Alice").stdout
        assert rendered == b"You are reviewing server.go.\nYour reviewer name is Alice.\n\nCheck correctness, identify missing cases, and explain your findings.\n"
        # Fresh project setup creates an empty template directory without a registry.
        empty_project = root / "empty-project"
        shutil.copytree(project / "tools", empty_project / "tools")
        shutil.copy2(project / "Makefile", empty_project / "Makefile")
        setup(empty_project)
        assert list((empty_project / ".sendy/templates").iterdir()) == []
        failed = cli("template", "render", "review", cwd=empty_project, code=1)
        assert b"available templates: (none)" in failed.stderr
        nested = project / "nested"
        nested.mkdir()
        assert b"project root" in cli("template", "validate", cwd=nested, code=1).stderr

        file_roundtrip(binary, env)

        print("Exercising concurrent creation, exact text, blocking submissions and repeated rounds...", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            batches = list(pool.map(lambda _: cli("create", "2").stdout.decode().split(), range(12)))
        ids = [id for batch in batches for id in batch]
        assert len(set(ids)) == 24
        assert all(len(id) == 5 and id[0].islower() and id[1:].isdigit() and id[1] != "0" for id in ids)
        first, second, pending, closed = ids[:4]
        cli("close", closed)
        exact = '  {"value":"$100 = \\\""}\n世界\x00no final newline'.encode()
        p1, p2 = submit(first, exact), submit(second, b"two")
        snap = wait(second, closed, first)
        assert snap == {"status": "ready", "results": [{"id": second, "message": "two"}, {"id": first, "message": exact.decode()}], "pending": [], "closed": [closed]}
        assert wait(second, closed, first) == snap
        assert p1.poll() is None and p2.poll() is None
        assert b"outstanding submission" in cli("submit", first, data=b"duplicate", code=1).stderr
        assert wait(first)["results"][0]["message"] == exact.decode()
        cli("reply", pending, data=b"unsolicited", code=1)
        cli("close", pending, "z1099", code=1)
        # Invalid template/UTF-8/empty stdin must not submit a result.
        bad = cli("submit", pending, "--template", "review", "--set", "filenmae=x", "--set", "name=A", "--set", "name=B", code=1)
        assert bad.stdout == b""
        for text in (b"Missing fields: filename", b"Unexpected fields: filenmae", b"Duplicate fields: name", b"Expected fields: filename, name", b"No message was sent."):
            assert text in bad.stderr
        cli("submit", pending, data=b"\xff", code=1)
        cli("submit", pending, data=b"", code=1)
        for args in (("create", "234000"), ("create", "0"), ("wait", first), ("wait", first, first, "--timeout", "1"), ("submit", first, "--timeout", "1"), ("close", first, first)):
            assert cli(*args, code=1).stdout == b""
        # A blocked submit remains blocked through repeated/concurrent setup.
        setup()
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda _: setup(), range(6)))
        unchanged_binary(fingerprint)
        assert p1.poll() is None and p2.poll() is None
        assert wait(first)["results"][0]["message"] == exact.decode()
        instruction = b"instruction\n\x00= {{.literal}}"
        assert cli("reply", first, data=instruction).stdout == b""
        assert receive(p1) == (instruction, b"")
        assert cli("reply", second, "--template", "review", "--set", "filename=server.go", "--set", "name=Alice", data=b"ignored stdin").stdout == b""
        assert receive(p2) == (rendered, b"")
        for n in range(3):
            p1 = submit(first, f"round {n}".encode())
            p2 = submit(second, b"ignored stdin", "--template", "completion", "--set", "filename=report.md")
            snap = wait(first, second)
            assert [entry["message"] for entry in snap["results"]] == [f"round {n}", "Completed report.md.\n"]
            cli("reply", first, data=b"next")
            cli("reply", second, data=b"next two")
            assert receive(p1) == (b"next", b"")
            assert receive(p2) == (b"next two", b"")
        # Wait started before results: separate processes, no in-process stand-in.
        wp = subprocess.Popen([str(binary), "wait", first, second, "--timeout", "1"], cwd=project, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        CHILDREN.append(wp)
        time.sleep(0.1)
        assert wp.poll() is None
        p1, p2 = submit(first, b"after wait"), submit(second, b"second after wait")
        out, err = receive(wp)
        assert not err and json.loads(out)["status"] == "ready"

        print("Running the documented real one-minute timeout with ready, pending and closed IDs...", flush=True)
        start = time.monotonic()
        result = cli("wait", second, pending, closed, first, "--timeout", "1", timeout=75)
        elapsed = time.monotonic() - start
        snap = json.loads(result.stdout)
        assert 59.5 <= elapsed < 75, elapsed
        assert snap == {"status": "timeout", "results": [{"id": second, "message": "second after wait"}, {"id": first, "message": "after wait"}], "pending": [pending], "closed": [closed]}
        assert p1.poll() is None and p2.poll() is None
        cli("close", first, second)
        out, diag = receive(p1, 2)
        assert not out and diag.startswith(b"sendy: conversation closed\n") and b"End the child session" in diag
        out, diag = receive(p2, 2)
        assert not out and diag.startswith(b"sendy: conversation closed\n") and b"End the child session" in diag
        cli("submit", first, data=b"later", code=2)
        cli("reply", first, data=b"later", code=1)
        assert wait(first)["closed"] == [first]
        # A reply already accepted must survive immediate closure.
        p = submit(pending, b"ready")
        wait(pending)
        os.kill(p.pid, signal.SIGSTOP)
        cli("reply", pending, data=b"accepted before close")
        cli("close", pending)
        os.kill(p.pid, signal.SIGCONT)
        assert receive(p) == (b"accepted before close", b"")
        cli("close", *ids)
        # Reading through EOF precedes submission; a parent wait stays blocked until EOF.
        eof_id = cli("create", "1").stdout.decode().strip()
        eof_child = subprocess.Popen([str(binary), "submit", eof_id], cwd=project, env=env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        CHILDREN.append(eof_child)
        eof_child.stdin.write(b"before EOF")
        eof_child.stdin.flush()
        eof_wait = subprocess.Popen([str(binary), "wait", eof_id, "--timeout", "1"], cwd=project, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        CHILDREN.append(eof_wait)
        time.sleep(0.15)
        assert eof_wait.poll() is None and eof_child.poll() is None
        eof_child.stdin.write(b" after EOF")
        eof_child.stdin.close()
        eof_child.stdin = None
        out, err = receive(eof_wait)
        assert not err and json.loads(out)["results"] == [{"id": eof_id, "message": "before EOF after EOF"}]
        cli("close", eof_id)
        out, diag = receive(eof_child, 2)
        assert not out and diag.startswith(b"sendy: conversation closed\n") and b"End the child session" in diag
        # Working-directory changes do not select another conversation store.
        assert wait(ids[-1])["closed"] == [ids[-1]]
        assert json.loads(cli("wait", ids[-1], "--timeout", "1", cwd=empty_project).stdout)["closed"] == [ids[-1]]

        print("Checking template errors and that setup rejects damage/mismatch without replacement...", flush=True)
        template_dir = project / ".sendy/templates"
        (template_dir / "bad.txt").write_text("line one\n{{if .name}}no{{end}}")
        (template_dir / "Wrong.txt").write_bytes(b"\xff")
        bad = cli("template", "validate", code=1)
        assert bad.stdout == b"" and b"bad.txt:2:1" in bad.stderr and b"Wrong.txt" in bad.stderr and b"UTF-8" in bad.stderr
        setup(code=2)
        unchanged_binary(fingerprint)
        (template_dir / "bad.txt").unlink()
        (template_dir / "Wrong.txt").unlink()
        (template_dir / "completion.txt").write_text("Changed {{.filename}}")
        setup()
        unchanged_binary(fingerprint)
        assert cli("template", "render", "completion", "--set", "filename=x=y").stdout == b"Changed x=y"
        pinfile = project / "tools/sendy.version"
        pin = pinfile.read_bytes()
        pinfile.write_text("v99.0.0\n")
        assert b"separate maintenance" in setup(code=2).stderr
        unchanged_binary(fingerprint)
        pinfile.write_bytes(pin)
        binary_bytes = binary.read_bytes()
        damaged = binary_bytes + b"damage"
        replacement = binary.with_name("sendy-damaged")
        replacement.write_bytes(damaged)
        replacement.chmod(0o755)
        replacement.replace(binary)
        assert b"damaged installation" in setup(code=2).stderr
        assert binary.read_bytes() == damaged
        replacement.write_bytes(binary_bytes)  # Explicit fixture maintenance, never done by setup.
        replacement.chmod(0o755)
        replacement.replace(binary)
        setup()
        assert wait(first)["closed"] == [first]
        print(f"PASS: full CLI, separate concurrent processes, 4 rounds, templates, setup; timeout {elapsed:.3f}s", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        for child in CHILDREN:
            if child.poll() is None:
                child.kill()
                child.wait()
