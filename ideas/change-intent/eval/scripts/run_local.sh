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
#
# What is and is not isolated. The workspace and a private copy of the harness (driver/, reviewer/,
# the chosen process directory, the brief and any --intent-file) are created OUTSIDE the repository
# under mktemp and the copy is what runs, so no repository path reaches a model session and the
# process-directory rename during review touches only the copy. A real model session is still NOT
# sandboxed: its tools can read anything this user can read, including this repository's hidden
# tests and reference solution, if the model goes looking. Local real-model runs are for debugging a
# process; headline numbers come from Harbor runs, where the container holds nothing but the seed.
#
# Results are copied to runs/<timestamp>-<process>/{app,reward.json,reward-details.json,driver.log}.
# Grading always runs, even when the driver reports a stage error.
set -euo pipefail
EVAL="$(cd "$(dirname "$0")/.." && pwd)"
TASK="$EVAL/tasks/ledger-budgets"
PROCESS="${1:?usage: run_local.sh <process> [driver args...]}"; shift
[[ -d "$EVAL/processes/$PROCESS" ]] || { echo "no such process: $EVAL/processes/$PROCESS" >&2; exit 2; }

# Pull --backend and --intent-file out of the driver args; everything else passes through untouched.
BACKEND="copilot"; INTENT_FILE=""; prev=""
for a in "$@"; do
  [[ "$prev" == "--backend" ]] && BACKEND="$a"
  [[ "$prev" == "--intent-file" ]] && INTENT_FILE="$a"
  prev="$a"
done

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN="$EVAL/runs/$STAMP-$PROCESS"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/eval-$PROCESS-XXXXXX")"
mkdir -p "$RUN" "$WORK/app" "$WORK/eval/processes"
cp -r "$TASK/environment/seed/." "$WORK/app/"

# Private copy of the harness: the driver records the harness commit from the real checkout through
# EVAL_HARNESS_SHA/EVAL_HARNESS_DIRTY because the copy has no git history of its own.
cp -r "$EVAL/driver" "$EVAL/reviewer" "$WORK/eval/"
cp -r "$EVAL/processes/$PROCESS" "$WORK/eval/processes/$PROCESS"
find "$WORK/eval" -name __pycache__ -type d -prune -exec rm -rf {} +
cp "$TASK/instruction.md" "$WORK/brief.md"
export EVAL_HARNESS_SHA="$(git -C "$EVAL" rev-parse HEAD 2>/dev/null || echo unknown)"
if [[ -n "$(git -C "$EVAL" status --porcelain -- . 2>/dev/null)" ]]; then export EVAL_HARNESS_DIRTY=1; else export EVAL_HARNESS_DIRTY=0; fi

ARGS=()
if [[ -n "$INTENT_FILE" ]]; then
  cp "$INTENT_FILE" "$WORK/intent.md"
  prev=""
  for a in "$@"; do
    if [[ "$prev" == "--intent-file" ]]; then ARGS+=("$WORK/intent.md"); else ARGS+=("$a"); fi
    prev="$a"
  done
else
  ARGS=("$@")
fi
if [[ "$BACKEND" == "fake" ]]; then
  # The fake implementer copies the reference solution; only this mode is handed a repository path.
  ARGS+=(--fake-reference "$TASK/solution")
fi

status=0
python3 "$WORK/eval/driver/run_process.py" --workspace "$WORK/app" --process "$WORK/eval/processes/$PROCESS" \
  --brief "$WORK/brief.md" --out "$WORK/app/.eval" --work-dir "$WORK/artifacts" \
  ${ARGS[@]+"${ARGS[@]}"} 2>&1 | tee "$RUN/driver.log" || status=$?
[[ $status -ne 0 ]] && echo "driver exited $status (see $RUN/driver.log); grading anyway"

echo "--- grading with Reward Kit"
export LEDGER_PYTHON="$(command -v python3)"
if command -v rewardkit >/dev/null; then RK=(rewardkit); else RK=(uvx --from 'harbor-rewardkit==0.2.3' rewardkit); fi
"${RK[@]}" --workspace "$WORK/app" --output "$RUN/reward.json" "$TASK/tests" || echo "rewardkit failed"

cp -r "$WORK/app" "$RUN/app"
rm -rf "$WORK"
echo "--- $RUN/reward.json"; cat "$RUN/reward.json" 2>/dev/null || true
