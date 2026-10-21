#!/bin/bash
# Harbor runs this after the agent finishes, with this directory copied to /tests and the workspace
# at /app. Reward Kit discovers every criterion under /tests and writes /logs/verifier/reward.json
# and reward-details.json. Generated from eval/grading/test.sh by scripts/build_tasks.py; identical
# for every task (task-specific settings live in task_config.json next to this file).
#
# uvx puts its own virtualenv first on PATH, and that interpreter has no pytest. Resolve the
# workspace image's python3 BEFORE uvx runs and hand it to the criteria explicitly. EVAL_* are the
# task-neutral names; the LEDGER_* names are kept for older hidden suites and scripts.
set -u
export EVAL_WORKSPACE=/app
export EVAL_PYTHON="$(command -v python3)"
export LEDGER_WORKSPACE="$EVAL_WORKSPACE"
export LEDGER_PYTHON="$EVAL_PYTHON"
uvx --from 'harbor-rewardkit==0.2.3' rewardkit /tests
