# Change Intent: Multi-Angle Design Review — Round 2

**Reviewed revision:** `47b0dcf` (`codex/change-intent-authoring-streamline-trial`)

**Review date:** 2026-07-16

**Scope:** Every file under `ideas/change-intent/`, the root framing, and the Working in Public stub. This round also audits what happened to [Round 1](multi-angle-review.md) (reviewed at `b9c3c71`): which of its findings the subsequent commits addressed, and which remain open.

## Method

The corpus was read end to end, then assessed by five independent reviewers, each occupying one seat with no visibility into the others and explicitly barred from reading Round 1 to avoid anchoring:

1. the AI agent executing the authoring skill in dialogue with a human author — simulated concretely on a cold-start feature ("add rate limiting to the login endpoint"), a one-line fix, and a messy session harvest;
2. the AI implementation agent working from an approved intent under the implementation guidance, with the intent as the `/goal` condition — simulated end to end on the worked GetUser-cache example including its A1 amendment, then stress-tested on unfalsifiable criteria, unboundable invariants, high-stakes precedence ties, and project-instruction conflicts;
3. the AI review agent applying the review guidance to a pull request — simulated on the worked example plus a plausible diff, from the minimum inputs the guidance defines;
4. an internal-consistency auditor tracing every rule that is stated in more than one document;
5. an adoption-and-economics reviewer costing the process against existing practice.

Two further passes ran alongside: a delta audit comparing each Round 1 finding against the `b9c3c71..47b0dcf` diff, and a fact-check of the `/goal` claims against the official Claude Code documentation.

Every candidate finding then went through an adversarial verification pass with a default-refute stance: the verifier's job was to kill the finding by locating corpus text that already handles it, or by showing it re-litigates a documented deliberate tradeoff. Of 34 raw findings, 29 remained after dedup and **18 survived verification** (7 confirmed, 11 partially confirmed — real but narrower or less severe than first claimed); 11 were refuted. Severities below are post-verification, which downgraded several findings the seats had rated higher. The refuted list is included at the end because it is itself informative: most refutations succeeded by citing a hedge or continuation path the corpus already contains, which is evidence of how unusually well-defended this design is.

## Executive conclusion

**All three seat questions come back qualified-yes.** I would rather author, implement, and review from this artifact than from a plan-mode document or a post-facto PR description, and — unlike at Round 1 — the surviving defects are now mostly concentrated in specific instrument wording and one flagship example, not in the design's basic shape.

| Question | Answer |
| --- | --- |
| Would it work for an AI helping a user author an intent? | **Qualified yes** — excellent for decision-dense changes; one confirmed silent-failure mode (pre-existing implementation on the branch) and a fixed cost floor for trivial changes |
| Would it work for an AI implementing a change from an intent? | **Qualified yes** — better than a conventional plan; evidence-verification gaps around the would-fail procedure need hardening |
| Would it work for an AI reviewing a change against an intent? | **Qualified yes** — always completable, honest about limits; dependability requires the team to supply execution evidence and an output convention the guidance doesn't yet define |

Two structural observations frame everything below.

First, the corpus's strongest engineering is its treatment of agent failure modes. The fork admission test ("could the author approve once and accept either branch?") applied identically in all three seats, the near-total continuation-path coverage (`cannot verify`, amend-on-the-record, report-a-failed-change), the anti-inflation rules that stop review from demanding an exhaustive spec, and the confidence-marked fact discipline are all aimed at real, specific ways agents fail — and in simulation they would actually change behavior. Eleven of twenty-nine findings died in verification because the corpus had already hedged the concern. That ratio is rare.

Second, the response to Round 1 was **selective repair plus claim-narrowing**. The cheapest semantic contradictions were fixed and the decision classifier got a genuine rework, but most mechanism-level asks were answered by shrinking the promise instead of building the mechanism ("chain of custody" is now defined as cooperative continuity, evidence durability is now team latitude). Narrowing a claim is a legitimate resolution — the design is honest about what it no longer promises — but a reader of Round 1 should know that the evidence/state-machine machinery it asked for was not built, and `mechanics/review-guidance.md` was not touched at all.

## Seat-by-seat answers

### Would it work for me helping a user author an intent?

**Qualified yes.** On the rate-limiting cold start, the process produced a genuinely decision-dense intent where the `Needs your attention` items earned their round trips (per-IP vs per-account limiting surfaced as a lockout-vs-throttle consequence a non-code-reading author could rule on). On the session harvest, the Phase 1 brief gate is exactly right: the Rejected section is the only mechanism that catches a mis-harvested half-decision before exploration is spent on the wrong change. The skill is written for how agents actually drift — "You will want to start reading code immediately... Emit it anyway" (authoring-skill.md:81), the fluent-wrong-baseline warning (authoring-skill.md:95), the private candidate list that keeps triage bookkeeping out of the author's view (authoring-skill.md:96, 178), and the "could the author rule from this entry alone, without opening a single file?" test (authoring-skill.md:184) — and those counter-instructions would genuinely change my behavior.

The qualifications: the one confirmed silent-failure mode is a branch that already contains implementation (Finding 1 below) — the skill has no entry mode or fact-marking rule for it, so Phase 2 reads the prototype as ⟨verified⟩ current-system fact and the draft anchors to the very code the intent is supposed to precede, reproducing the backfilled intent the agents block calls "worse than none" while every instruction is followed. And the process does not scale to zero for trivial changes: a one-line fix whose request already contains the outcome, why, and constraints still triggers the unconditional cold-start ask plus a brief-and-stop, two author turns carrying near-zero information (Finding 8).

### Would it work for me implementing a change from an intent?

**Qualified yes, and better than a conventional plan.** Simulated end to end on the GetUser-cache intent: every acceptance criterion admits a passing test plus a reversible product-mutation would-fail demonstration; the invariants resolve to concrete tests plus cross-path reasoning with an explicit, goal-accepted "surface material uncertainty" end state (implementation-guidance.md:36; design.md:414); constraints are explicitly not proof obligations; and the amendment channel gives a sanctioned alternative to the fabricate/drift/stall triad the design correctly names (design.md:310). The A1 amendment is mechanically writable from the format rules without guesswork, including the double-amendment chain case. Implementation latitude plus the five-rule precedence is a real decision procedure that a plan never provides.

The qualifications are about evidence, not decisions. Restoration of temporary mutations is stated as an outcome with no transcript-checkable obligation — a forgotten second temporary edit in a file the re-run tests don't touch produces a transcript indistinguishable from a clean one, and the transcript-reading Haiku evaluator cannot see the worktree (Finding 4). The procedure also silently assumes an exclusive, uninterrupted worktree and selective staging for the mid-work intent commit (Finding 13). And the amendment-eligibility enumeration omits project instructions even though three other sentences make them binding, leaving a claim-vs-CLAUDE.md conflict between a strict reading (report a failed change) and a generous one (amend, and get flagged ineligible by a literal reviewer) (Finding 7).

### Would it work for me reviewing a change against an intent?

**Qualified yes — always completable, honest, and materially better than reviewing without the artifact; not yet dependable as an independent gate without team-supplied plumbing.** The continuation-path design is real: `cannot verify` is a first-class result, the amendment coherence checks are mechanically executable from the file alone (terminal `Now` matches body, chained `Was`/`Now`, explicit additions/removals), the anti-inflation rules stop me from flagging incidental effects as missing intent, and the exclusion rule — waives missing work, never a shipped defect — is exactly right. In simulation this seat never hit a state with no legal move.

What the guidance under-defines is the semantics and destination of my own verdicts. `Met` on an acceptance criterion requires evidence a test passes, which the minimum stated inputs (intent, diff, tests, repository — no execution, no session) cannot supply, so a review operation without test execution either reports `cannot verify` on every AC or silently substitutes inference for execution. `Met` on an invariant quantified "across all caller paths" has no defined scope, and no required output artifact or overall disposition exists — the ordinary-review half of the job carries no trace obligation at all, so a review that skipped it is indistinguishable from one that ran it clean (Finding 5). The team-latitude framing genuinely covers some of this, but the instrument would be substantially stronger if it named the minimum: a verdict-table convention, a disposition rule for `cannot verify`-heavy results, and a reviewed-boundary statement for universal invariants.

### The two supporting lenses

**Internal consistency: qualified yes.** For a corpus that restates most rules in four or five places, drift is remarkably low — the fork admission test appears at least six times with no semantic variation, and the precedence order, amendment format, constraint semantics, and replacement semantics are verbatim-consistent across all instruments. The three real consistency defects found are Findings 2, 3, and 7 below, all fixable with targeted wording.

**Adoption: install a subset, not the system as written.** The genuinely differentiated mechanisms over plan-mode docs, ADRs, Kiro-style specs, and PR templates are the fork admission test (what keeps the artifact small), the `Was`/`Now` amendment record (what kills silent mid-flight drift), and frozen history (what kills spec rot — a 2,000-file `change-intent/` folder is inert context, not a growing requirements liability). Break-even sits at changes carrying at least one genuinely unsettled change-defining decision or a cross-cutting guarantee; below that line the process is net-negative and the corpus mandates it anyway (Findings 8, 6, 18). A pilot scoped to a subsystem or change-size threshold, with the would-fail demonstration reserved for high-risk ACs and self-built instrumentation of review outcomes, is the responsible install.

## Fact-check: `/goal`

The design's load-bearing external dependency checks out. Official docs confirm every claim in design.md's `/goal` section: requires v2.1.139+, sets a completion condition evaluated after each turn by the configured small fast model (Haiku default), and the evaluator "does not call tools, so it can only judge what Claude has already surfaced in the conversation." The "May 2026" ship date is corroborated only by third-party coverage, not the official changelog — immaterial.

## What happened to Round 1

Of Round 1's five blocking findings, four major findings, the worked-example defect, and nine "additional improvements": **none is fully addressed, five are partially addressed, and fourteen are open.** The commit `47b0dcf` concentrated on the cheapest-to-fix semantic contradictions and the decision classifier; `review-guidance.md` was not modified at all.

| Round 1 finding | Status | What happened |
| --- | --- | --- |
| B1: baseline vs provisional candidate confusion | Partially addressed | "Provisional" semantics defined (design.md:300), whole-file acceptance defined (design.md:314), and per-amendment disposition is now a documented rejection — but replacement mode still pre-fills from the amended body without surfacing unratified amendment-derived wording, so accidental laundering of a provisional ruling into an approved baseline remains mechanically possible |
| B2: chain of custody not durable/revision-bound | Partially addressed (by reframing) | "Chain of custody" redefined as cooperative continuity, not provenance (README.md:5); evidence durability delegated to teams. No revision binding, invalidation rule, or handoff inputs were built. The recorded rationale answers the adversary objection Round 1 explicitly set aside, not the cooperative-staleness one |
| B3: undefined non-happy-path continuations | Partially addressed | Project-instruction conflicts now have a stop path (implementation-guidance.md:45) and amendment authority explicitly cannot expand operational permissions (:57). High-risk precedence ties remain "select either and continue" |
| B4: no authoring repository-state preflight | **Open** | No Phase 0 was added; independently re-confirmed this round as the top authoring defect (Finding 1) |
| B5: decision test depends on private counterfactuals | Partially addressed | The deepest rework: consequence-first admission, "reasonable branch" defined, don't-stop-at-two, ambiguity-goes-to-author (authoring-skill.md:176). Delegation envelope, latitude-veto section, and high-risk presumption were not adopted |
| M6: outcomes can fail while process declares complete | Open | "Plausibly delivers" still has no evidence definition; the near-zero-TTL scenario still passes every AC |
| M7: review not operationally independent | Open | File untouched |
| M8: replacement erases the anchoring signal | Open | No supersession record; pre-existing deliberate-tradeoff text unchanged |
| M9: "every change" doesn't scale | Partially addressed | Gates reduced 4→2; friction named as the optimization target (design.md:46). No compact, emergency, or stacked/cross-repo lanes |
| Worked-example defect (A1 fact known at authoring) | **Open** | Unchanged; independently re-confirmed this round (Finding 3) |
| All nine "additional improvements" (stable IDs, minimum review artifact, causality check, proving-test definition, coverage-limit survival, durable eligibility evidence, linter + eval corpus, artifact hygiene, role of historical intents) | Open | No changes found in the diff |

## Verified findings

### Confirmed — major

**1. No branch-state handling: pre-existing implementation silently poisons authoring.** The skill enumerates exactly three entry modes — session harvest, cold start, replacement (authoring-skill.md:36-40) — with no detection step, entry mode, or fact-marking rule for a branch or working tree already containing candidate implementation. The design legitimizes prototype-first work (design.md:274) and the agents block forbids backfilling (agents-md-block.md:25), but the instrument the executing agent actually loads carries none of it: Phase 2's "Read the code the change touches" (authoring-skill.md:91) marks the prototype's behavior ⟨verified⟩, and by the skill's own warning the author cannot catch a fluent wrong baseline (authoring-skill.md:95). Every instruction is followed and the result is functionally the backfilled intent the corpus calls "worse than none." Secondary gap in the same area: Phase 4 says to commit the approved file "before implementation begins" but never says where, or what to do when the intended branch state is dirty. *Fix: add a preflight (branch, merge base, working-tree diff, existing intent files) and an explicit entry mode for prototype-in-tree, with a fact-marking rule that separates baseline behavior from candidate-implementation behavior. This is Round 1's B4; two independent rounds have now landed on it.*

**2. The review instrument's eligibility test excludes an amendment the design sanctions.** design.md:294 and implementation-guidance.md:42 both authorize amending an acceptance criterion whose behavior can be delivered but cannot be proved by any reasonable test available to the change (reword into provable form, or move to Outcomes/Constraints). review-guidance.md:23 defines eligibility as exactly two prongs — undeliverable within boundaries, or missing necessary decision — and a deliverable-but-unprovable claim fails both read literally. The instrument even enumerates its one proof-related rule ("Inability to prove a constraint is not eligible") while omitting the AC-provability inclusion, inviting the enumerated-case reading. A reviewer following its own self-contained instrument will judge a design-sanctioned repair ineligible and report it "with the same severity as a `not met` acceptance criterion" (design.md:321) — a false blocking-grade finding on the channel the design calls the highest-signal part of the returned work. *Fix: one sentence adding the third prong to review-guidance.md:23.*

**3. The flagship worked example demonstrates an authoring failure and presents it as the amendment channel working.** design.md:463 lists "GetUser(userID) returns the user, or nil for users that don't exist" among what authoring-time exploration found; design.md:508 then has the implementation agent "discover" that same fact and amend for negative-result caching — while conceding the branches "deliver different changes," i.e. the fork passes admission and belonged in the approved intent. The skill's own mandatory causal-continuity sweep (authoring-skill.md:104-114 — trace later behavior that can observe the result; ask what happens on a lost race) makes creation-after-cached-miss discoverable by rule from a fact already on the verified list. By the corpus's own standard — "a decision that a diligent pass should have found is a defect when later discovered" (design.md:541) — A1 is an authoring defect, presented without acknowledgment. *Fix: use a genuinely implementation-only discovery for the example, or keep it and annotate it as an authoring miss the amendment channel absorbed — which would actually strengthen the example.*

### Partially confirmed — moderate

**4. Would-fail evidence has no transcript-checkable restoration obligation, and the evaluator is its only verifier.** Restoration is stated as an outcome ("Never commit a temporary mutation," implementation-guidance.md:34; :99) whose only shown evidence is the re-passing test; a forgotten second temporary edit in a file the re-run tests don't touch survives invisibly, and the transcript-only Haiku evaluator (design.md:371-372, 380) cannot see the worktree. The claim-specific-failure judgment (implementation-guidance.md:31) is also exactly the discrimination a small evaluator over a long transcript is worst at. *Fix: require final `git status`/`git diff` surfaced in the transcript as restoration evidence, and note the evaluator-capability assumption.*

**5. "Your existing review still runs in full" has no trace requirement.** Intent-side judgments carry per-item basis obligations (review-guidance.md:20-21); the ordinary-review half carries none, so shrinkage is unobservable downstream — a review that skipped ordinary coverage is indistinguishable from one that ran it clean. The prohibition and the change-too-large stop condition (review-guidance.md:33) are real countermeasures, but they are self-instruction inside one intent-anchored context. *Fix: a symmetric minimal reporting obligation for the ordinary pass, and a note that teams may run it as a separate unanchored pass.*

**6. No incremental adoption path.** The agents-file block is repo-global and "designed to be used verbatim"; once pasted, agents decline intent-less implementation (agents-md-block.md:25) and review flags every intent-less PR (review-guidance.md:11). A half-adopted repo generates structural noise that trains reviewers to ignore intent findings, and the corpus never addresses scoping by path, team, or change class. *Fix: document a pilot scoping pattern; it costs a paragraph.*

**7. Amendment eligibility enumerations omit project instructions.** Trigger 1 enumerates "outcomes, constraints, or exclusions" (implementation-guidance.md:42; mirrored at review-guidance.md:23) while :11, :45, and :57 make project instructions binding. Strict reading: a claim blocked solely by a project instruction has no eligible repair and forces a failed-change report; generous reading: the agent amends and a literal reviewer must flag it ineligible. The worst realistic outcome is ceremony rather than harm, but the instruments claim "explicit rules, enumerated cases" as their standard. *Fix: add project instructions to both enumerations.*

**8. The two author gates never scale to zero, and cold start can't pre-fill from a content-bearing request.** A bare one-sentence request is a cold start requiring the ask (authoring-skill.md:39) even when the sentence already contains the outcome, why, and constraints — conspicuous because Replacement mode is explicitly allowed to pre-fill its brief. Verification correctly reassigned most of the claimed cost floor to the design's agent-cheap cost model and the sweeps' short-circuits; what survives is one redundant author round-trip on exactly the changes where the process is most resented. *Fix: let cold start pre-fill the brief from the request and present it for confirmation — same gate, one turn instead of two.*

**9. "Review less over time" collects no evidence.** Review verdicts, human findings, and post-merge defects are never durably tied to intents; the merged intent is frozen without the assessment and the file format forbids added metadata. The per-change "review better" value is unaffected, and the trajectory is framed as a premise partly outside the design (notes.md), but a team that pays today's overhead for tomorrow's reduction will discover after a year that it has no dataset distinguishing "AI review was sufficient" from "the human kept catching what AI missed." The single named metric — amendment count — diagnoses authoring, not review safety. See also Finding 17.

**10. Approval sequencing at the load-bearing gate supports two readings.** authoring-skill.md:209-214 does not pin whether presenting the final assembled file solicits a reaction or announces a fait accompli before commit, and "Approval is explicit" is never operationalized against utterances ("looks good"? "ok, now implement it"?). Verification downgraded this to minor-moderate — both readings preserve an explicit approval of content — but after several diff-applied rulings (the skill's preferred mode, :196) the author may never have seen the assembled text they approved. *Fix: require one confirmation on the assembled final file when rulings were applied as diffs.*

### Minor

**11. Self-contradiction on proposal headings.** authoring-skill.md:255 says "the proposal shows every heading" — contradicted on either parse by :130 (`Needs your attention` omitted when empty) and :151-155 (draft has empty sections omitted). The operative rules are consistent; the explanatory aside at :255 is false.

**12. Phase 1 harvest buckets underdetermined.** The rule "never into What" (authoring-skill.md:38) references a brief section that doesn't exist (stale name — the template says Outcomes), and the promise "Anything under Rejected will NOT appear in the draft" (:77-78) collides with Out of scope's job of carrying considered-and-excluded direction into the record, with no assignment rule between Rejected, Deferred, and Out of scope.

**13. The would-fail procedure assumes an exclusive, uninterrupted worktree.** No single-writer assumption is stated, no isolation guidance is given, an interruption between mutation and restore leaves falsified product code on disk with only the next turn's memory to fix it, and the mid-work "commit the amended intent before continuing" requires unstated selective staging while temporary mutations sit in the tree.

**14. The stop condition is enumerated at two strengths.** "Only when no amendment can preserve the approved outcomes and constraints" (design.md:54, 316; agents-md-block.md:30) vs "outcomes, constraints, and exclusions... or an applicable project instruction" (design.md:298; implementation-guidance.md:45). The practical window is narrow but the instruments claim enumerated-case precision.

**15. The same exclusion is a Constraint in the worked example and the canonical Out of scope exemplar.** "Do not introduce distributed cache coordination" (design.md:490, Constraints) vs "Distributed cache coordination... Single-node cache only for now" (design.md:197, the leading Out of scope example), with no tiebreak rule for prohibition-shaped exclusions. Downstream divergence is smaller than it looks, but authoring determinism suffers.

**16. Workflow step 4 hands the author's rulings to "the human reviewer."** design.md:406 attributes accepting amendments and replacing the intent to the human reviewer; every other statement in the corpus reserves both to the author. Teams may combine the seats, but the sentence assigns rather than permits.

**17. Only one direction of the fork-admission test's error rate has a diagnostic.** Missed decisions surface as amendments (design.md:345); over-asking — unnecessary `Needs your attention` items that double author cost and train authors to skim — has no counterpart signal anywhere. The scarce resource the design optimizes is author attention, and its consumption is unmeasured.

**18. "Instead of plan mode" mis-prices adoption.** For the large fraction of changes that receive no formal planning today, the process is new spend, not a substitution — precisely the changes where the fixed floor bites (Findings 6, 8).

## What should be preserved

1. **Complete over change-defining decisions, open over implementation**, enforced by one fork-admission test applied identically in authoring, implementation, and review. This is the genuinely novel mechanism relative to plan-mode docs, ADRs, spec-driven development, and PR templates, and it is what keeps the artifact small.
2. **Author owns direction, agent owns the map**, with confidence-marked facts and source tags making agent-invented direction visible instead of fluent.
3. **Continuation paths for every role**, including sanctioned failure — `cannot verify`, amend-on-the-record, report-a-failed-change — directly preempting the fabricate/drift/stall triad.
4. **The amendment record**: fact-shaped discovery statements, verbatim `Was`/`Now`, mechanical coherence checks executable from the file alone, and rarity as a load-bearing property.
5. **Frozen history plus "merged intents never govern later changes"** — designs away the spec rot that kills comparable durable-documentation processes.
6. **The anti-inflation rules in review** and the exclusion semantics (waives missing work, never a shipped defect).
7. **Deliberate tradeoffs documented in place with rationale** — several apparent gaps chased this round resolved into one of these passages, which is exactly what that documentation is for.
8. **The two-voice separation** between adopter-facing memo and agent-facing instrument.

## Raised and refuted

Eleven findings were killed by the default-refute verification pass, typically by locating corpus text that already handles the concern or a documented tradeoff the finding merely re-weighed. Notably refuted: the claimed hard dead-end when no safe would-fail falsification exists (implementation-guidance.md:34 defines the report-the-gap continuation and design.md:380 says the evaluator "does not demand proof that an unavailable environment cannot provide" — the residual weakness is captured in Finding 4); the claimed instability of the admission test between competent agents (the `47b0dcf` rework routes genuine ambiguity to the author, authoring-skill.md:176); the precedence tie-break on security-defining forks; session-scoped eligibility evidence; underdetermined `met` semantics; silent baseline drift; the missing review output artifact as a *blocking* defect (survives only as Finding 5's trace asymmetry); "verbatim" matching vs markdown re-wrapping; the provisional-content naming issue; and the historical-intents consultation bar. Several of these remain fair *suggestions* (and appear in Round 1's still-open list) — they are refuted as defects, not as improvements.

## Recommended revision order

1. **Fix the three confirmed majors** — all cheap: an authoring preflight/entry mode for in-tree implementation (also closes Round 1's B4); the third eligibility prong in review-guidance.md; repair or annotate the worked example's A1.
2. **Harden would-fail evidence**: transcript-surfaced `git status`/`git diff` after restoration; a stated worktree-isolation assumption; selective-staging instruction for the mid-work intent commit.
3. **Give the ordinary-review half a trace obligation** and name a minimum verdict-table/disposition convention, even if only as a recommended default within team latitude.
4. **Add the adoption on-ramps**: a documented pilot scoping pattern and a cold-start pre-fill path (one gate, one turn).
5. **Sweep the minor drift**: stop-condition enumerations, the stale "What" reference, the :255 heading aside, a Constraint-vs-Out-of-scope tiebreak, design.md:406's seat wording, Rejected-vs-Out-of-scope assignment.
6. **Decide the trajectory question explicitly**: either instrument review outcomes (even minimally) or scope the "review less" claim the way `47b0dcf` scoped "chain of custody."

## Final assessment

Round 1 judged the design "reliable mainly on the happy path." After `47b0dcf`, the happy path is wider and the claims are more honest, and this round's harder look — five seats simulating the process concretely, with an adversarial pass killing eleven of twenty-nine findings — confirms the core is sound in all three seats. What separates it from an unqualified yes is no longer the design's shape: it is one silent authoring failure mode, a handful of instrument sentences that contradict each other or the design, a flagship example that undermines the process it demonstrates, and evidence plumbing the design now officially leaves to teams but does not help them build. All of the confirmed defects are wording-level fixes. The partially-confirmed ones are where the real design work remains — and they are the same evidence-durability and scaling questions Round 1 raised, still open, now with a narrower blast radius because the design promises less.

---

# Addendum — reconsideration under the design's stated constraints

**Date:** 2026-07-16, same day as Round 2. This addendum responds to feedback from the design's author clarifying the constraints the review should have weighed findings against. The Round 2 body above is left unchanged as a record; this section re-triages it.

## The constraints, as clarified

Change intent is a **workflow contract in the same sense that "pick up a ticket, say when you're done, ask a teammate to review before merge" is one** — real, load-bearing, and almost entirely informal. The design goals that follow: the adoption bar is a few repository file changes, with no change to team structure or development practices; nothing in it may become a blocker — everything exists to make changes faster and smoother; it is cooperative, not mechanical and not adversarial; and adopting teams have structures the design cannot know, so they must be free to reshape it. Proposed fixes are therefore admissible only when they are (a) a wording repair inside an existing instrument, (b) a sentence of explicitly granted latitude, or (c) a claim honestly scoped to what the design delivers. No new phases, gates, artifacts, required formats, or tooling.

The design serves five purposes that fit together, and the corpus expresses all five but never enumerates them in one place:

| # | Purpose | Where it lives today |
| --- | --- | --- |
| 1 | The human author gets clarity about a change that usually starts muddled — especially with AI in the loop | The forcing-function argument (design.md:261) and the Phase 1–4 dialogue; framed mostly as a review benefit rather than an author benefit |
| 2 | A platform for AI to drive itself to goal completion — specific enough that a coding-harness goal works naturally | The `/goal` integration section (design.md:367-419) |
| 3 | The human reviewer gets confidence from **consistency** in how changes are developed, implemented, and reviewed — the thing uneven AI adoption across a team destroys | design.md:397-399 ("Because every change passes through the same chain... A teammate's change arrives with the same frame as the reviewer's own") — present but buried; this is the sharpest under-expressed purpose |
| 4 | The highest-value tokens are saved into the repository, because future *agents* — unlike future humans — really will read past intents when shaping decisions | README.md:5, design.md:559-569, and Working in Public |
| 5 | Forward-shaped toward less human authoring and less human review | design.md:277-281, notes.md:8-40 |

Much of the framing confusion in both review rounds traces to reading the design against purpose 3's parent (reviewability) alone. A short enumeration of the five purposes in the README — a documentation edit, not a mechanic — would give every future reader, and every future reviewer, the correct acceptance test for a proposed change to the design: *does it serve one of these five without adding a step for the team?* Several Round 1 asks (state machines, evidence envelopes, hash binding, mandatory two-pass review) fail that test cleanly, which is a faster and more principled rejection than arguing each on its merits.

## Re-triage of the Round 2 findings

The re-triage confirms something worth stating plainly: **in a deliberately lightweight process, the instrument wording is the only mechanics there is — so wording precision is not bureaucracy, it is the entire defect surface.** Every confirmed finding survives this re-triage precisely because it is a wording defect, and each admits a fix that adds nothing to the team's experience of the process.

| Finding | Disposition | Admissible fix |
| --- | --- | --- |
| 1. Branch-state poisoning | **Keep (major)** | Recast from "add a Phase 0" to one or two sentences in Phase 2's fact rules: the baseline is the change's base, not unmerged candidate implementation sitting on the branch; if the branch already carries implementation of the requested change, say so. Agent-side only; no new author gate; the agent already runs git. Silent poisoning of the fact base defeats purpose 1 invisibly, which is why it stays major |
| 2. Review eligibility omits the sanctioned unprovable-AC amendment | **Keep (major)** | One sentence in review-guidance.md:23. Directly serves the not-a-blocker goal: the current text makes the review seat generate false blocking findings against legitimate repairs |
| 3. Worked example's A1 is an authoring miss | **Keep (major)** | Documentation-only, and the cooperative framing makes the *annotation* option on-message: design.md:345 already says amendments mark authoring misses — owning that in the flagship example demonstrates the diagnostic honestly instead of undermining it |
| 4. Restoration has no transcript-checkable evidence | **Keep, reduced** | One line in the existing would-fail procedure: surface `git status`/`git diff` after restoration. A catch-mistakes self-check — exactly the category the no-adversary principle already embraces. All envelope/attestation thinking from Round 1 is retracted below |
| 5. Ordinary-review trace asymmetry | **Downgrade to minor, recast** | Extend the existing sentence at review-guidance.md:13 by one clause so "report what you established" covers the ordinary half. The original failure story ("shrinkage is unobservable") quietly assumed nobody reads the review output — in the actual workflow the human reviewer consumes it, which is the cooperative contract doing its job. The required verdict-table convention is retracted as a requirement |
| 6. No incremental adoption path | **Keep, strengthened by the constraints** | The stated goal is that teams can *experiment*; the block as pasted makes the experiment repo-global and binding ("Every change," agents refuse intent-less work). One sentence of granted latitude — teams may scope adoption to a directory, subteam, or change class during a pilot — is all that's missing, and it is the same latitude move the corpus makes everywhere else |
| 7. Eligibility enumerations omit project instructions | **Keep (minor)** | Add project instructions to the two enumerations. Pure consistency |
| 8. Cold start can't pre-fill from a content-bearing request | **Keep** | Allow pre-filling the brief for confirmation — the same gate in one author turn instead of two. This *removes* a round trip; it is the most on-mission fix in the list |
| 9. "Review less" collects no evidence | **Mostly dissolves** | Under purpose 5 as clarified — forward *shaping*, with AI improvement explicitly outside scope — instrumentation is out of bounds by design. The residue is one honest sentence in notes.md: a team that wants to *act* on reviewing less will need its own signal, and has latitude to build one. Same move `47b0dcf` made with chain of custody |
| 10. Approval sequencing ambiguous | **Keep (minor)** | One sentence: when rulings were applied as diffs, confirm on the assembled final file. Protects purpose 1 at its single load-bearing moment; also gives the author seat a machine-legible approval form for the autonomous case |
| 11–16, 18 (wording/consistency sweep) | **Keep (minor)** | All are wording repairs inside existing instruments with zero adoption cost. 13's fix is one stated assumption (exclusive worktree during temporary mutations) — which matters more, not less, under multi-agent operation |
| 17. No over-asking diagnostic | **Mostly dissolves** | In a cooperative team the over-asking signal is the author's lived annoyance, surfaced socially — the informal contract handles it. At most one sentence naming it |

## What this addendum retracts from Round 2

- **Characterizing `47b0dcf`'s claim-narrowing as "shrinking the promise."** Under the stated design goals, scoping "chain of custody" to cooperative continuity and delegating evidence durability to teams was the *correct* resolution, not an evasion: a lightweight contract should promise exactly what it delivers. The delta table's facts stand; that editorial frame does not.
- **The verdict-table/disposition convention as a definition ask.** At most, a non-normative example a team may copy. Requiring an output format is a mechanic.
- **Any residual Round 1 machinery** endorsed by implication — state machines, revision/hash binding, evidence envelopes, mandatory two-pass review. All fail the purpose test above. The right reference class for this design is the informal ticket-review-merge contract, formalized only at the artifact.

What does **not** relax: the wording-precision findings. Those get more important as the process gets lighter and as more seats go autonomous, because agents execute instruments literally, and a human's shrug at an ambiguous sentence is exactly the error-absorption that disappears when the human does.

## Could change intent run entirely on AI — authoring, implementation, and review, many agents driving outcomes?

**Yes — and more than "could": this design is more ready for that end state than any comparable process reviewed here, because it was visibly designed backward from it.** The features that matter for full autonomy are already the design's core features:

- **Every seat is a logical responsibility with a defined continuation path.** Agent systems fail at undefined states far more than at hard work; `cannot verify`, amend-on-the-record, and report-a-failed-change mean no seat ever needs a human to get unstuck. This is the single most autonomy-critical property a process can have, and it is already the design's strongest rule.
- **The artifact is the coordination medium.** A file-based, diffable record that is complete over decisions and open over implementation is exactly the thin durable handoff multi-agent orchestration wants. Nothing about the contract assumes a human on either end of any arrow in author → implement → review.
- **The fork admission test doubles as an escalation rule.** For an AI orchestrator in the author seat, "does choosing between branches decide which change is delivered?" is precisely the test for *what must be pushed up to the authority boundary* versus decided locally. Humans need that discipline; orchestrators are lost without it.
- **The amendment channel is the sanctioned repair loop autonomous implementation needs** to avoid the fabricate/drift/stall triad — which the design names explicitly and which is the observed failure profile of unsupervised coding agents.
- **Two independent machine checks already exist** (the in-loop goal evaluator and the review pass), with the design's insistence that neither substitutes for the other.
- As direct evidence: this review round itself ran the seats. Five AI agents independently occupied authoring, implementation, and review against this corpus, executed their instruments to completion, and returned structured judgments — including honest `cannot verify`-shaped limits. The seats are occupiable today.

Three things determine how fast "could" becomes "does":

1. **The author seat's authority boundary, not its dialogue.** The mechanics of authoring are automatable now; what an AI author needs is an upstream objective and an authority envelope — which the design already scopes correctly to the team's operating model (design.md:277-281) rather than pretending to solve. This is the binding constraint, and it is organizational, not technical.
2. **Instrument wording precision.** In full autonomy the review agent executes review-guidance.md literally at scale; Finding 2's false-blocking-finding defect goes from occasional friction to a systematic tax. The wording fixes above are the cheap insurance premium for the autonomous trajectory.
3. **Concurrency hygiene.** Many agents driving outcomes means the one-current-intent rule (natural serialization — good) plus Finding 13's unstated exclusive-worktree assumption (one sentence — needed).

Purpose 3 also inverts elegantly under autonomy rather than disappearing: when no human reviews each change, the consistent per-change frame becomes the substrate a human *samples* when auditing the autonomous pipeline — the same artifact serving supervision instead of review. That continuity between today's use and tomorrow's is the design earning its forward-looking claim.

## Revised recommendation order (all wording-level; nothing adds a step)

1. The three confirmed majors: the Phase 2 baseline sentence; the third eligibility prong; fix or annotate the worked example.
2. The one-turn cold start (removes a round trip) and the pilot-scoping latitude sentence (lowers the bar to experiment). These two most directly serve the stated goals.
3. The self-check line in the would-fail procedure and the exclusive-worktree assumption.
4. The minor wording sweep (Findings 7, 10–16, 18) plus the one-clause extension at review-guidance.md:13.
5. Enumerate the five purposes once in the README, and scope the "review less" claim in notes.md the way chain of custody was scoped.
