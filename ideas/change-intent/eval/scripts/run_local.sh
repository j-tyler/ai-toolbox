#!/usr/bin/env bash
# Run one process version against the ledger task in a plain directory, no Docker, no Harbor,
# then grade it with the same Reward Kit verifier Harbor would run.
#
#   scripts/run_local.sh <process> [--backend copilot|fake] [--model NAME] [--stand-in scripted|model]
#
# Examples
#   scripts/run_local.sh change-intent-v1 --backend fake      # pipeline check, no model, ~5 s
#   COPILOT_GITHUB_TOKEN=... scripts/run_local.sh change-intent-v1 --model gpt-5.4
#   scripts/run_local.sh baseline --model claude-sonnet-4.5
#
# Needs: python3 with pytest, `pip install github-copilot-sdk harbor-rewardkit` (or uvx), git.
# Output: runs/<timestamp>-<process>/{app,reward.json,reward-details.json}
set -euo pipefail
EVAL="$(cd "$(dirname "$0")/.." && pwd)"
TASK="$EVAL/tasks/ledger-budgets"
PROCESS="${1:?usage: run_local.sh <process> [driver args...]}"; shift
BACKEND="copilot"; prev=""
for a in "$@"; do [[ "$prev" == "--backend" ]] && BACKEND="$a"; prev="$a"; done
RUN="$EVAL/runs/$(date -u +%Y%m%dT%H%M%SZ)-$PROCESS"
mkdir -p "$RUN/app"
cp -r "$TASK/environment/seed/." "$RUN/app/"

EXTRA=()
if [[ "$BACKEND" == "fake" ]]; then EXTRA=(--fake-reference "$TASK/solution"); fi
python3 "$EVAL/driver/run_process.py" --workspace "$RUN/app" --process "$EVAL/processes/$PROCESS" \
  --brief "$TASK/instruction.md" --out "$RUN/app/.eval" "${EXTRA[@]}" "$@" | tee "$RUN/driver.log"

echo "--- grading with Reward Kit"
if command -v rewardkit >/dev/null; then RK=(rewardkit); else RK=(uvx --from 'harbor-rewardkit==0.2.*' rewardkit); fi
"${RK[@]}" --workspace "$RUN/app" --output "$RUN/reward.json" "$TASK/tests"
echo "--- $RUN/reward.json"; cat "$RUN/reward.json"
