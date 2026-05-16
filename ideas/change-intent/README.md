# Change Intent

A structured artifact authored *before any code is written* for a change. Each change has three required pieces:

- **Why** — the motivation, in enough detail that a future reader understands what triggered the work and what context shaped the decisions.
- **Acceptance criteria** — falsifiable scenarios that must hold for the change to be accepted, each provable by a single test. "When a user does X, the system returns Y." Mechanical to verify.
- **Invariants** — properties that must hold *across* the change, spanning multiple call sites or code paths. Not provable by a single test; closed by reasoning over the diff at implementation and review time. "Read-after-write holds across all caller paths of `GetUser`."

ACs and invariants are kept separate because they invite different downstream behavior: the implementation agent runs a test per AC and walks the diff for each invariant, and the AI review pass treats invariants as the heaviest single thing it scrutinizes.

The goal is to construct changes in a way that they're **reviewable**: less focus on the change itself, more focus on the review process around it. By the time a change reaches a human reviewer, the change intent has already been used as the goal for the implementation agent and validated by an automated review pass, so the reviewer can focus on the judgment question — *is this the right intent?* — instead of redoing the verification work.

See [design.md](design.md) for the full design, secondary effects, and the authoring-skill specification.
