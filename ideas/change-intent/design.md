# Change Intent: Design and Skill Specification

## TL;DR

A change intent is a structured document authored by a human (with AI assistance) **before any code is written** for a change. Each change gets its own intent file. The file captures *why* the change is being made, *acceptance criteria* (falsifiable claims each provable by a single test), and *invariants* (properties that span the change and require reasoning over the diff to close).

The same document then serves two downstream roles. First, it's the completion condition for the implementation agent (e.g., Claude Code's `/goal`), giving the agent a verifiable target to work toward. Second, it's the contract an AI code review pass checks the resulting diff against — before the change ever reaches a human reviewer. The human reviewer then receives a structured artifact, machine-verified evidence the diff matches it, and can spend their attention on the judgment question — *is this the right intent?* — rather than redoing the verification work.

This document explains the concept, the problems it addresses, how it integrates with the implementation and review phases downstream, and how a Claude Code skill could produce these intent documents through structured dialogue.

---

## The Problem This Tries to Solve

AI generates code far faster than humans can review it. A competent engineer with a good model produces thousands of lines a day; human review is sequential, attention-limited, and scales roughly linearly. Humans are the bottleneck on shipping changes today, and the bottleneck will only tighten — code generation keeps accelerating while reviewer throughput stays roughly flat. This work designs a change process that optimizes for the humans still in the loop today, and gets better as the AI in the loop gets better.

Just as autonomous vehicles will eventually drive themselves and we'll think nothing of it, code review will eventually be done by AI and we'll think nothing of that either. The point of a good process today is to walk us toward that future smoothly — more AI, less human, comfort accumulating along the way.

Until we're there, change intent addresses several failure modes of today's review process:

1. **Vague intent.** Most PRs today are accompanied by a one-line description and a 400-line diff. Reviewers (human or AI) have to infer the author's intent from the code itself. Change intent inverts this: intent is authored explicitly and the code is verified against it.

2. **Silent invariant breakage.** Most production bugs aren't "I thought X would happen and Y happened." They're "I didn't think about case Z, and the code now does something weird in case Z." Forcing the author to enumerate what must remain true surfaces these cases before code is written.

3. **Unverifiable claims.** Vague claims like "faster" or "more secure" can't be checked. Change intent requires every claim to be falsifiable — measurable, verifiable by a test or analysis the implementation agent can run.

4. **Lost context.** PR descriptions get lost in commit history. The change intent lives in the repository itself, structured enough that a future engineer (or AI) reading it months later can understand why the change was made and what tradeoffs were accepted.

5. **Conflation of two tasks.** Human reviewers today are nominally doing two jobs simultaneously: deciding whether the change is the right change to make, and verifying that the code matches the intent. Change intent separates these so each can be done by the right kind of agent: humans focus on intent correctness, machines focus on implementation fidelity.

---

## What Change Intent Is

A change intent file is a per-change document authored **before any code is written**. One file per change, living alongside the rest of the repository.

### File location and naming

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

**2. The slug is short, descriptive, and required up front.** When the author invokes the skill to create the intent file, they have to pick the slug right then. This is intentional: if you can't describe your change in five to ten words at the moment you're about to write the intent, you don't yet know what you're doing and shouldn't be starting. The slug is essentially the commit title you'd write if you were committing — same level of compression, same level of specificity.

**3. The slug is meant to be token-rich for future discovery.** The slug list is itself a useful artifact. Someone working in a new part of the codebase, or revisiting an old one, can scan the `change-intent/` folder and find prior intents that touched the same area or addressed the same concern — then read those intents to understand the reasoning behind earlier decisions. The slug should be written with that future reader in mind: concrete nouns about what was changed, not vague verbs about effort. `add-getuser-cache` is far more useful than `cache-improvements`; `migrate-auth-to-oidc` is far more useful than `auth-refactor`.

Once a file exists, it is never renamed and never deleted — it's a historical record. Follow-up changes to the same area get their own file with their own date and slug; the date prefix makes the lineage visible without explicit cross-references.

---

The remaining subsections describe what goes inside the file. Two sections are always required (`Why`, `Acceptance criteria`). A third (`Invariants`) is required when the change touches properties that span beyond a single test. The rest are optional.

### Why

A short paragraph explaining the motivation for the change. What problem is being solved? What's the trigger? What context will be needed by a future engineer (or AI) reading this commit a year from now?

### Acceptance criteria

A list of falsifiable scenarios that must hold for the change to be considered correct, where each scenario is **provable by a single test** (unit, integration, benchmark, or one-shot measurement). Each line describes a specific behavior the system supports after the change ships, named with the test or measurement that asserts it.

This is what authors usually have pre-code — "user calls X and sees Y," "this threshold is met," "this CLI command produces this output." Each AC is a focused, mechanical check: run the test, see it pass, done.

The list is forward-looking. It states what the change establishes or demonstrates, not a catalog of existing behavior. If a behavior is already true and your change isn't adding or altering it, it doesn't belong here.

**Examples of falsifiable acceptance criteria:**
- "GetUser P95 response time is below 10ms on cache hits, asserted by `BenchmarkGetUser_CacheHit`"
- "Cache hit rate exceeds 60% under production traffic, measured by the `cache_hits / cache_total` metric over a rolling 24h window"
- "`GetUserUncached` returns fresh data on every call, asserted by `TestGetUserUncached_AlwaysFresh`"

**Examples of non-falsifiable claims that should be rejected:**
- "GetUser is faster" — faster than what, by how much, measured how
- "The cache is correct" — correct in what sense
- "Backward compatibility is preserved" — which API surface, verified how

### Invariants

A list of properties that must hold *across* the change — properties that **can't be proven by a single test** because they span multiple call sites, code paths, or states. Read-after-write consistency, availability under failure, audit-log-on-every-mutation, thread safety across all paths into a shared resource — these are invariant-shaped.

Where an acceptance criterion is closed by one passing test, an invariant requires reasoning across the diff. The verifier convention is therefore different: an invariant has one or more **spot-check tests** that exercise specific cases, but those tests are not the proof. The proof is "every place this property could be violated, the implementation handles it" — demonstrated by the implementation agent walking the diff during work, and confirmed by the AI review pass scrutinizing the whole diff through the invariant's lens.

The invariants section is required when the change touches scope-spanning properties. It can be small or empty for trivial changes whose impact is fully captured by acceptance criteria. Heavier changes — concurrency primitives, mutation paths, security boundaries, cross-cutting behaviors — should have more invariants by definition, because their scope of impact is wider.

**Examples of invariants:**
- "Read-after-write: a user updated via `UpdateUser` is visible to `GetUser` within 30 seconds across all caller paths. Spot-checked by `TestGetUser_StalenessWindow`; verified across caller paths by review."
- "Every mutation of user data produces an audit log entry. Spot-checked by `TestUpdateUser_AuditLog`; verified across mutation sites by review."
- "The cache layer is safe for concurrent reads and writes from multiple goroutines, across all access paths added by this change. Spot-checked by `TestCacheLayer_Concurrent`; verified across paths by review."

Note the shape: each one reaches into the codebase beyond a single test — "across all caller paths," "across all mutation sites," "across access paths." That's the verb invariants do. ACs don't.

### Optional sections

A complete intent document may also include:

- **Out of scope** — what is *not* being changed. Anchors the bidirectional check (see below).
- **Alternatives considered** — what other approaches were evaluated and why they were rejected. Saves future engineers from re-litigating the same tradeoff.
- **Risks** — what could break, what the blast radius is.

---

## Why "Before Any Code"

The timing matters. Writing the intent first is a forcing function: the moment you try to state precisely what must hold, you discover where your thinking is fuzzy. Most software bugs aren't reasoning errors; they're cases the author didn't consider. Articulating acceptance criteria and invariants explicitly surfaces those cases at the cheapest possible time, before the code exists.

It also separates the two cognitive tasks that get conflated in normal code review:

1. **Deciding what should be true** — a high-judgment task humans are good at
2. **Verifying that code matches what should be true** — a mostly mechanical task machines are good at

Change intent splits the work so each gets done by the right agent at the right time.

---

## How It Integrates Downstream

The change intent has two downstream consumers. The implementation agent uses it as a *goal* — a completion condition to work toward. An AI code review pass then uses it as a *contract* — checking the resulting diff against what was claimed. Each stage adds an independent layer of verification before the change reaches a human reviewer.

### Implementation phase: the intent as the `/goal` condition

Claude Code shipped `/goal` in v2.1.139 (May 2026). It lets a user set a completion condition and have the implementation agent keep working autonomously across turns until that condition is met. After each turn, a separate evaluator model (Haiku by default) reads the conversation transcript and decides whether the condition holds. If yes, the goal clears. If no, the agent continues with the evaluator's reason as guidance for the next turn.

**Key architectural detail:** the evaluator only sees what's surfaced in the conversation. So the condition must be something the implementation agent can prove through its own output — tests passing, builds clean, benchmarks meeting targets, files matching some shape. The evaluator can't run commands itself.

A change intent file is naturally shaped to be a `/goal` condition. The acceptance criteria and invariants together form the completion condition, and the implementation agent's job differs slightly for each:

- **For each acceptance criterion**: write or update the named test (or measurement), run it, surface the passing result in the transcript. Mechanical.
- **For each invariant**: write the spot-check test(s) *and* walk the diff to confirm the property holds at every site where it could be violated. The named test alone doesn't close an invariant — the implementation agent has to demonstrate, in the transcript, that it has considered the property at every relevant site.

The in-loop evaluator checks the transcript for both kinds of evidence each turn. It's a fast first pass; the more reliable check — particularly on invariants — happens next.

### Review phase: the intent as the AI reviewer's target

After the goal clears, an AI code review pass runs against the resulting diff with the change intent as context. The review pass validates three things on top of the standard checks you'd expect:

1. **Is the intent itself well-described?** Are claims falsifiable, are all relevant categories addressed, is the scope clearly bounded? A vague or incomplete intent is a defect in its own right and should bounce the change back before the diff is even examined.
2. **Does the diff match the intent?** Every acceptance criterion has its asserting test in the diff, passing. Every invariant holds across the diff — not just where the spot-check tests assert it, but at every site where the property could be violated. The review pass's work on invariants is the heaviest single thing it does: scrutinize the whole diff through each invariant's lens. Nothing externally observable shows up in the diff that isn't covered by the listed claims or the "out of scope" section.
3. **Does the change contradict any prior intent?** The review pass searches the `change-intent/` folder for past intents that touched related surface and flags apparent contradictions — e.g., an older intent established a strong consistency guarantee and this change appears to weaken it without acknowledging the prior claim. This is the right place for that check: the review pass pays the cost of loading prior context once, instead of forcing every author to enumerate prior invariants up front.

This is independent from and stronger than the in-loop `/goal` evaluator. The evaluator is a fast Haiku pass over a transcript; the review pass is a slower, stronger model with access to the full diff, the repository, and the history of prior intents. It also runs the usual review checks — concurrency hazards, security boundaries, error handling, comment clarity — but now with the intent as additional context shaping what to focus on.

Only after the review pass approves does the change reach a human reviewer. By then there are two independent machine-verified confirmations that the implementation matches the stated intent, and the human can spend their attention on the judgment question rather than the verification one.

### Workflow

1. Human (with skill assistance) produces a change intent file at `change-intent/YYYY-MM-DD-slug.md`
2. Implementation phase: `/goal` with the acceptance criteria and invariants as the condition. Agent writes code, runs tests, demonstrates each acceptance criterion, and walks the diff to confirm each invariant. In-loop evaluator (Haiku) confirms each turn.
3. When the goal clears, the AI code review pass runs against the diff with the intent as context, validates intent quality and intent-vs-diff alignment (with particular scrutiny on invariants), and runs standard review checks.
4. Once the review pass approves, the change reaches a human reviewer. They focus on the judgment question — *is this the right intent?* — not on verifying the code matches it (that has already been checked twice).

### Sample `/goal` invocation

```
/goal All acceptance criteria and invariants in change-intent/2026-05-16-add-getuser-cache.md are demonstrated in this transcript:
- Every acceptance criterion has its named test passing (or its measurement at target)
- Every invariant has its spot-check tests passing AND the agent has walked the diff to confirm the property holds at every site where it could be violated
- The change does not introduce externally observable behavior outside the listed claims and the "out of scope" section
```

The last line is the **bidirectional check** at the change level: not just "did the agent prove what it was supposed to," but "did the agent stay within scope." This check runs both in-loop (Haiku, fast) and again in the AI review pass (stronger model, full diff visibility). The in-loop pass is a fast first cut; the review pass is the more reliable gate. Whether the Haiku evaluator alone can reliably catch out-of-scope behavior is an open question — see Design Tensions below.

---

## The Authoring Skill

The skill produces a change intent file through structured dialogue between the human and the AI. The human owns the macro intent; the AI helps make it rigorous, complete, and falsifiable.

**Critical constraint:** the AI **never** invents acceptance criteria or invariants for code that doesn't exist yet. The change hasn't been made. The AI's role is to read the affected surface, surface what currently holds there, and use that context to ask sharper questions about what the change should establish. The human is the source of intent; the AI is the source of context. The file itself only states forward-looking claims — what the change will prove — not a catalog of preserved behavior.

### Workflow

**Step 1: Human seeds the intent.**

The human says what they want to do at whatever level of specificity they have. Vague seeds are accepted ("speed up GetUser") but trigger more pushback. Precise seeds ("add a 30-second TTL cache to GetUser using the existing CacheManager interface") move faster through the workflow but still get the full category check.

If the seed is too vague to act on at all, the skill's first move is to refuse to proceed and push for specificity: "What does 'faster' mean? What's the current latency? What's the target? What can you trade off to get there?" The skill should not start enumerating invariants against an undefined target.

**Step 2: AI reads the existing relevant surface.**

Given the seed, the AI identifies the code likely to be affected and enumerates what currently holds:

- Type signatures and error contracts
- Concurrency patterns (mutex usage, channel semantics, goroutine spawning)
- Existing invariants documented in godoc
- Call sites — who depends on this code and how
- Existing tests — what's currently verified
- Performance characteristics where measurable
- Similar patterns elsewhere in the codebase (e.g., other services using the same caching approach)

This is the AI's primary contribution: it brings knowledge of the current codebase that the human doesn't carry in their head.

**Step 3: AI proposes a baseline of what's currently true.**

The AI presents an enumeration: "Here's what the existing code guarantees that your change will interact with." This grounds the conversation in reality. The human now has a concrete list to react to rather than a blank page to fill.

**Step 4: Elicit acceptance criteria first.**

The AI asks the human what they already know about the change pre-code — the AC-shaped knowledge that's natural at this stage. "What does the caller / user / operator see after this is done? What scenario do they exercise? What threshold do they observe?" Each candidate AC gets pushed for falsifiability: what named test or measurement asserts it?

This step is fast and productive because the human typically has this content ready. The skill's job is mostly to sharpen it: turn "user can log in faster" into "p95 login latency below 200ms, asserted by `TestLogin_P95`."

**Step 5: Elicit invariants from the surface.**

Using what the AI read in step 2, the skill now asks property-shaped questions that the human likely couldn't have come up with on their own:

- "AuditLog reads through GetUser. Your change introduces a staleness window. Is staleness acceptable for audit, or does this caller need a different guarantee?"
- "GetUser is called from four services with different consistency needs. Across all of them, what's the invariant — read-after-write, eventual, something in between?"
- "The cache touches a shared map. Under concurrent calls, what must hold across all access paths?"
- "If the cache backend fails, what must still hold for callers?"

Each candidate invariant gets at least one spot-check test, but the skill is explicit that the spot-check is not the proof — the invariant is closed by reasoning over the diff at implementation and review time. For trivial changes this step often produces zero or one invariants, and that's fine. For changes touching concurrency, mutation paths, security boundaries, or cross-cutting properties, this step is where the file gets its weight.

**Step 6: Categories pushed proactively.**

The AI ensures the human has addressed every category that applies to the touched surface:

- Concurrency / thread safety
- Error handling and propagation
- Observability (logs, metrics, tracing)
- Security boundaries
- Audit / compliance
- Performance
- Backward compatibility (API, on-disk format, wire protocol)
- Resource cleanup (file handles, connections, goroutines)
- Failure modes (what happens when dependencies fail)

The human can declare any category "not applicable" but they have to declare it explicitly. Silence isn't an answer.

**Step 7: Falsifiability enforced on every claim.**

Vague claims get pushed back until they're testable. The AI does not accept "faster," "more secure," or "backwards compatible" as standalone claims. Each must be made precise: what specifically, measured how, verified by what.

If the human can't make a claim falsifiable, that's a signal the claim isn't well thought out and should be removed or replaced with what the human actually means.

**Step 8: Convergence.**

When every relevant category has an explicit position and every claim is falsifiable, the AI writes the change intent file to `change-intent/YYYY-MM-DD-slug.md` and presents it for final review. If the human approves, the artifact is finalized and the implementation phase begins.

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
- `GetUser(ctx context.Context, id UserID) (*User, error)` returns nil for missing users
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
- GetUser P95 response time is below 10ms on cache hits, asserted by `BenchmarkGetUser_CacheHit`
- Cache hit rate exceeds 60% under production traffic, measured by the `cache_hits / cache_total` metric over a rolling 24h window
- `GetUserUncached` returns fresh data on every call, asserted by `TestGetUserUncached_AlwaysFresh`

## Invariants
- Read-after-write: a user updated via `UpdateUser` is visible to `GetUser` within 30 seconds across all caller paths. Spot-checked by `TestGetUser_StalenessWindow`; verified across caller paths by review.
- The cache layer is safe for concurrent reads and writes from multiple goroutines, across all access paths added by this change. Spot-checked by `TestCacheLayer_Concurrent`; verified across paths by review.

## Out of scope
- The cache implementation itself (using existing CacheManager interface)
- Eviction policy (using CacheManager defaults: LRU with 100k entry limit)
- Cache warming or pre-population
- Distributed cache coordination (single-node cache only for now)

## Alternatives considered
- Write-through cache: rejected because UpdateUser is rare and the added complexity 
  doesn't pay for itself at the current write rate.
- Shorter TTL (5s): rejected because cache hit rate modeling showed it would drop 
  below the 60% target.

## Risks
- Stale data visible to PaymentService for up to 30s: confirmed acceptable by 
  product (charge authorization uses separate fresh-data path).
- Cache stampede on key expiration: mitigated by CacheManager's built-in 
  singleflight behavior.
```

The implementation agent takes this file as the `/goal` condition. For each acceptance criterion, the agent runs the named test or measurement and surfaces the result. For each invariant, the agent runs the spot-check test(s) *and* walks the diff to confirm the property holds at every site where it could be violated — every caller path of `GetUser` for the read-after-write window, every access path into the cache for thread safety. The in-loop evaluator checks the transcript for both kinds of evidence.

When the goal clears, the AI code review pass takes the diff with this intent as context. It validates the alignment under a stronger model — with particular scrutiny on invariants, where the review pass walks the whole diff through each invariant's lens — searches the `change-intent/` folder for prior intents that might be in tension with this one, and runs the standard checks (concurrency, errors, security, clarity). Only then does the change reach the human reviewer — who focuses not on the code itself but on whether the intent captured here was the right one to ship.

---

## Design Tensions

A few areas where the design is not fully resolved and worth flagging for implementation:

### Bidirectional scope-check by evaluator

Whether the Haiku evaluator can reliably detect "the agent did something not claimed in the intent" is an open question. The simple direction (every claim demonstrated) is easy to check. The hard direction (no unclaimed behavior) requires understanding the diff and comparing it to the scope, which may exceed Haiku's reliability. Options to explore:

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

This document covers only the macro layer — change-scoped, human-authored (with AI assistance). There is a complementary system for method-level invariants: pedantic, AI-maintained annotations in godoc comments paired with named tests, enforced by a linter, consumed by an AI-only reviewer. That system handles the micro layer. The two layers compose in the broader review pipeline but are designed independently. Method-level invariants are **out of scope** for this document and this skill.

---

## Summary

A change intent is a per-change artifact authored *before* code, capturing the why, the acceptance criteria (each provable by a single test), and the invariants (properties that span the change and need reasoning over the diff to close). One file per change, stored under `change-intent/` in the repository. It's produced through structured dialogue between a human (who provides the intent) and an AI (which provides context from the existing codebase, pushes for category coverage, and enforces falsifiability). The artifact then serves two downstream roles: it's the `/goal` condition for the implementation phase, and it's the contract an AI code review pass checks the resulting diff against before any human review.

The discipline replaces the fiction of careful per-line human review with a process that's actually verifiable, scoped to each change, and produced by each party at the level it's good at: humans set intent, AI enforces rigor in authoring, the implementation agent works against a clear target, and the review pass verifies the result before the human reviewer ever opens the diff.

**The skill to build:** a structured-dialogue tool that takes a human's seed intent, reads the affected code surface, and walks the human through Socratic elicitation until every relevant category is addressed and every claim is falsifiable. The output is a change intent file ready to serve as both the `/goal` condition and the AI review pass's target.
