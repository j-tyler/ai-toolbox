# Agents-File Block

**Status: drafted. Bracketed names are placeholders until the instruments ship.**

The block below is what a team copies into their project's agents file (`AGENTS.md`, `CLAUDE.md`, or equivalent) so every agent working in the project is intent-aware without further setup. It is written for an AI agent reading it at the start of a context window, with no prior knowledge of change intent: decision procedure first, hard rules second, explanation only where it makes the rules execute faithfully. Seat-specific instructions stay out; they live in the instrument each agent loads when it takes the seat ([authoring-skill.md](authoring-skill.md), [implementation-guidance.md](implementation-guidance.md), [review-guidance.md](review-guidance.md)).

Before pasting, customize the `[BRACKETED]` spots: the skill names and the observable-behavior channel list. Everything else is designed to be used verbatim.

---

## Change intent

This project uses change intents: per-change contracts authored **before any code is written**, stored at `change-intent/YYYY-MM-DD-short-slug.md`. An intent states what a change must accomplish. The implementation must satisfy the intent — never the reverse. Every change is reviewed against its intent, so work that drifts from or bypasses an intent will fail review. The point: review checks the code against its stated intent, so the human's attention goes to whether the intent was right.

**Exactly one intent file per pull request.** Not one per commit, and never a second intent for later rounds of edits in the same PR — the original intent governs until merge, amended on the record if it proves wrong. Work that needs two intents is two changes: ship it as two pull requests.

### What to do, by task

- **Planning or starting a change** → run the authoring skill (`[/change-intent-author]`). Do not plan ad hoc and do not write an intent file freehand; the skill runs the pre-code dialogue and writes the file.
- **Implementing a change that has an intent** → the intent is your goal and your contract; follow `[implementation guidance]`: a passing test per acceptance criterion, a walk of the diff per invariant.
- **Reviewing a change** → follow `[your team's review process]`; its instructions carry the change-intent review guidance. You are checking the diff against its intent, not the diff alone.
- **Revising a change after review** → review — human or machine — can surface something significant enough that the author re-decides: they refuse an amendment, or want a different approach after seeing the finished implementation. The revision runs through the authoring skill against the existing file (same file, same slug) and is re-approved. Expect to then implement a revised intent with a partial implementation already on the branch: the revised intent is the contract — keep work that satisfies it, redo work that does not.
- **Anything that is not a change** (questions, debugging, exploration) → no process applies. Intent files are context; read them freely.

If asked to implement a change and no intent exists, say so and offer to run the authoring skill. Never write code first and backfill an intent to match it — a backfilled intent is worse than none. A prototype is not backfilling: exploratory work needs no intent, but shipping its result is a change — the intent is authored when the author decides what to ship, and the implementation that merges is reviewed against it.

### Rules that apply in every role

- **If a claim cannot hold, amend the intent — on the record.** If you are implementing and the intent is wrong as written — a claim that cannot hold, or the change forces observable behavior the intent takes no position on — amend the intent file: change the claim, add a dated entry under Amendments (what changed — the discovered fact that forced it), and note the discovery next to the claim it changed. Never pretend a claim holds and never drift past it silently; amendment exists so you never have to. This should be rare. The author rules on every amendment when the work comes back, and one they would have refused means rework — so amend with the evidence you would want in their place. If no amendment can deliver the change, stop and report: that is a failed change, not an amendment.
- **New direction from the author is a reopening, not an amendment.** If direction conflicts with the approved intent and the intent is not wrong — the author re-decided — do not record it as an amendment and do not implement against the old intent: route it through a revision (task list above), then continue.
- **Stay inside scope.** Items under "Out of scope" are conscious exclusions, not oversights — do not fix them while implementing this change. If you discover an improvement, propose it as a new intent; never fold it into the current one.
- **Add no unclaimed observable behavior.** Observable in this project means: `[UNCONFIGURED — team: replace with your list, e.g., API request/response shapes, persisted data formats, named metrics and log events, public error types. Agent: if you are reading this unfilled, the list is not set — ask rather than assuming these examples.]`. If your diff changes one of these channels and no claim or out-of-scope entry covers it: the change forced it → amend (rule above); your implementation chose it → remove it.
- **Discretion granted in the intent's text** ("TTL may be 10–60s, implementation's choice") **is yours to exercise without asking.** Anything else that conflicts with the intent: amend if the intent is wrong, treat it as a reopening if the author re-decided, otherwise don't do it.

### Reading an intent file

- **Outcomes** — what the change is intended to make true, in a few bullets — not the implementation chosen for it.
- **Why** — motivation and context that cannot be reconstructed from the diff. Always present.
- **Acceptance criteria** — falsifiable scenarios, each provable by a single test written at implementation time.
- **Invariants** — properties that span multiple code paths or call sites ("across all callers…"). Closed by reasoning over every affected site in the diff, not by any test alone. Do not treat them as acceptance criteria.
- **Out of scope** — what was considered and deliberately excluded.
- **Amendments** — repairs made during implementation; the author rules on each when the work returns. Absent means the intent held as written.

### Frozen history

Merged intents are never edited. They record what was decided *then*, not what holds *now* — verify current behavior against code and tests, never against old intents. Use the folder as memory, though: before working on a surface, grep `change-intent/` for prior intents that touched it. Their Why sections carry reasoning you cannot get anywhere else.

### When an intent is required

Every change. There is no change without an outcome and a why, so there is no change without an intent. Small changes have small intents.
