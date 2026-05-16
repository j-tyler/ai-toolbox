# ai-toolbox

A workspace for AI development tools, skills, and ideas.

## The core idea

Lower the burden on code review by making the design and implementation process **provable**.

Today, a reviewer has almost no signal about how a change was produced. A 400-line diff could be the result of careful thought and many iterations, or it could be slapped together in one shot — the reviewer can't tell, and ends up doing the verification work themselves.

**Change Intent** flips that. Before any code is written, the author commits to:

- **Why** the change is being made
- **What the change does** — stated as falsifiable claims the implementation must prove

A review agent then checks the implementation against the intent. By the time the change reaches a human reviewer, there is already a structured artifact stating what the change is supposed to do and machine-verified evidence that it does it. The human reviewer's job collapses to the part only a human can do well: *is this the right intent?* — not *does this code work?*

## Layout

- `ideas/` — design notes and proposals for tools/skills that may become real
  - `change-intent/` — a structured pre-code intent document and authoring skill
