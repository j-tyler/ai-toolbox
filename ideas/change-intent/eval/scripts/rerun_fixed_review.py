#!/usr/bin/env python3
"""Re-run the fixed reviewer on a saved trial, for test-retest of the judge.

    scripts/rerun_fixed_review.py runs/<trial>/app --reviewer-model <model from another vendor> [--out dir] [--repeat 3]

Uses the trial's own review-input/ (requirements.md, diff.patch, change_description.md) and its
workspace at the implementation commit, with the same reviewer instructions and schema the driver
uses. Writes review-rerun-<n>.json next to the other artifacts (or into --out). Comparing these to
review.json across several reruns gives the judge's test-retest agreement, which the write-up
should report before any review-dimension difference is interpreted.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "driver"))

from backends import CopilotBackend, StageSpec  # noqa: E402
from run_process import (FIXED_REVIEW_PROMPT, FIXED_REVIEWER_PROMPT_PATH, JSON_ONLY_RETRY, REVIEW_SCHEMA,  # noqa: E402
                         git_reset_to, parse_review_json, sh, validate_review)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", help="the trial's app/ directory (a git repo at the implementation commit)")
    ap.add_argument("--reviewer-model", required=True)
    ap.add_argument("--out", help="directory for review-rerun-N.json (default: <workspace>/.eval)")
    ap.add_argument("--repeat", type=int, default=1)
    args = ap.parse_args()
    ws = Path(args.workspace).resolve()
    out = Path(args.out).resolve() if args.out else ws / ".eval"
    review_input = out / "review-input"
    if not (review_input / "requirements.md").exists():
        raise SystemExit(f"{review_input} does not hold the saved reviewer inputs")
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    impl_commit = summary["impl_commit"]
    git_reset_to(ws, impl_commit)
    backend = CopilotBackend(args.reviewer_model)

    async def noop(_m: str) -> str | None:
        return None

    async def on_user_input(q: str, c):
        return ("Your call.", True)

    try:
        for n in range(1, args.repeat + 1):
            retried = {"n": 0}

            async def next_turn(message: str) -> str | None:
                if parse_review_json(message) is None and retried["n"] == 0:
                    retried["n"] += 1
                    return JSON_ONLY_RETRY
                return None

            res = await backend.run_stage(
                StageSpec("fixed_review", FIXED_REVIEW_PROMPT.format(review_input=review_input),
                          system_append=FIXED_REVIEWER_PROMPT_PATH.read_text(encoding="utf-8"), custom_instructions=False,
                          read_only=True, response_schema=REVIEW_SCHEMA, model=args.reviewer_model,
                          extra_dirs=[str(review_input)], max_turns=2),
                ws, on_user_input=on_user_input, next_turn=next_turn,
            )
            review = parse_review_json(res.final_message)
            problems = validate_review(review) if review is not None else ["unparseable"]
            record = review if review is not None and not problems else {"_meta": {"valid": False, "problems": problems}}
            record.setdefault("_meta", {}).update({"valid": not problems, "reviewer_model": res.resolved_model or args.reviewer_model, "rerun": n})
            (out / f"review-rerun-{n}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            git_reset_to(ws, impl_commit)
            print(f"rerun {n}: valid={not problems} verdict={record.get('overall_correctness')} findings={len(record.get('findings', []) or [])}")
    finally:
        await backend.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
