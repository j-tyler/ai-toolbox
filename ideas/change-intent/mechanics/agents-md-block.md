# Agents-File Block

**Status: stub. To be built after the design is settled.**

The block a team pastes into their project's agents file (`AGENTS.md`, `CLAUDE.md`, or equivalent) so every agent working in the project is intent-aware without further setup. The block carries only the always-loaded rules — orientation, policy, shared vocabulary, and routing; the seat-specific instructions live in the instrument each agent loads when it takes the seat ([authoring-skill.md](authoring-skill.md), [implementation-reference.md](implementation-reference.md), [review-skill.md](review-skill.md)).

What the block must cover:

- **Orientation.** What change intents are, that they live in `change-intent/`, and that merged intents are frozen history — a grep hit on an old intent is a record of what was decided then, not a statement of what holds now.
- **When an intent is required.** The team's risk profile for requiring one, so the folder stays an honest record of deliberate work rather than filling with boilerplate that quietly degrades every downstream consumer.
- **Routing.** Authoring a change runs the authoring skill instead of ad-hoc planning; implementing from an intent follows the implementation reference; reviewing a change that has an intent runs the review skill. The block is how an agent landing in the project learns these instruments exist.
- **What counts as observable.** The channels the scope rules apply to (API responses, persisted data, named metrics and logs, public error types — the team's own list). This is shared vocabulary between the implementation agent and the review pass, so it lives in the always-loaded block. Taken literally, "no unclaimed observable behavior" is unsatisfiable — every diff perturbs error strings and timing — and an agent that learns a rule can't be satisfied learns to discount it.
- **Bounded-discretion convention.** How intents grant latitude ("TTL may be anywhere in 10–60s, implementation's choice") — written into the signed text at authoring time, exercised silently at implementation time, everything else escalating.
