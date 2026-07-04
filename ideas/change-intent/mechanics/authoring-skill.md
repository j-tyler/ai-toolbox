# Authoring Skill

**Status: stub. To be built after the design is settled.**

The runnable skill implementing the structured pre-code dialogue specified in [design.md](../design.md) ("The Authoring Skill") — the workflow, depth calibration, and stopping condition all live there; the design states them fully. This file holds what the design deliberately leaves out: the prompt-level engineering that makes the dialogue work when the agent running it is fluent, fast, and eager to help. It channels that helpfulness into working *with* the author — the agent brings context and rigor, the author brings intent.

Requirements — each countering a known failure mode of a capable agent in this seat:

- **Elicit, don't draft.** The agent's strongest default is to take a vague seed, write the whole intent itself, and ask "does this look right?" — the author rubber-stamps, and the artifact records the agent's intent wearing the author's signature. Candidate claims are proposed only as questions, each paired with the specific code evidence that motivated it. The author affirmatively accepts or edits every claim; no batch approval. If the author waves through several claims in a row unedited, the skill says so and slows down.
- **Confidence-marked baseline.** The surface read (workflow steps 2–3) distinguishes "documented and tested" from "appears true, nothing enforces it." An inferred guarantee stated fluently poisons every question built on top of it.
- **Pre-filtered categories.** Present only the categories the surface read implicates, with the evidence ("this path spawns goroutines → concurrency applies"); the rest are dismissed in one line the author confirms. Nine mandatory not-applicable declarations produce fatigue, not coverage.
- **Red-team before sign-off.** Before convergence, the skill constructs the strongest implementation that satisfies every stated claim while clearly not being what the author wants. Claims that survive ship; the gaps become new claims. This is cheaper and sharper than another round of open questions.
- **Pacing.** One category per turn, answer before the next question. A long questionnaire produces lazy answers and lets the skill fill silence with its own assumptions.
- **Test-feasibility check.** Every acceptance criterion's proving test must be writable in this repository's actual harness. An AC that is true but unprovable here is caught at authoring time, not discovered as a dead end mid-implementation. (Whether "true but unprovable" also needs a home in the amendment protocol is an open artifact question in design.md.)
- **Persist the surface read.** What the skill found — caller lists, existing guarantees, prior intents touching the same surface — is evidence the review pass needs later. Where it lands is an open artifact question in design.md.
