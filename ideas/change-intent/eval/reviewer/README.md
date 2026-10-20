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

- a **synthetic review repository**: a fresh git repository with two commits by a neutral author,
  `base` (the seed tree) and `change` (the implementation tree with the intent directory removed
  and `AGENTS.md` as it was at the seed, or absent). It contains no `.eval`, no harness commit
  messages and no process files, so nothing in the checkout or its history identifies the arm.
  Workspace custom instructions are off for the session, built-in sub-agents, session store and
  memory are off, and the tool set is read-only (grep, glob, view, bash for running tests, no
  edit or create tools); edits the reviewer makes anyway are recorded as `reviewer_edits` and
  discarded;
- a sealed temporary directory, outside the harness work directory, holding exactly three files:
  `requirements.md` (the brief, the same for every condition, and the standard for correctness),
  `diff.patch` (the code change, with the artifact file excluded), and `change_description.md`
  (whatever the process produced to describe the change under a neutral heading: the artifact, if
  there is one, and every turn of the implementer's summary). The description is rated for
  adequacy; correctness is never judged against it.

It is not given the dialogue log, the transcripts, the process's own review, or the real
workspace. The process directory is renamed out of reach for the duration, and tool calls that
mention paths outside the review repository and the sealed directory are recorded as
`out_of_bounds_reads`. The review repository is deleted after the stage; `summary.json` records
its tree hash so it can be rebuilt (`build_review_repo` in the driver) for a re-review.

What this blinding does **not** remove: the content of `change_description.md`. A change-intent
arm's description is the intent plus the implementer's turn summaries; the baseline's is the
summaries alone. A reviewer that reads a change-intent-shaped document knows it is reading one, and
its adequacy rating is meant to respond to that content. Correctness is judged against
`requirements.md` so that this content-level difference cannot move the verdict standard, and
`verified_claims_ratio` is a ratio so a sparser description does not win by claiming less. The
remaining influence of description content on the review dimension is the thing under test, and
the reason the review dimension is exploratory rather than primary.

An answer that does not parse or validate gets one "JSON only" follow-up, then up to two fresh
sessions; if it is still missing, `review.json` records a missing review and the verifier scores
the review dimension 0 for that trial while `analyze.py` also reports the headline with missing
reviews excluded. `scripts/rerun_fixed_review.py` re-reviews a saved trial for test-retest.

The reviewer is not the same thing as the change-intent **process review** (the review-guidance
instrument in `../mechanics`), which belongs to the process under test and runs only for
process versions that include a `review` stage. Both outputs are graded; see `tasks/*/tests/`.
