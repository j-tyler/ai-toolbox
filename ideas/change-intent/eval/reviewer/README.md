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
`response_schema`, saves the parsed result to `.eval/review.json`, and the raw final message to
`.eval/review_raw.md`. The reviewer model is pinned separately from the implementer
(`--reviewer-model`, or `EVAL_REVIEWER_MODEL` in Harbor runs) so it can come from a different
vendor.

What the reviewer sees is the repository after the change plus `.eval/change_description.md`,
which holds whatever the process produced to describe the change: the approved intent file for
change-intent processes, the implementer's final summary for the baseline. That is deliberate:
reviewability is judged with the description the process actually leaves behind.

The reviewer is not the same thing as the change-intent **process review** (the review-guidance
instrument in `../mechanics`), which belongs to the process under test and runs only for
process versions that include a `review` stage. Both outputs are graded; see `tasks/*/tests/`.
