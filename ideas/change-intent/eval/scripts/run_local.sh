#!/usr/bin/env bash
# Run one process version against one task in a plain directory, no Docker, no Harbor, then grade it
# with the same Reward Kit verifier Harbor would run.
#
#   scripts/run_local.sh [<task>] <process> [driver args...]
#
# <task> is a directory under tasks/ (ledger-budgets, cloudbill-report, cloudbill-sqlite). It may be
# omitted, in which case EVAL_TASK or, failing that, ledger-budgets is used, so the older two-argument
# form keeps working.
#
# Examples
#   scripts/run_local.sh change-intent-v1 --backend fake                      # ledger-budgets, no model
#   scripts/run_local.sh cloudbill-report baseline --backend fake
#   scripts/run_local.sh cloudbill-sqlite change-intent-v1 --backend fake
#   COPILOT_GITHUB_TOKEN=... scripts/run_local.sh ledger-budgets change-intent-v1 --model <model> --reviewer-model <other model>
#   scripts/run_local.sh change-intent-v1-frozen --intent-file my-intent.md --model <model> --reviewer-model <other model>
#
# Needs: python3 with pytest, `pip install -r requirements.txt` (or uvx), git.
#
# What is and is not isolated. The workspace and a private copy of the harness (driver/, reviewer/,
# the chosen process directory, the task's task_config.json, the brief and any --intent-file) are
# created OUTSIDE the repository under mktemp and the copy is what runs, so no repository path reaches
# a model session and the process-directory rename during review touches only the copy. A real model
# session is still NOT sandboxed: its tools can read anything this user can read, including this
# repository's hidden tests and reference solution, if the model goes looking. Local real-model runs
# are for debugging a process; headline numbers come from Harbor runs, where the container holds
# nothing but the seed.
#
# Results are copied to runs/<timestamp>-<task>-<process>/{app,reward.json,reward-details.json,driver.log}.
# Grading always runs, even when the driver reports a stage error.
set -euo pipefail
EVAL="$(cd "$(dirname "$0")/.." && pwd)"
USAGE="usage: run_local.sh [<task>] <process> [driver args...]"
FIRST="${1:?$USAGE}"
if [[ -f "$EVAL/tasks/$FIRST/tests/task_config.json" ]]; then
  TASK_NAME="$FIRST"; shift
else
  TASK_NAME="${EVAL_TASK:-ledger-budgets}"
fi
TASK="$EVAL/tasks/$TASK_NAME"
TASK_CONFIG="$TASK/tests/task_config.json"
[[ -f "$TASK_CONFIG" ]] || { echo "no such task (missing $TASK_CONFIG)" >&2; exit 2; }
PROCESS="${1:?$USAGE}"; shift
[[ -d "$EVAL/processes/$PROCESS" ]] || { echo "no such process: $EVAL/processes/$PROCESS" >&2; exit 2; }

# Pull --backend and --intent-file out of the driver args; everything else passes through untouched.
BACKEND="copilot"; INTENT_FILE=""; prev=""
for a in "$@"; do
  [[ "$prev" == "--backend" ]] && BACKEND="$a"
  [[ "$prev" == "--intent-file" ]] && INTENT_FILE="$a"
  prev="$a"
done

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN="$EVAL/runs/$STAMP-$TASK_NAME-$PROCESS"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/eval-$PROCESS-XXXXXX")"
mkdir -p "$RUN" "$WORK/app" "$WORK/eval/processes"
# The seed, without caches a developer's local test run may have left in it (the image build excludes them too).
tar -C "$TASK/environment/seed" --exclude=.pytest_cache --exclude=__pycache__ --exclude='*.pyc' -cf - . | tar -C "$WORK/app" -xf -

# Private copy of the harness: the driver records the harness commit from the real checkout through
# EVAL_HARNESS_SHA/EVAL_HARNESS_DIRTY because the copy has no git history of its own. The task config
# goes next to driver/, where Harbor uploads it too, never into the workspace.
cp -r "$EVAL/driver" "$EVAL/reviewer" "$WORK/eval/"
cp -r "$EVAL/processes/$PROCESS" "$WORK/eval/processes/$PROCESS"
cp "$TASK_CONFIG" "$WORK/eval/task_config.json"
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
  # The fake implementer copies the task's reference files (task_config.json `fake_reference`, relative to
  # the task directory); only this mode is handed a repository path.
  FAKE_REF="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("fake_reference") or "solution")' "$TASK_CONFIG")"
  ARGS+=(--fake-reference "$TASK/$FAKE_REF")
fi

status=0
python3 "$WORK/eval/driver/run_process.py" --workspace "$WORK/app" --process "$WORK/eval/processes/$PROCESS" \
  --task-config "$WORK/eval/task_config.json" \
  --brief "$WORK/brief.md" --out "$WORK/app/.eval" --work-dir "$WORK/artifacts" \
  ${ARGS[@]+"${ARGS[@]}"} 2>&1 | tee "$RUN/driver.log" || status=$?
[[ $status -ne 0 ]] && echo "driver exited $status (see $RUN/driver.log); grading anyway"

echo "--- grading with Reward Kit"
export EVAL_PYTHON="$(command -v python3)"
export LEDGER_PYTHON="$EVAL_PYTHON"  # the older name, kept working
if command -v rewardkit >/dev/null; then RK=(rewardkit); else RK=(uvx --from 'harbor-rewardkit==0.2.3' rewardkit); fi
"${RK[@]}" --workspace "$WORK/app" --output "$RUN/reward.json" "$TASK/tests" || echo "rewardkit failed"

cp -r "$WORK/app" "$RUN/app"
rm -rf "$WORK"
echo "--- $RUN/reward.json"; cat "$RUN/reward.json" 2>/dev/null || true
