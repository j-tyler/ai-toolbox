# Change Intent: Mechanics

**Status: all four instruments are drafted.**

[design.md](../design.md) states the design in full — the argument, the artifact, the amendment protocol, the downstream integration, the authoring workflow. This folder holds the operational instruments a project actually installs to run it: skill files, prompt blocks, templates, tool bindings. The boundary is readability, not content: the design says everything the idea needs said; the mechanics carry the implementation detail — prompt-level engineering, harness specifics, agent failure-mode countermeasures — that would make the design read like a manual.

The package, in the order a team adopts it:

1. [agents-md-block.md](agents-md-block.md) — pasted into the project's agents file; always-loaded orientation, rules, shared vocabulary, and routing to the other three instruments
2. [authoring-skill.md](authoring-skill.md) — the skill that authors the initial pre-implementation intent and replaces the current unmerged candidate when returned work changes the author's direction
3. [implementation-guidance.md](implementation-guidance.md) — guidance a team adds to its implementing agents' instructions: how to work from an approved intent, and how to amend it on the record
4. [review-guidance.md](review-guidance.md) — guidance a team adds to its existing review instructions, so the review pass checks each diff against its intent

## Audience and voice

The package has two audiences. [README.md](../README.md), [design.md](../design.md), this file, and the preamble before the first horizontal rule in each instrument are written for a team evaluating or adopting the process. They describe purpose, authority, tradeoffs, and integration in the style of an engineering RFC. The content after that boundary is written for an AI agent executing a specific role. Those sections use direct instructions, explicit decision tests, and defined stop conditions.

The separation also reflects different failure modes. A design defect concerns the artifact or process and is addressed in [design.md](../design.md). A mechanics defect occurs when an agent executes the intended process incorrectly: the authoring agent asks the author to decide an ordinary implementation detail, the implementation agent resolves a change-defining decision without an amendment, or the review agent treats every observable side effect as missing intent. These are instruction-level failures and are addressed in this directory rather than in the design rationale.

Each instrument records the requirements for its role, including the known agent failure modes it is intended to prevent.
