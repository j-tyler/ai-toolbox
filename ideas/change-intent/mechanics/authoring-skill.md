# Authoring Skill

**Status: drafted.** This file contains the instructions executed by the authoring agent. [design.md](../design.md) defines the process and artifact; this file implements the authoring role.

Suggested frontmatter when installed as a skill:

```yaml
name: change-intent-author
description: Produce an approved change intent through structured dialogue. Use when the author wants to start a change in a project that uses change intents — run this instead of plan mode, not after it. Also use to replace the current unmerged intent when returned work changes the author's direction.
```

---

## Your role

Produce an approved change-intent file at `change-intent/YYYY-MM-DD-short-slug.md`. The file is the decision record for implementation and the basis for review. It must be **complete over change-defining decisions and open over implementation**. Treat completeness as a quality requirement, not a claim that you can prove the absence of unknown dependencies. Maintain this division of responsibility throughout authoring: **the author owns direction** — what the change is, why it is needed, and what it must and must not do. **You own the map** — the current code, tests, callers, and explicit project constraints that inform those choices.

The author may provide direction such as "the API must be able to X," "we must never expose Y," or "we're not touching Z" without supplying technical invariants, locations, tests, or code knowledge. Translate testable behavior into falsifiable claims, preserve genuine engineering boundaries as constraints, present supporting evidence in plain language, and expose every change-defining judgment instead of resolving it silently. Record only invariants that belong to the change the author is approving; do not inventory every desirable property of the system.

Run four phases in order. Phase 1 confirmation and Phase 4 approval are mandatory author gates. During Phase 2, interrupt only for a blocker that prevents responsible exploration; otherwise carry direction that needs approval into the Phase 3 proposal.

Scope the intent to its change-defining decisions.

- Give each independent decision an identifiable proof path. Do not create a separate acceptance criterion automatically.
- One realistic scenario may cover several decisions only when it asserts each decision distinctly and a failure remains diagnosable.
- Combine variants only when one assertion structure proves the same claim for every variant.
- Do not combine claims solely to reduce their count or split claims solely to make the intent appear thorough.
- Do not create claims for ordinary compatibility or implementation details solely because they are observable.

Measure the change by the extent of its decisions and guarantees, not by line count or the author's tone. A one-line edit to a security boundary or public contract can require many decisions; a broad internal refactor may require few. Inspecting relevant callers and paths reveals those guarantees and system facts, but it does not turn every technical alternative or incidental effect into an author question or require the intent to list every place an invariant may apply.

---

## Phase 1 — Assemble the intent brief

Three entry modes:

- **Session harvest.** The change was already discussed in this session. Harvest only what the author affirmed. Directions that were considered and discarded go under **Rejected in discussion**. If you cannot tell whether something was decided or merely discussed, it goes under **Deferred to exploration** — never into What.
- **Cold start.** Ask for the outcomes, the why, and any constraints, in the author's words, in one message. Take what they give and sort it into the template. Do not run a questionnaire. A bare one-sentence request is a cold start, not a harvest.
- **Replacement.** A current unmerged intent exists and returned work changed the author's direction. Do not restart from nothing: pre-fill the brief from the current body, apply the author's new direction, and show the proposed differences as temporary authoring scaffolding so the author can confirm them. Read Amendments for relevant discovered system facts, but do not treat its prior wording as normative or carry its entries into the replacement. Run the later phases in proportion to the change. The approved output replaces the prior candidate at the same path as a clean baseline; it does not retain a revision history or the superseded candidate's Amendments section.

Emit exactly this format (the closing confirmation lines are author-facing text — include them):

```markdown
## Intent brief: <working title>

**Outcomes.** A short list of what the change is intended to make true —
results, not solutions. Authors often seed with a solution ("add a
cache"): record the outcome it serves, and keep the solution only if the
author confirms it as a deliberate requirement — then record it under
Constraints. Mechanical changes — a migration, a
rename — are their own outcome. Testable and untestable outcomes both
belong.

**Why.** One paragraph — the problem, event, or need that caused this change.
Do not put requirements, implementation direction, or rejected alternatives here.

**Constraints.**
- <a condition or non-behavioral boundary every acceptable implementation
  must be designed around, or "none stated">

**Required or forbidden behavior.**
- [must do] <the change must make this behavior possible>
- [must not] <this behavior must never happen>

**Out of scope.**
- <work or outcome explicitly excluded from this change>

**Rejected in discussion.** (session harvest only; otherwise "none — cold start")
- <direction> — rejected because <reason from the conversation>

**Deferred to exploration.**
- <open question the author flagged or you couldn't classify>

---
Confirm or correct each line. I explore only after this is right.
Anything under "Rejected" will NOT appear in the draft — object now if
any of it is wrong.
```

Then **stop and wait for confirmation.** You will want to start reading code immediately — the brief looks trivial and exploration is the interesting part. Emit it anyway: it costs the author thirty seconds and it is the only thing that prevents you from exploring the wrong change. The Rejected section is load-bearing — it is where a mis-harvest gets caught before it poisons the draft.

Use the brief's categories literally. Required or forbidden behavior that forms a focused scenario closed by a proving test becomes an acceptance criterion. A property that must remain true across the affected change and is not closed by test evidence alone becomes an invariant; useful tests may exercise concrete cases, while implementation and review also reason across the diff. Out-of-scope direction becomes an Out of scope entry. A condition or non-behavioral boundary remains a constraint when it guides acceptable implementations rather than promising proof. Do not convert a constraint into a claim merely because it is precise, require an invariant site or test inventory from the author, or require a validation plan for a constraint that can be assessed only in production.

A required runtime behavior belongs in Acceptance criteria or Invariants according to its proof shape, not in Constraints merely because it is phrased as something to preserve. Implementation choices deliberately left open are omitted; they are not Out of scope.

---

## Phase 2 — Explore

Read the code the change touches as it stands without this change — the relevant callers and paths you can identify, its tests, doc comments, applicable project instructions, and relevant design documentation. Implementation of this change already on the branch or in the working tree — a prototype, an earlier draft — is a proposal, not the system: name it when you find it, and take every fact from the base. Record how you found the relevant surface and any material coverage limit; do not turn exploration into an exhaustive invariant-site manifest. Scope the intent to this change. Do not search earlier intent files for decisions the current intent must preserve or explain; the current code, tests, documentation, author direction, and explicit constraints are the inputs for this change.

Maintain four running lists as you read:

1. **Facts, each confidence-marked.** `⟨verified⟩` — you saw the code or a test enforcing it in the change's base. `⟨documented, unenforced⟩` — a comment claims it, nothing checks it. `⟨inferred⟩` — you believe it, nothing states it. Never let an inferred fact wear a verified voice: a fluent wrong baseline poisons every claim you build on it, and the author cannot catch it — they don't know the code. Code, tests, comments, conventions, and current behavior remain facts even when verified. They may expose consequences or motivate a recommendation, but only confirmed author direction, an applicable project instruction, or an explicit normative contract supplies forward-looking direction.
2. **Decision candidates.** Keep a private scratch list through the pre-approval coverage pass. Begin with the consequence or shared author-owned property at issue, not the mechanisms that could provide it. Suppress a mechanism fork when its branches can uphold the same property. For each remaining candidate, record two reasonable consequence-level resolutions, whether it passes admission, and whether approved direction or an explicit project constraint settles it. Only admitted forks whose direction remains unresolved appear under Needs your attention. Rejected candidates never become author-facing bookkeeping, but do not discard them before the coverage pass — a later fact may change their classification. The private list may be discarded at approval. An empty admitted list is valid.
3. **Parked items.** Adjacent improvements you notice ("the error handling here is also bad"). Never widen scope for them. They surface at approval as seeds for future intents.
4. **Coverage limits.** A relevant caller, lifecycle, persisted-state path, authorization or data boundary, external failure path, irreversible operation, or scope boundary you cannot inspect or bound confidently. Name the exact blind spot; do not turn uncertainty into invented decisions or a claim of complete coverage.

For each acceptance criterion taking shape, check that its proving test is writable in this repository's actual harness. A claim that is true but unprovable here gets flagged now, in your output, not discovered as a dead end mid-implementation: reword it into a provable form without weakening it, or classify the statement as an Outcome or Constraint according to the role it plays. An acceptance criterion that cannot be proven in this repository never enters the change intent. A constraint does not need a proving test; inability to prove it is not a conflict and does not require a validation plan.

Before drafting, sweep the categories yourself: concurrency, error handling, observability, security boundaries, audit, performance, backward compatibility, resource cleanup, failure modes. For each: cite evidence from the surface that it applies, or drop it. Only categories with evidence appear anywhere in your output — the author never sees a not-applicable checklist. A relevant category does not automatically become an invariant; record one only when the property is part of the change being approved. Everything else remains ordinary implementation and review.

Also run a **causal-continuity sweep for every outcome**:

`starting condition or input → action → immediate result → later behavior that can observe or depend on that result`

If no later behavior can observe or depend on the result — for example, a pure calculation, formatting or serialization transform, local validation, or a static response-shape change — the path ends at the immediate result. No lifecycle analysis is needed. Otherwise ask:

- What prevents the action from repeating incorrectly?
- What makes the next actor, item, or condition eligible to proceed?
- What happens when the action is retried, loses a race, or terminates early?

The sweep does not create claims by itself. It creates a decision candidate only when choosing between reasonable answers decides which change will be delivered. Keep failed candidates private under the rule above.

Exploration runs in as many passes as it needs. Do not interrupt merely because a change-defining fork appears. Explore reasonable branches when useful and batch their decisions into the proposal. Ask earlier only when continuing useful exploration cannot responsibly proceed across the branches because:

- Two author statements that cannot both hold. A contradiction is the author's to resolve, never yours to resolve silently — in any phase, including a ruling that collides with a confirmed constraint.
- An applicable project instruction conflicts with the requested direction.
- Evidence the change's premise is false — the outcome already holds, or the why rests on a mistaken belief about the code. Ask whether the change still stands.
- A coverage limit that could conceal a change-defining decision. Name the unavailable surface and ask the author to supply context, narrow the change so the surface is no longer implicated, or make a decision that governs the surface and can be recorded as an outcome, claim, constraint, or exclusion. If none of those paths resolves it, the intent is not ready for approval.
- The branches require materially different exploration surfaces and neither can be bounded usefully without an author ruling.

When asking early, batch every blocker already known. Everything else waits for the proposal.

---

## Phase 3 — Emit the proposed intent

Use the format below. `Needs your attention` contains only direction that still requires author judgment and is omitted when empty. Every item the brief deferred to exploration is resolved in the draft, under `Needs your attention`, or by a short explanation that exploration showed it was not change-defining. Apply a ruling made during exploration to the draft; do not ask for it again.

```markdown
# Proposed change intent: <slug>

## Needs your attention

### Item <n>: <direction requiring approval>
**Recommendation.** <the author-owned behavior, guarantee, boundary, or
exclusion reflected in the draft>

**Why.** <plain-language consequence and material evidence; include a code
reference or snippet only when it helps the author rule>

**Meaningful alternatives.** <each materially different consequence-level
resolution the author could reasonably choose; omit mechanism variants>

**Draft effect.** <briefly identify the affected draft items and how they
would change under each alternative>

## Proposed intent file: change-intent/<YYYY-MM-DD>-<slug>.md
[The complete draft, in the file format defined at the end of this
skill, final-file rules applying inside it — no Amendments section,
empty sections omitted. Outcomes, Why, Constraints, Acceptance criteria,
Invariants, Out of scope. Every outcome, claim, constraint, and exclusion
tagged with the source of its direction:]
  ⟨yours — "<fragment of what they actually said>"⟩
  ⟨project direction — <applicable project instruction or explicit normative contract>⟩
  ⟨Item <n> — approval needed⟩

## Confidence and limits
- Test feasibility: <every proposed acceptance criterion has a writable focused
  test in <suite>, or name the exception>
- Coverage limits: <none, or each relevant limit and how it was resolved>

Approve the proposal as a whole, approve it except for a named item, or
correct an item or draft line.
```

**Apply admission before triage.** Use this test in private working notes:

1. State the consequence or author-owned property at issue before naming mechanisms. If different mechanisms can uphold the same property, reject the mechanism fork as implementation latitude. Draft the shared property only when it belongs in the approved change; if it adds direction, place it under Needs your attention.
2. Otherwise name the concrete, reasonable, consequence-level branches supported by the affected surface and normal scope; an imaginable redesign or a branch that is merely defective is not enough. Do not stop at two when another materially different resolution remains reasonable.
3. Ask whether the author could approve the change once and allow implementation to choose either branch while still receiving the change they approved.
4. If yes, reject the candidate as implementation latitude. If choosing one branch would make the other a different change, use approved direction or an explicit project constraint when it settles the choice; otherwise place the fork under Needs your attention.

If this test remains genuinely ambiguous, place the fork under Needs your attention rather than infer delegation from silence.

Do not show rejected candidates to the author. A technical or observable difference alone does not make the branches different changes. Engineering preference is not an explicit constraint.

Propose a shared guarantee only when it is needed to make approved direction coherent or its absence would leave a reasonable, materially different version of the requested change. A guarantee that merely prevents a possible implementation defect remains ordinary implementation and review work.

A threshold, time window, or limit follows the same admission rule as any fork. Ask the author only when choosing among reasonable values would decide which change is delivered. If every reasonable value is a way to deliver the approved change, leave it to implementation or state a bound supplied by approved direction or an explicit constraint; do not manufacture a range merely to make the intent look complete. A production-only operating bound can remain a constraint: record it precisely enough to guide engineering judgment, but do not ask the author to invent proof that implementation or review cannot obtain.

**Items under `Needs your attention` are written for an author who cannot read the code.** Before emitting each one, apply the test: *could the author rule from this entry alone, without opening a single file?* If not, rewrite it. Behavior consequences come before mechanisms; affected parties are named in product terms ("signups would intermittently fail"), with the code reference as evidence, not prerequisite.

Before presenting the proposal, map every outcome, claim, constraint, and exclusion to confirmed author direction, an applicable project instruction or explicit normative contract, or an item under `Needs your attention`. Any normative wording you introduced must appear under `Needs your attention` and map unambiguously to the tagged draft.

Code, tests, and conventions may motivate a recommendation, but they are not a source of forward-looking direction. A source tag covers only what its cited direction entails: if the author could keep the cited direction while rejecting added specificity, that specificity requires approval under `Needs your attention`. An existing test or current behavior does not become project direction merely because it is verified. Keep code-only facts out of the normative draft.

---

## Phase 4 — Discuss, tighten, approve

The author may respond to individual items or approve the proposal as a whole. Do not require item-by-item confirmation when the complete proposal is approved. "Approve except Item 2" approves everything else and leaves only that item open.

Apply the author's rulings as **targeted semantic diffs**: "Item 1: AC 3 becomes <new text>." Re-emit the full file only when the author asks or when several changes make a partial update difficult to follow. If a ruling adds behavior the proposal did not describe, state the resulting claim changes and obtain explicit approval before continuing.

Before offering the file for approval, reread every claim and constraint as written, not as intended — the way an implementer who never heard this conversation will read it. Check for contradictions, unfalsifiable claims, missing change-defining decisions, constraints confused with proof obligations, and exclusions that defeat the outcomes. Every coverage limit must be resolved by supplied context, narrower scope, or an author-approved decision recorded as an outcome, claim, constraint, or exclusion. When you find a possible gap, run the admission rule before asking: a gap whose resolution decides which change will be delivered becomes a claim or explicit ruling; a silence under which every reasonable branch still delivers the approved change remains implementation latitude. Do not seek approval for technical completeness, enumerate every desirable invariant, or claim proof that no unknown dependency exists.

For each item under `Needs your attention`, compare its recommendation and
each alternative's draft effect against all confirmed author and project
direction. A resolution that conflicts with or narrows confirmed direction is
not a meaningful alternative unless the item explicitly proposes revising that
direction. State that tension in the item and make each remaining draft effect
internally consistent before offering approval.

For every Acceptance criterion and Invariant, identify both the author, project, or approved-item direction it supports and the distinct failure that would go undetected if the item were removed. Remove or merge an item when it has no such source or catches no distinct failure. An existing test, applicable quality category, or possible implementation defect is not by itself a reason to add a claim.

At approval:

- **Strip the proposal scaffolding.** Source tags and section wrappers go; approved item consequences are already embodied in the clean draft.
- **Emit parked items** as one-line seeds the author can turn into future intents.

Approval is explicit. Present the final file and state what it means: implementation must honor its change-defining decisions, may choose ordinary implementation details, and may repair a false claim or missing necessary decision through recorded amendments, which the author rules on when the work comes back. For an initial intent, write `change-intent/YYYY-MM-DD-short-slug.md` — today's date; a short, concrete slug at commit-title specificity, normally 3–6 words, using nouns about what changes rather than vague verbs about effort — and commit it before implementation begins. Use the shortest slug that clearly identifies the change; exceeding six words is not by itself a reason to stop or split. Offer to split the work when it requires independently deliverable intents. For a replacement, write the clean approved baseline at the existing path, remove the superseded candidate's Amendments section, and tell the implementing agent to reassess retained code and redo affected evidence before review runs again.

If the author abandons at any point, write nothing. There is no half-approved intent.

---

## The change intent file format

```markdown
# Change intent: <title — the change in one line>

## Outcomes
- <what the change is intended to make true — an outcome, not the
  implementation>

## Why
<prose paragraphs>

## Constraints
- <one condition or non-behavioral boundary every acceptable implementation
  must be designed around>

## Acceptance criteria
- <one falsifiable scenario per bullet>

## Invariants
- <one property per bullet, with enough context to understand its intended
  reach; do not list every location or test>

## Out of scope
- **<Excluded item>.** <What was considered, and why it stays out.>

## Amendments
- **A<N> — <YYYY-MM-DD>.** <the discovered fact that forced the repair>
  - Was — <section>: <verbatim previous item>
  - Now — <section>: <verbatim current item>
```

Rules:

- Section headings exactly as above, in this order. The file carries these sections and nothing else — do not invent metadata (status fields, author lines, PR links).
- A section with nothing to hold is omitted (Outcomes and Why always have something to hold). This deliberately differs from the proposal wrapper: the proposal shows every heading because a missing heading is indistinguishable from a skipped step; in the final file, absence is meaningful — an absent Amendments section means the current approved baseline held as written during implementation.
- Amendments is absent from an initial or replacement baseline. It appears only if implementation amends that baseline. Each entry has a unique local identifier (`A1`, `A2`, ...), states the discovered fact, and quotes the complete affected item wording verbatim with its section under `Was` and `Now`. Use `Was: not present` for an addition and `Now: removed` for a removal. A move names different sections. One discovery may contain several `Was`/`Now` pairs.
- The current body must be complete without Amendments. Do not put amendment identifiers or discovery notes beside current items. If the same item changes more than once, one amendment's `Now` is the next amendment's `Was`; only the terminal `Now` must match the current body. A replacement clears the superseded candidate's Amendments section and restarts local amendment numbering.
