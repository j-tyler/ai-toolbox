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


def test_welch_interval_is_conservative_on_small_overlapping_samples():
    # Welch df here is about 2.4; the old table rounded the quantile *down* (df<=3 -> 3.182 was right,
    # but df<=2.1 -> 4.303 was not applied). Picking the largest tabulated df at or below the actual
    # df gives the wider interval, which must include 0 for these samples.
    d, lo, hi = analyze.welch([0.9, 0.95, 1.0], [0.5, 0.8, 0.6])
    assert lo < 0 < hi
    assert analyze._t_quantile(2.4) == analyze._t_quantile(2) == 4.303
    assert analyze._t_quantile(1e12) == 1.96


def test_min_p_and_mde():
    assert analyze.min_permutation_p(3, 3) == 0.1
    assert analyze.min_permutation_p(5, 5) == 2 / 252
    mde = analyze.minimum_detectable_effect([0.8, 0.9, 1.0], [0.7, 0.9, 0.8])
    assert 0.25 < mde < 0.45  # about 3 SD at k=3


def _write(tmp_path: Path, name: str, summary: dict, reward: dict | None = None):
    d = tmp_path / name; (d / "app" / ".eval").mkdir(parents=True)
    (d / "app" / ".eval" / "summary.json").write_text(json.dumps(summary))
    if reward is not None:
        (d / "reward.json").write_text(json.dumps(reward))


def test_condition_key_separates_models_and_briefs(tmp_path: Path):
    a = _summary("x", manifest={"model": "m1", "reviewer_model": "r1", "brief_sha256": "a" * 64})
    b = _summary("x", manifest={"model": "m2", "reviewer_model": "r1", "brief_sha256": "a" * 64})
    c = _summary("x", manifest={"model": "m1", "reviewer_model": "r1", "brief_sha256": "b" * 64})
    for i, s in enumerate([a, b, c]):
        _write(tmp_path, f"2026010{i}T000000Z-x", s)
    trials, _ = analyze.load_trials(tmp_path)
    assert len({t["condition"] for t in trials}) == 3


def test_heterogeneous_condition_is_flagged(tmp_path: Path):
    base = {"model": "m", "reviewer_model": "r", "brief_sha256": "a" * 64, "stand_in": "scripted", "harness_dirty": False}
    a = _summary("x", manifest={**base, "harness_git_sha": "1" * 40, "process_files": {"process.json": "aa"}})
    b = _summary("x", manifest={**base, "harness_git_sha": "2" * 40, "process_files": {"process.json": "aa"}})
    c = _summary("x", manifest={**base, "harness_git_sha": "1" * 40, "process_files": {"process.json": "bb"}})
    for i, s in enumerate([a, b, c]):
        _write(tmp_path, f"2026010{i}T000000Z-x", s)
    trials, _ = analyze.load_trials(tmp_path)
    assert len({t["condition"] for t in trials}) == 1
    problems = analyze.heterogeneity(trials)
    assert any("harness_git_sha" in p for p in problems) and any("process_files_digest" in p for p in problems)
    assert analyze.heterogeneity(trials[:1]) == []
    dirty = _summary("x", manifest={**base, "harness_dirty": True})
    _write(tmp_path, "20260109T000000Z-x", dirty)
    trials, _ = analyze.load_trials(tmp_path)
    assert any("harness_dirty" in p for p in analyze.heterogeneity(trials))


def test_model_mismatch_is_invalid_unless_kept(tmp_path: Path):
    _write(tmp_path, "20260101T000000Z-x", _summary("x", model_mismatch_any=["implement: wanted model-a got model-b"]), {"reward": 0.5})
    trials, _ = analyze.load_trials(tmp_path)
    assert trials[0]["invalid"] == "model_mismatch"
    trials, _ = analyze.load_trials(tmp_path, keep_model_mismatch=True)
    assert trials[0]["invalid"] is None


def test_main_stops_on_mixed_conditions_and_reports_otherwise(tmp_path: Path, monkeypatch, capsys):
    base = {"model": "m", "reviewer_model": "r", "brief_sha256": "a" * 64, "stand_in": "scripted", "harness_dirty": False, "process_files": {"p": "1"}}
    _write(tmp_path, "20260101T000000Z-x", _summary("x", "approved", manifest={**base, "harness_git_sha": "1" * 40}), {"reward": 0.9, "correctness": 1.0, "review": 0.8, "handoff": 1.0})
    _write(tmp_path, "20260102T000000Z-x", _summary("x", "approved", manifest={**base, "harness_git_sha": "2" * 40}), {"reward": 0.8, "correctness": 0.9, "review": 0.7, "handoff": 1.0})
    monkeypatch.setattr(sys, "argv", ["analyze", str(tmp_path)])
    assert analyze.main() == 2
    assert "HETEROGENEOUS" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["analyze", str(tmp_path), "--allow-mixed"])
    assert analyze.main() == 0
    out = capsys.readouterr().out
    assert "primary endpoint: correctness" in out and out.index("primary endpoint") < out.index("== trials per condition")
    assert "PP  = biased" in out and "reviewer calibration" in out


def test_condition_key_includes_task(tmp_path: Path):
    a = _summary("baseline", task="ledger-budgets")
    b = _summary("baseline", task="cloudbill-report")
    c = _summary("baseline", manifest={"task": {"name": "cloudbill-report"}})  # manifest-only form
    old = _summary("baseline")  # written before the task config existed
    for i, s in enumerate([a, b, c, old]):
        _write(tmp_path, f"2026010{i}T000000Z-x", s)
    trials, _ = analyze.load_trials(tmp_path)
    conds = sorted({t["condition"] for t in trials})
    assert conds == ["baseline", "baseline task=cloudbill-report", "baseline task=ledger-budgets"]


def test_differences_use_the_reference_arm_of_the_same_task(tmp_path: Path, monkeypatch, capsys):
    conds = ["baseline task=a", "baseline task=b", "v1 task=a", "v1 task=b"]
    tasks = {c: c.split("task=")[1] for c in conds}
    assert analyze.reference_conditions(conds, tasks, "baseline") == {
        "baseline task=a": "baseline task=a", "baseline task=b": "baseline task=b",
        "v1 task=a": "baseline task=a", "v1 task=b": "baseline task=b"}
    # no --ref: each task's alphabetically first condition, never another task's
    assert analyze.reference_conditions(["x task=b", "y task=a", "z task=b"], {"x task=b": "b", "y task=a": "a", "z task=b": "b"}, None) == {
        "x task=b": "x task=b", "y task=a": "y task=a", "z task=b": "x task=b"}
    for i, (proc, task, corr) in enumerate([("baseline", "a", 1.0), ("v1", "a", 0.5), ("baseline", "b", 0.2), ("v1", "b", 0.2)]):
        _write(tmp_path, f"2026010{i}T000000Z-x", _summary(proc, task=task), {"reward": corr, "correctness": corr, "review": 0.5, "handoff": 1.0})
    monkeypatch.setattr(sys, "argv", ["analyze", str(tmp_path), "--ref", "baseline"])
    assert analyze.main() == 0
    out = capsys.readouterr().out
    diffs = out[out.index("== differences"):out.index("== decomposition")]
    assert "v1 task=a" in diffs and "v1 task=b" in diffs
    assert "correctness  (primary    ) -0.500" in diffs and "correctness  (primary    )  0.000" in diffs
