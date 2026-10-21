# Change-intent process eval (prototype)

An evaluation harness for comparing **code-generation processes**, not models. Every condition
uses the same model, the same tools, the same workspace, and the same brief. What varies is the
process the agent follows: no intent at all, change intent as drafted in
[`../mechanics`](../mechanics/README.md), or any variant you add. The output is graded by
third-party, inspectable tooling so the comparison is defensible to people who did not build it.

Status: **prototype, reviewed**. The pipeline runs end to end offline (fake backend) through all
four stages. A two-reviewer, one-adjudicator pass over the code found and fixed a set of defects
and confounds (see "What the review changed"). Real Copilot runs and Harbor container runs are
wired up but were not executed in the authoring environment, which has no Copilot-entitled token
and no Docker daemon.

## Diagrams

- [One run, stage by stage](docs/01-run-pipeline.svg): what each stage may read and write, the sealed artifact directory, and the verifier.
- [What you can vary](docs/02-process-options.svg): every input a stage receives, by process version, and which row to vary for which question.
- [Start, loop, stop, hand off](docs/03-author-handoff.svg): how the driver decides the authoring dialogue is over and hands the committed intent to implementation.

## Pieces

| Piece | Where | Third party? |
| --- | --- | --- |
| Outer harness: containers, repeated trials, logs, viewer | [Harbor](https://github.com/harbor-framework/harbor), Apache-2.0 | yes |
| Grader: multi-dimension verifier with audit details | [Reward Kit](https://docs.harborframework.com/rewardkit/quick-start), part of Harbor | yes |
| Agent runtime | [GitHub Copilot SDK](https://github.com/github/copilot-sdk), MIT, Python | yes |
| The exercises: seed project, brief, hidden tests, reference solution, one `task_config.json` each | `tasks/` (see [`tasks/README.md`](tasks/README.md)) | ours |
| Grading code shared by every task, copied into each task's `tests/` by `scripts/build_tasks.py` | `grading/` | ours |
| Process versions, generated from `../mechanics`; schema in `processes/README.md` | `processes/` | ours |
| Driver: author → implement → review → fixed review, with a stand-in author | `driver/` | ours |
| Fixed reviewer instructions, assembled from published sources | `reviewer/` | ours, cited |
| Harbor agent classes, one per condition (the task is found from the instruction) | `agents/copilot_process.py` | ours |

Everything "ours" is small and meant to be read. The claim to neutrality rests on the hidden
tests being objective, the grader being someone else's, and the process files being the only
thing that differs between conditions.

## The tasks

Three Python tasks of three types, all pure standard library ([`tasks/README.md`](tasks/README.md)
has the detail, the config schema, and how to add one):

| Task | Type | In one line | Hidden tests: seed / reference |
| --- | --- | --- | --- |
| `ledger-budgets` | extension | add budgets, recurring transactions, import and a report to a 300-line CLI, under a precise interface contract | 5 / 37 of 37 |
| `cloudbill-report` | greenfield | build a streaming cost-review CLI over a messy cloud billing export from a lighter ticket that leaves encodings, duplicates, rounding and the percentile method open, under a 100 MB memory cap | 0 / 55 of 55 |
| `cloudbill-sqlite` | migration | move that tool onto SQLite with idempotent loads, restatements across loads, provenance and byte-identical answers; the seed is the report task's reference | 2 / 75 of 75 |

`ledger` is a 300-line stdlib Python CLI that records and lists transactions. Its brief
([`tasks/ledger-budgets/instruction.md`](tasks/ledger-budgets/instruction.md)) asks for budgets,
recurring transactions, bank-CSV import with de-duplication, and a monthly report, with an
interface contract precise enough to test and open enough to leave real decisions. The reference
solution is about 500 lines of implementation. Its hidden tests keep the ledger in a `data/`
subdirectory with a different working directory, so "files next to the ledger file" is checked,
not assumed, and the seed's own 17 tests still pass on the reference.

The two `cloudbill` tasks are black box: the hidden tests run `python -m cloudbill` in a
subprocess against exports a seeded generator writes, and check standard output, exit codes and
files, plus properties (determinism, every view adding up, rejected counts consistent) and the
child's peak memory on a 1,500,000-row export under the brief's 100 MB cap. The migration task's
hidden suite is the report task's suite asked of a database loaded from the same files, plus
database tests. Each task's specifics (code directories, visible test command, seed tests, fake
reference) live in its `tests/task_config.json`, which the driver and the grader both read, so the
rest of the harness is the same for every task.

## How a run works

1. Harbor builds the task image (seed repo, Python, pytest, uv, a git identity) and installs the
   Copilot CLI and pinned SDK in it, then uploads `driver/`, `reviewer/`, the chosen
   `processes/<name>/`, and the task's `task_config.json` (next to the driver, never in the
   workspace). The agent finds the task from the instruction Harbor passes it (or `EVAL_TASK`, or
   a `TASK` class attribute) and refuses to start on a mismatch.
2. `driver/run_process.py` turns the workspace into a git repo, installs the process files
   (appends the agents-file block to `AGENTS.md`, creates the intent directory), and commits a
   baseline. Every artifact it produces lives **outside the workspace** until the end, so no stage
   can read another stage's output unless the harness hands it over.
3. **Author stage**, by `author.mode`. `skill`: one SDK session with the process's authoring skill
   loaded; its questions reach a **stand-in author** (`driver/stand_in.py`) through the SDK's
   `on_user_input_request` handler for `ask_user` calls and through scripted replies for prose
   questions. The stand-in judges each turn on what a human would have read: the whole turn's
   assistant text (not only the last message), or the `ask_user` question plus the text before it.
   It approves only when that text presents the artifact (most of its required section headings at
   any level, or a large share of its lines); it re-approves a re-shown file, nudges an approved
   but unwritten or uncommitted file at most twice, then lets the stage end. The dialogue ends when
   a commit made during the stage touches the intent directory, whatever the agent asks next; an
   existing but uncommitted draft gets one request to show it for approval. The stage records
   `author_outcome` (approved, unapproved_file, no_file), `end_reason` (committed,
   stand_in_stopped, turn_cap, deadline, error, agent_stopped) and which cue produced the approval,
   and restores and flags anything the author changed outside the intent directory, committed or
   not. `frozen`: a supplied file is committed with no dialogue, which
   removes authoring variance. `none`: no artifact. Harness commit messages are condition-neutral.
   `driver/test_author_stage.py` pins these rules.
4. **Implement stage**: a fresh session. The prompt is the same neutral text for every condition
   ("implement the change described in the {noun} at {path}", or "in the brief below"), with the
   brief attached when `implement.include_brief` is true. The noun comes from `intent.noun` in
   `process.json`, so a spec or a plan is named as such. Continuation is one objective rule for every
   condition: the driver nudges while the visible test suite (the task's `visible_test_command`) is
   red or nothing under the task's `code_dirs` changed, at most twice, and records why each turn ended. Every turn's summary is kept. Everything process-specific
   arrives through `implement.system_append` and the agents-file block, never through the harness
   prompt. The result is committed as `eval: implementation` (an empty marker commit if the agent
   already committed), and that commit is recorded.
5. The driver writes `diff.patch` and `change_description.md`, which holds whatever the process
   produced to describe the change: the approved intent plus the implementer's summary for
   change-intent processes, the summary alone for the baseline.
6. **Review stage** (processes with a `review` section): the process's review guidance is
   appended to a read-only session that assesses the diff against the intent and returns a met /
   not met / cannot verify table per claim as its final message; the driver saves it.
7. **Fixed review** (every condition): a second read-only session (the bundled runtime's own
   read-only tool set, built-in sub-agents off, session store and memory off) runs
   [`reviewer/fixed_reviewer.md`](reviewer/fixed_reviewer.md) with workspace custom instructions
   **off**, in a **synthetic review repository**: a fresh git repo with two neutral commits, `base`
   (the seed tree) and `change` (the implementation tree minus the intent directory, with
   `AGENTS.md` as it was at the seed). It holds no `.eval`, no harness commit messages and no
   process files, so nothing in the checkout says which arm produced it. The reviewer also gets
   exactly three inputs in a sealed temporary directory: `requirements.md` (the brief, the standard
   for correctness in every condition), `diff.patch` (code only), and `change_description.md`
   (rated for adequacy, never the standard). What remains condition-dependent is the content of
   that description, which is the thing under test.
   A non-JSON answer gets one follow-up and then fresh sessions; a review that is still missing is
   recorded as missing, not scored, and the analyzer reports the headline both ways.
   It returns JSON against `REVIEW_SCHEMA` (findings with location, severity, and confidence; an
   overall verdict; five reviewability ratings; effort to review; how many claims it checked and
   which it could not verify). The driver validates the JSON and keeps the raw message. The
   reviewer model must differ from the implementer's (`--reviewer-model`, or `EVAL_REVIEWER_MODEL`
   under Harbor); the driver refuses a same-model reviewer unless `--allow-same-reviewer`. After
   each review the tree is reset to the implementation commit and anything that moved is recorded.
8. The driver writes `.eval/` (summary, dialogue log, SDK events and transcripts per stage,
   `review.json`, `process_review.md`), and Harbor runs `tests/test.sh`, which is Reward Kit.

### Grading dimensions

```
reward            weighted mean: correctness 4, review 2, handoff 1   (diagnostics weight 0)
  correctness     acceptance (hidden tests pass fraction 3, all-pass 1) 3 : regression (seed tests 2, agent's suite 1, stdlib-only 1) 1
  review          fixed_reviewer (present 1, verdict correct 2, no blocking findings 2) 1
                  : reviewability (mean of five ratings 3, description adequacy 1, low effort 1, verified-claims ratio 1) 1
  handoff         implementation committed and tree clean 1, no stage errors or timeouts 1
  diagnostics     intent (present, sections, author approved), process_review (present, claims
                  assessed, determinacy), tests_added   -- reported, never in the headline
```

The headline uses only criteria every condition can satisfy identically. `review` is the fixed
reviewer's structured verdict turned into numbers; the criteria do not re-judge the code.
Process-specific artifacts are diagnostics with weight zero, so a process that produces no intent
is not penalised for honesty and a process that produces change-intent-shaped files gains
nothing for the shape alone. `reward-details.json` lists every criterion's value.

The correctness group is the same file in every task, but `correctness/regression.py` registers
the seed-regression criterion only when `task_config.json` lists seed tests, so on the greenfield
task it is absent (regression is the agent's own suite and the stdlib constraint) rather than a
free 1.0.

Offline check, fake backend, same grader, same fake output for every condition: on ledger-budgets,
baseline, change-intent-v1 and change-intent-v1-frozen all score 0.961 on the headline (diagnostics
0.263, 0.749, 0.749); on cloudbill-report and cloudbill-sqlite, baseline and change-intent-v1 both
score 0.961 with correctness 1.0 (diagnostics 0.500 and 0.986; 0.362 and 0.849). That parity is
the property that makes a real difference
attributable to the process. In real runs the review dimension is where conditions are expected
to separate: the fixed reviewer rates description adequacy and verifiability from the artifacts
each process leaves behind, and `verified_claims_ratio` is a ratio so a description that claims
less cannot win by claiming less.

## Running

### Offline pipeline check (no model, no Docker; ledger ~5 s, cloudbill-report about 1.5 min, cloudbill-sqlite about 3 min)

```bash
cd ideas/change-intent/eval
pip install -r requirements.txt            # or use uv
scripts/run_local.sh change-intent-v1 --backend fake                       # the task defaults to ledger-budgets
scripts/run_local.sh ledger-budgets baseline --backend fake
scripts/run_local.sh cloudbill-report baseline --backend fake
scripts/run_local.sh cloudbill-sqlite change-intent-v1 --backend fake
scripts/analyze.py runs/                                                   # conditions are keyed by task
python -m pytest driver/test_author_stage.py scripts/test_analyze.py scripts/test_build_tasks.py -q
```

`scripts/build_tasks.py` regenerates the grading code in every task and the files one task derives
from another; run it after editing `grading/` or the report task's reference or hidden tests
(`scripts/test_build_tasks.py` fails when anything is stale).

### Real run without Harbor (needs a Copilot-entitled token)

```bash
export COPILOT_GITHUB_TOKEN=...            # a token for a user with Copilot access
scripts/run_local.sh ledger-budgets change-intent-v1 --model <model> --reviewer-model <model from another vendor>
scripts/run_local.sh ledger-budgets baseline         --model <model> --reviewer-model <model from another vendor>
scripts/run_local.sh change-intent-v1-frozen --intent-file path/to/intent.md --model <model> --reviewer-model <model from another vendor>
scripts/analyze.py runs/ --ref baseline
```

The workspace and a private copy of the harness are created outside the repository, so no
repository path reaches a model session. A local real-model session is still not sandboxed: its
tools can read anything your user can read, including this repository's hidden tests, if the model
goes looking. Use local real runs to debug a process; headline numbers come from Harbor runs only.

BYOK instead of Copilot entitlement: pass `--provider-json '{"type":"anthropic","base_url":"...","api_key":"..."}'`
(the SDK's `ProviderConfig`). Note that without BYOK each SDK prompt counts against the Copilot
premium-request quota.

### Harbor runs (needs Docker)

```bash
cd ideas/change-intent/eval
uv tool install harbor                      # or pip install harbor
export COPILOT_GITHUB_TOKEN=... EVAL_REVIEWER_MODEL=<model from another vendor>
PYTHONPATH=. harbor run -p tasks/cloudbill-report -a oracle -k 1                                  # task sanity check: correctness 1.0
PYTHONPATH=. harbor run -p tasks/ledger-budgets -a agents.copilot_process:ChangeIntentV1 -m <model> -k 3
PYTHONPATH=. harbor run -p tasks/ledger-budgets -a agents.copilot_process:Baseline        -m <model> -k 3
EVAL_INTENT_FILE=path/to/intent.md EVAL_LABELS=intent=A \
PYTHONPATH=. harbor run -p tasks/ledger-budgets -a agents.copilot_process:ChangeIntentV1Frozen -m <model> -k 3
harbor view jobs
scripts/analyze.py ~/jobs/<job> --ref baseline
```

The same agent classes serve every task: each trial's task is found from its instruction and that
task's `task_config.json` is uploaded with the driver. A frozen intent is task-specific, so run the
frozen arm one task at a time.

The stage caps sum to 9000 s (author 1800, implement 3600, process review 900, three fixed-review
attempts of 900). The driver is given a 9600 s deadline and the task's agent timeout is 10500 s, so
the deadline is not binding before the caps in any arm and the driver always finishes, resets, and
copies its artifacts inside the window. A `deadline_clamped` flag per fixed-review attempt records
the exception.

**Run every arm in one job.** Harbor nests agents innermost in its plan, so a job config that lists
every arm interleaves their trials; separate `harbor run`s per arm would confound the arm with
whatever the model service was doing that hour:

```yaml
# job.yaml
agents:
  - import_path: agents.copilot_process:Baseline
    model_name: <model>
  - import_path: agents.copilot_process:ChangeIntentV1
    model_name: <model>
datasets:
  - path: tasks/ledger-budgets
  - path: tasks/cloudbill-report
  - path: tasks/cloudbill-sqlite
n_attempts: 20
```

`analyze.py` keys every condition by task and compares each arm with the reference arm of the
same task only.

```bash
PYTHONPATH=. harbor run -c job.yaml
```

**Run order.** A baseline pilot at about five attempts comes first. If its mean correctness is at
least 0.95, or at least nine in ten trials pass every hidden test, the task cannot discriminate on
the primary endpoint: stop and add a task, or a lighter-brief variant, before spending on the full
run. `analyze.py` prints the smallest p-value the arm sizes can attain and the minimum detectable
effect next to every difference.

`PYTHONPATH=.` is required: Harbor imports `module:Class` with importlib and does not add the
current directory to `sys.path`.

`-k` is attempts per task; three is the floor for seeing past run-to-run variance on a change
this size. Harbor keeps every trial's trajectory, the verifier output, and the `.eval/` artifacts
(copied to the agent logs). Sanity-check the task itself with the oracle: `-a oracle` overlays
the reference solution and should score 1.0 on correctness.

## Adding a process version

See [`processes/README.md`](processes/README.md) for the `process.json` schema and a table of
which field to vary for which question (whole process, intent artifact, guidance, authoring
skill, intent alone). `change-intent-v1` and `change-intent-v1-frozen` are generated from
`../mechanics` by `scripts/build_processes.py`; re-run it after editing the mechanics. To try a
variant, copy a generated directory to a new name, edit the copy, add a two-line subclass in
`agents/copilot_process.py`, and run it with `-a`.

## Decisions worth knowing

- **The intent is referenced by path, not pasted.** The implementing session gets the committed
  file path plus the brief as context. That matches how the process would run for real and keeps
  the intent in the diff where the verifier can read it.
- **The stand-in is part of the harness.** It must not vary between conditions. A passive author
  cannot catch a bad proposal; state that in any write-up. An opinionated-author variant is a
  separate experiment, not a tweak.
- **Hidden tests live under `tests/__hidden/`.** Reward Kit imports every `.py` under a criteria
  directory, and skips directories whose names start with `__` or `.`.
- **One contract per task, one copy of the grader.** Everything task-specific is in
  `tests/task_config.json`, read by the driver (uploaded next to it, never into the workspace) and
  by the grader. The grading code exists once, in `grading/`, and `scripts/build_tasks.py` mirrors
  it into each task's `tests/` (Harbor copies only `tests/`); `--check` fails on drift. A task
  derived from another (the migration task's seed and oracle tests) is built the same way, never
  copied by hand. The driver falls back to the ledger task's settings when it finds no config and
  records `builtin-ledger-defaults` in the manifest.
- **Harbor copies `tests/` into the container only at verification time**, so the agent never
  sees the hidden tests or the criteria.
- **Verifier interpreter.** Reward Kit runs under `uvx` with its own virtualenv; the criteria run
  pytest with the workspace image's `python3`, which has pytest installed.
- **Two reviews, two owners.** The process review belongs to the process version and varies with
  it; the fixed reviewer belongs to the harness and never varies. Only the fixed reviewer's output
  feeds the `review` dimension. Its instructions quote published sources (Google's review guide,
  the published Anthropic reviewer threshold, OpenAI's review schema shape, the TU Delft
  reviewability factors) so nobody in the experiment wrote the reviewer for their own process.
- **The fixed reviewer sees the description, not the condition.** "Reviewable with the artifact
  the process actually leaves behind" is the claim under test, so `change_description.md` carries
  the intent plus the implementer's summaries under a neutral heading. Correctness is judged
  against `requirements.md` (the brief, identical in every arm), never against the description;
  the description is rated for adequacy separately, and `verified_claims_ratio` is a ratio so a
  description that claims less cannot win by claiming less. The repository the reviewer reads is
  a neutral two-commit copy with no process files. Content-level unblinding is inherent: a
  reviewer that reads a change-intent-shaped description knows it is reading one. State it.
- **Primary endpoint: correctness.** The composite reward is secondary; review and handoff are
  exploratory. One pre-registered comparison is confirmatory; everything else is a look.
- **Reviewers are read-only by construction and by cleanup.** Edit tools are excluded from review
  sessions, and the driver resets the tree to the implementation commit afterwards and records
  anything that moved.
- **Structured output.** The fixed reviewer returns JSON through the SDK's `response_schema`; the
  driver validates it, tolerates a fenced block or surrounding prose, and keeps the raw message.
- **Every run is pinned and manifested.** `summary.json` carries the harness git SHA, SDK
  version, the hash of every process file, the brief, the reviewer instructions, the schema, and
  each rendered prompt, plus the resolved model per stage when the SDK reports it, the session
  isolation flags, and the provider route per role (type and host, never a key). `analyze.py`
  refuses to pool trials whose process files, harness commit, stand-in or dirty flag differ.
- **Sessions are isolated and keys stay off the command line.** Every session runs with the
  runtime's session store, memory, embedding retrieval and file hooks off, under a fresh
  `COPILOT_HOME`; the Copilot backend refuses to run without a token in the environment rather
  than reading a developer's `~/.copilot`. BYOK provider JSON travels only in environment
  variables, one per role (`EVAL_PROVIDER_JSON`, `EVAL_REVIEWER_PROVIDER_JSON`,
  `EVAL_STAND_IN_PROVIDER_JSON`); a BYOK implementer with no explicit reviewer route is refused,
  so the reviewer cannot silently share the implementer's vendor.
- **Time caps are per stage and identical across conditions.** The implement cap does not shrink
  because authoring took long; `task.toml`'s agent timeout covers the sum.

## What the review changed

A workflow of two independent model reviewers (defects; swappability of intent and guidance) and
one adjudicator reviewed the harness. The adjudicator verified each finding against the code or by
running it. Changes made as a result, in its priority order:

1. The uvx-run verifier graded with an interpreter that had no pytest, so every Harbor trial would
   have scored near zero on correctness. `test.sh` now resolves the workspace python first; a
   missing pytest fails loudly; pytest runs are cached, time-boxed, and the hidden tests carry a
   per-test alarm; malformed reviewer output scores zero instead of crashing the verifier.
2. The headline reward now contains only condition-invariant criteria; process-specific artifacts
   moved to a weight-zero diagnostics group. Before, the process term alone explained the entire
   offline gap between conditions.
3. Stage inputs are sealed: artifacts live outside the workspace during the run, the fixed reviewer
   gets custom instructions off and only two files in a sealed directory, the process review
   returns text instead of writing into the workspace, and the change description has a neutral
   heading.
4. `process.json` grew into a real schema (author mode, implement, review, intent sections) so
   intent construction and implementation guidance can be varied independently; the harness
   prompts are neutral; a frozen-intent mode isolates the intent artifact.
5. The stand-in stops once the intent is committed, asks once for an unapproved file, records the
   author outcome, and reverts and flags files the author touched outside the intent directory.
6. Real-path robustness: `get_events()` is awaited (it was not, so real runs would have lost every
   transcript and token count); events are also captured live; sessions are aborted on error or
   timeout; per-stage wall-clock caps; `summary.json` is always written; the Harbor command copies
   artifacts even when the driver fails; the tree is reset to the recorded implementation commit.
7. A git identity everywhere, an always-present implementation marker commit, and commit detection
   that survives an implementer committing its own work.
8. `analyze.py` groups by the process recorded in `summary.json`, reports bootstrap intervals and
   differences against a reference, cost per stage, and author outcomes.
9. Hidden tests distinguish "next to the ledger file" from "in the working directory"; the brief
   states JSON ordering and id numbering.
10. `PYTHONPATH=.` documented for Harbor; SDK and Reward Kit pinned; run manifest; same-model
    reviewer refused by default.
11. `run_local.sh` builds the workspace outside the repository and always grades.

Deferred, from the same review: the full intent-isolation protocol (author N times, freeze, implement
M times each), hidden author preferences for the stand-in so authoring can gain as well as lose, a
direct intent grader and test-strength (mutant) measures, a blinded diff-only reviewer arm, more
tasks and attempts, a separately pinned model for the model stand-in, and digest-pinned images.

## Second review pass

The same two-frame, one-adjudicator workflow was run again on the hardened harness (saved as
`docs/adjudication-2026-10-20-pass2.json`). It found six of the first pass's eleven changes landed
cleanly, four with residuals, and one regressed: the author stop rule counted the setup commit's
placeholder as "intent committed", so the dialogue ended as soon as any draft file existed and
committed contamination was never checked. Changes made from the second pass:

1. Author stage: committed means a commit made during the stage touched the intent directory;
   contamination is checked in committed changes as well as uncommitted ones and restored to the
   pre-stage state; `agent_committed` is measured before the harness's marker commit; the stand-in
   no longer treats "final" as an approval cue and records which cue fired; an offline test file
   pins all of this.
2. Fixed reviewer inputs are sealed in a temporary directory outside the work directory, the
   rendered-prompt hash no longer contains a random path, and harness commit messages no longer
   name the condition.
3. Time budget: the task timeout has margin over the stage caps and the Harbor agent passes an
   absolute deadline; the handoff criterion counts only the stages every condition runs, with the
   process's own stages reported as a diagnostic; one JSON-only retry when the reviewer answers in
   prose; the read-only tool set is the one the bundled runtime's explore agent declares.
4. `analyze.py` counts reward-less trials in both layouts, prints intention-to-treat and
   per-protocol rows, and per-stage cost; it has a self-test.
5. The harness prompts are shape-neutral: `intent.noun` in `process.json` names the artifact.
6. Reward Kit pinned to an exact version and warmed into the image; the Harbor agent forwards the
   harness git SHA; the manifest hashes every driver and reviewer file and records the CLI version,
   the tool list, the frozen intent's source, and free-form `--label key=value` tags.

Still deferred, from both passes: the full intent-isolation protocol, hidden author preferences,
direct intent and test-strength graders, a blinded reviewer arm, multi-file artifacts, per-stage
agents blocks, structural (not keyword) approval detection, and verdict calibration against the
hidden tests.

## Third review pass

A third pass, two fresh model reviewers with no knowledge of the earlier reviews and two new frames
(a realistic agent trying to break the harness; a methodologist vetting the measurement), plus an
adjudicator, is saved as `docs/adjudication-2026-10-20-pass3.json`. Both reviewers rated the
harness not yet sound for the inference; the adjudicator reproduced the mechanical claims and
ordered eight changes, all applied:

1. The frozen arm, launched as its own docstring said, never received its intent and graded the
   untouched seed as that arm's result. The Harbor agent now resolves the file from the host at run
   time and refuses to start without it; the frozen artifact gets a convention-shaped name; a
   provisional `summary.json` is written at start; the analyzer excludes invalid trials (harness
   error, driver never finished, no model calls) and counts them per condition.
2. The fixed reviewer judged each arm against that arm's own description. It now gets the brief as
   `requirements.md` in every condition and judges correctness against it; the description is rated
   separately; the diff it sees is code only; `AGENTS.md` and the process directory are hidden
   during the review; out-of-bounds reads are recorded.
3. The stand-in's default reply carried a scope directive the brief contradicts, and its approval
   was keyword-based in both directions. It now defers to the brief, approves only when the agent
   presents the artifact (structural match on its headings or lines), nudges once to commit after
   approval, and the model stand-in decides approval with a separate yes/no call. Two files in the
   intent directory resolve to the committed one and are labelled `multiple_files`.
4. A nudge used to replace the implementer's summary, and a mid-task stop without a question was
   accepted. Every turn's summary is kept, and continuation is one objective rule (visible suite
   green and code changed). Stashes are detected and recorded.
5. A missing or invalid fixed review used to score as the worst possible review. It is now retried
   in fresh sessions, then recorded as missing; handoff no longer depends on it; the analyzer
   reports the headline with and without missing reviews; `scripts/rerun_fixed_review.py` gives
   judge test-retest.
6. Built-in sub-agents pinned to other models (explore, research, task, and the rest) are excluded
   from every session; usage is recorded per model; `--model` is required; mismatches are flagged.
7. The analyzer groups by process, labels, and frozen-intent hash, decomposes the headline into
   individual criteria so a review win and a code win can be told apart, and reports differences
   with a permutation p-value and a Welch interval, warning below ten trials per arm (the
   adjudicator's simulation put the false-positive rate of the old bootstrap at about one in five
   at three attempts).
8. The artifact is re-resolved after implementation in case the implementer moved it; the hidden
   suite runs exactly once per verification; skipped and expected-failure tests do not count as
   passing.

Stated limitations the adjudicator asked for in any write-up: the brief's interface contract is
nearly complete, so this task cannot show an authoring benefit, only an implementation and
reviewability one; the baseline has no guidance-matched control; the primary endpoint should be
`hidden_tests_pass_fraction` with the composite secondary; and three attempts per arm is a pilot,
not a comparison.

## Fourth review pass

The fourth pass used four fresh model reviewers, each with one lens and no knowledge of the earlier
passes (realistic agent behaviour against the harness; the exercise and grader; the SDK, Harbor
and Reward Kit integration contract; measurement validity), plus an adjudicator who reproduced the
claims before ruling. It is saved as `docs/adjudication-2026-10-20-pass4.json`. Verdict: sound
with fixes, do not start a real comparison before they land. Nine changes were upheld and applied;
a longer list of proposed changes was rejected with reasons (kept: abort after timeout, all
built-in sub-agents excluded, cross-vendor reviewer, exit 0 on stage errors, weight-0
diagnostics, the all-pass bonus, the 4:2:1 weights, the diff excluding the intent directory,
correctness judged against the brief, the scripted stand-in as default, exact permutation for
small pools).

1. **The author stage could loop to its turn cap and run the change-intent arm with no intent.**
   Three realistic skill behaviours did it: re-showing the file after approval, showing the
   proposal and then calling `ask_user`, and a proposal that mentions "intent brief". The
   stand-in now reads the whole turn (the SDK's `send_and_wait` returns only the last root
   message, so the backend joins every root assistant message from live events) and the `ask_user`
   context; headings at any level and bold labels count as sections; a re-shown file is
   re-approved; an approved but unwritten file gets at most two nudges, then the stage ends with
   `end_reason=stand_in_stopped`. Tests pin each of these.
2. **The continuation rule counted the CLI's own `./ledger.csv` as a code change** (`ledger.csv`
   starts with `ledger`), which could swing correctness by about 0.7 in one arm. Prefix matching
   is now on `ledger/`. The non-author stand-in reply is identical in every arm, including the
   model stand-in's.
3. **Grader defects that landed unevenly.** Pytest outcomes were counted with a regex over the
   whole output, so a failing assertion that printed "1 skipped" scored 1/12 instead of 1/2; counts
   now come from JUnit XML. Suites run in a throwaway copy of the workspace, so an agent's tests
   cannot dirty the tree the handoff check reads. The seed regression suite runs from pristine
   copies under `tests/__seed/`, with `seed_tests_modified` as a diagnostic. The stdlib check
   parses imports with `ast` instead of matching docstring lines. `process_stages_clean` ignores
   the fixed review as well as the implement stage. The hidden conftest maps `SystemExit` to an
   exit code.
4. **Five contract-derived hidden tests** (import de-duplication ignores category; import amounts
   are exact cents; the report omits budgeted categories with no spending; apply ignores an
   identical manual entry; spent equal to the limit is not over), and the brief now defines
   `remaining`. Reference 37/37, seed 5/37.
5. **The fixed reviewer runs in a synthetic repository** (above), `change_description.md` has no
   path in its heading, and `run_local.sh` runs a private copy of the harness so no repository
   path reaches a session.
6. **The time budget was binding only in arms with author or review stages.** Caps sum to 9000 s;
   the driver budget is 9600 s and the agent timeout 10500 s; the driver runs under `timeout` so
   the copy-out always happens; SDK lifecycle calls are bounded; `deadline_clamped` is recorded.
7. **Session isolation and provider routing are pinned** (above), structured output falls back to
   a prompted JSON turn when the schema path errors, and usage is accounted from live events
   because `assistant.usage` is not persisted.
8. **Statistics.** The t quantile was taken from the first tabulated df at or above the actual
   df, which made intervals too narrow; it now uses the largest df at or below. The condition key
   includes model, reviewer model and brief hash; mixed conditions stop the analysis; model
   mismatches are invalid; a calibration table shows whether the reviewer's verdict tracks the
   hidden tests; the smallest attainable p and the minimum detectable effect print next to every
   difference; PP is labelled as the biased sensitivity view it is.
9. **How to run a comparison** so it can be interpreted: one job for all arms, the pilot gate,
   and what artifact comparisons can and cannot say (`processes/README.md`).

## Fifth review pass

The fifth pass reviewed the three-task generalisation (the two cloudbill tasks, `task_config.json`,
the shared grading code and the build script) with one reviewer and one adjudicator who reproduced
each finding before ruling and made the changes. It is saved as
`docs/adjudication-2026-10-20-tasks.json`. Verdict: sound enough to run a pilot on; the two findings
worth fixing first both added noise to the primary endpoint on the greenfield task rather than bias.
Six findings were upheld (two in part), one rejected as out of scope (the workflow's own worktrees
under `.claude/`), and three defects the reviewer did not see were found and fixed on the way.

1. **The memory test was a knife edge.** On the 600,000-row export the natural two-pass design (one
   dict entry per line item id holding its latest `last_updated`) peaked at 98.3 MB against the
   100 MB cap, inside it by less than an interpreter or allocator difference, so one test worth 0.11
   of the headline could flip on noise. The export is now 1,500,000 rows (about 380 MB): a bare set
   of ids measures 183 MB, the id-to-`last_updated` map 270 MB, and the references 25 to 36 MB, so
   the test is 80 MB clear of the cap on both sides. The numbers are in the hidden conftest and
   `tasks/README.md`.
2. **Raising the size exposed a generator defect.** `write_large` stamped its corrections with fixed
   September dates while each row's own `last_updated` is its start plus five hours; past 20
   September the original was the later version and the reference, correctly, kept it, so the
   reference failed its own memory test on the larger export. Corrections are now stamped relative to
   the end of the export and the oracle holds at any size.
3. **Time boxes nest.** One run of the tool inside the hidden suite is capped at 240 s and fails that
   test with a message; the cloudbill suites have 900 s and their `task.toml` verifier 1800 s (the
   grader runs the hidden suite and the visible one). Before, a per-run timeout of 900 s sat inside a
   600 s suite budget, so a slow tool lost the whole hidden suite rather than one test.
   `scripts/test_build_tasks.py::test_the_time_boxes_nest` keeps it that way.
4. **Hidden tests check stated rules, not display choices.** The file-order property compares the
   service view by normalised key and money, since which spelling of a service name is shown is the
   implementer's; accounts, months and statistics are still compared exactly. An unknown line item
   type (a stated rejection rule) now has a generator mode, a scenario row and a test. A header-only
   export, which the brief does not classify, may be answered empty or refused with exit 1, but the
   test first checks that the tool answers a one-row export at all, so the untouched seed still fails
   it. Both cloudbill suites grew by one test: 0 / 55 and 2 / 75 on the seeds, all passing on the
   references.
5. **Documentation.** The fake backend's docstring says its intent and reviews are ledger-shaped
   placeholders on every task; two figures in this file were corrected.

Verified after the changes: offline suites 55 passed; hidden tests 0 / 55 and 55 / 55
(cloudbill-report, 55 s for the reference suite here), 2 / 75 and 75 / 75 (cloudbill-sqlite, 131 s),
5 / 37 and 37 / 37 (ledger-budgets); the seven fake runs through `run_local.sh` all grade 0.961 with
correctness 1.0; Reward Kit through `uvx` on one saved run per task gives the same numbers in 57 s,
133 s and 5 s; `scripts/build_tasks.py --check` is clean.

### Limitations to state in any write-up

- Three tasks, all Python, two of them on one domain (the migration task's seed is the greenfield
  task's reference). ledger-budgets has a fully specified interface contract, so correctness there
  can only move through slips against a spec-grade brief and may sit at the ceiling in every arm;
  the cloudbill briefs are lighter and leave real decisions open (encodings, duplicates, rounding,
  the percentile method, the text layout), but every hidden test still checks a stated item or a
  property. Report results per task; do not pool tasks. Results do not
  generalise beyond these tasks or beyond Python.
- The scripted stand-in adds no information beyond the brief, so the authoring dialogue's main
  mechanism (eliciting decisions the author holds) is not exercised. A null or negative result is
  not evidence against change intents where the author knows things the brief does not say.
- A whole-process comparison bundles about 60 KB of guidance, an extra authoring session, the
  artifact and a process review pass against a baseline with none of them. A win cannot be
  attributed to the artifact alone without the decomposition arms.
- A frozen-artifact comparison compares specific documents (one per shape) written by the
  experimenter, under change-intent-specific guidance. It says nothing about artifact shape.
- The review dimension (2/7 of the headline) is a single LLM judge whose input includes a
  condition-dependent description. It is not calibrated against humans, its test-retest
  reliability is not yet measured, and it can be moved by description quality independently of
  the code. Review results are exploratory; the primary endpoint is correctness.
- A missing fixed review scores 0 (ITT). The headline is also reported with missing reviews
  excluded (XR) and the missing-review rate per arm. PP selects on post-treatment authoring
  success and is biased.
- Power: at three attempts per arm the smallest two-sided permutation p is 0.10, and the minimum
  detectable effect is about 3.0, 1.3 and 0.9 standard deviations at 3, 10 and 20 attempts. One
  failing hidden test moves the headline by about 0.11. Only one pre-registered comparison is
  confirmatory.
- The headline weights (4:2:1) are a design choice. Per-criterion means are reported so readers
  can re-weight.
- The tasks are medium-sized: ledger-budgets about 435 reference lines with low coupling;
  cloudbill-report about 1,160 lines of package and tests; cloudbill-sqlite about 600 changed or new
  lines on top of it.
- The memory cap of the cloudbill tasks is measured as the child's peak RSS on the grading machine,
  on a 1,500,000-row export (about 380 MB) rather than the 2 GB the brief names. The reference
  peaks at about 36 MB under the 100 MB cap and the smallest per-line-item design (a bare set of
  ids) at about 183 MB, so the test is robust to ordinary interpreter and allocator differences in
  both directions; at 600,000 rows a per-id map sat at 98 MB and would have passed or failed by
  noise. A design that passes here would still need to be streaming at 2 GB; the test cannot tell
  a design that spills to disk from one that happens to fit.
- Only Harbor runs count. Local real-model runs are not sandboxed from the repository.
- Server-side model behaviour (default reasoning effort, A/B treatments, alias updates) is outside
  the harness's control. Arms are interleaved in one job and the recorded signals are checked for
  heterogeneity, but a rerun weeks later may not match.

## What was and was not verified here

Verified in the authoring environment: hidden tests versus seed and reference; the driver end to
end in fake mode for baseline, change-intent-v1, and change-intent-v1-frozen through every stage;
the offline tests in `driver/test_author_stage.py` (stand-in probes for every loop the fourth
pass reproduced, an `ask_user` ruling flow, an author that never writes, a data-file-only turn,
the synthetic review repository, a prose-only reviewer, two artifact files) and
`scripts/test_analyze.py` (condition keys, heterogeneity, model mismatch, the conservative
interval, the mixed-condition stop);
Reward Kit grading of the resulting workspaces, including through `uvx` exactly as `test.sh`
runs it; headline parity across conditions with identical outputs; the stand-in stopping rules;
verifier survival on malformed reviewer output; the Harbor agent classes import against Harbor
0.24 and `task.toml` validates against its schema; the Copilot SDK runtime downloads, starts, and
creates a session; `create_session` accepts `excluded_tools`, `skip_custom_instructions`,
`additional_directories`, `on_event`, per-session `model`; `send_and_wait` accepts
`response_schema`; `get_events` is a coroutine and is awaited.

For the three-task generalisation, also verified offline: ledger-budgets grades exactly as before
(the three fake runs score 0.961 with every value in `reward-details.json` unchanged); for each
cloudbill task the hidden tests against the seed (0 of 55, 2 of 75) and the reference (55 of 55,
75 of 75); fake runs of baseline and change-intent-v1 on both new tasks (correctness 1.0, headline
0.961); Reward Kit through `uvx` via each task's `test.sh`; every `task.toml` validates against
Harbor's `TaskConfig`, the agent classes import against Harbor and resolve each task from its
instruction; and `scripts/test_build_tasks.py` (generated files in sync, every task config valid
and read by both the driver and the grader, the greenfield task without the seed criterion, the
agent's task selection, the continuation rule on the task's code directories, the overlay guard).

Not verified: a real model turn through the SDK (the environment's GitHub token has no Copilot
entitlement, the failure is `Session was not created with authentication info or custom
provider`), the Docker image build, and an actual `harbor run`. Those are the first three things
to do on a machine with Docker and a Copilot token. Two things to watch on the first real run:
whether the tool names in `excluded_tools` match the CLI's current names (the reset-and-record
fallback covers a mismatch), and whether the model honours the response schema on a long review
turn (the raw message is kept and the parser is lenient).
