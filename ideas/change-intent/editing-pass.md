# Editing-Pass Findings

This file is the worklist for tightening the adopter-facing corpus. It holds two passes over the same revision:

- **Part 1 — Voice and tone** (immediately below): terms and phrases that read as AI-written or are hard for humans to understand, with per-site rewrites.
- **Part 2 — Repetition and structure** (second half of this file): the design concepts repeated across the corpus, which repetitions to remove, and how to restructure the major files so each concept is defined once and referenced thereafter.

**Recommended order: apply Part 2 first, then Part 1.** The restructure deletes or moves much of the text Part 1 annotates; polishing sentences that are about to be cut is wasted work. After the restructure, Part 1's line numbers are stale — re-locate each entry by its quoted phrase, not its line number.

**Status: applied.** design.md is the restructured version (Part 2's spine and cuts, Part 1's design.md entries); the change-intent README is a directory card; the notes.md trims and voice fixes, the mechanics/README.md boundary reword, and the instrument-preamble, working-in-public, and root-README voice items are all in. The only open item is the optional instrument-heading alignment (P1: "from the implementation seat" / "from the review seat"). This file remains as the record of the editing program.

**Corpus revision:** `d2d443e`. All line numbers below refer to that revision; later commits on this branch have already shifted some lines, so re-locate each entry by its quoted phrase before editing.

**Scope.** Per the two-voices rule in [notes.md](notes.md), the human-read corpus is: the root `README.md`, `ideas/change-intent/README.md`, `design.md`, `notes.md`, `mechanics/README.md`, `ideas/working-in-public/README.md`, and the preamble before the first horizontal rule in each mechanics instrument. The instrument bodies are agent-facing and deliberately untouched by this pass.

**What this pass looked for.** Terms and phrases that are (a) recognizable tells of AI writing, or (b) hard for a human reader to understand without insider context. Each finding proposes a rewrite fitted to its sentence — the same term often gets different treatment in different places. This file is the worklist for the editing pass; it makes no edits itself.

**Preamble check.** The human-facing preambles of `agents-md-block.md`, `authoring-skill.md`, and `review-guidance.md` are clean. `implementation-guidance.md` has one finding (below).

---

## Terms to keep (do not "fix" these in the editing pass)

These are deliberate, defined vocabulary. Some look coined, but they carry the design and are used consistently across the human corpus and the agent instruments:

- **"complete over change-defining decisions and open over implementation"** — the design's central sentence; both review rounds singled it out as its best.
- **"change-defining"** — the core coinage; everything depends on it.
- **"implementation latitude"** — defined, precise, no plainer equivalent of equal precision.
- **"falsifiable"** — precise, and the corpus glosses it ("specific enough to fail," design.md:50).
- **"Used beats better"** — keep as the principle's name where it is defined (design.md:46); see README finding for the one place it is referenced before being defined.
- **"on the record"** — plain English, does real work.
- **"would-fail demonstration"** — defined procedure name.
- **"the author owns direction; the skill owns the map"** — the map metaphor is glossed inline at both uses (design.md:417, authoring-skill.md:16); leave it.
- **"frozen history," "worked example," "artifact," "downstream," "ceremony," "parked items"** — standard or self-explaining engineering vocabulary.
- The fabricate/drift/stall sentence (design.md:310) — concrete, human, exactly right. Do not touch.

Borderline, lean keep: **"instruments"** for the mechanics files (unusual word, but defined at first use and used consistently); **"proposal scaffolding"** (construction metaphor, but clear); **"commit-title specificity"** (design.md:249 — engineers parse it); **"smuggle"** (design.md:90 — vivid but plain).

---

## Recurring patterns (fix per-site, never by find-and-replace)

### P1. "seat" for a workflow role

The corpus uses "seat" and "role" interchangeably for the same concept, and "seat" is the odd coinage — poker-table flavor, and the mixing itself is confusing. Recommendation: standardize on **"role"** throughout the human corpus. "Role" already does the job in design.md:48 ("These are logical responsibilities") and in the role-path table.

Sites: `ideas/change-intent/README.md:15, 27 (twice)`; `design.md:48, 278, 353, 391, 577`; `notes.md:36, 49, 102`. Per-site wording in the file sections below.

Note: the agent-facing instrument headings "from the implementation seat" / "from the review seat" (implementation-guidance.md:13, review-guidance.md:15) may stay as-is under the two-voices rule, or be aligned later for consistency — a separate, optional decision.

### P2. "load-bearing"

The canonical AI-writing tell. Two sites: `design.md:331` (heading) and `design.md:423`. Different fixes each — see below.

### P3. "-shaped" compounds and "the shape of"

"Invariant-shaped," "naturally shaped," "the shape of the process," "exactly the shape … needs." Another strong AI tell. Sites: `README.md (change-intent):9, 11`; `design.md:168, 182, 365`. The agent-facing "fact-shaped / activity-shaped" in implementation-guidance.md:77-80 stays — it is doing precise work for an agent reader.

### P4. "signal" as a mass noun

"Highest-signal," "carries no signal," "is missing is signal." Fine as a verb ("Signals to the reviewer…" — keep those); as a mass noun it is radio-engineering jargon humans stumble on. Sites: `design.md:186 (light), 336 (light), 398, 571`.

### P5. "channel" for the amendment process

"The amendment channel," "keep the channel quiet," "bloat the channel." Plumbing metaphor with no payoff; "process," "mechanism," or "path" reads plainly. Sites: `design.md:302, 310, 318, 504`.

### P6. "tokens" and "high-value" for content

"The highest-value tokens of the pre-code dialogue" — tokens is model-internals vocabulary; a human hears currency. "High-value" as a compound modifier is also an AI tic. Sites: `README.md (root):7`; `ideas/change-intent/README.md:13, 19`; `ideas/working-in-public/README.md:5, 15`. Generally → "the most valuable parts / thinking / context."

### P7. "surface" — noun for a code area, verb for "show"

Noun: "the affected surface," "the surface read," "a relevant surface." Verb: "surfaces those cases," "surfaced before approval." Both are agent-instrument vocabulary that leaked into the memo voice. In human prose the noun is "the affected code" / "part of the system"; the verb is "expose," "reveal," "bring to light," or just "show." Sites (human corpus only): `ideas/change-intent/README.md:7, 27`; `design.md:261, 337, 363, 425, 539, 543`. Exception: in the `/goal` section (design.md:363-372), "surfaced in the conversation/transcript" describes the actual mechanism — the evaluator literally sees only the transcript — so those uses may stay, apart from the one flagged at 363.

### P8. "fork" and "branches" — collision with git vocabulary

The change-defining test is phrased as a "fork" with "branches" — in a document that also talks about git branches constantly. "Fork" (as in a fork in the road) is a natural, human metaphor and can stay; **"branches" is the collision**. Recommendation: in the human corpus, prefer "options" or "paths" ("choosing between its options decides which change will be delivered").

**Decision needed before applying:** the fork test is repeated near-verbatim in the agent instruments, and Round 2 praised that verbatim consistency. Changing the human-side wording breaks it. Options: (a) accept the divergence under the two-voices rule; (b) change it everywhere, including instruments; (c) keep "branches" and rely on context. This file recommends (a) but flags it as the author's call. Sites if applied: `ideas/change-intent/README.md:21`; `design.md:70-78 (the decision tree), 80, 263, 296, 298, 425`.

### P9. "chain of custody" and "cooperative continuity"

The forensic term needs an immediate disclaimer everywhere it appears ("not an audit trail, not mechanically verified provenance") — a sign it is the wrong term. And "cooperative continuity," the phrase that disclaims it, is itself abstract. Recommendation: drop both in favor of plain description — the change arrives with a complete, visible record of the steps it went through, kept by cooperation rather than enforcement. Sites: `ideas/change-intent/README.md:19`; `design.md:52, 387, 389`. Per-site rewrites below.

### P10. "the team's review operation"

Coined phrase, used seven times, never defined. A human reads "operation" as surgery or military. Vary by context: "the team's review setup," "the tools and evidence the team's review process provides," "however the team runs review." Sites: `ideas/change-intent/README.md:27`; `design.md:9, 357, 376, 383 (twice), 389`.

### P11. "harness"

AI-practitioner insider jargon for the tool wrapping the model. Adopting teams may not know it. → "coding tool," "coding agent," or the concrete product name where one is meant. Sites: `ideas/change-intent/README.md:9`; `design.md:46, 353`; `mechanics/README.md:5`; `implementation-guidance.md:5` (preamble).

### P12. "decision boundary"

Central term, used by the instruments too — keep it, but it collides with the machine-learning term and deserves a one-time gloss at first human use. First uses: `ideas/change-intent/README.md:3` and `design.md:7`. Suggested gloss at first use: "a goal and a decision boundary — a clear line around what has already been decided." Elsewhere leave as-is.

---

## Per-file findings

### README.md (root)

**Line 7** — "preserves high-value context for future agents"
→ "preserves valuable context for future agents" (P6; "high-value" as compound modifier).

### ideas/change-intent/README.md

**Line 3** — "gives implementation a goal and decision boundary"
→ First use in the corpus; add the P12 gloss: "gives implementation a goal and a decision boundary — a clear line around what has already been decided."

**Line 7** — "before code exists to anchor on — surfaces the fuzzy spots in the author's own thinking"
Two problems: "anchor on" (cognitive-bias jargon) and "surfaces" (P7).
→ "Stating what a change must make true — before any code exists to pull the author's thinking toward it — exposes where that thinking is still vague."

**Line 7** — "direction that used to be sharpened by the labor of implementation now needs its own deliberate moment"
"Its own deliberate moment" is AI-poetic.
→ "direction that used to become clear through the work of implementing it now has to be worked out deliberately, before the work starts."

**Line 9** — heading "**AI gets a platform to drive against.**"
"Drive against" is not something humans say.
→ "**AI gets a goal to work toward.**"

**Line 9** — "exactly the shape a coding harness's goal mechanism needs"
P3 + P11 in one phrase.
→ "exactly what a coding agent's goal mechanism needs."

**Line 11** — "the reviewer can trust the shape of the process and spend their judgment on the change itself"
P3, plus "spend their judgment" is an AI-economics tic.
→ "the reviewer can trust the process and give their judgment to the change itself."

**Line 13** — "they read history cheaply and act on what they find — so the highest-value tokens of the pre-code dialogue are worth saving into the repository"
"Cheaply" (economics tic) and P6.
→ "reading history costs them nothing, and they act on what they find — so the most valuable parts of the pre-code dialogue are worth saving into the repository."

**Line 15** — "Every seat is a logical responsibility, not a job title"
P1. → "Every role in the workflow is a responsibility, not a job title."

**Line 17** — "the used-beats-better tradeoff from [design.md](design.md), applied as a test"
The principle is named here before the reader has seen its definition.
→ "the tradeoff from [design.md](design.md) that a process people actually use beats a stronger one they don't — applied as a test."

**Line 19** — "it carries a visible chain of custody: an approved intent, … Here chain of custody means cooperative continuity through the team's existing workflow, not an audit trail or mechanically verified provenance."
P9 — the term plus its two-part disclaimer.
→ "it arrives with a complete, visible record of the steps it went through: an approved intent, the resulting implementation and tests, any implementation-time amendments, completion against the goal, and an independent review assessment. That record is kept by cooperation through the team's existing workflow — it is not an audit trail, and nothing mechanically verifies it."

**Line 19** — "capturing the high-value outputs of AI work in artifacts that persist beyond the session"
P6. → "capturing the most valuable outputs of AI work in artifacts that persist beyond the session."

**Line 27** — "Adoption uses author, implementation, and review as logical seats in the workflow … may assign or combine those seats"
P1. → "Adoption uses author, implementation, and review as roles in the workflow … may assign or combine those roles."

**Line 27** — "the change-defining questions surfaced before approval"
P7. → "the change-defining questions raised before approval."

**Line 27** — "using the capabilities available in the team's review operation and inference"
P10. → "using whatever tools and evidence the team's review setup provides, plus inference."

**Line 39** — "invariants invite property thinking across the diff"
"Property thinking" is jargon shorthand.
→ "invariants ask implementation and review to reason about a property across the whole change."

### ideas/change-intent/design.md

**Line 7** — "gives implementation a goal and decision boundary"
First use in this file; same P12 gloss as README line 3.

**Line 9** — "using the evidence and capabilities available in the team's review operation"
P10. → "using the evidence and capabilities the team's review setup provides."

**Line 46** — "the ask of a teammate is one sentence"
"The ask" as a noun is corporate/AI-speak.
→ "what we ask of a teammate is one sentence."

**Line 46** — "run the change-intent skill instead of the coding harness's built-in plan mode"
P11. → "run the change-intent skill instead of your coding tool's built-in plan mode."

**Line 48** — "future agents may occupy seats held by humans today"
P1. → "future agents may take over roles held by humans today."

**Line 52** — "Chain of custody therefore describes cooperative continuity around a shared intent, not mechanically verified provenance."
P9. If the term is dropped corpus-wide, this closing sentence becomes:
→ "The record of a change is therefore kept by cooperation around a shared intent; nothing mechanically verifies it."

**Line 54** — "**Every role has a defined continuation path.**"
"Continuation path" is agent-design jargon; the table below it already says "Path forward" in plain words.
→ "**Every role has a defined path forward.**"

**Line 70-80** — the decision tree and fork test use "branches"
P8 — apply only if the decision there lands on changing it. E.g. line 80: "A fork is change-defining only when choosing between its options decides what change will be delivered. … If either option still delivers that direction, the fork is implementation latitude."

**Line 168** — "audit-log-on-every-mutation, and thread safety across access paths are invariant-shaped"
P3. → "…are all typical invariants."

**Line 182** — "Note the shape: each states one property whose reach extends beyond a focused proving test. It names that reach as a rule"
P3, plus "reach" used twice as an abstract noun.
→ "Note the pattern: each states one property whose scope extends beyond a single proving test. It states that scope as a rule…"

**Line 186** — "turning intentional exclusion into a signal the same way the diff makes intentional inclusion a signal"
P4, light — the parallel works but lands plainer without the jargon noun.
→ "making intentional exclusion visible the same way the diff makes intentional inclusion visible."

**Line 251** — "leaves a legible historical record"
"Legible" in the Seeing-Like-a-State sense is an AI-writing tell.
→ "leaves a clear historical record."

**Line 261** — "**It's a forcing function.**"
Corporate/AI-speak. The body sentence after it already carries the meaning.
→ "**Writing it down forces clarity.**"

**Line 261** — "Articulating acceptance criteria and invariants explicitly surfaces those cases at the cheapest possible time"
P7. → "…brings those cases to light at the cheapest possible time."

**Line 263** — "If every reasonable branch still delivers the approved change, the implementer chooses and continues."
P8, if applied: "If every reasonable option still delivers the approved change…"

**Line 278** — "an AI orchestrator in the author seat"
P1. → "an AI orchestrator in the author role."

**Line 280** — "This is what lets the discipline carry forward into the autonomous trajectory."
"Trajectory" as destination-noun is an AI tic.
→ "This is what lets the discipline carry forward as the workflow becomes autonomous."

**Line 280** — "the autonomous-vehicle arc described at the top of this document"
"Arc" is lit-crit vocabulary.
→ "the autonomous-vehicle comparison at the top of this document."

**Line 302** — "is a seed for the next change intent: its own file, own date, own slug, own deciding moment"
"Seed" metaphor plus "own deciding moment" (AI-poetic). Note design.md:429 already says "candidates for future intents" — align with that.
→ "is a candidate for the next change intent: its own file, its own date and slug, its own decision."

**Line 302** — "The pressure that would otherwise bloat the amendment channel gets redirected into the artifact system: the deferred idea is handed to the author as a named seed for its own intent"
P5, plus "the artifact system" names a system that doesn't exist.
→ "Ideas that would otherwise swell the amendment record get redirected: the deferred idea is handed to the author as a named candidate for its own intent."

**Line 310** — "The channel exists because an agent that discovers a wrong claim mid-implementation…"
P5. → "This path exists because an agent that discovers a wrong claim mid-implementation…" (keep the rest of the sentence exactly as written — see keep list).

**Line 318** — "Two supporting rules keep the channel quiet and enforceable:"
P5, plus "quiet" is a metaphor doing unclear work.
→ "Two supporting rules keep amendments rare and checkable:"

**Line 331** — heading "### Why rarity is load-bearing"
P2 — the flagship instance.
→ "### Why amendments must stay rare" (the body's first sentence then reads naturally against it).

**Line 333** — "the design leans on that rarity three ways"
Light; pairs with the heading fix.
→ "the design depends on that rarity in three ways."

**Line 335** — "**Every amendment is a decision made under anchoring.**"
"Anchoring" is cognitive-bias jargon; the next two sentences already explain the idea plainly.
→ "**Every amendment is a decision made after code has begun shaping everyone's view.**" (Then trim the now-redundant second sentence or leave it as reinforcement — editor's call.)

**Line 336** — "a skimmed Amendments section carries no signal at all"
P4, light. → "a skimmed Amendments section tells the author nothing at all."

**Line 337** — "One or two entries is ordinary contact with reality."
AI-poetic. → "One or two entries is normal — implementation always turns up surprises."

**Line 337** — "the author, the authoring dialogue, and the surface read all missed something that reality then surfaced"
P7 twice — "the surface read" is opaque even for engineers.
→ "the author, the authoring dialogue, and the exploration of the affected code all missed something that implementation then exposed."

**Line 353** — "not a required organizational topology or tool pipeline"
"Organizational topology" is jargon.
→ "not a required team structure or tool pipeline."

**Line 353** — "Teams may fit those seats into broader development practices" / "as models and harnesses improve"
P1, P11. → "Teams may fit those roles into broader development practices" / "as models and coding tools improve."

**Line 355** — "The role-path table above governs unresolved conditions for each role."
"Role-path table" is a coined compound naming the table nothing else calls that.
→ "The table above (Role and situation → Path forward) defines the path for each unresolved condition."

**Line 357** — "What travels between the stages is deliberately thin"
"Thin" as praise is an AI tic. → "What travels between the stages is deliberately minimal."

**Line 357** — "the evidence available through the team's review operation"
P10. → "the evidence available through the team's review setup."

**Line 363** — "the evaluator only sees what's surfaced in the conversation"
P7 — and here plain wording is strictly clearer.
→ "the evaluator only sees what appears in the conversation."

**Line 365** — "A change intent file is naturally shaped to be a `/goal` condition."
P3. → "A change intent file is a natural fit for a `/goal` condition."

**Line 376** — "is defined by the team's review operation, not by change intent"
P10. → "is defined by how the team runs review, not by change intent."

**Line 383** — "available in the team's review operation" / "When the review operation cannot support a conclusion"
P10. → "available in the team's review setup" / "When that setup cannot support a conclusion."

**Line 387** — heading "### Human review: the chain of custody pays out"
P9, plus "pays out" is a gambling metaphor.
→ "### Human review: where the record pays off"

**Line 389** — "it has passed through a repeatable chain of custody. That cooperative chain provides continuity through the team's existing workflow rather than an audit trail or mechanically verified provenance."
P9. → "it has passed through the same sequence of recorded steps as every other change. That continuity comes from cooperation within the team's existing workflow — it is not an audit trail, and nothing mechanically verifies it."

**Line 389** — "through the team's chosen review operation"
P10. → "through whatever review setup the team has chosen."

**Line 391** — "the strengths, weaknesses, and quirks of each AI seat"
P1. → "the strengths, weaknesses, and quirks of the AI in each role."

**Line 398** — "Any amendments are the highest-signal part of the returned work"
P4. → "Amendments are the first thing in the returned work to read carefully."

**Line 423** — "harvested from the session when the change was already discussed there"
"Harvest" is agent-instrument vocabulary (fine in the skill body, which keeps it).
→ "gathered from the conversation when the change was already discussed there."

**Line 423** — "The gate is cheap and load-bearing: it is where a misread of the author's direction gets caught"
P2, plus "misread" as a noun.
→ "The gate costs seconds and earns its place: it is where a misreading of the author's direction gets caught."

**Line 425** — "The skill reads the affected surface and records a confidence level for each fact"
P7. → "The skill reads the affected code and records a confidence level for each fact."

**Line 425** — "If a relevant caller, lifecycle, data boundary, or other required surface cannot be inspected or bounded confidently"
P7, plus "bounded confidently" is math-flavored.
→ "If a relevant caller, lifecycle, data boundary, or other necessary part of the system cannot be examined, or its limits cannot be established with confidence."

**Line 527** — "the review pass walks the whole diff through each invariant's lens"
"Lens" is an AI tic. → "the review pass checks the whole diff against each invariant."

**Line 539** — "When authoring cannot inspect or confidently bound a relevant surface"
P7. → "When authoring cannot examine a relevant part of the system or establish its limits with confidence."

**Line 543** — "the AI's bounded surface read may therefore miss a real interaction"
P7. → "the AI's bounded read of the affected code may therefore miss a real interaction."

**Line 563** — "We don't have to be exactly right about the future to be directionally right."
"Directionally right" is corporate/AI-speak.
→ "We don't have to be exactly right about the future to be right about the direction."

**Line 565** — "The form feels durable"
AI-poetic hedge. → "The pattern seems likely to last."

**Line 565** — "structured to be a net value add to the review process rather than ceremony on top of it"
"Net value add" is corporate-speak ("ceremony" is fine — keep it).
→ "structured to genuinely improve the review process rather than sit as ceremony on top of it."

**Line 571** — "What the review process is missing is signal about whether design intent actually drove the change. (573) Change intent provides that signal by inverting the direction of fit"
P4 in 571; "direction of fit" in 573 is philosophy-of-language jargon no general reader knows.
→ 571: "What the review process is missing is any indication of whether design intent actually drove the change."
→ 573: "Change intent provides that by reversing the order: the initial intent is approved before implementation begins, and every implementation and review pass works against the current intent."

**Line 577** — "workflows in which humans no longer occupy every seat"
P1. → "workflows in which humans no longer fill every role."

**Line 577** — "the trajectory where humans gradually exit the loop"
Two tics in one phrase.
→ "the future in which humans gradually hand off the work."

**Line 577** — "the same semantic responsibilities and shared artifact"
"Semantic" adds nothing for a human reader.
→ "the same responsibilities and shared artifact."

### ideas/change-intent/notes.md

**Line 28** — "The semantic responsibilities and shared decision artifact remain useful"
Same as design.md:577. → "The responsibilities and the shared decision artifact remain useful."

**Line 36** — "may occupy the author seat"
P1. → "may fill the author role."

**Line 49** — "who or what holds the author and reviewer seats"
P1. → "who or what fills the author and reviewer roles."

**Line 79-80** — "and for an AI agent that history is incredibly rich"
AI-superlative. → "and for an AI agent that history is unusually valuable."

**Line 102** — "loaded by an AI agent taking a seat in the process"
P1. → "loaded by an AI agent taking a role in the process."

### ideas/change-intent/mechanics/README.md

**Line 5** — "prompt-level engineering, harness specifics, agent failure-mode countermeasures"
P11, plus a stacked-compound list that reads as AI writing.
→ "prompt engineering, tool-specific details, and safeguards against known agent failure modes."

### ideas/change-intent/mechanics/implementation-guidance.md (preamble)

**Line 5** — "including optional integration with a harness mechanism such as Claude Code's `/goal`"
P11. → "including optional integration with a coding-tool mechanism such as Claude Code's `/goal`."

### ideas/working-in-public/README.md

**Line 5** — "the value of those tokens disappears with it — a lot of high-value structured thinking thrown away"
P6 twice. → "the value of that work disappears with it — a lot of valuable structured thinking thrown away."

**Line 7** — "the artifacts that crystallize the structured work"
"Crystallize" is an AI tell. → "the artifacts that capture the structured work."

**Line 15** — "The pre-code dialogue between the deciding agent and the authoring skill produces high-value tokens; those tokens persist with the change forever"
"The deciding agent" is opaque (it means the author), plus P6 twice.
→ "The pre-code dialogue between the author and the authoring skill produces the most valuable thinking of the change; that thinking persists with the change forever."

**Line 17** — "where the economic line sits between save and discard"
Abstract coinage. → "when saving is worth the cost and when it isn't."

---

## Optional / editor's discretion

Lower-confidence flags. Each is defensible as-is; listed so the editing pass can decide deliberately rather than by omission:

- `design.md:247` — "linearly scannable" → "easy to scan in time order."
- `design.md:437` — heading "### Stopping condition" → "### When authoring is done." (CS jargon, but the audience is engineers.)
- `design.md:531` — heading "## Design Tensions" → "## Where the design is not settled." ("Tensions" is common RFC-speak; borderline.)
- `design.md:571` — "The case for change intent is structural, not aesthetic." Mild AI-antithesis; works in context. Alternative: "The case for change intent is practical, not stylistic."
- `design.md:17` — "The squeeze is the same on a team of two as on a team of twenty." Plain English; keep.
- `design.md:427/429` — "proposal scaffolding" → "the proposal's working annotations (source tags, open items)." Clear enough to keep.
- `ideas/working-in-public/README.md:12` — "the practice compounds." Finance metaphor but widely understood; keep.

---

# Part 2 — Repetition and Structure

**Goal.** Make the major files — design.md above all — substantially shorter without losing content or introducing confusion. The method: identify each concept that is currently explained in several places, choose one canonical home for it, and reduce every other site to the term plus a link. Restructure so concepts are introduced before they are referenced.

## Diagnosis: why the corpus is long

Four causes, in order of impact:

1. **The overview exists in four layers.** README.md, design.md's Overview (lines 3-11), design.md's Summary (lines 569-579), and fragments of notes.md all state the same definition, payoff, and workflow. README.md:3 and design.md:7 are near-verbatim copies of the same paragraph. The Summary restates the entire document it summarizes. A reader entering through the README then reading design.md top to bottom encounters the full pitch three times before reaching anything new.

2. **Defensive caveats accreted at every mention site instead of at the definition site.** The corpus was built through successive review-response commits, and each round's fix was patched in wherever the concept appeared. The result: "lack of proof is not a violation" appears roughly eight times in design.md; "the intent states the property, not an inventory of sites or tests" roughly seven; "the current body must remain complete without Amendments" five (lines 211, 312, 321, 325, 380). Each caveat is correct; the repetition is what a reader experiences as length. The fix is systematic, not sentence-by-sentence: state each rule once where its concept is defined, and let other sites use the defined term without re-arguing it.

3. **Design.md re-explains process rules at every stage that touches them.** The amendment rules are the worst case: format in the artifact spec (211-225), process in Amending the intent (284-337), a full re-walk in the review phase (380), echoes in the workflow list (396-398), the sample `/goal` (405-408), and the Summary (575). The would-fail demonstration is fully specified four times (367, 383, 405, 525) — the sentence "one falsification may support multiple criteria only when each test fails on its own claim" appears verbatim-adjacent in all four.

4. **Design.md duplicates the instruments in memo voice.** The Authoring Skill section (415-446) walks the same four phases authoring-skill.md specifies; the amendment record grammar (213-225) is specified again in authoring-skill.md:254-265 and implementation-guidance.md:59-70; the sample `/goal` invocation (400-411) is operational content. mechanics/README.md:5 currently sanctions this ("the design says everything the idea needs said") — so cutting here requires a deliberate boundary change, flagged below as **Decision D1**.

## Repetition to keep

Deliberate redundancy that should survive the restructure:

- **Design ↔ instruments.** Instruments are loaded by agents per role and must be self-contained; their overlap with the design (and with the always-loaded agents-md-block) is the two-voices architecture working. Part 2 shortens the *human* corpus; instrument-internal redundancy is a separate, later question with its own tradeoff (agent context cost vs. self-containment).
- **README as compressed pitch.** The five purposes and a short definition belong in both README and design.md — entry point and full document. What should not be duplicated is the paragraph-level text itself.
- **The fork test stated as both prose and decision tree** (design.md:68-80). Two renderings of the canonical statement serve different readers; keep both, in one place.
- **The worked example.** Concrete redundancy with the spec is what examples are for. Trim only where it re-*tells* process rules instead of *showing* them (see R11).
- **Short refrains** ("Today that means reviewing better; over time, it means reviewing less") — a sentence-length echo is rhetoric, not bloat.

## Repeated concepts: inventory

Format: canonical home (proposed) → all sites → action. Line numbers are `d2d443e`.

### R1. The definition paragraph (artifact + contract + team latitude)

- **Canonical:** design.md's Overview. design.md is fully self-contained and never references the change-intent README; it also absorbs the five purposes and the purposes-as-bar sentence, which currently live only in the README.
- **Sites:** README.md:3; design.md:7 (near-verbatim duplicate); compressed echoes at design.md:353 and 575.
- **Action:** design.md's Overview keeps the full definition. The README shrinks to a directory card that summarizes and points in (see the README target shape below). The echo in 353 trims to a clause; 575 goes with the Summary (R14).

### R2. The Overview pre-states the whole Downstream section

- **Sites:** design.md:9 states the three consumers (dup. of 355), replacement before merge (dup. of 341-347), the implementation/review evidence split (dup. of 357 and 383), and the core-adoption-level evidence rule (dup. of README.md:19 and notes.md:44-46).
- **Action:** Overview shrinks to orientation — what the artifact is, that the document covers concept → artifact → integration → skill — and stops pre-arguing. Two to three sentences replace lines 9-11.

### R3. Reviewability payoff refrain

- **Canonical:** design.md — the Overview for the pitch, 387-391 for the substantive human-review treatment; the README may echo one line as part of its directory card.
- **Sites:** README.md:19; design.md:5; design.md:387-391; notes.md:8-23 (mechanism discussion — distinct, keep).
- **Action:** design.md:5 keeps one framing sentence. No other change; listed to prevent the editing pass from cutting the wrong copy.

### R4. The change-defining test and implementation latitude

- **Canonical:** design.md:68-80 (Design principles — prose + tree).
- **Sites:** README.md:21 (compressed — keep); design.md:68-80; 263; 296 (partial re-derivation); 320; 379; 425.
- **Action:** 263, 320, 379, and 425 use the term "change-defining" with a link instead of re-stating the could-the-author-approve-once test. 296 keeps only its amendment-specific nuance (a fork created by the selected implementation is not necessary) and drops the general restatement.

### R5. Completeness is a quality standard, not omniscience

- **Canonical:** design.md:86 (one sentence at the artifact spec) + 537-539 (the full discussion, in Design Tensions).
- **Sites:** README.md:21; design.md:86; 537-539; (agents-md-block.md:13 — agent-facing, stays).
- **Action:** README.md:21 drops the caveat sentence; the README does not need to pre-defend. 86 keeps one sentence pointing at 537 for the argument.

### R6. Constraints are boundaries, not proof obligations — and the outcome/constraint/AC classification rule

- **Canonical:** §Constraints (design.md:100-104). The classification rule for environment-dependent targets lives there once.
- **Sites:** README.md:33; design.md:50 (one line in the Falsifiable principle — keep, the principle needs it); 62 (table row — keep, terse); 100-104; 116; 143; 164; 369; 372; 379; 575. The classification rule alone is stated four times: 104, 116, 143, 164.
- **Action:** The AC section states the redirect once ("statements like these belong in Outcomes or Constraints — see §Constraints") and the Performance subsection keeps only its own contribution: the environment-independence criterion and the good/bad examples. Lines 369, 372, 379 compress to "accounts for constraints as §Constraints defines" or equivalent; 575 goes with the Summary.

### R7. Invariants are not closed by tests; no site inventory

- **Canonical:** §Invariants (design.md:166-182).
- **Sites:** README.md:35 (short — keep); design.md:166-182; 357; 368; 406; 433/435; 525; 547 (tension-specific — keep).
- **Action:** 357's sentence "An invariant states a property and its intended reach, never a list of sites or tests…" is §Invariants' content verbatim — delete. 368 and 406 compress to the obligation without the rationale. 525 trims the re-teaching sentence ("The intent states the invariant properties; it does not enumerate…") — the example has already shown it.

### R8. The amendment cluster (biggest single consolidation)

- **Canonical:** one chapter, "Amending the intent" (284-337), which **absorbs the record format currently at 211-225**. The artifact-spec §Amendments becomes three to four lines: what the section is, that absence means the intent held, pointer to the chapter. This also fixes the current forward reference (the format at 211-225 depends on a process not yet explained).
- **Sites:** README.md:21, 27, 37 (three separate explanations in one README); design.md:86; 211-225; 292-304 (canonical process); 312; 320 (precedence repeated from 300); 321; 325-329; 370; 380 (full re-walk in the review phase); 396; 405; 504-523 (worked example — keep); 575.
- **Action:**
  - README carries the amendment concept **once** (in the line-21 paragraph or the line-37 bullet, not both plus line 27).
  - The precedence list is stated once (300); the copy at 320 becomes "the shared precedence above."
  - "The current body must remain complete without Amendments" is stated once, in the chapter (currently at 211, 312, 321, 325, and 380).
  - The review-phase item 3 (380) compresses to: what review checks (eligibility, coherence, precedence applied) with a link to the chapter — the *how* is already there and in review-guidance.md. Roughly ten lines become three.
  - "What an amendment leaves behind" (323-329) merges into the chapter's format material; most of it duplicates 211-225 once they are co-located.

### R9. Replacement before merge

- **Canonical:** Revision before merge (design.md:341-347).
- **Sites:** README.md:21, 25; design.md:9; 86; 253; 286; 314; 341-347; 353; 398; 429; 575.
- **Action:** Every site outside the chapter reduces to one clause — "the author may replace the unmerged intent (see Revision before merge)" — instead of re-explaining supersession, clean-baseline, and reassessment semantics. The current text re-explains those at 314, 345, and 429.

### R10. One current intent; frozen after merge; merged intents don't govern later changes

- **Canonical:** File location and naming (design.md:253), with one sentence at 86.
- **Sites:** README.md:21; design.md:86; 253; 343; 345; 355; 381.
- **Action:** 345, 355, and 381 reference rather than restate.

### R11. The would-fail demonstration

- **Canonical at design level:** the implementation-phase bullet (367), stated once in compressed form; the full procedure already lives in implementation-guidance.md.
- **Sites:** design.md:367; 383; 405-408; 525.
- **Action:** 383 keeps only what is new there — *why* the requirement exists (the agent writes both code and tests) and that review does not depend on the session demonstrations — and drops the procedural restatement. The sample `/goal` invocation (400-411) moves to implementation-guidance.md (see Decision D1) or shrinks to two lines; its five bullets duplicate 367-370 almost line for line. 525 trims to one sentence. The "one falsification serves multiple criteria only when…" sentence survives in exactly one design.md location.

### R12. Review independence, evidence latitude, and `cannot verify`

- **Canonical:** the review phase (design.md:376-385).
- **Sites:** README.md:19, 27; design.md:9; 357; 383; 389; 397; 539; 575. The "teams may preserve further evidence" rule alone appears at README.md:19, design.md:9, 357, 383, and notes.md:44-47.
- **Action:** 357 currently makes the full independence argument that 383 makes again — keep it in the review phase, reduce 357 to the thin-handoff statement. `Cannot verify` semantics are defined once (383); 397 and 539 use the term without re-defining it.

### R13. Roles are logical; teams map them freely; the author needn't be human

- **Canonical:** one place, proposed: the Diligence principle (design.md:48) for the role/latitude rule, and "The intent author doesn't have to be a human" (277-281) for the autonomous trajectory.
- **Sites:** README.md:3, 15, 27; design.md:7; 48; 278; 353; 391; 577; notes.md:34-40; 42-53.
- **Action:** This is the most-repeated meta-point in the corpus. README keeps purpose 5 and one sentence in Adoption fit. design.md:353's intro paragraph trims its restatement; 577 goes with the Summary. notes.md:34-40 substantially duplicates design.md:277-281 — keep the design.md copy, reduce the notes passage to its one distinct point (teams orchestrate in unpredictable ways).

### R14. The Summary section (design.md:569-579)

- **Action: delete it, or reduce to a three-sentence close.** Line 571 repeats the Problem section; 573 repeats the artifact spec and naming; 575 repeats the entire Downstream section including the amendment and constraint rules; 577 repeats 277-281; 579 repeats 415-446. Nothing in it is unique. A document whose body is tight does not need an internal summary — the README is the summary.

### R15 (minor). Review-job conflation stated twice

- **Sites:** design.md:31-38 (Problem 5: four jobs) and 265-270 (two cognitive tasks).
- **Action:** These are related framings, not duplicates, but 265-270 can compress to two lines with a back-reference to Problem 5.

### R16 (minor). README's three amendment/author-ruling mentions

- **Sites:** README.md:21, 27, 37 all state that the author rules on amendments when work returns.
- **Action:** once.

## Restructuring plan

### The rule that drives everything

**Each concept is argued in one home; every other mention restates just enough to keep the local text readable — a clause, not a re-derivation.** The goal is that each document reads well top to bottom, not deduplication for its own sake; the two align almost everywhere, and where they pull apart, readability wins. The guard against the accretion pattern resuming still holds: a future review fix lands at the concept's home, and other sites keep only their reading-flow restatements.

### README.md (change-intent) — target shape

A directory card, not a compressed spec. The README says what this folder holds and points into it: a short definition, a line or two on why a team would care, links to design.md and mechanics/. All design information — the five purposes, the purposes-as-bar test, adoption fit, section semantics, amendment and replacement rules — lives in design.md, which is fully self-contained and never references the README. A reader who starts at design.md never needs to go back. (This reverses the earlier framing where the README owned the pitch: design.md owns everything; the README summarizes.)

### design.md — target shape

Section-by-section, with what each becomes canonical for. The table lists sections in their **current** order and its cuts apply regardless of order; section order itself is revisited in "Reading order — the second pass" below, which is the recommended sequence for the final document.

| Section | Now | Action |
| --- | --- | --- |
| Overview (3-11) | Restates README + pre-states Downstream | 1 short paragraph + document map (R1, R2) |
| The Problem (15-38) | Mostly unique | Keep; light trim only |
| Design principles (42-80) | Mostly unique | Keep — canonical for: used-beats-better, no-adversary, falsifiability, continuation paths + role table, **approved boundaries** definition, **fork test + tree** (R4) |
| What an intent file contains (84-225) | Longest section; classification rule ×3; amendment format | Canonical for section semantics (R5, R6, R7). Classification rule stated once. §Amendments shrinks to a pointer; format moves to the amendment chapter (R8) |
| File location and naming (229-253) | Mostly unique | Keep — canonical for frozen history / one current intent (R10). Merge the overlapping slug points (choices 2 and 3) |
| Why the initial intent comes first (257-280) | Unique + one restatement | Keep — canonical for exploration boundary and AI-author (R13). Compress 263's fork restatement and 265-270 (R15) |
| Amending the intent (284-337) | Canonical process, minus format | **Absorbs the record format**; states body-standalone rule and precedence once each (R8) |
| Revision before merge (341-347) | Canonical | Keep as-is; everything elsewhere links to it (R9) |
| How It Integrates Downstream (351-411) | Heaviest internal repetition | Biggest cut. Intro (353-357) → thin-handoff + consumers, minus the latitude/invariant/evidence restatements. Implementation phase keeps the four bullets once (R11). Review phase keeps the four assessments with item 3 compressed (R8) and is canonical for independence + `cannot verify` (R12). Sample `/goal` moves to mechanics or shrinks to two lines (D1). Human review + workflow keep |
| The Authoring Skill (415-446) | Duplicates authoring-skill.md in memo voice | Keep: role split, the critical constraint (419), scaling, stopping condition. Phase walk (421-429) compresses to ~4 lines — the phases are the instrument's content (D1) |
| Worked Example (450-527) | Keep | Trim only 525-527 where it re-tells process rules (R7, R11) |
| Design Tensions (531-551) | Mostly unique | Keep — canonical for completeness-not-omniscience (R5) |
| Where this is heading (555-565) | Unique | Keep |
| Summary (569-579) | Full duplicate | Delete or 3 sentences (R14) |

Estimated result: design.md from 586 lines to roughly 380-420 — about a third shorter — with no rule lost, because every deletion has a surviving canonical site.

### notes.md

Small file, mostly distinct. Two trims: 34-40 duplicates design.md:277-281 (R13); 42-53's latitude points consolidate once design.md has a single canonical latitude statement. "Nearest alternatives" and "Two voices" stay untouched.

### Reading order — the second pass

The first pass optimized for deduplication; this pass asks whether the surviving document reads best top to bottom. Verdict: the cuts stand, but the section order should change with them. design.md tells the story of a change out of chronological order, and both its introduce-before-reference problems and part of its repetition trace to that one fact.

**The ordering diagnosis:**

1. **The lifecycle is told out of order.** A change's life runs author → approve → implement (amend if needed) → review → return or replace → merge and freeze. The document presents: artifact (84) → naming (229) → why-first (257) → amending (284) → replacement (341) → implementation and review (351) → the authoring skill (415). The first step of the lifecycle is explained last; amendment mechanics come before the implementation stage they belong to; replacement comes before the "returned work" that triggers it; the workflow list at 393-398 references the skill 20 lines before its section begins. The review phase's re-walk of amendment rules (380, flagged as R8) is partly a symptom: the chapter that owns those rules is far away in the wrong direction, so the text re-explains instead of referencing. Chronological order makes the reference natural — review checks the amendments the *previous section* just defined.
2. **The role-path table (56-66) forward-references nearly everything.** Its rows use "amend on the record," `cannot verify`, and constraint-not-proof semantics — all defined later. As a preview it half-works; as a recap after the lifecycle it fully works, because every row then names a known concept.
3. **The change-defining test is buried.** The design's most novel mechanism (68-80) sits as an appendage to the continuation-path principle. It deserves a marquee position — its own short section — and it should sit immediately before the artifact chapter, which is where "change-defining" starts doing constant work.
4. **"Why the initial intent comes first" (257-280) is three different things in one section:** the rationale for the authoring stage (261-270), the prototype/exploration boundary (274), and the AI-author trajectory (277-281). The first two belong to the authoring stage; the third belongs with the forward-looking material at the end of the document, where it currently has a twin (577).
5. **The numbered workflow list (393-398) and the sample `/goal` (400-411) duplicate structure.** Once the middle of the document *is* the workflow in order, the list is a table of contents for the chapter it sits in, and the sample restates the implementation bullets. Both become deletable rather than trimmable (the sample moves to implementation-guidance.md under D1).

**Proposed spine** (the table's cuts still apply within each section):

1. **Overview** — self-contained: the definition, the five purposes in compact form, the purposes-as-bar sentence, the reviewability framing, and a document map matching this order. No reference to the change-intent README anywhere in the file.
2. **The Problem** — as-is, light trim.
3. **Design principles** — the four value principles, plus a short continuation-path principle that keeps the "approved boundaries" definition. The table moves out (item 6.5).
4. **The change-defining test** — promoted to its own short section, prose + decision tree, immediately before the artifact it governs.
5. **The intent file** — intro (complete over / open over), the sections (§Amendments = purpose + pointer forward), and file location / naming / frozen-at-merge as a closing subsection.
6. **The lifecycle of a change** (rename of "How It Integrates Downstream"), chronological:
   - **6.1 Authoring** — the why-first rationale (forcing function, direction before start, the two-tasks split), the skill in brief (role split, the critical constraint, compressed phases, stopping condition — the current §Authoring Skill after its D1 cut), and the exploration/prototype boundary.
   - **6.2 Implementation** — the intent as goal (`/goal` bullets, stated once), then **Amending the intent** as an intact block: necessity test, precedence, the record, who amends, rarity.
   - **6.3 AI review** — the four assessments, with item 3 now a short reference to the block directly above; independence and `cannot verify` semantics live here (R12).
   - **6.4 The human reviewer, return, and merge** — the payoff paragraph, **Revision before merge** (the author's mechanism, firing at the stage where it fires), then merge → frozen (pointer back to 5's subsection).
   - **6.5 The role-path table** as the chapter's closing recap: wherever a role gets stuck, its path — every row now referencing concepts the reader has.
7. **Worked example** — unchanged in content, and now it mirrors the document order exactly: request → exploration → approved file → amendment → implementation → review.
8. **Design Tensions.**
9. **Where this is heading** — absorbs "The intent author doesn't have to be a human," consolidating the forward-looking material that currently appears at 277, 555, and 577 into one place.
10. **Related.**

**What the reorder fixes that cuts alone don't:** concepts introduced before use without forward-glosses; the review section referencing the amendment block immediately above it instead of re-walking it; the two intent-change mechanisms each presented at the stage where they fire — agent amends during implementation, author replaces at return — with one contrast sentence linking them; the workflow list and sample `/goal` becoming deletions instead of trims; and the forward-looking material consolidated instead of scattered.

**Copy consequences — moves are not free:**

- Each relocated section's opening sentence must be re-stitched to its new predecessor; a moved section that still says "as described below" or assumes the old neighbor reads as damage.
- The Overview's document map must match the new order.
- "How It Integrates Downstream" renames (e.g., "The lifecycle of a change"); "Why the initial intent comes first" dissolves as a heading — its argument becomes 6.1's opening prose.
- Keep the amendment material intact as one block when it moves. Both review rounds treated its coherence as a strength; the relocation must not scatter it across 6.2.
- Early mentions of amendment and replacement become forward links (already R8/R9); "approved boundaries" stays defined once in the principles (used by both 6.2 and 6.3).

**Lower-risk alternative:** apply only the cuts and keep today's order. Safe, but it leaves the table's forward references, the skill-explained-last inversion, and the workflow-list redundancy in place, and the R8 review-phase compression has to fight the distance instead of benefiting from adjacency. Recommended: the full reorder — this restructure is already a real change; making it once, in reading order, avoids editing the same sections twice.

**README.md ordering:** sound as-is (what → purposes → payoff → adoption fit → pointers); only the Part 2 trims apply, no reorder.

## Decisions needed before applying

**D1 — the design/mechanics boundary.** mechanics/README.md:5 currently says the design "says everything the idea needs said" and the mechanics only add operational detail. The deepest cuts above (amendment grammar, sample `/goal`, the four-phase walk) move *normative operational detail* so it lives only in the instruments, with design.md carrying the concept plus the worked example. That is a boundary change: design.md stops being a self-contained spec and becomes the argument + artifact definition, with exact procedures owned by the instruments. Recommendation: accept it — a human adopter needs the concept and one concrete example, not the grammar, and the grammar already exists in three files. If accepted, reword mechanics/README.md:5 to match. If declined, the cut shrinks from ~35% to ~25% (the internal repetition still goes; the design keeps its own full copies of formats).

**D2 — where the fork test's canonical prose lives.** Revised by the reading-order pass: promote it to its own short section immediately before the artifact chapter (spine item 4), rather than leaving it as an appendage inside Design principles. The principles keep the continuation-path principle in short form (with the "approved boundaries" definition), and the role-path table moves to the lifecycle chapter's end as a recap (spine item 6.5). The original recommendation — keep the test at design.md:68-80 — stands only under the lower-risk no-reorder alternative.

**D3 — instrument-internal redundancy.** The agents-md-block restates the fork test, precedence, necessity test, and constraint semantics that each instrument also carries. That redundancy is deliberate (self-contained instruments) but costs agent context on every load. Out of scope for this pass; listed so it is a decision, not an accident, when the instruments are next revised.

## How to run the edit

1. **The restructure commit first:** reorder design.md to the proposed spine, fold the amendment format into its block (R8's move), delete the Summary (R14), and re-stitch every moved section's transitions and the Overview map in the same commit. Moves before cuts — cutting first means defining every cut against an order that is about to change.
2. **Then the lifecycle-chapter cuts (R11, R12),** which the new adjacency makes natural: the workflow list and sample `/goal` fall out here, and the review section's amendment re-walk collapses to a reference.
3. **Then the per-site caveat sweep (R4-R7, R9, R10, R13)** — delicate: at each site, confirm the canonical home actually carries the caveat before deleting the local copy.
4. **Then README and notes.**
5. **Then Part 1 (voice) over the surviving text,** re-locating entries by quoted phrase — most line numbers are stale by this point.
6. **Final read top to bottom** as a first-time reader: check each section's opening flows from its new predecessor, no concept is used before its introduction, and no caveat lost its last home.
