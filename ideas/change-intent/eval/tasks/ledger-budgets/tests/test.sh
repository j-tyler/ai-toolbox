#!/bin/bash
# Harbor runs this after the agent finishes, with this directory copied to /tests and the
# workspace at /app. Reward Kit discovers every criterion under /tests and writes
# /logs/verifier/reward.json and reward-details.json.
set -u
export LEDGER_WORKSPACE=/app
uvx --from 'harbor-rewardkit==0.2.*' rewardkit /tests
