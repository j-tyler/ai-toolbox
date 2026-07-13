# Review Guidance

**Status: drafted.**

[design.md](../design.md) states what the review pass checks. This file is what a team adds to its own review instructions — a prompt, a skill, a pipeline step — so the reviewing agent knows the repository uses change intents and what that changes about its job. It is deliberately not a procedure: how review runs, in what order, and where findings go are the team's decisions, already made. Copy the block below into your review instructions and shape the wording to your process.

---

## Change intent: what it changes about your review

This repository uses change intents. Every pull request carries one intent file at `change-intent/YYYY-MM-DD-short-slug.md`, authored before any code was written. The intent is the contract for the change: the code was written to satisfy it, and your review checks that it did. You are not reviewing the diff alone — you are reviewing the diff against its intent, and hunting for whatever the intent does not cover. If a pull request has no intent file, this section does not apply: review it under your normal instructions and flag the missing intent as a process defect.

You are also the first check with no stake in the change. The implementing agent wrote the code, wrote the tests that prove its claims, and worked until its own checks passed — so the change will arrive looking finished, and your prior will be to confirm it. The goal is the opposite: find the claim that does not hold. Finding nothing is a legitimate result — report it as what you verified and how, never as a bare approval.

### The intent file, from the review seat

- **Outcomes** — the results the author wanted. Not verified at review; your judgment call is whether the claims below plausibly deliver them.
- **Why** — the author's reasoning. It directs your attention; it is not a checklist.
- **Acceptance criteria** — falsifiable scenarios. A criterion is met only by a test in this diff that passes and that would fail if the behavior broke; a test that cannot fail proves nothing. Establish that by reading the test's assertions against the claim — or, when you can run code, by breaking the behavior and watching the test fail. Record a verdict per criterion: `met`, `not met`, or `cannot verify` with what stopped you. The verdict list belongs in your review's summary; `not met` is a finding like any other, and whether `cannot verify` blocks the change is your team's call. An honest `cannot verify` always beats a hopeful `met`.
- **Invariants** — properties spanning many sites ("across all caller paths…"). No single test closes one. Enumerate the sites where the property could break yourself, before reading the implementation's own account of them, and confirm the property at each. A site on their list and not yours, or on yours and not theirs, is a finding either way.
- **Out of scope** — decisions, not oversights. Never flag a listed item as missing work. An exclusion waives missing work only: a defect in code this change ships — a security hole, a correctness bug — is a finding no matter what list its subject appears on.
- **Amendments** — repairs made to the intent during implementation: a dated entry per repair in the Amendments section, and a marked discovery note on each changed claim. Each is a judgment call no one has reviewed yet, at a spot where the intent already proved wrong once; read them hardest. The record must hold together: every entry names a discovered fact about the system (not an activity), every changed claim carries its note, every note has its entry, and a relaxed claim has its deferral under Out of scope.

### Rules that follow

- **Account for the diff's observable behavior.** Everything the change makes visible to a caller, user, or operator — `[your agents file names the observable channels, e.g., API shapes, persisted formats, named metrics and log events]` — is covered by a claim or an out-of-scope entry. Behavior you cannot account for is a finding even when the code behind it is good — the remedy is not to discard good work but to move it to its own change, with its own intent.
- **Read the code diff before the intent when your process allows it** — skip the intent file and the pull request description on that first pass. The intent's claims anchor; a cold read of the code is your one chance at an open-ended sweep. A cold-read finding that the intent genuinely answers — a recorded decision, a listed exclusion — is closed by pointing to that answer; the rest stand, however fluently the change explains itself. Closing is not endorsing: a recorded decision that looks wrong or dangerous is itself a finding, raised against the intent.
- **Check the intent as well as the code.** Claims too vague to check are a blocking finding on their own: whatever the code looks like, the review cannot certify a change against a contract that cannot carry the check.
- **Use the folder as memory, not as truth.** Prior intents in `change-intent/` record what was decided when they merged, not what necessarily holds now. When this change quietly cuts against a recorded decision, raise it — and verify the current behavior against the code, never against the old intent alone.
- **Your existing review still runs in full.** Security, concurrency, error handling, clarity — everything you check today, you keep checking. The intent tells you where to look harder; it never shrinks the job. If the change is too large to do both well, say that — a change too large to review against its claims is itself a finding — and when something must give, give up mechanical verification honestly (`cannot verify`) before you give up the open-ended read: the open read is the only part that catches what nobody claimed.
