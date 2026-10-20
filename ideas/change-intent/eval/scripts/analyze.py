#!/usr/bin/env python3
"""Summarise eval results, grouped by condition, with honest uncertainty.

    scripts/analyze.py runs/                       # local runs made by run_local.sh
    scripts/analyze.py ~/jobs/<job> [--ref baseline]

A trial is a summary.json; it has a reward when a reward.json resolves to the same summary. The
condition is (process, labels, frozen-intent hash, model, reviewer model, brief hash): trials that
differ in any of these are never pooled. Within a condition the process files, harness commit,
stand-in and dirty flag must agree; a mixed condition stops the analysis unless --allow-mixed.

Trials with a harness error, a driver that never finished, no model calls in the implement stage,
or a model mismatch (a stage served by a model other than the one requested; --keep-model-mismatch
keeps them) are INVALID and excluded from outcome tables (counted per condition). Trials whose
fixed review is missing are reported both ways: scored as 0 in `review` (as the verifier does, ITT)
and excluded (XR).

Primary endpoint: correctness (hidden tests). The headline reward, review and handoff are
secondary or exploratory. Differences against --ref come with a permutation p-value, a Welch t
interval, the smallest p the arm sizes can attain, and the minimum detectable effect. With one task
and a handful of attempts these are pilot estimates: at k=3 the smallest two-sided permutation p is
0.10 and the detectable effect is about three standard deviations.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

PRIMARY = "correctness"
DIMS_HEADLINE = ["correctness", "reward", "review", "handoff"]
DIM_ROLE = {"correctness": "primary", "reward": "secondary", "review": "exploratory", "handoff": "exploratory"}
CRITERIA_OF_INTEREST = [
    "hidden_tests_pass_fraction", "hidden_tests_all_pass", "existing_tests_still_pass", "agent_tests_pass",
    "reviewer_verdict_correct", "no_blocking_findings", "reviewability_score", "description_adequacy", "verified_claims_ratio",
]
# Fields that must agree inside one condition for the pooled trials to be comparable.
HOMOGENEITY_FIELDS = ("process_files_digest", "harness_git_sha", "stand_in", "stand_in_model", "harness_dirty")


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
    """Everything that defines an experimental condition; two trials pool only if this matches."""
    manifest = summary.get("manifest") or {}
    process = summary.get("process") or "?"
    labels = summary.get("labels") or {}
    parts = [process] + [f"{k}={v}" for k, v in sorted(labels.items())]
    src = (manifest.get("intent_source") or {}).get("sha256")
    if src:
        parts.append(f"artifact={src[:8]}")
    if manifest.get("model"):
        parts.append(f"model={manifest['model']}")
    if manifest.get("reviewer_model") and manifest.get("reviewer_model") != manifest.get("model"):
        parts.append(f"reviewer={manifest['reviewer_model']}")
    if manifest.get("brief_sha256"):
        parts.append(f"brief={manifest['brief_sha256'][:8]}")
    return " ".join(parts)


def homogeneity_key(summary: dict) -> dict:
    manifest = summary.get("manifest") or {}
    files = manifest.get("process_files") or {}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:12] if files else None
    return {
        "process_files_digest": digest,
        "harness_git_sha": (manifest.get("harness_git_sha") or "")[:12] or None,
        "stand_in": manifest.get("stand_in"),
        "stand_in_model": manifest.get("stand_in_model"),
        "harness_dirty": manifest.get("harness_dirty"),
    }


def heterogeneity(trials: list[dict]) -> list[str]:
    """Human-readable reasons a set of same-condition trials should not be pooled."""
    problems = []
    for field in HOMOGENEITY_FIELDS:
        values = {json.dumps(t["homogeneity"].get(field)) for t in trials}
        if field == "harness_dirty":
            if any(t["homogeneity"].get(field) for t in trials):
                problems.append("harness_dirty=true in some trial (uncommitted harness changes)")
        elif len(values) > 1:
            problems.append(f"{field} varies: {sorted(values)}")
    return problems


def invalid_reason(summary: dict, keep_model_mismatch: bool = False) -> str | None:
    if summary.get("harness_error"):
        return "harness_error"
    if summary.get("status") == "running":
        return "driver_never_finished"
    impl = (summary.get("stages") or {}).get("implement")
    if impl is None:
        return "no_implement_stage"
    if summary.get("backend") == "copilot" and not (impl.get("usage") or {}).get("model_calls"):
        return "no_model_calls"
    if summary.get("model_mismatch_any") and not keep_model_mismatch:
        return "model_mismatch"
    return None


def load_trials(root: Path, keep_model_mismatch: bool = False) -> tuple[list[dict], list[str]]:
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
            "invalid": invalid_reason(summary, keep_model_mismatch),
            "homogeneity": homogeneity_key(summary),
            "review_missing": bool(fixed.get("missing")) or (reward is not None and fixed.get("status") == "missing"),
        })
    return trials, unknown


def is_per_protocol(summary: dict) -> bool:
    author = (summary.get("stages") or {}).get("author")
    return author is None or author.get("author_outcome") == "approved"


# Two-sided 97.5% Student t quantiles. _t_quantile picks the entry for the largest tabulated df at or
# below the actual df, so the interval is never narrower than the exact one.
_T_TABLE = [(1, 12.706), (2, 4.303), (3, 3.182), (4, 2.776), (5, 2.571), (6, 2.447), (7, 2.365), (8, 2.306),
            (9, 2.262), (10, 2.228), (12, 2.179), (15, 2.131), (20, 2.086), (25, 2.060), (30, 2.042),
            (40, 2.021), (60, 2.000), (120, 1.980), (1e9, 1.960)]


def _t_quantile(df: float) -> float:
    if df < 1:
        return _T_TABLE[0][1]
    q = _T_TABLE[0][1]
    for d, val in _T_TABLE:
        if d <= df:
            q = val
        else:
            break
    return q


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


def min_permutation_p(na: int, nb: int) -> float:
    """Smallest two-sided p an exact permutation test can report for these arm sizes."""
    if na == 0 or nb == 0:
        return float("nan")
    total = math.comb(na + nb, na)
    return 2 / total if total else float("nan")  # the extreme split and its mirror


def minimum_detectable_effect(a: list[float], b: list[float]) -> float:
    """Approximate MDE for 80% power at two-sided 5%: (t_crit + 0.84) * pooled_sd * sqrt(1/na + 1/nb)."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    pooled = math.sqrt(((len(a) - 1) * statistics.variance(a) + (len(b) - 1) * statistics.variance(b)) / (len(a) + len(b) - 2))
    return (_t_quantile(len(a) + len(b) - 2) + 0.84) * pooled * math.sqrt(1 / len(a) + 1 / len(b))


def fmt(x: float) -> str:
    return "  nan " if x != x else f"{x:6.3f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="runs")
    ap.add_argument("--ref", help="reference process for differences (default: alphabetically first condition)")
    ap.add_argument("--allow-mixed", action="store_true", help="report even when a condition pools trials from different harness/process versions")
    ap.add_argument("--keep-model-mismatch", action="store_true", help="keep trials where a stage was served by a model other than the one requested")
    args = ap.parse_args()
    trials, unknown = load_trials(Path(args.root), keep_model_mismatch=args.keep_model_mismatch)
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
    width = max(44, min(96, max(len(c) for c in conds) + 8))

    mixed = {c: heterogeneity(by_cond[c]) for c in conds if heterogeneity(by_cond[c])}
    if mixed:
        print("== HETEROGENEOUS CONDITIONS: these trials were not produced by one harness/process version and must not be pooled")
        for c, problems in mixed.items():
            for p in problems:
                print(f"   {c}: {p}")
        if not args.allow_mixed:
            print("   stopping; rerun with --allow-mixed to report anyway, or split the runs by version with --label")
            return 2
        print("   --allow-mixed given; the tables below pool them anyway\n")

    def valid(c: str, pp: bool = False, drop_missing_review: bool = False) -> list[dict]:
        return [t for t in by_cond[c] if not t["invalid"] and t["reward"]
                and (not pp or is_per_protocol(t["summary"])) and (not drop_missing_review or not t["review_missing"])]

    def vals(ts: list[dict], dim: str) -> list[float]:
        return [float(t["reward"][dim]) for t in ts if isinstance(t["reward"].get(dim), (int, float))]

    print(f"primary endpoint: {PRIMARY} (hidden tests). reward is secondary; review and handoff are exploratory.\n")
    print("== trials per condition")
    print(f"{'condition':{width}} {'n':>3} {'valid':>5} {'invalid':>7} {'no_reward':>9} {'review_missing':>14}  invalid reasons")
    for c in conds:
        ts = by_cond[c]
        inv = [t["invalid"] for t in ts if t["invalid"]]
        n_valid = len(valid(c))
        missing = sum(1 for t in valid(c) if t["review_missing"])
        rate = f"{missing}/{n_valid}" if n_valid else "-"
        print(f"{c:{width}} {len(ts):>3} {n_valid:>5} {len(inv):>7} {sum(1 for t in ts if not t['invalid'] and not t['reward']):>9} "
              f"{rate:>14}  {dict((r, inv.count(r)) for r in set(inv))}")

    small = any(len(valid(c)) < 10 for c in conds)
    print("\n== headline (mean ± sd), valid trials only.")
    print("   ITT = every valid trial (missing fixed review scored 0, as the verifier does)")
    print("   XR  = missing fixed review excluded")
    print("   PP  = biased: selects on post-treatment authoring success in one arm; sensitivity only")
    if small:
        print("   WARNING: fewer than 10 valid trials in some arm; treat every difference below as a pilot estimate, not a result.")
    print(f"{'condition':{width}} {'n':>3}  " + "  ".join(f"{d + ' (' + DIM_ROLE[d][:4] + ')':>18}" for d in DIMS_HEADLINE))
    for c in conds:
        for tag, ts in (("ITT", valid(c)), ("XR", valid(c, drop_missing_review=True)), ("PP", valid(c, pp=True))):
            cells = []
            for d in DIMS_HEADLINE:
                v = vals(ts, d)
                cells.append(f"{statistics.mean(v):8.3f} ±{(statistics.pstdev(v) if len(v) > 1 else 0.0):5.3f}" if v else f"{'-':>18}")
            print(f"{c + '  [' + tag + ']':{width}} {len(ts):>3}  " + "  ".join(cells))

    print(f"\n== differences vs {ref} (valid, ITT): mean diff, Welch 95% interval, permutation p")
    print("   min p = smallest two-sided p attainable for these arm sizes; MDE = effect detectable with 80% power at 5%")
    for c in conds:
        if c == ref:
            continue
        na, nb = len(valid(c)), len(valid(ref))
        print(f"{c:{width}} n={na} vs {nb}; min p={min_permutation_p(na, nb):.3f}")
        for d in DIMS_HEADLINE:
            a, b = vals(valid(c), d), vals(valid(ref), d)
            diff, lo, hi = welch(a, b)
            print(f"{'':{width}}   {d:12} ({DIM_ROLE[d]:11}) {fmt(diff)} [{fmt(lo)},{fmt(hi)}] p={permutation_p(a, b):.3f}  MDE={fmt(minimum_detectable_effect(a, b))}")

    print("\n== decomposition: mean of individual criteria (valid, ITT), so a review win and a code win can be told apart")
    present = [k for k in CRITERIA_OF_INTEREST if any(k in t["criteria"] for ts in by_cond.values() for t in ts)]
    if present:
        print(f"{'condition':{width}} " + " ".join(f"{k[:14]:>14}" for k in present))
        for c in conds:
            ts = valid(c)
            cells = []
            for k in present:
                v = [t["criteria"][k] for t in ts if k in t["criteria"]]
                cells.append(f"{statistics.mean(v):14.3f}" if v else f"{'-':>14}")
            print(f"{c:{width}} " + " ".join(cells))
    else:
        print("   (no reward-details.json found next to the rewards)")

    print("\n== reviewer calibration (valid, XR): does the fixed reviewer's verdict track the hidden tests?")
    print("   P(verdict correct) and P(no blocking findings) split by whether every hidden test passed; mean(review - correctness)")
    print(f"{'condition':{width}} {'all_pass':>8} {'n':>3} {'P(verdict ok)':>13} {'P(no block)':>11}   {'mean(rev-corr)':>14}")
    for c in conds:
        ts = [t for t in valid(c, drop_missing_review=True) if "hidden_tests_all_pass" in t["criteria"]]
        for flag in (1.0, 0.0):
            grp = [t for t in ts if t["criteria"]["hidden_tests_all_pass"] == flag]
            if not grp:
                continue
            pv = [t["criteria"].get("reviewer_verdict_correct") for t in grp if "reviewer_verdict_correct" in t["criteria"]]
            pb = [t["criteria"].get("no_blocking_findings") for t in grp if "no_blocking_findings" in t["criteria"]]
            gap = [float(t["reward"]["review"]) - float(t["reward"]["correctness"]) for t in grp
                   if isinstance(t["reward"].get("review"), (int, float)) and isinstance(t["reward"].get("correctness"), (int, float))]
            print(f"{c:{width}} {('yes' if flag else 'no'):>8} {len(grp):>3} {fmt(statistics.mean(pv)) if pv else '-':>13} "
                  f"{fmt(statistics.mean(pb)) if pb else '-':>11}   {fmt(statistics.mean(gap)) if gap else '-':>14}")

    print("\n== code-only diff size, cost per stage (mean per valid trial), author outcomes and end reasons, model mismatches")
    for c in conds:
        ts = valid(c)
        if not ts:
            continue
        per_stage: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
        outcomes: dict[str, int] = defaultdict(int)
        end_reasons: dict[str, int] = defaultdict(int)
        mism: set[str] = set()
        sizes = []
        for t in ts:
            for name, st in (t["summary"].get("stages") or {}).items():
                u = st.get("usage") or {}
                acc = per_stage[name]
                acc[0] += u.get("input_tokens", 0) or 0; acc[1] += u.get("output_tokens", 0) or 0; acc[2] += st.get("seconds", 0) or 0
            a = (t["summary"].get("stages") or {}).get("author")
            if a is not None:
                outcomes[a.get("author_outcome", "n/a")] += 1
                end_reasons[a.get("end_reason", "n/a")] += 1
            mism |= set(t["summary"].get("model_mismatch_any") or [])
            sizes.append(t["summary"].get("diff_shortstat_code_only", ""))
        n = len(ts)
        for name, (tin, tout, secs) in per_stage.items():
            print(f"{c:{width}} {name:14} in={tin / n:9.0f} out={tout / n:9.0f} s={secs / n:7.0f}")
        print(f"{c:{width}} author outcomes {dict(outcomes) or 'n/a'}; end reasons {dict(end_reasons) or 'n/a'}; "
              f"model mismatches {sorted(mism) or 'none'}; e.g. diff: {sizes[0]}")

    excluded_mismatch = [t for t in trials if t["invalid"] == "model_mismatch"]
    if excluded_mismatch:
        print(f"\n== {len(excluded_mismatch)} trial(s) excluded for model mismatch (a stage ran on a model other than the one requested); --keep-model-mismatch keeps them")
    if unknown:
        print("\n== skipped")
        for u in unknown:
            print("  ", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
