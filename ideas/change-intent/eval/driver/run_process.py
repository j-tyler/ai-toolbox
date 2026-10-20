#!/usr/bin/env python3
"""Run one process version against one workspace and leave gradable artifacts behind.

    python run_process.py --workspace /app --process ../processes/change-intent-v1 \
        --brief /path/to/instruction.md --out /app/.eval [--model gpt-5.4] [--reviewer-model ...] \
        [--backend copilot|fake] [--intent-file path]

Stages, in order (which run is decided by the process's process.json; see processes/README.md):
  author        mode "skill": the authoring skill runs in a Copilot SDK session and a stand-in author
                answers every question; mode "frozen": a supplied intent file is committed as-is (no
                dialogue), which isolates the intent from authoring variance; mode "none": no intent.
  implement     always. One neutral prompt for every condition: implement what {source} describes,
                where source is the intent file when one exists, else the brief. The brief is attached
                only when the process says include_brief. Process-specific guidance arrives only through
                the process's system_append and its agents-file block.
  review        the process's own review pass, when the process defines one; returns its review as text.
  fixed_review  always, harness-owned: the same reviewer for every condition, read-only, custom
                instructions off, shown only diff.patch and change_description.md from a sealed
                directory outside the workspace; returns JSON matching REVIEW_SCHEMA.

During the run all artifacts live OUTSIDE the workspace (a temp dir, or --work-dir), so no stage can
read another stage's output unless the harness hands it over. At the end everything is copied to --out
for the verifier. summary.json is always written, even on failure; the exit code is 0 unless
--fail-on-error is given, and per-stage status lives in summary.json.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backends import Backend, CopilotBackend, FakeBackend, StageResult, StageSpec  # noqa: E402
from stand_in import ModelStandIn, ScriptedStandIn  # noqa: E402

EVAL_ROOT = Path(__file__).resolve().parents[1]
FIXED_REVIEWER_PROMPT_PATH = EVAL_ROOT / "reviewer" / "fixed_reviewer.md"

# ---- harness-neutral prompt templates. Process-specific wording belongs in the process directory. ----

DEFAULT_AUTHOR_PROMPT = """Use the `{skill}` skill to author the change described below. I am the author; ask me \
whenever the skill says to ask the author, and show me the complete proposed file before asking for approval. \
Once I approve, write the file under `{intent_dir}/`, commit it, tell me its path, and stop. Do not implement anything.

# Brief

{brief}
"""

DEFAULT_IMPLEMENT_PROMPT = """Implement the change described in {source}. Run the test suite (`python -m pytest -q`) \
before you finish, and finish by summarising what you changed and how you verified it.
{brief_section}"""

BRIEF_SECTION = "\n# Brief\n\n{brief}\n"

IMPLEMENT_NUDGE = "Please continue until the implementation is complete and all tests pass, then summarise. Do not wait for me."

DEFAULT_PROCESS_REVIEW_PROMPT = """Review the change in this repository following the review guidance in your \
instructions. The change is `git diff {baseline}..HEAD`; the current intent, if any, is `{intent_path}`. You may \
read any file and run the test suite. Do not modify any file.

Return the complete review as your final message: a table with one row per acceptance criterion and per \
invariant in the intent, with columns Claim, Assessment (`met`, `not met`, or `cannot verify`), and Basis; \
then ordinary-review findings (correctness, security, error handling, clarity), each with file and line; then a \
verdict on the intent itself. Report; do not repair.
"""

FIXED_REVIEW_PROMPT = """Review the change described by the two files in `{review_input}`: `diff.patch` is the \
complete change, and `change_description.md` is what the author's process produced to describe it. The repository \
in your working directory is checked out at the state after the change; read what you need there and run \
`python -m pytest -q`. Return your review as JSON matching the schema. Do not modify any file.
"""

REVIEW_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "findings", "overall_correctness", "overall_confidence", "reviewability", "effort_to_review", "claims_checked", "cannot_verify"],
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
        "claims_checked": {"type": "integer", "minimum": 0},
        "cannot_verify": {"type": "array", "items": {"type": "string"}},
    },
}


# ---- helpers -----------------------------------------------------------------------------------

def sh(cmd: list[str], cwd: Path, check: bool = True) -> str:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {proc.stderr.strip()}")
    return proc.stdout


def git_head(ws: Path) -> str:
    return sh(["git", "rev-parse", "HEAD"], ws).strip()


def git_commit_all(ws: Path, message: str, allow_empty: bool = False) -> str | None:
    sh(["git", "add", "-A"], ws)
    if not allow_empty and not sh(["git", "status", "--porcelain"], ws).strip():
        return None
    args = ["git", "commit", "-q", "-m", message] + (["--allow-empty"] if allow_empty else [])
    sh(args, ws)
    return git_head(ws)


def git_dirty_paths(ws: Path) -> list[str]:
    return [line[3:].strip() for line in sh(["git", "status", "--porcelain"], ws).splitlines() if line.strip()]


def git_reset_to(ws: Path, commit: str) -> tuple[list[str], bool]:
    """Discard uncommitted changes and extra commits. Returns (dirty paths, head_moved)."""
    dirty = git_dirty_paths(ws)
    moved = git_head(ws) != commit
    if dirty or moved:
        sh(["git", "reset", "-q", "--hard", commit], ws, check=False)
        sh(["git", "clean", "-fdq"], ws, check=False)
    return dirty, moved


def revert_paths(ws: Path, paths: list[str]) -> None:
    for p in paths:
        tracked = sh(["git", "ls-files", "--error-unmatch", p], ws, check=False).strip()
        if tracked:
            sh(["git", "checkout", "--", p], ws, check=False)
        else:
            target = ws / p
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            elif target.exists():
                target.unlink()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_rel(process_dir: Path, name: str | None) -> str | None:
    return (process_dir / name).read_text(encoding="utf-8") if name else None


def load_process(process_dir: Path) -> dict:
    process = json.loads((process_dir / "process.json").read_text(encoding="utf-8"))
    if "author" not in process:
        raise SystemExit(f"{process_dir}/process.json uses the old schema; run scripts/build_processes.py")
    process.setdefault("intent", {"dir": "change-intent", "claim_sections": ["Acceptance criteria", "Invariants"]})
    process.setdefault("implement", {})
    process["implement"].setdefault("custom_instructions", True)
    process["implement"].setdefault("include_brief", True)
    return process


def find_intent(ws: Path, intent_dir: str) -> Path | None:
    files = sorted(p for p in (ws / intent_dir).glob("*.md") if p.is_file()) if (ws / intent_dir).exists() else []
    return files[-1] if files else None


def write_transcript(path: Path, result: StageResult) -> None:
    lines = [f"# {result.stage}", "", f"turns: {result.turns}  seconds: {result.seconds}  error: {result.error}  timed_out: {result.timed_out}", ""]
    pending_questions: dict[str, str] = {}
    for ev in result.events:
        t = str(ev.get("type", ""))
        data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
        if t.endswith("assistant.message") or t == "fake.message":
            lines += ["## assistant", "", str(data.get("content", "")).strip(), ""]
        elif t.endswith("tool.execution_start"):
            args = json.dumps(data.get("arguments", data.get("args")), default=str)
            lines += [f"- tool `{data.get('tool_name') or data.get('toolName')}` {args[:300]}"]
        elif t.endswith("user_input.requested") or t == "fake.ask_user":
            rid = str(data.get("request_id") or data.get("requestId") or "")
            pending_questions[rid] = str(data.get("question", ""))
            if t == "fake.ask_user":
                lines += [f"- ask_user -> {data.get('answer', '')}"]
        elif t.endswith("user_input.completed"):
            rid = str(data.get("request_id") or data.get("requestId") or "")
            lines += [f"- ask_user: {pending_questions.pop(rid, '?')} -> {data.get('answer', '')}"]
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


def validate_review(review: dict) -> list[str]:
    """Minimal structural check against REVIEW_SCHEMA; returns a list of problems (empty = valid)."""
    problems = []
    for key in REVIEW_SCHEMA["required"]:
        if key not in review:
            problems.append(f"missing {key}")
    if not isinstance(review.get("findings"), list) or not all(isinstance(f, dict) for f in review.get("findings", [])):
        problems.append("findings must be a list of objects")
    if review.get("overall_correctness") not in ("correct", "incorrect", "uncertain"):
        problems.append("overall_correctness not in enum")
    rv = review.get("reviewability")
    if not isinstance(rv, dict) or not all(isinstance(rv.get(k), int) and 1 <= rv[k] <= 5 for k in REVIEW_SCHEMA["properties"]["reviewability"]["required"]):
        problems.append("reviewability ratings must be integers 1..5")
    if not isinstance(review.get("effort_to_review"), int) or not 1 <= review.get("effort_to_review", 0) <= 5:
        problems.append("effort_to_review must be 1..5")
    if not isinstance(review.get("claims_checked"), int):
        problems.append("claims_checked must be an integer")
    if not isinstance(review.get("cannot_verify"), list):
        problems.append("cannot_verify must be a list")
    return problems


def stage_summary(res: StageResult, **extra) -> dict:
    return {
        "status": "error" if res.error else "ok",
        "turns": res.turns, "seconds": res.seconds, "usage": res.usage, "error": res.error,
        "timed_out": res.timed_out, "resolved_model": res.resolved_model, **extra,
    }


# ---- main --------------------------------------------------------------------------------------

async def run(args: argparse.Namespace, summary: dict) -> None:
    ws = Path(args.workspace).resolve()
    process_dir = Path(args.process).resolve()
    process = load_process(process_dir)
    brief = Path(args.brief).read_text(encoding="utf-8")
    out = Path(args.out).resolve()
    work = Path(args.work_dir).resolve() if args.work_dir else Path(tempfile.mkdtemp(prefix="eval-work-"))
    work.mkdir(parents=True, exist_ok=True)
    summary["work_dir"] = str(work)
    intent_cfg = process["intent"]
    intent_dir = intent_cfg["dir"]

    # Git identity for every session the driver spawns (author commits, implementer commits).
    for k, v in {"GIT_AUTHOR_NAME": "eval", "GIT_AUTHOR_EMAIL": "eval@example.invalid",
                 "GIT_COMMITTER_NAME": "eval", "GIT_COMMITTER_EMAIL": "eval@example.invalid"}.items():
        os.environ.setdefault(k, v)

    author_mode = process["author"].get("mode", "none")
    if args.intent_file:
        author_mode = "frozen"
    if author_mode == "frozen" and not (args.intent_file or process["author"].get("frozen_intent")):
        raise SystemExit("author mode 'frozen' needs --intent-file or author.frozen_intent in process.json")

    # Backend and stand-in
    if args.backend == "fake":
        backend: Backend = FakeBackend(Path(args.fake_reference) if args.fake_reference else None, intent_dir)
    else:
        provider = json.loads(args.provider_json) if args.provider_json else None
        backend = CopilotBackend(args.model, provider)
        reviewer = args.reviewer_model or args.model
        if (not args.reviewer_model or reviewer == args.model) and not args.allow_same_reviewer:
            raise SystemExit(
                "The fixed reviewer would run on the same model as the implementer, which adds self-preference. "
                "Pass --reviewer-model <other vendor's model> or --allow-same-reviewer to proceed anyway."
            )
        summary["reviewer_same_model"] = reviewer == args.model

    dialogue_log = work / "author_dialogue.json"
    stand_in = (ModelStandIn(brief, lambda s, u: backend.ask_once(s, u, args.stand_in_model), intent_dir, dialogue_log)
                if args.stand_in == "model" else ScriptedStandIn(brief, intent_dir, dialogue_log))

    async def on_user_input(question: str, choices: list[str] | None) -> tuple[str, bool]:
        if isinstance(stand_in, ModelStandIn):
            return await stand_in.answer_question_async(question, choices)
        return stand_in.answer_question(question, choices)

    async def no_follow_up(_message: str) -> str | None:
        return None

    rendered_prompts: dict[str, str] = {}

    def save_stage(res: StageResult) -> None:
        (work / f"events-{res.stage}.json").write_text(json.dumps(res.events, indent=1, default=str), encoding="utf-8")
        write_transcript(work / f"transcript-{res.stage}.md", res)

    def deadline_for(cap: float | None) -> float | None:
        stage_deadline = time.time() + cap if cap else None
        if args.deadline_epoch:
            stage_deadline = min(stage_deadline or args.deadline_epoch, args.deadline_epoch)
        return stage_deadline

    # ---- manifest: tie every number to the exact inputs that produced it --------------------
    manifest: dict = {
        "process_name": process["name"],
        "process_dir": str(process_dir),
        "process_files": {str(p.relative_to(process_dir)): sha256_file(p) for p in sorted(process_dir.rglob("*")) if p.is_file()},
        "brief_sha256": sha256_text(brief),
        "fixed_reviewer_sha256": sha256_file(FIXED_REVIEWER_PROMPT_PATH),
        "review_schema_sha256": sha256_text(json.dumps(REVIEW_SCHEMA, sort_keys=True)),
        "stand_in": args.stand_in,
        "stand_in_model": args.stand_in_model,
        "model": args.model,
        "reviewer_model": args.reviewer_model or args.model,
        "author_mode": author_mode,
        "versions": backend.versions(),
    }
    try:
        manifest["harness_git_sha"] = sh(["git", "rev-parse", "HEAD"], EVAL_ROOT, check=False).strip() or None
        manifest["harness_dirty"] = bool(sh(["git", "status", "--porcelain", "--", str(EVAL_ROOT)], EVAL_ROOT, check=False).strip())
    except Exception:
        pass
    summary["manifest"] = manifest
    shutil.copy2(process_dir / "process.json", work / "process.json")

    # ---- workspace -----------------------------------------------------------------------------
    if not (ws / ".git").exists():
        sh(["git", "init", "-q"], ws)
    exclude = ws / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    rel_out = os.path.relpath(out, ws)
    if not rel_out.startswith(".."):
        with exclude.open("a", encoding="utf-8") as fh:
            fh.write(f"\n{rel_out}/\n")
    git_commit_all(ws, "eval: seed")
    block = read_rel(process_dir, process.get("agents_block"))
    if block:
        agents_md = ws / "AGENTS.md"
        existing = agents_md.read_text(encoding="utf-8") if agents_md.exists() else ""
        agents_md.write_text((existing.rstrip() + "\n\n" if existing else "") + block, encoding="utf-8")
    if author_mode != "none":
        (ws / intent_dir).mkdir(exist_ok=True)
        (ws / intent_dir / ".gitkeep").touch()
    git_commit_all(ws, f"eval: install process {process['name']}")
    baseline = git_head(ws)
    summary["baseline_commit"] = baseline
    intent_path: Path | None = None

    try:
        # ---- author ----------------------------------------------------------------------------
        if author_mode == "frozen":
            src = Path(args.intent_file) if args.intent_file else process_dir / process["author"]["frozen_intent"]
            (ws / intent_dir).mkdir(exist_ok=True)
            dst = ws / intent_dir / src.name
            shutil.copy2(src, dst)
            commit = git_commit_all(ws, "eval: change intent")
            intent_path = dst
            summary["stages"]["author"] = {"status": "ok", "mode": "frozen", "intent_file": str(dst.relative_to(ws)),
                                           "intent_sha256": sha256_file(dst), "commit": commit, "author_outcome": "approved"}
        elif author_mode == "skill":
            stand_in.stage = "author"
            a = process["author"]
            skill_dirs = [str(process_dir / a["skills_dir"])] if a.get("skills_dir") else []
            template = read_rel(process_dir, a.get("prompt_file")) or DEFAULT_AUTHOR_PROMPT
            prompt = template.format(skill=a.get("skill", ""), intent_dir=intent_dir, brief=brief)
            rendered_prompts["author"] = prompt
            head_before = git_head(ws)

            def intent_state() -> tuple[bool, bool]:
                exists = find_intent(ws, intent_dir) is not None
                committed = exists and (git_head(ws) != head_before or bool(sh(["git", "log", "--oneline", "--", intent_dir], ws, check=False).strip()))
                return exists, committed

            async def next_author_turn(message: str) -> str | None:
                exists, committed = intent_state()
                if isinstance(stand_in, ModelStandIn):
                    return await stand_in.reply_to_message_async(message, exists, committed)
                return stand_in.reply_to_message(message, exists, committed)

            res = await backend.run_stage(
                StageSpec("author", prompt, skill_dirs=skill_dirs, custom_instructions=a.get("custom_instructions", True),
                          max_turns=args.max_author_turns, turn_timeout_sec=args.stage_timeout, deadline=deadline_for(args.cap_author)),
                ws, on_user_input=on_user_input, next_turn=next_author_turn,
            )
            intent_path = find_intent(ws, intent_dir)
            # Anything the author stage touched outside the intent dir is contamination: revert and flag.
            stray = [p for p in git_dirty_paths(ws) if not p.startswith(intent_dir + "/") and p != intent_dir]
            if stray:
                revert_paths(ws, stray)
            commit = git_commit_all(ws, "eval: change intent")
            outcome = "approved" if intent_path and stand_in.approved else ("unapproved_file" if intent_path else "no_file")
            summary["stages"]["author"] = stage_summary(
                res, mode="skill", intent_file=str(intent_path.relative_to(ws)) if intent_path else None,
                intent_sha256=sha256_file(intent_path) if intent_path else None, commit=commit,
                author_outcome=outcome, author_contamination=stray, exchanges=len(stand_in.exchanges),
            )
            save_stage(res)

        # ---- implement -------------------------------------------------------------------------
        stand_in.stage = "implement"
        impl = process["implement"]
        system_append = read_rel(process_dir, impl.get("system_append"))
        source = f"the approved change intent at `{intent_path.relative_to(ws)}`" if intent_path else "the brief below"
        include_brief = impl.get("include_brief", True) or intent_path is None
        template = read_rel(process_dir, impl.get("prompt_file")) or DEFAULT_IMPLEMENT_PROMPT
        prompt = template.format(source=source, brief_section=BRIEF_SECTION.format(brief=brief) if include_brief else "", brief=brief)
        rendered_prompts["implement"] = prompt
        head_before_impl = git_head(ws)
        nudges = {"n": 0}

        async def next_impl_turn(message: str) -> str | None:
            worked = bool(git_dirty_paths(ws)) or git_head(ws) != head_before_impl
            if worked and "?" not in message[-300:]:
                return None
            if nudges["n"] >= args.max_implement_nudges:
                return None
            nudges["n"] += 1
            return IMPLEMENT_NUDGE

        res = await backend.run_stage(
            StageSpec("implement", prompt, system_append=system_append, custom_instructions=impl.get("custom_instructions", True),
                      max_turns=1 + args.max_implement_nudges, turn_timeout_sec=args.stage_timeout, deadline=deadline_for(args.cap_implement)),
            ws, on_user_input=on_user_input, next_turn=next_impl_turn,
        )
        implement_message = res.final_message
        impl_commit = git_commit_all(ws, "eval: implementation", allow_empty=True)
        summary["impl_commit"] = impl_commit
        summary["stages"]["implement"] = stage_summary(
            res, commit=impl_commit, used_intent=intent_path is not None, include_brief=include_brief,
            agent_committed=git_head(ws) != head_before_impl and not res.error and impl_commit is not None,
        )
        save_stage(res)

        # ---- artifacts the reviewers may see --------------------------------------------------
        diff = sh(["git", "diff", f"{baseline}..HEAD"], ws, check=False)
        (work / "diff.patch").write_text(diff, encoding="utf-8")
        summary["diff_shortstat"] = sh(["git", "diff", "--shortstat", f"{baseline}..HEAD"], ws, check=False).strip()
        summary["diff_shortstat_code_only"] = sh(
            ["git", "diff", "--shortstat", f"{baseline}..HEAD", "--", ".", f":(exclude){intent_dir}"], ws, check=False).strip()
        sections = ["# Change description", ""]
        if intent_path is not None:
            sections += [f"## Description document (`{intent_path.relative_to(ws)}`)", "", intent_path.read_text(encoding="utf-8").strip(), ""]
        sections += ["## Implementer summary", "", implement_message.strip() or "(none)", ""]
        (work / "change_description.md").write_text("\n".join(sections), encoding="utf-8")

        # ---- process review (owned by the process version) -----------------------------------
        rv = process.get("review")
        if rv and not args.skip_reviews:
            stand_in.stage = "review"
            template = read_rel(process_dir, rv.get("prompt_file")) or DEFAULT_PROCESS_REVIEW_PROMPT
            intent_ref = str(intent_path.relative_to(ws)) if intent_path else "(no intent file was produced)"
            prompt = template.format(baseline=baseline, intent_path=intent_ref)
            rendered_prompts["review"] = prompt
            res = await backend.run_stage(
                StageSpec("review", prompt, system_append=read_rel(process_dir, rv.get("system_append")),
                          custom_instructions=rv.get("custom_instructions", True), read_only=True,
                          turn_timeout_sec=args.stage_timeout, deadline=deadline_for(args.cap_review)),
                ws, on_user_input=on_user_input, next_turn=no_follow_up,
            )
            if res.final_message.strip():
                (work / "process_review.md").write_text(res.final_message, encoding="utf-8")
            dirty, moved = git_reset_to(ws, impl_commit)
            summary["stages"]["review"] = stage_summary(res, output="process_review.md" if res.final_message.strip() else None,
                                                        reset_paths=dirty, head_moved=moved)
            save_stage(res)

        # ---- fixed review (owned by the harness; identical for every condition) ---------------
        if not args.skip_reviews:
            stand_in.stage = "fixed_review"
            review_input = work / "review-input"
            review_input.mkdir(exist_ok=True)
            shutil.copy2(work / "diff.patch", review_input / "diff.patch")
            shutil.copy2(work / "change_description.md", review_input / "change_description.md")
            prompt = FIXED_REVIEW_PROMPT.format(review_input=review_input)
            rendered_prompts["fixed_review"] = prompt
            res = await backend.run_stage(
                StageSpec("fixed_review", prompt, system_append=FIXED_REVIEWER_PROMPT_PATH.read_text(encoding="utf-8"),
                          custom_instructions=False, read_only=True, response_schema=REVIEW_SCHEMA,
                          model=args.reviewer_model, extra_dirs=[str(review_input)],
                          turn_timeout_sec=args.stage_timeout, deadline=deadline_for(args.cap_fixed_review)),
                ws, on_user_input=on_user_input, next_turn=no_follow_up,
            )
            (work / "review_raw.md").write_text(res.final_message, encoding="utf-8")
            review = parse_review_json(res.final_message)
            problems = validate_review(review) if review is not None else ["unparseable"]
            if review is not None:
                review["_meta"] = {"reviewer_model": res.resolved_model or args.reviewer_model or args.model,
                                   "usage": res.usage, "seconds": res.seconds, "valid": not problems, "problems": problems}
                (work / "review.json").write_text(json.dumps(review, indent=2), encoding="utf-8")
            dirty, moved = git_reset_to(ws, impl_commit)
            summary["stages"]["fixed_review"] = stage_summary(
                res, parsed=review is not None, valid=not problems, problems=problems,
                verdict=(review or {}).get("overall_correctness"), findings=len((review or {}).get("findings", []) or []),
                reset_paths=dirty, head_moved=moved,
            )
            save_stage(res)
    finally:
        await backend.close()
        summary["rendered_prompts_sha256"] = {k: sha256_text(v) for k, v in rendered_prompts.items()}
        (work / "rendered_prompts.json").write_text(json.dumps(rendered_prompts, indent=1), encoding="utf-8")
        summary["author_exchanges"] = len(stand_in.exchanges)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", required=True)
    p.add_argument("--process", required=True, help="directory containing process.json")
    p.add_argument("--brief", required=True, help="markdown file with the author's brief")
    p.add_argument("--out", required=True, help="final artifact directory, copied at the end (the verifier reads it)")
    p.add_argument("--work-dir", help="where artifacts live during the run; default: a temp dir outside the workspace")
    p.add_argument("--model", default=os.environ.get("EVAL_MODEL"))
    p.add_argument("--reviewer-model", default=os.environ.get("EVAL_REVIEWER_MODEL"), help="model for the fixed reviewer; pin one from another vendor")
    p.add_argument("--stand-in-model", default=os.environ.get("EVAL_STAND_IN_MODEL"), help="model for the model stand-in; defaults to --model")
    p.add_argument("--allow-same-reviewer", action="store_true", help="permit the fixed reviewer to share the implementer's model")
    p.add_argument("--provider-json", default=os.environ.get("EVAL_PROVIDER_JSON"), help="BYOK ProviderConfig as JSON")
    p.add_argument("--backend", choices=["copilot", "fake"], default="copilot")
    p.add_argument("--fake-reference", help="fake backend: directory copied in as the implementation")
    p.add_argument("--stand-in", choices=["scripted", "model"], default="scripted")
    p.add_argument("--intent-file", help="freeze this intent: commit it as the intent and skip the author dialogue")
    p.add_argument("--skip-reviews", action="store_true", help="stop after implementation")
    p.add_argument("--max-author-turns", type=int, default=12)
    p.add_argument("--max-implement-nudges", type=int, default=2)
    p.add_argument("--stage-timeout", type=float, default=3600.0, help="seconds to wait for one turn")
    p.add_argument("--cap-author", type=float, default=float(os.environ.get("EVAL_CAP_AUTHOR", 1800)), help="wall-clock cap for the author stage, seconds")
    p.add_argument("--cap-implement", type=float, default=float(os.environ.get("EVAL_CAP_IMPLEMENT", 3600)), help="same cap for every condition")
    p.add_argument("--cap-review", type=float, default=float(os.environ.get("EVAL_CAP_REVIEW", 900)))
    p.add_argument("--cap-fixed-review", type=float, default=float(os.environ.get("EVAL_CAP_FIXED_REVIEW", 900)))
    p.add_argument("--deadline-epoch", type=float, default=None, help="absolute unix time by which every stage must have started")
    p.add_argument("--fail-on-error", action="store_true", help="exit 1 when any stage errored (default: exit 0, status in summary.json)")
    args = p.parse_args()

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    summary: dict = {"process": None, "stages": {}, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "backend": args.backend}
    exit_code = 0
    try:
        summary["process"] = json.loads((Path(args.process) / "process.json").read_text(encoding="utf-8")).get("name")
        asyncio.run(run(args, summary))
    except SystemExit as exc:
        summary["harness_error"] = str(exc)
        exit_code = 2
    except Exception:
        summary["harness_error"] = traceback.format_exc()
        exit_code = 1
    finally:
        summary["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        failed = any(s.get("status") == "error" for s in summary["stages"].values()) or "harness_error" in summary
        summary["status"] = "error" if failed else "ok"
        work = Path(summary["work_dir"]) if summary.get("work_dir") else None
        if work and work.exists():
            for src in work.rglob("*"):
                if src.is_file():
                    dst = out / src.relative_to(work)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        if failed and args.fail_on_error and exit_code == 0:
            exit_code = 1
    return exit_code if (args.fail_on_error or exit_code == 2) else 0


if __name__ == "__main__":
    sys.exit(main())
