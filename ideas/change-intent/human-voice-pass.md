# Human-Voice Pass: Findings

**Corpus revision:** `d2d443e`. All line numbers below refer to that revision; re-verify before editing if the files have moved.

**Scope.** Per the two-voices rule in [notes.md](notes.md), the human-read corpus is: the root `README.md`, `ideas/change-intent/README.md`, `design.md`, `notes.md`, `mechanics/README.md`, `ideas/working-in-public/README.md`, and the preamble before the first horizontal rule in each mechanics instrument. The instrument bodies are agent-facing and deliberately untouched by this pass. The two multi-angle-review files are frozen review records, not adopter-facing corpus, and are excluded.

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
