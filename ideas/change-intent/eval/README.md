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
| The exercise: seed project, brief, hidden tests, reference solution | `tasks/ledger-budgets/` | ours |
| Process versions, generated from `../mechanics`; schema in `processes/README.md` | `processes/` | ours |
| Driver: author → implement → review → fixed review, with a stand-in author | `driver/` | ours |
| Fixed reviewer instructions, assembled from published sources | `reviewer/` | ours, cited |
| Harbor agent classes, one per condition | `agents/copilot_process.py` | ours |

Everything "ours" is small and meant to be read. The claim to neutrality rests on the hidden
tests being objective, the grader being someone else's, and the process files being the only
thing that differs between conditions.

## The exercise

`ledger` is a 300-line stdlib Python CLI that records and lists transactions. The brief
([`tasks/ledger-budgets/instruction.md`](tasks/ledger-budgets/instruction.md)) asks for budgets,
recurring transactions, bank-CSV import with de-duplication, and a monthly report, with an
interface contract precise enough to test and open enough to leave real decisions. The reference
solution is about 500 lines of implementation; with the tests the brief demands, a complete
answer lands in the 1,000 to 2,000 line range.

Hidden acceptance tests (32, under `tests/__hidden/`) are never visible to the agent. On the
untouched seed they fail 28 of 32; on the reference solution all pass, and the seed's own 17 tests
still pass. The tests keep the ledger in a `data/` subdirectory with a different working directory,
so "files next to the ledger file" is checked, not assumed.

## How a run works

1. Harbor builds the task image (seed repo, Python, pytest, uv, a git identity) and installs the
   Copilot CLI and pinned SDK in it, then uploads `driver/`, `reviewer/`, and the chosen
   `processes/<name>/`.
2. `driver/run_process.py` turns the workspace into a git repo, installs the process files
   (appends the agents-file block to `AGENTS.md`, creates the intent directory), and commits a
   baseline. Every artifact it produces lives **outside the workspace** until the end, so no stage
   can read another stage's output unless the harness hands it over.
3. **Author stage**, by `author.mode`. `skill`: one SDK session with the process's authoring skill
   loaded; its questions reach a **stand-in author** (`driver/stand_in.py`) through the SDK's
   `on_user_input_request` handler for `ask_user` calls and through scripted replies for prose
   questions. The dialogue ends when a commit made during the stage touches the intent directory,
   whatever the agent asks next; an existing but uncommitted draft gets one request to show it for
   approval. The stage records `author_outcome` (approved, unapproved_file, no_file) and which cue
   produced the approval, and restores and flags anything the author changed outside the intent
   directory, committed or not. `frozen`: a supplied file is committed with no dialogue, which
   removes authoring variance. `none`: no artifact. Harness commit messages are condition-neutral.
   `driver/test_author_stage.py` pins these rules.
4. **Implement stage**: a fresh session. The prompt is the same neutral text for every condition
   ("implement the change described in the {noun} at {path}", or "in the brief below"), with the
   brief attached when `implement.include_brief` is true. The noun comes from `intent.noun` in
   `process.json`, so a spec or a plan is named as such. Everything process-specific
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
   read-only tool set) runs [`reviewer/fixed_reviewer.md`](reviewer/fixed_reviewer.md) with
   workspace custom instructions **off**, so the change-intent `AGENTS.md` block cannot reach it,
   and with exactly two inputs copied into a sealed temporary directory outside both the workspace
   and the harness work directory: `diff.patch` and `change_description.md`. If the first answer is
   not JSON the driver asks once more for JSON only.
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

Offline check, fake backend, same grader, same fake output for every condition: baseline,
change-intent-v1, and change-intent-v1-frozen all score 0.961 on the headline, and differ only in
diagnostics (0.017 vs 0.665). That parity is the property that makes a real difference
attributable to the process. In real runs the review dimension is where conditions are expected
to separate: the fixed reviewer rates description adequacy and verifiability from the artifacts
each process leaves behind, and `verified_claims_ratio` is a ratio so a description that claims
less cannot win by claiming less.

## Running

### Offline pipeline check (no model, no Docker, ~5 s)

```bash
cd ideas/change-intent/eval
pip install -r requirements.txt            # or use uv
scripts/run_local.sh change-intent-v1 --backend fake
scripts/run_local.sh baseline --backend fake
scripts/analyze.py runs/
```

### Real run without Harbor (needs a Copilot-entitled token)

```bash
export COPILOT_GITHUB_TOKEN=...            # a token for a user with Copilot access
scripts/run_local.sh change-intent-v1 --model gpt-5.4 --reviewer-model claude-sonnet-4.5
scripts/run_local.sh baseline         --model gpt-5.4 --reviewer-model claude-sonnet-4.5
scripts/run_local.sh change-intent-v1-frozen --intent-file path/to/intent.md --model gpt-5.4 --reviewer-model claude-sonnet-4.5
scripts/analyze.py runs/ --ref baseline
```

The workspace is created outside the repository so a real run cannot read the hidden tests.

BYOK instead of Copilot entitlement: pass `--provider-json '{"type":"anthropic","base_url":"...","api_key":"..."}'`
(the SDK's `ProviderConfig`). Note that without BYOK each SDK prompt counts against the Copilot
premium-request quota.

### Harbor runs (needs Docker)

```bash
cd ideas/change-intent/eval
uv tool install harbor                      # or pip install harbor
export COPILOT_GITHUB_TOKEN=... EVAL_REVIEWER_MODEL=claude-sonnet-4.5
PYTHONPATH=. harbor run -p tasks/ledger-budgets -a oracle -k 1                                    # task sanity check: correctness 1.0
PYTHONPATH=. harbor run -p tasks/ledger-budgets -a agents.copilot_process:ChangeIntentV1 -m gpt-5.4 -k 3
PYTHONPATH=. harbor run -p tasks/ledger-budgets -a agents.copilot_process:Baseline        -m gpt-5.4 -k 3
EVAL_INTENT_FILE=path/to/intent.md EVAL_LABELS=intent=A \
PYTHONPATH=. harbor run -p tasks/ledger-budgets -a agents.copilot_process:ChangeIntentV1Frozen -m gpt-5.4 -k 3
harbor view jobs
scripts/analyze.py ~/jobs/<job> --ref baseline
```

The task's agent timeout is 9000 s; the driver is given a 7800 s deadline so it always finishes,
resets, and copies its artifacts inside that window.

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
- **Harbor copies `tests/` into the container only at verification time**, so the agent never
  sees the hidden tests or the criteria.
- **Verifier interpreter.** Reward Kit runs under `uvx` with its own virtualenv; the criteria run
  pytest with the workspace image's `python3`, which has pytest installed.
- **Two reviews, two owners.** The process review belongs to the process version and varies with
  it; the fixed reviewer belongs to the harness and never varies. Only the fixed reviewer's output
  feeds the `review` dimension. Its instructions quote published sources (Google's review guide,
  the published Anthropic reviewer threshold, OpenAI's review schema shape, the TU Delft
  reviewability factors) so nobody in the experiment wrote the reviewer for their own process.
- **The fixed reviewer sees the intent.** This is a deliberate choice: "reviewable with the
  artifact the process actually leaves behind" is the claim under test. Its verdict standard is
  relative to the description, which favours sparser descriptions a little; the ratio scoring and
  the neutral heading reduce that, and a blinded diff-only arm is listed under future work. The
  intent file is also inside `diff.patch`; `summary.json` records a code-only shortstat as well.
- **Reviewers are read-only by construction and by cleanup.** Edit tools are excluded from review
  sessions, and the driver resets the tree to the implementation commit afterwards and records
  anything that moved.
- **Structured output.** The fixed reviewer returns JSON through the SDK's `response_schema`; the
  driver validates it, tolerates a fenced block or surrounding prose, and keeps the raw message.
- **Every run is pinned and manifested.** `summary.json` carries the harness git SHA, SDK
  version, the hash of every process file, the brief, the reviewer instructions, the schema, and
  each rendered prompt, plus the resolved model per stage when the SDK reports it.
- **Time caps are per stage and identical across conditions.** The implement cap does not shrink
  because authoring took long; `task.toml`'s agent timeout covers the sum.

## What the review changed

A workflow of two independent Opus reviewers (defects; swappability of intent and guidance) and
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

## What was and was not verified here

Verified in the authoring environment: hidden tests versus seed and reference; the driver end to
end in fake mode for baseline, change-intent-v1, and change-intent-v1-frozen through every stage;
the offline tests in `driver/test_author_stage.py` and `scripts/test_analyze.py`;
Reward Kit grading of the resulting workspaces, including through `uvx` exactly as `test.sh`
runs it; headline parity across conditions with identical outputs; the stand-in stopping rules;
verifier survival on malformed reviewer output; the Harbor agent classes import against Harbor
0.24 and `task.toml` validates against its schema; the Copilot SDK runtime downloads, starts, and
creates a session; `create_session` accepts `excluded_tools`, `skip_custom_instructions`,
`additional_directories`, `on_event`, per-session `model`; `send_and_wait` accepts
`response_schema`; `get_events` is a coroutine and is awaited.

Not verified: a real model turn through the SDK (the environment's GitHub token has no Copilot
entitlement, the failure is `Session was not created with authentication info or custom
provider`), the Docker image build, and an actual `harbor run`. Those are the first three things
to do on a machine with Docker and a Copilot token. Two things to watch on the first real run:
whether the tool names in `excluded_tools` match the CLI's current names (the reset-and-record
fallback covers a mismatch), and whether the model honours the response schema on a long review
turn (the raw message is kept and the parser is lenient).
