"""Parameter-file CLI acceptance, including validation before mutation or blocking."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile


def params_files(binary, env):
    with tempfile.TemporaryDirectory(prefix="sendy-params-") as scratch:
        project = Path(scratch)
        params_env = dict(env, HOME=str(project / "home"))
        templates = project / ".sendy/templates"
        templates.mkdir(parents=True)
        (templates / "fields.txt").write_text("[{{.name}}]|[{{.value}}]")
        (templates / "plain.txt").write_text("fixed")
        (templates / "empty.txt").write_text("{{.name}}")
        params = project / "params"

        def cli(*args, code=0):
            p = subprocess.run([str(binary), *args], cwd=project, env=params_env,
                               input=b"ignored stdin", capture_output=True, timeout=5)
            assert p.returncode == code, (args, p.returncode, p.stdout, p.stderr)
            if code:
                assert not p.stdout and b"No message was sent" in p.stderr, p
            else:
                assert not p.stderr, p.stderr
            return p

        prefixes = (("template", "render", "fields"),
                    ("submit", "a1000", "--template", "fields"),
                    ("reply", "a1000", "--template", "fields"))
        invalid = (
            b'{"name":"x",}', b'{\nname=x\nvalue=y', b'[]', b'"name=x"',
            b'null', b'true', b'123', b'{"name":null}', b'{"name":false}',
            b'{"name":42}', b'{"name":{}}', b'{"name":[]}',
            b'{"name":"x"} {}', b'{"name":"x","name":"y","value":"z"}',
            b'{"name=x":"y","value":"z"}', b'name=x\nname=y\nvalue=z',
            b'name=x\nextra=y', b'name', b'name="unclosed', b'name="x" trailing',
            b'name="\\q"', b'name=\xff', b'\xef\xbb\xbfname=x', b'name=x\rvalue=y',
        )

        def check_failures():
            for content in invalid:
                params.write_bytes(content)
                for prefix in prefixes:
                    failed = cli(*prefix, "--params-file", str(params), code=1)
                    assert b"invalid file" in failed.stderr, failed.stderr
            for prefix in prefixes:
                for flags in (("--params-file",), ("--params-file", ""),
                              ("--params-file", "params", "--params-file", "params"),
                              ("--set", "name=x", "--params-file", "params"),
                              ("--params-file", "params", "--set", "name=x")):
                    cli(*prefix, *flags, code=1)
                for path in ("missing", ".sendy/templates", "fifo"):
                    failed = cli(*prefix, "--params-file", path, code=1)
                    assert b"invalid file" in failed.stderr, failed.stderr
            for command in ("submit", "reply"):
                failed = cli(command, "a1000", "--params-file", "params", code=1)
                assert b"requires --template" in failed.stderr, failed.stderr
            params.write_text('{"name":""}')
            for prefix in (("template", "render", "empty"),
                           ("submit", "a1000", "--template", "empty"),
                           ("reply", "a1000", "--template", "empty")):
                failed = cli(*prefix, "--params-file", "params", code=1)
                assert b"message must not be empty" in failed.stderr, failed.stderr

        os.mkfifo(project / "fifo")
        check_failures()
        assert not (project / "home").exists(), "validation opened storage"

        for content in (b"", b" \t\r\n# comment\r\n", b"{}"):
            params.write_bytes(content)
            assert cli("template", "render", "plain", "--params-file", "params").stdout == b"fixed"
            failed = cli("template", "render", "fields", "--params-file", "params", code=1)
            assert b"Missing fields: name, value" in failed.stderr, failed.stderr

        # Suffixes deliberately disagree with formats. Also exercise option-looking paths.
        expected = "[Alice]|[  世界 # = $HOME ${USER} $(touch sentinel)  \nnext\t]".encode()
        json_content = json.dumps({"name": "Alice", "value": "  世界 # = $HOME ${USER} $(touch sentinel)  \nnext\t"}).encode()
        dotenv_content = b' export name = Alice # note\r\nvalue="  ' + "世界".encode() + b' # = $HOME ${USER} $(touch sentinel)  \r\nnext\\t" # note\r\n'
        for path, content in (("json.env", json_content), ("dotenv.json", dotenv_content),
                              ("--help", json_content), ("-h", dotenv_content), ("-", json_content)):
            (project / path).write_bytes(content)
            assert cli("template", "render", "fields", "--params-file", path).stdout == expected
        assert not (project / "sentinel").exists(), "parameter text executed"
        assert not (project / "home").exists(), "render opened storage"

        assert cli("create", "1").stdout == b"a1000\n"
        with sqlite3.connect(project / "home/.sendy/conversations.db") as db:
            def state():
                return (db.execute("SELECT * FROM conversations").fetchall(),
                        db.execute("SELECT * FROM replies").fetchall())

            before = state()
            check_failures()
            assert state() == before, "invalid input mutated a pending conversation"
            for submit_file, reply_file in (("json.env", "dotenv.json"), ("dotenv.json", "json.env")):
                p = subprocess.Popen([str(binary), "submit", "a1000", "--params-file", submit_file,
                                      "--template", "fields"], cwd=project, env=params_env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    # stdin stays open: template mode must not read it before submitting.
                    ready = json.loads(cli("wait", "a1000", "--timeout", "1").stdout)
                    assert ready["results"] == [{"id": "a1000", "message": expected.decode()}], ready
                    assert p.poll() is None, "submit did not block for a reply"
                    before = state()
                    check_failures()
                    assert state() == before, "invalid input mutated an outstanding result"
                    assert p.poll() is None, "invalid reply released submit"
                    assert cli("reply", "a1000", "--template", "fields", "--params-file", reply_file).stdout == b""
                    out, err = p.communicate(timeout=5)
                    assert p.returncode == 0 and out == expected and not err, (p.returncode, out, err)
                finally:
                    if p.poll() is None:
                        p.kill()
                        p.communicate()
        cli("close", "a1000")
    print("PASS: JSON/dotenv parameter files, options, exact round trips, validation before state changes", flush=True)
