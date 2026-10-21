"""Which task a Harbor trial is running, so the agent uploads that task's task_config.json.

Harbor hands the agent the task's instruction (instruction.md, plus any extra instructions a job
appends) but not the task directory. The driver needs the task's contract (code directories for the
continuation rule, the visible test command), and a wrong one would silently change the rule for that
arm, so the choice is explicit or provable and never a default:

1. the agent class's ``TASK`` attribute, else
2. ``EVAL_TASK`` in the host environment, else
3. the one task under tasks/ whose instruction.md is contained in the instruction Harbor passed.

An explicit choice must also match the instruction; anything else refuses to start. No Harbor import
here, so scripts/test_build_tasks.py can test it offline.
"""

from __future__ import annotations

from pathlib import Path

TASKS_DIR = Path(__file__).resolve().parents[1] / "tasks"


def known_tasks(tasks_dir: Path = TASKS_DIR) -> list[str]:
    return sorted(p.parent.parent.name for p in tasks_dir.glob("*/tests/task_config.json"))


def _brief_in(instruction: str, task: str, tasks_dir: Path) -> bool:
    brief = (tasks_dir / task / "instruction.md").read_text(encoding="utf-8").strip()
    return bool(brief) and brief in instruction


def resolve_task(instruction: str, explicit: str | None, tasks_dir: Path = TASKS_DIR) -> str:
    tasks = known_tasks(tasks_dir)
    if explicit:
        if explicit not in tasks:
            raise ValueError(f"unknown task {explicit!r}; tasks with a task_config.json: {tasks}")
        if not _brief_in(instruction, explicit, tasks_dir):
            raise ValueError(
                f"the instruction Harbor passed is not tasks/{explicit}/instruction.md; the agent was told to run task "
                f"{explicit!r} (TASK or EVAL_TASK) against a different task. Unset EVAL_TASK or fix the job."
            )
        return explicit
    hits = [t for t in tasks if _brief_in(instruction, t, tasks_dir)]
    if len(hits) != 1:
        raise ValueError(
            f"cannot tell which task this trial runs (instruction matches {hits or 'no'} task brief); "
            f"set EVAL_TASK on the host or TASK on the agent class. Known tasks: {tasks}"
        )
    return hits[0]


def task_config_path(task: str, tasks_dir: Path = TASKS_DIR) -> Path:
    return tasks_dir / task / "tests" / "task_config.json"
