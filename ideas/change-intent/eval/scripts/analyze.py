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
    """One trial per summary.json. A trial has a reward when a reward.json resolves to the same summary."""
    trials, unknown = [], []
    rewarded: dict[Path, dict] = {}
    for reward_path in sorted(root.rglob("reward.json")):
        try:
            reward = json.loads(reward_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            unknown.append(f"{reward_path}: unreadable reward.json")
            continue
        summary_path = find_summary(reward_path)
        if summary_path is None:
            unknown.append(f"{reward_path}: no summary.json next to it")
            continue
        rewarded[summary_path.resolve()] = reward
    for summary_path in sorted(root.rglob("summary.json")):
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            unknown.append(f"{summary_path}: unreadable summary.json")
            continue
        process = summary.get("process")
        if not process:
            unknown.append(f"{summary_path}: no process name")
            continue
        reward = rewarded.get(summary_path.resolve())
        trials.append({"process": process, "reward": reward, "summary": summary, "path": str(summary_path)})
    return trials, unknown


def is_per_protocol(summary: dict) -> bool:
    """Per-protocol = the author stage, if any, ended approved (frozen counts as approved)."""
    author = (summary.get("stages") or {}).get("author")
    return author is None or author.get("author_outcome") == "approved"


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

    def values(proc: str, dim: str, per_protocol: bool = False) -> list[float]:
        return [
            float(t["reward"][dim]) for t in by_proc[proc]
            if t["reward"] and isinstance(t["reward"].get(dim), (int, float)) and (not per_protocol or is_per_protocol(t["summary"]))
        ]

    def row(label: str, proc: str, per_protocol: bool) -> str:
        trials_ = [t for t in by_proc[proc] if not per_protocol or is_per_protocol(t["summary"])]
        n = len(trials_); miss = sum(1 for t in trials_ if not t["reward"])
        cells = []
        for d in DIMS_HEADLINE:
            v = values(proc, d, per_protocol)
            if not v:
                cells.append(f"{'-':>26}"); continue
            lo, hi = bootstrap_ci(v)
            sd = statistics.pstdev(v) if len(v) > 1 else 0.0
            cells.append(f"{statistics.mean(v):5.3f} ±{sd:5.3f} [{fmt(lo)},{fmt(hi)}]")
        return f"{label:30} {n:>3} {miss:>4}  " + "  ".join(cells)

    print("== headline (mean, sd, bootstrap 95% CI); ITT = every trial, PP = author stage approved or absent")
    print(f"{'process':30} {'n':>3} {'miss':>4}  " + "  ".join(f"{d:>26}" for d in DIMS_HEADLINE))
    for p in procs:
        print(row(p + "  [ITT]", p, False))
        print(row(p + "  [PP]", p, True))

    print(f"\n== differences vs {ref} (mean diff, bootstrap 95% CI)")
    for p in procs:
        if p == ref:
            continue
        cells = []
        for d in DIMS_HEADLINE:
            diff, lo, hi = diff_ci(values(p, d), values(ref, d))
            cells.append(f"{d}: {fmt(diff)} [{fmt(lo)},{fmt(hi)}]")
        print(f"{p:30} " + "  ".join(cells))

    print("\n== cost per stage (mean per trial) and author outcomes")
    print(f"{'process':30} {'stage':14} {'tokens_in':>10} {'tokens_out':>10} {'seconds':>8}")
    for p in procs:
        per_stage: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
        outcomes: dict[str, int] = defaultdict(int)
        for t in by_proc[p]:
            for name, st in (t["summary"].get("stages") or {}).items():
                u = st.get("usage") or {}
                acc = per_stage[name]
                acc[0] += u.get("input_tokens", 0) or 0; acc[1] += u.get("output_tokens", 0) or 0; acc[2] += st.get("seconds", 0) or 0
            a = (t["summary"].get("stages") or {}).get("author") or {}
            outcomes[a.get("author_outcome", "n/a")] += 1
        n = max(1, len(by_proc[p]))
        for name, (tin, tout, secs) in per_stage.items():
            print(f"{p:30} {name:14} {tin / n:10.0f} {tout / n:10.0f} {secs / n:8.0f}")
        print(f"{p:30} {'author outcomes':14} {dict(outcomes)}")

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
