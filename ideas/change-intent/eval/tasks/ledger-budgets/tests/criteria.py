"""Custom Reward Kit criteria for the ledger-budgets task.

Every criterion receives the workspace path (``/app`` in Harbor) and returns a float in [0, 1] or a
bool. Nothing here imports the workspace's code; test runs happen in a subprocess under the
workspace's own interpreter (``LEDGER_PYTHON``, set by tests/test.sh before uvx changes PATH), so a
broken workspace cannot break the verifier and a missing pytest fails loudly instead of scoring 0.

Groups (see the reward.toml files):
  correctness   hidden acceptance tests, regression, constraints      -> headline
  review        the fixed reviewer's structured verdict                -> headline
  handoff       condition-invariant hygiene (committed, summary clean) -> headline
  diagnostics   process-specific artifacts (intent, process review,    -> reported, weight 0
                tests added); meaningful only for processes that promise them
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from functools import lru_cache
from pathlib import Path

from rewardkit import criterion

HIDDEN = Path(__file__).resolve().parent / "__hidden"  # "__" prefix: Reward Kit skips it as a criteria group
SEED_TESTS = ("tests/test_money.py", "tests/test_cli.py")
SEED_TEST_COUNT = 17
PYTEST_TIMEOUT_SEC = 240
_PYTEST_LOCKS: dict = {}


# ---- running pytest ---------------------------------------------------------------------------

def _python() -> str:
    """The workspace's interpreter (has pytest). The verifier itself may run under uvx with its own venv."""
    return os.environ.get("LEDGER_PYTHON") or shutil.which("python3") or sys.executable


@lru_cache(maxsize=None)
def _pytest_cached(args: tuple[str, ...], cwd: str) -> tuple[int, int, str]:
    # Reward Kit runs criteria on threads; the lock makes the hidden suite run once per verification.
    with _PYTEST_LOCKS.setdefault((args, cwd), threading.Lock()):
        return _pytest_run(args, cwd)


def _pytest_run(args: tuple[str, ...], cwd: str) -> tuple[int, int, str]:
    env = dict(os.environ, LEDGER_WORKSPACE=cwd, PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run(
            [_python(), "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header", *args],
            cwd=cwd, env=env, text=True, capture_output=True, timeout=PYTEST_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        return 0, 1, "timeout"
    out = proc.stdout + proc.stderr
    if "No module named pytest" in out:
        raise RuntimeError(f"pytest is not installed for {_python()}; set LEDGER_PYTHON to the workspace interpreter")
    passed = sum(int(n) for n in re.findall(r"(\d+) passed", out))
    failed = sum(int(n) for n in re.findall(r"(\d+) (?:failed|error)", out))
    return passed, passed + failed, out[-2000:]


def _pytest(args: list[str], cwd: Path) -> tuple[int, int, str]:
    """(passed, total, tail). Cached per (args, workspace) so the hidden suite runs once per verification."""
    return _pytest_cached(tuple(args), str(cwd))


# ---- correctness -----------------------------------------------------------------------------

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
    """The seed project's own tests must still pass unmodified."""
    if not all((workspace / t).exists() for t in SEED_TESTS):
        return False
    passed, total, _ = _pytest(list(SEED_TESTS), workspace)
    return total >= SEED_TEST_COUNT and passed == total


@criterion(shared=True)
def agent_tests_pass(workspace: Path) -> bool:
    """Whatever tests the agent left in tests/ pass. A red suite at hand-off is a defect."""
    passed, total, _ = _pytest(["tests"], workspace)
    return total > 0 and passed == total


@criterion(shared=True)
def stdlib_only(workspace: Path) -> bool:
    """No third-party imports anywhere under ledger/ (a stated constraint of the brief)."""
    stdlib = set(sys.stdlib_module_names) | {"ledger"}
    for path in (workspace / "ledger").rglob("*.py"):
        for m in re.finditer(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", path.read_text(encoding="utf-8", errors="replace"), re.M):
            if m.group(1) not in stdlib:
                return False
    return True


# ---- artifacts written by the driver ---------------------------------------------------------

def _json(workspace: Path, name: str) -> dict | None:
    path = workspace / ".eval" / name
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _intent_cfg(workspace: Path) -> dict:
    cfg = (_json(workspace, "process.json") or {}).get("intent") or {}
    cfg.setdefault("dir", "change-intent")
    cfg.setdefault("claim_sections", ["Acceptance criteria", "Invariants"])
    cfg.setdefault("required_sections", ["Outcomes", "Why", "Constraints", "Acceptance criteria", "Invariants", "Out of scope"])
    return cfg


def _intent_files(workspace: Path) -> list[Path]:
    d = workspace / _intent_cfg(workspace)["dir"]
    return sorted(p for p in d.glob("*.md") if p.is_file()) if d.exists() else []


def _git(workspace: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=workspace, text=True, capture_output=True, timeout=30).stdout
    except Exception:
        return ""


# ---- handoff (condition-invariant) ------------------------------------------------------------

@criterion(shared=True)
def implementation_committed(workspace: Path) -> bool:
    """HEAD is the implementation commit the driver recorded and the tree is clean (reviews left no trace)."""
    summary = _json(workspace, "summary.json") or {}
    impl = summary.get("impl_commit")
    if not impl:
        return False
    head = _git(workspace, "rev-parse", "HEAD").strip()
    return head == impl and not _git(workspace, "status", "--porcelain").strip()


HEADLINE_STAGES = ("implement", "fixed_review")  # the stages every condition runs


@criterion(shared=True)
def summary_recorded(workspace: Path) -> bool:
    """The driver wrote .eval/summary.json, no harness error, and the stages every condition runs
    (implement, fixed review) finished without error or timeout. Process-only stages are diagnostics."""
    summary = _json(workspace, "summary.json")
    if not summary or summary.get("harness_error"):
        return False
    stages = summary.get("stages", {})
    return all(
        stages.get(name, {}).get("status") == "ok" and not stages.get(name, {}).get("timed_out")
        for name in HEADLINE_STAGES
    )


@criterion(shared=True)
def process_stages_clean(workspace: Path) -> float:
    """Diagnostic: share of the process's own stages (author, review) that finished ok; 1.0 when it has none."""
    summary = _json(workspace, "summary.json") or {}
    stages = summary.get("stages", {})
    own = [s for name, s in stages.items() if name not in HEADLINE_STAGES]
    if not own:
        return 1.0
    return sum(1 for s in own if s.get("status") == "ok" and not s.get("timed_out")) / len(own)


# ---- review: the fixed reviewer's verdict, turned into numbers (no re-judging here) -----------

REVIEWABILITY_KEYS = ["description_adequacy", "coherence", "verifiability", "size_appropriateness", "clarity"]


def _review(workspace: Path) -> dict | None:
    r = _json(workspace, "review.json")
    if not r:
        return None
    meta = r.get("_meta") or {}
    if isinstance(meta, dict) and meta.get("valid") is False:
        return None
    return r


def _scale_1_to_5(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, (v - 1.0) / 4.0))


@criterion(shared=True)
def fixed_review_present(workspace: Path) -> bool:
    """The fixed reviewer ran and returned JSON that validated against the schema."""
    return _review(workspace) is not None


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
    for f in r.get("findings") or []:
        if not isinstance(f, dict):
            continue
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
    ratings = (r or {}).get("reviewability")
    if not isinstance(ratings, dict):
        return 0.0
    vals = [_scale_1_to_5(ratings.get(k)) for k in REVIEWABILITY_KEYS]
    return sum(vals) / len(vals)


@criterion(shared=True)
def description_adequacy(workspace: Path) -> float:
    """The single rating most tied to what a process leaves behind for a reviewer."""
    r = _review(workspace)
    ratings = (r or {}).get("reviewability")
    return _scale_1_to_5(ratings.get("description_adequacy")) if isinstance(ratings, dict) else 0.0


@criterion(shared=True)
def review_effort_low(workspace: Path) -> float:
    """Inverse of the reviewer's 1..5 effort estimate: 1.0 for a few-minutes review, 0.0 for a long hard one."""
    r = _review(workspace)
    return 1.0 - _scale_1_to_5(r.get("effort_to_review")) if r else 0.0


@criterion(shared=True)
def verified_claims_ratio(workspace: Path) -> float:
    """Share of the claims the reviewer checked that it could verify: 1 - |cannot_verify| / claims_checked.
    A ratio, so a description that claims less does not score higher by claiming less."""
    r = _review(workspace)
    if not r:
        return 0.0
    cannot = r.get("cannot_verify")
    cannot_n = len(cannot) if isinstance(cannot, list) else 0
    try:
        checked = int(r.get("claims_checked", 0))
    except (TypeError, ValueError):
        checked = 0
    if checked <= 0:
        return 0.0 if cannot_n else 0.5  # nothing checked: neither credit nor blame
    return max(0.0, min(1.0, 1.0 - cannot_n / checked))


# ---- diagnostics (process-specific; reported, not in the headline) ---------------------------

@criterion(shared=True)
def intent_file_present(workspace: Path) -> bool:
    """Exactly one intent file under the process's intent dir."""
    return len(_intent_files(workspace)) == 1


@criterion(shared=True)
def intent_has_required_sections(workspace: Path) -> float:
    files = _intent_files(workspace)
    if len(files) != 1:
        return 0.0
    text = files[0].read_text(encoding="utf-8", errors="replace")
    required = _intent_cfg(workspace)["required_sections"]
    found = sum(1 for s in required if re.search(rf"^##\s+{re.escape(s)}\b", text, re.M | re.I))
    return found / len(required) if required else 0.0


@criterion(shared=True)
def author_approved(workspace: Path) -> bool:
    """The author stage ended with an approved intent (frozen counts as approved)."""
    stage = ((_json(workspace, "summary.json") or {}).get("stages") or {}).get("author") or {}
    return stage.get("author_outcome") == "approved"


@criterion(shared=True)
def agent_added_tests(workspace: Path) -> float:
    """Number of new test functions, saturating at 20. Rewards volume; diagnostic only."""
    count = 0
    for path in (workspace / "tests").glob("test_*.py"):
        if path.name in {Path(t).name for t in SEED_TESTS}:
            continue
        count += len(re.findall(r"^\s*def test_", path.read_text(encoding="utf-8", errors="replace"), re.M))
    return min(count, 20) / 20


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
    """Fraction of intent claims (the process's claim sections) that the review table assesses, saturating at 1."""
    files = _intent_files(workspace)
    rows = _process_review_rows(workspace)
    if len(files) != 1 or not rows:
        return 0.0
    text = files[0].read_text(encoding="utf-8", errors="replace")
    claims = 0
    for section in _intent_cfg(workspace)["claim_sections"]:
        m = re.search(rf"^##\s+{re.escape(section)}\s*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S | re.I)
        if m:
            claims += len(re.findall(r"^\s*[-*]\s+", m.group(1), re.M))
    return min(1.0, len(rows) / claims) if claims else 0.0


@criterion(shared=True)
def process_review_determinacy(workspace: Path) -> float:
    """Share of assessed claims the review decided (met or not met) rather than `cannot verify`. Diagnostic:
    a reviewer that never says cannot verify also scores 1.0, so read it next to the fixed reviewer."""
    rows = _process_review_rows(workspace)
    if not rows:
        return 0.0
    undecided = sum(1 for r in rows if re.search(r"cannot verify", r, re.I))
    return 1.0 - undecided / len(rows)
