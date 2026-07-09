# Implementation Reference

**Status: stub. To be built after the design is settled.**

The runnable instructions for the implementation phase specified in [design.md](../design.md) ("Implementation phase: the intent as the `/goal` condition") — the integration, the sample goal invocation, and the bidirectional check are stated there. This file holds the operational layer: the full goal-prompt template and the agent behaviors the design's obligations depend on.

Requirements:

- **The goal template.** Expands the design's sample invocation into the full template: per acceptance criterion, a test written, run, and shown passing *plus* a would-fail demonstration (break the behavior, watch the test fail, revert) surfaced in the transcript; per invariant, spot-check tests plus a site-by-site walk of the diff. The would-fail demonstration runs in-loop because it is cheap for the implementor and turns the review pass's hardest static check into transcript evidence.
- **Amendment, with the default inverted.** An agent's trained default under ambiguity is to pick a reasonable value and keep going — silently. The instructions state plainly: when a claim cannot hold, or the change forces observable behavior the intent takes no position on, the recorded amendment is the success condition, not an admission of failure. The entry names the discovered fact, the discovery note lands on the changed claim, the amendment is committed, and work continues.
- **Bounded-discretion exercise.** Granted latitude ("TTL may be anywhere in 10–60s, implementation's choice") is exercised silently; anything else that conflicts with the intent is amended if the intent is wrong, and not done otherwise — direction that would change a right intent is the author's to apply by reopening, never the implementor's edit. The agent never treats that gap as delegated discretion just because a default seems obvious.
- **Evidence surfacing.** The in-loop evaluator sees only the transcript, so every obligation is demonstrated in output the evaluator can read — tests run with results shown, walks written out site by site, scope reasoning stated.
- **Evaluator strategy for the out-of-scope direction.** The design tension "Bidirectional scope-check by evaluator" lists candidate strategies; this file picks one and makes it concrete — and states the check's measured confidence rather than presenting it as a gate.
