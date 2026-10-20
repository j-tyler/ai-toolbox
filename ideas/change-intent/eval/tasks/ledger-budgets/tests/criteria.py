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


# ---- review dimension ------------------------------------------------------------------------
# The fixed reviewer (eval/reviewer/) runs identically for every process version and writes
# .eval/review.json. These criteria turn its structured verdict into scores. They do not re-judge
# the code; they report what the fixed reviewer concluded.

REVIEWABILITY_KEYS = ["description_adequacy", "coherence", "verifiability", "size_appropriateness", "clarity"]


def _review(workspace: Path) -> dict | None:
    path = workspace / ".eval" / "review.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _scale_1_to_5(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, (v - 1.0) / 4.0))


@criterion(shared=True)
def fixed_review_present(workspace: Path) -> bool:
    """The fixed reviewer ran and returned parseable JSON with the required keys."""
    r = _review(workspace)
    return bool(r) and all(k in r for k in ("findings", "overall_correctness", "reviewability", "effort_to_review"))


@criterion(shared=True)
def reviewer_verdict_correct(workspace: Path) -> float:
    """1.0 when the reviewer judged the change correct, 0.5 uncertain, 0.0 incorrect or absent."""
    r = _review(workspace)
    if not r:
        return 0.0
    return {"correct": 1.0, "uncertain": 0.5}.get(str(r.get("overall_correctness")), 0.0)


@criterion(shared=True)
def no_blocking_findings(workspace: Path) -> bool:
    """No severity-3 finding reported at confidence 0.8 or higher."""
    r = _review(workspace)
    if not r:
        return False
    for f in r.get("findings", []) or []:
        try:
            if int(f.get("severity", 0)) >= 3 and float(f.get("confidence", 0)) >= 0.8:
                return False
        except (TypeError, ValueError):
            continue
    return True


@criterion(shared=True)
def reviewability_score(workspace: Path) -> float:
    """Mean of the reviewer's five reviewability ratings, rescaled from 1..5 to 0..1."""
    r = _review(workspace)
    if not r or not isinstance(r.get("reviewability"), dict):
        return 0.0
    ratings = r["reviewability"]
    vals = [_scale_1_to_5(ratings.get(k)) for k in REVIEWABILITY_KEYS]
    return sum(vals) / len(vals)


@criterion(shared=True)
def description_adequacy(workspace: Path) -> float:
    """The single rating most tied to what a process leaves behind for a reviewer."""
    r = _review(workspace)
    if not r or not isinstance(r.get("reviewability"), dict):
        return 0.0
    return _scale_1_to_5(r["reviewability"].get("description_adequacy"))


@criterion(shared=True)
def review_effort_low(workspace: Path) -> float:
    """Inverse of the reviewer's 1..5 effort estimate: 1.0 for a few-minutes review, 0.0 for a long hard one."""
    r = _review(workspace)
    if not r:
        return 0.0
    return 1.0 - _scale_1_to_5(r.get("effort_to_review"))


@criterion(shared=True)
def few_unverifiable_claims(workspace: Path) -> float:
    """1.0 when the reviewer could verify everything the description claimed; drops 0.25 per unverifiable item."""
    r = _review(workspace)
    if not r:
        return 0.0
    n = len(r.get("cannot_verify", []) or [])
    return max(0.0, 1.0 - 0.25 * n)


# ---- process review (change-intent's own review pass; absent for processes without it) --------

def _process_review_rows(workspace: Path) -> list[str]:
    path = workspace / ".eval" / "process_review.md"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("|") and re.search(r"\b(met|not met|cannot verify)\b", line, re.I) and not re.search(r"\|\s*-{3,}", line):
            rows.append(line)
    return rows


@criterion(shared=True)
def process_review_present(workspace: Path) -> bool:
    return (workspace / ".eval" / "process_review.md").exists()


@criterion(shared=True)
def process_review_assessed_claims(workspace: Path) -> float:
    """Fraction of intent claims (acceptance criteria + invariants) that the review table assesses, saturating at 1."""
    path = _intent_file(workspace)
    rows = _process_review_rows(workspace)
    if not path or not rows:
        return 0.0
    text = path.read_text(encoding="utf-8", errors="replace")
    claims = 0
    for section in ("Acceptance criteria", "Invariants"):
        m = re.search(rf"^##\s+{section}\s*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S | re.I)
        if m:
            claims += len(re.findall(r"^\s*[-*]\s+", m.group(1), re.M))
    if claims == 0:
        return 0.0
    return min(1.0, len(rows) / claims)


@criterion(shared=True)
def process_review_determinacy(workspace: Path) -> float:
    """Share of assessed claims the review could decide (met or not met) rather than `cannot verify`."""
    rows = _process_review_rows(workspace)
    if not rows:
        return 0.0
    undecided = sum(1 for r in rows if re.search(r"cannot verify", r, re.I))
    return 1.0 - undecided / len(rows)
