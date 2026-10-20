import json
import signal
import sys
from pathlib import Path

import pytest

# The workspace under test is /app in Harbor; allow override for local runs.
WORKSPACE = Path(__import__("os").environ.get("LEDGER_WORKSPACE", "/app"))
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))


@pytest.fixture(autouse=True)
def _per_test_timeout():
    """A hung implementation must not hang the verifier; 20 s is generous for these CLI calls."""
    if hasattr(signal, "SIGALRM"):
        def _raise(signum, frame):
            raise TimeoutError("hidden test exceeded 20 s")
        old = signal.signal(signal.SIGALRM, _raise)
        signal.alarm(20)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
    else:
        yield


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch) -> Path:
    """cwd is tmp_path; the ledger lives in tmp_path/data so files written "next to the ledger file"
    are distinguishable from files written in the current directory. Returns the data directory."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LEDGER_FILE", str(data / "ledger.csv"))
    return data


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
