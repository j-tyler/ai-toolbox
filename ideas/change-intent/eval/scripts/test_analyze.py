"""Self-check for analyze.py's trial discovery on the two layouts it supports.

    python -m pytest scripts/test_analyze.py -q
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze  # noqa: E402


def _summary(process, outcome=None):
    stages = {"implement": {"status": "ok"}}
    if outcome:
        stages["author"] = {"status": "ok", "author_outcome": outcome}
    return {"process": process, "stages": stages}


def test_local_layout_counts_rewardless_trial(tmp_path: Path):
    a = tmp_path / "20260101T000000Z-x"; (a / "app" / ".eval").mkdir(parents=True)
    (a / "app" / ".eval" / "summary.json").write_text(json.dumps(_summary("x", "approved")))
    (a / "reward.json").write_text(json.dumps({"reward": 0.9}))
    b = tmp_path / "20260101T000001Z-x"; (b / "app" / ".eval").mkdir(parents=True)
    (b / "app" / ".eval" / "summary.json").write_text(json.dumps(_summary("x", "no_file")))  # graded never ran
    trials, unknown = analyze.load_trials(tmp_path)
    assert [t["process"] for t in trials] == ["x", "x"]
    assert sum(1 for t in trials if t["reward"] is None) == 1
    assert sum(1 for t in trials if analyze.is_per_protocol(t["summary"])) == 1
    assert unknown == []


def test_harbor_layout(tmp_path: Path):
    for i, proc in enumerate(["baseline", "change-intent-v1"]):
        trial = tmp_path / "job" / f"trial-{i}"
        (trial / "agent" / "eval").mkdir(parents=True); (trial / "verifier").mkdir()
        (trial / "agent" / "eval" / "summary.json").write_text(json.dumps(_summary(proc)))
        (trial / "verifier" / "reward.json").write_text(json.dumps({"reward": 0.5 + i / 10}))
    trials, unknown = analyze.load_trials(tmp_path)
    assert sorted(t["process"] for t in trials) == ["baseline", "change-intent-v1"]
    assert all(t["reward"] for t in trials)
    assert unknown == []
