"""Self-check for analyze.py's trial discovery and validity rules.

    python -m pytest scripts/test_analyze.py -q
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze  # noqa: E402


def _summary(process, outcome=None, backend="fake", **extra):
    stages = {"implement": {"status": "ok", "usage": {"model_calls": 3}}}
    if outcome:
        stages["author"] = {"status": "ok", "author_outcome": outcome}
    s = {"process": process, "stages": stages, "backend": backend, "status": "ok"}
    s.update(extra)
    return s


def test_local_layout_counts_rewardless_trial(tmp_path: Path):
    a = tmp_path / "20260101T000000Z-x"; (a / "app" / ".eval").mkdir(parents=True)
    (a / "app" / ".eval" / "summary.json").write_text(json.dumps(_summary("x", "approved")))
    (a / "reward.json").write_text(json.dumps({"reward": 0.9}))
    b = tmp_path / "20260101T000001Z-x"; (b / "app" / ".eval").mkdir(parents=True)
    (b / "app" / ".eval" / "summary.json").write_text(json.dumps(_summary("x", "no_file")))
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
    assert all(t["reward"] for t in trials) and unknown == []


def test_invalid_trials_are_flagged_not_pooled(tmp_path: Path):
    cases = {
        "harness": _summary("x", harness_error="boom"),
        "running": {**_summary("x"), "status": "running"},
        "nocalls": {"process": "x", "backend": "copilot", "status": "ok", "stages": {"implement": {"status": "ok", "usage": {}}}},
        "fine": _summary("x"),
    }
    for name, s in cases.items():
        d = tmp_path / f"20260101T00000{len(name)}Z-{name}"; (d / "app" / ".eval").mkdir(parents=True)
        (d / "app" / ".eval" / "summary.json").write_text(json.dumps(s))
        (d / "reward.json").write_text(json.dumps({"reward": 0.1}))
    trials, _ = analyze.load_trials(tmp_path)
    reasons = sorted(t["invalid"] for t in trials if t["invalid"])
    assert reasons == ["driver_never_finished", "harness_error", "no_model_calls"]
    assert sum(1 for t in trials if not t["invalid"]) == 1


def test_conditions_separate_frozen_intents(tmp_path: Path):
    for i, sha in enumerate(["a" * 64, "b" * 64]):
        d = tmp_path / f"2026010{i}T000000Z-f"; (d / "app" / ".eval").mkdir(parents=True)
        s = _summary("f"); s["manifest"] = {"intent_source": {"sha256": sha}}
        (d / "app" / ".eval" / "summary.json").write_text(json.dumps(s))
    trials, _ = analyze.load_trials(tmp_path)
    assert len({t["condition"] for t in trials}) == 2


def test_missing_review_is_marked(tmp_path: Path):
    d = tmp_path / "20260101T000000Z-x"; (d / "app" / ".eval").mkdir(parents=True)
    s = _summary("x"); s["stages"]["fixed_review"] = {"status": "missing", "missing": True}
    (d / "app" / ".eval" / "summary.json").write_text(json.dumps(s))
    (d / "reward.json").write_text(json.dumps({"reward": 0.7, "review": 0.0}))
    trials, _ = analyze.load_trials(tmp_path)
    assert trials[0]["review_missing"] is True


def test_permutation_and_welch_behave():
    assert analyze.permutation_p([1, 1, 1], [1, 1, 1]) == 1.0
    assert analyze.permutation_p([0.9, 0.95, 0.92, 0.91], [0.1, 0.12, 0.08, 0.11]) < 0.05
    d, lo, hi = analyze.welch([1.0, 1.0, 1.0], [0.0, 0.0, 0.0])
    assert d == 1.0 and lo == hi == 1.0
