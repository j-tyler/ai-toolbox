# Change-intent process eval (prototype)

An evaluation harness for comparing **code-generation processes**, not models. Every condition
uses the same model, the same tools, the same workspace, and the same brief. What varies is the
process the agent follows: no intent at all, change intent as drafted in
[`../mechanics`](../mechanics/README.md), or any variant you add. The output is graded by
third-party, inspectable tooling so the comparison is defensible to people who did not build it.

Status: **prototype**. The pipeline runs end to end offline (fake backend) and the grader
discriminates correctly. Real Copilot runs and Harbor container runs are wired up but were not
executed in the authoring environment, which has no Copilot-entitled token and no Docker daemon.
The review stage is deliberately not included yet; it slots in as a third stage in the driver.

## Pieces

| Piece | Where | Third party? |
| --- | --- | --- |
| Outer harness: containers, repeated trials, logs, viewer | [Harbor](https://github.com/harbor-framework/harbor), Apache-2.0 | yes |
| Grader: multi-dimension verifier with audit details | [Reward Kit](https://docs.harborframework.com/rewardkit/quick-start), part of Harbor | yes |
| Agent runtime | [GitHub Copilot SDK](https://github.com/github/copilot-sdk), MIT, Python | yes |
| The exercise: seed project, brief, hidden tests, reference solution | `tasks/ledger-budgets/` | ours |
| Process versions, generated from `../mechanics` | `processes/` | ours |
| Driver: author → implement with a stand-in author | `driver/` | ours |
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

Hidden acceptance tests (31, under `tests/__hidden/`) are never visible to the agent. On the
untouched seed they fail 27 of 31; on the reference solution all pass, and the seed's own 17 tests
still pass.

## How a run works

1. Harbor builds the task image (seed repo, Python, pytest, uv) and installs the Copilot CLI and
   SDK in it, then uploads `driver/` and the chosen `processes/<name>/`.
2. `driver/run_process.py` turns the workspace into a git repo, installs the process files
   (appends the agents-file block to `AGENTS.md`, creates `change-intent/`), and commits a baseline.
3. **Author stage** (change-intent processes only): one Copilot SDK session with the
   `change-intent-author` skill loaded. The skill's questions reach a **stand-in author**
   (`driver/stand_in.py`): `ask_user` tool calls arrive through the SDK's `on_user_input_request`
   handler, and prose questions at the end of a turn get a scripted reply on the next turn. The
   scripted policy is: confirm the brief, take the recommended or first option, keep scope
   minimal, approve. A model-backed stand-in exists for skills that ask open questions. Either
   way the stand-in is identical across conditions and every exchange is logged. The approved
   intent is committed.
4. **Implement stage**: a fresh session with the implementation guidance appended to its system
   prompt and a prompt that points at the committed intent file by path, with the brief attached
   as context. The baseline gets the brief alone. The result is committed.
5. The driver writes `.eval/` (summary, dialogue log, full SDK events per stage, readable
   transcripts, `diff.patch`), and Harbor runs `tests/test.sh`, which is Reward Kit.

### Grading dimensions (today)

```
reward            weighted mean: correctness 4, process 1
  correctness     acceptance (hidden tests pass fraction, all-pass) 3 : regression (seed tests, agent's suite, stdlib-only) 1
  process         artifacts (committed, summary without errors, tests added) 2 : intent (file present, required sections) 1
```

Offline check, fake backend, same grader: change-intent-v1 0.958, baseline 0.891, untouched seed
0.303. The baseline loses only on the intent-artifact checks, which is by design and why
`process` is weighted low. `reward-details.json` lists every criterion's value.

Judge-based dimensions (intent quality, implementation adherence, reviewability with a fixed
reviewer) are the next addition: a sibling directory under `tests/` with a Reward Kit judge TOML.
Keep the judge model pinned and from a different vendor than the implementer.

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
scripts/run_local.sh change-intent-v1 --model gpt-5.4
scripts/run_local.sh baseline --model gpt-5.4
```

BYOK instead of Copilot entitlement: pass `--provider-json '{"type":"anthropic","base_url":"...","api_key":"..."}'`
(the SDK's `ProviderConfig`). Note that without BYOK each SDK prompt counts against the Copilot
premium-request quota.

### Harbor runs (needs Docker)

```bash
cd ideas/change-intent/eval
uv tool install harbor                      # or pip install harbor
export COPILOT_GITHUB_TOKEN=...
harbor run -p tasks/ledger-budgets -a agents.copilot_process:ChangeIntentV1 -m gpt-5.4 -k 3
harbor run -p tasks/ledger-budgets -a agents.copilot_process:Baseline        -m gpt-5.4 -k 3
harbor view jobs
```

`-k` is attempts per task; three is the floor for seeing past run-to-run variance on a change
this size. Harbor keeps every trial's trajectory, the verifier output, and the `.eval/` artifacts
(copied to the agent logs). Sanity-check the task itself with the oracle: `-a oracle` overlays
the reference solution and should score 1.0 on correctness.

## Adding a process version

Process versions are directories under `processes/` with a `process.json`:

```json
{ "name": "...", "stages": ["author", "implement"],
  "agents_block": "AGENTS.block.md", "skills_dir": "skills", "authoring_skill": "change-intent-author",
  "implementation_guidance": "implementation-guidance.md", "intent_dir": "change-intent" }
```

`change-intent-v1` is generated from `../mechanics` by `scripts/build_processes.py`; re-run it
after editing the mechanics. To try a variant, copy the generated directory to a new name, edit
the copy, add a two-line subclass in `agents/copilot_process.py`, and run it with `-a`.

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

## What was and was not verified here

Verified in the authoring environment: hidden tests versus seed and reference; the driver end to
end in fake mode for both processes; Reward Kit grading of the resulting workspaces; the Harbor
agent classes import against Harbor 0.24 and `task.toml` validates against its schema; the
Copilot SDK runtime downloads, starts, and creates a session.

Not verified: a real model turn through the SDK (the environment's GitHub token has no Copilot
entitlement, the failure is `Session was not created with authentication info or custom
provider`), the Docker image build, and an actual `harbor run`. Those are the first three things
to do on a machine with Docker and a Copilot token.
