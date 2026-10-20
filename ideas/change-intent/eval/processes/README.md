# Process versions

A process version is one experimental condition: everything the agent is told beyond the brief.
Each is a directory with a `process.json` and the files it names. The harness owns the stage
prompts, the stand-in author, and the fixed reviewer, and keeps their wording neutral;
process-specific wording enters only through `process.json` fields (the files it names and
`intent.noun`, the word the harness uses for the artifact).

```json
{
  "name": "change-intent-v1",
  "agents_block": "AGENTS.block.md",
  "author":    { "mode": "skill", "skill": "change-intent-author", "skills_dir": "skills",
                 "prompt_file": null, "custom_instructions": true },
  "implement": { "system_append": "implementation-guidance.md", "prompt_file": null,
                 "include_brief": true, "custom_instructions": true },
  "review":    { "system_append": "review-guidance.md", "prompt_file": null, "custom_instructions": true },
  "intent":    { "dir": "change-intent", "noun": "change intent",
                 "claim_sections": ["Acceptance criteria", "Invariants"],
                 "required_sections": ["Outcomes", "Why", "Constraints", "Acceptance criteria", "Invariants", "Out of scope"] }
}
```

| Field | What it controls |
| --- | --- |
| `agents_block` | Appended to the workspace `AGENTS.md` before any stage. Null for none. |
| `author.mode` | `skill`: run the authoring skill with the stand-in author. `frozen`: commit a supplied intent (`--intent-file`, or `author.frozen_intent`) with no dialogue. `none`: no intent. |
| `author.skill`, `author.skills_dir` | The skill the author session is told to use and where its `SKILL.md` lives. |
| `*.prompt_file` | Optional template replacing the harness's neutral prompt for that stage. Placeholders: author `{skill} {intent_dir} {brief}`; implement `{source} {brief_section} {brief}`; review `{baseline} {intent_path}`. |
| `*.system_append` | File appended to that stage's system prompt. This is where guidance belongs. |
| `*.custom_instructions` | Whether that session loads `AGENTS.md` and the like from the workspace. |
| `implement.include_brief` | Attach the brief alongside the intent. `false` makes the intent the implementer's only source. |
| `review` | Null for no process-owned review pass. The fixed harness reviewer runs regardless. |
| `intent.dir`, `intent.noun` | Where the artifact lives, and what the harness calls it in its prompts and the stand-in's replies ("change intent", "spec", "plan"; default "description document"). |
| `intent.claim_sections`, `intent.required_sections` | Which `## ` sections hold claims and which must be present. Used only by the weight-zero diagnostics; the verifier reads them from the copied `process.json`. |

## Versions here

- **baseline**: no intent, no guidance. The implementer gets the neutral prompt and the brief.
- **change-intent-v1**: generated from `../../mechanics` by `scripts/build_processes.py`. Authoring
  skill, implementation guidance, review guidance, agents-file block.
- **change-intent-v1-frozen**: the same guidance with a pre-authored intent (`--intent-file`).
  Removes authoring variance so the intent artifact itself is what varies.

## Designing a comparison

What the headline reward can attribute depends on what you hold constant:

| Question | Vary | Hold constant | What the answer can and cannot say |
| --- | --- | --- | --- |
| Does the whole process help? | process version | model, brief, stand-in | Bundles the guidance (about 60 KB), an extra authoring session, the artifact and a process review pass against a baseline with none of them. A win is not attributable to the artifact alone. |
| Is this intent *artifact* better than that one? | `--intent-file` under the frozen process | guidance, model, brief | Compares two specific documents, one per condition, under change-intent-specific guidance. It says nothing about artifact *shape*. |
| Does the *guidance* help, given the same intent? | `implement.system_append` (copy the frozen process) | the frozen intent |
| Does the authoring *skill* produce better intents? | `author.skill` (run authoring only, then freeze) | everything downstream |
| Does the intent carry the information alone? | `implement.include_brief: false` | the intent |

Comparing artifact **shapes** (change intent versus spec versus plan) needs two things this
directory does not yet hold: a process per shape whose guidance is shape-neutral, so that
`intent.noun` and the artifact are the only differences, and at least five artifacts per shape,
produced by the same skill and stand-in, or by authors who have not seen `tests/__hidden`, analysed
by artifact cluster rather than pooled as trials. One document per shape is an anecdote.

Run order for any comparison: a baseline pilot at about five attempts first. If its mean
correctness is at least 0.95, or nine in ten trials pass every hidden test, this task cannot
discriminate on the primary endpoint; add a task or a lighter-brief variant before the full run.
Put every arm in one Harbor job so trials interleave (the agent docstring shows the config).

Regenerate the generated versions after editing the mechanics; copy a directory to make a variant;
add a two-line subclass in `agents/copilot_process.py` to run it under Harbor.
