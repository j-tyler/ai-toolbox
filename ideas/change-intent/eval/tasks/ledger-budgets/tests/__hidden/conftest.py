import json
import sys
from pathlib import Path

import pytest

# The workspace under test is /app in Harbor; allow override for local runs.
WORKSPACE = Path(__import__("os").environ.get("LEDGER_WORKSPACE", "/app"))
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LEDGER_FILE", str(tmp_path / "ledger.csv"))
    return tmp_path


@pytest.fixture
def run(capsys):
    from ledger.cli import main

    def _run(argv):
        code = main(argv)
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return _run


@pytest.fixture
def run_json(run):
    def _run(argv):
        code, out, err = run(argv)
        assert code == 0, err
        return json.loads(out)

    return _run


def add(run, d, amount, category, note=""):
    code, out, err = run(["add", "--date", d, "--amount", amount, "--category", category, "--note", note])
    assert code == 0, err
