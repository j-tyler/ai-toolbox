"""Subprocess acceptance tests for quiet waits and recoverable child timeouts."""
import json
from pathlib import Path
import select
import signal
import subprocess
import tempfile
import time


def receive_recovery(binary, env):
    with tempfile.TemporaryDirectory(prefix="sendy-receive-") as scratch:
        recovery_env = dict(env, HOME=str(Path(scratch) / "home"))
        children = []

        def cli(*args, data=b"", code=0):
            p = subprocess.run([str(binary), *args], cwd=scratch, env=recovery_env,
                               input=data, capture_output=True, timeout=10)
            assert (p.returncode, p.stdout if code else b"") == (code, b""), (args, p.returncode, p.stdout, p.stderr)
            return p

        def start(*args, data=None):
            p = subprocess.Popen([str(binary), *args], cwd=scratch, env=recovery_env,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            children.append(p)
            if data is not None:
                p.stdin.write(data)
                p.stdin.close()
                p.stdin = None
            return p

        def quiet(*processes):
            assert all(p.poll() is None for p in processes)
            streams = [f for p in processes for f in (p.stdout, p.stderr)]
            assert not select.select(streams, [], [], 0.1)[0], "waiting command produced output"

        def finish(p, expected=b"", code=0, timeout=10):
            out, err = p.communicate(timeout=timeout)
            assert (p.returncode, out) == (code, expected), (p.returncode, out, err)
            if code == 0:
                assert err == b"", err
            return err

        def result(id, expected):
            snap = json.loads(cli("wait", id, "--timeout", "1").stdout)
            assert snap == {"status": "ready", "results": [{"id": id, "message": expected}], "pending": [], "closed": []}, snap

        try:
            id, empty = cli("create", "2").stdout.decode().split()
            assert b"no submission" in cli("receive", empty, code=1).stderr
            cli("close", empty)
            cli("receive", empty, code=2)

            started = time.monotonic()
            submit = start("submit", id, "--timeout", "1", data=b"timed work")
            result(id, "timed work")
            receiver = start("receive", id, "--timeout", "1")
            indefinite = start("receive", id)
            quiet(submit, receiver, indefinite)
            for p in (submit, receiver):
                diag = finish(p, code=3, timeout=75)
                assert b"timed out waiting for reply" in diag and b"sendy receive " + id.encode() in diag, diag
            elapsed = time.monotonic() - started
            assert 59.5 <= elapsed < 75, elapsed
            quiet(indefinite)
            result(id, "timed work")
            instruction = b' exact\r\n"quoted"\\\x00' + "世界\n\n".encode()
            cli("reply", id, data=instruction)
            finish(indefinite, instruction)
            assert cli("receive", id).stdout == instruction
            assert cli("receive", id, "--timeout", "1").stdout == instruction

            # The interrupted submit was durably recorded. Receive neither
            # resends it nor returns a reply from the preceding round.
            for sig in (signal.SIGTERM, signal.SIGKILL):
                submit = start("submit", id, data=b"interrupted work")
                result(id, "interrupted work")
                quiet(submit)
                submit.send_signal(sig)
                finish(submit, code=-sig)
                receiver = start("receive", id, "--timeout", "1")
                quiet(receiver)
                receiver.send_signal(sig)
                finish(receiver, code=-sig)
                result(id, "interrupted work")
                receiver = start("receive", id)
                quiet(receiver)
                cli("reply", id, data=instruction)
                # stdin stays open: receive must exit without waiting for EOF.
                receiver.wait(timeout=5)
                finish(receiver, instruction)

            # A reply accepted while no receiver is running survives closure.
            submit = start("submit", id, data=b"late reply work")
            result(id, "late reply work")
            submit.kill()
            finish(submit, code=-signal.SIGKILL)
            cli("reply", id, data=instruction)
            cli("close", id)
            assert cli("receive", id).stdout == instruction

            id = cli("create", "1").stdout.decode().strip()
            submit = start("submit", id, "--timeout", "1", data=b"close work")
            result(id, "close work")
            receiver = start("receive", id)
            quiet(submit, receiver)
            cli("close", id)
            for p in (submit, receiver):
                assert b"conversation closed" in finish(p, code=2)

            # Timed submit succeeds before its deadline, including templates.
            templates = Path(scratch) / ".sendy/templates"
            templates.mkdir(parents=True)
            (templates / "task.txt").write_text("work {{.name}}")
            id = cli("create", "1").stdout.decode().strip()
            submit = start("submit", id, "--template", "task", "--timeout", "1", "--set", "name=example")
            result(id, "work example")
            cli("reply", id, data=instruction)
            submit.wait(timeout=5)
            finish(submit, instruction)
            print(f"PASS: child timeout {elapsed:.3f}s, quiet receive, interruption recovery, late replies", flush=True)
        finally:
            for p in children:
                if p.poll() is None:
                    p.kill()
                p.communicate(timeout=10)
