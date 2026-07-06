# Change Intent: Design and Skill Specification

## TL;DR

The goal: construct changes in a way that they're **reviewable**. Less focus on the change itself, more focus on the review process around it. By the time a change reaches a human reviewer, design intent has already driven the implementation and been verified by automated review — the reviewer knows the process the change went through and what each step already checked, so their attention goes to the judgment question *is this the right intent?* Today that means reviewing better; as the machines earn trust, it means reviewing less.

A **change intent** is a per-change artifact authored before any code is written. It captures the design intent in a form that can drive the implementation agent, can be checked against the resulting diff by an AI review pass, and remains in the repository as a persistent record. Machine verification lands a change on the human reviewer's plate already aligned with its stated intent.

This document covers the concept, the problems it addresses, the artifact's structure, how it integrates downstream, and how a skill could produce these intent documents through structured dialogue. The operational instruments that carry it into a project — skill files, prompt blocks, tool bindings — live in [mechanics/](mechanics/README.md): this document makes the argument; those files make it runnable.

---

## The Problem This Tries to Solve

AI generates code far faster than humans can review it. A competent engineer with a good model produces thousands of lines a day; human review is sequential, attention-limited, and scales roughly linearly. Humans are the bottleneck on shipping changes today, and the bottleneck will only tighten — code generation keeps accelerating while reviewer throughput stays roughly flat. The squeeze is the same on a team of two as on a team of twenty: the question is no longer how much code the team can write, but how much the team can effectively review. This work designs a change process that optimizes for the humans still in the loop today, and gets better as the AI in the loop gets better.

Just as autonomous vehicles will eventually drive themselves and we'll think nothing of it, code review will eventually be done by AI and we'll think nothing of that either. The point of a good process today is to walk us toward that future smoothly — more AI, less human, comfort accumulating along the way.

Until we're there, change intent addresses several failure modes of today's review process:

1. **Post-facto rationalization.** PR descriptions are written *after* the change is made. In the age of AI code generation, they're often just a summary of what the AI produced — and an AI reviewer can derive that summary from the code itself, so the description carries little information the reviewer doesn't already have. And because descriptions are written after, they get shaped to fit the change the author ended up with, covering what the code does but not what was intended before starting or wasn't considered along the way. Either way, reviewers get little signal about whether design intent actually drove the change. Change intent inverts the direction: intent is authored before code, the code must satisfy the intent, and the description can't retroactively absorb whatever the code did.

2. **Unconsidered cases.** Most production bugs aren't "I thought X would happen and Y happened." They're "I didn't think about case Z, and the code now does something weird in case Z." The pre-code dialogue forces the author and the AI to walk through use cases the change will touch — surfacing unconsidered ones at the only moment the author still has an unbiased view of what they wanted to do. Once code exists, the author has anchored on the implementation, and cases that weren't considered tend to stay unconsidered.

3. **Unverifiable claims.** Vague claims like "faster" or "more secure" are too abstract to use cleanly downstream — the implementation agent can't satisfy them (faster than what?) and the AI review pass can't verify them (measured how?). The review pass doesn't know a change's intent on its own; it sees the diff plus whatever context is provided. Change intent is how the intent gets communicated, with each claim specific enough that the review pass can compare the diff against it and say "met" or "not met, more work needed." Falsifiability is what makes that comparison possible.

4. **Lost context.** Commit messages are too compressed to carry the full intent of a change; they're a summary, not a record. And while AI can read git history well, most first-pass searches happen via `grep` over the working tree — which doesn't see git history at all. Change intent files live in the repository alongside the code, so they're discoverable the same way code is: a future engineer or AI grepping for a function name, an issue area, or a past concern will find the intents that touched it without walking git log.

5. **Conflation of multiple tasks.** Human reviewers today are nominally doing four jobs at once:

    - Deciding whether this is the right change to make
    - Deciding whether the implementation is the right one for that change
    - Verifying correctness — the code does what it claims
    - Verifying clarity — the code is understandable

    Only the first needs human taste. The other three are increasingly within reach of AI, and change intent accelerates that handoff: with explicit intent in hand, the AI review pass has what it needs to verify the implementation, correctness, and clarity against a stated target. The human's attention frees up for the judgment task that only they can do — and as AI gets better, the human's role on the other three recedes naturally over time.

---

## Design principles

Four principles govern this design.

**Used beats better.** A process only pays off if the team actually runs it, so the bar to start is as low as we can make it: the project's agents file explains what change intents are, the coding and review agents are made intent-aware, and the ask of a teammate is one sentence — run the change-intent skill instead of the coding harness's built-in plan mode. Change intent adds no new activity to a project. You already plan implementations; this plans one as a change intent. You already review code; code review now starts with the output of a consistent pipeline. Mechanically stronger ideas exist — structural coverage over the intent's tests, per-routine contracts, machine-checked proofs — and they are stronger precisely because they demand more: team effort, specific languages, dedicated tooling. When strength and adoption pull in different directions, this design sides with adoption.

**Diligence to agents, judgment to humans.** Rigor is cheap for an agent and expensive for a human. The agents carry the mechanical work in this design: the authoring skill reads the affected code and runs the elicitation dialogue, the implementation agent writes the tests and walks the diff for each invariant, the review agent checks the diff against the intent and any amendments. The human supplies judgment: they author the intent, they rule on any amendment when the work returns, and they decide at merge whether the change was the right one.

**Every claim is falsifiable.** An acceptance criterion can be refuted by a test; an invariant can be refuted by reasoning over the diff. Anything the pipeline is asked to verify has to be specific enough to fail.

**No adversary.** This is a workflow teams adopt for their own benefit, not a control imposed on them, so the design assumes cooperative actors. The pipeline checks compliance — agents check other agents' work at every stage — but it does not try to prove it: the authoring date is self-reported, intent-before-code is not attested, and the ledger is a receipt rather than an audit trail. The checks catch mistakes, not forgery. Proof would defend against a bad actor the design assumes away, and charge for that defense in adoption cost — the used-beats-better tradeoff again, decided the same way. Gaming the process is easy and pointless: its only output is review quality for the team running it.

---

## What an intent file contains

A change intent file is a per-change document authored **before any code is written**. One file per change, living alongside the rest of the repository — and a change is a pull request. Exactly one intent per PR: not one per local commit, and never a second intent for later rounds of edits within the same PR, which stay under the original intent (amended by its author if implementation proves it wrong). Work that seems to need two intents is two changes, shipped as two pull requests. Each section below is required when its conditions apply — `Why` applies to every change; `Acceptance criteria` applies when there's observable behavior to verify; `Invariants` applies when the change touches properties that span beyond a single test; `Out of scope` applies when there are conscious exclusions worth signaling; `Amendments` applies when implementation discovered the intent was wrong as written and it had to be repaired to deliver the change. A section being absent means there's nothing for it to hold, not that the author skipped it.

### Why

A thorough, clear paragraph (or a few) that captures the high-value context surrounding the change — the kind of reasoning a future reader (engineer or AI) couldn't reconstruct from the diff alone. The Why is written as prose, not a Q&A. The prompts below are the kinds of information to weave in, in whatever order makes sense — not a list to answer point-by-point:

- What problem is being solved?
- What triggered this change — a bug, a metric regression, user feedback, a planned migration, a product request?
- What domain context isn't obvious from the code but shapes the decision? Constraints, prior decisions, system behavior the reader needs to know.
- What tradeoffs were accepted, and which alternatives were rejected for reasons that shaped the design? "We chose X over Y because Z" — carried with its reason, so a future reader can see when Z has stopped being true and the rejection has expired with it. Alternatives that were never serious don't earn tokens here.
- What context will a future engineer (or AI) reading this a year from now need to make sense of why this happened?

This is where the high-value tokens from the pre-code dialogue land — the reasoning that wouldn't survive in a commit message and can't be recovered from the diff. Err toward including too much rather than too little; the Why is durable storage for context that's expensive or impossible to reconstruct later.

### Acceptance criteria

A list of falsifiable scenarios that must hold for the change to be **accepted**. Each one describes specific observable behavior — what a caller, user, or operator can do or see after the change ships. Each AC must be provable by a single test in principle (unit, integration, or one-shot measurement), but **at authoring time you do not name the test**. The implementation agent writes the test as part of the work; the test shows up in the transcript when it runs.

This is what authors usually have pre-code — "user calls X and sees Y," "field C appears in response D," "when E happens, metric F is emitted." Each AC is a focused scenario.

**ACs are decision criteria, not exhaustive specs.** They capture what this change introduces or alters that needs verification before accepting it. Properties covered by the project's default standards — general performance characteristics, basic style, default error handling, existing test coverage — don't need to be restated as ACs. The AC list should be sized to the change: a small or internal change may have few or no ACs; a large change may have tens or even hundreds. A short list isn't a defect any more than a long list is — what matters is whether each AC describes a claim the change is making.

The list is forward-looking. It states what the change establishes or demonstrates, not a catalog of existing behavior. If a behavior is already true and your change isn't adding or altering it, it doesn't belong here.

**Each AC must be provable by a test that ships with the diff.** If there's no integration test, unit test, or one-shot measurement that can be run against the change to demonstrate the claim, it doesn't belong here. "Cache hit rate exceeds 60% in production," for example, can't be verified at change time — production isn't running the diff when the review happens. Claims like that go in `Why` (if they're motivation) or in dashboards/runbooks (if they're operational targets), not in the intent.

**Examples of falsifiable acceptance criteria:**

Functional behavior:
- "When `UpdateUser` is called with a new email, a subsequent `GetUser` for that user returns the new email"
- "`DELETE /items/{id}` returns 204 on success; a subsequent `GET /items/{id}` returns 404"

Observability:
- "When `GET /orders` returns a 500, the `get_orders_error_rate` metric is incremented"
- "When a user is deleted, an audit log entry is written with the deleting actor's identity"

Schema / response shape:
- "`GetUser` response includes the user's email address as a top-level string field"

These are all provable by integration or unit tests; none depend on production traffic.

**Examples of claims that should be rejected:**

Too abstract — what would it even mean to uphold these?
- "GetUser is faster" — faster than what, in what scenario, by how much
- "The cache is correct" — correct in what sense

Concrete but not provable by a test that ships with the diff:
- "Cache hit rate exceeds 60% under production traffic over a rolling 24h window" — specific, but observable only after deployment
- "GetUser p95 latency drops below 10ms under 1000 RPS" — specific, but requires production-scale load to verify

Claims in the second category usually belong in `Why` (if they're motivation) or in dashboards/runbooks (if they're operational targets), not in the AC list.

#### Performance acceptance criteria

Most changes don't have performance ACs, and shouldn't. The default position is: the change is accepted under the project's general performance characteristics, and if performance regresses elsewhere, monitoring and load testing will surface it.

Include a performance AC only when **both** conditions hold:

1. The change is **performance-constrained** — performance is the reason for the change, or a specific bound is a hard requirement.
2. The measurement is **environment-independent** — it produces the same answer regardless of machine, OS, or concurrent load.

Memory allocation, allocation count, database-query count, network-call count, and algorithmic complexity (operations as a function of input size) are environment-independent and make good benchmark-style ACs. Wall-clock latency, throughput, and percentile latencies under load are environment-dependent and don't — they need different verification paths (staging load tests, production monitoring, perf regression suites), not single-test ACs.

**Examples of good performance ACs:**
- "A single `ProcessOrder` call makes at most one database query"
- "At most 10 concurrent requests can be in-flight through `ProcessOrder` at any given moment — useful for verifying bulkhead or rate-limiter patterns"

**Examples of performance claims that aren't good ACs:**
- "GetUser returns in under 10ms" — depends on machine, DB connection, concurrent load
- "Throughput exceeds 1000 req/s" — depends on hardware, parallelism, network

If your change needs an environment-dependent performance bound, that's not an AC — it's a separate verification track (benchmark suite, load test, production SLI). The intent file is the wrong artifact for that.

### Invariants

A list of properties that must hold *across* the change — properties that **can't be proven by a single test** because they span multiple call sites, code paths, or states. Read-after-write consistency across all callers, availability under failure, audit-log-on-every-mutation, thread safety across all access paths — these are invariant-shaped.

Where an acceptance criterion is closed by one passing test, an invariant requires reasoning across the diff. The implementation agent demonstrates each invariant by walking the affected code paths and confirming the property holds at each; the AI review pass independently scrutinizes the whole diff through the invariant's lens. Spot-check tests may help — they pin down specific cases — but the invariant is closed by analysis, not by any single test passing alone.

As with ACs, invariants are written at authoring time **without naming specific tests**. The shape of the claim is the contract; the implementation figures out how to verify it.

The invariants section is required when the change touches scope-spanning properties. It can be small or empty for trivial changes whose impact is fully captured by acceptance criteria. Heavier changes — concurrency primitives, mutation paths, security boundaries, cross-cutting behaviors — should have more invariants by definition, because their scope of impact is wider.

**Examples of invariants:**
- "Read-after-write: a user updated via `UpdateUser` is visible to `GetUser` across all caller paths, within the staleness window"
- "Every mutation of user data produces an audit log entry"
- "The cache layer is safe for concurrent reads and writes from multiple callers, across all access paths added by this change"
- "If the cache backend is unreachable, every code path that reads through the cache falls back to the database without surfacing the failure to callers"

Note the shape: each one reaches into the codebase beyond a single test — "across all caller paths," "across all mutation sites," "across access paths," "every code path." That's the verb invariants do. ACs don't.

### Out of scope

A list of things this change explicitly is *not* doing — work the author considered but intentionally left out. Without this section, the diff alone can't tell a reader whether something was thought about and excluded, or just never considered. Out of scope captures that distinction, turning intentional exclusion into a signal the same way the diff makes intentional inclusion a signal.

What it does:

- **Signals to the author at authoring time.** Writing an out-of-scope item often prompts "wait, should this actually be in scope?" That reflection happens before any code is written — before the implementation itself starts to bias the author's view of what the change should be.
- **Signals to the implementation agent.** These areas are excluded from the goal, so the agent doesn't drift into them while satisfying the ACs and invariants.
- **Signals to the AI review pass.** Items listed here were a conscious choice, not an oversight. The review pass doesn't flag the absence of an out-of-scope item as a defect.
- **Signals to the human reviewer.** If a related item is missing from this list and the reviewer would expect it to be considered, that's a question to ask — the author may not have thought about it.

Out-of-scope items are typically multi-sentence — enough to convey what was considered and why it was excluded. Examples:

- **Distributed cache coordination.** Single-node cache only for now. Cross-node consistency would require a separate design and a measurable need we don't yet have.

- **Cache eviction policy customization.** The library defaults work for current access patterns. We can add hooks for customization later as specific callers need different policies.

- **A batch `GetUsers` endpoint.** Considered but deferred. The dashboard would benefit from a multi-user fetch to reduce round-trips, but the auth model for batch requests needs its own design. A follow-up PR will deliver it once the auth approach is settled.

Each item is something the author thought about and explicitly excluded. Note the third example: an out-of-scope item can flag work the author has explicitly deferred. That signals to the reviewer that more work is coming, and gives a later reader the ability to check whether the follow-up actually landed.

**Why no dedicated Alternatives or Risks sections?** Two shapes common in design docs are handled differently in this artifact:

- *Alternatives considered* gets no section of its own; the load-bearing subset lives in `Why`. An alternative rejected for a reason that shaped the design — "we chose X over Y because Z" — is exactly the context a future reader can't reconstruct from the diff. Recording the reason is also the defense against anchoring: a bare list of rejected names creates gravity around old decisions, but a rejection carried with its reason expires visibly — the moment Z stops being true, the reader can see the rejection no longer applies and the decision is open for re-evaluation. What stays out is the survey: options that were never serious, comparisons that didn't shape the outcome.
- *Risks* are converted, not listed. A risk worth recording is a claim about what could go wrong — and if it can be made falsifiable, it belongs in the artifact as an acceptance criterion or invariant. "The cache might mask database failures" isn't a risk entry; it's the invariant "if the cache backend is unreachable, every read path falls back to the database." A risk that resists conversion is exactly the unfalsifiable speculation the artifact already refuses everywhere else. The review-bias concern — a listed risk becomes the reviewer's checklist, and unlisted risks get less scrutiny than fresh eyes would give them — is real but argues for conversion, not exclusion: converted risks are checked like every other claim, and the AI review pass runs its open-ended sweep blind to any author-stated framing.

What remains excluded is the residue — speculative risks that resist conversion, and alternative-surveys that didn't shape the design. Those belong in less-permanent artifacts: discussion threads, working design docs, postmortems. If the reasoning shaped the change, it's in `Why`; if it's a checkable worry, it's a claim; only what's neither stays out.

### Amendments

A ledger of repairs made to the intent during implementation — present only when the intent proved wrong as written and had to change for the change to be deliverable. Most intents never get one; an absent Amendments section means the contract held as authored. The process that produces these entries — who may amend, when, and what each amendment must leave behind — is covered in [Amending the intent](#amending-the-intent).

Each entry is one line with two required fields beyond the date:

```
- <DATE> — <WHAT: the delta, at claim granularity> — <WHY: the discovered fact that forced it>
```

The WHY must name a fact about the system, not an activity of the author — a statement that would still be true and checkable if the rest of the file were deleted. This is the same falsifiability discipline the artifact applies to acceptance criteria, pointed at the ledger:

```
Fails — activity-shaped, tells a future reader nothing:
- 2026-07-08 — AC 2 changed — ran into implementation issues

Passes — fact-shaped, verifiable against the codebase:
- 2026-07-08 — AC relaxed: revocation latency 1m → 5m — AuthMiddleware caches
  token validation for 5m with no invalidation hook
```

The ledger is a custody receipt and an index, not the story. Every semantic amendment also leaves a provenance note in the body, attached to the claim it changed — that's where a future reader actually learns why (the body-residue rule in [Amending the intent](#amending-the-intent)). The two homes serve different readers at different times: the merge-time reviewer reads the ledger top to bottom and gets complete custody in a few lines; the month-later reader reads the body and gets complete understanding without ever reaching the ledger. Neither should have to join the two against each other.

---

## File location and naming

Intent files live in a `change-intent/` folder at the repository root. Each file is named:

```
YYYY-MM-DD-short-slug.md
```

Where `YYYY-MM-DD` is the date the intent was authored and `short-slug` is a kebab-case description of the change. Examples:

```
change-intent/2026-05-16-add-getuser-cache.md
change-intent/2026-05-22-migrate-auth-to-oidc.md
change-intent/2026-06-03-fix-payment-timeout.md
```

Three design choices are wrapped up here, each worth being explicit about:

**1. The date comes first so the folder is linearly scannable.** A repository accumulates intent files over time — hundreds, eventually thousands in a long-lived codebase. Sorting by name gives you sorting by time, so a reader can scan the folder and see what happened when without digging into git history. The date is the *authoring* date, set at file creation, and never changes through review, merge, or squash.

**2. The slug is short, descriptive, and required up front.** The intent file gets its 3-6 token kebab-case slug at the moment of creation. This is intentional: if the change can't be compressed into a three-to-six-token slug, the change might be too big — break it into smaller changes, each with its own intent. The slug is essentially the commit title you'd write if you were committing — same level of compression, same level of specificity.

**3. The slug is meant to be token-rich for future discovery.** The slug list is itself a useful artifact. Someone working in a new part of the codebase, or revisiting an old one, can scan the `change-intent/` folder and find prior intents that touched the same area or addressed the same concern — then read those intents to understand the reasoning behind earlier decisions. The slug should be written with that future reader in mind: concrete nouns about what was changed, not vague verbs about effort. `add-getuser-cache` is far more useful than `cache-improvements`; `migrate-auth-to-oidc` is far more useful than `auth-refactor`.

Once its change merges, an intent file is frozen — never edited, never renamed, never deleted; it's a historical record. Before merge, the file is a live contract that can change through exactly one channel: the amendment process described in [Amending the intent](#amending-the-intent). Follow-up changes to the same area get their own file with their own date and slug; the date prefix makes the lineage visible without explicit cross-references.

---

## Why "Before Any Code"

Two reasons, both about timing.

**It's a forcing function.** The moment you try to state precisely what must hold, you discover where your thinking is fuzzy. Most software bugs aren't reasoning errors; they're cases the author didn't consider. Articulating acceptance criteria and invariants explicitly surfaces those cases at the cheapest possible time, before the code exists.

**It's the last point where the intent author is in the loop.** Once the change intent is set, the downstream agents work in narrower modes: the implementation agent thinks about *how* to satisfy the intent (write code, run tests, walk the diff for invariants), and the review pass thinks about *whether the implementation matches the stated intent*. Neither is asking "what should the change be?" — that's been settled. The downstream work is more focused and more verifiable precisely because the design question has already been answered. The intent describes the change in full — whatever isn't in the intent isn't part of this change. It's the contract between the deciding step and the doing step; once approved, the doing is on its own. If the doing discovers the contract itself is wrong — a claim that can't hold, a forced behavior the intent takes no position on — the remedy is a recorded amendment ([Amending the intent](#amending-the-intent)), not silent discretion.

This split also separates the two cognitive tasks that get conflated in normal code review:

1. **Deciding what should be true** — high-judgment work
2. **Verifying that code matches what should be true** — mostly mechanical work

Change intent splits the work so each gets done by the right agent at the right time.

### The intent author doesn't have to be a human

Everything in this design works if an AI orchestrator fills the dialogue role instead of a person. The orchestrator brings the intent, the authoring skill brings the structure and rigor, the result is a change intent file ready for the implementation phase — same artifact, same downstream pipeline.

This is what lets the discipline carry forward into the autonomous trajectory. As humans gradually exit the loop (the Waymo-style arc described at the top of this document), the artifact and process don't change: the orchestrator-implementer-reviewer chain runs end-to-end without a human, each step a different agent with a different job, the change intent file the contract between them. The skill that elicits intent from a human today is the same skill that elicits intent from an orchestrator later — same dialogue shape, same artifact, same pipeline.

---

## Amending the intent

"Before any code" doesn't mean the author knows everything before starting — implementation is contact with reality, and reality sometimes proves the intent wrong. The design absorbs this with one principle: **immutability attaches at merge time, not authoring time**. Before merge, the intent is a live contract that can be repaired through the process below. After merge, it is frozen history.

### The necessity test

The amendment channel exists to repair a wrong intent, not to improve a good one. An amendment is justified only when **the change cannot be correctly delivered under the intent as written** — when the contract and the deliverable cannot both hold. Exactly two triggers meet the test:

1. **A claim is falsified.** An acceptance criterion or invariant cannot hold as written, for a discoverable reason. The amendment relaxes or replaces the claim.

2. **The scope is unsatisfiable.** The change necessarily produces observable behavior the intent takes no position on, so no implementation can deliver the change and pass the bidirectional scope check. This is the only door for adding acceptance criteria or invariants mid-implementation, and it is narrow: the behavior must be *forced by the change*, not adjacent to it. In the worked example below, caching `GetUser` unavoidably either caches missing-user lookups or doesn't — the intent must say which. "The admin endpoint could also use pagination" does not qualify; nothing about the change forces it.

Everything else — better ideas, opportunistic hardening, adjacent fixes, "while we're in here" — is not an amendment. A discovery that would *improve* the change is a seed for the next change intent: its own file, own date, own slug, own deciding moment. The pressure that would otherwise bloat the amendment channel gets redirected into the artifact system, and the deferred idea stays discoverable in `change-intent/` instead of dying as a rejected request.

### Who amends: the agent, on the record

Amendments are the exception, not a phase of every change — the authoring dialogue exists to make them rare, and most intents merge exactly as approved. If implementation proves a claim wrong, the implementation agent amends the intent itself. The author is unlikely to ever write this file by hand: the authoring skill writes it during the dialogue, and the implementing agent repairs it during implementation.

The channel exists because an agent that discovers a wrong claim mid-implementation, with no sanctioned way to repair it, fails in predictable ways: it fabricates success, drifts past the problem silently, or stalls. Amendment preempts all three by sanctioning the correct move — change the claim, record what changed and the fact that forced it, keep working. Work on unaffected claims never stops.

Nothing changes invisibly. The intent as the author approved it, plus its amendment entries, fully determines the final text — the review pass checks exactly that — so the author reviewing the returned work sees what they approved and what bent, at claim granularity.

The author still rules on every amendment — at review rather than mid-implementation. When the work comes back, the author reads the Amendments section and accepts or rejects each repair; a rejected amendment sends the change back for rework. Moving the ruling to review has a known cost: a repair the author would have decided differently is discovered after the work is done, not before. The design accepts that cost deliberately — rework is cheap for an agent, and stopping mid-implementation to wait on a decision is expensive for everyone — and states it here so a future reader doesn't reintroduce mid-implementation approval as a fix.

One boundary stays hard: an amendment repairs a deliverable change. If no repair can deliver it — the change itself no longer makes sense — that is not an amendment; the agent stops and reports. Amendment sanctions repairing the contract, not redefining the mission.

Two supporting rules keep the channel quiet and enforceable:

- **Discretion is granted inside the contract, not exercised as amendments to it.** If a detail is genuinely the implementation's call, the intent says so up front ("TTL may be anywhere in 10–60s, implementation's choice"). Bounded discretion written into the approved text is exercised silently; the amendment channel is reserved for claims the contract got wrong.
- **The review pass checks the record mechanically.** The final intent must be exactly the approved intent plus its amendment entries: every change to the text traces to an entry naming the discovered fact, and every semantic amendment leaves a discovery note next to the claim it changed. An intent modified without a matching entry is a process defect that bounces the change — same severity as a failing acceptance criterion. Per the no-adversary principle, this check catches mistakes, not forgery: the failure mode is an agent that repaired the text and forgot the record, not one gaming the process.

### What an amendment leaves behind

Every amendment has two components with different lifespans. The **decision** — claim changed from X to Y — has its residue in the final text itself and needs only a one-line ledger entry as a receipt. The **discovery** — the fact about the system that forced the change — is durable knowledge, and usually the most valuable tokens in the file: it is both non-obvious (it was missed at authoring time) and empirically verified (learned by contact with the code, not speculated). The discovery gets folded into the body, next to the claim it affected.

Concretely, an amendment produces:

- **A ledger entry** in the [Amendments](#amendments) section: `<DATE> — <WHAT> — <WHY>`, with the WHY naming the discovered fact.
- **Body residue, required for every semantic amendment.** A provenance note attached to the changed claim — one to three sentences carrying the mechanism and its forward-looking implication, marked as discovered during implementation. The marker is signal, not decoration: it tells a future reader the fact was non-obvious and paid for. Wording-only amendments are exempt; they have no WHY worth carrying. The review pass rejects a semantic amendment whose WHY exists only in the ledger.
- **For relaxations, residue in two places.** When a claim is weakened and the original strength is deferred rather than abandoned, the residue lands on the weakened claim *and* as an Out of scope entry recording the deferral. The pairing keeps a relaxation from silently becoming the permanent state of the world — a future reader can check whether the follow-up ever landed.

The result reads coherently for both readers the file serves. The merge-time reviewer reads the ledger and gets complete custody in a few lines — what changed since signing, and why. The month-later reader reads the body and gets complete understanding without reaching the ledger — the intent as if authored by someone who knew everything known at merge time, with the discoveries marked in place.

This is not the post-facto rationalization the design warns against. The sin of post-facto writing was never that it is written late — it is that it erases the gap between what was intended and what happened. An amended intent preserves the gap at claim granularity in the ledger and marks each discovery where it lives. A traditional PR description hides the journey by never having recorded a destination; an amended intent recorded the destination, marks where the route changed, and hands the reader the map with the detours labeled.

### Why rarity is load-bearing

Amendments should be rare, and the design leans on that rarity three ways:

- **Every amendment is a decision made under anchoring.** The argument for "before any code" is that it is the only moment the author has an unbiased view. An amendment reopens the deciding question after implementation has started shaping everyone's view of the change. Sometimes that is unavoidable — reality falsified the plan, and re-deciding with better information is the process working — but it is never free. A process where amendments are routine is a process where deciding happens continuously during implementation: the pre-intent world, rebuilt with extra paperwork.
- **Rarity is what earns each amendment the author's full attention.** When amendments appear only on falsification, an Amendments section on a returned change is a signal worth reading carefully. If amendments appeared for every nice-to-have, the author would learn to skim them — and a skimmed Amendments section carries no signal at all.
- **Amendment count becomes a diagnostic.** Every amendment marks a spot where confusion was confirmed in practice — the author, the authoring dialogue, and the surface read all missed something that reality then surfaced. One or two entries is reality doing its thing. Six entries on a small change points at the elicitation (the dialogue missed real interactions with the touched surface) or at the code itself (the area is genuinely hard to reason about). Either way the signal is actionable: a surface that accumulates amendments across changes has earned extra scrutiny in review passes, and a deeper authoring pass the next time a change touches it.

---

## How It Integrates Downstream

The change intent has three downstream consumers. The implementation agent uses it as a *goal* — a completion condition to work toward. The AI code review pass uses it as a *contract* — checking the resulting diff against what was claimed. The human reviewer uses it as *evidence of the process* — confirming the design question was settled before code was written and seeing exactly what context the AI agents had. Each consumer adds verification of a different kind, and the same artifact passes through every hand — a chain of custody running from the intent author to the merge decision. By the time the human engages, they don't need to wonder what was looked at or what wasn't.

### Implementation phase: the intent as the `/goal` condition

Claude Code shipped `/goal` in v2.1.139 (May 2026). It lets a user set a completion condition and have the implementation agent keep working autonomously across turns until that condition is met. After each turn, a separate evaluator model (Haiku by default) reads the conversation transcript and decides whether the condition holds. If yes, the goal clears. If no, the agent continues with the evaluator's reason as guidance for the next turn.

**Key architectural detail:** the evaluator only sees what's surfaced in the conversation. So the condition must be something the implementation agent can prove through its own output — tests passing, builds clean, benchmarks meeting targets, files matching some shape. The evaluator can't run commands itself.

A change intent file is naturally shaped to be a `/goal` condition. The acceptance criteria and invariants together form the completion condition, and the implementation agent's job differs slightly for each:

- **For each acceptance criterion**: write a test that exercises the scenario, run it, and surface the passing result in the transcript. The test is the agent's own work; the AC didn't name it.
- **For each invariant**: write spot-check test(s) for specific cases *and* walk the diff to confirm the property holds at every site where it could be violated. The spot-check passing doesn't close the invariant — the agent has to demonstrate, in the transcript, that it has considered the property at every relevant site.
- **If it discovers the intent is wrong** — a claim that can't hold, or forced observable behavior the intent takes no position on — the agent neither fabricates the claim nor drifts past it: it amends the intent on the record ([Amending the intent](#amending-the-intent)) — the claim changed, an amendment entry added, a discovery note left on the claim — and keeps working against the amended contract.

The in-loop evaluator checks the transcript for both kinds of evidence each turn. It's a fast first pass; the more reliable check — particularly on invariants — happens next.

### Review phase: the intent as the AI reviewer's target

After the goal clears, an AI code review pass runs against the resulting diff with the change intent as context. The review pass validates four things on top of the standard checks you'd expect:

1. **Is the intent itself well-described?** Are claims falsifiable, are all relevant categories addressed, is the scope clearly bounded? A vague or incomplete intent is a defect in its own right and should bounce the change back before the diff is even examined.
2. **Does the diff match the intent?** Every acceptance criterion is exercised by a test in the diff, that test passes, and it would fail if the claim were false — a test that can't fail proves nothing. Every invariant holds across the diff — not just where the spot-check tests assert it, but at every site where the property could be violated. The review pass's work on invariants is the heaviest single thing it does: scrutinize the whole diff through each invariant's lens. Nothing externally observable shows up in the diff that isn't covered by the listed claims or the "out of scope" section.
3. **Does the change contradict any prior intent?** The review pass searches the `change-intent/` folder for past intents that touched related surface and flags apparent contradictions — e.g., an older intent established a strong consistency guarantee and this change appears to weaken it without acknowledging the prior claim. This is the right place for that check: the review pass pays the cost of loading prior context once, instead of forcing every author to enumerate prior invariants up front.
4. **Was every amendment recorded?** This check is executable because the approved intent is a commit on the change's branch: the review pass diffs the intent file from its approval commit to its final state, and every change must trace to an amendment entry naming the discovered fact, with every semantic amendment leaving a discovery note next to the claim it changed. A change to the file with no matching entry is a process defect that bounces the change ([Amending the intent](#amending-the-intent)). Amendments also get the review pass's particular scrutiny: each is a decision made during implementation that no one has reviewed yet, at a spot where the intent already proved wrong once.

The would-fail clause in check 2 exists because the pipeline grades its own homework. The implementation agent writes the code, writes the tests that prove its acceptance criteria, and produces the only transcript the in-loop evaluator sees — so a test that exercises the scenario while asserting almost nothing clears the goal, and nothing inside the loop can tell. The review pass is the first layer that holds the diff and has no stake in the goal clearing. Reading each AC test with the claim in hand — break the behavior, confirm the test catches it — is a check the loop cannot run on itself.

This is independent from and stronger than the in-loop `/goal` evaluator. The evaluator is a fast Haiku pass over a transcript; the review pass is a slower, stronger model with access to the full diff, the repository, and the history of prior intents. It also runs the usual review checks — concurrency hazards, security boundaries, error handling, comment clarity — but now with the intent as additional context shaping what to focus on.

### Human review: the intent as evidence of the process

After both machine layers approve, the change lands on a human reviewer's plate. The change intent serves them differently from how it served the AI agents: it's evidence that the design question was settled before code was written, that the implementation agent worked from a stated intent, and that the AI review pass had that intent as context for its checks. The human reviewer doesn't need to wonder what the AI agents had in front of them — the intent file is the record, sitting in the repository alongside the change.

This is the record paying out. The reviewer knows what the intent author settled, what the implementation agent built toward, and what the review agent validated — not because they watched it happen, but because every change in the project goes through the same steps. A teammate's change reads the same as their own. On the rare change that carries an Amendments section, those entries are the highest-signal lines in the file: each is a judgment call made during implementation that the author has not yet seen. What's left is the one task only a human can do: deciding whether this was the right change to make. The intent everything was checked against is right there in the file.

### Workflow

1. Human (with skill assistance) produces a change intent file at `change-intent/YYYY-MM-DD-slug.md`
2. Implementation phase: `/goal` with the acceptance criteria and invariants as the condition. Agent writes code, runs tests, demonstrates each acceptance criterion, and walks the diff to confirm each invariant. In-loop evaluator (Haiku) confirms each turn. In the rare case the agent discovers the intent cannot be delivered as written, it amends the intent on the record and keeps working.
3. When the goal clears, the AI code review pass runs against the diff with the intent as context, validates intent quality and intent-vs-diff alignment (with particular scrutiny on invariants), and runs standard review checks.
4. Once the review pass approves, the change reaches a human reviewer. Any amendments are the highest-signal part of the returned work — judgment calls no one has yet reviewed. Beyond those, the reviewer focuses on the judgment question — *is this the right intent?* — not on verifying the code matches it (that has already been checked twice).

### Sample `/goal` invocation

```
/goal All acceptance criteria and invariants in change-intent/2026-05-16-add-getuser-cache.md are demonstrated in this transcript:
- Every acceptance criterion is exercised by a test the agent wrote, and the test passes
- Every invariant has its spot-check tests passing AND the agent has walked the diff to confirm the property holds at every site where it could be violated
- The change does not introduce externally observable behavior outside the listed claims and the "out of scope" section
```

The last line is the **bidirectional check** at the change level: not just "did the agent prove what it was supposed to," but "did the agent stay within scope." This check runs both in-loop (Haiku, fast) and again in the AI review pass (stronger model, full diff visibility). The in-loop pass is a fast first cut; the review pass is the more reliable gate. Whether the Haiku evaluator alone can reliably catch out-of-scope behavior is an open question — see Design Tensions below.

---

## The Authoring Skill

The skill produces a change intent file through structured dialogue with the intent author — a human today, possibly an AI orchestrator in autonomous chains. The intent author owns the macro intent (what the change should accomplish); the skill helps make that intent rigorous, complete, and falsifiable. The workflow below uses "human" as the dominant case, but every step works the same when the intent author is an orchestrator.

**Critical constraint:** the skill **never** invents acceptance criteria or invariants for code that doesn't exist yet. The change hasn't been made. The skill's role is to read the affected surface, surface what currently holds there, and use that context to ask sharper questions about what the change should establish. The intent author is the source of intent; the skill is the source of context. The file itself only states forward-looking claims — what the change will prove — not a catalog of preserved behavior.

### Workflow

**Step 1: Human seeds the intent.**

The human says what they want to do at whatever level of specificity they have. Vague seeds are accepted ("speed up GetUser") but trigger more pushback. Precise seeds ("add a 30-second TTL cache to GetUser using the existing CacheManager interface") move faster through the workflow but still get the full category check.

If the seed is too vague to act on at all, the skill's first move is to refuse to proceed and push for specificity: "What does 'faster' mean? What's the current latency? What's the target? What can you trade off to get there?" The skill should not start enumerating invariants against an undefined target.

**Step 2: AI reads the existing relevant surface.**

Given the seed, the AI identifies the code likely to be affected and enumerates what currently holds:

- Type signatures and error contracts
- Concurrency patterns (locking, message passing, spawning of concurrent work)
- Existing invariants documented in doc comments
- Call sites — who depends on this code and how
- Existing tests — what's currently verified
- Performance characteristics where measurable
- Similar patterns elsewhere in the codebase (e.g., other services using the same caching approach)

This is the AI's primary contribution: it brings knowledge of the current codebase that the human doesn't carry in their head.

**Step 3: AI proposes a baseline of what's currently true.**

The AI presents an enumeration: "Here's what the existing code guarantees that your change will interact with." This grounds the conversation in reality. The human now has a concrete list to react to rather than a blank page to fill.

**Step 4: Elicit acceptance criteria first.**

The AI asks the human what they already know about the change pre-code — the AC-shaped knowledge that's natural at this stage. The questions cover the breadth of what an AC can capture:

- *Functional:* "What does the caller / user / operator see? What scenario do they exercise?"
- *Observability:* "When something happens, what metric, log, or audit entry should be emitted?"
- *Schema:* "What new fields, endpoints, or response shapes does this introduce?"
- *Performance (only if perf-constrained):* "Is there an environment-independent bound — memory, query count, complexity — that must hold?"

Each candidate AC gets pushed for specificity: is the scenario concrete enough that someone could write a test against it without further questions?

This step is fast and productive because the human typically has this content ready. The skill's job is mostly to sharpen: turn "user can update their email" into "when `PATCH /users/me` is called with a new email, a subsequent `GET /users/me` returns the new email." Note what's missing: no test name. The test gets written at implementation time. The AC is the scenario, not the test.

The skill pushes back on:
- Vague claims ("faster," "more secure") that don't describe an observable scenario — sharpened or removed
- Production-traffic claims ("hit rate >60% in prod") — moved to `Why` or dropped
- Environment-dependent performance claims ("returns in under 10ms") — replaced with env-independent measures if the change is perf-constrained, dropped otherwise
- Properties already covered by the project's defaults — kept out of the AC list to avoid bloat

**Step 5: Elicit invariants from the surface.**

Using what the AI read in step 2, the skill now asks property-shaped questions that the human likely couldn't have come up with on their own:

- "AuditLog reads through GetUser. Your change introduces a staleness window. Is staleness acceptable for audit, or does this caller need a different guarantee?"
- "GetUser is called from four services with different consistency needs. Across all of them, what's the invariant — read-after-write, eventual, something in between?"
- "The cache touches a shared map. Under concurrent calls, what must hold across all access paths?"
- "If the cache backend fails, what must still hold for callers?"

Each candidate invariant must describe the property specifically enough that the implementation agent can walk the diff and verify it. As with ACs, no test names at this stage — the implementation will add spot-check tests as it works, and the invariant is closed by reasoning over the diff at implementation and review time, not by any single test passing. For trivial changes this step often produces zero or one invariants, and that's fine. For changes touching concurrency, mutation paths, security boundaries, or cross-cutting properties, this step is where the file gets its weight.

**Step 6: Categories pushed proactively.**

The AI ensures the human has addressed every category that applies to the touched surface:

- Concurrency / thread safety
- Error handling and propagation
- Observability (logs, metrics, tracing)
- Security boundaries
- Audit / compliance
- Performance
- Backward compatibility (API, on-disk format, wire protocol)
- Resource cleanup (file handles, connections, background tasks)
- Failure modes (what happens when dependencies fail)

The human can declare any category "not applicable" but they have to declare it explicitly. Silence isn't an answer.

**Step 7: Falsifiability enforced on every claim.**

Vague claims get pushed back until they describe specific observable behavior. The AI does not accept "faster," "more secure," or "backwards compatible" as standalone claims. Each must be made precise: what scenario, what behavior, observable how. The test that proves it doesn't have to exist yet — but the claim has to be specific enough that the implementation agent could write the test from the claim alone.

If the human can't make a claim falsifiable, that's a signal the claim isn't well thought out and should be removed or replaced with what the human actually means.

**Step 8: Convergence.**

When every relevant category has an explicit position and every claim is falsifiable, the AI writes the change intent file to `change-intent/YYYY-MM-DD-slug.md` and presents it for final review. If the human approves, the artifact is signed and the implementation phase begins. From that point until merge, the intent changes only through the amendment process ([Amending the intent](#amending-the-intent)); at merge it freezes for good.

### Depth calibration

Not every change deserves a fifteen-page intent file. Depth should scale with risk, detected from the existing code:

- **Light pass**: 2-5 acceptance criteria, zero or one invariants, single category. Leaf utility, pure helper, isolated refactor.
- **Medium pass**: 5-10 acceptance criteria, 1-3 invariants, multiple categories. Typical feature work touching one or two services.
- **Deep pass**: many acceptance criteria, multiple invariants, all categories covered. Changes to concurrency primitives, public APIs, security-relevant paths, hot paths, mutation paths — anything that historically required care.

The risk profile comes from the existing code, not the proposed change (which doesn't exist yet). If the touched surface has historically required care, the skill pushes deeper regardless of how casually the human stated the intent.

### Stopping condition

The skill is "done" when:

- Every category flagged as applicable has either an explicit position or an explicit not-applicable
- Every claim is falsifiable
- The human signs off on the produced artifact

Without an explicit stopping rule, elicitation either runs forever or stops too early.

---

## Worked Example

**Human seed:** "Add caching to UserService.GetUser to reduce database load."

**AI reads relevant code and finds:**
- `GetUser(userID)` returns the user, or nil for users that don't exist
- Documented as safe for concurrent use
- Called by PaymentService, AuthService, AuditLog, NotificationService
- No existing cache in this service
- Similar caching pattern exists in `OrderService` using `CacheManager` interface

**AI presents baseline and conducts elicitation.** After dialogue, the produced file at `change-intent/2026-05-16-add-getuser-cache.md`:

```markdown
## Why
GetUser is read-heavy (40k req/s peak). P95 latency is 80ms, dominated by 
the DB round-trip. Adding a 30-second TTL cache should drop P95 below 10ms 
on cache hits and reduce DB load by ~70% based on access patterns in 
production traces. The 30s TTL aligns with the staleness budget product 
approved for user profile data. AuditLog, the one caller that needs 
immediate consistency, is migrated to a new GetUserUncached method.

## Acceptance criteria
- On a cache hit, `GetUser` returns the cached value without querying the database
- On a cache miss, the `cache_misses` counter is incremented; on a hit, `cache_hits` is incremented
- `GetUserUncached` returns fresh data from the database on every call, never reading from the cache
- When `UpdateUser` is called with a new email, a subsequent `GetUser` for that user returns the new email within 30 seconds

## Invariants
- Read-after-write: across all caller paths through `GetUser`, no caller sees data older than 30 seconds after an `UpdateUser` for that user
- The cache layer is safe for concurrent reads and writes from multiple callers, across all access paths added by this change
- If the cache backend is unreachable, every code path that reads through the cache falls back to the database without surfacing the failure to callers

## Out of scope
- **The cache implementation itself.** Using the existing CacheManager interface; no new caching primitives are introduced.
- **Eviction policy customization.** CacheManager defaults (LRU with a 100k entry limit) are sufficient for the access patterns we've measured.
- **Distributed cache coordination.** Single-node cache only. Cross-node consistency would require a separate design and isn't justified by current request volume.
- **A dedicated API for cache inspection or invalidation.** Not included here. A follow-up PR will add inspection endpoints once production data shows whether on-demand invalidation is needed.
```

**A mid-implementation amendment.** While wiring the cache, the implementation agent hits a fact the intent takes no position on: `GetUser` returns nil for users that don't exist, and the change must either cache those negative results or not. Either choice is observable — caching negatives means a just-created user can stay invisible for up to 30 seconds to any caller that looked them up pre-creation; not caching them means missing-user lookups always hit the database. This meets the necessity test (the scope is unsatisfiable as written), so the agent amends on the record: it chooses not to cache negatives — user-creation flows read right back after creation, and missing-user traffic is negligible — and the intent gains one acceptance criterion and one amendment entry:

```markdown
## Acceptance criteria (addition)
- A `GetUser` for a nonexistent user is never served from the cache: a user
  created immediately after a missing lookup is returned by the next `GetUser`
  call. *(Added during implementation: `GetUser` returns nil for missing
  users, and the intent took no position on caching negatives — caching them
  would leave a just-created user invisible for up to the TTL.)*

## Amendments
- 2026-05-19 — AC added: missing-user lookups never cached — `GetUser`
  returns nil for nonexistent users; caching negatives would delay visibility
  of newly created users by up to the TTL
```

Implementation continues against the amended contract. At review, the intent author weighs the amendment — accept the repair, or send the change back for rework.

The implementation agent takes this file as the `/goal` condition. For each acceptance criterion, the agent writes a test that exercises the scenario, runs it, and surfaces the passing result. For each invariant, the agent writes spot-check test(s) for specific cases *and* walks the diff to confirm the property holds at every site where it could be violated — every caller path of `GetUser` for the read-after-write window, every access path into the cache for thread safety, every cache-read code path for the backend-unreachable fallback. The in-loop evaluator checks the transcript for both kinds of evidence.

When the goal clears, the AI code review pass takes the diff with this intent as context. It validates the alignment under a stronger model — with particular scrutiny on invariants, where the review pass walks the whole diff through each invariant's lens — searches the `change-intent/` folder for prior intents that might be in tension with this one, and runs the standard checks (concurrency, errors, security, clarity). Only then does the change reach the human reviewer — who focuses not on the code itself but on whether the intent captured here was the right one to ship.

---

## Design Tensions

A few areas where the design is not fully resolved and worth flagging for implementation:

### Bidirectional scope-check by evaluator

Whether the Haiku evaluator can reliably detect "the agent did something not claimed in the intent" is an open question. The simple direction (every claim demonstrated) is easy to check. The hard direction (no unclaimed behavior) requires understanding the diff and comparing it to the scope, which may exceed Haiku's reliability. Reviewing better comes free with the artifact; reviewing less is earned by this check. Options to explore:

- Make the constraint very explicit in the goal prompt and rely on Haiku's pattern-matching
- Add a separate analysis pass before evaluator review
- Use a stronger model for this specific check
- Have the implementation agent itself produce an "evidence summary" the evaluator checks against

### Cold start on existing codebases

Untouched code has no documented invariants. The AI's enumeration of what currently holds — used in the authoring dialogue to sharpen the human's claims — is partly inferential and may miss real interactions the change will have. The file itself only states forward-looking claims, so this affects elicitation quality more than file correctness, but a missed interaction can still produce a change intent that doesn't ask the right questions.

### Scoping the past-intent search

The review pass searches prior change intents to flag contradictions with the current change. In a mature repository this is potentially thousands of files. The pass can't load them all on every review. Options to explore: filter by file/package overlap with the current diff, embedding search over intent contents, time-window restrictions, or a combination. Picking a strategy that's both cheap and high-recall is a real engineering question, not a free check.

### Spike-then-formalize

Exploratory work doesn't fit this model — you don't know the right invariants until you've tried something. The skill should support a "draft mode" that produces tentative invariants for spike work, with full discipline applied when the change moves toward merge. Forcing full intent rigor on exploratory code will kill the practice.

### Cross-cutting invariants

The change-level intent captures invariants on the touched surface, but some properties are system-wide ("every mutation of user data produces an audit log entry"). These need a separate registry that the intent can reference. Not covered by this document, but worth flagging that the macro intent layer is not the complete invariant story.

### Method-level invariants are separate

This document covers only the macro layer — change-scoped, human-authored (with AI assistance). There is a complementary system for method-level invariants: pedantic, AI-maintained annotations in doc comments paired with named tests, enforced by a linter, consumed by an AI-only reviewer. That system handles the micro layer. The two layers compose in the broader review pipeline but are designed independently. Method-level invariants are **out of scope** for this document and this skill.

### Open artifact questions

Three questions surfaced while specifying the mechanics ([mechanics/](mechanics/README.md)), parked here because they change the artifact or the protocol, not the prompts:

- **Should invariants carry their blast radius?** The authoring surface read finds the caller list; the intent file currently drops it. Checking a named list is verifiable; regenerating the list is where an implementation agent silently drops a site.
- **Where does the authoring surface read persist?** It is evidence the review pass consumes — caller lists, existing guarantees, prior intents on the same surface — so its home is part of the artifact spec.
- **What about claims that are true but unprovable in this repository?** An acceptance criterion whose proving test can't be written in the project's harness is neither a falsified claim nor unsatisfiable scope; the necessity test has no door for it. Either an authoring-time feasibility check closes the gap, or the amendment protocol needs a third trigger.

---

## Where this is heading

A change is the package of the work that produced it — the decisions, the intent, the falsifiable claims, the consciously-excluded scope — bundled with the code itself. An AI or future engineer should be able to almost hermetically open a single merged change and reconstruct it: the what, the why, the tradeoffs that were accepted, all the important tokens that went into producing the change saved alongside it.

That's the deeper claim. Change intent is one expression of it, scoped to 2026 tools.

What this looks like a year or two from now is probably different. Code review may not use git as the substrate. Intent may be captured through richer interactions than markdown files. The specific conventions here will evolve.

We don't have to be exactly right about the future to be directionally right. The asymmetry that matters: information saved now can be reshaped into whatever future tooling needs; information that wasn't saved can't be reconstructed. As long as we capture the substance — the work, the decisions, the intent that went into the change — the format can adapt to whatever future review processes look like. The conviction underneath is that the future will want a lot more information about each change than the executable code carries on its own.

The form feels durable: every change carrying the structured reasoning that produced it, retrievable indefinitely. Change intent is what that form looks like today, with the tools and the intelligence level of current foundation models, structured to be a net value add to the review process rather than ceremony on top of it. The artifact will change; the goal of opening a change and getting into the mind of what produced it will not.

---

## Summary

The case for change intent is structural, not aesthetic. AI generates code far faster than humans can review it, and the gap is widening. Post-facto PR descriptions don't help — in the AI era they're often just a summary of what the AI did, and an AI reviewer can derive that from the diff. What the review process is missing is signal about whether design intent actually drove the change.

Change intent provides that signal by inverting the direction of fit: intent is authored before code, the code must satisfy the intent, and the implementation can't retroactively absorb whatever happened to get built. The artifact has a small set of sections — *Why* always, plus *Acceptance criteria*, *Invariants*, *Out of scope*, and *Amendments* when their conditions apply — and a naming convention (`change-intent/YYYY-MM-DD-short-slug.md`) that makes it discoverable forever via the same tools the rest of the codebase uses.

Once authored, the same artifact does work at two downstream stages. The implementation agent treats it as a `/goal` condition: a passing test for every acceptance criterion, a walk over the diff for every invariant, and a refusal to drift outside the listed scope. In the rare case implementation proves the intent wrong — a falsified claim, a forced behavior the intent didn't cover — the agent amends on the record rather than fabricating or stalling: the Amendments section records what changed and the fact that forced it, the author rules on every amendment at review, and the intent freezes at merge. The AI review pass treats it as a contract: it confirms the intent is itself well-described, that the diff matches it, and that the change doesn't contradict prior intents in the same area. By the time the change reaches a human reviewer, machines have already verified that the implementation matches the stated intent — the human arrives knowing what was settled, what was built toward, and what was checked. Their attention goes to the four-task model's only judgment task, *is this the right change to make,* while the other three (implementation choice, correctness, clarity) recede onto the AI at the pace the machines prove reliable — no faster.

The discipline is built to work without humans entirely. The intent author — currently a human in dialogue with the authoring skill — can be an AI orchestrator in autonomous chains, producing the same artifact for the same downstream pipeline. That's what carries the design forward into the trajectory where humans gradually exit the loop: same dialogue shape, same artifact, same review process, just different agents in the role.

**The skill to build:** a structured-dialogue tool that takes a seed intent, reads the affected code surface, walks the intent author through acceptance-criteria elicitation, then invariant elicitation, then category coverage, and refuses to settle for unfalsifiable claims. The output is a change intent file ready to drive implementation and pass review. That skill ships as part of a small mechanics package — an agents-file block, the authoring skill, an implementation reference, and a review skill — stubbed in [mechanics/](mechanics/README.md). The design stays out of the prompt-level engineering those instruments carry; they stay out of the argument this document makes.

---

## Related

Change intent is one instance of a broader pattern this repository explores: [**working in public**](../working-in-public/README.md) — capturing the high-value structured work between humans and AI in artifacts that persist for future agents and humans to reference, rather than letting it die with the context window it happened in. The pre-code dialogue here produces high-value tokens; the change intent file is how those tokens get preserved beyond the session that produced them.
