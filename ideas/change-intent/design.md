# Change Intent: Design and Skill Specification

## Overview

Change intent serves five purposes — author clarity, an implementation goal an AI can drive against, review consistency across a team, durable context for future agents, and a shape that carries into autonomous workflows — enumerated in [README.md](README.md). This document argues from the most immediate payoff: construct changes in a way that they're **reviewable**. Less focus on the change itself, more focus on the review process around it. By the time a change reaches a human reviewer, design intent has already driven the implementation and informed an automated review assessment. The reviewer knows that the goal evaluator checked the implementation evidence and what the review agent could or could not establish independently, so their attention can go to the judgment question *is this the right intent?* Today that means reviewing better; over time, it means reviewing less.

A **change intent** is both a durable per-change artifact and the lightweight, cooperative workflow contract around it. The artifact helps the author make the intended change deliberate, gives implementation a goal and decision boundary, gives review a consistent target, and preserves the change's purpose and boundaries for future agents. The contract establishes a small common shape: its initial form is approved before implementation begins, implementation works from that direction, and review assesses the resulting change against it. Beyond that common shape, the design aims to fit within a team's existing structure and practices. Teams retain substantial latitude over who or what occupies each role, how those roles integrate with existing development practices, where evidence and findings live, and how review results affect merge decisions.

The artifact captures the design intent in a form that can drive the implementation agent, can be checked against the resulting diff by an AI review pass, and remains in the repository as a persistent record after merge. Before merge, returned work may cause the author to replace the current unmerged intent; implementation and review then run again against the replacement. The implementation goal establishes its own completion evidence; the review pass independently assesses the resulting change using the evidence and capabilities available in the team's review operation. At the core workflow level, the intent file is the additional durable per-change artifact; a team may preserve further implementation or review evidence when it benefits its environment.

This document covers the concept, the problems it addresses, the artifact's structure, how it integrates downstream, and how a skill could produce these intent documents through structured dialogue. The operational instruments that carry it into a project — skill files, prompt blocks, tool bindings — live in [mechanics/](mechanics/README.md): this document makes the argument; those files make it runnable.

---

## The Problem This Tries to Solve

AI generates code far faster than humans can review it. A competent engineer with a good model produces thousands of lines a day; human review is sequential, attention-limited, and scales roughly linearly. Humans are the bottleneck on shipping changes today, and the bottleneck will only tighten — code generation keeps accelerating while reviewer throughput stays roughly flat. The squeeze is the same on a team of two as on a team of twenty: the question is no longer how much code the team can write, but how much the team can effectively review. This work designs a change process that optimizes for the humans still in the loop today, and gets better as the AI in the loop gets better.

Just as autonomous vehicles will eventually drive themselves and we'll think nothing of it, code review will eventually be done by AI and we'll think nothing of that either. The point of a good process today is to walk us toward that future smoothly — more AI, less human, comfort accumulating along the way.

Until we're there, change intent addresses several failure modes of today's review process:

1. **Post-facto rationalization.** PR descriptions are written *after* the change is made. In the age of AI code generation, they're often just a summary of what the AI produced — and an AI reviewer can derive that summary from the code itself, so the description carries little information the reviewer doesn't already have. And because descriptions are written after, they get shaped to fit the change the author ended up with, covering what the code does but not what was intended before starting or wasn't considered along the way. Either way, reviewers get little signal about whether design intent actually drove the change. Change intent inverts the direction: the initial intent is approved before implementation, and every implementation and review pass works against the current intent. If the author replaces an unmerged intent after seeing returned work, the replacement becomes a new baseline and the affected work is assessed again.

2. **Unconsidered cases.** Most production bugs aren't "I thought X would happen and Y happened." They're "I didn't think about case Z, and the code now does something weird in case Z." The initial pre-code dialogue forces the author and the AI to walk through use cases the change will touch, surfacing unconsidered ones before implementation begins. Returned work may later give the author reason to replace that intent, but it does not remove the value of making the first direction explicit before code starts shaping it.

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

**Used beats better.** A process only pays off if the team actually runs it, so the bar to start is as low as we can make it: the project's agents file explains what change intents are, the coding and review agents are made intent-aware, and the ask of a teammate is one sentence — run the change-intent skill instead of the coding harness's built-in plan mode. Change intent works through activities teams already perform: planning, implementation, testing, and review. It improves those activities by giving implementation and review the same approved intent. The optimization target is lower end-to-end friction and cycle time, not maximum procedural assurance. A short up-front clarification is worthwhile when it prevents implementation and review churn; the process should surface genuine missing direction rather than create waits whose only purpose is demonstrating process compliance. Mechanically stronger ideas exist — structural coverage over the intent's tests, per-routine contracts, machine-checked proofs — and they are stronger precisely because they demand more: team effort, specific languages, dedicated tooling. When strength and adoption pull in different directions, this design sides with adoption.

**Diligence to agents, judgment to humans.** Rigor is cheap for an agent and expensive for a human. The agents carry the mechanical work in this design: the authoring skill reads the affected code and runs the authoring dialogue, the implementation agent writes the tests and reasons across the affected change for each invariant, and the review agent checks the diff against the intent and any amendments. In the current reference workflow, the human supplies judgment: they author the intent, they rule on any amendment when the work returns, and they decide at merge whether the change was the right one. These are logical responsibilities; teams may map them to people and agents in ways compatible with their practices, and future agents may occupy seats held by humans today.

**Every claim is falsifiable.** An acceptance criterion can be refuted by a test; an invariant can be refuted by reasoning over the diff. Anything the pipeline is asked to verify has to be specific enough to fail. Outcomes and constraints are not claims: they orient and bound engineering judgment without promising proof that the available environment cannot provide.

**No adversary.** This is a workflow teams adopt for their own benefit, not a control imposed on them, so the design assumes cooperative actors. The pipeline checks compliance — agents check other agents' work at every stage — but it does not try to prove it: the authoring date and initial approval timing are self-reported, and the Amendments section is a plain record rather than an audit trail. The checks catch mistakes, not forgery. Proof would defend against a bad actor the design assumes away, and charge for that defense in adoption cost — the used-beats-better tradeoff again, decided the same way. Gaming the process is easy and pointless: its only output is review quality for the team running it. Chain of custody therefore describes cooperative continuity around a shared intent, not mechanically verified provenance.

**Every role has a defined continuation path.** The process assigns an action for each unresolved condition. The authoring agent may request a decision from the author. The implementation agent has authority over unconstrained technical choices and may amend a newly discovered change-defining decision. The review agent may report `cannot verify` or raise a finding without repairing the change. The process stops only when no amendment can preserve the **approved boundaries** — the intent's outcomes, constraints, and exclusions, together with applicable project instructions.

| Role and situation | Path forward |
| --- | --- |
| Authoring: a change-defining decision is unresolved | Ask the author, with concrete options and their effects on the intent |
| Authoring: the approved direction or an explicit constraint settles the choice | Apply it, cite its source, and continue |
| Authoring: a relevant surface cannot be inspected or bounded confidently | Name the blind spot and ask the author to supply context, narrow the change, or make an explicit decision that governs the surface |
| Implementation: the intent leaves a technical choice open | Choose using normal engineering judgment and continue |
| Implementation: a constraint cannot be proved in the available environment | Use it as a design boundary and continue; lack of proof is not a violation or amendment trigger |
| Implementation: a claim cannot be delivered within the approved boundaries or a necessary change-defining decision is missing | Amend on the record and continue |
| Implementation: no repair can preserve the approved boundaries | Stop and report a failed change |
| Review: evidence cannot establish a claim | Report `cannot verify` and name the missing evidence |
| Review: the diff violates or silently changes a decision in this intent | Raise a finding; do not repair it in review |

The following distinction determines whether a choice belongs in the intent:

```text
Do the branches decide which change will be delivered?
├─ no  → different implementations of the same change: implementation latitude
└─ yes → is the choice already settled by the approved intent?
         ├─ yes → apply it
         └─ no  → authoring: ask
                  implementation: amend and continue
                  review: report a finding
```

A fork is change-defining only when choosing between its branches decides what change will be delivered. Ask whether the author could approve the change once and allow implementation to choose either branch while still receiving the change they approved. Apply that question to the branches' consequences for author-owned direction — intended outcomes; material behavior or guarantees for users, callers, operators, or downstream systems; explicit engineering boundaries; and conscious exclusions — not merely to their mechanisms. If either branch still delivers that direction, the fork is implementation latitude. If one branch changes it, the intent must settle the choice. A reasonable branch is supported by the affected system and the normal scope of the change, not merely imaginable. A technical or observable difference alone does not make a decision change-defining; ordinary engineering and review still apply.

---

## What an intent file contains

A change intent file is a per-change document whose initial form is approved **before implementation begins**. It is complete over change-defining decisions and open over implementation: it identifies the approved change precisely while leaving technical choices open when they are different ways to deliver that change. Completeness is a quality requirement on the artifact and the authoring process, not a proof that no unknown dependency exists. Each pull request contains exactly one current intent file. Implementation may amend it under the narrow rules below. If returned work changes the author's direction, the author may replace the unmerged candidate; the prior candidate is superseded, the replacement becomes the approved baseline, and implementation and review run again against it. Only the intent that merges becomes frozen history. `Outcomes` and `Why` apply to every change. `Constraints`, `Acceptance criteria`, `Invariants`, `Out of scope`, and `Amendments` apply under the conditions described below. An omitted section indicates that its condition does not apply.

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

**Each AC must be provable by a test that ships with the diff.** If there's no integration test, unit test, or one-shot measurement that can be run against the change to demonstrate the claim, it doesn't belong here. "Cache hit rate exceeds 60% in production," for example, can't be verified at change time — production isn't running the diff when the review happens. State it as an outcome when it describes what the change is intended to achieve, or as a constraint when it is an operating boundary every implementation must account for. Neither classification manufactures a proof obligation.

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

Statements in the second category belong in `Outcomes` or `Constraints`, depending on whether they describe the result the change seeks or a boundary the implementation must account for. They do not belong in the AC list.

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

If your change needs an environment-dependent performance bound, that bound is not an AC. Record it as an outcome or constraint and let the team's normal performance systems provide whatever evidence they can. Change intent does not require the authoring agent to design that verification or require implementation and review to prove what their environments cannot establish.

### Invariants

A list of properties that must remain true across the parts of the system affected by the change. Their full obligation cannot be closed by test evidence alone because implementation and review must also reason across the affected change. Read-after-write consistency across callers, availability under failure, audit-log-on-every-mutation, and thread safety across access paths are invariant-shaped.

Tests should exercise an invariant where useful, but passing tests do not close it by themselves. The implementation agent must also reason across the affected diff and relevant surrounding paths; the AI review pass independently applies the same property to the resulting change. Tests establish concrete cases, while the reasoning addresses the property across the change.

The intent states the property in plain language, not every location where it applies and not every test that might exercise it. Discovering the relevant locations and choosing useful tests are implementation and review responsibilities.

Authoring does not attempt to enumerate every desirable invariant of the system. Include an invariant when it is part of the change the author is approving and its obligation extends beyond a focused acceptance scenario. Ordinary correctness, security, concurrency, and quality concerns remain part of implementation and review even when they are not written as intent invariants. The section may therefore be small or absent when acceptance criteria capture the approved change.

**Examples of invariants:**
- "Read-after-write: a track added via `UpdatePlaylist` is visible to `GetPlaylist` across all caller paths, within the staleness window"
- "Every mutation of a collaborative playlist writes an activity entry with the acting user's identity"
- "The cache layer is safe for concurrent reads and writes from multiple callers, across all access paths added by this change"
- "If the cache backend is unreachable, every code path that reads through the cache falls back to the database without surfacing the failure to callers"

Note the shape: each states one property whose reach extends beyond a focused proving test. It names that reach as a rule rather than inventorying the files, callers, branches, or tests that implementation must inspect.

### Out of scope

A list of things this change explicitly is *not* doing — work the author considered but intentionally left out. Without this section, the diff alone can't tell a reader whether something was thought about and excluded, or just never considered. Out of scope captures that distinction, turning intentional exclusion into a signal the same way the diff makes intentional inclusion a signal.

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

**Why no dedicated Alternatives or Risks sections?** Alternatives may appear temporarily while the author makes a decision. The final file keeps the selected consequence under Outcomes, Constraints, Acceptance criteria, Invariants, or Out of scope. Rejected alternatives do not move into `Why`.

A risk belongs in the file only when it changes the approved intent. Express the resulting requirement as an acceptance criterion or invariant, or the engineering boundary as a constraint. Other risks remain part of ordinary implementation and review rather than becoming an author-provided checklist.

### Amendments

A dated record of repairs made during implementation — present only when a claim proved wrong or a necessary change-defining decision surfaced after approval. Most intents never get one; an absent Amendments section means the current intent held as written. The current intent must remain complete and understandable without this section. Amendments exists only for a reader who wants to see what implementation changed from the approved wording.

Each amendment receives a short identifier local to the file. It states the discovered system fact, then quotes the affected item's previous and current wording verbatim with the section where each belongs:

```markdown
- **A<N> — <DATE>.** <The discovered fact that forced the repair.>
  - Was — <Section>: <verbatim previous item>
  - Now — <Section>: <verbatim current item>
```

For an item's first addition, write `Was: not present`. For a removal, write `Now: removed`. A move or reclassification names the previous section under `Was` and the current section under `Now`. If one discovery changes several items, the same amendment may contain several `Was` and `Now` pairs.

The discovered fact must describe the system, not the author's activity: something still true and checkable if the rest of the file were deleted. `Ran into implementation issues` fails; `SharingMiddleware caches access grants for 5m with no invalidation hook` passes.

No amendment marker or discovery note appears beside the current item. A reader first reads the body as the complete current intent, then reads Amendments only to understand its implementation-time changes. The terminal verbatim `Now` wording makes the affected current item easy to find without adding identifiers to the body. The process that permits and checks these entries is covered in [Amending the intent](#amending-the-intent).

---

## File location and naming

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

Three design choices are wrapped up here, each worth being explicit about:

**1. The date comes first so the folder is linearly scannable.** A repository accumulates intent files over time — hundreds, eventually thousands in a long-lived codebase. Sorting by name gives you sorting by time, so a reader can scan the folder and see what happened when without digging into git history. The date is the *authoring* date, set at file creation, and never changes through review, merge, or squash.

**2. The slug is short, descriptive, and required up front.** The intent file gets a concise kebab-case slug at the moment of creation, normally three to six tokens. The target is commit-title specificity: use the shortest wording that clearly identifies the change. Slug length is naming guidance, not a scope test; exceeding six tokens is not by itself a reason to stop or split the change. Work that contains independently deliverable changes should be split, with a separate intent for each.

**3. The slug identifies the change.** Use concrete nouns about what this pull request changes, not vague verbs about effort. A specific slug makes the intent recognizable in the current review and leaves a legible historical record without making that record an input to later changes. `add-getplaylist-cache` is more useful than `playlist-improvements`; `migrate-artwork-to-webp` is more useful than `artwork-refactor`.

Once its change merges, an intent file is frozen — never edited, never renamed, never deleted; it is a historical record. Before merge, the current intent governs implementation and review. The implementation agent may amend that candidate through the process described in [Amending the intent](#amending-the-intent). If returned work changes the author's direction, the author may replace the candidate through [Revision before merge](#revision-before-merge). The replacement supersedes the prior unmerged candidate; the process does not preserve its revision history. Follow-up changes to the same area get their own file with their own date and slug; the date prefix makes the lineage visible without making earlier intents govern later changes.

---

## Why the initial intent comes first

Two reasons, both about timing.

**It's a forcing function.** The moment you try to state precisely what must hold, you discover where your thinking is fuzzy. Most software bugs aren't reasoning errors; they're cases the author didn't consider. Articulating acceptance criteria and invariants explicitly surfaces those cases at the cheapest possible time, before the code exists.

**Approval gives implementation a direction before it starts.** Once the initial change intent is approved, downstream agents work in narrower modes: the implementation agent decides *how* to satisfy it, and the review pass checks *whether the implementation honors it*. The approved artifact settles which change to deliver, not every implementation decision. If implementation discovers that a claim cannot be delivered within the approved boundaries or that it cannot continue without deciding which change will be delivered, the remedy is a recorded amendment ([Amending the intent](#amending-the-intent)). If every reasonable branch still delivers the approved change, the implementer chooses and continues. Returned work may later cause the author to approve a replacement intent, which begins another implementation and review pass.

This split also separates the two cognitive tasks that get conflated in normal code review:

1. **Deciding what should be true** — high-judgment work
2. **Verifying that code matches what should be true** — mostly mechanical work

Change intent splits the work so each gets done by the right agent at the right time.

### When exploration comes first

Not all work results in a change: a toy, a prototype, exploratory testing — work that is not intended to merge needs no intent, and this design proposes no process for it. Change intent picks up when the author decides to ship: shipping is a change, its initial intent is authored and approved first, and everything that merges — including any prototype code the author keeps — is implemented and reviewed against it. In this design, implementation means that shipping work; a prototype that preceded the intent is exploration, not implementation begun early. If returned work later changes the author's direction, the replacement intent is approved before the affected implementation and evidence are reassessed.

### The intent author doesn't have to be a human

The same workflow can support an AI orchestrator in the author seat instead of a person. The orchestrator brings an upstream objective and operates within an authority boundary supplied by a human, product process, incident signal, policy, or broader program; the authoring skill brings the structure and rigor. The result is the same kind of change intent file ready for implementation. How that objective and authority are supplied can remain part of the team's broader operating model.

This is what lets the discipline carry forward into the autonomous trajectory. As humans gradually exit the loop (the autonomous-vehicle arc described at the top of this document), the same semantic responsibilities and shared decision artifact can support an orchestrator, implementation agents, and review agents even as their orchestration and surrounding tools evolve. The skill that runs the dialogue with a human today can serve an orchestrator later without requiring a different kind of downstream contract.

---

## Amending the intent

Approving the initial intent before implementation does not require the author to know every implementation fact in advance. Implementation may expose an incorrect claim or a missing decision. The implementation agent can repair the current candidate through a narrow amendment; the author can instead replace an unmerged candidate when returned work changes their direction. After merge, the intent is frozen history.

### The necessity test

The amendment mechanism corrects an inaccurate or decision-incomplete intent; it is not an implementation log or an escape from a difficult implementation. Exactly two conditions permit an amendment:

1. **A claim cannot be delivered within the approved boundaries.** Facts discovered during implementation show that no reasonable implementation can make an acceptance criterion or invariant hold without violating the approved boundaries. Failure of the current approach is not enough: if another reasonable in-scope implementation can satisfy the claim, the agent changes the implementation rather than the intent. The amendment relaxes or replaces the claim only as far as the discovered fact requires.

    This trigger also covers an acceptance criterion whose behavior can be delivered but cannot be proved by any reasonable test available to the change. An acceptance criterion promises a proving test that ships with the diff. When the behavior is real but that proof obligation cannot be met, the amendment rewords the criterion into a provable form without weakening its substance, or moves the statement to Outcomes or Constraints according to the role it plays. A constraint's lack of proof never triggers an amendment; constraints are not claims. An invariant's need for reasoning beyond test evidence is part of its ordinary evidence shape, not an amendment trigger.

2. **A necessary change-defining decision is missing.** Implementation cannot complete without choosing which change will be delivered, and the current intent does not make that choice. The process authorizes the implementation agent to select a resolution using the shared precedence below, record it as an amendment, and continue. A decision is not necessary merely because the selected implementation happens to expose a fork; if either reasonable branch still delivers the approved change, the agent chooses an implementation without amending. A technical fork, incidental observable effect, better idea, or ordinary engineering tradeoff does not qualify by itself.

This is a bounded engineering test, not a proof of impossibility. A reasonable alternative is one supported by the current repository and normal scope of the pull request, not a hypothetical redesign outside the approved boundaries. Before amending, the implementation agent names the plausible in-scope alternatives revealed by the work. If one can satisfy the current intent, the agent uses it or another qualifying alternative. An amendment may repair a claim or settle a missing decision only while preserving the approved boundaries. If every reasonable in-scope resolution would violate one of those boundaries, the agent reports a failed change.

When the second condition applies, the implementation agent compares the reasonable in-scope resolutions in this order: preserve the approved outcomes; honor explicit constraints and exclusions; preserve existing external behavior unless the intent changes it; minimize scope; prefer the more reversible resolution. It selects the first resolution distinguished by that order. If the full precedence leaves reasonable resolutions tied, it selects either, records that the precedence did not distinguish them, and continues. Every missing-decision amendment is a provisional implementation-time decision made under the narrow authority of this amendment process. It takes effect immediately for implementation and review; provisional describes its relationship to author acceptance, not whether downstream work follows the amended intent. Code, tests, documentation, and project instructions are evidence about the system and constraints the implementation must honor; they are not a separate source of product direction. Amendment authority permits the implementation agent to update the current intent and continue implementation against it; it does not override applicable project instructions or expand the agent's operational permissions. The amendment records the decision, the discovered fact, and the precedence basis for the selection. The record distinguishes the implementation-time decision from the author's approval of the current baseline.

Everything else — better ideas, opportunistic hardening, adjacent fixes, "while we're in here" — is not an amendment. A discovery that would *improve* the change is a seed for the next change intent: its own file, own date, own slug, own deciding moment. The pressure that would otherwise bloat the amendment channel gets redirected into the artifact system: the deferred idea is handed to the author as a named seed for its own intent, instead of dying as a rejected request.

An editorial correction that preserves a claim's meaning is not an amendment and is not needed for implementation; the implementation agent leaves the approved wording unchanged. If the ambiguity could describe different changes, the issue is semantic rather than editorial and must satisfy the amendment necessity test.

### Who amends: the agent, on the record

Amendments are the exception, not a phase of every change — the authoring dialogue exists to make them rare, and most intents merge exactly as approved. If implementation proves that a claim cannot be delivered within the approved boundaries, the implementation agent amends the intent itself. The author is unlikely to ever write this file by hand: the authoring skill writes it during the dialogue, and the implementing agent repairs it during implementation.

The channel exists because an agent that discovers a wrong claim mid-implementation, with no sanctioned way to repair it, fails in predictable ways: it fabricates success, drifts past the problem silently, or stalls. Amendment preempts all three by sanctioning the correct move — change the claim, record what changed and the fact that forced it, keep working. Work on unaffected claims never stops.

Nothing changes invisibly within the current candidate. Every repair leaves an identified, dated entry that states the discovered fact and quotes the affected item's previous and current wording verbatim. The current body contains only the intent as it now stands, so it reads cleanly without the amendment history.

The author still rules on every amendment — at review rather than mid-implementation. When the work comes back, accepting the current intent accepts all of its recorded amendments together. If the author wants different direction, they replace it under [Revision before merge](#revision-before-merge). No separate per-amendment approval step is required. A replacement incorporates relevant discovered facts into its ordinary current wording and starts as a clean baseline without the superseded candidate's Amendments section. Moving the ruling to review has a known cost: a repair the author would have decided differently is discovered after the work is done, not before. The design accepts that cost deliberately — rework is cheap for an agent, and stopping mid-implementation to wait on a decision is expensive for everyone — and states it here so a future reader doesn't reintroduce mid-implementation approval as a fix.

One boundary remains fixed: an amendment repairs a deliverable change. If no amendment can preserve the approved boundaries, the agent stops and reports a failed change. The amendment process does not authorize replacement of those outcomes with a different change.

Two supporting rules keep the channel quiet and enforceable:

- **Implementation latitude does not need to be enumerated.** The intent may explicitly bound a choice ("TTL may be anywhere in 10–60s"), but the implementation agent also owns unspecified choices when every reasonable branch still delivers the approved change. The same precedence applies when the agent must settle a missing change-defining decision: approved outcomes, explicit constraints and exclusions, existing external behavior unless the intent changes it, minimum scope, and reversibility. Rationale for ordinary technical choices is recorded where normal engineering practice requires it; an amendment is not required merely to document the choice.
- **The review pass checks eligibility and coherence.** The reviewer assesses whether the discovered fact satisfies the necessity test and whether a missing-decision amendment applied the precedence above. It then checks that every entry quotes the `Was` wording and section verbatim, quotes the `Now` wording and section verbatim or states that the item was removed, and forms a coherent chain if the same item changed more than once. An addition states `Was: not present`. The current intent must remain coherent without Amendments, and each terminal `Now` item must match the current body. An ineligible or incoherent record is reported with the same severity as a `not met` acceptance criterion. The reviewer does not reconstruct Git history to prove the `Was` text; the rule binds the implementing agent in this cooperative process.

### What an amendment leaves behind

The current body is the complete normative intent. Amendments does not carry requirements that are absent from the body, and the body does not depend on amendment markers. The section adds only the short implementation-time history, in the record format defined in [Amendments](#amendments) above. A missing-decision entry also names the precedence rule that selected the resolution or states that the precedence left the reasonable resolutions tied.

When a claim is weakened and its prior strength is deferred rather than abandoned, the current body also contains the corresponding Out of scope item. The amendment quotes both affected item transitions where necessary; it does not annotate them in place.

The result serves two independent reads. A reader can understand the change by reading the current intent alone. A reader who continues into Amendments can see the exact approved wording implementation encountered, the wording now in force, and the system fact that required the repair.

### Why rarity is load-bearing

Amendments should be rare, and the design leans on that rarity three ways:

- **Every amendment is a decision made under anchoring.** Initial authoring is the moment before implementation starts shaping everyone's view. An amendment settles a question after that shaping has begun. Sometimes that is unavoidable — reality falsified the plan, and deciding with better information is the process working — but it is never free. A process where amendments are routine is a process where deciding happens continuously during implementation: the pre-intent world, rebuilt with extra paperwork.
- **Rarity is what earns each amendment the author's full attention.** When amendments appear only on falsification, an Amendments section on a returned change is a signal worth reading carefully. If amendments appeared for every nice-to-have, the author would learn to skim them — and a skimmed Amendments section carries no signal at all.
- **Amendment count becomes a diagnostic.** Every amendment marks a spot where confusion was confirmed in practice — the author, the authoring dialogue, and the surface read all missed something that reality then surfaced. One or two entries is ordinary contact with reality. Six entries on a small change points at the authoring dialogue (it missed real interactions with the touched surface) or at the code itself (the area is genuinely hard to reason about). Either way the signal is actionable: a surface that accumulates amendments across changes has earned extra scrutiny in review passes, and a deeper authoring pass the next time a change touches it.

---

## Revision before merge

The amendment process constrains the implementing agent; it does not prevent the author from changing direction after seeing returned implementation or review. When that happens, the author replaces the current unmerged intent and approves the replacement. The prior candidate is superseded rather than amended or archived by this process. Change intent does not preserve or ask review to reconstruct the iterations that did not merge.

The replacement is a new approved baseline at the same intent path. Approval applies to the complete replacement, including any amendment-derived wording it retains. Relevant implementation discoveries are incorporated into its ordinary current wording, and the superseded candidate's Amendments section is removed. Existing code may be retained where it satisfies the replacement, but affected implementation and evidence are reassessed before review runs again. At every point, implementation and review have exactly one current intent.

In the worked example, the returned change may cause the author to require invalidating the cached entry on `UpdatePlaylist` rather than allowing PlaybackService to bypass the cache. The author replaces the current intent with that direction, approves it, and sends the change through implementation and review again. The merged intent describes the change that landed; it does not explain the superseded candidate.

---

## How It Integrates Downstream

The minimal logical flow is **author → implement → review → merge**. The arrows express dependencies among responsibilities, not a required organizational topology or tool pipeline. Teams may fit those seats into broader development practices, assign them to the same or different participants, and add integrations while preserving the common contract: direction is explicit before affected implementation, implementation uses the current intent as its goal and decision boundary, and review assesses the resulting change against it before merge. The design is meant to remain useful as models and harnesses improve enough for this flow to run end to end without a human occupant. In the current reference workflow, humans normally author with the skill's help and review after the machine review. Returned work may repeat part or all of the logical flow with a replacement intent.

The change intent has three downstream consumers. The implementation agent uses it as a *goal and decision boundary*, with latitude over choices it does not constrain. The AI code review pass uses it as a *basis for review*, not as an exhaustive specification. The human reviewer uses it as *evidence of the process*. The role-path table above governs unresolved conditions for each role. Each pass uses the one current intent, and only the version that merges becomes durable.

What travels between the stages is deliberately thin: the intent file and the change itself — the diff and its tests. The implementation agent produces test results, would-fail demonstrations, and invariant reasoning in its session. The in-loop goal evaluator sees that context and uses it to decide whether implementation is complete. Review does not depend on receiving that session context: the reviewer independently assesses the implementation and the evidence available through the team's review operation, using inference where direct implementation evidence is absent. An invariant states a property and its intended reach, never a list of sites or tests. Implementation and review each apply that rule across the affected diff and relevant surrounding paths. A pipeline may carry more evidence forward; the design deliberately leaves substantial latitude in how a team's review operation reads, runs, or otherwise examines the change.

### Implementation phase: the intent as the `/goal` condition

Claude Code shipped `/goal` in v2.1.139 (May 2026). It lets a user set a completion condition and have the implementation agent keep working autonomously across turns until that condition is met. After each turn, a separate evaluator model (Haiku by default) reads the conversation transcript and decides whether the condition holds. If yes, the goal clears. If no, the agent continues with the evaluator's reason as guidance for the next turn.

**Key architectural detail:** the evaluator only sees what's surfaced in the conversation. So the condition must be something the implementation agent can prove through its own output — tests passing, builds clean, benchmarks meeting targets, files matching some shape. The evaluator can't run commands itself.

A change intent file is naturally shaped to be a `/goal` condition. The acceptance criteria and invariants form the proof obligations; constraints bound the engineering judgment used to satisfy them:

- **For each acceptance criterion**: write a test that exercises the scenario, run it, and surface the passing result in the transcript. Then temporarily make the criterion's defining condition false with a reversible product change or, when that is unsafe, a controlled configuration or dependency negative control. Show that the test fails for the expected, claim-specific reason, restore the temporary state, and show the test passing again. One falsification may support multiple criteria only when each criterion's own proving test fails on its own claim. The test is the agent's own work; the AC didn't name it.
- **For each invariant**: add tests for concrete cases where they provide useful protection, then reason across the affected diff and relevant surrounding paths. Passing tests do not close the invariant by themselves. The implementation agent surfaces its analysis and any material uncertainty in the transcript; the intent author was not required to enumerate the locations or tests in advance.
- **For each constraint**: account for it in the implementation. Directly check it when the diff permits; otherwise use it as an engineering boundary. The agent does not owe proof of a production-only condition and does not amend or stop merely because its environment cannot establish one. It acts when affirmative evidence shows a conflict.
- **If it discovers that the intent is inaccurate or decision-incomplete** — a claim cannot be delivered within the approved boundaries, or implementation cannot continue without deciding which change will be delivered — the agent records an amendment ([Amending the intent](#amending-the-intent)) and continues. If every reasonable branch still delivers the approved change, the agent selects an implementation without amendment.

The in-loop evaluator checks the transcript for the passing tests, would-fail demonstrations, invariant reasoning, and any known conflict with a constraint. It does not demand proof that an unavailable environment cannot provide. This is the only stage required to verify the temporary falsification evidence directly. The review that follows has a different role and different inputs.

### Review phase: the intent as the AI reviewer's target

After the goal clears, an AI code review pass independently reviews the implementation and its available evidence with the change intent as context. What the reviewer can inspect or execute is defined by the team's review operation, not by change intent. It assesses four things:

1. **Is the intent itself well-described?** Are claims falsifiable, are the change-defining decisions complete, and are conscious exclusions clear? A vague or decision-incomplete intent is a defect; absence of implementation detail is not.
2. **Does the diff match the intent?** Every acceptance criterion must be exercised by a test whose assertions would detect the claimed behavior becoming false. The reviewer uses available evidence and inference to assess that relationship between the criterion, test, and implementation. For every invariant, the reviewer uses available tests and reasons across the affected diff and relevant surrounding paths; no passing test closes the property by itself. Constraints bound the reviewer's engineering judgment but do not each require a test or conclusive verdict; lack of proof is not a violation. In the reverse decision check, the reviewer asks whether the diff selected which change to deliver where the current intent left that choice unresolved. If every reasonable alternative would still deliver the approved change, the choice is implementation latitude and remains subject to ordinary review rather than an intent finding.
3. **Is the amendment eligible and coherent?** The reviewer checks whether the discovered fact shows that the pre-amendment `Was` claim could not be delivered within the approved boundaries, or that implementation could not complete the change without settling a missing change-defining decision. Difficulty with the chosen approach is not enough. The reviewer then reads the current intent independently and checks the amendment record: each entry quotes the prior section and item verbatim under `Was`, quotes the current section and item verbatim under `Now` or records addition/removal explicitly, and forms a coherent chain when an item changed more than once. Each terminal `Now` item must match the current body. For a missing-decision amendment, the reviewer also assesses whether implementation applied the shared precedence and recorded either the selecting rule or a full tie. A relaxed claim records an Out of scope deferral only when the prior strength is actually deferred rather than abandoned. Review does not reconstruct Git history to prove the prior wording.
4. **Does this pull request conform to the intent folder's rules?** The pull request carries exactly one intent file: the intent for this change. The assessment is scoped to that file and this change; it does not compare the change against earlier intent files or other branches.

The would-fail requirement belongs to implementation completion. It addresses the risk that the implementation agent writes both the code and the tests used to accept it. For each acceptance criterion, the implementation agent demonstrates in its session that the proving test fails for the expected, claim-specific reason when the criterion's defining condition is temporarily made false. A reversible product mutation is preferred; a controlled configuration or dependency negative control is used when that is unsafe. One falsification may support multiple criteria only when each criterion's own proving test produces its own claim-specific failure. The in-loop evaluator can see those demonstrations. Review does not require that session context: the reviewer independently assesses each acceptance criterion's proving test and each invariant across the affected change, using available evidence and inference. A team may give its reviewer additional evidence or execution capabilities. When the review operation cannot support a conclusion, the reviewer reports `cannot verify`. `Cannot verify` is a complete review result, not a successful verification: the available inputs establish neither `met` nor `not met`, and the team decides what that uncertainty means for the change.

The two machine roles are complementary. The in-loop `/goal` evaluator sees the implementation transcript and judges whether the implementation agent demonstrated completion. The review pass keeps intent alignment and ordinary code review as distinct judgments, regardless of input order. It uses the intent to assess the approved change but never treats the intent's silence, exclusions, or decisions as an excuse for a defect in code the pull request ships. Neither role substitutes for the other.

### Human review: the chain of custody pays out

By the time a change reaches human review, it has passed through a repeatable chain of custody. That cooperative chain provides continuity through the team's existing workflow rather than an audit trail or mechanically verified provenance. The approved intent records what the author and authoring agent settled. The implementation and tests show what the implementation agent built, while the cleared implementation goal establishes that its required completion demonstrations were evaluated. Any amendments identify change-defining decisions made during implementation. The review assessment conveys what the review agent concluded and what it could not verify independently through the team's chosen review operation.

This gives the human reviewer a consistent frame for how AI participated in developing the change: what authoring decided, what implementation produced and demonstrated, and what review examined. Because every change passes through the same chain, the team can learn the strengths, weaknesses, and quirks of each AI seat and use that knowledge to decide where human attention is most valuable. A teammate's change arrives with the same frame as the reviewer's own.

### Workflow

1. The author — typically a human with skill assistance in the current reference workflow — produces and approves an initial change intent file at `change-intent/YYYY-MM-DD-slug.md` before implementation begins.
2. Implementation phase: `/goal` with the acceptance criteria and invariants as proof obligations and the constraints as engineering boundaries. Agent writes code, runs tests, demonstrates each acceptance criterion, applies each invariant across the affected diff and relevant surrounding paths, and accounts for each constraint without manufacturing unavailable proof. In-loop evaluator (Haiku) confirms each turn. In the rare case the agent discovers the intent cannot be delivered as written, it amends the intent on the record and keeps working.
3. When the goal clears, the AI code review pass reads the diff, tests, repository, and intent; assesses intent quality and intent-vs-diff alignment; runs standard review checks; and reports findings and limits such as `cannot verify`.
4. In the current reference workflow, once the review assessment is complete, the change reaches the human reviewer. Any amendments are the highest-signal part of the returned work — provisional implementation-time decisions awaiting the author's ruling. The human reviewer also receives any review findings or limits, then decides whether this is the right change to merge; if the returned work changes the author's direction, the author replaces the unmerged intent and sends the change through implementation and review again.

### Sample `/goal` invocation

```
/goal The change in change-intent/2026-05-16-add-getplaylist-cache.md is complete:
- Every acceptance criterion is exercised by a test the agent wrote, and the test passes
- For every acceptance criterion, a reversible product mutation or, when that is unsafe, a controlled configuration or dependency negative control makes the defining condition false and its proving test fails for the expected, claim-specific reason, with any limit on what could be safely demonstrated surfaced with its reason; one falsification serves multiple criteria only when each test fails on its own claim, and every temporary change is restored before the tests pass again
- Every invariant has useful concrete tests where appropriate, and the agent has reasoned across the affected diff and relevant surrounding paths and surfaced any material uncertainty
- The implementation accounts for the outcomes, constraints, exclusions, and amendments without claiming proof for constraints the available environment cannot establish
- Any newly discovered change-defining decision is amended on the record; ordinary technical choices remain implementation latitude
```

The last two lines form the **decision-alignment check**. They require the implementation to honor approved decisions and to record any newly necessary change-defining decision. The implementation loop evaluates the transcript evidence; AI review independently assesses the final diff without depending on that transcript. Neither check requires every observable effect to appear in the intent.

---

## The Authoring Skill

The skill produces a change intent file through structured dialogue with the intent author — a human today, possibly an AI orchestrator in autonomous chains. During authoring, **the author owns direction** — the outcomes, the why, what the change must and must not do — and **the skill owns the map**, the code as it exists today, which the author may not know at all, especially where agents wrote it. The author speaks in outcomes and plain-language constraints; the skill translates testable behavior into falsifiable claims and preserves genuine engineering boundaries as constraints. The prompt-level instrument lives in [mechanics/authoring-skill.md](mechanics/authoring-skill.md); this section fixes the design it implements.

**Critical constraint: the skill drafts the artifact but does not decide change-defining questions.** It may propose direction the author did not state, but every outcome, claim, constraint, and exclusion identifies its source, every settled change-defining fork cites the approved direction or explicit constraint that settled it, and every remaining fork is presented to the author as an explicit decision. Repository contents establish facts about the current system; they do not independently decide what the change should be. Ordinary implementation choices are not elevated into author questions. The resulting file contains forward-looking claims rather than a catalog of existing behavior.

### Workflow

**Phase 1 — the intent brief.** The skill assembles the author's direction — harvested from the session when the change was already discussed there, asked for otherwise — into a short fixed-format brief: outcomes, why, constraints, directions explicitly rejected, questions deferred to exploration. The author corrects and confirms it before anything else happens. The gate is cheap and load-bearing: it is where a misread of the author's direction gets caught, before exploration is spent on the wrong change.

**Phase 2 — exploration.** The skill reads the affected surface and records a confidence level for each fact. It retains decision candidates as private working state through a coverage pass and includes only change-defining forks in author-facing output. For every outcome, it traces the input or starting condition through the immediate result and any later behavior that can observe or depend on that result. A pure transformation ends at its result; a continuing path is examined for repetition, progression, retry, and early termination. The analysis identifies lifecycle decisions without converting every path into a claim. The skill also confirms that each proposed acceptance criterion has a writable test and records adjacent improvements without expanding scope. If a relevant caller, lifecycle, data boundary, or other required surface cannot be inspected or bounded confidently, the skill names that blind spot instead of asserting completeness.

**Phase 3 — the proposed intent.** The skill produces one compact fixed-format proposal: an optional `Needs your attention` section for unresolved author-owned direction, with each item answerable without opening a file; the complete draft with a temporary source tag on every outcome, claim, constraint, and exclusion; and a short statement of test feasibility and resolved coverage limits. Technical alternatives that do not change the intent are omitted. The final intent keeps the approved consequences and discards the proposal scaffolding.

**Phase 4 — discussion and approval.** Rulings are applied as diffs rather than full-file restatements. Before approval, the skill reads each claim literally and checks for contradictions, missing change-defining decisions, unfalsifiable claims, and exclusions that conflict with the outcomes. Unspecified details remain implementation latitude when every reasonable branch still delivers the approved change. On approval, the proposal scaffolding is removed, the file is written and committed on the change's branch, and parked items are reported as candidates for future intents. If the author abandons the change, no file is written. Before merge, implementation may amend the current candidate, or the author may replace it and begin another implementation and review pass. At merge, the current intent becomes frozen history.

### Scaling the intent to the change

Intent size follows the number and scope of change-defining decisions and proof obligations, not the number of implementation details or observable channels. The file should not be expanded to create an appearance of thoroughness. Each acceptance criterion proves a selected decision; each invariant protects a property across the affected change without inventorying every site or test. A one-line fix can require a substantial intent when it changes a security boundary or caller guarantee, while a broad internal refactor may require few claims when its alternatives are different ways to deliver the same change.

The measure is the extent of the change's decisions and guarantees, not its diff size and not how casually the author stated it. Bounded exploration of callers and paths can reveal guarantees, system facts, and explicit constraints, but the authoring artifact does not inventory every effect or every location where an invariant might apply.

### Stopping condition

The skill is "done" when:

- Every open decision has the author's ruling
- Every claim is falsifiable
- Every relevant coverage limit has been resolved by supplied context, narrower scope, or an author-approved decision recorded as an outcome, claim, constraint, or exclusion
- The author approves the produced artifact

Without an explicit stopping rule, the dialogue either runs forever or stops too early.

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
- Do not introduce distributed cache coordination.

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
- **Eviction policy customization.** CacheManager defaults (LRU with a 100k entry limit) are sufficient for the access patterns we've measured.
- **A dedicated API for cache inspection or invalidation.** Not included here. A follow-up PR will add inspection endpoints once production data shows whether on-demand invalidation is needed.
```

**A mid-implementation amendment.** While implementing the cache, the implementation agent hits a question the approved intent does not settle: `GetPlaylist` returns nil for playlists that do not exist — should negative results be cached? The authoring read recorded the nil-return fact, but the dialogue never carried it forward to the fork it creates: an authoring miss, of exactly the kind the amendment channel exists to absorb without stalling the work. Caching nil would leave a playlist created immediately after a missing lookup invisible to `GetPlaylist` for up to the TTL — "playlist not found" on a playlist the listener just made; not caching negative results preserves existing immediate post-creation visibility. Those branches deliver different changes rather than different implementations of the same change, and the approved intent does not choose between them. The shared precedence selects not caching negative results because it preserves existing external behavior. The intent gains one acceptance criterion and one amendment entry:

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

The implementation agent takes this file as the `/goal` condition. For each acceptance criterion, the agent writes a test that exercises the scenario, runs it, and surfaces the passing result. It also completes the would-fail demonstration for every criterion, reusing a safe falsification only when each proving test fails for its own claim, and restores every temporary change before showing the tests passing again. For each invariant, it adds tests for concrete cases where useful and reasons across the affected cache diff and relevant surrounding paths. The intent states the invariant properties; it does not enumerate the callers, access paths, or tests the agent must consider. The in-loop evaluator checks the transcript for both kinds of evidence.

When the goal clears, the AI code review pass takes the diff with this intent as context. It assesses the alignment from the final code and tests—with particular scrutiny on invariants, where the review pass walks the whole diff through each invariant's lens—and runs the standard checks (concurrency, errors, security, clarity). It reports both findings and anything it cannot verify from those inputs. The change then reaches the human reviewer with that assessment.

---

## Design Tensions

A few areas where the design is not fully resolved and worth flagging for implementation. Premises and direction that lie outside the design — for example, the mechanism behind "reviewing less" — are recorded in [notes.md](notes.md).

### Decision completeness is diligent, not omniscient

The change-defining test can classify a decision only after the process discovers the relevant fork. Authoring and reverse review therefore inspect the defined affected surfaces and settle every change-defining decision they find, but neither pass proves that no unknown dependency exists. "Complete over change-defining decisions" is a quality requirement: a decision that a diligent pass should have found is a defect when later discovered, not evidence that the process had to search without bound.

When authoring cannot inspect or confidently bound a relevant surface, it exposes the specific blind spot to the author. The author supplies context, narrows the change, or makes a decision that governs the surface and can be recorded as an outcome, claim, constraint, or exclusion. If none of those paths resolves the blind spot, the intent is not ready for approval. Review independently repeats the bounded decision sweep and may report `cannot verify` when its available view cannot support a conclusion. These paths preserve the completeness standard without encouraging manufactured decisions or indefinite exploration.

### Cold start on existing codebases

Existing codebases rarely document every property a change may affect. The author's direction and the AI's bounded surface read may therefore miss a real interaction. The intent still records only the invariants that belong to the approved change; authoring does not compensate by inventorying every property or location in the system. The coverage-limit path above handles known uncertainty, but it cannot expose a dependency that no available evidence reveals.

### Cross-cutting invariants

Some properties are system-wide ("every mutation of a collaborative playlist writes an activity entry with the acting user's identity"). A change intent includes such a property only when it is part of the change being approved, and states the property without requiring the author to enumerate every mutation site. Existing project-wide rules remain applicable through normal project instructions and ordinary implementation and review; this design does not require a separate registry before a team can use change intent.

### Method-level invariants are separate

This document covers only the macro layer — change-scoped and author-directed. There is a complementary system for method-level invariants: pedantic, AI-maintained annotations in doc comments paired with named tests, enforced by a linter, consumed by an AI-only reviewer. That system handles the micro layer. The two layers compose in the broader review pipeline but are designed independently. Method-level invariants are **out of scope** for this document and this skill.

---

## Where this is heading

A change is the package of the work that produced it — the intent, its decisions, its falsifiable claims, its constraints, and its consciously excluded scope — bundled with the code itself. An AI or future engineer should be able to open a single merged change and understand what change was intended, why it was needed, and which boundaries governed it.

That's the deeper claim. Change intent is one expression of it, scoped to 2026 tools.

What this looks like a year or two from now is probably different. Code review may not use git as the substrate. Intent may be captured through richer interactions than markdown files. The specific conventions here will evolve.

We don't have to be exactly right about the future to be directionally right. The asymmetry that matters: information saved now can be reshaped into whatever future tooling needs; information that wasn't saved can't be reconstructed. Capturing why the change was needed, what was approved, and the boundaries used for implementation and review gives future tooling more than executable code carries on its own while leaving the format free to evolve.

The form feels durable: every change carrying its purpose, approved direction, and decision boundaries, retrievable indefinitely. Change intent is what that form looks like today, with the tools and the intelligence level of current foundation models, structured to be a net value add to the review process rather than ceremony on top of it. The artifact will change; the goal of opening a change and understanding those decisions will not.

---

## Summary

The case for change intent is structural, not aesthetic. AI generates code far faster than humans can review it, and the gap is widening. Post-facto PR descriptions don't help — in the AI era they're often just a summary of what the AI did, and an AI reviewer can derive that from the diff. What the review process is missing is signal about whether design intent actually drove the change.

Change intent provides that signal by inverting the direction of fit: the initial intent is approved before implementation begins, and every implementation and review pass works against the current intent. The artifact has a small set of sections — *Outcomes* and *Why* always, plus *Constraints*, *Acceptance criteria*, *Invariants*, *Out of scope*, and *Amendments* when their conditions apply — and a naming convention (`change-intent/YYYY-MM-DD-short-slug.md`) that makes the merged intent discoverable via the same tools the rest of the codebase uses.

The artifact serves two downstream stages. The implementation agent uses it as a `/goal` and a decision boundary: prove each acceptance criterion, test invariant cases where useful and reason across the affected change, account for each constraint, honor the exclusions, and apply normal engineering judgment when reasonable branches are different ways to deliver the approved change. A constraint whose truth depends on production guides that judgment without becoming a proof obligation. If a claim cannot be delivered within the approved boundaries or implementation cannot continue without deciding which change will be delivered, the agent records an eligible amendment and continues. It stops only when no amendment can preserve the approved boundaries. The AI review pass independently assesses claims in the forward direction and decisions in reverse while retaining ordinary correctness, security, performance, and clarity review. It reports findings or `cannot verify` without expanding the intent into an exhaustive specification. When returned work changes the author's direction, the author replaces the current unmerged intent; retained work is reassessed and implementation and review run again against the replacement.

The discipline is designed to support workflows in which humans no longer occupy every seat, and potentially none of them. The intent author — currently a human in dialogue with the authoring skill — can be an AI orchestrator in autonomous chains, producing the same artifact for the same downstream pipeline. That's what carries the design forward into the trajectory where humans gradually exit the loop: the same semantic responsibilities and shared artifact, with different people or agents occupying the roles.

**The skill to build:** a structured-dialogue tool that assembles the author's direction into a confirmed brief, explores the affected surface, applies the change-defining test, and returns a proposed intent. The proposal batches unresolved author-owned direction into a compact attention section, records the source of every outcome, claim, constraint, and exclusion in the draft, and briefly states test feasibility and coverage limits while leaving technical latitude to implementation. The resulting intent is suitable as the goal for implementation and the basis for review. The skill is part of the mechanics package in [mechanics/](mechanics/README.md), together with the agents-file block, implementation guidance, and review guidance.

---

## Related

Change intent is one instance of a broader pattern this repository explores: [**working in public**](../working-in-public/README.md) — capturing the high-value structured work between humans and AI in artifacts that persist for future agents and humans to reference, rather than letting it die with the context window it happened in. The merged change intent preserves the approved result of that dialogue beyond the session that produced it.
