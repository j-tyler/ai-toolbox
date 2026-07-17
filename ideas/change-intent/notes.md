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

## Nearest alternatives

A team evaluating change intent may weigh it against three familiar
practices. What it does differently:

**A committed plan document.** A plan says what will be done. Once the
work merges it tells the future nothing: the code shows what happens,
not why, and not what was intended. An intent states what the change
must and must not do — a goal that judges when implementation is done,
a target review checks the finished change against, and, after merge,
the record of why the change was made: the most valuable context of the
work, kept with the code it produced. A reviewer who can see what the
agents were held to can spend their attention where it is most valuable.

**Architecture decision records.** An architecture decision record is a
standing, project-wide decision: it binds future work until another
record supersedes it, so before acting, an agent must gather the records
still in force and reason across them — a burden that grows with the
project. A merged intent binds nothing later. It governs only its own
change, so a project using change intent gets clearer as changes
accumulate, not more complicated: the repository carries the why behind
every change it contains, and for an AI agent that history is
incredibly rich.

**Spec-driven development.** A system spec tries to be complete about
behavior and must be maintained as the system changes. A per-change
spec — requirements, design, tasks, written before the work — is the
closest neighbor, but it still tries to describe the whole change, the
how included. An intent is deliberately smaller than either: the
change-defining test lets in only the decisions that choose which
change is delivered, and everything else stays the implementer's call.
One intent per change, frozen at merge — there is nothing to maintain.

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
