# Change Intent

A structured artifact authored *before any code is written* for a change. It captures two things:

- **Why** the change is being made
- **What the change does** — stated as falsifiable claims the implementation must prove

The goal is to construct changes in a way that they're **reviewable**: less focus on the change itself, more focus on the review process around it. By the time a change reaches a human reviewer, the change intent has already been used as the goal for the implementation agent and validated by an automated review pass, so the reviewer can focus on the judgment question — *is this the right intent?* — instead of redoing the verification work.

See [design.md](design.md) for the full design, secondary effects, and the authoring-skill specification.
