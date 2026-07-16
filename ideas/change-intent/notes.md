# Change Intent: Notes

This file holds information that lies outside the design: the premises it
rests on and the directions it leans toward. Nothing here is part of the
design, and nothing here changes it. If a point would change what
[design.md](design.md) says, it belongs there.

## Reviewing less

The design says that over time, humans review less. Two mechanisms
produce that, and they are different in kind.

The first is the codebase itself. A project that uses change intent
gains quality over time because every merged change was built and
reviewed against stated claims. The human reviewer learns where mistakes
actually happen and what needs their attention. Their review gets smaller
because it gets better aimed. Earlier intent files remain records of their
own changes, not requirements for later ones.

The second is AI getting smarter. As models improve, they make fewer
mistakes and need less handholding in review. That is outside the scope
of this work. We are not building the thing that makes AI better; we are
building the process that benefits when it does.

Both mechanisms are designed for. Change intent is deliberately built so
that a team using it grows into this future: the codebase improves, AI
improves alongside it, and at some point human review may go away
altogether. The semantic responsibilities and shared decision artifact
remain useful even as the people, agents, tools, and interactions around
them change. This matters when adopting a process while the future is
uncertain: what a team adopts today should still fit the future when it
arrives.

The roles are stable responsibilities, not permanent assignments to
humans. An AI orchestrator given an upstream objective and an appropriate
authority boundary may occupy the author seat, while multiple specialized
agents may implement and independently review through the same artifact.
Change intent defines the responsibilities those agents inherit while
leaving teams substantial latitude in how they orchestrate them and
establish authoring authority.

## What the design leaves to the team

At the core adoption level, change intent adds one new durable per-change
artifact — the intent file — and asks the project's agents to honor it.
Teams may retain or require additional workflow evidence appropriate to
their environment. Beyond the minimum responsibilities and logical flow
defined by the design, teams retain substantial latitude: where review
findings live, who or what holds the author and reviewer seats, and when
each first reads an intent. Teams run design and review in ways we cannot
predict, and additional core rules about their process would shrink the
set of teams the design fits. A team that wants more can extend the workflow
for its environment.

Urgent changes use the same process because the authoring dialogue scales
with the change.

## Two voices

These files are written for two readers, and each file holds one voice.

The design files — design.md and the READMEs — are for people deciding
whether to adopt change intent. They are written as a professional
memo: declarative prose, the argument and the artifact, no operational
detail.

The mechanics instruments — the agents-file block, the authoring
skill, the implementation guidance, the review guidance — are loaded
by an AI agent taking a seat in the process. They are written for how
an agent reads: explicit rules, enumerated cases, nothing left to tone
or implication.
