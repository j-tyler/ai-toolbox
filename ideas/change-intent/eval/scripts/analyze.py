#!/usr/bin/env python3
"""Summarise eval results into one table, grouped by process, with bootstrap intervals.

    scripts/analyze.py runs/                      # local runs made by run_local.sh
    scripts/analyze.py ~/jobs/<job> [--ref baseline]

Each trial is a reward.json plus the driver's summary.json. The process name comes from
summary.json (never from directory names). Trials whose process cannot be determined are listed
and excluded, not merged. Output:

  per process      n, trials missing a reward, mean +/- sd and bootstrap 95% CI per reward dimension
  per process      per-stage tokens and seconds, author outcomes (intention-to-treat vs per-protocol)
  differences      every process minus --ref (default: alphabetically first), with bootstrap CI
  diagnostics      reported separately from the headline reward

With one task and few trials the intervals are wide; that is the point of printing them.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

DIMS_HEADLINE = ["reward", "correctness", "review", "handoff"]
DIMS_DIAG = ["diagnostics"]


def find_summary(reward_path: Path) -> Path | None:
    # local: runs/<ts>-<p>/reward.json with app/.eval/summary.json
    # harbor: <trial>/verifier/reward.json with <trial>/agent/eval/summary.json
    for base in [reward_path.parent, reward_path.parent.parent]:
        for rel in ("app/.eval/summary.json", "agent/eval/summary.json", ".eval/summary.json", "eval/summary.json"):
            cand = base / rel
            if cand.exists():
                return cand
    return None


def load_trials(root: Path) -> tuple[list[dict], list[str]]:
    trials, unknown = [], []
    for reward_path in sorted(root.rglob("reward.json")):
        try:
            reward = json.loads(reward_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            unknown.append(f"{reward_path}: unreadable reward.json")
            continue
        summary_path = find_summary(reward_path)
        summary = {}
        if summary_path:
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        process = summary.get("process")
        if not process:
            unknown.append(f"{reward_path}: no summary.json with a process name")
            continue
        trials.append({"process": process, "reward": reward, "summary": summary, "path": str(reward_path)})
    # trials that ran but never got a reward (harness failure)
    for summary_path in sorted(root.rglob("summary.json")):
        if not any(t["summary"] is not None and str(summary_path).startswith(str(Path(t["path"]).parent.parent)) for t in trials):
            try:
                s = json.loads(summary_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if s.get("process") and not any(Path(t["path"]).parent in summary_path.parents for t in trials):
                trials.append({"process": s["process"], "reward": None, "summary": s, "path": str(summary_path)})
    return trials, unknown


def bootstrap_ci(values: list[float], n: int = 2000, seed: int = 0) -> tuple[float, float]:
    if len(values) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    means = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


def diff_ci(a: list[float], b: list[float], n: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    if not a or not b:
        return (float("nan"),) * 3
    rng = random.Random(seed)
    d = statistics.mean(a) - statistics.mean(b)
    diffs = sorted(statistics.mean(rng.choices(a, k=len(a))) - statistics.mean(rng.choices(b, k=len(b))) for _ in range(n))
    return d, diffs[int(0.025 * n)], diffs[int(0.975 * n)]


def fmt(x: float) -> str:
    return "  nan " if x != x else f"{x:6.3f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="runs")
    ap.add_argument("--ref", help="reference process for differences (default: alphabetically first)")
    args = ap.parse_args()
    trials, unknown = load_trials(Path(args.root))
    if not trials:
        print(f"no gradable trials under {args.root}")
        for u in unknown:
            print("  skipped:", u)
        return 1

    by_proc: dict[str, list[dict]] = defaultdict(list)
    for t in trials:
        by_proc[t["process"]].append(t)
    procs = sorted(by_proc)
    ref = args.ref or procs[0]

    def values(proc: str, dim: str) -> list[float]:
        return [float(t["reward"][dim]) for t in by_proc[proc] if t["reward"] and isinstance(t["reward"].get(dim), (int, float))]

    print("== headline (mean, sd, bootstrap 95% CI)")
    print(f"{'process':30} {'n':>3} {'miss':>4}  " + "  ".join(f"{d:>26}" for d in DIMS_HEADLINE))
    for p in procs:
        n = len(by_proc[p]); miss = sum(1 for t in by_proc[p] if not t["reward"])
        cells = []
        for d in DIMS_HEADLINE:
            v = values(p, d)
            if not v:
                cells.append(f"{'-':>26}"); continue
            lo, hi = bootstrap_ci(v)
            sd = statistics.pstdev(v) if len(v) > 1 else 0.0
            cells.append(f"{statistics.mean(v):5.3f} ±{sd:5.3f} [{fmt(lo)},{fmt(hi)}]")
        print(f"{p:30} {n:>3} {miss:>4}  " + "  ".join(cells))

    print(f"\n== differences vs {ref} (mean diff, bootstrap 95% CI)")
    for p in procs:
        if p == ref:
            continue
        cells = []
        for d in DIMS_HEADLINE:
            diff, lo, hi = diff_ci(values(p, d), values(ref, d))
            cells.append(f"{d}: {fmt(diff)} [{fmt(lo)},{fmt(hi)}]")
        print(f"{p:30} " + "  ".join(cells))

    print("\n== cost and author outcome")
    print(f"{'process':30} {'tokens_in':>10} {'tokens_out':>10} {'seconds':>8}  author outcomes (ITT counts; per-protocol = approved only)")
    for p in procs:
        tin = tout = secs = 0.0; outcomes: dict[str, int] = defaultdict(int)
        for t in by_proc[p]:
            for name, st in (t["summary"].get("stages") or {}).items():
                u = st.get("usage") or {}
                tin += u.get("input_tokens", 0) or 0; tout += u.get("output_tokens", 0) or 0; secs += st.get("seconds", 0) or 0
            a = (t["summary"].get("stages") or {}).get("author") or {}
            outcomes[a.get("author_outcome", "n/a")] += 1
        n = max(1, len(by_proc[p]))
        print(f"{p:30} {tin / n:10.0f} {tout / n:10.0f} {secs / n:8.0f}  {dict(outcomes)}")

    print("\n== diagnostics (not in the headline reward)")
    for p in procs:
        v = values(p, "diagnostics")
        print(f"{p:30} diagnostics: {statistics.mean(v):.3f} (n={len(v)})" if v else f"{p:30} diagnostics: -")

    if unknown:
        print("\n== skipped")
        for u in unknown:
            print("  ", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
