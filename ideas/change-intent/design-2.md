# Change Intent: Design

**Draft.** This file is the proposed restructuring of [design.md](design.md) — the reading-order plan, the repetition cuts, and the voice pass from [editing-pass.md](editing-pass.md) applied together so the result can be read whole. The current design.md remains authoritative until this draft replaces it.

---

## Overview

A **change intent** is a durable per-change artifact and the lightweight, cooperative workflow contract around it. The artifact records what a change is meant to make true and the boundaries that govern it. The contract is a small common shape: the intent's initial form is approved before implementation begins, implementation works from that direction, and review assesses the resulting change against it. Beyond that shape, the design fits within a team's existing structure and practices: teams keep substantial latitude over who or what fills each role, how the roles integrate with existing development practices, where evidence and findings live, and how review results affect merge decisions.

Change intent serves five purposes, and each one shapes the design:

1. **The author gets clarity.** Stating what a change must make true — before any code exists to pull thinking toward it — exposes where that thinking is still vague. This got harder with AI, not easier: direction that used to be sharpened by the labor of implementation now has to be worked out deliberately, before the work starts.

2. **AI gets a goal to work toward.** An approved intent is specific about what the change is and what must hold for it to be done — exactly what a coding agent's goal mechanism needs to drive implementation without being re-prompted turn by turn.

3. **The human reviewer gets consistency.** With AI adoption uneven across a team, changes arrive developed in ways that vary by teammate, tool, and day. When every change passes through the same authored, implemented, reviewed frame, the reviewer can trust the process and give their judgment to the change itself.

4. **Future agents get the context.** The reasoning behind a change used to die with the pull request, because no future human would dig it up. Future AI agents will — reading history costs them nothing, and they act on what they find — so the most valuable parts of the pre-code dialogue are worth saving into the repository.

5. **The design points forward.** Every role is a responsibility, not a job title, so the same artifact and contract keep working as humans author less and review less.

These purposes are also the bar for changing this design: a modification is accepted only when it serves at least one of them **and** adds no required step, wait, or artifact for the team.

This document argues from the most immediate payoff: constructing changes so that they are **reviewable**. By the time a change reaches a human reviewer, design intent has already driven the implementation and informed an automated review assessment, so the reviewer's attention can go to the judgment question — *is this the right change?* Today that means reviewing better; over time, it means reviewing less.

The document runs in the order the ideas are used: the problem, the principles, the test that decides what belongs in an intent, the intent file itself, the life of a change from authoring through merge, a worked example, and the open questions. The operational instruments that carry the process into a project — an agents-file block, the authoring skill, implementation guidance, and review guidance — live in [mechanics/](mechanics/README.md): this document makes the argument; those files make it runnable.

---

## The Problem This Tries to Solve

AI generates code far faster than humans can review it. A competent engineer with a good model produces thousands of lines a day; human review is sequential, attention-limited, and scales roughly linearly. Humans are the bottleneck on shipping changes today, and the bottleneck will only tighten — code generation keeps accelerating while reviewer throughput stays roughly flat. The squeeze is the same on a team of two as on a team of twenty: the question is no longer how much code the team can write, but how much the team can effectively review. This work designs a change process that optimizes for the humans still in the loop today, and gets better as the AI in the loop gets better.

Just as autonomous vehicles will eventually drive themselves and we'll think nothing of it, code review will eventually be done by AI and we'll think nothing of that either. The point of a good process today is to walk us toward that future smoothly — more AI, less human, comfort accumulating along the way.

Until we're there, change intent addresses several failure modes of today's review process:

1. **Post-facto rationalization.** PR descriptions are written *after* the change is made. In the age of AI code generation, they're often just a summary of what the AI produced — and an AI reviewer can derive that summary from the code itself, so the description carries little information the reviewer doesn't already have. And because descriptions are written after, they get shaped to fit the change the author ended up with, covering what the code does but not what was intended before starting or wasn't considered along the way. Either way, reviewers get little evidence about whether design intent actually drove the change. Change intent inverts the direction: the initial intent is approved before implementation, and every implementation and review pass works against the current intent.

2. **Unconsidered cases.** Most production bugs aren't "I thought X would happen and Y happened." They're "I didn't think about case Z, and the code now does something weird in case Z." The initial pre-code dialogue forces the author and the AI to walk through use cases the change will touch, revealing unconsidered ones before implementation begins. Returned work may later give the author reason to revise that intent, but it does not remove the value of making the first direction explicit before code starts shaping it.

3. **Unverifiable claims.** Vague claims like "faster" or "more secure" are too abstract to use cleanly downstream — the implementation agent can't satisfy them (faster than what?) and the AI review pass can't assess them (measured how?). The review pass doesn't know a change's intent on its own; it sees the intent, diff, tests, and repository. Change intent makes each claim specific enough that the review pass can report `met`, `not met`, or `cannot verify` from those inputs. Falsifiability is what makes that assessment possible.

4. **Lost context.** Commit messages are too compressed to carry the full intent of a change; they're a summary, not a record. Change intent preserves why this pull request was needed, what change was approved, and the boundaries used for implementation and review. It remains a record of this change after merge, without becoming a requirement for later changes.

5. **Conflation of multiple tasks.** Human reviewers today are nominally doing four jobs at once:

    - Deciding whether this is the right change to make
    - Deciding whether the implementation is the right one for that change
    - Verifying correctness — the code does what it claims
    - Verifying clarity — the code is understandable

    Today, teams are most likely to reserve the first for human judgment. The other three are increasingly within reach of AI, and change intent accelerates that handoff: with explicit intent in hand, the AI review pass has what it needs to verify the implementation, correctness, and clarity against a stated target. Human attention can concentrate on the judgment task where teams currently need it most, while the human role in the other three recedes naturally as AI improves.

---

## Design principles

Five principles govern this design.

**Used beats better.** A process only pays off if the team actually runs it, so the bar to start is as low as we can make it: the project's agents file explains what change intents are, the coding and review agents are made intent-aware, and what we ask of a teammate is one sentence — run the change-intent skill instead of the coding tool's built-in plan mode. Change intent works through activities teams already perform: planning, implementation, testing, and review. It improves those activities by giving implementation and review the same approved intent. The optimization target is lower end-to-end friction and cycle time, not maximum procedural assurance. A short up-front clarification is worthwhile when it prevents implementation and review churn; the process should reveal genuine missing direction rather than create waits whose only purpose is demonstrating process compliance. Mechanically stronger ideas exist — structural coverage over the intent's tests, per-routine contracts, machine-checked proofs — and they are stronger precisely because they demand more: team effort, specific languages, dedicated tooling. When strength and adoption pull in different directions, this design sides with adoption.

**Diligence to agents, judgment to humans.** Rigor is cheap for an agent and expensive for a human. The agents carry the mechanical work in this design: the authoring skill reads the affected code and runs the authoring dialogue, the implementation agent writes the tests and reasons across the affected change for each invariant, and the review agent checks the diff against the intent and any amendments. In the current reference workflow, the human supplies judgment: they author the intent, they rule on any amendment when the work returns, and they decide at merge whether the change was the right one. These are logical responsibilities; teams may map them to people and agents in ways compatible with their practices, and future agents may take over roles held by humans today.

**Every claim is falsifiable.** An acceptance criterion can be refuted by a test; an invariant can be refuted by reasoning over the diff. Anything the pipeline is asked to verify has to be specific enough to fail. Outcomes and constraints are not claims: they orient and bound engineering judgment without promising proof that the available environment cannot provide.

**No adversary.** This is a workflow teams adopt for their own benefit, not a control imposed on them, so the design assumes cooperative actors. The pipeline checks compliance — agents check other agents' work at every stage — but it does not try to prove it: the authoring date and initial approval timing are self-reported, and the Amendments section is a plain record rather than an audit trail. The checks catch mistakes, not forgery. Proof would defend against a bad actor the design assumes away, and charge for that defense in adoption cost — the used-beats-better tradeoff again, decided the same way. Gaming the process is easy and pointless: its only output is review quality for the team running it. The record a change carries is therefore kept by cooperation around a shared intent — continuity through the team's existing workflow, not mechanically verified provenance.

**Every role has a defined path forward.** The process assigns an action to each unresolved condition: authoring may ask the author for a decision, implementation may repair a provably wrong claim on the record, and review may report `cannot verify` rather than manufacture a verdict. The process stops only when no repair can preserve the **approved boundaries** — the current intent's outcomes, constraints, and exclusions, together with applicable project instructions. The full table of situations and paths closes [the lifecycle chapter](#every-role-has-a-path-forward), where each entry can be read with the concepts it names already in hand.

---

## What belongs in an intent: the change-defining test

An intent must be **complete over change-defining decisions and open over implementation**: it records the outcomes, guarantees, constraints, and exclusions that distinguish the change, without prescribing every technical choice or incidental effect. One test decides which side of that line a choice falls on.

A fork is change-defining only when choosing between its options decides *which change will be delivered*. Ask whether the author could approve the change once and allow implementation to take either option while still receiving the change they approved. Apply that question to the options' consequences for author-owned direction — intended outcomes; material behavior or guarantees for users, callers, operators, or downstream systems; explicit engineering boundaries; and conscious exclusions — not merely to their mechanisms. If either option still delivers that direction, the fork is implementation latitude. If one option changes it, the intent must settle the choice. A reasonable option is supported by the affected system and the normal scope of the change, not merely imaginable. A technical or observable difference alone does not make a decision change-defining; ordinary engineering and review still apply.

```text
Do the options decide which change will be delivered?
├─ no  → different implementations of the same change: implementation latitude
└─ yes → is the choice already settled by the approved intent?
         ├─ yes → apply it
         └─ no  → authoring: ask the author
                  implementation: amend on the record and continue
                  review: report a finding
```

The same test runs in every role. Authoring asks the author to settle the unresolved change-defining forks it finds; implementation amends when it discovers one the intent missed; review checks the finished change for one that was decided silently.

---

## The intent file

A change intent file is a per-change document whose initial form is approved **before implementation begins**. It identifies the approved change precisely while leaving open the technical choices that are different ways to deliver it. Completeness is a quality standard for the artifact and the authoring process, not a claim that no unknown dependency exists. Each pull request carries exactly one current intent file; implementation may amend it and the author may replace it before merge, both under rules [the lifecycle chapter](#the-lifecycle-of-a-change) defines.

`Outcomes` and `Why` apply to every change. `Constraints`, `Acceptance criteria`, `Invariants`, `Out of scope`, and `Amendments` apply under the conditions described below; an omitted section means its condition does not apply.

### Outcomes

A short list of what the change is intended to make true. Each entry is an outcome — the result the author wants from the change — not the implementation chosen to produce it. "Database load from GetPlaylist drops by roughly 70%" is an outcome; "add a cache" is not, unless the cache is itself the deliberate outcome — which is exactly the case for changes that are mechanical by nature (a migration, a rename: "playlist artwork is served as WebP"). Take care not to smuggle an implementation choice into the outcome as an unnecessary constraint; when the author deliberately requires an approach ("must use the existing CacheManager"), record it under `Constraints`.

Outcomes may be individually testable or not, and both belong here. "GetPlaylist reports the playlist's total duration" is provable by a test; "database load drops by half" is observable only in production, long after review. This section doesn't promise proof — the claims below do that. It records the *intended* outcome: what the author meant the change to accomplish, and the standard the reviewer judges the claims against — do these acceptance criteria and invariants plausibly deliver these outcomes? Intent and achievement can diverge: a change can merge having proven every claim and still miss its outcome. Recording what was intended is what lets a future reader see that divergence plainly, instead of reading the result as if it had been the goal.

### Why

A short prose explanation of the problem, event, or need that caused the change to be made. Include the context necessary to understand why the outcomes matter and why the change is being made. Requirements and implementation direction live in the sections that define them; nothing is binding merely because it appears in `Why`.

### Constraints

Conditions and non-behavioral boundaries that every acceptable implementation must be designed around. A constraint can prohibit an otherwise reasonable implementation choice, establish an operating condition the design must account for, or require an approach for a non-behavioral reason. It is included only when the author's direction or an explicit project instruction supplies the boundary; engineering preference is not a constraint.

Constraints guide and bound engineering judgment; they are not automatically proof obligations. Some are directly checkable in the diff, such as "do not add a third-party runtime dependency." Others can be assessed only through engineering judgment before production, such as "the design must account for sustained production traffic of 40,000 `GetPlaylist` requests per second at evening listening peak." Lack of proof is not a violation. Implementation and review act on affirmative evidence that the change conflicts with a constraint, and otherwise use the constraint to guide their assessment without manufacturing a test, amendment, or definitive verdict.

An environment-dependent target is an outcome when achieving it is the purpose of the change and a constraint when it is an operating boundary the change must preserve or account for. It can be both important and unprovable before production; that does not move it into an acceptance criterion. If implementation discovers an actual conflict, it changes the implementation. If no reasonable in-scope implementation can honor the constraint, it reports a failed change rather than weakening an approved boundary.

### Acceptance criteria

A list of falsifiable scenarios that must hold for the change to be **accepted**. Each one proves a selected outcome, guarantee, guardrail, or decision through specific behavior — what a caller, user, or operator can do or see after the change ships. Each AC must have a focused proving test in principle (unit, integration, or one-shot measurement), but the test is not named during authoring. The implementation agent writes the test as part of the work and reports its result during implementation.

This is what authors usually have pre-code — "a listener renames a playlist and sees the new name," "`trackCount` appears in the `GetPlaylist` response," "when a playlist fetch fails, the `playlist_fetch_errors` metric is emitted." Each AC is a focused scenario.

**ACs are proof obligations, not an exhaustive behavioral specification.** Each independent decision should have an identifiable proof path, but it does not require a separate AC. One realistic scenario may prove several decisions when each is asserted distinctly and a failure remains diagnosable. Variants may share an AC when one assertion structure can falsify the same claim for each variant. Branches should not be combined solely because they share an implementation helper, and a claim should not be split solely because its implementation affects several observable surfaces. Project defaults and incidental implementation effects remain ordinary engineering and review concerns.

The list is forward-looking. It states what the change establishes or demonstrates, not a catalog of existing behavior. If a behavior is already true and your change isn't adding or altering it, it doesn't belong here.

**Each AC must be provable by a test that ships with the diff.** If there's no integration test, unit test, or one-shot measurement that can be run against the change to demonstrate the claim, it doesn't belong here. "Cache hit rate exceeds 60% in production," for example, can't be verified at change time — production isn't running the diff when the review happens. A statement like that is an outcome or a constraint, as the Constraints section classifies them; neither classification manufactures a proof obligation.

**Examples of falsifiable acceptance criteria:**

Functional behavior:
- "When `UpdatePlaylist` renames a playlist, a subsequent `GetPlaylist` for that playlist returns the new name"
- "`DELETE /playlists/{id}` returns 204 on success; a subsequent `GET /playlists/{id}` returns 404"

Observability:
- "When `GET /playlists/{id}` returns a 500, the `playlist_fetch_errors` metric is incremented"
- "When a track is added to a collaborative playlist, an activity entry is written with the acting user's identity"

Schema / response shape:
- "`GetPlaylist` response includes the playlist's track count as a top-level integer field"

These are all provable by integration or unit tests; none depend on production traffic.

**Examples of claims that should be rejected:**

Too abstract — what would it even mean to uphold these?
- "GetPlaylist is faster" — faster than what, in what scenario, by how much
- "The cache is correct" — correct in what sense

Concrete but not provable by a test that ships with the diff:
- "Cache hit rate exceeds 60% under production traffic over a rolling 24h window" — specific, but observable only after deployment
- "GetPlaylist p95 latency drops below 10ms under 1000 RPS" — specific, but requires production-scale load to verify

Statements in the second category belong in `Outcomes` or `Constraints`; they do not belong in the AC list.

#### Performance acceptance criteria

Most changes don't have performance ACs, and shouldn't. The default position is: the change is accepted under the project's general performance characteristics, and if performance regresses elsewhere, monitoring and load testing will surface it.

Include a performance AC only when **both** conditions hold:

1. The change is **performance-constrained** — performance is the reason for the change, or a specific bound is a hard requirement.
2. The measurement is **environment-independent** — it produces the same answer regardless of machine, OS, or concurrent load.

Memory allocation, allocation count, database-query count, network-call count, and algorithmic complexity (operations as a function of input size) are environment-independent and make good benchmark-style ACs. Wall-clock latency, throughput, and percentile latencies under load are environment-dependent and don't — they need different verification paths (staging load tests, production monitoring, perf regression suites), not focused proving-test ACs.

**Examples of good performance ACs:**
- "A single `GetPlaylist` call makes at most two database queries, regardless of the playlist's track count"
- "At most 10 concurrent imports can be in-flight through `ImportPlaylist` at any given moment — useful for verifying bulkhead or rate-limiter patterns"

**Examples of performance claims that aren't good ACs:**
- "GetPlaylist returns in under 10ms" — depends on machine, DB connection, concurrent load
- "Throughput exceeds 1000 req/s" — depends on hardware, parallelism, network

An environment-dependent performance bound is recorded as an outcome or constraint, and the team's normal performance systems provide whatever evidence they can. The authoring process does not design that verification, and implementation and review do not owe proof their environments cannot establish.

### Invariants

A list of properties that must remain true across the parts of the system affected by the change. Their full obligation cannot be closed by test evidence alone, because implementation and review must also reason across the affected change. Read-after-write consistency across callers, availability under failure, audit-log-on-every-mutation, and thread safety across access paths are all typical invariants.

Tests should exercise an invariant where useful, but passing tests do not close it by themselves. The implementation agent must also reason across the affected diff and relevant surrounding paths; the AI review pass independently applies the same property to the resulting change. Tests establish concrete cases, while the reasoning addresses the property across the change.

The intent states the property in plain language, not every location where it applies and not every test that might exercise it. Discovering the relevant locations and choosing useful tests are implementation and review responsibilities.

Authoring does not attempt to enumerate every desirable invariant of the system. Include an invariant when it is part of the change the author is approving and its obligation extends beyond a focused acceptance scenario. Ordinary correctness, security, concurrency, and quality concerns remain part of implementation and review even when they are not written as intent invariants. The section may therefore be small or absent when acceptance criteria capture the approved change.

**Examples of invariants:**
- "Read-after-write: a track added via `UpdatePlaylist` is visible to `GetPlaylist` across all caller paths, within the staleness window"
- "Every mutation of a collaborative playlist writes an activity entry with the acting user's identity"
- "The cache layer is safe for concurrent reads and writes from multiple callers, across all access paths added by this change"
- "If the cache backend is unreachable, every code path that reads through the cache falls back to the database without surfacing the failure to callers"

Note the pattern: each states one property whose scope extends beyond a single proving test, naming that scope as a rule rather than inventorying the files, callers, branches, or tests that implementation must inspect.

### Out of scope

A list of things this change explicitly is *not* doing — work the author considered but intentionally left out. Without this section, the diff alone can't tell a reader whether something was thought about and excluded, or just never considered. Out of scope captures that distinction, making intentional exclusion visible the same way the diff makes intentional inclusion visible.

What it does:

- **Signals to the author at initial authoring time.** Writing an out-of-scope item often prompts "wait, should this actually be in scope?" That reflection happens before implementation begins — before implementation starts to bias the author's view of what the change should be.
- **Signals to the implementation agent.** These areas are excluded from the goal, so the agent doesn't drift into them while satisfying the ACs and invariants.
- **Signals to the AI review pass.** Items listed here were a conscious choice, not an oversight. The review pass doesn't flag the absence of an out-of-scope item as a defect.
- **Signals to the human reviewer.** If a related item is missing from this list and the reviewer would expect it to be considered, that's a question to ask — the author may not have thought about it.

Out-of-scope items are typically multi-sentence — enough to convey what was considered and why it was excluded. Examples:

- **Distributed cache coordination.** Single-node cache only for now. Cross-node consistency would require a separate design and a measurable need we don't yet have.

- **Cache eviction policy customization.** The library defaults work for current access patterns. We can add hooks for customization later as specific callers need different policies.

- **A batch `GetPlaylists` endpoint.** Considered but deferred. The home screen would benefit from fetching a listener's playlists in one call to reduce round-trips, but the access model for batch requests — owned, collaborative, and followed playlists mixed — needs its own design. A follow-up PR will deliver it once that approach is settled.

Each item is something the author thought about and explicitly excluded. Note the third example: an out-of-scope item can flag work the author has explicitly deferred. That signals to the reviewer that more work is coming, and gives a later reader the ability to check whether the follow-up actually landed.

A prohibition can sit in either this section or Constraints; the test is what it governs. It is a constraint when it bounds how this change's included work is built ("do not add a third-party runtime dependency"). It is out of scope when it excludes work or an outcome the change could otherwise have delivered ("distributed cache coordination — single-node only for now").

**Why no dedicated Alternatives or Risks sections?** The file records what was decided. An alternative that was not chosen drives nothing downstream — implementation does not build it, review does not check against it, and it is not evidence for why the change was made. A genuinely alternative *intent* is rare: when the author's direction truly changes, the intent is replaced, and only the merged intent is the record. What an Alternatives section actually collects is alternative *implementations* — exactly the detail an intent deliberately leaves open. Alternatives may still appear temporarily while the author makes a decision; the final file keeps only the selected consequence, under Outcomes, Constraints, Acceptance criteria, Invariants, or Out of scope, and rejected alternatives do not move into `Why`.

Risks pull the same direction: most risks are implementation risks, and listing them describes an implementation rather than an intent. A risk belongs in the file only when it changes what the author is approving — and then it is already expressible as an acceptance criterion, an invariant, or a constraint. Those sections bound the change's alternatives and risks exactly as far as they define the intent, which is as far as the file should go. Other risks remain part of ordinary implementation and review rather than becoming an author-provided checklist.

### Amendments

A dated record of repairs made during implementation — present only when a claim proved wrong or a necessary change-defining decision surfaced after approval. Most intents never get one; an absent Amendments section means the current intent held as written. The current intent must remain complete and understandable without this section, which exists only for a reader who wants to see what implementation changed from the approved wording. The rules and record format are part of the implementation stage, described in [Amending the intent](#amending-the-intent).

### File location and naming

Intent files live in a `change-intent/` folder at the repository root. Each file is named:

```
YYYY-MM-DD-short-slug.md
```

Where `YYYY-MM-DD` is the date the intent was authored and `short-slug` is a kebab-case description of the change. Examples:

```
change-intent/2026-05-16-add-getplaylist-cache.md
change-intent/2026-05-22-migrate-artwork-to-webp.md
change-intent/2026-06-03-fix-offline-sync-timeout.md
```

Two choices are wrapped up here. The date comes first so the folder is scannable in time order: sorting by name gives sorting by time, and the date — the authoring date, set at file creation — never changes through review, merge, or squash. The slug is short, concrete, and required up front: normally three to six words at commit-title specificity, using nouns about what changes rather than vague verbs about effort — `add-getplaylist-cache`, not `playlist-improvements`. Slug length is naming guidance, not a scope test; work that contains independently deliverable changes should be split, with a separate intent for each.

Once its change merges, an intent file is frozen — never edited, never renamed, never deleted; it is a historical record of its own change, never a requirement on later ones. Before merge, the current intent governs implementation and review; implementation may amend it and the author may replace it, under the rules in [the lifecycle chapter](#the-lifecycle-of-a-change). Follow-up changes to the same area get their own file with their own date and slug; the date prefix makes the lineage visible without making earlier intents govern later changes.

---

## The lifecycle of a change

The minimal flow is **author → implement → review → merge**. The arrows express dependencies among responsibilities, not a required team structure or tool pipeline. Teams may assign the roles to the same or different people and agents, and add integrations, as long as the common contract holds: direction is explicit before implementation, implementation uses the current intent as its goal and decision boundary — the line around what has already been decided — and review assesses the resulting change against it before merge.

What travels between the stages is deliberately minimal: the intent file and the change itself — the diff and its tests. A team may carry more evidence forward; the design leaves how review reads, runs, or otherwise examines the change to the team.

### Authoring

**Writing it down forces clarity.** The moment you try to state precisely what must hold, you discover where your thinking is fuzzy. Most software bugs aren't reasoning errors; they're cases the author didn't consider. Articulating acceptance criteria and invariants explicitly brings those cases to light at the cheapest possible time, before the code exists.

**Approval gives implementation a direction before it starts.** Once the initial intent is approved, downstream agents work in narrower modes: the implementation agent decides *how* to satisfy it, and review checks *whether the finished change honors it*. This split separates the two tasks that ordinary code review conflates — deciding what should be true, which is high-judgment work, and verifying that code matches it, which is mostly mechanical — so each is done by the right participant at the right time.

The intent is produced through a structured dialogue between the author and an authoring skill. **The author owns direction** — what the change is, why it is needed, what it must and must not do. **The skill owns the map** — the code as it exists today, which the author may not know at all, especially where agents wrote it. The author speaks in outcomes and plain-language boundaries; the skill translates testable behavior into falsifiable claims and preserves genuine engineering boundaries as constraints. One constraint on the skill is critical: it drafts the artifact but does not decide change-defining questions. It may propose direction the author did not state, but every proposal identifies its source, every settled change-defining fork cites the approved direction or explicit constraint that settled it, and every remaining fork is presented to the author as an explicit decision. Repository contents establish facts about the current system; they do not independently decide what the change should be.

The dialogue runs four phases: a short brief the author confirms before any exploration is spent — a cheap gate, and the place a misreading of the author's direction gets caught; an exploration of the affected code, with each fact marked by the confidence it deserves; one proposed intent, with the remaining change-defining decisions batched for the author in plain product terms; and discussion ending in explicit approval of the assembled file, which is committed on the change's branch before implementation begins. The dialogue is done when every open decision has the author's ruling, every claim is falsifiable, every gap in what could be explored is resolved, and the author approves. The full procedure, including the failure modes it defends against, is [mechanics/authoring-skill.md](mechanics/authoring-skill.md).

Intent size follows the number and scope of change-defining decisions, not diff size and not how casually the author stated the request. A one-line fix can require a substantial intent when it changes a security boundary or caller guarantee; a broad internal refactor may require few claims when its alternatives are different ways to deliver the same change. The file is never expanded to create an appearance of thoroughness.

**When exploration comes first.** Not all work results in a change: a toy, a prototype, exploratory testing — work that is not intended to merge needs no intent, and this design proposes no process for it. Change intent picks up when the author decides to ship: shipping is a change, its initial intent is authored and approved first, and everything that merges — including any prototype code the author keeps — is implemented and reviewed against it. In this design, implementation means that shipping work; a prototype that preceded the intent is exploration, not implementation begun early.

### Implementation

An approved intent is a completion condition an agent can drive toward. Claude Code's `/goal`, shipped in v2.1.139 ([official documentation](https://code.claude.com/docs/en/goal)), is the reference integration: the user sets a completion condition, and the agent keeps working across turns until a separate evaluator model — which reads only what the agent has surfaced in the conversation and cannot run commands itself — judges the condition met. A change intent slots in naturally: the acceptance criteria and invariants are the proof obligations, and the constraints bound the engineering judgment used to satisfy them.

Working against the intent means demonstrating, not just doing:

- **For each acceptance criterion**: write a test that exercises the scenario, run it, and show the passing result. Then temporarily make the criterion's defining condition false — a reversible product change, or a controlled configuration or dependency negative control when that is unsafe — show the test failing for the expected, claim-specific reason, restore the temporary state, and show the test passing again. One falsification may support multiple criteria only when each criterion's own proving test fails on its own claim. The test is the agent's own work; the intent never named it. This would-fail demonstration exists because the agent writes both the code and the tests used to accept it: a test that cannot fail when its claim is false proves nothing.
- **For each invariant**: add tests for concrete cases where they provide useful protection, then reason across the affected diff and relevant surrounding paths — passing tests do not close an invariant by themselves. Show the analysis and any material uncertainty.
- **For each constraint**: account for it in the implementation. Check it directly when the diff permits; otherwise use it as an engineering boundary. The agent does not owe proof of a production-only condition; it acts when affirmative evidence shows a conflict.
- **If the intent proves wrong or incomplete**: amend it on the record, under the rules of the next section, and keep working.

The in-loop evaluator checks the conversation for the passing tests, the would-fail demonstrations, the invariant reasoning, and any known conflict with a constraint. It does not demand proof that an unavailable environment cannot provide. This is the only stage required to verify the would-fail evidence directly; review, next, has a different role and different inputs. The full procedure is [mechanics/implementation-guidance.md](mechanics/implementation-guidance.md).

### Amending the intent

Approving the initial intent before implementation does not require the author to know every implementation fact in advance. Implementation may expose an incorrect claim or a missing decision. The implementation agent can repair the current intent through a narrow amendment — and only through it; after merge, the intent is frozen history.

**The necessity test.** The amendment process corrects an inaccurate or decision-incomplete intent; it is not an implementation log or an escape from a difficult implementation. Exactly two conditions permit an amendment:

1. **A claim cannot be delivered within the approved boundaries.** Facts discovered during implementation show that no reasonable implementation can make an acceptance criterion or invariant hold without violating the approved boundaries. Failure of the current approach is not enough: if another reasonable in-scope implementation can satisfy the claim, the agent changes the implementation rather than the intent. The amendment relaxes or replaces the claim only as far as the discovered fact requires.

    This condition also covers an acceptance criterion whose behavior can be delivered but cannot be proved by any reasonable test available to the change. An acceptance criterion promises a proving test that ships with the diff; when the behavior is real but that proof cannot be produced, the amendment rewords the criterion into a provable form without weakening its substance, or moves the statement to Outcomes or Constraints according to the role it plays. A constraint's lack of proof never triggers an amendment — constraints are not claims — and an invariant's need for reasoning beyond tests is its ordinary shape, not a trigger.

2. **A necessary change-defining decision is missing.** Implementation cannot complete without choosing which change will be delivered, and the current intent does not make that choice. A decision is not necessary merely because the selected implementation happens to expose a fork; if either reasonable option still delivers the approved change, the agent chooses an implementation without amending. A technical fork, incidental observable effect, better idea, or ordinary engineering tradeoff does not qualify by itself.

This is a bounded engineering test, not a proof of impossibility. A reasonable alternative is one supported by the current repository and the normal scope of the pull request, not a hypothetical redesign. Before amending, the agent names the plausible in-scope alternatives the work revealed; if one can satisfy the current intent, it uses that one. An amendment may repair a claim or settle a missing decision only while preserving the approved boundaries. If every reasonable in-scope resolution would violate one of them, the agent stops and reports a failed change.

When the second condition applies, the agent compares the reasonable in-scope resolutions in a fixed order: preserve the approved outcomes; honor explicit constraints and exclusions; preserve existing external behavior unless the intent changes it; minimize scope; prefer the more reversible resolution. It selects the first resolution distinguished by that order; if the full precedence leaves resolutions tied, it selects either, records that result, and continues. Every missing-decision amendment is a provisional implementation-time decision: it takes effect immediately for implementation and review, and the author rules on it when the work returns. Code, tests, documentation, and project instructions are evidence about the system and constraints the implementation must honor; none of them supplies new product direction. Amendment authority permits updating the current intent and continuing against it; it does not override applicable project instructions or expand the agent's operational permissions.

Everything else — better ideas, opportunistic hardening, adjacent fixes, "while we're in here" — is not an amendment. A discovery that would *improve* the change is a candidate for the next change intent: its own file, its own date and slug, its own decision. The pressure that would otherwise swell the amendment record gets redirected: the deferred idea is handed to the author as a named candidate for its own intent, instead of dying as a rejected request. An editorial correction that preserves a claim's meaning is not an amendment either; if wording is ambiguous enough to describe different changes, the problem is semantic and must pass the necessity test.

**Who amends: the agent, on the record.** Amendments are the exception, not a phase of every change — the authoring dialogue exists to make them rare, and most intents merge exactly as approved. The author is unlikely to ever write this file by hand: the authoring skill writes it during the dialogue, and the implementing agent repairs it during implementation. The repair path exists because an agent that discovers a wrong claim mid-implementation, with no sanctioned way to fix it, fails in predictable ways: it fabricates success, drifts past the problem silently, or stalls. Amendment preempts all three by sanctioning the correct move — change the claim, record what changed and the fact that forced it, keep working. Work on unaffected claims never stops.

The author still rules on every amendment — at review rather than mid-implementation. When the work comes back, accepting the current intent accepts all of its recorded amendments together; if the author wants different direction, they replace the intent (described under [human review](#human-review-return-and-merge)). No separate per-amendment approval step is required. Moving the ruling to review has a known cost: a repair the author would have decided differently is discovered after the work is done, not before. The design accepts that cost deliberately — rework is cheap for an agent, and stopping mid-implementation to wait on a decision is expensive for everyone — and states it here so a future reader doesn't reintroduce mid-implementation approval as a fix.

Implementation latitude does not need to be enumerated to be real: the intent may explicitly bound a choice ("TTL may be anywhere in 10–60s"), but the agent also owns unspecified choices whenever every reasonable option still delivers the approved change, and an amendment is never required merely to document an ordinary technical choice.

**The record.** A semantic amendment is two edits made together. First, update the current body — rewrite, add, remove, or move the affected item only as far as the discovered fact requires, so the body remains a complete account of the current intent on its own. Second, add an identified, dated entry under an `## Amendments` section at the end of the file, stating the discovered fact and quoting the affected item's previous and current wording verbatim with its section:

```markdown
- **A<N> — <DATE>.** <The discovered fact that forced the repair.>
  - Was — <Section>: <verbatim previous item>
  - Now — <Section>: <verbatim current item>
```

For an item's first addition, write `Was: not present`; for a removal, `Now: removed`; a move names the previous section under `Was` and the current one under `Now`. One discovery may contain several `Was`/`Now` pairs. A missing-decision entry also names the precedence rule that selected the resolution, or states that the precedence left the reasonable resolutions tied. The discovered fact must describe the system, not the agent's activity — something still true and checkable if the rest of the file were deleted: `Ran into implementation issues` fails; `SharingMiddleware caches access grants for 5m with no invalidation hook` passes. When a claim is weakened and its prior strength is deferred rather than abandoned, the body also gains the corresponding Out of scope item, quoted in the same amendment.

No amendment marker appears beside current items: a reader reads the body as the complete current intent, then reads Amendments only to see what implementation changed. If the same item changes more than once, the later entry's `Was` equals the earlier entry's `Now`, and only the terminal `Now` must match the body.

**Why amendments must stay rare.** The design depends on that rarity in three ways:

- **Every amendment is a decision made after code has begun shaping everyone's view.** Initial authoring is the moment before implementation starts doing that. Sometimes deciding late is unavoidable — reality falsified the plan, and deciding with better information is the process working — but it is never free. A process where amendments are routine is a process where deciding happens continuously during implementation: the pre-intent world, rebuilt with extra paperwork.
- **Rarity is what earns each amendment the author's full attention.** When amendments appear only on falsification, an Amendments section on a returned change is worth reading carefully. If amendments appeared for every nice-to-have, the author would learn to skim them — and a skimmed Amendments section tells the author nothing at all.
- **Amendment count becomes a diagnostic.** Every amendment marks a spot where the author, the authoring dialogue, and the exploration of the affected code all missed something that implementation then exposed. One or two entries is normal — implementation always turns up surprises. Six entries on a small change points at the authoring dialogue or at the code itself, and either way the signal is actionable: an area that accumulates amendments across changes has earned extra scrutiny in review, and a deeper authoring pass the next time a change touches it.

### AI review

After the goal clears, an AI review pass independently reviews the implementation with the change intent as context. What the reviewer can inspect or execute is defined by how the team runs review, not by change intent, and review does not depend on the implementation session: the reviewer assesses the diff, tests, repository, and intent with whatever evidence and capabilities its setup provides, using inference where direct implementation evidence is absent. It assesses four things:

1. **Is the intent itself well-described?** Are claims falsifiable, are the change-defining decisions complete, and are conscious exclusions clear? A vague or decision-incomplete intent is a defect; absence of implementation detail is not.

2. **Does the diff match the intent?** Every acceptance criterion must be exercised by a test whose assertions would detect the claimed behavior becoming false; the reviewer assesses that relationship between criterion, test, and implementation. For every invariant, the reviewer uses available tests and reasons across the affected diff and relevant surrounding paths — no passing test closes the property by itself. Constraints bound the reviewer's engineering judgment without each requiring a test or conclusive verdict. And in the reverse direction, the reviewer asks whether the diff selected which change to deliver where the current intent left that choice unresolved — the change-defining test again, run over the finished work. If every reasonable alternative would still deliver the approved change, the choice is implementation latitude and remains subject to ordinary review rather than an intent finding.

3. **Is any amendment eligible and coherent?** The reviewer applies the necessity test to each entry's discovered fact — difficulty with the chosen approach is not enough — checks that a missing-decision amendment applied the shared precedence, and verifies the record: verbatim `Was` and `Now`, explicit additions and removals, coherent chains, terminal `Now` matching the body. The reviewer does not reconstruct Git history to authenticate `Was`; the rule binds the implementing agent in this cooperative process. An ineligible or incoherent record is reported with the same severity as a `not met` acceptance criterion.

4. **Does the pull request conform to the intent folder's rules?** Exactly one current intent file: the intent for this change. The assessment is scoped to that file and this change; it does not compare against earlier intent files or other branches.

For each claim, the reviewer reports `met`, `not met`, or `cannot verify`. `Cannot verify` is a complete review result, not a successful verification: the available inputs establish neither `met` nor `not met`, and the team decides what that uncertainty means for the change.

The two machine roles are complementary. The in-loop goal evaluator sees the implementation conversation and judges whether the agent demonstrated completion; the review pass assesses the finished change independently. The review pass also keeps intent alignment and ordinary code review as distinct judgments: it uses the intent to assess the approved change, but never treats the intent's silence, exclusions, or decisions as an excuse for a defect in code the pull request ships. Neither role substitutes for the other. The full instructions are [mechanics/review-guidance.md](mechanics/review-guidance.md).

### Human review, return, and merge

By the time a change reaches human review, it has passed through the same sequence of recorded steps as every change: an approved intent, the implementation and its tests, a cleared implementation goal, any amendments, and an independent review assessment with its findings and limits. That continuity comes from cooperation within the team's existing workflow — it is not an audit trail, and nothing mechanically verifies it. What it gives the reviewer is a consistent frame for how AI participated in developing the change: what authoring decided, what implementation produced and demonstrated, and what review examined. Because every change arrives in the same frame, the team learns the strengths, weaknesses, and quirks of the AI in each role, and human attention goes where it is most valuable. A teammate's change arrives looking like the reviewer's own.

Amendments are the first thing in returned work to read carefully — provisional implementation-time decisions awaiting the author's ruling. Accepting the current intent accepts its recorded amendments together. The human reviewer then decides the question the process has been protecting all along: is this the right change to merge?

**Revision before merge.** The amendment process constrains the implementing agent; it does not prevent the author from changing direction after seeing returned implementation or review. When that happens, the author replaces the current unmerged intent and approves the replacement. The prior candidate is superseded rather than amended or archived: the replacement is a new approved baseline at the same path, relevant implementation discoveries are folded into its ordinary wording, and the superseded candidate's Amendments section is removed. Existing code may be retained where it satisfies the replacement, but affected implementation and evidence are reassessed before review runs again. At every point, implementation and review have exactly one current intent, and the process does not preserve or ask review to reconstruct the iterations that did not merge.

In the worked example below, the returned change might cause the author to require invalidating the cached entry on `UpdatePlaylist` rather than allowing PlaybackService to bypass the cache. The author replaces the current intent with that direction, approves it, and sends the change through implementation and review again. The merged intent describes the change that landed; it does not explain the superseded candidate.

At merge, the intent file freezes — the historical record described under [File location and naming](#file-location-and-naming).

### Every role has a path forward

Wherever a role meets an unresolved condition, the process assigns its next action — no role ever needs to fabricate, drift, or stall:

| Role and situation | Path forward |
| --- | --- |
| Authoring: a change-defining decision is unresolved | Ask the author, with concrete options and their effects on the intent |
| Authoring: the approved direction or an explicit constraint settles the choice | Apply it, cite its source, and continue |
| Authoring: a relevant part of the system cannot be examined or bounded with confidence | Name the blind spot and ask the author to supply context, narrow the change, or make an explicit decision that governs it |
| Implementation: the intent leaves a technical choice open | Choose using normal engineering judgment and continue |
| Implementation: a constraint cannot be proved in the available environment | Use it as a design boundary and continue; lack of proof is not a violation or amendment trigger |
| Implementation: a claim cannot be delivered within the approved boundaries, or a necessary change-defining decision is missing | Amend on the record and continue |
| Implementation: no repair can preserve the approved boundaries | Stop and report a failed change |
| Review: evidence cannot establish a claim | Report `cannot verify` and name the missing evidence |
| Review: the diff violates or silently changes a decision in this intent | Raise a finding; do not repair it in review |

---

## Worked Example

**The author's request:** "Add caching to PlaylistService.GetPlaylist to reduce database load."

**AI reads relevant code and finds:**
- `GetPlaylist(playlistID)` returns the playlist — its metadata and track list — or nil for playlists that don't exist
- Documented as safe for concurrent use
- Called by PlaybackService, SharingService, SearchIndexer, RecommendationService, and OfflineSyncService
- No existing cache in this service
- Similar caching pattern exists in `TrackCatalogService` using `CacheManager` interface

**The skill explores and proposes; the author rules on the open decisions.** The approved file at `change-intent/2026-05-16-add-getplaylist-cache.md`:

```markdown
# Change intent: Cache GetPlaylist reads

## Outcomes
- Database load from `GetPlaylist` reads drops by roughly 70% at current traffic.
- `GetPlaylist` P95 latency drops from ~80ms to under 10ms on repeated reads.
- PlaybackService has immediate read-after-write consistency.

## Why
GetPlaylist is read-heavy at 40k requests per second during evening peak
listening. Its P95 latency is 80ms, dominated by the database round-trip,
and these reads now account for most PlaylistService database load. Search
indexing, recommendations, share pages, and offline sync all tolerate a
briefly stale track list; playback does not — a song a listener just added
to a playlist must play when they tap it.

## Constraints
- The design must account for sustained production traffic of 40k requests
  per second at evening listening peak; this operating condition guides
  implementation and review but is not expected to be reproduced by a
  repository test.
- Use the existing CacheManager, the pattern TrackCatalogService already
  uses, rather than introducing a new caching primitive.

## Acceptance criteria
- On a cache hit, `GetPlaylist` returns the cached value without querying the database
- On a cache miss, the `cache_misses` counter is incremented; on a hit, `cache_hits` is incremented
- After `UpdatePlaylist` adds a track, PlaybackService's next read of that playlist includes the new track even if the ordinary `GetPlaylist` cache entry has not expired
- When `UpdatePlaylist` adds a track, a subsequent `GetPlaylist` for that playlist includes the new track within 30 seconds

## Invariants
- Read-after-write: across all caller paths through `GetPlaylist`, no caller sees a track list or metadata older than 30 seconds after an `UpdatePlaylist` or `DeletePlaylist` for that playlist
- The cache layer is safe for concurrent reads and writes from multiple callers, across all access paths added by this change
- If the cache backend is unreachable, every code path that reads through the cache falls back to the database without surfacing the failure to callers

## Out of scope
- **Distributed cache coordination.** Single-node cache only for now. Cross-node consistency would require a separate design and a measurable need we don't yet have.
- **Eviction policy customization.** CacheManager defaults (LRU with a 100k entry limit) are sufficient for the access patterns we've measured.
- **A dedicated API for cache inspection or invalidation.** Not included here. A follow-up PR will add inspection endpoints once production data shows whether on-demand invalidation is needed.
```

**A mid-implementation amendment.** While implementing the cache, the implementation agent hits a question the approved intent does not settle: `GetPlaylist` returns nil for playlists that do not exist — should negative results be cached? The authoring read recorded the nil-return fact, but the dialogue never carried it forward to the fork it creates: an authoring miss, of exactly the kind the amendment process exists to absorb without stalling the work. Caching nil would leave a playlist created immediately after a missing lookup invisible to `GetPlaylist` for up to the TTL — "playlist not found" on a playlist the listener just made; not caching negative results preserves existing immediate post-creation visibility. Those options deliver different changes rather than different implementations of the same change, and the approved intent does not choose between them. The shared precedence selects not caching negative results because it preserves existing external behavior. The intent gains one acceptance criterion and one amendment entry:

```markdown
## Acceptance criteria
- A `GetPlaylist` for a nonexistent playlist is never served from the cache:
  a playlist created immediately after a missing lookup is returned by the
  next `GetPlaylist` call.

## Amendments
- **A1 — 2026-05-19.** `GetPlaylist` returns nil for playlists that do not
  exist; caching those results would delay visibility of newly created
  playlists by up to the TTL. The preserve-existing-external-behavior rule
  selects keeping immediate post-creation visibility.
  - Was: not present
  - Now — Acceptance criteria: - A `GetPlaylist` for a nonexistent playlist
    is never served from the cache: a playlist created immediately after a
    missing lookup is returned by the next `GetPlaylist` call.
```

Implementation continues against the amended intent. At review, the intent author accepts the current candidate or replaces it and sends the change through implementation and review again.

The implementation agent takes this file as the `/goal` condition, producing the passing tests, would-fail demonstrations, and invariant reasoning described in the lifecycle chapter; the in-loop evaluator checks the conversation for that evidence. When the goal clears, the AI review pass assesses the diff against the intent — with particular scrutiny on the invariants, checking the whole diff against each one — runs the standard checks (concurrency, errors, security, clarity), and reports findings and anything it cannot verify. The change then reaches the human reviewer with that assessment.

---

## Design Tensions

A few areas where the design is not fully resolved and worth flagging for implementation. Premises and direction that lie outside the design — for example, the mechanism behind "reviewing less" — are recorded in [notes.md](notes.md).

### Decision completeness is diligent, not omniscient

The change-defining test can classify a decision only after the process discovers the relevant fork. Authoring and reverse review therefore inspect the affected code and settle every change-defining decision they find, but neither pass proves that no unknown dependency exists. "Complete over change-defining decisions" is a quality requirement: a decision that a diligent pass should have found is a defect when later discovered, not evidence that the process had to search without bound.

When authoring cannot examine a relevant part of the system or establish its limits with confidence, it exposes the specific blind spot to the author. The author supplies context, narrows the change, or makes a decision that governs the area and can be recorded as an outcome, claim, constraint, or exclusion. If none of those paths resolves the blind spot, the intent is not ready for approval. Review independently repeats the bounded decision check and may report `cannot verify` when its available view cannot support a conclusion. These paths preserve the completeness standard without encouraging manufactured decisions or indefinite exploration.

### Cold start on existing codebases

Existing codebases rarely document every property a change may affect. The author's direction and the AI's bounded read of the affected code may therefore miss a real interaction. The intent still records only the invariants that belong to the approved change; authoring does not compensate by inventorying every property or location in the system. The blind-spot path above handles known uncertainty, but it cannot expose a dependency that no available evidence reveals.

### Where the per-change value concentrates

The dialogue scales down with the change, but its two author gates do not scale to zero. The payoff a single change gets from its intent concentrates where the change carries a genuinely unsettled change-defining decision or a guarantee that crosses the code it touches. For a trivial change, the intent is carried instead by the purposes every change shares — the consistent frame the reviewer gets and the record the repository keeps. The design accepts that trade; it is stated here so adopters price it knowingly.

### Cross-cutting invariants

Some properties are system-wide ("every mutation of a collaborative playlist writes an activity entry with the acting user's identity"). A change intent includes such a property only when it is part of the change being approved, and states the property without requiring the author to enumerate every mutation site. Existing project-wide rules remain applicable through normal project instructions and ordinary implementation and review; this design does not require a separate registry before a team can use change intent.

### Method-level invariants are separate

This document covers only the macro layer — change-scoped and author-directed. There is a complementary system for method-level invariants: pedantic, AI-maintained annotations in doc comments paired with named tests, enforced by a linter, consumed by an AI-only reviewer. That system handles the micro layer. The two layers compose in the broader review pipeline but are designed independently. Method-level invariants are **out of scope** for this document and this skill.

---

## Where this is heading

**The intent author doesn't have to be a human.** The same workflow can support an AI orchestrator in the author role instead of a person. The orchestrator brings an upstream objective and operates within an authority boundary supplied by a human, product process, incident signal, policy, or broader program; the authoring skill brings the structure and rigor. The change-defining test is also the orchestrator's escalation rule: a fork that decides which change will be delivered goes up to whatever holds the authority boundary, and everything else is decided locally — the same discipline the test gives a human author's dialogue. The result is the same kind of change intent file ready for implementation, and the same responsibilities and shared decision artifact keep working as an orchestrator, implementation agents, and review agents fill the roles humans hold today. How the objective and authority are supplied remains part of the team's broader operating model.

**A change as a self-describing package.** A change is the package of the work that produced it — the intent, its decisions, its falsifiable claims, its constraints, and its consciously excluded scope — bundled with the code itself. An AI or future engineer should be able to open a single merged change and understand what change was intended, why it was needed, and which boundaries governed it. That is the deeper claim, and change intent is one expression of it, scoped to 2026 tools. What this looks like a year or two from now is probably different: code review may not use git as the substrate, and intent may be captured through richer interactions than markdown files. We don't have to be exactly right about the future to be right about the direction, because the asymmetry runs one way — information saved now can be reshaped into whatever future tooling needs; information that wasn't saved can't be reconstructed. The pattern seems likely to last: every change carrying its purpose, approved direction, and decision boundaries, retrievable indefinitely. The artifact will change; the goal of opening a change and understanding those decisions will not.

---

## Related

Change intent is one instance of a broader pattern this repository explores: [**working in public**](../working-in-public/README.md) — capturing the most valuable structured work between humans and AI in artifacts that persist for future agents and humans to reference, rather than letting it die with the context window it happened in. The merged change intent preserves the approved result of that dialogue beyond the session that produced it.
