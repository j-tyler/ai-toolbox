"""Existing behaviour, the agent's own suite, and the stdlib constraint.

The seed-regression criterion is registered only when the task's seed has tests of its own
(task_config.json `seed_tests`); a greenfield task has none, so the criterion is absent rather than
trivially satisfied and the group is the agent's suite plus the stdlib constraint.
"""
import json
from pathlib import Path

from rewardkit import criteria

_CFG = json.loads((Path(__file__).resolve().parent.parent / "task_config.json").read_text(encoding="utf-8"))

if _CFG.get("seed_tests"):
    criteria.existing_tests_still_pass(weight=2.0)
criteria.agent_tests_pass(weight=1.0)
criteria.stdlib_only(weight=1.0)
