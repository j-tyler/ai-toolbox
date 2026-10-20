"""Offline tests for the author-stage rules the harness depends on.

    python -m pytest driver/test_author_stage.py -q

They run the driver end to end with the fake backend (no model) and assert the stop rule, the
approval bookkeeping, and contamination handling, so a regression in these cannot pass silently.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent
sys.path.insert(0, str(HERE))

import backends  # noqa: E402
import run_process  # noqa: E402

SEED = EVAL / "tasks" / "ledger-budgets" / "environment" / "seed"
BRIEF = EVAL / "tasks" / "ledger-budgets" / "instruction.md"
SOLUTION = EVAL / "tasks" / "ledger-budgets" / "solution"


def _args(ws: Path, out: Path, process: str = "change-intent-v1", **over) -> SimpleNamespace:
    base = dict(
        workspace=str(ws), process=str(EVAL / "processes" / process), brief=str(BRIEF), out=str(out),
        work_dir=str(out.parent / "work"), model=None, reviewer_model=None, stand_in_model=None,
        allow_same_reviewer=True, provider_json=None, backend="fake", fake_reference=str(SOLUTION),
        stand_in="scripted", intent_file=None, skip_reviews=False, max_author_turns=12,
        max_implement_nudges=2, max_review_attempts=3, stage_timeout=60.0, cap_author=600, cap_implement=600, cap_review=300,
        cap_fixed_review=300, deadline_epoch=None, fail_on_error=False, label=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _run(tmp_path: Path, backend_cls=None, process: str = "change-intent-v1", **over) -> dict:
    ws = tmp_path / "app"; shutil.copytree(SEED, ws)
    out = tmp_path / "out"
    summary = {"process": process, "stages": {}}
    if backend_cls is not None:
        orig = run_process.FakeBackend
        run_process.FakeBackend = backend_cls  # type: ignore[assignment]
    try:
        asyncio.run(run_process.run(_args(ws, out, process, **over), summary))
    finally:
        if backend_cls is not None:
            run_process.FakeBackend = orig  # type: ignore[assignment]
    summary["_ws"] = ws
    summary["_out"] = out
    return summary


def _git(ws: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=ws, text=True, capture_output=True).stdout


def test_author_dialogue_stops_only_after_commit(tmp_path: Path):
    s = _run(tmp_path)
    author = s["stages"]["author"]
    assert author["author_outcome"] == "approved"
    dialogue = json.loads((Path(s["work_dir"]) / "author_dialogue.json").read_text())
    cues = [e["cue"] for e in dialogue if e["stage"] == "author"]
    # an unpresented draft triggers exactly one "show me the file"; presenting the file triggers
    # approval; after the commit the stand-in is silent even though the agent asked whether to implement.
    assert cues.count("ask-for-file") == 1
    assert "approve:presented" in cues
    assert "Shall I proceed" not in " ".join(e["prompt"] for e in dialogue), "no reply after the commit"
    log = _git(s["_ws"], "log", "--format=%s")
    assert "Add description document" in log  # the agent's own commit ended the dialogue
    assert "eval: description document" not in log  # nothing was left over for the harness to commit
    assert "eval: setup" in log and "install process" not in log and "change intent" not in log


def test_draft_without_approval_is_labelled_not_approved(tmp_path: Path):
    class DraftOnly(backends.FakeBackend):
        async def run_stage(self, spec, workspace, *, on_user_input, next_turn):
            if spec.name != "author":
                return await super().run_stage(spec, workspace, on_user_input=on_user_input, next_turn=next_turn)
            res = backends.StageResult(stage="author", final_message="", turns=1)
            d = workspace / self.intent_dir; d.mkdir(exist_ok=True)
            (d / "2026-01-01-draft.md").write_text("## Outcomes\n- x\n")
            await next_turn("I wrote a draft. What else?")  # stand-in asks for the file
            res.final_message = "ok"  # agent stops without presenting or committing
            return res

    s = _run(tmp_path, DraftOnly)
    assert s["stages"]["author"]["author_outcome"] == "unapproved_file"
    assert s["stages"]["implement"]["used_intent"] is True  # still implemented, labelled


def test_committed_contamination_is_reverted_and_flagged(tmp_path: Path):
    class Messy(backends.FakeBackend):
        async def run_stage(self, spec, workspace, *, on_user_input, next_turn):
            if spec.name != "author":
                return await super().run_stage(spec, workspace, on_user_input=on_user_input, next_turn=next_turn)
            res = backends.StageResult(stage="author", final_message="", turns=1)
            (workspace / "ledger" / "cli.py").write_text("# clobbered\n")  # edits code during authoring
            (workspace / "scratch.txt").write_text("notes\n")
            d = workspace / self.intent_dir; d.mkdir(exist_ok=True)
            (d / "2026-01-01-x.md").write_text(backends.FAKE_INTENT)
            await next_turn("Here is the proposed document:\n\n" + backends.FAKE_INTENT + "\n\nDo you approve?")
            subprocess.run(["git", "add", "-A"], cwd=workspace, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-q", "-m", "intent plus junk"], cwd=workspace, check=True, capture_output=True)
            (workspace / "README.md").write_text("also dirty\n")  # left uncommitted
            await next_turn("Committed. Shall I implement?")
            return res

    s = _run(tmp_path, Messy)
    author = s["stages"]["author"]
    assert author["author_outcome"] == "approved"
    assert set(author["author_contamination"]["committed"]) == {"ledger/cli.py", "scratch.txt"}
    assert author["author_contamination"]["uncommitted"] == ["README.md"]
    ws = s["_ws"]
    assert "clobbered" not in (ws / "ledger" / "cli.py").read_text()
    assert not (ws / "scratch.txt").exists()
    assert "also dirty" not in (ws / "README.md").read_text()
    # the intent itself survived and the implementation ran on a clean baseline
    assert (ws / "change-intent" / "2026-01-01-x.md").exists()
    assert s["stages"]["implement"]["status"] == "ok"


def test_frozen_mode_skips_dialogue(tmp_path: Path):
    intent = tmp_path / "my-intent.md"; intent.write_text(backends.FAKE_INTENT)
    s = _run(tmp_path, process="change-intent-v1-frozen", intent_file=str(intent))
    assert s["stages"]["author"]["mode"] == "frozen" and s["stages"]["author"]["author_outcome"] == "approved"
    assert s["manifest"]["intent_source"]["sha256"]
    assert s["stages"]["implement"]["used_intent"] is True


def test_baseline_has_no_author_and_neutral_prompt(tmp_path: Path):
    s = _run(tmp_path, process="baseline")
    assert "author" not in s["stages"]
    prompts = json.loads((Path(s["work_dir"]) / "rendered_prompts.json").read_text())
    assert "intent" not in prompts["implement"].lower()
    assert "approved" not in prompts["implement"].lower()


def test_fixed_review_inputs_are_sealed(tmp_path: Path):
    s = _run(tmp_path)
    review_input = Path(s["review_input_dir"])
    assert not str(review_input).startswith(s["work_dir"])
    assert sorted(p.name for p in review_input.iterdir()) == ["change_description.md", "diff.patch", "requirements.md"]
    assert s["stages"]["fixed_review"]["status"] == "ok" and s["stages"]["fixed_review"]["missing"] is False
    assert s["stages"]["implement"]["agent_committed"] is False  # fake implementer never commits
    assert "change-intent/" not in (Path(s["work_dir"]) / "diff.patch").read_text()  # code-only diff
    assert "change-intent/" in (Path(s["work_dir"]) / "diff-with-artifact.patch").read_text()
    assert s["stages"]["fixed_review"]["agents_md_hidden"] is True


def test_missing_fixed_review_is_recorded_not_scored(tmp_path: Path):
    class ProseReviewer(backends.FakeBackend):
        async def run_stage(self, spec, workspace, *, on_user_input, next_turn):
            if spec.name != "fixed_review":
                return await super().run_stage(spec, workspace, on_user_input=on_user_input, next_turn=next_turn)
            res = backends.StageResult(stage="fixed_review", final_message="I looked at it and it seems fine.", turns=1)
            res.messages = [res.final_message]
            await next_turn(res.final_message)  # driver asks for JSON once; we still answer prose
            return res

    s = _run(tmp_path, ProseReviewer)
    fr = s["stages"]["fixed_review"]
    assert fr["status"] == "missing" and fr["missing"] is True
    assert len(fr["attempts"]) == 3  # fresh sessions, then give up
    review = json.loads((Path(s["work_dir"]) / "review.json").read_text())
    assert review["_meta"]["missing"] is True and "overall_correctness" not in review


def test_stand_in_probes():
    """Behaviours a real skill exhibits that must not be mislabelled."""
    from stand_in import ScriptedStandIn
    sections = ["Outcomes", "Why", "Constraints", "Acceptance criteria", "Invariants", "Out of scope"]
    # 1. A Phase-1 preview that echoes the harness prompt's words must not approve anything.
    s = ScriptedStandIn("brief", "change-intent", noun="change intent", required_sections=sections)
    r = s.reply_to_message("## Intent brief\n... Once you confirm, I will explore the code and show you the complete "
                           "proposed file before asking you to approve it.", False, False, None)
    assert not s.approved and "Approved" not in (r or "")
    # 2. A neutral question with an affirmative choice approves only after a presentation.
    s = ScriptedStandIn("brief", "change-intent", noun="change intent", required_sections=sections)
    s.answer_question("How would you like to proceed?", ["Approve as written", "Revise"], None)
    assert not s.approved
    s.reply_to_message(backends.FAKE_INTENT + "\n\nThat is the complete file.", True, False, backends.FAKE_INTENT)
    assert s.presented and s.approved
    # 3. An unrelated approval-word question, draft never shown, does not approve.
    s = ScriptedStandIn("brief", "change-intent", noun="change intent", required_sections=sections)
    s.answer_question("Do you approve of keeping the existing `list` naming?", ["Yes (recommended)", "No"], None)
    assert not s.approved
    # 4. Approved, file exists, agent announces it will commit but stops: one commit nudge, then silence.
    s = ScriptedStandIn("brief", "change-intent", noun="change intent", required_sections=sections)
    s.reply_to_message(backends.FAKE_INTENT, True, False, backends.FAKE_INTENT)
    assert s.approved
    r = s.reply_to_message("I'll strip the scaffolding tags and commit now.", True, False, backends.FAKE_INTENT)
    assert r and "commit it now" in r
    assert s.reply_to_message("Done?", True, False, backends.FAKE_INTENT) is None
    # 5. The default reply adds no scope direction beyond the brief.
    s = ScriptedStandIn("brief", "change-intent", noun="change intent", required_sections=sections)
    r = s.reply_to_message("Should I add caching?", False, False, None)
    assert "out of scope" not in r.lower() and "your call" in r.lower()


def test_two_intent_files_resolve_to_the_committed_one(tmp_path: Path):
    class TwoFiles(backends.FakeBackend):
        async def run_stage(self, spec, workspace, *, on_user_input, next_turn):
            if spec.name != "author":
                return await super().run_stage(spec, workspace, on_user_input=on_user_input, next_turn=next_turn)
            res = backends.StageResult(stage="author", final_message="", turns=1)
            d = workspace / self.intent_dir; d.mkdir(exist_ok=True)
            (d / "2026-01-01-a-real.md").write_text(backends.FAKE_INTENT)
            (d / "2026-01-01-z-draft.md").write_text("## Outcomes\n- scratch\n")  # sorts last, is NOT committed
            await next_turn("Here is the complete document:\n\n" + backends.FAKE_INTENT)
            subprocess.run(["git", "add", "change-intent/2026-01-01-a-real.md"], cwd=workspace, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-q", "-m", "intent"], cwd=workspace, check=True, capture_output=True)
            await next_turn("Committed. Anything else?")
            return res

    s = _run(tmp_path, TwoFiles)
    a = s["stages"]["author"]
    assert a["intent_file"] == "change-intent/2026-01-01-a-real.md"
    assert a["author_outcome"] == "multiple_files" and len(a["intent_candidates"]) == 2


def test_implement_continuation_rule_is_objective(tmp_path: Path):
    """Nudge while nothing in the code tree changed or the visible suite is red; stop once both hold."""
    class Lazy(backends.FakeBackend):
        async def run_stage(self, spec, workspace, *, on_user_input, next_turn):
            if spec.name != "implement":
                return await super().run_stage(spec, workspace, on_user_input=on_user_input, next_turn=next_turn)
            res = backends.StageResult(stage="implement", final_message="", turns=0)
            # turn 1: no code change at all -> must be nudged
            res.turns += 1; res.messages.append("I read the brief. Done.")
            follow = await next_turn(res.messages[-1]); assert follow is not None
            # turn 2: code changed but the suite is red (a broken test) -> must be nudged
            (workspace / "ledger" / "extra.py").write_text("x = 1\n")
            (workspace / "tests" / "test_broken.py").write_text("def test_broken():\n    assert False\n")
            res.turns += 1; res.messages.append("Added a module.")
            follow = await next_turn(res.messages[-1]); assert follow is not None
            # turn 3: suite green -> stop
            (workspace / "tests" / "test_broken.py").unlink()
            for src in (self.reference_dir / "ledger").rglob("*.py"):
                (workspace / "ledger" / src.name).write_text(src.read_text())
            res.turns += 1; res.messages.append("Fixed and green. Shall I also add caching?")
            follow = await next_turn(res.messages[-1]); assert follow is None
            res.final_message = res.messages[-1]
            return res

    s = _run(tmp_path, Lazy, process="baseline")
    detail = s["stages"]["implement"]["turns_detail"]
    assert [d["action"] for d in detail] == ["nudge", "nudge", "stop"]
    assert [d["end_reason"] for d in detail] == ["no_code_change", "suite_red", "complete"]
    desc = (Path(s["work_dir"]) / "change_description.md").read_text()
    assert "### Turn 1" in desc and "### Turn 3" in desc  # every turn's summary is kept
