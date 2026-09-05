# AGENTS.md

This file is read at the start of every task. Name it whatever your agent harness loads automatically, `AGENTS.md` or `CLAUDE.md`, and keep one such file. It says how to run the code, where things are, and how to read and maintain the documentation you will find inside files. Anything in square brackets is a placeholder to be filled in for this repository.

## Commands

Every command runs non-interactively from a clean checkout. If a command needs a service, the command starts it.

- Install: `[command]`
- Run all tests: `[command]`
- Run the tests for one file: `[command] path/to/test_file`
- Typecheck: `[command]`
- Lint and format: `[command]`
- Run locally: `[command]`

## Conventions

Rules that apply everywhere in this repository, stated as rules.

- [Rule. Example: All database access goes through `repositories/`; nothing else imports the ORM.]
- [Rule. Example: Handlers return `Result`; they never raise.]
- [Rule. Example: A stored state field is changed only through its owner's transition functions, never assigned directly.]
- [Rule. Example: Generated code under `generated/` is never edited; change the source and regenerate.]

## Map

One line per top-level directory that has been described, looking past a bare wrapper directory such as `src/`. A directory not listed here has nothing written in it yet. A directory listed as not yet described carries facts written from another directory's side but no description of its own. Neither says anything about what it contains.

## Flows

Named scenarios that bring together behavior scattered across code locations. Each line names the flow, its actual first sender as shown in the diagram, and the Markdown path and heading anchor holding its sequence.

## Glossary

See GLOSSARY.md.

## Reading the documentation

Documentation uses five homes:

- A **map block** at the top of a source file: selected file-wide facts and routes to relevant explanations, using the keys below.
- **Comments above code**: local reasons, constraints, hazards, and hidden wiring facts; compact state or packet diagrams may sit beside their definition or operation.
- **Owner-local documentation**: directory READMEs hold ownership, named flows and explanations, and qualifying dependency rules or data models. A nearby subject document may hold a larger explanation, linked from the README. Source pointers lead directly to the relevant section.
- **This file's index sections**, `## Map`, `## Flows`, and `## Glossary`: follow their named directories or document locations.
- **`GLOSSARY.md`** at the root: domain terms, identifiers, and aliases.

Check behavior against current code. Documentation records selected claims verified when written and can become stale. Preserve its stated scenario and conditions when using it. A missing block, key, section, comment, or diagram edge does not establish absence, completeness, or exclusivity. A pointer helps find an explanation; it does not independently prove the relationship.

Before changing code, read its map, relevant linked explanations, and comments near the affected definitions or operations. Source search can land below a header, so inspect those local comments too. Follow exact identifiers and paths to the implementation; documentation helps decide what to read and does not replace that reading.

The Placement Guide's key reference gives the exact form of each map line.

## Comments in code

Code should explain itself. Write an inline comment only when it cannot and something important would otherwise be unclear: why a line exists, why it is unusual, what it works around, what elsewhere depends on it. Put the comment directly above the code it refers to. Never describe what the code does; that is visible by reading it. If a better name or a small restructuring would make the comment unnecessary, do that instead. Do not simplify or remove a line that has such a comment without addressing what the comment says.

## Maintaining the documentation

Keep affected documentation current with the code:

- For a known rename, move, or removal, find existing mentions by the old identifier and location and reconcile them against the code. Preserve unaffected supported wording and information.
- For a hidden connection, verify the endpoints and actual wiring. Use paired entries for compact connections, or the Placement Guide's shared-explanation exception: exact relationships and conditions in one explanation, routes from both eligible ends, necessary local qualifications, and references back to source. Do not place this documentation in excluded files, including tests, generated, vendored, configuration, migration, or pure utility files; name an excluded endpoint from the eligible end or explanation.
- Reconcile a removed connection wherever it was documented. Keep a shared pointer when its explanation still covers another relevant relationship.
- Maintain the permitted `writes:` and `calls:` indexes for documented table writes and external calls.
- Reconcile affected diagrams and their direct source pointers and index entries. Keep supported transitions, guards, notes, and qualifications absent from an incoming partial view. Add compatible verified information without inventing order or other connections between fragments. Distinct scenarios may need separate views.
- When a diagram moves or is removed, update its direct references. Search the affected subject, explanation name, and known locations; do not recursively audit unrelated explanations reached through participants.
- Keep one full copy of each explanation. Owner and shown-writer `transitions:` pointers, definition-owner and documented codec `format:` pointers, and flow pointers lead to the actual retained view. A targeted local hazard can remain beside the code as well.

Do not add inspection history or completeness claims. Unlisted behavior may exist; an omission warning does not repair an unsupported claim. Verify additions and changed meaning, preserve unresolved existing limitations, and follow the Placement Guide's reconciliation rules when a view contains a known-false claim.

## Map blocks

A source file may begin with a comment block delimited by `map` and `end map` comment lines. It records selected relationships and navigation: ownership, dependencies without visible calls or imports, tables written, external systems called, lifecycle and format locations, and named explanations. Read it and relevant linked explanations when working in the file; source search may also lead directly to a local comment. A missing block or key means only that nothing was recorded there; it does not show whether the file was inspected or whether what the block or key would describe exists. For example, no `event in:` line does not mean the file consumes no events. These selected facts were checked when written and do not guarantee current completeness. Verify relevant behavior before changing it.

Conventions: names are full identifiers, `module.function` for code and bare names for tables and external systems. A repository path in parentheses after a code name is its defining file; after an explanation name it is a Markdown path and heading anchor. A name followed by `(outside repository)` is a system with no file here and no partner line. `->` means "to" and `<-` means "from," in the direction control or data moves; an `out` line describes something leaving this file and an `in` line something arriving. A compact hidden connection normally has paired entries. A larger coherent relationship network may instead have source pointers from both eligible ends to one full explanation containing its endpoints, conditions, and wiring locations. Follow that explanation; a pointer alone is not proof of a connection. Locally necessary conditions and hazards remain visible beside code or in map facts. When the other end is a test, generated, vendored, or configuration file, or lies outside this repository, this line names it and nothing is written there. Two lines have no partner by design: `called from:`, because the caller's side is visible in the caller's own code, and a `soft-ref out:` into another database or service, which has no second end in this repository. A `di out:` line pairs with `di in:` on the implementation; the binding file it names need not have a paired key; a necessary registration fact may appear beside its wiring code. A qualifier `; in <identifier>` names the local function or object; `; when <condition>` limits every relationship on that line. Endpoints on one line share these qualifiers; separate lines distinguish different subjects or conditions. Neither a listed caller nor a listed validator implies that it is the only one. Diagrams also show selected relationships; their omission warnings limit what they explain.

- `owns:` what this file is responsible for. Use it to choose where to begin reading; it does not exclude other responsibilities or dependencies.
- `entry point of:` the first eligible in-repository sender in a retained scenario. The named Markdown section shows its sequence, including any preceding external or excluded sender. Read it before changing the relevant behavior.
- `participates in:` this file participates in a scenario whose entry is elsewhere; follow its Markdown path and heading anchor to the sequence. A change here can affect other steps.
- `explained in:` a named explanation covering this file or the local subject after `; in`. Follow its exact Markdown section for the combined relationships and source references; it does not imply completeness or a runtime dependency by itself.
- `called from:` callers whose execution context or hidden connection matters, with the reason stated, such as a scheduled job calling request-path code. Check them before changing behavior or signatures.
- `event out:` an event this file emits, and its documented consumers. Changing when it fires or what it carries can affect them; the list may be incomplete. These connections need not appear as direct calls or imports; a consumer marked `(outside repository)` is another system and has no line here to pair with.
- `event in:` a function here runs when the named event is emitted from the named place. To change what triggers it, go to the emitter.
- `hook out:` an operation on an object defined here, such as saving it, runs a handler elsewhere. Only operations that invoke the registered hook trigger it; bulk operations may bypass it. Respect any stated condition.
- `hook in:` a function here runs as a hook on an object defined elsewhere, when the registered operation and its conditions trigger the hook.
- `flag out:` a feature flag checked here decides which code runs. The two paths appear together as `FLAG -> on: ...; off: ...`, or on separate lines as `FLAG on -> ...` and `FLAG off -> ...` when their conditions differ. A `when` clause applies to its whole line, and `skipped` means that branch does nothing. Check both paths when changing the decision.
- `flag in:` the named caller reaches code here when its flag check has the named state, on or off. Other callers may reach the same code without that flag.
- `di out:` an abstraction resolved through a container here, and where its binding lives. The implementation is not named here; to find or change it, go to the binding.
- `di in:` a class here is what a container hands out for the named abstraction. The resolver need not name the implementation directly; other construction paths may also exist.
- `callback out:` a function here is handed to another module, which calls it later, in a context decided there.
- `callback in:` the named function from elsewhere is supplied to the stated parameter or registration point. Check how this receiver invokes it and handles its failures; other functions may also be supplied.
- `other out:` / `other in:` a hidden dependency through a mechanism named first: a file on disk, a cache key, an environment variable, a database trigger. Read both ends before changing the mechanism.
- `writes:` tables whose rows code in this file can change. Search for `writes:` and the table name to find documented writers; unlisted writers may exist.
- `reads remote:` a table in another database, schema, or service, whose schema this repository does not control.
- `writes remote:` a table in another database, schema, or service that code here writes; its schema is not under this repository's control.
- `calls:` external systems reached over the network, with the operations used. These fail, stall, and throttle independently of this code. Search for `calls:` and a system's name to find documented callers; unlisted callers may exist.
- `soft-ref out:` the named source column points at another table with no foreign key. A named validator is a verified check, not necessarily the only check or one used by every write. No validation clause makes no claim about validation.
- `soft-ref in:` the named source column points at the named local table with no foreign key. Deleting or re-keying rows can orphan those references.
- `transitions:` this file defines a stored state or performs a shown transition; the line points to its canonical diagram beside a source definition or in a named Markdown section. Labels name transition functions and conditions. An omitted edge does not establish a prohibition; a stated prohibition needs an explicit basis.
- `format:` the byte layout this file defines, encodes, or decodes, with its one full explanation above a named source definition/operation or at a Markdown section. The eligible definition owner and documented codecs point to the same layout; a definition-only file need not encode or decode it.
- `hazard:` something about this file's behavior to know before editing anything in it.
