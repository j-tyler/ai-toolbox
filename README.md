# ai-toolbox

A workspace for AI development tools, skills, and ideas.

## Ideas

- **[Change Intent](ideas/change-intent/README.md)** — a lightweight, cooperative workflow contract carried by a durable per-change artifact whose initial form is approved before implementation. It clarifies the intended change, gives implementation a goal and decision boundary, gives review a consistent target, and preserves valuable context for future agents.
- **[AI Documentation](ideas/ai-documentation/README.md)** — documentation written for AI readers rather than human ones: facts kept as local as possible to the code they describe, and Mermaid diagrams written for the model reading the text rather than for the rendered picture. Includes a diagram guide, a guide for placing those facts into the codebase, and an example agents file.
- **[Working in Public](ideas/working-in-public/README.md)** *(stub)* — the principle of capturing the most valuable outputs of human-AI work in artifacts that persist, rather than letting them die with the context window they happened in. Change intent is one instance of this pattern.
- **[Sendy](ideas/sendy/README.md)** — a proposed local message-passing utility that intentionally blocks agents while they wait for the next assignment, giving parent-child AI workflows a simple, harness-agnostic communication interface.

## License

Original content in this repository is released under [CC0 1.0 Universal](LICENSE) — a
public domain dedication. You can copy, modify, and reuse any of it for any
purpose, commercial or not, with no attribution required and no obligation to
include this license in whatever you build.

Third-party dependencies retain their own licenses. See Sendy's
[packaging and redistribution requirements](ideas/sendy/README.md#packaging-and-redistribution)
before distributing a compiled binary or dependency source.
