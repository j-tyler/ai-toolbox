# Review Skill

**Status: stub. To be built after the design is settled.**

The skill (or review-prompt reference) for the AI review pass specified in [design.md](../design.md) ("Review phase: the intent as the AI reviewer's target"). The design fixes the four validations; this skill fixes how an agent performs them reliably. The organizing rule: every check the agent runs is an enumeration, not a principle — the same falsifiability discipline the artifact applies to the author's claims, applied to the reviewer's instructions.

Requirements:

- **Blind pass first.** The agent reviews the diff cold — what it does, what could be wrong, what it observably changes — *before* reading the intent. Reading the intent first anchors the review to the listed claims and degrades the open-ended sweep into checklist confirmation. Intent quality (are the claims falsifiable?) is also judged before seeing the diff: with the diff in view, hindsight makes vague claims look clear.
- **Per-claim verdict schema.** For each acceptance criterion: which test, does it pass, how was would-fail established, verdict `met / not-met / cannot-verify`. `cannot-verify` is a first-class, unpunished outcome — the counter to the agent confidently reporting "verified" when it actually means "plausible."
- **Independent enumeration for invariants.** The agent enumerates the sites where each invariant could be violated, then diffs its list against the implementation transcript's walk. A site on one list but not the other is automatically a finding. "Does the invariant hold?" is never asked as a single question.
- **Per-hunk scope classification.** Every hunk of the diff is classified as serving a claim, an acknowledged out-of-scope item, or infrastructure; anything unclassifiable is a finding. This replaces "is there unclaimed observable behavior?" — a question that gets one shallow answer.
- **The amendment check as an algorithm.** The joins, spelled out: the final text equals the approval commit's text plus the amendment entries; every entry has a discovery note on its claim and every discovery note has an entry; dates are consistent; relaxations also landed in Out of scope.
- **Prior-intent retrieval strategy.** The design tension "Scoping the past-intent search" lists candidate strategies; this file picks one and makes it concrete — e.g., files overlapping the diff → search `change-intent/` for those paths and symbols → read the top matches. Left unspecified, the check silently doesn't happen.
- **Adversarial framing.** The change arrives with a green transcript, and the agent's prior is to confirm. The prompt states the job as finding the claim that does *not* hold, and treats zero findings on a nontrivial change as a result that itself needs explaining.
- **Fan-out on large diffs.** Per-invariant scrutiny degrades non-uniformly across a big diff. The review pass is a workflow — one pass per invariant, chunked diff — not one prompt.
- **Honest gates vs. screens.** Checks known to have limited recall (the bidirectional scope check above all) are reported as screens with stated confidence, not passed as gates. "Reviewing less" is priced off measured catch rates — seeded violations, periodically — not off the existence of the check.
