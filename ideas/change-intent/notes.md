# Change Intent: Notes

This file holds information that lies outside the design: the premises it
rests on and the directions it leans toward. Nothing here is part of the
design, and nothing here changes it. If a point would change what
[design.md](design.md) says, it belongs there.

## Reviewing less

The design says that over time, humans review less. Two mechanisms
produce that, and they are different in kind.

The first is the codebase itself. A project that uses change intent
gains quality over time: every merged change was built and checked
against stated claims, and the record of past intents stays in the
repository. Working with that record, the human reviewer learns where
mistakes actually happen and what actually needs their attention. Their
review gets smaller because it gets better aimed.

The second is AI getting smarter. As models improve, they make fewer
mistakes and need less handholding in review. That is outside the scope
of this work. We are not building the thing that makes AI better; we are
building the process that benefits when it does.

Both mechanisms are designed for. Change intent is deliberately built so
that a team using it grows into this future: the codebase improves, AI
improves alongside it, and at some point human review may go away
altogether — while the artifact and the process keep their shape the
whole way. Just as deliberately, nothing in the design works against
that future. This matters when adopting a process while the future is
uncertain: what a team adopts today should still fit the future when it
arrives.
