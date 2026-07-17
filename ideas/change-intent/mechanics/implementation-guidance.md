# Implementation Guidance

**Status: drafted.**

[design.md](../design.md) defines the implementation role, including optional integration with a harness mechanism such as Claude Code's `/goal`. This file contains the agent-facing instructions a team adds to its implementation environment. The block below may be copied and adapted to the project.

---

## Change intent: how to implement against one

Apply this section only when the change has a current intent at `change-intent/YYYY-MM-DD-short-slug.md`. Treat that intent as the decision boundary and completion condition. The change is complete only when every claim is demonstrated, every change-defining decision is honored, and no known conflict with a constraint remains. You own technical choices that the intent and applicable project instructions leave open.

### The intent file, from the implementation seat

- **Outcomes** — what the change is meant to make true. They orient your choices; the claims below are what you must prove.
- **Why** — the problem, event, or need that caused the change. It explains the work; it does not settle implementation choices or establish requirements.
- **Constraints** — conditions and non-behavioral boundaries every acceptable implementation must be designed around. Use them to guide engineering judgment. They do not each require a test or conclusive proof. Lack of proof is not a violation or amendment trigger; act when evidence shows a conflict.
- **Acceptance criteria** — for each criterion, add a proving test and complete the would-fail procedure below. Add any other tests required by ordinary engineering practice.
- **Invariants** — properties that must remain true across the parts of the system affected by the change. Add tests for concrete cases where useful, but do not treat passing tests as closure; also reason across the affected diff and relevant surrounding paths.
- **Out of scope** — work this change does not deliver. Do not implement or expand into the excluded outcome, even when it is easy. You may edit a shared surface when necessary to deliver the included change without delivering the excluded work; a surface that must remain literally unchanged is an explicit constraint, not an Out of scope entry.
- **Amendments** — the only implementation-time process for changing the approved intent, described below.

### Demonstrate, don't just do

Report test results, would-fail demonstrations, and invariant reasoning in the implementation session so the goal evaluator can determine whether the change is complete. This evidence may remain session-scoped. The later review independently assesses the implementation and whatever evidence the team's review operation makes available; it does not depend on receiving your session proof. Produce the full implementation evidence even when review uses different mechanics.

**The would-fail demonstration, per acceptance criterion.** A test that cannot fail when its criterion is false proves nothing:

1. Write the test that proves the claim. Run it; show it passing.
2. State the criterion's defining condition. Prefer a reversible temporary product-code edit that makes that condition false. If that is unsafe, use the closest claim-level negative control: a controlled product configuration or dependency state that makes the defining condition false. Mutate the promised behavior, not merely an internal branch that another valid path can compensate for. Never edit the proving test to make it fail.
3. Run the test; show the failure — and check that it fails *on the claim*. A crash or an unrelated error demonstrates nothing about what the test guards.
4. Restore the product code, configuration, or dependency state and confirm the break is fully removed. Run the test; show it passing again.

If another path leaves the criterion true, reject the falsification and choose one that actually makes the criterion false. One falsification may support multiple acceptance criteria only when each criterion's own proving test fails for the expected, claim-specific reason. One demonstration does not need to cover every possible failure. Identify a configuration or dependency fallback as a negative control. If neither a safe product mutation nor a controlled negative state can produce an observed claim-specific failure, that is a limit on the evidence, not a failure of the change: say what you could not show and why, and let the goal evaluator weigh the evidence as it stands. Never present evidence as stronger than it is, and never weaken a claim to escape demonstrating it. Never commit a temporary mutation or other falsifying state.

**The invariant analysis, per invariant.** Add tests for concrete cases where they provide useful protection. Then reason across the affected diff and the relevant surrounding paths: explain how the change could affect the property, what you inspected, and why the property remains true. Name material uncertainty in the session evidence rather than manufacturing closure. Do not treat a passing test as sufficient, and do not expect the intent author to have listed every location or test in advance.

### When the intent is wrong: amend, on the record

Exactly two cases qualify. Apply these tests to the approved change, not only to your current implementation:

- **A claim cannot be delivered within the approved boundaries** — the intent's outcomes, constraints, and exclusions, together with applicable project instructions. Discovered facts must show that no reasonable implementation can make an acceptance criterion or invariant hold without violating them. Failure of your selected approach is not enough. If another reasonable in-scope implementation can satisfy the claim, change the implementation instead. An acceptance criterion whose behavior can be delivered but cannot be proved by any reasonable test available to the change may be reworded without weakening it or moved to Outcomes or Constraints according to the role it plays. An invariant's need for reasoning beyond tests is not an amendment trigger. A constraint that cannot be proved does not qualify; constraints are not claims.
- **A necessary change-defining decision is missing** — you cannot complete implementation without choosing which change will be delivered, and the approved intent does not make that choice. If either reasonable branch still delivers the approved change, choose an implementation without amending. A fork created only by your selected implementation is not necessary when another reasonable implementation avoids it while delivering the approved change.

Do not try to prove that no imaginable implementation exists. Consider the plausible alternatives supported by the current repository and normal scope of this pull request. Before amending, name those alternatives in your implementation evidence. If any can satisfy the current intent, change the implementation. An amendment may repair a claim or settle a missing decision only while preserving the approved boundaries. If affirmative evidence shows that every reasonable in-scope implementation would violate one of those boundaries, stop and report a failed change; do not amend the boundary away. Uncertainty or unavailable production proof is not affirmative evidence of a conflict.

For a necessary missing decision, compare the reasonable in-scope resolutions in this order:

1. Preserve the approved Outcomes.
2. Honor Constraints and Out of scope exclusions.
3. Preserve existing external behavior unless the intent changes it.
4. Minimize scope.
5. Prefer the more reversible resolution.

Select the first resolution distinguished by that order. If the full precedence leaves reasonable resolutions tied, select either one, record that the precedence did not distinguish them, and continue. Your selection is a provisional implementation-time decision that the author rules on when the work returns. Do not use repository convention or engineering preference as an additional source of product direction.

In either case, record an amendment before continuing. Do not report a false claim as satisfied, proceed past a missing change-defining decision, or wait for additional approval of the amended direction. Continue only within the applicable project instructions and operational permissions already governing the work; an amendment overrides neither. The author reviews every amendment when the work returns.

**A semantic amendment is two edits to the intent file, made together:**

1. **Update the current body.** Rewrite, add, remove, or move the affected item only as far as the discovered fact and amendment authority permit. The body must remain a complete account of the current intent without relying on Amendments.
2. **Add the history entry.** Assign the next local identifier (`A1`, `A2`, ...). Under an `## Amendments` section at the end of the file, state the discovered fact, then quote the complete previous and current item wording verbatim with its section:

   ```markdown
   - **A<N> — YYYY-MM-DD.** <the discovered fact that forced the repair>
     - Was — <section>: <verbatim previous item>
     - Now — <section>: <verbatim current item>
   ```

   Use `Was: not present` for an item's first addition and `Now: removed` for a removal. A move names the previous section under `Was` and the current section under `Now`. If one discovery changes several items, include one `Was`/`Now` pair for each. If an item changes again, leave the prior entry unchanged and make the later amendment's `Was` equal the earlier amendment's `Now`; only the terminal `Now` wording must match the current body. For a missing decision, also name the precedence rule that selected the resolution — the rule itself, not a number — or state that the full precedence left the reasonable resolutions tied. Do not add an amendment identifier or discovery note to the current body.

Do not edit the approved intent merely to improve wording. If the wording has one clear meaning, leave it unchanged. If its ambiguity could describe different changes, treat the problem as semantic and use the necessity test; any resulting amendment includes both edits above.

The fact named in the entry is a statement about the system — something still true and checkable if the rest of the file were deleted — never a description of your activity:

```
Fails — activity-shaped and omits the exact prior and current items:
- A1 — 2026-07-08 — AC 2 relaxed — ran into implementation issues

Passes — fact-shaped with verbatim item wording:
- **A1 — 2026-07-08.** All collaborator access checks are delegated to
  SharingMiddleware, which caches access grants for 5m with no invalidation
  or configuration hook.
  - Was — Acceptance criteria: - A removed collaborator loses edit access within 1 minute.
  - Now — Acceptance criteria: - A removed collaborator loses edit access within 5 minutes.
```

If you weakened a claim and the prior strength is deferred rather than abandoned, also record the deferral under Out of scope and include its own `Was`/`Now` pair in the amendment. The fences themselves are not yours to move: when an Out of scope entry is what blocks a claim, the repair still goes through the claim — moving the fence requires an author replacement. Commit the amended intent before continuing the work that depends on it.

Everything else is not an amendment:

- **Implementation latitude** applies whether or not the intent explicitly grants it. Ask whether the author could approve the change once and allow either reasonable branch while still receiving the change they approved. If yes, choose one and continue without amendment. A technical or observable difference alone does not require an amendment.
- **A better idea** — an improvement, hardening, an adjacent fix — is a seed for a future intent: name it when you finish, never fold it into this change.
- **New direction from the author** replaces the current unmerged intent. Stop using the superseded candidate. After the replacement is approved, reassess retained code against it, redo affected evidence, and send the change through review again. Do not record a revision history or keep the superseded candidate's Amendments section.
- **A change no repair can deliver** — the change itself no longer makes sense — is a failed change: stop and report, with the discovered facts.

### Done

Every acceptance criterion has its passing test shown, with an observed would-fail demonstration that makes the criterion false and shows the expected, claim-specific failure, and any limit on what could be safely demonstrated is surfaced with its reason. One falsification may cover multiple criteria only when every criterion's own proving test produces its own claim-specific failure. Every temporary product mutation or controlled negative state is restored before the affected tests pass again. Every invariant has useful tests where appropriate and surfaced reasoning across the affected diff and relevant surrounding paths. The diff plausibly delivers the outcomes, demonstrates the claims, respects the exclusions, and accounts for the explicit constraints. A constraint whose truth depends on production does not need to be proven here; completion requires no known conflict, not manufactured certainty. Any newly discovered necessary change-defining decision is recorded as an amendment; ordinary implementation choices are explained where normal code review needs them, not manufactured into intent claims. The current body stands on its own, and every implementation-time change to its approved baseline appears under Amendments with exact `Was` and `Now` wording.
