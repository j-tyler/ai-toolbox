"""Custom Reward Kit criteria for the ledger-budgets task.

Every criterion receives the workspace path (``/app`` in Harbor) and returns a float in [0, 1]
or a bool. They must not import the workspace's code into this process; everything runs in a
subprocess so a broken workspace cannot break the verifier.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from rewardkit import criterion

HIDDEN = Path(__file__).resolve().parent / "__hidden"  # "__" prefix: Reward Kit skips it as a criteria group
STDLIB_ALLOWLIST_EXTRA = {"ledger", "tests", "conftest", "pytest"}


def _python() -> str:
    """The workspace's interpreter, which has pytest; the verifier may run under uvx with its own venv."""
    return os.environ.get("LEDGER_PYTHON") or shutil.which("python3") or sys.executable


def _pytest(args: list[str], cwd: Path, env_extra: dict[str, str] | None = None) -> tuple[int, int, str]:
    """Run pytest and return (passed, total, tail_of_output) using the summary line."""
    env = dict(os.environ)
    env["LEDGER_WORKSPACE"] = str(cwd)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [_python(), "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header", *args],
        cwd=cwd, env=env, text=True, capture_output=True, timeout=600,
    )
    out = proc.stdout + proc.stderr
    passed = sum(int(n) for n in re.findall(r"(\d+) passed", out))
    failed = sum(int(n) for n in re.findall(r"(\d+) (?:failed|error)", out))
    return passed, passed + failed, out[-2000:]


@criterion(shared=True)
def hidden_tests_pass_fraction(workspace: Path) -> float:
    """Fraction of the hidden acceptance tests that pass. These tests are never visible to the agent."""
    passed, total, _ = _pytest([str(HIDDEN)], workspace)
    return 0.0 if total == 0 else passed / total


@criterion(shared=True)
def hidden_tests_all_pass(workspace: Path) -> bool:
    passed, total, _ = _pytest([str(HIDDEN)], workspace)
    return total > 0 and passed == total


@criterion(shared=True)
def existing_tests_still_pass(workspace: Path) -> bool:
    """The seed project's own tests (tests/test_money.py, tests/test_cli.py) must still pass unmodified."""
    seed_tests = ["tests/test_money.py", "tests/test_cli.py"]
    if not all((workspace / t).exists() for t in seed_tests):
        return False
    passed, total, _ = _pytest(seed_tests, workspace)
    return total >= 17 and passed == total


@criterion(shared=True)
def agent_tests_pass(workspace: Path) -> bool:
    """Whatever tests the agent left in tests/ pass. A red suite at hand-off is a process failure."""
    passed, total, _ = _pytest(["tests"], workspace)
    return total > 0 and passed == total


@criterion(shared=True)
def agent_added_tests(workspace: Path) -> float:
    """The brief asks for tests. Score the number of new test functions, saturating at 20."""
    count = 0
    for path in (workspace / "tests").glob("test_*.py"):
        if path.name in {"test_money.py", "test_cli.py"}:
            continue
        count += len(re.findall(r"^def test_", path.read_text(encoding="utf-8", errors="replace"), re.M))
    return min(count, 20) / 20


@criterion(shared=True)
def stdlib_only(workspace: Path) -> bool:
    """No third-party imports anywhere under ledger/ (a stated constraint of the brief)."""
    stdlib = set(sys.stdlib_module_names) | STDLIB_ALLOWLIST_EXTRA
    for path in (workspace / "ledger").rglob("*.py"):
        for m in re.finditer(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", path.read_text(encoding="utf-8", errors="replace"), re.M):
            if m.group(1) not in stdlib:
                return False
    return True


def _intent_file(workspace: Path) -> Path | None:
    files = sorted(p for p in (workspace / "change-intent").glob("*.md")) if (workspace / "change-intent").exists() else []
    return files[-1] if files else None


@criterion(shared=True)
def intent_file_present(workspace: Path) -> bool:
    """A process that promises an intent must leave exactly one under change-intent/. Baseline scores 0 here by design."""
    files = sorted(p for p in (workspace / "change-intent").glob("*.md")) if (workspace / "change-intent").exists() else []
    return len(files) == 1


@criterion(shared=True)
def intent_has_required_sections(workspace: Path) -> float:
    """Structural check from design.md: the six sections an intent must carry (Amendments is optional)."""
    path = _intent_file(workspace)
    if not path:
        return 0.0
    text = path.read_text(encoding="utf-8", errors="replace")
    required = ["Outcomes", "Why", "Constraints", "Acceptance criteria", "Invariants", "Out of scope"]
    found = sum(1 for s in required if re.search(rf"^##\s+{re.escape(s)}\b", text, re.M | re.I))
    return found / len(required)


@criterion(shared=True)
def implementation_committed(workspace: Path) -> bool:
    """The driver commits each stage; a clean tree with an implementation commit means hand-off was orderly."""
    try:
        log = subprocess.run(["git", "log", "--format=%s"], cwd=workspace, text=True, capture_output=True, timeout=30).stdout
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=workspace, text=True, capture_output=True, timeout=30).stdout
    except Exception:
        return False
    return "eval: implementation" in log and not dirty.strip()


@criterion(shared=True)
def summary_recorded(workspace: Path) -> bool:
    """The driver wrote .eval/summary.json without a stage error."""
    path = workspace / ".eval" / "summary.json"
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return all(not s.get("error") for s in data.get("stages", {}).values())
