#!/bin/bash
# Harbor runs this after the agent finishes, with this directory copied to /tests and the workspace
# at /app. Reward Kit discovers every criterion under /tests and writes /logs/verifier/reward.json
# and reward-details.json.
#
# uvx puts its own virtualenv first on PATH, and that interpreter has no pytest. Resolve the
# workspace image's python3 BEFORE uvx runs and hand it to the criteria explicitly.
set -u
export LEDGER_WORKSPACE=/app
export LEDGER_PYTHON="$(command -v python3)"
uvx --from 'harbor-rewardkit==0.2.*' rewardkit /tests
