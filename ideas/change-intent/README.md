# Change Intent

The goal is to construct changes in a way that they're **reviewable**: less focus on the change itself, more focus on the review process around it. By the time a change reaches a human reviewer, the change intent has already been used as the goal for the implementation agent and validated by an automated review pass, so the reviewer can focus on the judgment question — *is this the right intent?* — instead of redoing the verification work.

A change intent is a structured artifact authored *before any code is written* for the change.

**Why** is always included: the motivation for the change, in enough detail that a future reader understands what triggered the work and what context shaped the decisions.

It also includes any of the following when their conditions apply:

- **Acceptance criteria** — falsifiable scenarios that must hold for the change to be accepted, each provable by a single test. "When a user does X, the system returns Y." Applies when there's observable behavior to verify.
- **Invariants** — properties that must hold *across* the change, spanning multiple call sites or code paths. Not provable by a single test; closed by reasoning over the diff. "Read-after-write holds across all caller paths of `GetUser`." Applies when the change touches properties that span beyond a single test.
- **Out of scope** — what this change explicitly is *not* doing. Signals conscious exclusions to the implementation agent, the AI review pass, and the human reviewer. Applies when there are conscious exclusions worth signaling.

Each section serves a distinct downstream purpose: Why carries motivation to future readers; acceptance criteria are mechanically checked test-by-test; invariants invite property thinking across the diff; out of scope signals conscious exclusion to every downstream consumer. A section being absent means there's nothing for it to hold, not that the author skipped it.

See [design.md](design.md) for the full design, secondary effects, and the authoring-skill specification.
