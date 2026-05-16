# ai-toolbox

A workspace for AI development tools, skills, and ideas.

## The core idea

The goal is to construct changes in a way that they're **reviewable**. Less focus on the change itself, more focus on the review process around it.

Today, a reviewer has almost no signal about how a change was produced. A 400-line diff could be the result of careful thought and many iterations, or slapped together in one shot — the reviewer can't tell, and ends up redoing the verification work themselves.

**Change Intent** flips that. Before any code is written, the author commits to:

- **Why** the change is being made
- **What the change does** — stated as falsifiable claims the implementation must prove

By the time the change reaches a human reviewer, there is a structured artifact stating what the change is supposed to do and machine-verified evidence that it does it. The reviewer's job collapses to the part only a human can do well: *is this the right intent?* — not *does this code work?*

## Secondary effects

The core idea is reviewability. But for that to land in practice, the system has to feel smoother than the way we work today, not more painful. Developers are already figuring out what software development looks like in an AI era; a process that adds friction on top of that won't survive. The design below is shaped so the practice is doable end-to-end, and that produces several intentional secondary effects worth naming.

### 1. Authoring is a skill, not a policy

At the top of the funnel, an authoring skill helps the developer and the AI work out what the change should be. This is planning, but formalized away from the *mechanics* of what code to write and toward the *outcomes*: what is the reason for the change, what must be true when it's done. Because it's a conversational skill, adoption is low-friction — the developer isn't filling out a form, they're sharpening their thinking. Teams can pick this up without it feeling like extra ceremony.

### 2. Slides cleanly into agent goals

The change intent is naturally shaped to be the goal for an implementation agent. Today that's Claude Code's `/goal`; tomorrow it will be something else. The pattern of *agent working toward a clearly-stated goal* is evergreen. In an AI coding era the internal structure of code matters less than the outcomes — which invariants hold, which APIs exist, how they behave. Change intent captures exactly that, in a form the implementation agent can work against directly.

### 3. Feeds the automated review harness with high-signal context

The review harness knows every change should carry a change intent, knows what change intent means, and can validate two things: is the intent itself well-described, and does the diff actually match what's claimed in it? This sits on top of the review checks you'd expect anyway — concurrency, bugs, clarity. The change intent isn't relying on a single Haiku pass behind `/goal`; it gets checked again by the review agents with a different lens before a human ever opens the PR.

The combined effect: a human reviewer arrives at a change with confidence that it has been thought through, that multiple passes have agreed the implementation matches the intent, and they can spend their attention on the judgment work — is this the right change to make.

## Layout

- `ideas/` — design notes and proposals for tools/skills that may become real
  - `change-intent/` — a structured pre-code intent document and authoring skill
