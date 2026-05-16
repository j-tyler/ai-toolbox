# ai-toolbox

A workspace for AI development tools, skills, and ideas.

## The problem this repo is attacking

AI now writes code faster than humans can carefully review it, and the "careful per-line review" we pretend to do is mostly theater anyway. So instead of asking "when can we trust AI to review," the goal is to **build a process that's verifiable regardless of who runs it** — where intent is authored explicitly, up front, in a form both humans and machines can check code against, instead of being reverse-engineered from a 400-line diff.

That also splits the two jobs reviewers conflate today: *deciding what should be true* (high-judgment, human) vs. *verifying the code matches* (mechanical, machine).

## Layout

- `ideas/` — design notes and proposals for tools/skills that may become real
  - `change-intent/` — a structured pre-code intent document and authoring skill
