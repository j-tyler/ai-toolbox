# Change Intent: Design and Skill Specification

## TL;DR

A `CHANGE_INTENT.md` is a structured document authored by a human (with AI assistance) **before any code is written** for a change. It captures *why* the change is being made and *what externally observable invariants must hold* for the change to be considered correct.

The same document then serves two downstream roles. First, it's the completion condition for the implementation agent (e.g., Claude Code's `/goal`), giving the agent a verifiable target to work toward. Second, it's the contract an AI code review pass checks the resulting diff against — before the change ever reaches a human reviewer. The human reviewer then receives a structured artifact, machine-verified evidence the diff matches it, and can spend their attention on the judgment question — *is this the right intent?* — rather than redoing the verification work.

This document explains the concept, the problems it addresses, how it integrates with the implementation and review phases downstream, and how a Claude Code skill could produce these intent documents through structured dialogue.

---

## The Problem This Tries to Solve

AI generates code far faster than humans can review it. Humans are the bottleneck on shipping changes, and the bottleneck will only tighten as models and agents get better. This work designs a change process that optimizes for the humans still in the loop today, and gets better as the AI in the loop gets better.

Just as autonomous vehicles will eventually drive themselves and we'll think nothing of it, code review will eventually be done by AI and we'll think nothing of that either. The point of a good process today is to walk us toward that future smoothly — more AI, less human, comfort accumulating along the way.

Until we're there, `CHANGE_INTENT.md` addresses several failure modes of today's review process:

1. **Vague intent.** Most PRs today are accompanied by a one-line description and a 400-line diff. Reviewers (human or AI) have to infer the author's intent from the code itself. CHANGE_INTENT inverts this: intent is authored explicitly and the code is verified against it.

2. **Silent invariant breakage.** Most production bugs aren't "I thought X would happen and Y happened." They're "I didn't think about case Z, and the code now does something weird in case Z." Forcing the author to enumerate what must remain true surfaces these cases before code is written.

3. **Unverifiable claims.** Vague claims like "faster" or "more secure" can't be checked. CHANGE_INTENT requires every claim to be falsifiable — measurable, verifiable by a test or analysis the implementation agent can run.

4. **Lost context.** PR descriptions get lost in commit history. CHANGE_INTENT lives in the commit itself, structured enough that a future engineer (or AI) reading it months later can understand why the change was made and what tradeoffs were accepted.

5. **Conflation of two tasks.** Human reviewers today are nominally doing two jobs simultaneously: deciding whether the change is the right change to make, and verifying that the code matches the intent. CHANGE_INTENT separates these so each can be done by the right kind of agent: humans focus on intent correctness, machines focus on implementation fidelity.

---

## What Change Intent Is

A `CHANGE_INTENT.md` is a per-commit (or per-change) document authored **before any code is written**. It has two required sections:

### Why

A short paragraph explaining the motivation for the change. What problem is being solved? What's the trigger? What context will be needed by a future engineer (or AI) reading this commit a year from now?

### External invariants

A list of properties that must be true for the change to be considered correct. These are observable from outside — by callers of the API, by users of the system, by tests run against the changed surface. Each invariant must be **falsifiable**: stated specifically enough that an evaluator can determine whether it holds based on the implementation's behavior.

**Examples of falsifiable invariants:**
- "GetUser returns nil for users that don't exist (unchanged)"
- "GetUser remains safe to call concurrently from multiple goroutines (unchanged)"
- "A user updated via UpdateUser is visible to GetUser within 30 seconds (new; weakened from immediate consistency)"
- "GetUser P95 response time drops below 10ms on cache hits, measured by BenchmarkGetUser_CacheHit"

**Examples of non-falsifiable claims that should be rejected:**
- "GetUser is faster" — faster than what, by how much, measured how
- "The cache is correct" — correct in what sense
- "Backward compatibility is preserved" — which API surface, verified how

### Invariant annotations

Each invariant carries an annotation describing how it changes relative to the current state:

- **`[unchanged]`** — the invariant currently holds; the change must preserve it
- **`[new]`** — the invariant doesn't currently hold; the change establishes it
- **`[weakened]`** — the invariant currently holds in a stronger form; the change relaxes it (requires justification)
- **`[strengthened]`** — the change tightens an existing invariant
- **`[modified]`** — the invariant changes in a way that isn't a simple weakening or strengthening
- **`[removed]`** — an invariant currently holds but will no longer apply after this change (requires justification)

The annotations matter because the most dangerous changes are weakenings — they're how silent breakage happens. Making each change visible in the intent document forces the author to acknowledge it explicitly. A reviewer (human or machine) seeing `[weakened]` knows to look at callers that may depend on the stronger form.

### Optional sections

A complete intent document may also include:

- **Out of scope** — what is *not* being changed. Anchors the bidirectional check (see below).
- **Alternatives considered** — what other approaches were evaluated and why they were rejected. Saves future engineers from re-litigating the same tradeoff.
- **Risks** — what could break, what the blast radius is.

---

## Why "Before Any Code"

The timing matters. Writing the intent first is a forcing function: the moment you try to state precisely what must hold, you discover where your thinking is fuzzy. Most software bugs aren't reasoning errors; they're cases the author didn't consider. Articulating invariants explicitly surfaces those cases at the cheapest possible time, before the code exists.

It also separates the two cognitive tasks that get conflated in normal code review:

1. **Deciding what should be true** — a high-judgment task humans are good at
2. **Verifying that code matches what should be true** — a mostly mechanical task machines are good at

CHANGE_INTENT splits the work so each gets done by the right agent at the right time.

---

## How It Integrates Downstream

The change intent has two downstream consumers. The implementation agent uses it as a *goal* — a completion condition to work toward. An AI code review pass then uses it as a *contract* — checking the resulting diff against what was claimed. Each stage adds an independent layer of verification before the change reaches a human reviewer.

### Implementation phase: the intent as the `/goal` condition

Claude Code shipped `/goal` in v2.1.139 (May 2026). It lets a user set a completion condition and have the implementation agent keep working autonomously across turns until that condition is met. After each turn, a separate evaluator model (Haiku by default) reads the conversation transcript and decides whether the condition holds. If yes, the goal clears. If no, the agent continues with the evaluator's reason as guidance for the next turn.

**Key architectural detail:** the evaluator only sees what's surfaced in the conversation. So the condition must be something the implementation agent can prove through its own output — tests passing, builds clean, benchmarks meeting targets, files matching some shape. The evaluator can't run commands itself.

`CHANGE_INTENT.md` is naturally shaped to be a `/goal` condition. The external invariants list **is** the completion condition. The implementation agent's job is to make the code such that every invariant in the document can be demonstrated in the transcript:

- `[unchanged]` invariants: existing tests still pass, run visibly
- `[new]` invariants: new tests are added that pass
- `[weakened]` invariants: the new (weaker) form is demonstrated; old behavior is no longer asserted
- `[strengthened]` invariants: a tighter test is added and passes
- `[modified]` / `[removed]` invariants: explicit demonstration that the new state is correct

The in-loop evaluator checks the transcript and confirms each turn. It's a fast first pass; the more reliable check happens next.

### Review phase: the intent as the AI reviewer's target

After the goal clears, an AI code review pass runs against the resulting diff with the change intent as context. The review pass validates two things on top of the standard checks you'd expect:

1. **Is the intent itself well-described?** Are claims falsifiable, are all relevant categories addressed, is the scope clearly bounded? A vague or incomplete intent is a defect in its own right and should bounce the change back before the diff is even examined.
2. **Does the diff match the intent?** Every invariant the change claims to establish, preserve, weaken, or remove is reflected in the diff and supported by visible evidence. Nothing externally observable shows up in the diff that isn't covered by the intent or the "out of scope" section.

This is independent from and stronger than the in-loop `/goal` evaluator. The evaluator is a fast Haiku pass over a transcript; the review pass is a slower, stronger model with access to the full diff and repository context. It also runs the usual review checks — concurrency hazards, security boundaries, error handling, comment clarity — but now with the intent as additional context shaping what to focus on.

Only after the review pass approves does the change reach a human reviewer. By then there are two independent machine-verified confirmations that the implementation matches the stated intent, and the human can spend their attention on the judgment question rather than the verification one.

### Workflow

1. Human (with skill assistance) produces `CHANGE_INTENT.md`
2. Implementation phase: `/goal` with the invariants as the condition. Agent writes code, runs tests, and demonstrates each invariant. In-loop evaluator (Haiku) confirms each turn.
3. When the goal clears, the AI code review pass runs against the diff with the intent as context, validates intent quality and intent-vs-diff alignment, and runs standard review checks.
4. Once the review pass approves, the change reaches a human reviewer. They focus on the judgment question — *is this the right intent?* — not on verifying the code matches it (that has already been checked twice).

### Sample `/goal` invocation

```
/goal All external invariants in CHANGE_INTENT.md are demonstrated in this transcript:
- Every [unchanged] invariant has a passing test visible in the transcript
- Every [new] invariant has a new test that passes
- Every [weakened] invariant's new form is demonstrated and old behavior is no longer asserted
- The change does not introduce externally observable behavior outside the listed invariants and the "out of scope" section
```

The last line is the **bidirectional check** at the change level: not just "did the agent prove what it was supposed to," but "did the agent stay within scope." This check runs both in-loop (Haiku, fast) and again in the AI review pass (stronger model, full diff visibility). The in-loop pass is a fast first cut; the review pass is the more reliable gate. Whether the Haiku evaluator alone can reliably catch out-of-scope behavior is an open question — see Design Tensions below.

---

## The Authoring Skill

The skill produces `CHANGE_INTENT.md` through structured dialogue between the human and the AI. The human owns the macro intent; the AI helps make it rigorous, complete, and falsifiable.

**Critical constraint:** the AI **never** invents invariants for code that doesn't exist yet. The change hasn't been made. The AI's role is to enumerate what currently holds on the affected surface (which it can read), then help the human decide which existing invariants to preserve, modify, or replace, and what new invariants to add. The human is the source of intent; the AI is the source of context.

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

**Step 4: Iterative Socratic refinement.**

The AI asks targeted questions that get sharpness from the existing invariants it just enumerated:

- "AuditLog reads through GetUser. Your cache introduces a staleness window. Is staleness acceptable for audit purposes?"
- "PaymentService verifies account state through GetUser before charging. Is a 30-second staleness window acceptable there, or do you need a cache-bypass path for that caller?"
- "GetUser is currently safe for concurrent use. Does your cache implementation preserve that?"

The questions reference specific existing code but ask about what *should* be true after the change. The AI is not anticipating the change — it's surfacing the constraints the change will have to satisfy.

**Step 5: Categories pushed proactively.**

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

**Step 6: Falsifiability enforced on every claim.**

Vague claims get pushed back until they're testable. The AI does not accept "faster," "more secure," or "backwards compatible" as standalone claims. Each must be made precise: what specifically, measured how, verified by what.

If the human can't make a claim falsifiable, that's a signal the claim isn't well thought out and should be removed or replaced with what the human actually means.

**Step 7: Convergence.**

When every relevant category has an explicit position and every claim is falsifiable, the AI produces the `CHANGE_INTENT.md` and presents it for final review. If the human approves, the artifact is finalized and the implementation phase begins.

### Depth calibration

Not every change deserves a fifteen-page intent file. Depth should scale with risk, detected from the existing code:

- **Light pass** (3-5 invariants, single category): leaf utility, pure helper, isolated refactor
- **Medium pass** (5-10 invariants, multiple categories): typical feature work touching one or two services
- **Deep pass** (10+ invariants, all categories): changes to concurrency primitives, public APIs, security-relevant paths, hot paths, anything that historically required care

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

**AI presents baseline and conducts elicitation.** After dialogue, the produced `CHANGE_INTENT.md`:

```markdown
# CHANGE_INTENT

## Why
GetUser is read-heavy (40k req/s peak). P95 latency is 80ms, dominated by 
the DB round-trip. Adding a 30-second TTL cache should drop P95 below 10ms 
on cache hits and reduce DB load by ~70% based on access patterns in 
production traces. The 30s TTL aligns with the staleness budget product 
approved for user profile data.

## External invariants
- [unchanged] GetUser returns nil exactly when no user exists with the given ID
- [unchanged] GetUser remains safe to call concurrently from multiple goroutines
- [unchanged] GetUser propagates ctx cancellation and respects deadlines
- [unchanged] AuditLog continues to receive consistent reads (migrated to new GetUserUncached method)
- [new] GetUser P95 response time below 10ms on cache hits, verified by BenchmarkGetUser_CacheHit
- [new] Cache hit rate above 60% under production traffic, verified by ratio of cache_hits / cache_total metric
- [weakened] A user updated via UpdateUser is visible to GetUser within 30 seconds 
  (was: immediate consistency). Justification: read-after-write consistency was not 
  required by any current caller except AuditLog, which is migrated to GetUserUncached.
- [new] GetUserUncached method bypasses cache and provides immediate consistency 
  for audit and compliance use cases. Same signature as GetUser; documented for 
  audit/compliance callers only.

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

The implementation agent then takes this file as the `/goal` condition. After each turn, the in-loop evaluator checks:
- Does the transcript demonstrate each `[unchanged]` invariant still holds (passing tests visible)?
- Does the transcript demonstrate each `[new]` invariant (new tests passing, benchmark results)?
- Is the `[weakened]` invariant's new form visible? Is the old (stronger) assertion gone?
- Has the implementation introduced any externally observable behavior not in this list and not in "Out of scope"?

When all conditions are met, the goal clears. The AI code review pass then takes the diff with this intent as context, validates the alignment again under a stronger model, and runs the standard checks (concurrency, errors, security, clarity). Only then does the change reach the human reviewer — who focuses not on the code itself but on whether the intent captured here was the right one to ship.

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

Untouched code has no documented invariants. The AI's "enumeration of what's currently true" is partly inferential and may be wrong. Early iterations of this system will produce intent files based on inferred-but-not-formalized invariants. This is a real risk and worth acknowledging in early deployment.

### Spike-then-formalize

Exploratory work doesn't fit this model — you don't know the right invariants until you've tried something. The skill should support a "draft mode" that produces tentative invariants for spike work, with full discipline applied when the change moves toward merge. Forcing full intent rigor on exploratory code will kill the practice.

### Cross-cutting invariants

The change-level intent captures invariants on the touched surface, but some properties are system-wide ("every mutation of user data produces an audit log entry"). These need a separate registry that the intent can reference. Not covered by this document, but worth flagging that the macro intent layer is not the complete invariant story.

### Method-level invariants are separate

This document covers only the macro layer — change-scoped, human-authored (with AI assistance). There is a complementary system for method-level invariants: pedantic, AI-maintained annotations in godoc comments paired with named tests, enforced by a linter, consumed by an AI-only reviewer. That system handles the micro layer. The two layers compose in the broader review pipeline but are designed independently. Method-level invariants are **out of scope** for this document and this skill.

---

## Summary

`CHANGE_INTENT.md` is a per-change artifact authored *before* code, capturing the why and the externally observable invariants the change must satisfy. It's produced through structured dialogue between a human (who provides the intent) and an AI (which provides context from the existing codebase, pushes for category coverage, and enforces falsifiability). The artifact then serves two downstream roles: it's the `/goal` condition for the implementation phase, and it's the contract an AI code review pass checks the resulting diff against before any human review.

The discipline replaces the fiction of careful per-line human review with a process that's actually verifiable, scoped to each change, and produced by each party at the level it's good at: humans set intent, AI enforces rigor in authoring, the implementation agent works against a clear target, and the review pass verifies the result before the human reviewer ever opens the diff.

**The skill to build:** a structured-dialogue tool that takes a human's seed intent, reads the affected code surface, and walks the human through Socratic elicitation until every relevant category is addressed and every claim is falsifiable. The output is a `CHANGE_INTENT.md` ready to serve as both the `/goal` condition and the AI review pass's target.
