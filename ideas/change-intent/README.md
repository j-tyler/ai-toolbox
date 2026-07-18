# Change Intent

This folder holds the design for **change intent**: a lightweight, cooperative workflow contract carried by a durable per-change artifact. The intent's initial form is approved before implementation begins; implementation works from that direction, and review assesses the resulting change against it. The payoff is reviewable changes today, and a process that keeps working as AI takes on more of the authoring, implementation, and review.

Start with [design.md](design.md). It is self-contained: the problem, the design principles, the change-defining test, the intent file's sections, the life of a change from authoring through merge, a worked example, and the open questions.

The operational instruments a project installs to run the process — an agents-file block, the authoring skill, implementation guidance, and review guidance — are in [mechanics/](mechanics/README.md). Premises and direction that sit outside the design are in [notes.md](notes.md).

Change intent is one instance of [working in public](../working-in-public/README.md): capturing the most valuable outputs of human-AI work in artifacts that persist beyond the session that produced them.
