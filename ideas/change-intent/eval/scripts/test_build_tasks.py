"""Offline checks for the per-task contract and the grading code every task shares.

    python -m pytest scripts/test_build_tasks.py -q

- the generated copies (grading code in each task's tests/, cloudbill-sqlite's seed, seed tests and
  oracle tests, cloudbill-report's sample exports) match what scripts/build_tasks.py would write;
- every task_config.json is valid and agrees with the task's files, and the grader and the driver both
  read it (the grader with a stub rewardkit, since Reward Kit lives in its own environment);
- the Harbor agent picks the task from the instruction and refuses a mismatch;
- the driver's continuation rule uses the task's code directories, not a hardwired one.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import re
import shutil
import tomllib
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

EVAL = Path(__file__).resolve().parents[1]
TASKS = EVAL / "tasks"
sys.path.insert(0, str(EVAL / "scripts"))
sys.path.insert(0, str(EVAL / "driver"))
sys.path.insert(0, str(EVAL))

import build_tasks  # noqa: E402
import run_process  # noqa: E402
import backends  # noqa: E402
from agents import task_select  # noqa: E402

TASK_NAMES = [t.name for t in build_tasks.task_dirs(TASKS)]
TYPES = {"extension", "greenfield", "migration"}


def config(task: str) -> dict:
    return json.loads((TASKS / task / "tests" / "task_config.json").read_text(encoding="utf-8"))


def test_the_three_tasks_are_present():
    assert {"ledger-budgets", "cloudbill-report", "cloudbill-sqlite"} <= set(TASK_NAMES)
    assert {config(t)["type"] for t in TASK_NAMES} == TYPES


def test_generated_files_are_up_to_date():
    diffs = build_tasks.check()
    assert diffs == [], "run scripts/build_tasks.py:\n" + "\n".join(diffs[:40])


@pytest.mark.parametrize("task", TASK_NAMES)
def test_task_config_agrees_with_the_task_files(task):
    cfg = config(task)
    root = TASKS / task
    assert cfg["name"] == task and cfg["type"] in TYPES and cfg.get("language") == "python"
    assert cfg["visible_test_command"][1:3] == ["-m", "pytest"]
    assert cfg["code_dirs"] and all("/" not in d.strip("/") for d in cfg["code_dirs"])
    for f in ("instruction.md", "task.toml", "environment/Dockerfile", "environment/.dockerignore", "solution/solve.sh",
              "tests/test.sh", "tests/criteria.py", "tests/__hidden/conftest.py"):
        assert (root / f).is_file(), f
    assert (root / cfg["fake_reference"]).is_dir()
    seed = root / "environment" / "seed"
    if cfg["type"] == "greenfield":
        assert cfg["seed_tests"] == [] and not cfg["seed_test_count"]
        assert not any(seed.rglob("test_*.py")) and not any(seed.rglob("*.py")), "a greenfield seed holds no code"
        assert not (root / "tests" / "__seed").exists()
    else:
        assert cfg["seed_tests"] and cfg["seed_test_count"] > 0
        for t in cfg["seed_tests"]:
            assert (seed / t).is_file(), t
            assert (root / "tests" / "__seed" / Path(t).name).read_bytes() == (seed / t).read_bytes(), f"tests/__seed/{Path(t).name} drifted"
        for d in cfg["code_dirs"]:
            assert (seed / d).is_dir(), d


@pytest.mark.parametrize("task", [t for t in TASK_NAMES if config(t)["seed_tests"]])
def test_seed_test_count_is_what_pytest_collects(task, tmp_path):
    seed = tmp_path / "seed"  # a copy: collecting imports the seed's modules, which must not leave caches in the task
    shutil.copytree(TASKS / task / "environment" / "seed", seed)
    out = subprocess.run([sys.executable, "-B", "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *config(task)["seed_tests"]],
                         cwd=seed, capture_output=True, text=True, timeout=120)
    collected = [l for l in out.stdout.splitlines() if "::" in l]
    assert len(collected) == config(task)["seed_test_count"], out.stdout[-1000:]


def test_no_caches_in_any_seed():
    """A local test run in a seed directory leaves caches the image or run_local.sh could ship to the model."""
    stray = [str(p.relative_to(TASKS)) for p in TASKS.glob("*/environment/seed/**/*") if p.name in (".pytest_cache", "__pycache__")]
    assert stray == [], f"delete these: {stray}"
    for task in TASK_NAMES:
        ignore = (TASKS / task / "environment" / ".dockerignore").read_text()
        assert "**/.pytest_cache" in ignore and "**/__pycache__" in ignore


def _stub_rewardkit(monkeypatch) -> list[tuple[str, float]]:
    """A stand-in for rewardkit: `criterion` returns a factory that records registrations."""
    calls: list[tuple[str, float]] = []

    def criterion(shared=False):
        def wrap(fn):
            def factory(weight=1.0):
                calls.append((fn.__name__, weight))
            factory.__wrapped__ = fn
            return factory
        return wrap

    module = types.ModuleType("rewardkit")
    module.criterion = criterion
    module.criteria = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "rewardkit", module)
    return calls


def _import(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("task", TASK_NAMES)
def test_the_grader_reads_the_task_config(task, monkeypatch):
    calls = _stub_rewardkit(monkeypatch)
    crit = _import(TASKS / task / "tests" / "criteria.py", f"criteria_{task.replace('-', '_')}")
    cfg = config(task)
    assert crit.TASK["name"] == task
    assert list(crit.SEED_TESTS) == cfg["seed_tests"] and crit.SEED_TEST_COUNT == (cfg["seed_test_count"] or 0)
    assert list(crit.CODE_DIRS) == cfg["code_dirs"] and crit.VISIBLE_TEST_ARGS == cfg["visible_test_command"][3:]
    # Wire the stub's criteria namespace to the module's factories, then load the regression group as Reward Kit would.
    import rewardkit

    for name in dir(crit):
        obj = getattr(crit, name)
        if callable(obj) and hasattr(obj, "__wrapped__"):
            setattr(rewardkit.criteria, name, obj)
    _import(TASKS / task / "tests" / "correctness" / "regression.py", f"regression_{task.replace('-', '_')}")
    registered = [n for n, _ in calls]
    assert ("existing_tests_still_pass" in registered) == bool(cfg["seed_tests"]), "greenfield: absent, others: present"
    assert {"agent_tests_pass", "stdlib_only"} <= set(registered)


def test_stdlib_only_checks_the_task_code_dirs(tmp_path, monkeypatch):
    _stub_rewardkit(monkeypatch)
    crit = _import(TASKS / "cloudbill-report" / "tests" / "criteria.py", "criteria_report_stdlib")
    stdlib_only = crit.stdlib_only.__wrapped__
    (tmp_path / "cloudbill").mkdir()
    (tmp_path / "cloudbill" / "a.py").write_text("import csv\nfrom cloudbill import export\nfrom . import b\n")
    assert stdlib_only(tmp_path) is True
    (tmp_path / "cloudbill" / "b.py").write_text('"""import requests"""\nimport sqlite3\n')
    assert stdlib_only(tmp_path) is True
    (tmp_path / "cloudbill" / "c.py").write_text("import requests\n")
    assert stdlib_only(tmp_path) is False
    (tmp_path / "cloudbill" / "c.py").unlink()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("import hypothesis\n")  # outside the code dirs
    assert stdlib_only(tmp_path) is True


def test_a_missing_task_config_fails_loudly(tmp_path, monkeypatch):
    _stub_rewardkit(monkeypatch)
    shutil.copy(TASKS / "ledger-budgets" / "tests" / "criteria.py", tmp_path / "criteria.py")
    with pytest.raises(RuntimeError, match="task configuration"):
        _import(tmp_path / "criteria.py", "criteria_without_config")


# ---- task selection in the Harbor agent ---------------------------------------------------------

def test_the_agent_finds_the_task_from_its_instruction():
    for task in TASK_NAMES:
        brief = (TASKS / task / "instruction.md").read_text(encoding="utf-8")
        assert task_select.resolve_task(brief, None) == task
        assert task_select.resolve_task(brief + "\n\nExtra instruction appended by a job.", None) == task
        assert task_select.resolve_task(brief, task) == task
        assert task_select.task_config_path(task).is_file()


def test_the_agent_refuses_a_task_that_does_not_match_the_instruction():
    ledger = (TASKS / "ledger-budgets" / "instruction.md").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="different task"):
        task_select.resolve_task(ledger, "cloudbill-report")
    with pytest.raises(ValueError, match="unknown task"):
        task_select.resolve_task(ledger, "no-such-task")
    with pytest.raises(ValueError, match="cannot tell"):
        task_select.resolve_task("an instruction from no task", None)


# ---- the driver's use of the config -----------------------------------------------------------

def test_driver_loads_the_config_and_falls_back_to_the_ledger_defaults(tmp_path):
    cfg, source = run_process.load_task_config(TASKS / "cloudbill-report" / "tests" / "task_config.json")
    assert cfg["name"] == "cloudbill-report" and source.endswith("task_config.json")
    assert run_process.code_prefixes(cfg) == ("cloudbill/",)
    argv = run_process.visible_test_argv(cfg)
    assert argv[0] == sys.executable and argv[1:3] == ["-m", "pytest"] and argv[-1] == "tests" and "no:cacheprovider" in argv
    if not run_process.DEFAULT_TASK_CONFIG_PATH.exists():
        cfg, source = run_process.load_task_config(None)
        assert cfg["code_dirs"] == ["ledger"] and source == "builtin-ledger-defaults"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"name": "x"}))
    with pytest.raises(SystemExit):
        run_process.load_task_config(bad)


def test_continuation_rule_uses_the_task_code_dirs(tmp_path):
    """On cloudbill-report a change outside cloudbill/ is not progress: the implementer is nudged until the
    package exists and the visible suite is green. The manifest records the task."""
    task = TASKS / "cloudbill-report"

    class TestsFirst(backends.FakeBackend):
        async def run_stage(self, spec, workspace, *, on_user_input, next_turn):
            if spec.name != "implement":
                return await super().run_stage(spec, workspace, on_user_input=on_user_input, next_turn=next_turn)
            res = backends.StageResult(stage="implement", final_message="", turns=0)
            (workspace / "notes.md").write_text("plan\n")
            res.turns += 1; res.messages.append("Wrote a plan.")
            assert await next_turn(res.messages[-1]) is not None
            shutil.copytree(self.reference_dir, workspace, dirs_exist_ok=True)
            res.turns += 1; res.messages.append("Implemented.")
            assert await next_turn(res.messages[-1]) is None
            res.final_message = res.messages[-1]
            return res

    ws = tmp_path / "app"
    shutil.copytree(task / "environment" / "seed", ws)
    out = tmp_path / "out"
    args = SimpleNamespace(
        workspace=str(ws), process=str(EVAL / "processes" / "baseline"), brief=str(task / "instruction.md"), out=str(out),
        work_dir=str(tmp_path / "work"), model=None, reviewer_model=None, stand_in_model=None, allow_same_reviewer=True,
        provider_json=None, backend="fake", fake_reference=str(task / "solution" / "repo"), stand_in="scripted",
        intent_file=None, skip_reviews=True, max_author_turns=12, max_implement_nudges=2, max_review_attempts=1,
        stage_timeout=60.0, cap_author=600, cap_implement=600, cap_review=300, cap_fixed_review=300, deadline_epoch=None,
        fail_on_error=False, label=None, task_config=str(task / "tests" / "task_config.json"),
    )
    summary: dict = {"process": "baseline", "stages": {}}
    orig = run_process.FakeBackend
    run_process.FakeBackend = TestsFirst  # type: ignore[assignment]
    try:
        asyncio.run(run_process.run(args, summary))
    finally:
        run_process.FakeBackend = orig  # type: ignore[assignment]
    assert [d["end_reason"] for d in summary["stages"]["implement"]["turns_detail"]] == ["no_code_change", "complete"]
    assert summary["task"] == "cloudbill-report"
    assert summary["manifest"]["task"]["name"] == "cloudbill-report" and summary["manifest"]["task"]["code_dirs"] == ["cloudbill"]


# ---- grafts: the config next to the driver or in the environment, a greenfield suite, seeds, the overlay guard

def test_driver_finds_the_config_next_to_it_or_in_the_environment(monkeypatch, tmp_path):
    cfg_path = TASKS / "cloudbill-report" / "tests" / "task_config.json"
    monkeypatch.setattr(run_process, "DEFAULT_TASK_CONFIG_PATH", tmp_path / "absent.json")
    assert run_process.load_task_config(None)[1] == "builtin-ledger-defaults"
    shutil.copy(cfg_path, tmp_path / "task_config.json")
    monkeypatch.setattr(run_process, "DEFAULT_TASK_CONFIG_PATH", tmp_path / "task_config.json")
    cfg, source = run_process.load_task_config(None)
    assert cfg["name"] == "cloudbill-report" and source == str(tmp_path / "task_config.json")
    # --task-config defaults to $EVAL_TASK_CONFIG (argparse default), so the Harbor agent and run_local.sh can set either
    assert 'default=os.environ.get("EVAL_TASK_CONFIG")' in (EVAL / "driver" / "run_process.py").read_text(encoding="utf-8")


def test_visible_suite_is_red_until_a_greenfield_repo_has_passing_tests(tmp_path):
    """pytest exit 5 (no tests collected) is not green: a greenfield implementer is nudged until it adds tests."""
    cfg = config("cloudbill-report")
    ws = tmp_path / "ws"
    shutil.copytree(TASKS / "cloudbill-report" / "environment" / "seed", ws)
    assert run_process.visible_suite_green(ws, cfg) is False
    shutil.copytree(TASKS / "cloudbill-report" / "solution" / "repo", ws, dirs_exist_ok=True)
    assert run_process.visible_suite_green(ws, cfg) is True


@pytest.mark.parametrize("task", TASK_NAMES)
def test_seeds_never_name_the_experiment(task):
    """The agent reads the seed; nothing in it may mention the harness, the experiment or the hidden tests."""
    seed = TASKS / task / "environment" / "seed"
    words = ("change-intent", "change intent", "hidden test", "build_tasks", "eval harness", "experiment", "reference solution")
    for p in seed.rglob("*"):
        if p.is_file() and p.suffix in (".py", ".md", ".toml", ".txt", ".cfg", ".sql"):
            text = p.read_text(encoding="utf-8").lower()
            assert not [w for w in words if w in text], f"{task}: {p.relative_to(seed)}"


def test_mirror_keeps_the_files_a_task_owns(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir(); dst.mkdir()
    (src / "shared.py").write_text("new\n")
    (dst / "shared.py").write_text("old\n"); (dst / "stale.py").write_text("gone\n"); (dst / "own.py").write_text("mine\n")
    build_tasks.mirror(src, dst, keep=["own.py"])
    assert sorted(p.name for p in dst.iterdir()) == ["own.py", "shared.py"]
    assert (dst / "shared.py").read_text() == "new\n" and (dst / "own.py").read_text() == "mine\n"


def test_the_overlay_base_guard_catches_a_seed_that_changed_under_a_reference(tmp_path):
    """cloudbill-sqlite's reference replaces files of a seed that is generated from cloudbill-report; if that
    seed changes under them the check fails until the reference is ported and --accept-base is run."""
    copy = tmp_path / "tasks"
    shutil.copytree(TASKS, copy, ignore=build_tasks.IGNORE)
    assert build_tasks.base_problems(copy) == []
    assert build_tasks.overlay_base(copy / "ledger-budgets") is None  # a hand-maintained seed has no guard
    base = copy / "cloudbill-sqlite" / build_tasks.BASE_FILE
    assert base.is_file() and "cloudbill/cli.py" in base.read_text()
    cli = copy / "cloudbill-report" / "solution" / "repo" / "cloudbill" / "cli.py"
    cli.write_text(cli.read_text() + "\n# a change to the report task's reference\n")
    build_tasks.build(copy)
    problems = build_tasks.base_problems(copy)
    assert len(problems) == 1 and "cloudbill-sqlite" in problems[0] and "--accept-base" in problems[0]
    assert build_tasks.base_problems(copy, accept=True) == [] and build_tasks.base_problems(copy) == []


@pytest.mark.parametrize("task", TASK_NAMES)
def test_the_time_boxes_nest(task):
    """One run of the tool inside a hidden suite ends well before the suite's budget, and the suite's
    budget, spent at most once by the hidden suite and once by the visible one, fits inside Harbor's
    verifier timeout. Otherwise a slow workspace loses the whole grade (the grader returns 0 of 1 on a
    suite timeout) instead of the one test that was slow."""
    cfg = config(task)
    budget = cfg["hidden_timeout_sec"]
    harbor = tomllib.loads((TASKS / task / "task.toml").read_text(encoding="utf-8"))
    assert harbor["verifier"]["timeout_sec"] >= 2 * budget, "task.toml verifier timeout must cover two suites"
    conftest = (TASKS / task / "tests" / "__hidden" / "conftest.py").read_text(encoding="utf-8")
    caps = {m.group(1): int(m.group(2)) for m in re.finditer(r"^(\w*TIMEOUT\w*) = (\d+)\s*$", conftest, re.M)}
    for name, cap in caps.items():
        assert 3 * cap <= budget, f"{name} = {cap}: three such runs must fit in hidden_timeout_sec = {budget}"
