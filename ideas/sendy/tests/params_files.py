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
        (templates / "next.txt").write_text("Next: {{.task}}")
        (templates / "all.txt").write_text("[{{.text}}]|{{.number}}|{{.yes}}|{{.no}}|{{.nothing}}|{{.object}}|{{.array}}")
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
            b'null', b'true', b'123', b'{"name":null}', b'{"name":{}}', b'{"name":[]}',
            b'{"name":01,"value":null}', b'{"name":+1,"value":null}',
            b'{"name":1.,"value":null}', b'{"name":1e,"value":null}',
            b'{"name":NaN,"value":null}', b'{"name":Infinity,"value":null}',
            b'{"name":True,"value":null}', b'{"name":nul,"value":null}',
            b'{"name":{"inner":[1,]}}', b'{"name":[{"inner":}]}',
            b'{"name":[{"inner":true}]',
            b'{"name":"x","na\\u006de":{"inner":1},"value":[]}',
            b'{"name":{},"name":[],"value":"z"}',
            b'{"name":null,"na\\u006de":null,"value":false}',
            b'{"name":true,"name":false,"value":null}',
            b'{"name":1,"name":2,"value":null}',
            b'{"name":[],"name":"x","extra":{}}',
            b'{"name=x":{"inner":1},"value":[]}',
            b'{"name":"x"} {}', b'{"name":"x","name":"y","value":"z"}',
            b'{"name=x":"y","value":"z"}', b'name=x\nname=y\nvalue=z',
            b'name=x\nextra=y', b'name', b'name="unclosed', b'name="x" trailing',
            b'name="\\q"', b'name=\xff', b'\xef\xbb\xbfname=x', b'name=x\rvalue=y',
        )
        invalid_extras = (
            (b'{"name":"x","value":"y","extra":{},"extra":[]}', b"Duplicate fields: extra"),
            (b'{"name":"x","value":"y","extra":null,"extra":null}', b"Duplicate fields: extra"),
            (b'{"name":"x","value":"y","extra":true,"extra":false}', b"Duplicate fields: extra"),
            (b'{"name":"x","value":"y","extra":1,"extra":2}', b"Duplicate fields: extra"),
            (b'{"name":"x","value":"y","extra":falsee}', b"invalid file"),
            (b'{"name":"x","value":"y","bad-key":null}', b"Malformed assignments"),
            (b'{"name":"x","value":"y","extra":[1,]}', b"invalid file"),
            (b'{"name":"x","value":"y","bad-key":{}}', b"Malformed assignments"),
            (b'name=x\nvalue=y\nextra=a\nextra=b', b"Duplicate fields: extra"),
            (b'name=x\nvalue=y\nbad-key=z', b"Malformed assignments"),
            (b'name=x\nvalue=y\nextra="unclosed', b"unterminated"),
        )

        def check_failures():
            for content in invalid:
                params.write_bytes(content)
                for prefix in prefixes:
                    failed = cli(*prefix, "--params-file", str(params), code=1)
                    assert b"invalid file" in failed.stderr, failed.stderr
                    if b'na\\u006de' in content or b',"name":' in content:
                        assert b"Duplicate fields: name" in failed.stderr, failed.stderr
                    if b'"extra":{}' in content:
                        for detail in (b"Missing fields: value", b"Unexpected fields: (none)",
                                       b"Duplicate fields: name"):
                            assert detail in failed.stderr, failed.stderr
                    if content == b'name=x\nextra=y':
                        assert b"Missing fields: value\nUnexpected fields: (none)" in failed.stderr, failed.stderr
                    if content == b'{"name":null}':
                        assert b"Missing fields: value\n" in failed.stderr, failed.stderr
            for content, detail in invalid_extras:
                params.write_bytes(content)
                for template in ("fields", "plain"):
                    for prefix in (("template", "render", template),
                                   ("submit", "a1000", "--template", template),
                                   ("reply", "a1000", "--template", template)):
                        failed = cli(*prefix, "--params-file", str(params), code=1)
                        assert b"invalid file" in failed.stderr and detail in failed.stderr, failed.stderr
            for prefix in prefixes:
                failed = cli(*prefix, "--set", "name=x", "--set", "value=y", "--set", "extra=z", code=1)
                assert b"Missing fields: (none)\nUnexpected fields: extra" in failed.stderr, failed.stderr
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

        nested_content = r'''{
  "name": {"items": ["世界", 9007199254740993, -0, 1.2300e+40, true, false, null], "meta": {}},
  "value": [{"escaped": "quote: \" slash: \\ newline: \n unicode: \u4e16", "literal": "{{.name}} <>&"}, [], {"key": 1, "key": 2}]
}'''.encode()
        nested_expected = r'''[{"items":["世界",9007199254740993,-0,1.2300e+40,true,false,null],"meta":{}}]|[[{"escaped":"quote: \" slash: \\ newline: \n unicode: \u4e16","literal":"{{.name}} <>&"},[],{"key":1,"key":2}]]'''.encode()
        mixed_expected = '[Alice\n世界]|[{"deep":[[{"ready":true}]]}]'.encode()
        scalar_cases = (
            ("booleans", b'{"name": true, "value": false}', b'[true]|[false]'),
            ("nulls", b'{"name": null, "value": null}', b'[null]|[null]'),
            ("large-numbers", b'{"name":900719925474099312345678901234567890,"value":-900719925474099312345678901234567890}',
             b'[900719925474099312345678901234567890]|[-900719925474099312345678901234567890]'),
            ("exponents", b'{"name":1.2300e+400,"value":-2.500E-400}', b'[1.2300e+400]|[-2.500E-400]'),
            ("zeroes", b'{"name": -0, "value": 0.000}', b'[-0]|[0.000]'),
        )
        for path, content, rendered in (
            ("nested", nested_content, nested_expected),
            ("empty-collections", b'{"name": {}, "value": []}', b'[{}]|[[]]'),
            ("mixed", '{"name":"Alice\\n世界","value":{"deep": [[{"ready": true}]]}}'.encode(), mixed_expected),
        ) + scalar_cases:
            (project / path).write_bytes(content)
            assert cli("template", "render", "fields", "--params-file", path).stdout == rendered
            assert cli("template", "render", "plain", "--params-file", path).stdout == b"fixed"
        all_content = r'''{"text":"世界\n","number":1.2300e+400,"yes":true,"no":false,"nothing":null,"object":{ "n": -0 },"array":[ null, false ]}'''.encode()
        all_expected = '[世界\n]|1.2300e+400|true|false|null|{"n":-0}|[null,false]'.encode()
        (project / "all").write_bytes(all_content)
        assert cli("template", "render", "all", "--params-file", "all").stdout == all_expected
        assert cli("template", "render", "empty", "--params-file", "nulls").stdout == b"null"
        for path, content in (
            ("shared.json", b'{"name":"Alice","value":"","task":"Review","metadata":{"ready":true},"items":[1,null],"count":900719925474099312345678901234567890,"ready":true,"done":false,"result":null}'),
            ("shared.env", b'name=Alice\nvalue=\ntask=Review\nmetadata=unused\nitems=unused'),
        ):
            (project / path).write_bytes(content)
            for template, rendered in (("fields", b"[Alice]|[]"), ("next", b"Next: Review"), ("plain", b"fixed")):
                assert cli("template", "render", template, "--params-file", path).stdout == rendered
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
            for submit_file, reply_file, submit_template, reply_template, rendered, reply in (
                ("json.env", "dotenv.json", "fields", "fields", expected, expected),
                ("dotenv.json", "json.env", "fields", "fields", expected, expected),
                ("nested", "nested", "fields", "fields", nested_expected, nested_expected),
                ("empty-collections", "empty-collections", "fields", "fields", b'[{}]|[[]]', b'[{}]|[[]]'),
                ("mixed", "mixed", "fields", "fields", mixed_expected, mixed_expected),
                ("all", "all", "all", "all", all_expected, all_expected),
                ("nulls", "nulls", "empty", "empty", b"null", b"null"),
                ("shared.json", "shared.json", "fields", "next", b"[Alice]|[]", b"Next: Review"),
                ("shared.env", "shared.env", "fields", "next", b"[Alice]|[]", b"Next: Review"),
                ("shared.json", "shared.json", "plain", "plain", b"fixed", b"fixed"),
                ("shared.env", "shared.env", "plain", "plain", b"fixed", b"fixed"),
            ) + tuple((path, path, "fields", "fields", rendered, rendered)
                      for path, _, rendered in scalar_cases):
                p = subprocess.Popen([str(binary), "submit", "a1000", "--params-file", submit_file,
                                      "--template", submit_template], cwd=project, env=params_env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    # stdin stays open: template mode must not read it before submitting.
                    ready = json.loads(cli("wait", "a1000", "--timeout", "1").stdout)
                    assert ready["results"] == [{"id": "a1000", "message": rendered.decode()}], ready
                    assert p.poll() is None, "submit did not block for a reply"
                    before = state()
                    check_failures()
                    assert state() == before, "invalid input mutated an outstanding result"
                    assert p.poll() is None, "invalid reply released submit"
                    assert cli("reply", "a1000", "--template", reply_template, "--params-file", reply_file).stdout == b""
                    out, err = p.communicate(timeout=5)
                    assert p.returncode == 0 and out == reply and not err, (p.returncode, out, err)
                finally:
                    if p.poll() is None:
                        p.kill()
                        p.communicate()
        cli("close", "a1000")
    print("PASS: JSON/dotenv parameter files, options, exact round trips, validation before state changes", flush=True)
