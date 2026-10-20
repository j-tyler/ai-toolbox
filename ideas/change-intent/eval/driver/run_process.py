#!/usr/bin/env python3
"""Run one process version against one workspace and leave gradable artifacts behind.

    python run_process.py --workspace /app --process ../processes/change-intent-v1 \
        --brief /path/to/instruction.md --out /app/.eval [--model gpt-5.4] [--backend copilot|fake]

Stages, in order:
  author        (process stage) the authoring skill runs in a Copilot SDK session; a stand-in author
                answers every question; the approved intent is committed under change-intent/.
  implement     (always) a session implements, against the committed intent when one exists,
                otherwise against the brief; the result is committed.
  review        (process stage) the process's own review pass, with its review guidance appended,
                writes .eval/process_review.md. Only process versions that list it get it.
  fixed_review  (always, harness-owned) the same reviewer for every condition, read-only, with the
                change description the process left behind; returns JSON matching REVIEW_SCHEMA.

Artifacts in --out:
  summary.json             what ran, timings, token counts, intent path, per-stage errors
  author_dialogue.json     every stand-in exchange (ask_user calls and end-of-turn replies)
  change_description.md    what the process produced to describe the change (intent and/or summary)
  diff.patch               git diff from the installed-process baseline to the implementation commit
  process_review.md        the process review's output (review stage only)
  review.json, review_raw.md   the fixed reviewer's structured verdict and its raw final message
  events-<stage>.json, transcript-<stage>.md   full SDK events and a readable transcript per stage

The harness never grades here. Grading is the verifier's job (Harbor tests/ via Reward Kit, or
scripts/run_local.sh for a plain worktree).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backends import Backend, CopilotBackend, FakeBackend, StageResult  # noqa: E402
from stand_in import ModelStandIn, ScriptedStandIn  # noqa: E402

EVAL_ROOT = Path(__file__).resolve().parents[1]
FIXED_REVIEWER_PROMPT_PATH = EVAL_ROOT / "reviewer" / "fixed_reviewer.md"

AUTHOR_PROMPT = """Use the `change-intent-author` skill to author a change intent for the change described below. \
I am the author; ask me whenever the skill says to ask the author, and show me the complete proposed file before \
asking for approval. Once I approve, write the file under `{intent_dir}/`, commit it, tell me its path, and stop. \
Do not implement anything.

# Brief

{brief}
"""

IMPLEMENT_WITH_INTENT_PROMPT = """Implement the change described by the approved change intent at `{intent_path}`. \
Treat that file as the goal and decision boundary; follow the change-intent implementation guidance in your \
instructions, including the per-criterion tests and would-fail demonstrations. The author's original brief is \
included below for context only; the intent governs where they differ. Run the full test suite \
(`python -m pytest -q`) before you finish, and finish by summarising what you changed and what you demonstrated.

# Brief (context)

{brief}
"""

IMPLEMENT_BASELINE_PROMPT = """Implement the change described in the brief below in this repository. Add tests for \
everything you build and run the full test suite (`python -m pytest -q`) before you finish. Finish by summarising \
what you changed and how you verified it.

# Brief

{brief}
"""

IMPLEMENT_NUDGE = "Please continue until the implementation is complete and all tests pass, then summarise. Do not wait for me."

PROCESS_REVIEW_PROMPT = """Review the change in this repository against its change intent, following the change-intent \
review guidance in your instructions. The change is `git diff {baseline}..HEAD` (a copy is at `.eval/diff.patch`); \
the current intent is `{intent_path}`. You may read any file and run the test suite. Do not modify any file \
other than the one you are asked to write.

Write your complete review to `.eval/process_review.md`. It must contain a table with one row per acceptance \
criterion and per invariant in the intent, with columns Claim, Assessment (`met`, `not met`, or `cannot verify`), \
and Basis; then an ordinary-review findings section (correctness, security, error handling, clarity), each finding \
with file and line; then a verdict on the intent itself (claims falsifiable, decisions complete, amendments \
eligible and coherent, exactly one current intent). Report; do not repair. When the file is written, say so and stop.
"""

FIXED_REVIEW_PROMPT = """Review the change in this repository. The change is `git diff {baseline}..HEAD` (a copy is at \
`.eval/diff.patch`); the change description the author's process produced is at `.eval/change_description.md`. \
Read what you need, run `python -m pytest -q`, and return your review as JSON matching the schema. Do not modify \
any file.
"""

REVIEW_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "findings", "overall_correctness", "overall_confidence", "reviewability", "effort_to_review", "cannot_verify"],
    "properties": {
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "body", "file", "line_start", "line_end", "severity", "confidence", "category"],
                "properties": {
                    "title": {"type": "string", "maxLength": 120},
                    "body": {"type": "string"},
                    "file": {"type": "string"},
                    "line_start": {"type": "integer", "minimum": 1},
                    "line_end": {"type": "integer", "minimum": 1},
                    "severity": {"type": "integer", "minimum": 1, "maximum": 3},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "category": {"type": "string", "enum": ["functionality", "tests", "design", "complexity", "naming", "security", "error_handling", "other"]},
                },
            },
        },
        "overall_correctness": {"type": "string", "enum": ["correct", "incorrect", "uncertain"]},
        "overall_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reviewability": {
            "type": "object",
            "additionalProperties": False,
            "required": ["description_adequacy", "coherence", "verifiability", "size_appropriateness", "clarity"],
            "properties": {k: {"type": "integer", "minimum": 1, "maximum": 5} for k in ["description_adequacy", "coherence", "verifiability", "size_appropriateness", "clarity"]},
        },
        "effort_to_review": {"type": "integer", "minimum": 1, "maximum": 5},
        "cannot_verify": {"type": "array", "items": {"type": "string"}},
    },
}


def sh(cmd: list[str], cwd: Path, check: bool = True) -> str:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {proc.stderr.strip()}")
    return proc.stdout


def git_commit_all(ws: Path, message: str) -> str | None:
    sh(["git", "add", "-A"], ws)
    if not sh(["git", "status", "--porcelain"], ws).strip():
        return None
    sh(["git", "-c", "user.name=eval", "-c", "user.email=eval@example.invalid", "commit", "-q", "-m", message], ws)
    return sh(["git", "rev-parse", "HEAD"], ws).strip()


def git_reset_tracked(ws: Path) -> list[str]:
    """Undo any modification a read-only stage made. Returns the paths that had changed."""
    dirty = [line[3:] for line in sh(["git", "status", "--porcelain"], ws).splitlines() if line.strip()]
    if dirty:
        sh(["git", "checkout", "--", "."], ws, check=False)
        sh(["git", "clean", "-fdq"], ws, check=False)
    return dirty


def prepare_workspace(ws: Path, process: dict, process_dir: Path, out: Path) -> str:
    """Make the workspace a git repo with the process files installed, and return the baseline commit."""
    if not (ws / ".git").exists():
        sh(["git", "init", "-q"], ws)
    exclude = ws / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    rel_out = os.path.relpath(out, ws)
    if not rel_out.startswith(".."):
        with exclude.open("a", encoding="utf-8") as fh:
            fh.write(f"\n{rel_out}/\n")
    git_commit_all(ws, "eval: seed")

    block = process.get("agents_block")
    if block:
        text = (process_dir / block).read_text(encoding="utf-8")
        agents_md = ws / "AGENTS.md"
        existing = agents_md.read_text(encoding="utf-8") if agents_md.exists() else ""
        agents_md.write_text((existing.rstrip() + "\n\n" if existing else "") + text, encoding="utf-8")
    intent_dir = process.get("intent_dir")
    if intent_dir:
        (ws / intent_dir).mkdir(exist_ok=True)
        (ws / intent_dir / ".gitkeep").touch()
    git_commit_all(ws, f"eval: install process {process['name']}")
    return sh(["git", "rev-parse", "HEAD"], ws).strip()


def find_intent(ws: Path, intent_dir: str | None) -> Path | None:
    if not intent_dir:
        return None
    files = sorted(p for p in (ws / intent_dir).glob("*.md") if p.is_file())
    return files[-1] if files else None


def write_transcript(path: Path, result: StageResult) -> None:
    lines = [f"# {result.stage}", "", f"turns: {result.turns}  seconds: {result.seconds}  error: {result.error}", ""]
    for ev in result.events:
        t = str(ev.get("type", ""))
        data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
        if t.endswith("assistant.message") or t == "fake.message":
            lines += ["## assistant", "", str(data.get("content", "")).strip(), ""]
        elif t.endswith("tool.execution_start"):
            args = json.dumps(data.get("arguments"), default=str)
            lines += [f"- tool `{data.get('tool_name')}` {args[:300]}"]
        elif t.endswith("user_input.requested") or t == "fake.ask_user":
            lines += [f"- ask_user: {data.get('question', '')} -> {data.get('answer', '')}"]
        elif t.endswith("user.message"):
            lines += ["## user", "", str(data.get("content", "")).strip(), ""]
    lines += ["", "## final message", "", result.final_message]
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_review_json(text: str) -> dict | None:
    """The reviewer returns JSON; tolerate a fenced block or surrounding prose."""
    text = text.strip()
    for candidate in (text, re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def stage_summary(res: StageResult, **extra) -> dict:
    return {"turns": res.turns, "seconds": res.seconds, "usage": res.usage, "error": res.error, **extra}


async def run(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve()
    process_dir = Path(args.process).resolve()
    process = json.loads((process_dir / "process.json").read_text(encoding="utf-8"))
    brief = Path(args.brief).read_text(encoding="utf-8")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    stages = list(process["stages"])

    summary: dict = {
        "process": process["name"],
        "stages": {},
        "model": args.model,
        "reviewer_model": args.reviewer_model or args.model,
        "backend": args.backend,
        "stand_in": args.stand_in,
        "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if args.backend == "fake":
        backend: Backend = FakeBackend(Path(args.fake_reference) if args.fake_reference else None, process.get("intent_dir", "change-intent"))
    else:
        provider = json.loads(args.provider_json) if args.provider_json else None
        backend = CopilotBackend(args.model, provider)

    dialogue_log = out / "author_dialogue.json"
    stand_in = ModelStandIn(brief, backend.ask_once, dialogue_log) if args.stand_in == "model" else ScriptedStandIn(brief, dialogue_log)

    async def on_user_input(question: str, choices: list[str] | None) -> tuple[str, bool]:
        if isinstance(stand_in, ModelStandIn):
            return await stand_in.answer_question_async(question, choices)
        return stand_in.answer_question(question, choices)

    async def no_follow_up(_message: str) -> str | None:
        return None

    def save_stage(res: StageResult) -> None:
        (out / f"events-{res.stage}.json").write_text(json.dumps(res.events, indent=1, default=str), encoding="utf-8")
        write_transcript(out / f"transcript-{res.stage}.md", res)

    baseline = prepare_workspace(ws, process, process_dir, out)
    summary["baseline_commit"] = baseline
    intent_dir = process.get("intent_dir")
    intent_path: Path | None = None
    implement_message = ""

    try:
        # ---- author -------------------------------------------------------------------------
        if "author" in stages:
            stand_in.stage = "author"
            skill_dirs = [str(process_dir / process["skills_dir"])] if process.get("skills_dir") else []

            async def next_author_turn(message: str) -> str | None:
                exists = find_intent(ws, intent_dir) is not None
                if isinstance(stand_in, ModelStandIn):
                    return await stand_in.reply_to_message_async(message, exists)
                return stand_in.reply_to_message(message, exists)

            res = await backend.run_stage(
                "author", ws, AUTHOR_PROMPT.format(brief=brief, intent_dir=intent_dir),
                system_append=None, skill_dirs=skill_dirs, on_user_input=on_user_input,
                next_turn=next_author_turn, max_turns=args.max_author_turns, timeout_sec=args.stage_timeout,
            )
            intent_path = find_intent(ws, intent_dir)
            commit = git_commit_all(ws, "eval: change intent")
            summary["stages"]["author"] = stage_summary(res, intent_file=str(intent_path.relative_to(ws)) if intent_path else None, commit=commit)
            save_stage(res)

        # ---- implement ----------------------------------------------------------------------
        stand_in.stage = "implement"
        guidance = process.get("implementation_guidance")
        system_append = (process_dir / guidance).read_text(encoding="utf-8") if guidance else None
        if intent_path is not None:
            prompt = IMPLEMENT_WITH_INTENT_PROMPT.format(intent_path=intent_path.relative_to(ws), brief=brief)
        else:
            prompt = IMPLEMENT_BASELINE_PROMPT.format(brief=brief)
            if "author" in stages:
                summary["stages"].setdefault("author", {})["note"] = "no intent file produced; implemented from brief"

        nudges = {"n": 0}

        async def next_impl_turn(message: str) -> str | None:
            dirty = sh(["git", "status", "--porcelain"], ws).strip()
            if dirty and "?" not in message[-300:]:
                return None
            if nudges["n"] >= args.max_implement_nudges:
                return None
            nudges["n"] += 1
            return IMPLEMENT_NUDGE

        res = await backend.run_stage(
            "implement", ws, prompt, system_append=system_append, skill_dirs=[], on_user_input=on_user_input,
            next_turn=next_impl_turn, max_turns=1 + args.max_implement_nudges, timeout_sec=args.stage_timeout,
        )
        implement_message = res.final_message
        commit = git_commit_all(ws, "eval: implementation")
        summary["stages"]["implement"] = stage_summary(res, commit=commit, used_intent=intent_path is not None)
        save_stage(res)

        # ---- artifacts the reviewers read ---------------------------------------------------
        diff = sh(["git", "diff", f"{baseline}..HEAD"], ws, check=False)
        (out / "diff.patch").write_text(diff, encoding="utf-8")
        summary["diff_shortstat"] = sh(["git", "diff", "--shortstat", f"{baseline}..HEAD"], ws, check=False).strip()
        description = []
        if intent_path is not None:
            description.append(f"# Approved change intent (`{intent_path.relative_to(ws)}`)\n\n" + intent_path.read_text(encoding="utf-8"))
        description.append("# Implementer's final summary\n\n" + (implement_message.strip() or "(none)"))
        (out / "change_description.md").write_text("\n\n---\n\n".join(description) + "\n", encoding="utf-8")

        # ---- process review (owned by the process version) ---------------------------------
        if "review" in stages and not args.skip_reviews:
            stand_in.stage = "review"
            review_guidance = process.get("review_guidance")
            review_append = (process_dir / review_guidance).read_text(encoding="utf-8") if review_guidance else None
            intent_ref = str(intent_path.relative_to(ws)) if intent_path else "(no intent file was produced)"
            res = await backend.run_stage(
                "review", ws, PROCESS_REVIEW_PROMPT.format(baseline=baseline, intent_path=intent_ref),
                system_append=review_append, skill_dirs=[], on_user_input=on_user_input,
                next_turn=no_follow_up, max_turns=1, timeout_sec=args.stage_timeout, read_only=True,
            )
            review_file = out / "process_review.md"
            if not review_file.exists() and res.final_message.strip():
                review_file.write_text(res.final_message, encoding="utf-8")  # reviewer answered inline
            touched = git_reset_tracked(ws)
            summary["stages"]["review"] = stage_summary(res, output=str(review_file.relative_to(ws)) if review_file.exists() else None, reset_paths=touched)
            save_stage(res)

        # ---- fixed review (owned by the harness; identical for every condition) ------------
        if not args.skip_reviews:
            stand_in.stage = "fixed_review"
            reviewer_system = FIXED_REVIEWER_PROMPT_PATH.read_text(encoding="utf-8")
            res = await backend.run_stage(
                "fixed_review", ws, FIXED_REVIEW_PROMPT.format(baseline=baseline),
                system_append=reviewer_system, skill_dirs=[], on_user_input=on_user_input,
                next_turn=no_follow_up, max_turns=1, timeout_sec=args.stage_timeout,
                response_schema=REVIEW_SCHEMA, read_only=True, model=args.reviewer_model,
            )
            (out / "review_raw.md").write_text(res.final_message, encoding="utf-8")
            review = parse_review_json(res.final_message)
            if review is not None:
                review["_meta"] = {"reviewer_model": args.reviewer_model or args.model, "usage": res.usage, "seconds": res.seconds}
                (out / "review.json").write_text(json.dumps(review, indent=2), encoding="utf-8")
            touched = git_reset_tracked(ws)
            summary["stages"]["fixed_review"] = stage_summary(
                res, parsed=review is not None, verdict=(review or {}).get("overall_correctness"),
                findings=len((review or {}).get("findings", [])), reset_paths=touched,
            )
            save_stage(res)
    finally:
        await backend.close()

    summary["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    summary["author_exchanges"] = len(stand_in.exchanges)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    failed = any(s.get("error") for s in summary["stages"].values())
    return 1 if failed else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", required=True)
    p.add_argument("--process", required=True, help="directory containing process.json")
    p.add_argument("--brief", required=True, help="markdown file with the author's brief")
    p.add_argument("--out", required=True, help="artifact directory (kept out of the diff)")
    p.add_argument("--model", default=os.environ.get("EVAL_MODEL"))
    p.add_argument("--reviewer-model", default=os.environ.get("EVAL_REVIEWER_MODEL"), help="model for the fixed reviewer; pin one from another vendor")
    p.add_argument("--provider-json", default=os.environ.get("EVAL_PROVIDER_JSON"), help="BYOK ProviderConfig as JSON")
    p.add_argument("--backend", choices=["copilot", "fake"], default="copilot")
    p.add_argument("--fake-reference", help="fake backend: directory copied in as the implementation")
    p.add_argument("--stand-in", choices=["scripted", "model"], default="scripted")
    p.add_argument("--skip-reviews", action="store_true", help="stop after implementation")
    p.add_argument("--max-author-turns", type=int, default=12)
    p.add_argument("--max-implement-nudges", type=int, default=2)
    p.add_argument("--stage-timeout", type=float, default=3600.0, help="seconds to wait for one turn")
    return asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
