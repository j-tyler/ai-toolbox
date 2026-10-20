#!/usr/bin/env bash
# Run one process version against the ledger task in a plain directory, no Docker, no Harbor,
# then grade it with the same Reward Kit verifier Harbor would run.
#
#   scripts/run_local.sh <process> [driver args...]
#
# Examples
#   scripts/run_local.sh change-intent-v1 --backend fake                    # pipeline check, no model
#   scripts/run_local.sh baseline --backend fake
#   COPILOT_GITHUB_TOKEN=... scripts/run_local.sh change-intent-v1 --model gpt-5.4 --reviewer-model claude-sonnet-4.5
#   scripts/run_local.sh change-intent-v1-frozen --intent-file my-intent.md --model gpt-5.4 --reviewer-model ...
#
# Needs: python3 with pytest, `pip install -r requirements.txt` (or uvx), git.
# The workspace is created OUTSIDE the repository (mktemp), so a real run cannot read the hidden
# tests or the reference solution through relative paths. Results are copied to
# runs/<timestamp>-<process>/{app,reward.json,reward-details.json,driver.log}. Grading always runs,
# even when the driver reports a stage error.
set -euo pipefail
EVAL="$(cd "$(dirname "$0")/.." && pwd)"
TASK="$EVAL/tasks/ledger-budgets"
PROCESS="${1:?usage: run_local.sh <process> [driver args...]}"; shift

BACKEND="copilot"; prev=""
for a in "$@"; do [[ "$prev" == "--backend" ]] && BACKEND="$a"; prev="$a"; done

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN="$EVAL/runs/$STAMP-$PROCESS"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/eval-$PROCESS-XXXXXX")"
mkdir -p "$RUN" "$WORK/app"
cp -r "$TASK/environment/seed/." "$WORK/app/"

EXTRA=()
if [[ "$BACKEND" == "fake" ]]; then EXTRA=(--fake-reference "$TASK/solution"); fi
status=0
python3 "$EVAL/driver/run_process.py" --workspace "$WORK/app" --process "$EVAL/processes/$PROCESS" \
  --brief "$TASK/instruction.md" --out "$WORK/app/.eval" --work-dir "$WORK/artifacts" \
  ${EXTRA[@]+"${EXTRA[@]}"} "$@" 2>&1 | tee "$RUN/driver.log" || status=$?
[[ $status -ne 0 ]] && echo "driver exited $status (see $RUN/driver.log); grading anyway"

echo "--- grading with Reward Kit"
export LEDGER_PYTHON="$(command -v python3)"
if command -v rewardkit >/dev/null; then RK=(rewardkit); else RK=(uvx --from 'harbor-rewardkit==0.2.*' rewardkit); fi
"${RK[@]}" --workspace "$WORK/app" --output "$RUN/reward.json" "$TASK/tests" || echo "rewardkit failed"

cp -r "$WORK/app" "$RUN/app"
rm -rf "$WORK"
echo "--- $RUN/reward.json"; cat "$RUN/reward.json" 2>/dev/null || true
