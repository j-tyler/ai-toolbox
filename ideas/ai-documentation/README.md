# AI Documentation

Code that AI agents read and write needs different documentation than code written
for people. This folder holds an idea about what that documentation should look
like and where it should go.

## The premise

Two beliefs sit underneath everything here.

**Information should be as local as possible.** Put a useful fact about a line
above that line, and a file-wide fact or navigation pointer in its header map.
Keep a coherent explanation together when its relationships, ordering, or
conditions would lose meaning if split into comments. Such explanations belong
beside their definition or in owner-local documentation, with specific routes from
the relevant source files. Agents may reach a function directly through search,
so a locally important constraint or hazard still belongs at the operation where
it matters.

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
The guide decides whether to retain a coherent diagram, extract independently
useful facts, or omit redundant or unsupported material. It places the result in
source maps, comments beside code, owner-local explanations, root indexes, or the
glossary. Full explanations keep the context that makes their relationships useful;
source pointers make them discoverable without copying them into every file.
README and root navigation select useful starting points rather than aggregating
every source map or flow.
Hand it to an agent with the diagrams and current code for placement.

**3. [Example agents file](agents-file-example.md)** — not something to copy as-is.
It shows what a repository's root instructions file needs to say once the placement
guide has been run against it: how to read the blocks and comments that are now in
the files, what to trust when documentation and code disagree, and how to keep it
current through direct reading, search, and editing. It is self-contained for
readers who do not have the placement guide or its input artifacts. Take the parts
that fit and include only commands and conventions established in your repository.

See the [placement examples](examples/README.md) for runnable before/input/expected
fixtures and a compact maintenance exercise.

## Status

Early. The three documents exist and are usable, but the idea hasn't been run
end to end on a real codebase yet, and nothing here is automated.
