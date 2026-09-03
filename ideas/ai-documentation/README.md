# AI Documentation

Code that AI agents read and write needs different documentation than code written
for people. This folder holds an idea about what that documentation should look
like and where it should go.

## The premise

Two beliefs sit underneath everything here.

**Information should be as local as possible.** The most useful place for a fact
about a line of code is directly above that line. The most useful place for a fact
about a class or a method is directly above its definition. Agents read the top of
a file first, so a block of file-level documentation at the top is a cheap way to
put real context in front of them — what the file owns, what depends on it in ways
the imports don't show, what it will break if changed. Whenever an agent opens that
file, whether to implement something or to review a change, that context lands in
its window at exactly the moment it's needed.

**Diagrams are worth writing for the AI reader, not the picture.** A model reads the
diagram's source text, never the rendered image. Because models already understand
Mermaid, a Mermaid diagram is a very token-efficient way to express relationships,
lifecycles, and cross-process flows — the things that no single file can show.
But that only works if the diagram is written for someone reading the text top to
bottom: exact identifiers, comments carrying the meaning, deliberate absences
written down. Most training data optimizes for the rendered picture instead, so
this has to be spelled out.

## The three pieces

**1. [Diagram guide](diagram-guide.md)** — how to write Mermaid for an AI reader.
Which diagram types are worth drawing, when each one is the wrong choice, and the
exact rules for writing them: real identifiers as names, no placeholder nodes, no
meaning carried by layout or color, and an explicit statement of what the diagram
is complete over.

**2. [Placement guide](placement-guide.md)** — how to get those facts into the code.
Diagrams sitting in a documents folder are nice; the value comes from putting each
fact next to the code it describes. This guide takes a set of diagrams and decides
what gets written into the repository, in what form, and where — a structured
block at the top of a source file, a comment above a specific line, a directory
README, an index in the root agent file, or a glossary row. Hand it to an agent
along with your diagrams and it does the placement.

**3. [Example agents file](agents-file-example.md)** — not something to copy as-is.
It shows what a repository's root instructions file needs to say once the placement
guide has been run against it: how to read the blocks and comments that are now in
the files, what to trust when documentation and code disagree, and how to keep it
current. Take the parts that fit and adapt them for your own repository.

## Status

Early. The three documents exist and are usable, but the idea hasn't been run
end to end on a real codebase yet, and nothing here is automated.
