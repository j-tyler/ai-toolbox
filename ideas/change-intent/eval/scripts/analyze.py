#!/usr/bin/env python3
"""Summarise eval results, grouped by condition, with honest uncertainty.

    scripts/analyze.py runs/                       # local runs made by run_local.sh
    scripts/analyze.py ~/jobs/<job> [--ref baseline]

A trial is a summary.json; it has a reward when a reward.json resolves to the same summary. The
condition is (process, labels, frozen-intent hash): different frozen artifacts are never pooled.
Trials with a harness error, a driver that never finished, or no model calls in the implement stage
are INVALID and excluded from outcome tables (counted per condition). Trials whose fixed review is
missing are reported both ways: scored as 0 in `review` (as the verifier does) and excluded.

Differences against --ref come with a permutation p-value and a Welch t interval, and a warning
below 10 trials per arm: with one task and a handful of attempts, a bootstrap interval on the mean
is far too narrow (about one in five null comparisons would look significant at k=3).
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

DIMS_HEADLINE = ["reward", "correctness", "review", "handoff"]
CRITERIA_OF_INTEREST = [
    "hidden_tests_pass_fraction", "hidden_tests_all_pass", "existing_tests_still_pass", "agent_tests_pass",
    "reviewer_verdict_correct", "no_blocking_findings", "reviewability_score", "description_adequacy", "verified_claims_ratio",
]


def find_summary(reward_path: Path) -> Path | None:
    for base in [reward_path.parent, reward_path.parent.parent]:
        for rel in ("app/.eval/summary.json", "agent/eval/summary.json", ".eval/summary.json", "eval/summary.json"):
            cand = base / rel
            if cand.exists():
                return cand
    return None


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def flatten_criteria(details: dict | None) -> dict[str, float]:
    out: dict[str, float] = {}

    def walk(node):
        if not isinstance(node, dict):
            return
        if node.get("kind") == "group":
            for c in node.get("components", []):
                walk(c.get("detail"))
        else:
            for c in node.get("criteria", []):
                try:
                    out[c["name"]] = float(c["value"])
                except (KeyError, TypeError, ValueError):
                    pass
    for v in (details or {}).values():
        walk(v)
    return out


def condition_of(summary: dict) -> str:
    process = summary.get("process") or "?"
    labels = summary.get("labels") or {}
    parts = [process] + [f"{k}={v}" for k, v in sorted(labels.items())]
    src = ((summary.get("manifest") or {}).get("intent_source") or {}).get("sha256")
    if src:
        parts.append(f"intent={src[:8]}")
    return " ".join(parts)


def invalid_reason(summary: dict) -> str | None:
    if summary.get("harness_error"):
        return "harness_error"
    if summary.get("status") == "running":
        return "driver_never_finished"
    impl = (summary.get("stages") or {}).get("implement")
    if impl is None:
        return "no_implement_stage"
    if summary.get("backend") == "copilot" and not (impl.get("usage") or {}).get("model_calls"):
        return "no_model_calls"
    return None


def load_trials(root: Path) -> tuple[list[dict], list[str]]:
    trials, unknown = [], []
    rewarded: dict[Path, tuple[dict, dict | None]] = {}
    for reward_path in sorted(root.rglob("reward.json")):
        reward = load_json(reward_path)
        if reward is None:
            unknown.append(f"{reward_path}: unreadable reward.json"); continue
        summary_path = find_summary(reward_path)
        if summary_path is None:
            unknown.append(f"{reward_path}: no summary.json next to it"); continue
        details = load_json(reward_path.with_name(reward_path.stem + "-details.json")) or load_json(reward_path.parent / "reward-details.json")
        rewarded[summary_path.resolve()] = (reward, details)
    for summary_path in sorted(root.rglob("summary.json")):
        summary = load_json(summary_path)
        if not summary:
            unknown.append(f"{summary_path}: unreadable summary.json"); continue
        if not summary.get("process"):
            unknown.append(f"{summary_path}: no process name"); continue
        reward, details = rewarded.get(summary_path.resolve(), (None, None))
        fixed = (summary.get("stages") or {}).get("fixed_review") or {}
        trials.append({
            "condition": condition_of(summary), "process": summary["process"], "reward": reward,
            "criteria": flatten_criteria(details), "summary": summary, "path": str(summary_path),
            "invalid": invalid_reason(summary),
            "review_missing": bool(fixed.get("missing")) or (reward is not None and fixed.get("status") == "missing"),
        })
    return trials, unknown


def is_per_protocol(summary: dict) -> bool:
    author = (summary.get("stages") or {}).get("author")
    return author is None or author.get("author_outcome") == "approved"


def welch(a: list[float], b: list[float]) -> tuple[float, float, float]:
    """(diff, lo, hi) 95% Welch t interval; nan when either side has <2 values."""
    if len(a) < 2 or len(b) < 2:
        return (statistics.mean(a) - statistics.mean(b) if a and b else float("nan"), float("nan"), float("nan"))
    ma, mb = statistics.mean(a), statistics.mean(b)
    va, vb = statistics.variance(a), statistics.variance(b)
    se = math.sqrt(va / len(a) + vb / len(b))
    if se == 0:
        return ma - mb, ma - mb, ma - mb
    df = (va / len(a) + vb / len(b)) ** 2 / ((va / len(a)) ** 2 / (len(a) - 1) + (vb / len(b)) ** 2 / (len(b) - 1))
    t = _t_quantile(df)
    return ma - mb, ma - mb - t * se, ma - mb + t * se


def _t_quantile(df: float) -> float:
    table = [(1, 12.706), (2, 4.303), (3, 3.182), (4, 2.776), (5, 2.571), (6, 2.447), (8, 2.306), (10, 2.228),
             (15, 2.131), (20, 2.086), (30, 2.042), (60, 2.000), (1e9, 1.960)]
    for d, q in table:
        if df <= d:
            return q
    return 1.96


def permutation_p(a: list[float], b: list[float], n: int = 5000, seed: int = 0) -> float:
    if not a or not b:
        return float("nan")
    observed = abs(statistics.mean(a) - statistics.mean(b))
    pool = a + b
    k = len(a)
    if len(pool) <= 12:  # exact enumeration when small
        combos = list(itertools.combinations(range(len(pool)), k))
        hits = 0
        for idx in combos:
            sa = [pool[i] for i in idx]; sb = [pool[i] for i in range(len(pool)) if i not in idx]
            if abs(statistics.mean(sa) - statistics.mean(sb)) >= observed - 1e-12:
                hits += 1
        return hits / len(combos)
    rng = random.Random(seed); hits = 0
    for _ in range(n):
        rng.shuffle(pool)
        if abs(statistics.mean(pool[:k]) - statistics.mean(pool[k:])) >= observed - 1e-12:
            hits += 1
    return hits / n


def fmt(x: float) -> str:
    return "  nan " if x != x else f"{x:6.3f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="runs")
    ap.add_argument("--ref", help="reference process for differences (default: alphabetically first condition)")
    args = ap.parse_args()
    trials, unknown = load_trials(Path(args.root))
    if not trials:
        print(f"no trials under {args.root}")
        for u in unknown:
            print("  skipped:", u)
        return 1

    by_cond: dict[str, list[dict]] = defaultdict(list)
    for t in trials:
        by_cond[t["condition"]].append(t)
    conds = sorted(by_cond)
    ref = next((c for c in conds if c == args.ref or c.split(" ")[0] == args.ref), None) or conds[0]

    def valid(c: str, pp: bool = False, drop_missing_review: bool = False) -> list[dict]:
        return [t for t in by_cond[c] if not t["invalid"] and t["reward"]
                and (not pp or is_per_protocol(t["summary"])) and (not drop_missing_review or not t["review_missing"])]

    def vals(ts: list[dict], dim: str) -> list[float]:
        return [float(t["reward"][dim]) for t in ts if isinstance(t["reward"].get(dim), (int, float))]

    print("== trials per condition")
    print(f"{'condition':44} {'n':>3} {'valid':>5} {'invalid':>7} {'no_reward':>9} {'review_missing':>14}  invalid reasons")
    for c in conds:
        ts = by_cond[c]
        inv = [t["invalid"] for t in ts if t["invalid"]]
        print(f"{c:44} {len(ts):>3} {len(valid(c)):>5} {len(inv):>7} {sum(1 for t in ts if not t['invalid'] and not t['reward']):>9} "
              f"{sum(1 for t in valid(c) if t['review_missing']):>14}  {dict((r, inv.count(r)) for r in set(inv))}")

    small = any(len(valid(c)) < 10 for c in conds)
    print("\n== headline (mean ± sd), valid trials only. ITT = every valid trial; PP = author approved or absent; XR = missing fixed review excluded")
    if small:
        print("   WARNING: fewer than 10 valid trials in some arm; treat every difference below as a pilot estimate, not a result.")
    print(f"{'condition':44} {'n':>3}  " + "  ".join(f"{d:>16}" for d in DIMS_HEADLINE))
    for c in conds:
        for tag, ts in (("ITT", valid(c)), ("PP", valid(c, pp=True)), ("XR", valid(c, drop_missing_review=True))):
            cells = []
            for d in DIMS_HEADLINE:
                v = vals(ts, d)
                cells.append(f"{statistics.mean(v):6.3f} ±{(statistics.pstdev(v) if len(v) > 1 else 0.0):5.3f}" if v else f"{'-':>16}")
            print(f"{c + '  [' + tag + ']':44} {len(ts):>3}  " + "  ".join(cells))

    print(f"\n== differences vs {ref} (valid, ITT): mean diff, Welch 95% interval, permutation p")
    for c in conds:
        if c == ref:
            continue
        cells = []
        for d in DIMS_HEADLINE:
            a, b = vals(valid(c), d), vals(valid(ref), d)
            diff, lo, hi = welch(a, b)
            cells.append(f"{d}: {fmt(diff)} [{fmt(lo)},{fmt(hi)}] p={permutation_p(a, b):.3f}")
        print(f"{c:44} " + "  ".join(cells))

    print("\n== decomposition: mean of individual criteria (valid, ITT), so a review win and a code win can be told apart")
    present = [k for k in CRITERIA_OF_INTEREST if any(k in t["criteria"] for ts in by_cond.values() for t in ts)]
    if present:
        print(f"{'condition':44} " + " ".join(f"{k[:14]:>14}" for k in present))
        for c in conds:
            ts = valid(c)
            cells = []
            for k in present:
                v = [t["criteria"][k] for t in ts if k in t["criteria"]]
                cells.append(f"{statistics.mean(v):14.3f}" if v else f"{'-':>14}")
            print(f"{c:44} " + " ".join(cells))
    else:
        print("   (no reward-details.json found next to the rewards)")

    print("\n== code-only diff size, cost per stage (mean per valid trial), author outcomes, model mismatches")
    for c in conds:
        ts = valid(c)
        if not ts:
            continue
        per_stage: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
        outcomes: dict[str, int] = defaultdict(int)
        mism: set[str] = set()
        sizes = []
        for t in ts:
            for name, st in (t["summary"].get("stages") or {}).items():
                u = st.get("usage") or {}
                acc = per_stage[name]
                acc[0] += u.get("input_tokens", 0) or 0; acc[1] += u.get("output_tokens", 0) or 0; acc[2] += st.get("seconds", 0) or 0
            a = (t["summary"].get("stages") or {}).get("author") or {}
            outcomes[a.get("author_outcome", "n/a")] += 1
            mism |= set(t["summary"].get("model_mismatch_any") or [])
            sizes.append(t["summary"].get("diff_shortstat_code_only", ""))
        n = len(ts)
        for name, (tin, tout, secs) in per_stage.items():
            print(f"{c:44} {name:14} in={tin / n:9.0f} out={tout / n:9.0f} s={secs / n:7.0f}")
        print(f"{c:44} author outcomes {dict(outcomes)}; model mismatches {sorted(mism) or 'none'}; e.g. diff: {sizes[0]}")

    if unknown:
        print("\n== skipped")
        for u in unknown:
            print("  ", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
