#!/usr/bin/env python3
"""Write the shared grading code into every task, and build the files one task derives from another.

    scripts/build_tasks.py                # write
    scripts/build_tasks.py --check        # exit 1 and list the differences if anything is stale
    scripts/build_tasks.py --accept-base  # after porting a solution overlay to a changed seed (below)

A task is a directory under tasks/ with tests/task_config.json (schema: tasks/README.md). For every
task this script:

1. mirrors eval/grading/ into tasks/<task>/tests/: criteria.py, reward.toml, test.sh and the criteria
   groups (correctness/, review/, handoff/, diagnostics/). Harbor copies only tests/ into the
   container at verification time, so each task needs its own copy; this script is the only writer,
   so the copies cannot drift. Task-specific grading settings live in task_config.json, never in
   these files.
2. applies the task's `build` steps from task_config.json, in order:
     {"copy": "<task>/<path>", "to": "<path>", "mode": "mirror" | "overlay", "keep": [...]}
        copy a file tree from another task (mirror: the destination becomes exactly the source, except
        for the files named in `keep`, which belong to this task and stay; overlay: files are added or
        replaced, others are kept)
     {"generate": "<path to a python script in this task>", "args": [...], "to": "<path>"}
        run a generator with the destination directory appended to args (mirror semantics)
   This is how cloudbill-sqlite's seed is cloudbill-report's seed plus its reference solution, how
   its hidden suite reuses cloudbill-report's hidden tests as the oracle (keeping its own
   test_database.py), and how cloudbill-report's sample export is produced from the seeded generator
   that lives in its hidden tests.
3. guards a hand-maintained overlay against a generated seed. When a task's seed is built from
   another task and its reference (`fake_reference`) replaces some of the seed's files, the reference
   was written against those files as they were. `solution/BASE.sha256` records their hashes; the
   check fails when the seed changes under the overlay, until the change is ported into the
   reference and `--accept-base` records the new hashes.

Tasks are processed so that a task is built after the tasks it copies from. --check builds into a
temporary copy of tasks/ and compares it with the real tree, so a hand edit to a generated file, a
stale copy, or a changed generator all fail the check (scripts/test_build_tasks.py runs it).
"""

from __future__ import annotations

import argparse
import filecmp
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
GRADING = EVAL / "grading"
TASKS = EVAL / "tasks"
IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", ".DS_Store")
GRADING_FILES = ("criteria.py", "reward.toml", "test.sh")
GRADING_GROUPS = ("correctness", "review", "handoff", "diagnostics")
BASE_FILE = Path("solution") / "BASE.sha256"


def task_dirs(root: Path) -> list[Path]:
    return sorted(p.parent.parent for p in root.glob("*/tests/task_config.json"))


def config_of(task: Path) -> dict:
    return json.loads((task / "tests" / "task_config.json").read_text(encoding="utf-8"))


def build_order(root: Path) -> list[Path]:
    """Topological order: a task after every task its copy steps read from."""
    tasks = {t.name: t for t in task_dirs(root)}
    deps = {name: {s["copy"].split("/", 1)[0] for s in config_of(t).get("build", []) if "copy" in s} for name, t in tasks.items()}
    order: list[str] = []
    visiting: set[str] = set()

    def visit(name: str) -> None:
        if name in order:
            return
        if name in visiting:
            raise SystemExit(f"build steps form a cycle through {name}")
        if name not in tasks:
            raise SystemExit(f"a build step copies from unknown task {name!r}")
        visiting.add(name)
        for d in sorted(deps[name] - {name}):
            visit(d)
        visiting.discard(name)
        order.append(name)

    for name in sorted(tasks):
        visit(name)
    return [tasks[n] for n in order]


def mirror(src: Path, dst: Path, keep: list[str] | None = None) -> None:
    kept = {k: (dst / k).read_bytes() for k in keep or [] if (dst / k).is_file()}
    if dst.exists():
        shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
    if src.is_dir():
        shutil.copytree(src, dst, ignore=IGNORE)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for k, data in kept.items():
        (dst / k).parent.mkdir(parents=True, exist_ok=True)
        (dst / k).write_bytes(data)


def overlay(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, ignore=IGNORE, dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def build_task(task: Path, root: Path) -> None:
    tests = task / "tests"
    for name in GRADING_FILES:
        mirror(GRADING / name, tests / name)
    (tests / "test.sh").chmod(0o755)
    for group in GRADING_GROUPS:
        mirror(GRADING / group, tests / group)
    for step in config_of(task).get("build", []):
        dst = task / step["to"]
        if "copy" in step:
            src = root / step["copy"]
            if not src.exists():
                raise SystemExit(f"{task.name}: build step source {src} does not exist")
            if step.get("mode") == "overlay":
                overlay(src, dst)
            else:
                mirror(src, dst, step.get("keep"))
        elif "generate" in step:
            script = task / step["generate"]
            if dst.exists():
                shutil.rmtree(dst)
            dst.mkdir(parents=True)
            subprocess.run([sys.executable, "-B", str(script), *step.get("args", []), str(dst)], check=True,
                           cwd=task, capture_output=True, text=True)
        else:
            raise SystemExit(f"{task.name}: unknown build step {step}")


def build(root: Path) -> list[str]:
    built = []
    for task in build_order(root):
        build_task(task, root)
        built.append(task.name)
    return built


def tree_files(root: Path) -> dict[str, Path]:
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_file() and not any(part in ("__pycache__", ".pytest_cache") for part in rel.parts) and p.suffix != ".pyc":
            out[rel.as_posix()] = p
    return out


def differences(real: Path, built: Path) -> list[str]:
    a, b = tree_files(real), tree_files(built)
    diffs = [f"missing (build would create): {k}" for k in sorted(b.keys() - a.keys())]
    diffs += [f"extra (build would remove): {k}" for k in sorted(a.keys() - b.keys())]
    diffs += [f"stale: {k}" for k in sorted(a.keys() & b.keys()) if not filecmp.cmp(a[k], b[k], shallow=False)]
    return diffs


# ---- the overlay base guard ---------------------------------------------------------------------

def overlay_base(task: Path) -> str | None:
    """The expected text of solution/BASE.sha256: a hash per seed file the task's reference replaces.
    None for a task whose seed is not built from another task (nothing can change under the overlay)."""
    cfg = config_of(task)
    derived = any("copy" in s and Path(s["to"]).parts[:2] == ("environment", "seed") for s in cfg.get("build", []))
    reference = task / cfg.get("fake_reference", "solution")
    if not derived or not reference.is_dir():
        return None
    seed = task / "environment" / "seed"
    lines = []
    for p in sorted(reference.rglob("*")):
        rel = p.relative_to(reference)
        if p.is_file() and (seed / rel).is_file() and not {"__pycache__", ".pytest_cache"} & set(rel.parts):
            lines.append(f"{hashlib.sha256((seed / rel).read_bytes()).hexdigest()}  {rel.as_posix()}")
    return (f"# sha256 of each {task.name} seed file its reference overlay replaces (scripts/build_tasks.py --accept-base)\n"
            + "\n".join(lines) + "\n")


def base_problems(root: Path, accept: bool = False) -> list[str]:
    problems = []
    for task in task_dirs(root):
        expected = overlay_base(task)
        base = task / BASE_FILE
        if expected is None:
            continue
        if accept or not base.exists():
            base.parent.mkdir(parents=True, exist_ok=True)
            base.write_text(expected, encoding="utf-8")
        elif base.read_text(encoding="utf-8") != expected:
            problems.append(f"{task.name}: the seed changed under files its reference overlay replaces ({BASE_FILE.as_posix()}); "
                            f"port the change into {task.name}'s reference, then run scripts/build_tasks.py --accept-base")
    return problems


def check() -> list[str]:
    with tempfile.TemporaryDirectory(prefix="build-tasks-") as tmp:
        copy = Path(tmp) / "tasks"
        shutil.copytree(TASKS, copy, ignore=IGNORE)
        build(copy)
        problems = base_problems(copy)
        return differences(TASKS, copy) + problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report stale generated files instead of writing them")
    ap.add_argument("--accept-base", action="store_true", help="record the current seed hashes under each reference overlay")
    args = ap.parse_args()
    if args.check:
        diffs = check()
        for d in diffs:
            print(d)
        print("up to date" if not diffs else f"{len(diffs)} difference(s); run scripts/build_tasks.py")
        return 1 if diffs else 0
    for name in build(TASKS):
        print(f"built tasks/{name}")
    problems = base_problems(TASKS, accept=args.accept_base)
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
