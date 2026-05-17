# Working in Public

**Status: stub. To be expanded in a later commit.**

Most work between humans and AI happens inside a single context window. When that window disappears, the value of those tokens disappears with it — a lot of high-value structured thinking thrown away.

"Working in public" is the principle of capturing the high-value outputs of that work in artifacts that persist — visible to future AI agents and future humans, referenceable from new contexts, durable beyond the session that produced them. Not every context window should be saved (that isn't economical). But the artifacts that crystallize the structured work — decisions, intents, design rationales, verified properties — should live in the repository alongside the code.

The benefit shows up immediately and compounds over time:

- **Near-term:** the implementation agent has a clear goal; the AI review pass has clear context for what to focus on; the human reviewer knows what's already been verified by machine and can spend their attention on the judgment work.
- **Later:** a future engineer (or AI) can look at a commit and understand why it happened and what the thinking behind it was, weeks or months on. Each artifact becomes context for the next one, and the practice compounds.

**Already in this repo:**
- [Change intent](../change-intent/README.md) is one instance of this pattern. The pre-code dialogue between a deciding agent (human or AI orchestrator) and the authoring skill produces high-value tokens; those tokens persist with the change forever, consumed by the implementation phase, the AI review pass, and future humans and agents.

This is a stub. The principle deserves a fuller treatment — what's worth capturing, what file shapes work best, how the practice scales across a repo, where the economic line sits between save and discard. To be developed.
