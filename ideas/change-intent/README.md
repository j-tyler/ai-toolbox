# Change Intent

The goal is to construct changes in a way that they're **reviewable**: less focus on the change itself, more focus on the review process around it. By the time a change reaches a human reviewer, the change intent has already been used as the goal for the implementation agent and validated by an automated review pass, so the reviewer knows the process the change went through and what each step already checked, and puts their attention on the judgment question — *is this the right intent?* Today that means reviewing better; as the machines earn trust, it means reviewing less. This is an idea related to [Working in Public](../working-in-public/README.md) — the principle of capturing the high-value outputs of AI work in artifacts that persist beyond the session that produced them, so future agents can reference them; change intent does this for the pre-code dialogue that figures out what a change should be.

A change intent is a structured artifact authored *before any code is written* for the change. Until the change merges, the intent is a live contract: the implementing agent may amend it, on the record, only if it proves wrong as written, and the author may reopen and revise it if the returned work changes their mind. Once the change merges, it is frozen history.

**Outcomes** and **Why** are always included: what the change is intended to make true, and the motivation behind it — in enough detail that a future reader understands what triggered the work and what context shaped the decisions.

The change intent file also includes any of the following when their conditions apply:

- **Acceptance criteria** — falsifiable scenarios that must hold for the change to be accepted, each provable by a single test. "When a user does X, the system returns Y." Applies when there's observable behavior to verify.
- **Invariants** — properties that must hold *across* the change, spanning multiple call sites or code paths. Not provable by a single test; closed by reasoning over the diff. "Read-after-write holds across all caller paths of `GetUser`." Applies when the change touches properties that span beyond a single test.
- **Out of scope** — what this change explicitly is *not* doing. Signals conscious exclusions to the implementation agent, the AI review pass, and the human reviewer. Applies when there are conscious exclusions worth signaling.
- **Amendments** — repairs made during implementation, when the intent proved wrong as written and had to change for the change to be deliverable. One line per repair — what changed, and the discovered fact that forced it — with the full reasoning folded into the body next to the claim it changed. The author rules on any amendment when the work returns. Applies when implementation falsified part of the intent.

Each section serves a distinct downstream purpose: Why carries motivation to future readers; acceptance criteria are mechanically checked test-by-test; invariants invite property thinking across the diff; out of scope signals conscious exclusion to every downstream consumer; amendments preserve the chain of custody, recording how the contract bent when reality pushed back. A section being absent means there's nothing for it to hold, not that the author skipped it.

See [design.md](design.md) for the full design, secondary effects, and the authoring-skill specification. The mechanics that make it runnable in a project — the agents-file block, authoring skill, implementation reference, and review skill teams borrow — are stubbed in [mechanics/](mechanics/README.md).
