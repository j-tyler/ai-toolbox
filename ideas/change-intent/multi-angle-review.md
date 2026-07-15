# Change Intent: Multi-Angle Design Review

**Reviewed revision:** `b9c3c71` (`codex/change-intent-decision-complete-h`)  
**Review date:** 2026-07-15  
**Scope:** Every file under `ideas/change-intent/`, plus the root framing and the related Working in Public stub.

## Method

The design was read end to end, then assessed independently from three seats:

1. an AI helping a user author an intent;
2. an AI implementing a change from that intent;
3. an independent AI reviewing the result against that intent.

The review also pressure-tested replacements, amendments, unavailable evidence, cross-cutting invariants, small and urgent changes, stacked and cross-repository work, and concurrent agents. The current Claude Code `/goal` behavior was checked against the official documentation because the downstream design depends on it.

## Executive conclusion

The central idea is good. I would rather author, implement, and review from this artifact than from an ordinary plan or post-facto pull-request description. The best sentence in the design is **complete over change-defining decisions and open over implementation**. That is the right division: decide what change is being approved without prescribing every technical choice.

The current design is nevertheless reliable mainly on the happy path: a material, bounded, single-repository change; a clean branch; inspectable code; locally runnable tests; no high-risk missing decision; no amendment; and one implementation session. Outside that path, the process often knows what question should be asked but does not define the state, evidence, or handoff required to answer it.

My readiness judgment is:

| Intended use | Judgment |
| --- | --- |
| Pilot on material, bounded changes after the blocking fixes below | **Yes** |
| Use as a helpful decision artifact today | **Yes** |
| Install unchanged as the mandatory process for every change | **No** |
| Treat it as a visible chain of custody | **Not yet** |
| Use it to justify less human review | **Not yet** |

The design should be preserved and completed, not discarded. Its largest problems are in lifecycle mechanics rather than in the intent file's basic shape.

## Role-by-role answer

### Would it work for me while helping a user author an intent?

**Yes for a material, bounded change, with qualifications.** The brief gate, author/agent responsibility split, confidence-marked exploration, source-tagged proposal, coverage limits, and separation of claims from constraints would make me a better design partner. They force me to expose what I inferred from the repository and what I invented for the user to decide.

It would not yet work reliably as a universal authoring workflow. I could unknowingly backfill an already implemented branch because there is no repository-state preflight. I must privately decide which forks the author would care about, then hide every candidate I classify as implementation latitude. The fixed A/B and code-snippet decision template cannot cleanly represent greenfield, configuration, documentation, infrastructure, licensing, or multi-option decisions. The mandatory four phases and two author-facing gates are also disproportionate for exact reverts and tiny mechanical changes.

### Would it work for me while implementing a change from an intent?

**Yes in the happy path, and it would be better than a conventional plan.** Outcomes orient tradeoffs, acceptance criteria define focused proof, invariants force cross-path reasoning, constraints preserve real engineering boundaries, and Out of scope limits opportunistic expansion. The explicit implementation latitude is particularly important: it lets me engineer rather than repeatedly ask the author to decide ordinary mechanisms.

It is not yet a complete autonomous protocol. The mandatory semantic would-fail procedure has a literal dead end when no safe negative control exists. Material invariant uncertainty has no implementation status corresponding to review's `cannot verify`. Missing decisions can force the implementer to choose arbitrary or unsafe product direction. The strongest evidence may remain in one session, and no harness-neutral result binds that evidence to the intent and code revision. In Codex I can follow the instructions, but I do not have Claude Code's exact `/goal` evaluator; `/goal` needs to be one adapter to a portable completion contract, not the implicit architecture.

### Would it work for me while reviewing a change against an intent?

**Yes as a substantial review aid; no as a dependable independent gate in its current form.** The artifact gives me explicit claims, conscious exclusions, constraints, amendment records, and permission to report uncertainty. The instruction to keep ordinary review separate from intent alignment is correct, and the reverse decision sweep can catch drift that a claim-only review misses.

The current reviewer often lacks the inputs needed to reach the required conclusions. Implementation evidence can disappear with the session. Amendment eligibility depends on alternatives that are not preserved. Broad invariant results do not record the reviewed boundary. Nothing binds the assessment to an exact code and intent revision. `Cannot verify` is honest, but there is no required overall `incomplete` state or disposition. Reading the intent first can also anchor the reviewer and weaken the open-ended defect search.

## What should be preserved

The following are strong and should survive any revision:

1. **Author owns direction; agent owns the map.** This is clear in `mechanics/authoring-skill.md:14-18` and `design.md:421-425`.
2. **A confirmed brief before solution and change-surface exploration.** Separating affirmed, rejected, and deferred direction is a useful anti-misread gate after repository-state preflight and resolution of user-supplied issue or specification references (`mechanics/authoring-skill.md:34-83`).
3. **Complete over change-defining decisions, open over implementation.** This prevents both underspecification and implementation micromanagement (`design.md:66-78`).
4. **Different roles for Outcomes, Constraints, Acceptance criteria, Invariants, and Out of scope.** The distinctions are meaningful downstream (`design.md:82-205`).
5. **Confidence-marked facts, bounded exploration, and explicit coverage limits.** These counter fluent but unsupported repository claims (`mechanics/authoring-skill.md:87-121`).
6. **Source tags during approval.** Agent-proposed direction remains visible instead of being presented as a translation of the user's words (`mechanics/authoring-skill.md:168-177,204-206`).
7. **Narrow amendments rather than silent reinterpretation.** The necessity test and exact `Was`/`Now` record are directionally right (`design.md:282-335`).
8. **Ordinary review remains fully applicable.** Intent silence and exclusions never excuse security, correctness, concurrency, or quality defects (`mechanics/review-guidance.md:27-34`).
9. **`Cannot verify` is allowed.** The reviewer is not forced to manufacture certainty (`design.md:389,537-545`).
10. **No adversary is a reasonable premise.** The process need not become a compliance ledger. It still needs referential integrity to prevent cooperative mistakes.

## Blocking findings

### 1. The lifecycle confuses an approved baseline with a provisional amended candidate

The design says a missing-decision amendment is provisional and the author rules on it when work returns (`design.md:298,304-314`; `mechanics/implementation-guidance.md:47-57`). It also says that implementation and review always have one “current approved intent” (`design.md:351,359-363`; `mechanics/agents-md-block.md:13-15`). Both cannot be true after the implementer changes the body but before the author accepts that change.

This is not just terminology. Replacement mode pre-fills from the current amended body and then deletes the Amendments section (`mechanics/authoring-skill.md:40`; `design.md:347-353`). An unrelated author revision can therefore launder a provisional implementation ruling into a clean, apparently author-approved baseline.

Example:

1. The author approves “revoked tokens are rejected within one minute.”
2. Implementation provisionally amends the claim to five minutes.
3. Returned work causes the author to change an unrelated outcome.
4. Replacement starts from the five-minute body and highlights only the new direction.
5. Approval removes the amendment history; the five-minute ruling has silently become author direction.

Define three states explicitly:

- **Approved baseline** — the exact author-approved wording and revision.
- **Current candidate** — the baseline plus provisional implementation amendments.
- **Accepted amended intent** — the current candidate only after the author explicitly disposes every amendment.

Add a returned-work/amendment-disposition instrument. It must present every amendment with its fact, approved `Was`, provisional `Now`, eligibility assessment, and implementation impact. The author must accept it or invoke replacement before merge. State whether whole-PR approval counts; do not let merge imply a ruling accidentally.

Replacement must begin from the last author-approved baseline, separately present every unratified amendment, and require an explicit accept/reject/replace decision before producing a clean file.

Approval semantics also need to be explicit: answering one decision is not final approval; material targeted diffs require approval of the resulting complete file; the accepted phrases or action that constitute approval must be defined; and implementation must not begin if writing or committing the approved intent fails.

### 2. The promised chain of custody is neither durable nor revision-bound

The overview promises a visible chain containing approval, implementation evidence, goal completion, amendments, and independent review (`ideas/change-intent/README.md:3`; `design.md:393-397`). The required handoff is only the current intent plus the diff and tests; implementation evidence may remain session-scoped (`design.md:361-363`; `mechanics/implementation-guidance.md:23-25`). Replacements erase the prior candidate, and no review output is bound to an exact revision.

The official Claude Code documentation confirms that `/goal` is session-scoped and that its evaluator only reads what the implementing agent surfaced in the conversation; it cannot inspect files or run commands independently: [Claude Code goals](https://code.claude.com/docs/en/goal). The repository's description of `/goal` is accurate. The problem is treating that session event as visible, durable custody for later consumers.

A cooperative team can accidentally combine:

- a cleared goal from revision N;
- an intent replacement from N+1;
- code changes from N+2;
- a review assessment from N+3.

Define a small harness-neutral evidence envelope or required PR check. It need not be another normative repository file, but it must include:

```text
intent_path
target_base
approved_baseline_revision_or_hash
current_intent_hash
implementation_revision

acceptance_criteria:
  id / proving test / command and environment / pass result /
  sensitivity evidence / restoration result
invariants:
  id / semantic boundary / discovery method / tests /
  reasoning / inaccessible surfaces / status
constraints:
  accounted for / conflict / implausible / cannot assess
amendments:
  eligibility evidence / alternatives / author disposition
ordinary_checks:
  build / test / lint and other project checks
implementation_state:
  complete / blocked-evidence / needs-author / failed-intent

reviewed_code_revision
reviewed_intent_hash
review_state:
  aligned / not-aligned / incomplete
```

Any code or intent change invalidates the corresponding completion and review result. This is referential integrity, not adversarial security.

The implementer must receive `intent_path`, `target_base`, and `approved_baseline_revision_or_hash` as handoff inputs, not infer them from the folder. Amendment review must validate each `Was` value against that approved baseline; the current rule that forbids reconstructing the approved wording makes `Was` self-authenticating.

### 3. Several non-happy-path states have no defined continuation

The design's strongest rule is that every role has a continuation path (`design.md:52-64`). The mechanics do not yet satisfy it.

#### No safe semantic falsification

Every acceptance criterion requires pass → temporary product mutation or negative state → claim-specific fail → restore → pass (`mechanics/implementation-guidance.md:27-34,97-99`). If neither safe mechanism exists, the agent must report an evidence gap but may not count the criterion complete. It also may not amend a true, testable claim. The goal cannot clear, yet no stop state exists.

Use an evidence hierarchy:

1. observed red-before-green on the pre-change baseline;
2. an isolated mutation tool or temporary checkout;
3. a local configuration, fake, or dependency negative control;
4. a claim-specific compile/static failure when that is the natural proof;
5. `cannot safely falsify` → `blocked-evidence`, resolved by CI or explicit team/human policy.

Allow an existing proving test when it already supplies strong red-before-green evidence. Never mutate shared worktrees or external/shared state. Parallel agents need isolated worktrees or an equivalent mutation runner.

Sensitivity is necessary but not sufficient: the proving test must exercise the relevant changed production path. A mutation of a mock, fixture, or disconnected helper can produce a clean claim-shaped failure while proving nothing about the code the pull request ships.

#### Material invariant uncertainty

Implementation must demonstrate every claim but is also told to surface uncertainty rather than manufacture closure (`mechanics/implementation-guidance.md:11,36,99`). Review has `met | not met | cannot verify`; implementation does not. A dynamic plugin, inaccessible downstream repository, generated caller, or external mutation path can leave the agent unable to prove, amend, fail, or finish.

Give implementation the same three-state vocabulary. Require each invariant to state its semantic boundary—service, operation, data domain, time window, and failure boundary where relevant—without listing every file, and whether the change **establishes** or **preserves** the property. Define the response when a preserved invariant is already false on an untouched baseline path: avoid new violations, expand scope, amend, or stop cannot be left to inference. Material `cannot verify` produces `blocked-evidence` or requires an explicit policy disposition; it cannot silently satisfy Done.

#### High-risk missing decisions

When precedence ties, the implementer selects either branch even though the branches are defined to deliver different changes (`design.md:294-312`; `mechanics/implementation-guidance.md:47-57`). That is acceptable for low-risk, reversible choices. It is not a safe universal rule for authorization, privacy, money movement, destructive migration, data loss or retention, legal/compliance, public compatibility, or other irreversible decisions.

Restrict provisional autonomous amendments to low-risk, reversible decisions. High-risk change-defining decisions return to the author before dependent implementation continues. “Do not wait for additional permission” must mean no additional product-direction approval for an eligible low-risk amendment; it never overrides filesystem, git, credential, deployment, or external-side-effect permissions.

Add the same explicit `needs-author` or `failed-intent` path when an applicable project instruction discovered during implementation conflicts with the approved intent. Project instructions are binding at `mechanics/implementation-guidance.md:11`, but the current amendment and failure boundaries are defined only in terms of Outcomes, Constraints, and exclusions.

### 4. Authoring has no repository-state preflight, so it can create a post-facto intent

The process forbids backfilling (`mechanics/agents-md-block.md:19-25`) but the authoring skill starts with the brief and does not inspect branch state until after confirmation. It never establishes the target base, merge base, current diff, dirty worktree, existing intent candidates, stacked-branch relationship, or whether shipping code already implements the request. Phase 2 can therefore read branch modifications as the baseline and shape the intent around them—the exact failure the design exists to prevent.

Add Phase 0 before the brief:

1. resolve repository root, current branch, intended target/base, and merge base;
2. inspect the working-tree and branch diff without yet exploring the proposed solution;
3. identify intent files added or modified relative to the immediate target;
4. distinguish unrelated changes, exploratory prototype code, and shipping implementation;
5. refuse an initial intent over an already implemented shipping diff unless the workflow returns to a clean pre-implementation baseline;
6. verify that the agent can write and commit only the intent file.

Define “exactly one intent per PR” as exactly one current intent added or modified relative to the PR's immediate target. A stacked child branch may legitimately include its parent's intent relative to `main`.

### 5. The change-defining decision test is too dependent on private agent counterfactuals

The author owns direction, but the agent privately decides whether the author “could approve” either branch. Rejected candidates are hidden and discarded (`mechanics/authoring-skill.md:94,192-206`), while the design says the skill must not decide change-defining questions (`design.md:423-425`).

The cache example shows the ambiguity. Both caching and not caching negative results can satisfy “reduce database load,” yet the design calls their visibility difference a different change. Almost any observable difference can be framed that way, even though observable difference alone is said not to qualify.

Improve the classifier with:

- a confirmed **delegation envelope** in the brief: which surfaces the author delegates and where they expect a ruling;
- a presumption that materially different external semantics, irreversible state, compatibility policy, security/compliance posture, operator commitment, or cost commitment are change-defining;
- a short **material latitude delegated** proposal section, giving the author a veto without requiring a ruling;
- a definition of a reasonable branch so the result cannot be changed by selectively framing alternatives.

Also generalize the decision card. “What the code does today” should become **Evidence from the current system**, allowing code, tests, configuration, documentation, contracts, runtime observations, or “greenfield—no existing surface.” Support two or more options, and permit “no recommendation; the evidence does not distinguish this product choice.”

Clarify compatibility at the same time. Existing behavior by itself does not become a forward-looking claim. But when a plausible branch introduced by this change alters existing external behavior, that branch is a decision candidate. If preservation is selected and material to the approved change, encode the necessary guardrail as an AC, invariant, or constraint. This resolves the tension among `mechanics/authoring-skill.md:28`, `design.md:112`, and the negative-cache example at `design.md:294-298,506-523`.

## Major design findings

### 6. Outcomes can fail while the process declares the change complete

The design explicitly permits every claim to pass while an outcome fails (`design.md:86-90`). That honesty is useful, but the completion protocol only says the implementation must “plausibly” deliver Outcomes (`mechanics/implementation-guidance.md:15,99`). There is no defined evidence for plausibility.

The worked cache example can satisfy every listed test with a near-zero TTL and almost no cache hits, missing both the 70% database-load and latency Outcomes (`design.md:472-499`).

For every Outcome, require one of:

- direct support from identified acceptance criteria or invariants;
- a deterministic proxy plus explicit assumptions;
- a reasoned implementation case and a named post-deployment success measure when only production can establish it.

Affirmative evidence that the implementation is unlikely to deliver an Outcome prevents `complete`, even when every AC passes. Production-only Outcomes need not become fake tests, but the human should see what remains a hypothesis and how it will be observed.

### 7. Review is not operationally independent enough

The mechanics correctly preserve ordinary review, but they do not require an unanchored pass. An intent-first reviewer can focus on proving the named claims and miss an unrelated injection flaw, resource leak, data race, or unsafe default.

Require two logically separate passes:

1. a diff-first ordinary defect review without the intent's framing;
2. an intent-alignment review;
3. reconciliation into one assessment.

The passes can use one agent with separate contexts, but a fresh reviewer or subagent is stronger. Independence does not require deliberate amnesia: carry the authoring surface map and implementation evidence as non-normative leads, then require review to validate or dispute them.

For broad invariants, replace bare `met` with **supported within reviewed boundary**, or define `met` to mean exactly that. Record the boundary, discovery method, representative sites, inaccessible surfaces, concrete tests, and reasoning.

`Cannot verify` must yield overall `incomplete`, never a bare approval. A team may decide whether a particular incomplete result blocks merge, but the disposition must be explicit.

The review assessment should also account for every Constraint (`no conflict found | conflict | implausible | cannot assess`) and every exclusion (`not delivered | violated | cannot assess`).

Implementation should use the same material-implausibility threshold for Constraints. Today it can declare completion on “no known conflict” while review is instructed to raise a finding for a materially implausible design (`mechanics/implementation-guidance.md:11,99`; `mechanics/review-guidance.md:19`).

### 8. Replacement deliberately removes the signal most needed to detect anchoring

Replacement is a valid capability: authors are allowed to change direction. But the process overwrites the prior candidate, removes its Amendments, keeps retained code, and tells review not to reconstruct earlier candidates (`design.md:347-353`; `mechanics/review-guidance.md:31-32`). That recreates a softer version of post-facto rationalization: code can shape the replacement, while the final artifact no longer shows what changed after seeing the code.

Preserve a minimal, non-normative supersession record:

- previous approved-baseline revision or content hash;
- reason the direction changed;
- explicit dispositions of pending amendments;
- old/new intent diff for evidence invalidation.

The final intent can remain clean and current. The review operation still needs to know that it is a replacement and which evidence must rerun. The simple safe rule is that a replacement invalidates all implementation evidence; a more optimized rule requires evidence keyed to stable item IDs and both intent hashes.

Define when a replacement remains the same change. If “add a cache” becomes “batch database reads,” the old slug is misleading; permit renaming an unmerged replacement or require a new intent.

### 9. “Every change” and “exactly one intent per PR” do not yet scale

Every change must use four non-mergeable phases, separate approvals, a separate intent commit, per-AC test sensitivity evidence, and full ordinary plus intent review (`mechanics/authoring-skill.md:20`; `mechanics/agents-md-block.md:52-54`; `notes.md:44-45`). This conflicts with Used beats better (`design.md:40-44`) for typo fixes, deterministic generated changes, exact reverts, automated dependency bumps, and urgent restoration.

Add a compact lane that preserves pre-code approval:

- mechanical, reversible, narrowly bounded change;
- no admitted change-defining decision;
- no meaningful constraint, invariant, or coverage limit;
- one combined brief/proposal and one approval;
- immediate escalation to the full lane when exploration discovers complexity.

Add an emergency revert lane with a minimal pre-action Outcome and Why, plus the ordinary incident/change record. If the process has no break-glass path, teams will bypass it without leaving a structured signal.

The one-intent/one-PR model also lacks composition for coordinated schema/client rollouts, stacked PRs, and cross-repository changes. Either declare those outside adoption fit or add a lightweight parent intent/correlation ID with one child intent per independently reviewed PR.

## Additional improvements

### Add stable item identifiers

The final file uses unnumbered bullets while implementation, amendments, and review operate item-by-item. Add stable local IDs such as `O1`, `C1`, `AC1`, `INV1`, and `OOS1`. Keep verbatim `Was`/`Now` text, but use IDs for evidence, targeted revisions, and assessment output.

### Define the minimum review artifact

At minimum, every review should state:

1. reviewed code revision, intent hash, and approved baseline;
2. intent-internal consistency findings;
3. per-AC status and evidence basis;
4. per-invariant reviewed boundary and status;
5. per-constraint accounting;
6. per-exclusion conformance;
7. amendment eligibility, coherence, and author disposition;
8. reverse-decision findings;
9. ordinary review findings;
10. overall `aligned | not-aligned | incomplete`.

### Check causality, not only current truth

A test can prove behavior that already existed and that this PR did not establish. Review should distinguish:

- new behavior: the base revision fails or cannot express the proving test;
- preservation guardrail: the behavior existed, but the test exercises a path changed by this PR;
- unrelated pre-existing behavior: intent defect or `not met`.

### Clarify what counts as a proving test

`design.md:106` permits a one-shot measurement, while `design.md:114` requires a test that ships with the diff. Define whether a repeatable checked-in script, a CI command, a compile check, or only a conventional test counts.

### Make useful coverage-limit consequences survive approval

The proposal contains a valuable Surface read and coverage-limit resolution, then strips all scaffolding (`mechanics/authoring-skill.md:179-189,218-225`). If supplied context or an assumption materially qualifies the approved change, preserve its consequence as an Outcome, Constraint, claim, or exclusion. The full exploration log need not become normative.

### Make amendment eligibility evidence durable

Implementation must name plausible alternatives before amending, and review must decide whether one would have satisfied the baseline (`mechanics/implementation-guidance.md:45`; `mechanics/review-guidance.md:23`). The alternatives may disappear with the session. Preserve a concise eligibility basis: alternatives considered, why each fails, the discovered fact, and the precedence result.

Define exact write authority for each amendment trigger. The current guidance allows moving an unprovable AC into Outcomes or Constraints (`mechanics/implementation-guidance.md:42`) while treating Outcomes, Constraints, and exclusions as fences the implementer cannot move (`mechanics/implementation-guidance.md:88`; `mechanics/agents-md-block.md:33`). State which sections may be added, rewritten, moved, or removed in each eligible case.

### Add deterministic validation and an evaluation corpus

The folder rules, heading order, stable IDs, one-current-intent rule, amendment chains, terminal `Now` matches, and frozen-history checks are mechanically lintable. A small linter would reduce prompt duplication and let review focus on semantics.

Before universal adoption, run the authoring, implementation, and review prompts against a shared corpus containing:

- tiny mechanical fixes;
- greenfield changes;
- behavior and API changes;
- production-only performance Outcomes;
- security and data migrations;
- cross-cutting invariants;
- false baselines and untestable claims;
- stacked, concurrent, and cross-repository work;
- amendments, replacements, and evidence loss.

Measure author corrections, agent agreement on change-defining decisions, amendment frequency, `cannot verify` rate, false review findings, completion cost, and defects missed. The design's claim that it becomes a net value add should be tested, not assumed.

### Add persistent-artifact hygiene

Why, evidence summaries, and exclusions become permanent repository history. Instruct agents not to persist secrets, customer identifiers, incident-sensitive details, credentials, or ephemeral authenticated links, and to follow repository data-classification rules.

### Clarify the role of historical intents

The design treats merged intents as durable memory while telling current authoring and review not to search them for requirements or decisions that must be preserved (`mechanics/agents-md-block.md:48-50`; `mechanics/review-guidance.md:31`). That is coherent if their value is archival only, but it weakens the claim that the practice compounds into future context. Decide explicitly whether prior intents are:

- archival records only;
- optional non-normative discovery context; or
- searched for prior rationale and reversals, never as current law.

Do not leave future agents to infer the intended use.

## Scenario pressure tests

| Scenario | Current behavior | Needed behavior |
| --- | --- | --- |
| User invokes authoring on a half-implemented branch | Phase 2 can treat modified code as baseline and backfill intent | Phase 0 detects the shipping diff and stops or restores a clean baseline |
| Offset vs cursor pagination on a public API | Agent may privately call it implementation latitude | External-contract presumption plus material-latitude veto |
| CI-only SSO test needs unavailable credentials | No safe observed pass/fail; agent cannot amend or finish | `blocked-evidence`, closed by CI or explicit policy |
| Existing compatibility test fails on base and passes after a dependency upgrade | Agent is still told to add a test and mutate code | Existing red-before-green evidence is accepted |
| Dynamic plugin callers make an audit invariant unbounded | Implementation has no completion status | Scoped invariant plus `cannot verify` / `blocked-evidence` |
| Authorization outage requires fail-open vs fail-closed | Precedence may select unsafe existing behavior and continue | High-risk decision returns to author |
| Cache tests pass with a near-zero TTL | ACs pass while load and latency Outcomes fail | Outcome-to-proof/proxy/production-measure mapping |
| Implementer weakens one-minute token revocation to five minutes | Reviewer gets self-reported `Was`/`Now`, alternatives may be lost | Durable eligibility evidence and explicit author disposition |
| Author replaces a 30-second AC with a five-second AC | Old goal evidence can appear current | Hash-bound evidence is invalidated and rerun |
| Reviewer can inspect only one repository for a universal invariant | Reviewers may disagree between `met` and `cannot verify` | `supported within reviewed boundary` or `incomplete` |
| Two agents share a worktree during temporary mutations | False failures or a committed mutant are possible | Isolated worktrees and one amendment/evidence owner |
| Stacked child PR includes its parent's intent relative to `main` | “Exactly one” can be falsely reported as violated | Cardinality is measured relative to the immediate PR target |

## Worked-example defect

The example says exploration already found that `GetUser` returns nil for nonexistent users (`design.md:460-465`), but implementation later “discovers” that same fact and amends the intent for negative-result caching (`design.md:506-523`). The causal-continuity sweep in the authoring skill should have surfaced creation-after-miss before approval.

Either use a genuinely implementation-only discovery, or explain why the lifecycle was unavailable during authoring. As written, the flagship example demonstrates a failure of the proposed authoring pass and then describes it as ordinary contact with implementation.

## Recommended revision order

1. **Define the state machine and authority.** Approved baseline, current candidate, accepted amended intent, amendment disposition, replacement rules.
2. **Define the revision-bound handoff.** Harness-neutral implementation result, review result, invalidation rules, stable IDs.
3. **Close the continuation gaps.** Evidence hierarchy, `blocked-evidence`, invariant uncertainty, high-risk author escalation.
4. **Add authoring preflight and a stronger decision classifier.** Target base, anti-backfill, delegation envelope, flexible evidence/options.
5. **Connect Outcomes to evidence and post-deployment observation.** Make residual hypotheses visible.
6. **Make review genuinely independent and bounded.** Diff-first ordinary pass, alignment pass, explicit incomplete state.
7. **Add compact, emergency, stacked, and cross-repository lanes.** Preserve the idea without forcing one workflow shape everywhere.
8. **Lint and evaluate the mechanics.** Use a representative corpus before declaring the design universal.

## Final assessment

Change intent is a strong decision artifact and a promising review architecture. Its best contribution is not the Markdown template; it is separating author-owned change definition from implementation-owned technical choice, then giving review a forward claim check and a reverse decision check.

Today, the documents describe the questions each role should ask more successfully than they define the durable states and evidence needed to answer those questions. Fixing that gap would make the idea genuinely useful to me in all three roles. Without those fixes, I would use it selectively for material changes, but I would not present it as a universal process, a visible chain of custody, or a reason to reduce human review.
