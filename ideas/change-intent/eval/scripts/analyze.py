#!/usr/bin/env python3
"""Summarise reward.json files from local runs or Harbor jobs into one table.

    scripts/analyze.py runs/            # local runs made by run_local.sh
    scripts/analyze.py ~/jobs/<job>     # a Harbor jobs directory

Prints per-process mean and spread for each reward dimension. With several processes it also
prints the per-dimension difference against the first process named alphabetically. This is a
starting point; a paired bootstrap across tasks belongs here once there is more than one task.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def find_rewards(root: Path):
    for path in root.rglob("reward.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        process = None
        summary = next(iter(path.parent.rglob("summary.json")), None)
        if summary:
            try:
                process = json.loads(summary.read_text(encoding="utf-8")).get("process")
            except json.JSONDecodeError:
                pass
        if process is None:
            # local runs: runs/<ts>-<process>/reward.json ; harbor: .../<task>__<agent>/... use parent name
            process = path.parent.name.split("-", 1)[-1] if "-" in path.parent.name else path.parent.name
        yield process, data


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "runs")
    by_proc: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for process, data in find_rewards(root):
        for dim, val in data.items():
            if isinstance(val, (int, float)):
                by_proc[process][dim].append(float(val))
    if not by_proc:
        print(f"no reward.json under {root}")
        return 1
    dims = sorted({d for p in by_proc.values() for d in p})
    print(f"{'process':32} {'n':>3} " + " ".join(f"{d:>18}" for d in dims))
    for process in sorted(by_proc):
        row = by_proc[process]
        n = max(len(v) for v in row.values())
        cells = []
        for d in dims:
            v = row.get(d, [])
            if not v:
                cells.append(f"{'-':>18}")
            else:
                sd = statistics.pstdev(v) if len(v) > 1 else 0.0
                cells.append(f"{statistics.mean(v):>10.3f} ±{sd:<6.3f}")
        print(f"{process:32} {n:>3} " + " ".join(cells))
    return 0


if __name__ == "__main__":
    sys.exit(main())
