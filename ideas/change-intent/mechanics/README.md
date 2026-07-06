# Change Intent: Mechanics

**Status: the agents-file block and authoring skill are drafted; the implementation reference and review skill are stubs, to be built after the design is settled.**

[design.md](../design.md) states the design in full — the argument, the artifact, the amendment protocol, the downstream integration, the authoring workflow. This folder holds the operational instruments a project actually installs to run it: skill files, prompt blocks, templates, tool bindings. The boundary is readability, not content: the design says everything the idea needs said; the mechanics carry the implementation detail — prompt-level engineering, harness specifics, agent failure-mode countermeasures — that would make the design read like a manual.

The package, in the order a team adopts it:

1. [agents-md-block.md](agents-md-block.md) — pasted into the project's agents file; always-loaded orientation, the when-required policy, shared vocabulary, and routing to the other three instruments
2. [authoring-skill.md](authoring-skill.md) — the skill that runs the pre-code elicitation dialogue and writes the intent file
3. [implementation-reference.md](implementation-reference.md) — how the implementation agent binds a signed intent to its harness's goal mechanism, and how it halts and escalates
4. [review-skill.md](review-skill.md) — the skill for the AI review pass that checks a diff against its intent

The split matters because the two layers fail differently. A design flaw means the artifact or the process is wrong — fixed once, in design.md. A mechanics flaw means an agent runs the right process badly: an authoring skill that drafts the intent for the author instead of eliciting it, an implementation agent that quietly resolves a forced choice instead of halting, a review pass that confirms instead of adversarially checks. Those failure modes are real and predictable, but they are prompt-level problems with prompt-level fixes, and they live here so the design can stay silent on them on purpose.

Each stub records the requirements the eventual instrument must satisfy — including the known agent failure modes it exists to counter — so it gets written against a checklist rather than from memory.
