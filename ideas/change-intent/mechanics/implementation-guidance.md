# Implementation Guidance

**Status: drafted.**

[design.md](../design.md) states how implementation integrates downstream, including binding the intent to a harness mechanism such as Claude Code's `/goal`. That binding is the team's setup, not this file's. This file is what a team adds to its implementing agents' instructions — a CLAUDE.md, an agents file, a system prompt — so an agent holding an approved intent knows how to work from it. Copy the block below and shape it to your project.

---

## Change intent: how to implement against one

This section governs implementing a change that has an approved intent at `change-intent/YYYY-MM-DD-short-slug.md`; a task with no intent is not governed by it. The intent is your goal and your contract: the change is complete when every claim in it is demonstrated, and the change contains nothing the intent does not cover. What the change should be was settled at approval; how to satisfy it is yours.

### The intent file, from the implementation seat

- **Outcomes** — what the change is meant to make true. They orient your choices; the claims below are what you must prove.
- **Why** — the reasoning behind the change. Where the claims leave a choice open, choose in the direction the Why points.
- **Acceptance criteria** — each needs a proving test, written by you, in this change, shown by the would-fail demonstration below. Write other tests freely; each claim needs its one.
- **Invariants** — properties that span sites ("across all caller paths…"); closed by the written walk below, not by tests alone.
- **Out of scope** — fences, not suggestions. Do not fix, improve, or touch what is listed, even when it is easy.
- **Amendments** — your one way to change the contract, described below.

### Demonstrate, don't just do

Surface the evidence — tests run with results shown, the would-fail demonstrations, the invariant walks — where your team checks completion: the session transcript, the pull request description. It does not need to outlive your session; what crosses to review is the diff, its tests, and the intent file. Do not thin the evidence on the grounds that review will redo it, and do not skip it on the grounds that no one will look.

**The would-fail demonstration, per acceptance criterion.** A test that cannot fail proves nothing — and you are the most likely person to write one, because you are testing your own work:

1. Write the test that proves the claim. Run it; show it passing.
2. Break the behavior in the product code — a temporary edit that falsifies the claim; invasive is fine, the break is temporary. Never edit the test to make it fail.
3. Run the test; show the failure — and check that it fails *on the claim*. A crash or an unrelated error demonstrates nothing about what the test guards.
4. Restore the code and confirm the break is fully removed. Run the test; show it passing again.

Never commit while a break is in the tree. A claim with nothing to break at runtime — a dependency absent, a file removed — is proven by its test alone; state why the demonstration does not apply.

**The invariant walk, per invariant:** enumerate the sites first — everywhere the span rule reaches that your change could affect, in changed and unchanged code alike — then write one entry per site: the site (file and function), how the property could break there, and why it does not. A site you cannot close is never skipped — it is a fix, or it is an amendment.

### When the intent is wrong: amend, on the record

Exactly two cases qualify:

- **A claim cannot hold** — an acceptance criterion or invariant is false for a reason you discovered, or true but unprovable in this repository's tests.
- **The scope is unsatisfiable** — the change forces observable behavior the intent takes no position on, so no implementation can deliver the change and stay inside the claims.

In either case the correct move — the success move, not an admission of failure — is to amend the intent and keep working. Never pretend a claim holds; never drift past it silently; never stall waiting for permission — the author rules on every amendment when your work returns.

**An amendment is three edits to the intent file, made together:**

1. **The claim.** Rewrite it to the text that can hold — or add it, when the scope was unsatisfiable and the intent needed a position it lacked.
2. **The discovery note.** Immediately after the changed claim, an italic parenthetical: `*(Amended YYYY-MM-DD: <the discovered fact — one to three sentences carrying the mechanism and what it implies>.)*`
3. **The entry.** One line under an `## Amendments` section, created at the end of the file if absent: `- YYYY-MM-DD — <what changed, at claim granularity> — <the discovered fact that forced it>`.

The fact named in the note and the entry is a statement about the system — something still true and checkable if the rest of the file were deleted — never a description of your activity:

```
Fails — activity-shaped, tells a future reader nothing:
- 2026-07-08 — AC 2 relaxed — ran into implementation issues

Passes — fact-shaped, verifiable against the codebase:
- 2026-07-08 — AC relaxed: revocation latency 1m → 5m — AuthMiddleware
  caches token validation for 5m with no invalidation hook
```

If you weakened a claim and the original strength is deferred rather than abandoned, also record the deferral under Out of scope. The fences themselves are not yours to move: when an Out of scope entry is what blocks a claim, the repair still goes through the claim — moving the fence is the author's reopening to make. Commit the amended intent before continuing the work that depends on it.

Everything else is not an amendment:

- **Latitude the intent grants** ("TTL may be 10–60s, implementation's choice") is yours; exercise it without ceremony.
- **A better idea** — an improvement, hardening, an adjacent fix — is a seed for a future intent: name it when you finish, never fold it into this change.
- **New direction from the author** is a reopening: take their direction through the reopening process — the intent is revised and re-approved — then continue against the revised text. Do not record it as an amendment, and do not keep implementing against the old text.
- **A change no repair can deliver** — the change itself no longer makes sense — is a failed change: stop and report, with the discovered facts.

### Done

Every acceptance criterion has its passing test shown, with its would-fail demonstration. Every invariant has its written walk. Nothing observable in your diff — observable means the channels named in this project's agents file — falls outside the claims and the out-of-scope list; where something does, either the change forced it (amend) or you chose it (remove it). The intent file carries whatever amendments the work required, and nothing changed it without one.
