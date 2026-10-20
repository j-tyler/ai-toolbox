#!/usr/bin/env python3
"""Run one process version against one workspace and leave gradable artifacts behind.

    python run_process.py --workspace /app --process ../processes/change-intent-v1 \
        --brief /path/to/instruction.md --out /app/.eval --model gpt-5.4 --reviewer-model claude-sonnet-4.5 \
        [--backend copilot|fake] [--intent-file path] [--label key=value ...]

Stages, in order (which run is decided by the process's process.json; see processes/README.md):
  author        mode "skill": the authoring skill runs in a Copilot SDK session and a stand-in author
                answers every question; the stage ends when a commit made during the stage touches the
                intent dir; mode "frozen": a supplied file is committed as-is (no dialogue), which
                isolates the artifact from authoring variance; mode "none": no artifact.
  implement     always. One neutral prompt for every condition: implement what {source} describes,
                where source is the artifact when one exists, else the brief. The brief is attached only
                when the process says include_brief. Process-specific guidance arrives only through the
                process's system_append and its agents-file block. Continuation is decided by one
                objective rule for every condition: nudge while the visible test suite is red or nothing
                under the code tree changed, up to a fixed number of times.
  review        the process's own review pass, when the process defines one; returns its review as text.
  fixed_review  always, harness-owned: the same reviewer for every condition, read-only, custom
                instructions off, built-in sub-agents off, shown exactly three files in a sealed
                directory outside the workspace: requirements.md (the brief), diff.patch (code only),
                change_description.md (the artifact, if any, plus the implementer's summary). Correctness
                is judged against requirements.md; the description is rated for adequacy. An invalid or
                missing review is retried in a fresh session, then recorded as missing, never as a score.

Harness commits are condition-neutral: "eval: setup", "eval: description document",
"eval: implementation". During the run all artifacts live OUTSIDE the workspace (a temp dir, or
--work-dir); at the end everything is copied to --out for the verifier. summary.json is written at
start (status running) and at the end; the exit code is 0 unless --fail-on-error is given.
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

from backends import READ_ONLY_TOOLS, Backend, CopilotBackend, FakeBackend, StageResult, StageSpec  # noqa: E402
from stand_in import ModelStandIn, ScriptedStandIn  # noqa: E402

EVAL_ROOT = Path(__file__).resolve().parents[1]
FIXED_REVIEWER_PROMPT_PATH = EVAL_ROOT / "reviewer" / "fixed_reviewer.md"
CODE_DIRS = ("ledger",)  # where "the implementation" lives for the continuation rule

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

IMPLEMENT_NUDGE = "Please continue until the implementation is complete and the test suite passes, then summarise. Do not wait for me."

DEFAULT_PROCESS_REVIEW_PROMPT = """Review the change in this repository following the review guidance in your \
instructions. The change is `git diff {baseline}..HEAD`; the current {noun}, if any, is `{intent_path}`. You may \
read any file and run the test suite. Do not modify any file.

Return the complete review as your final message: a table with one row per item listed under {claim_sections} \
in the {noun}, with columns Claim, Assessment (`met`, `not met`, or `cannot verify`), and Basis; then \
ordinary-review findings (correctness, security, error handling, clarity), each with file and line; then a \
verdict on the {noun} itself. Report; do not repair.
"""

FIXED_REVIEW_PROMPT = """Review the change described by the three files in `{review_input}`: `requirements.md` is \
what was asked for and is the standard for correctness; `diff.patch` is the complete code change; \
`change_description.md` is what the author's process produced to describe the change. The repository in your \
working directory is checked out at the state after the change; read what you need there and run \
`python -m pytest -q`. Return your review as JSON matching the schema. Do not modify any file.
"""

JSON_ONLY_RETRY = "Return only the JSON object matching the schema, nothing else."

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
FINDING_CATEGORIES = set(REVIEW_SCHEMA["properties"]["findings"]["items"]["properties"]["category"]["enum"])


# ---- helpers -----------------------------------------------------------------------------------

def sh(cmd: list[str], cwd: Path, check: bool = True, timeout: float | None = None) -> str:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
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
    """Uncommitted paths (modified, added, deleted, renamed: the new name), parsed from porcelain v1 -z."""
    raw = subprocess.run(["git", "status", "--porcelain=v1", "-z"], cwd=ws, text=True, capture_output=True).stdout
    fields = raw.split("\0")
    paths, i = [], 0
    while i < len(fields):
        entry = fields[i]
        if not entry:
            i += 1
            continue
        code, path = entry[:2], entry[3:]
        paths.append(path)
        if code[0] in "RC":
            i += 1
        i += 1
    return paths


def git_committed_paths(ws: Path, since: str) -> list[str]:
    return [p for p in sh(["git", "diff", "--name-only", f"{since}..HEAD"], ws, check=False).splitlines() if p.strip()]


def git_tracked_at(ws: Path, commit: str, path: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{commit}:{path}"], cwd=ws, capture_output=True).returncode == 0


def git_stash_count(ws: Path) -> int:
    return len([l for l in sh(["git", "stash", "list"], ws, check=False).splitlines() if l.strip()])


def git_reset_to(ws: Path, commit: str) -> tuple[list[str], bool]:
    """Discard uncommitted changes and extra commits. Returns (dirty paths, head_moved)."""
    dirty = git_dirty_paths(ws)
    moved = git_head(ws) != commit
    if dirty or moved:
        sh(["git", "reset", "-q", "--hard", commit], ws, check=False)
        sh(["git", "clean", "-fdq"], ws, check=False)
    return dirty, moved


def revert_paths(ws: Path, paths: list[str], to_commit: str) -> None:
    """Restore each path to its state at ``to_commit`` (delete it if it did not exist there)."""
    for p in paths:
        if git_tracked_at(ws, to_commit, p):
            sh(["git", "checkout", to_commit, "--", p], ws, check=False)
        else:
            sh(["git", "rm", "-rq", "--cached", "--ignore-unmatch", p], ws, check=False)
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


def slugify(text: str, n: int = 32) -> str:
    text = re.sub(r"^\s*(brief|task|change)\s*[:\-]\s*", "", text, flags=re.I)
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:n].rstrip("-") or "change"


def load_process(process_dir: Path) -> dict:
    process = json.loads((process_dir / "process.json").read_text(encoding="utf-8"))
    if "author" not in process:
        raise SystemExit(f"{process_dir}/process.json uses the old schema; run scripts/build_processes.py")
    process.setdefault("intent", {"dir": "change-intent", "claim_sections": ["Acceptance criteria", "Invariants"]})
    process["intent"].setdefault("noun", "description document")
    process["intent"].setdefault("required_sections", [])
    process.setdefault("implement", {})
    process["implement"].setdefault("custom_instructions", True)
    process["implement"].setdefault("include_brief", True)
    return process


def intent_files_in(ws: Path, intent_dir: str) -> list[Path]:
    return sorted(p for p in (ws / intent_dir).glob("*.md") if p.is_file()) if (ws / intent_dir).exists() else []


def resolve_intent(ws: Path, intent_dir: str, since: str | None) -> tuple[Path | None, list[str]]:
    """The artifact file. Prefer files added or modified by commits since ``since`` (newest commit wins);
    fall back to whatever exists on disk. Returns (path, all candidate relative paths)."""
    candidates = [str(p.relative_to(ws)) for p in intent_files_in(ws, intent_dir)]
    if since:
        committed = [
            p for p in sh(["git", "diff", "--name-only", f"{since}..HEAD", "--", intent_dir], ws, check=False).splitlines()
            if p.strip() and p.endswith(".md") and (ws / p).exists()
        ]
        if committed:
            # newest: the one touched by the most recent commit
            def last_touch(p: str) -> int:
                out = sh(["git", "log", "-1", "--format=%ct", "--", p], ws, check=False).strip()
                return int(out) if out else 0
            best = max(committed, key=last_touch)
            return ws / best, candidates
    if candidates:
        return ws / candidates[-1], candidates
    return None, candidates


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


def out_of_bounds_reads(events: list[dict], allowed: list[str]) -> list[str]:
    """Tool calls whose arguments mention an absolute path outside the allowed roots."""
    hits: list[str] = []
    for ev in events:
        if not str(ev.get("type", "")).endswith("tool.execution_start"):
            continue
        data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
        text = json.dumps(data.get("arguments", data.get("args")), default=str)
        for m in re.finditer(r"(?<![\w.])(/[\w./@-]+)", text):
            path = m.group(1)
            if path.startswith(("/usr", "/bin", "/dev", "/proc", "/etc", "/lib", "/opt", "/root/.cache", "/home")):
                continue
            if not any(path.startswith(a) for a in allowed):
                hits.append(f"{data.get('tool_name') or data.get('toolName')}: {path}")
    return sorted(set(hits))[:50]


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
    """Structural check against REVIEW_SCHEMA, including each finding; returns problems (empty = valid)."""
    problems = []
    for key in REVIEW_SCHEMA["required"]:
        if key not in review:
            problems.append(f"missing {key}")
    findings = review.get("findings")
    if not isinstance(findings, list):
        problems.append("findings must be a list")
    else:
        for i, f in enumerate(findings):
            if not isinstance(f, dict):
                problems.append(f"finding {i} is not an object"); continue
            for k in ("title", "body", "file"):
                if not isinstance(f.get(k), str):
                    problems.append(f"finding {i}.{k} must be a string")
            for k in ("line_start", "line_end"):
                if not isinstance(f.get(k), int) or isinstance(f.get(k), bool) or f.get(k, 0) < 1:
                    problems.append(f"finding {i}.{k} must be an integer >= 1")
            if not isinstance(f.get("severity"), int) or isinstance(f.get("severity"), bool) or not 1 <= f.get("severity", 0) <= 3:
                problems.append(f"finding {i}.severity must be 1..3")
            if not isinstance(f.get("confidence"), (int, float)) or isinstance(f.get("confidence"), bool) or not 0 <= f.get("confidence", -1) <= 1:
                problems.append(f"finding {i}.confidence must be 0..1")
            if f.get("category") not in FINDING_CATEGORIES:
                problems.append(f"finding {i}.category not in enum")
    if review.get("overall_correctness") not in ("correct", "incorrect", "uncertain"):
        problems.append("overall_correctness not in enum")
    oc = review.get("overall_confidence")
    if not isinstance(oc, (int, float)) or isinstance(oc, bool) or not 0 <= oc <= 1:
        problems.append("overall_confidence must be 0..1")
    rv = review.get("reviewability")
    if not isinstance(rv, dict) or not all(isinstance(rv.get(k), int) and not isinstance(rv.get(k), bool) and 1 <= rv[k] <= 5 for k in REVIEW_SCHEMA["properties"]["reviewability"]["required"]):
        problems.append("reviewability ratings must be integers 1..5")
    e = review.get("effort_to_review")
    if not isinstance(e, int) or isinstance(e, bool) or not 1 <= e <= 5:
        problems.append("effort_to_review must be 1..5")
    if not isinstance(review.get("claims_checked"), int) or isinstance(review.get("claims_checked"), bool):
        problems.append("claims_checked must be an integer")
    cv = review.get("cannot_verify")
    if not isinstance(cv, list) or not all(isinstance(x, str) for x in cv):
        problems.append("cannot_verify must be a list of strings")
    return problems


def stage_summary(res: StageResult, **extra) -> dict:
    return {
        "status": "error" if res.error else "ok",
        "turns": res.turns, "seconds": res.seconds, "usage": res.usage, "usage_by_model": res.usage_by_model,
        "error": res.error, "timed_out": res.timed_out, "resolved_model": res.resolved_model,
        "models_seen": res.models_seen, **extra,
    }


def model_mismatch(res: StageResult, expected: str | None) -> list[str]:
    if not expected:
        return []
    return [m for m in res.models_seen if m and m != expected and m.rsplit("/", 1)[-1] != expected.rsplit("/", 1)[-1]]


def visible_suite_green(ws: Path) -> bool | None:
    """Run the workspace's own test suite; None if it could not run."""
    try:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header", "tests"],
                              cwd=ws, text=True, capture_output=True, timeout=300)
    except Exception:
        return None
    return proc.returncode == 0


def write_summary(out: Path, summary: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


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
    noun = intent_cfg.get("noun", "description document")

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
        if not args.model:
            raise SystemExit("--model is required for the copilot backend so every stage runs on a known model")
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
    required_sections = list(intent_cfg.get("required_sections") or [])
    stand_in = (ModelStandIn(brief, lambda s, u: backend.ask_once(s, u, args.stand_in_model), intent_dir, dialogue_log, noun, required_sections)
                if args.stand_in == "model" else ScriptedStandIn(brief, intent_dir, dialogue_log, noun, required_sections))

    async def on_user_input(question: str, choices: list[str] | None) -> tuple[str, bool]:
        if isinstance(stand_in, ModelStandIn):
            return await stand_in.answer_question_async(question, choices)
        return stand_in.answer_question(question, choices)

    async def no_follow_up(_message: str) -> str | None:
        return None

    rendered_prompts: dict[str, str] = {}

    def save_stage(res: StageResult, suffix: str = "") -> None:
        (work / f"events-{res.stage}{suffix}.json").write_text(json.dumps(res.events, indent=1, default=str), encoding="utf-8")
        write_transcript(work / f"transcript-{res.stage}{suffix}.md", res)

    def deadline_for(cap: float | None) -> float | None:
        stage_deadline = time.time() + cap if cap else None
        if args.deadline_epoch:
            stage_deadline = min(stage_deadline or args.deadline_epoch, args.deadline_epoch)
        return stage_deadline

    # ---- manifest -------------------------------------------------------------------------------
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
        "read_only_tools": list(READ_ONLY_TOOLS),
        "builtin_agents_excluded": list(backend.excluded_builtin_agents()),
    }
    manifest["harness_git_sha"] = os.environ.get("EVAL_HARNESS_SHA") or (sh(["git", "rev-parse", "HEAD"], EVAL_ROOT, check=False).strip() or None)
    dirty_env = os.environ.get("EVAL_HARNESS_DIRTY")
    manifest["harness_dirty"] = (dirty_env == "1") if dirty_env is not None else bool(sh(["git", "status", "--porcelain", "--", str(EVAL_ROOT)], EVAL_ROOT, check=False).strip())
    manifest["harness_files"] = {
        str(p.relative_to(EVAL_ROOT)): sha256_file(p)
        for d in ("driver", "reviewer") for p in sorted((EVAL_ROOT / d).rglob("*")) if p.is_file() and "__pycache__" not in p.parts
    }
    try:
        from copilot import _cli_version  # type: ignore

        manifest["copilot_cli_version"] = getattr(_cli_version, "CLI_VERSION", None)
    except Exception:
        manifest["copilot_cli_version"] = None
    if args.intent_file:
        manifest["intent_source"] = {"path": str(Path(args.intent_file).resolve()), "sha256": sha256_file(Path(args.intent_file))}
    labels = dict(kv.split("=", 1) for kv in (args.label or []) if "=" in kv)
    for kv in os.environ.get("EVAL_LABELS", "").split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            labels.setdefault(k.strip(), v.strip())
    summary["labels"] = labels
    summary["manifest"] = manifest
    summary["status"] = "running"
    write_summary(out, summary)  # provisional: a killed driver still leaves a labelled record
    shutil.copy2(process_dir / "process.json", work / "process.json")

    # ---- workspace ------------------------------------------------------------------------------
    if not (ws / ".git").exists():
        sh(["git", "init", "-q"], ws)
    exclude = ws / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    rel_out = os.path.relpath(out, ws)
    if not rel_out.startswith(".."):
        with exclude.open("a", encoding="utf-8") as fh:
            fh.write(f"\n{rel_out}/\n")
    git_commit_all(ws, "eval: seed")
    seed_commit = git_head(ws)
    block = read_rel(process_dir, process.get("agents_block"))
    if block:
        agents_md = ws / "AGENTS.md"
        existing = agents_md.read_text(encoding="utf-8") if agents_md.exists() else ""
        agents_md.write_text((existing.rstrip() + "\n\n" if existing else "") + block, encoding="utf-8")
    if author_mode != "none":
        (ws / intent_dir).mkdir(exist_ok=True)
        (ws / intent_dir / ".gitkeep").touch()
    git_commit_all(ws, "eval: setup")
    baseline = git_head(ws)
    summary["baseline_commit"] = baseline
    intent_path: Path | None = None
    stage_model_flags: dict[str, list[str]] = {}

    try:
        # ---- author -----------------------------------------------------------------------------
        if author_mode == "frozen":
            src = Path(args.intent_file) if args.intent_file else process_dir / process["author"]["frozen_intent"]
            (ws / intent_dir).mkdir(exist_ok=True)
            first_line = next((l.strip("# ").strip() for l in brief.splitlines() if l.strip()), "change")
            dst = ws / intent_dir / f"{time.strftime('%Y-%m-%d')}-{slugify(first_line)}.md"  # convention-shaped, never the source name
            shutil.copy2(src, dst)
            commit = git_commit_all(ws, "eval: description document")
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

            def intent_state() -> tuple[bool, bool, str | None]:
                files = intent_files_in(ws, intent_dir)
                exists = bool(files)
                committed = exists and git_head(ws) != head_before and any(
                    p.startswith(intent_dir + "/") for p in git_committed_paths(ws, head_before)
                )
                text = files[-1].read_text(encoding="utf-8", errors="replace") if files else None
                return exists, committed, text

            async def next_author_turn(message: str) -> str | None:
                exists, committed, text = intent_state()
                if isinstance(stand_in, ModelStandIn):
                    return await stand_in.reply_to_message_async(message, exists, committed, text)
                return stand_in.reply_to_message(message, exists, committed, text)

            res = await backend.run_stage(
                StageSpec("author", prompt, skill_dirs=skill_dirs, custom_instructions=a.get("custom_instructions", True),
                          max_turns=args.max_author_turns, turn_timeout_sec=args.stage_timeout, deadline=deadline_for(args.cap_author)),
                ws, on_user_input=on_user_input, next_turn=next_author_turn,
            )
            stage_model_flags["author"] = model_mismatch(res, args.model)
            intent_path, candidates = resolve_intent(ws, intent_dir, head_before)

            def outside(p: str) -> bool:
                return not p.startswith(intent_dir + "/") and p != intent_dir
            stray_uncommitted = [p for p in git_dirty_paths(ws) if outside(p)]
            stray_committed = [p for p in git_committed_paths(ws, head_before) if outside(p)]
            if stray_uncommitted or stray_committed:
                revert_paths(ws, sorted(set(stray_uncommitted) | set(stray_committed)), head_before)
            commit = git_commit_all(ws, "eval: description document")
            if intent_path and len(candidates) > 1:
                outcome = "multiple_files"
            elif intent_path and stand_in.approved:
                outcome = "approved"
            elif intent_path:
                outcome = "unapproved_file"
            else:
                outcome = "no_file"
            summary["stages"]["author"] = stage_summary(
                res, mode="skill", intent_file=str(intent_path.relative_to(ws)) if intent_path else None,
                intent_candidates=candidates,
                intent_sha256=sha256_file(intent_path) if intent_path else None, commit=commit,
                author_outcome=outcome,
                author_contamination={"uncommitted": stray_uncommitted, "committed": stray_committed},
                exchanges=len(stand_in.exchanges),
                approval_cues=[e.cue for e in stand_in.exchanges if e.cue and e.cue.startswith(("approve", "ask_user:approve", "model:approve"))],
                model_mismatch=stage_model_flags["author"],
            )
            save_stage(res)

        # ---- implement --------------------------------------------------------------------------
        stand_in.stage = "implement"
        impl = process["implement"]
        system_append = read_rel(process_dir, impl.get("system_append"))
        source = f"the {noun} at `{intent_path.relative_to(ws)}`" if intent_path else "the brief below"
        include_brief = impl.get("include_brief", True) or intent_path is None
        template = read_rel(process_dir, impl.get("prompt_file")) or DEFAULT_IMPLEMENT_PROMPT
        prompt = template.format(source=source, brief_section=BRIEF_SECTION.format(brief=brief) if include_brief else "", brief=brief)
        rendered_prompts["implement"] = prompt
        head_before_impl = git_head(ws)
        nudges = {"n": 0}
        turn_log: list[dict] = []

        async def next_impl_turn(message: str) -> str | None:
            """One objective continuation rule for every condition: continue while the visible suite is
            red or nothing in the code tree changed, up to --max-implement-nudges times."""
            changed = [p for p in git_dirty_paths(ws) + git_committed_paths(ws, head_before_impl) if p.startswith(CODE_DIRS)]
            green = visible_suite_green(ws)
            done = bool(changed) and green is True
            reason = "complete" if done else ("suite_red" if changed else "no_code_change")
            if not done and nudges["n"] < args.max_implement_nudges:
                nudges["n"] += 1
                turn_log.append({"end_reason": reason, "action": "nudge"})
                return IMPLEMENT_NUDGE
            turn_log.append({"end_reason": reason, "action": "stop"})
            return None

        res = await backend.run_stage(
            StageSpec("implement", prompt, system_append=system_append, custom_instructions=impl.get("custom_instructions", True),
                      max_turns=1 + args.max_implement_nudges, turn_timeout_sec=args.stage_timeout, deadline=deadline_for(args.cap_implement)),
            ws, on_user_input=on_user_input, next_turn=next_impl_turn,
        )
        stage_model_flags["implement"] = model_mismatch(res, args.model)
        implement_messages = [m for m in res.messages if m.strip()] or ([res.final_message] if res.final_message.strip() else [])
        head_after_agent = git_head(ws)
        stash_left = git_stash_count(ws)
        if stash_left:
            sh(["git", "stash", "drop", "-q"], ws, check=False)  # recorded; the implementation is what was committed/left in the tree
        impl_commit = git_commit_all(ws, "eval: implementation", allow_empty=True)
        summary["impl_commit"] = impl_commit
        summary["stages"]["implement"] = stage_summary(
            res, commit=impl_commit, used_intent=intent_path is not None, include_brief=include_brief,
            agent_committed=head_after_agent != head_before_impl, turns_detail=turn_log, stash_left=stash_left,
            model_mismatch=stage_model_flags["implement"],
        )
        save_stage(res)

        # ---- artifacts the reviewers may see ---------------------------------------------------
        # The artifact may have been moved or deleted by the implementer: re-resolve and record it.
        if intent_path is not None and not intent_path.exists():
            new_path, _ = resolve_intent(ws, intent_dir, None)
            summary["stages"]["implement"]["intent_removed_by_implementer"] = True
            summary["stages"]["implement"]["intent_relocated_to"] = str(new_path.relative_to(ws)) if new_path else None
            intent_path = new_path
        code_only = ["--", ".", f":(exclude){intent_dir}"]
        diff = sh(["git", "diff", f"{baseline}..HEAD", *code_only], ws, check=False)
        (work / "diff.patch").write_text(diff, encoding="utf-8")
        (work / "diff-with-artifact.patch").write_text(sh(["git", "diff", f"{baseline}..HEAD"], ws, check=False), encoding="utf-8")
        summary["diff_shortstat"] = sh(["git", "diff", "--shortstat", f"{baseline}..HEAD"], ws, check=False).strip()
        summary["diff_shortstat_code_only"] = sh(["git", "diff", "--shortstat", f"{baseline}..HEAD", *code_only], ws, check=False).strip()
        sections = ["# Change description", ""]
        try:
            if intent_path is not None:
                sections += [f"## Description document (`{intent_path.relative_to(ws)}`)", "", intent_path.read_text(encoding="utf-8").strip(), ""]
        except Exception as exc:  # never let the description abort the reviews
            sections += ["## Description document", "", f"(unreadable: {exc})", ""]
        sections += ["## Implementer summary", ""]
        for i, m in enumerate(implement_messages, 1):
            sections += [f"### Turn {i}", "", m.strip(), ""]
        if not implement_messages:
            sections += ["(none)", ""]
        (work / "change_description.md").write_text("\n".join(sections), encoding="utf-8")

        # ---- process review (owned by the process version) -------------------------------------
        rv = process.get("review")
        if rv and not args.skip_reviews:
            stand_in.stage = "review"
            template = read_rel(process_dir, rv.get("prompt_file")) or DEFAULT_PROCESS_REVIEW_PROMPT
            intent_ref = str(intent_path.relative_to(ws)) if intent_path else "(no file was produced)"
            prompt = template.format(baseline=baseline, intent_path=intent_ref, noun=noun,
                                     claim_sections=", ".join(f"`## {c}`" for c in intent_cfg.get("claim_sections", [])) or "the claims")
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
                                                        reset_paths=dirty, head_moved=moved, model_mismatch=model_mismatch(res, args.model))
            save_stage(res)

        # ---- fixed review (owned by the harness; identical for every condition) -----------------
        if not args.skip_reviews:
            stand_in.stage = "fixed_review"
            review_input = Path(tempfile.mkdtemp(prefix="review-input-"))
            (review_input / "requirements.md").write_text(brief, encoding="utf-8")
            shutil.copy2(work / "diff.patch", review_input / "diff.patch")
            shutil.copy2(work / "change_description.md", review_input / "change_description.md")
            prompt = FIXED_REVIEW_PROMPT.format(review_input=review_input)
            rendered_prompts["fixed_review"] = FIXED_REVIEW_PROMPT.format(review_input="<review_input>")
            summary["review_input_dir"] = str(review_input)

            # Blind the reviewer to process-owned context in the checkout: AGENTS.md back to its seed
            # content (uncommitted; reset afterwards) and the process directory out of reach.
            agents_md = ws / "AGENTS.md"
            agents_hidden = False
            if block:
                if git_tracked_at(ws, seed_commit, "AGENTS.md"):
                    sh(["git", "checkout", seed_commit, "--", "AGENTS.md"], ws, check=False)
                elif agents_md.exists():
                    agents_md.unlink()
                agents_hidden = True
            hidden_process_dir = process_dir.with_name(process_dir.name + ".hidden-during-review")
            process_hidden = False
            try:
                process_dir.rename(hidden_process_dir)
                process_hidden = True
            except OSError:
                pass

            attempts: list[dict] = []
            review: dict | None = None
            problems: list[str] = ["not run"]
            try:
                for attempt in range(1, args.max_review_attempts + 1):
                    retried = {"n": 0}

                    async def next_fixed_review_turn(message: str) -> str | None:
                        if parse_review_json(message) is None and retried["n"] == 0:
                            retried["n"] += 1
                            return JSON_ONLY_RETRY
                        return None

                    res = await backend.run_stage(
                        StageSpec("fixed_review", prompt, system_append=FIXED_REVIEWER_PROMPT_PATH.read_text(encoding="utf-8"),
                                  custom_instructions=False, read_only=True, response_schema=REVIEW_SCHEMA,
                                  model=args.reviewer_model, extra_dirs=[str(review_input)], max_turns=2,
                                  turn_timeout_sec=args.stage_timeout, deadline=deadline_for(args.cap_fixed_review)),
                        ws, on_user_input=on_user_input, next_turn=next_fixed_review_turn,
                    )
                    suffix = "" if attempt == 1 else f"-attempt{attempt}"
                    (work / f"review_raw{suffix}.md").write_text(res.final_message, encoding="utf-8")
                    save_stage(res, suffix)
                    candidate = parse_review_json(res.final_message)
                    problems = validate_review(candidate) if candidate is not None else ["unparseable"]
                    oob = out_of_bounds_reads(res.events, [str(ws), str(review_input)])
                    attempts.append({"attempt": attempt, "parsed": candidate is not None, "valid": not problems, "problems": problems,
                                     "json_retries": retried["n"] + res.retries, "error": res.error, "timed_out": res.timed_out,
                                     "seconds": res.seconds, "usage": res.usage, "out_of_bounds_reads": oob,
                                     "model_mismatch": model_mismatch(res, args.reviewer_model or args.model)})
                    dirty, moved = git_reset_to(ws, impl_commit)
                    attempts[-1]["reset_paths"] = [p for p in dirty if not (agents_hidden and p == "AGENTS.md")]
                    attempts[-1]["head_moved"] = moved
                    if agents_hidden and not block:
                        pass
                    if agents_hidden:  # re-apply the blind for the next attempt (reset restored it)
                        if git_tracked_at(ws, seed_commit, "AGENTS.md"):
                            sh(["git", "checkout", seed_commit, "--", "AGENTS.md"], ws, check=False)
                        elif agents_md.exists():
                            agents_md.unlink()
                    if candidate is not None and not problems:
                        review = candidate
                        review["_meta"] = {"reviewer_model": res.resolved_model or args.reviewer_model or args.model,
                                           "usage": res.usage, "seconds": res.seconds, "valid": True, "attempt": attempt}
                        break
                    if res.error and not res.timed_out and attempt == 1 and "SystemExit" in (res.error or ""):
                        break
            finally:
                git_reset_to(ws, impl_commit)
                if process_hidden:
                    hidden_process_dir.rename(process_dir)
            if review is None:
                review = {"_meta": {"valid": False, "missing": True, "attempts": len(attempts), "problems": problems}}
            (work / "review.json").write_text(json.dumps(review, indent=2), encoding="utf-8")
            shutil.copytree(review_input, work / "review-input", dirs_exist_ok=True)
            last = attempts[-1] if attempts else {}
            summary["stages"]["fixed_review"] = {
                "status": "ok" if review.get("_meta", {}).get("valid") else "missing",
                "missing": not review.get("_meta", {}).get("valid", False),
                "attempts": attempts, "verdict": review.get("overall_correctness"),
                "findings": len(review.get("findings", []) or []), "agents_md_hidden": agents_hidden,
                "process_dir_hidden": process_hidden, "seconds": sum(a.get("seconds", 0) or 0 for a in attempts),
                "usage": {k: sum((a.get("usage") or {}).get(k, 0) for a in attempts) for k in {k for a in attempts for k in (a.get("usage") or {})}},
                "timed_out": any(a.get("timed_out") for a in attempts), "error": last.get("error"),
                "out_of_bounds_reads": sorted({h for a in attempts for h in a.get("out_of_bounds_reads", [])}),
                "model_mismatch": sorted({m for a in attempts for m in a.get("model_mismatch", [])}),
            }
    finally:
        await backend.close()
        summary["rendered_prompts_sha256"] = {k: sha256_text(v) for k, v in rendered_prompts.items()}
        (work / "rendered_prompts.json").write_text(json.dumps(rendered_prompts, indent=1), encoding="utf-8")
        summary["author_exchanges"] = len(stand_in.exchanges)
        summary["model_mismatch_any"] = sorted({m for v in stage_model_flags.values() for m in v} | set(summary["stages"].get("fixed_review", {}).get("model_mismatch", [])))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", required=True)
    p.add_argument("--process", required=True, help="directory containing process.json")
    p.add_argument("--brief", required=True, help="markdown file with the author's brief")
    p.add_argument("--out", required=True, help="final artifact directory, copied at the end (the verifier reads it)")
    p.add_argument("--work-dir", help="where artifacts live during the run; default: a temp dir outside the workspace")
    p.add_argument("--model", default=os.environ.get("EVAL_MODEL"), help="required for the copilot backend")
    p.add_argument("--reviewer-model", default=os.environ.get("EVAL_REVIEWER_MODEL"), help="model for the fixed reviewer; pin one from another vendor")
    p.add_argument("--stand-in-model", default=os.environ.get("EVAL_STAND_IN_MODEL"), help="model for the model stand-in; defaults to --model")
    p.add_argument("--allow-same-reviewer", action="store_true", help="permit the fixed reviewer to share the implementer's model")
    p.add_argument("--provider-json", default=os.environ.get("EVAL_PROVIDER_JSON"), help="BYOK ProviderConfig as JSON")
    p.add_argument("--backend", choices=["copilot", "fake"], default="copilot")
    p.add_argument("--fake-reference", help="fake backend: directory copied in as the implementation")
    p.add_argument("--stand-in", choices=["scripted", "model"], default="scripted")
    p.add_argument("--intent-file", help="freeze this artifact: commit it as the intent and skip the author dialogue")
    p.add_argument("--skip-reviews", action="store_true", help="stop after implementation")
    p.add_argument("--label", action="append", help="key=value recorded in summary.json (repeatable); e.g. --label intent=A --label guidance=v1")
    p.add_argument("--max-author-turns", type=int, default=12)
    p.add_argument("--max-implement-nudges", type=int, default=2)
    p.add_argument("--max-review-attempts", type=int, default=3, help="fresh fixed-review sessions before recording the review as missing")
    p.add_argument("--stage-timeout", type=float, default=3600.0, help="seconds to wait for one turn")
    p.add_argument("--cap-author", type=float, default=float(os.environ.get("EVAL_CAP_AUTHOR", 1800)))
    p.add_argument("--cap-implement", type=float, default=float(os.environ.get("EVAL_CAP_IMPLEMENT", 3600)), help="same cap for every condition")
    p.add_argument("--cap-review", type=float, default=float(os.environ.get("EVAL_CAP_REVIEW", 900)))
    p.add_argument("--cap-fixed-review", type=float, default=float(os.environ.get("EVAL_CAP_FIXED_REVIEW", 900)))
    p.add_argument("--deadline-epoch", type=float, default=None, help="absolute unix time by which every stage must have started")
    p.add_argument("--fail-on-error", action="store_true", help="exit 1 when any stage errored (default: exit 0, status in summary.json)")
    args = p.parse_args()

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    summary: dict = {"process": None, "stages": {}, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "backend": args.backend, "status": "running"}
    exit_code = 0
    try:
        summary["process"] = json.loads((Path(args.process) / "process.json").read_text(encoding="utf-8")).get("name")
        write_summary(out, summary)
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
        write_summary(out, summary)
        print(json.dumps(summary, indent=2, default=str))
        if failed and args.fail_on_error and exit_code == 0:
            exit_code = 1
    return exit_code if (args.fail_on_error or exit_code == 2) else 0


if __name__ == "__main__":
    sys.exit(main())
