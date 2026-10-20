# Fixed reviewer

The harness-owned reviewer that runs identically for every process version, after implementation,
in its own Copilot SDK session with read-only intent. It exists so that "how reviewable is the
output" is judged by something nobody in the experiment wrote for their own process.

Its instructions (`fixed_reviewer.md`) are assembled from published sources rather than written
fresh, and say so:

- Review dimensions: Google's engineering practices guide, "What to look for in a code review"
  (CC BY 3.0). https://google.github.io/eng-practices/review/reviewer/looking-for.html
- Reporting threshold: report only findings with confidence 0.8 or higher, no style or
  pre-existing issues, following the published Anthropic `pr-review-toolkit` code-reviewer agent.
- Output shape: findings with location, severity, and confidence, plus an overall correctness
  verdict with confidence, following OpenAI's published Codex code-review cookbook schema.
- Reviewability factors: description, size, coherence, from Ram, Sawant, Castelluccio, and
  Bacchelli, "What makes a code change easier to review", ESEC/FSE 2018, plus verifiability and
  clarity.

The schema is in `driver/run_process.py` (`REVIEW_SCHEMA`). The driver passes it as the SDK's
`response_schema`, asks once more for JSON only if the first answer does not parse, validates the
result, and saves it to `review.json` with the raw final message in `review_raw.md`. The reviewer
model must differ from the implementer's (`--reviewer-model`, or `EVAL_REVIEWER_MODEL` in Harbor
runs); the driver refuses a same-model reviewer unless told otherwise.

What the reviewer sees, and only this:

- the repository, checked out at the implementation commit, with workspace custom instructions
  (`AGENTS.md` and the like) turned off for the session and a read-only tool set (grep, glob,
  view, bash for running tests, no edit or create tools);
- a sealed temporary directory, outside the harness work directory, holding exactly two files:
  `diff.patch` and `change_description.md`. The description holds whatever the process produced to
  describe the change under a neutral heading: the artifact file, if there is one, and the
  implementer's final summary.

It is not given the dialogue log, the transcripts, or the process's own review. The harness's git
commit messages are condition-neutral (`eval: setup`, `eval: description document`,
`eval: implementation`), so `git log` does not name the condition. After the stage the working
tree is reset to the implementation commit and anything that moved is recorded. Reviewability is
judged with the description the process actually leaves behind; that is deliberate.

The reviewer is not the same thing as the change-intent **process review** (the review-guidance
instrument in `../mechanics`), which belongs to the process under test and runs only for
process versions that include a `review` stage. Both outputs are graded; see `tasks/*/tests/`.
