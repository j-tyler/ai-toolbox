"""Backends that run one agent stage.

``CopilotBackend`` drives the GitHub Copilot SDK. ``FakeBackend`` produces plausible artifacts
without a model so the pipeline, stand-in loop, and grading can be exercised offline.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

UserInputFn = Callable[[str, list[str] | None], Awaitable[tuple[str, bool]]]


@dataclass
class StageSpec:
    """Everything a stage needs from the backend, with harness-neutral defaults."""

    name: str
    prompt: str
    system_append: str | None = None
    skill_dirs: list[str] = field(default_factory=list)
    custom_instructions: bool = True  # load AGENTS.md etc. from the workspace
    read_only: bool = False
    response_schema: dict[str, Any] | None = None
    model: str | None = None
    extra_dirs: list[str] = field(default_factory=list)  # readable directories outside the workspace
    max_turns: int = 1
    turn_timeout_sec: float = 3600.0
    deadline: float | None = None  # absolute time.time() after which no new turn starts


@dataclass
class StageResult:
    stage: str
    final_message: str
    turns: int
    events: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    started: float = 0.0
    finished: float = 0.0
    error: str | None = None
    timed_out: bool = False
    resolved_model: str | None = None
    retries: int = 0
    messages: list[str] = field(default_factory=list)  # every turn's final message, in order
    usage_by_model: dict[str, dict[str, int]] = field(default_factory=dict)
    models_seen: list[str] = field(default_factory=list)

    @property
    def seconds(self) -> float:
        return round(self.finished - self.started, 1)


class Backend:
    async def run_stage(
        self,
        spec: StageSpec,
        workspace: Path,
        *,
        on_user_input: UserInputFn,
        next_turn: Callable[[str], Awaitable[str | None]],
    ) -> StageResult:
        raise NotImplementedError

    async def ask_once(self, system_prompt: str, user_prompt: str, model: str | None = None) -> str:
        raise NotImplementedError

    async def close(self) -> None:
        pass

    def versions(self) -> dict[str, str]:
        return {}

    def excluded_builtin_agents(self) -> tuple[str, ...]:
        return BUILTIN_AGENTS


def _event_to_dict(ev: Any) -> dict[str, Any]:
    for attr in ("to_dict", "model_dump"):
        fn = getattr(ev, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    out: dict[str, Any] = {"type": str(getattr(ev, "type", type(ev).__name__))}
    data = getattr(ev, "data", None)
    if data is not None:
        fn = getattr(data, "to_dict", None)
        out["data"] = fn() if callable(fn) else repr(data)
    return out


USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "reasoning_tokens")
READ_ONLY_TOOLS = ("grep", "glob", "view", "bash", "read_bash", "stop_bash", "lsp")
# Built-in sub-agents of the pinned runtime (cli 1.0.100 definitions/*.agent.yaml). Some are pinned to
# other models (explore: gpt-5.6-luna/gpt-5.4-mini; research: claude-sonnet-5), which would break the
# "same model for every condition" premise, so every stage excludes all of them.
BUILTIN_AGENTS = ("code-review", "explore", "rem-agent", "research", "rubber-duck", "security-review", "task")
STRUCTURED_OUTPUT_MISSING = "Run completed without a structured assistant response"


def _camel(key: str) -> str:
    head, *rest = key.split("_")
    return head + "".join(w.capitalize() for w in rest)


def _usage_from_events(events: list[dict[str, Any]]) -> dict[str, int]:
    """Sum the per-call usage counters from ``assistant.usage`` events (not the limit fields)."""
    totals: dict[str, int] = {}
    calls = 0
    for ev in events:
        if str(ev.get("type", "")) != "assistant.usage":
            continue
        data = ev.get("data") or {}
        if not isinstance(data, dict):
            continue
        calls += 1
        for key in USAGE_KEYS:
            v = data.get(key, data.get(_camel(key)))
            if isinstance(v, (int, float)):
                totals[key] = totals.get(key, 0) + int(v)
    if calls:
        totals["model_calls"] = calls
    return totals


def _usage_by_model(events: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for ev in events:
        if str(ev.get("type", "")) != "assistant.usage":
            continue
        data = ev.get("data") or {}
        if not isinstance(data, dict):
            continue
        model = str(data.get("model") or "unknown")
        bucket = out.setdefault(model, {})
        bucket["model_calls"] = bucket.get("model_calls", 0) + 1
        for key in USAGE_KEYS:
            v = data.get(key, data.get(_camel(key)))
            if isinstance(v, (int, float)):
                bucket[key] = bucket.get(key, 0) + int(v)
    return out


def _resolved_model(events: list[dict[str, Any]]) -> str | None:
    for ev in events:
        t = str(ev.get("type", ""))
        data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
        if t in ("session.start", "session.model_change", "assistant.usage") and data.get("model"):
            return str(data["model"])
    return None


def _message_text(ev: Any) -> str:
    if ev is None:
        return ""
    data = getattr(ev, "data", None)
    content = getattr(data, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(ev, dict):
        return str((ev.get("data") or {}).get("content", ""))
    return str(ev)


class CopilotBackend(Backend):
    """Runs each stage as one Copilot SDK session in the workspace."""

    def __init__(self, model: str | None, provider: dict | None = None, log_level: str = "info"):
        from copilot import CopilotClient

        self.model = model
        self.provider = provider
        kwargs: dict[str, Any] = {"log_level": log_level}
        token = os.environ.get("COPILOT_GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            kwargs["github_token"] = token
        self._client = CopilotClient(**kwargs)
        self._started = False

    def versions(self) -> dict[str, str]:
        out: dict[str, str] = {}
        try:
            from importlib.metadata import version

            out["github-copilot-sdk"] = version("github-copilot-sdk")
        except Exception:
            pass
        return out

    async def _ensure(self) -> None:
        if not self._started:
            await self._client.start()
            self._started = True

    async def close(self) -> None:
        if self._started:
            await self._client.stop()
            self._started = False

    async def ask_once(self, system_prompt: str, user_prompt: str, model: str | None = None) -> str:
        from copilot.session import PermissionHandler

        await self._ensure()
        session = await self._client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model=model or self.model,
            provider=self.provider,
            system_message={"mode": "replace", "content": system_prompt},
            available_tools=[],
            skip_custom_instructions=True,
        )
        try:
            ev = await session.send_and_wait(user_prompt, timeout=300)
            return _message_text(ev)
        finally:
            await session.disconnect()

    async def run_stage(self, spec: StageSpec, workspace: Path, *, on_user_input, next_turn) -> StageResult:
        from copilot.session import PermissionHandler

        result = StageResult(stage=spec.name, final_message="", turns=0, started=time.time())
        live_events: list[dict[str, Any]] = []

        async def user_input_handler(request: dict, _invocation: dict) -> dict:
            answer, freeform = await on_user_input(request.get("question", ""), request.get("choices"))
            return {"answer": answer, "wasFreeform": freeform}

        def on_event(ev: Any) -> None:
            try:
                live_events.append(_event_to_dict(ev))
            except Exception:
                pass

        session = None
        try:
            await self._ensure()
            session_kwargs: dict[str, Any] = dict(
                on_permission_request=PermissionHandler.approve_all,
                model=spec.model or self.model,
                provider=self.provider,
                working_directory=str(workspace),
                on_user_input_request=user_input_handler,
                enable_file_change_tracking=True,
                skip_custom_instructions=not spec.custom_instructions,
                on_event=on_event,
                excluded_builtin_agents=list(BUILTIN_AGENTS),
            )
            if spec.system_append:
                session_kwargs["system_message"] = {"mode": "append", "content": spec.system_append}
            if spec.skill_dirs:
                session_kwargs["skill_directories"] = spec.skill_dirs
            if spec.extra_dirs:
                session_kwargs["additional_directories"] = spec.extra_dirs
            if spec.read_only:
                # Reviewer sessions get the read-only tool set the bundled runtime's own "explore" agent
                # declares (definitions/explore.agent.yaml in cli 1.0.100): no edit/create tools; bash
                # stays so the reviewer can run tests. The driver also resets the working tree after a
                # read-only stage and records anything that changed.
                session_kwargs["available_tools"] = list(READ_ONLY_TOOLS)
            session = await self._client.create_session(**session_kwargs)

            message = spec.prompt
            while True:
                if spec.deadline is not None and time.time() >= spec.deadline:
                    result.timed_out = True
                    result.error = "stage deadline reached before turn"
                    break
                timeout = spec.turn_timeout_sec
                if spec.deadline is not None:
                    timeout = max(1.0, min(timeout, spec.deadline - time.time()))
                result.turns += 1
                send_kwargs: dict[str, Any] = {"timeout": timeout}
                if spec.response_schema is not None:
                    send_kwargs["response_schema"] = spec.response_schema
                try:
                    ev = await session.send_and_wait(message, **send_kwargs)
                except (asyncio.TimeoutError, TimeoutError) as exc:
                    result.timed_out = True
                    result.error = f"turn timeout after {timeout:.0f}s: {exc}"
                    try:
                        await session.abort()
                    except Exception:
                        pass
                    break
                except RuntimeError as exc:
                    if spec.response_schema is not None and str(exc).startswith(STRUCTURED_OUTPUT_MISSING):
                        # The model answered in prose instead of the schema; hand an empty message to the
                        # driver's next_turn so it can ask once more for JSON only.
                        ev = None
                        result.retries += 1
                    else:
                        raise
                result.final_message = _message_text(ev)
                result.messages.append(result.final_message)
                if result.turns >= spec.max_turns:
                    break
                follow_up = await next_turn(result.final_message)
                if follow_up is None:
                    break
                message = follow_up
        except Exception as exc:  # keep partial artifacts
            result.error = f"{type(exc).__name__}: {exc}"
            if session is not None:
                try:
                    await session.abort()
                except Exception:
                    pass
        finally:
            events: list[dict[str, Any]] = []
            if session is not None:
                try:
                    events = [_event_to_dict(e) for e in await session.get_events()]
                except Exception as exc:
                    events = [{"type": "harness.error", "data": {"message": f"get_events failed: {exc}"}}]
                try:
                    await session.disconnect()
                except Exception:
                    pass
            # Prefer the full history; fall back to what we captured live (covers timeouts/disconnects).
            result.events = events if len(events) >= len(live_events) else live_events
            result.usage = _usage_from_events(result.events)
            result.usage_by_model = _usage_by_model(result.events)
            result.models_seen = sorted(result.usage_by_model)
            result.resolved_model = _resolved_model(result.events)
            result.finished = time.time()
        return result


class FakeBackend(Backend):
    """Offline stand-in for the model. Writes a template intent, asks one question, and, when given a
    directory of reference files, copies them in as the "implementation"."""

    def __init__(self, reference_dir: Path | None, intent_dir: str = "change-intent"):
        self.reference_dir = reference_dir
        self.intent_dir = intent_dir

    def versions(self) -> dict[str, str]:
        return {"backend": "fake"}

    async def ask_once(self, system_prompt: str, user_prompt: str, model: str | None = None) -> str:
        return "Yes, let's do that."

    async def run_stage(self, spec: StageSpec, workspace: Path, *, on_user_input, next_turn) -> StageResult:
        result = StageResult(stage=spec.name, final_message="", turns=0, started=time.time())
        events: list[dict[str, Any]] = [{"type": "fake.prompt", "data": {"content": spec.prompt[:500]}}]
        if spec.name == "review":
            result.turns += 1
            result.final_message = FAKE_PROCESS_REVIEW
        elif spec.name == "fixed_review":
            result.turns += 1
            has_tests = any((workspace / "tests").glob("test_*.py"))
            result.final_message = json.dumps(FAKE_REVIEW if has_tests else {**FAKE_REVIEW, "overall_correctness": "uncertain"})
        elif spec.name == "author":
            # Mirrors a real skill: confirm the brief, write an UNCOMMITTED draft, ask an open question,
            # get asked for the file, present it, get approval, commit, then ask whether to implement.
            # The driver's stop rule must only end the dialogue after the commit.
            result.turns += 1
            ans, _ = await on_user_input("Is this brief accurate?", ["Yes, proceed", "No, let me restate"])
            events.append({"type": "fake.ask_user", "data": {"answer": ans}})
            target = workspace / self.intent_dir
            target.mkdir(parents=True, exist_ok=True)
            draft = target / f"{time.strftime('%Y-%m-%d')}-ledger-budgets.md"
            draft.write_text(FAKE_INTENT, encoding="utf-8")
            script = [
                "I explored the code and drafted a file. Should I also refactor the CLI while I am here?",
                "Here is the complete proposed document:\n\n" + FAKE_INTENT + "\n\nDo you approve?",
            ]
            result.messages = []
            for msg in script:
                result.messages.append(msg)
                follow = await next_turn(msg)
                result.turns += 1
                events.append({"type": "fake.message", "data": {"content": msg[:200], "reply": follow}})
                if follow is None:
                    break
            subprocess.run(["git", "add", "-A"], cwd=workspace, check=False, capture_output=True)
            subprocess.run(["git", "commit", "-q", "-m", "Add description document"], cwd=workspace, check=False, capture_output=True)
            msg = "Committed as " + str(draft.relative_to(workspace)) + ". Shall I proceed with the implementation?"
            follow = await next_turn(msg)
            result.turns += 1
            events.append({"type": "fake.message", "data": {"content": msg, "reply": follow}})
            result.final_message = msg
        else:
            result.turns += 1
            if self.reference_dir and self.reference_dir.exists():
                for src in self.reference_dir.rglob("*"):
                    if src.is_file():
                        dst = workspace / src.relative_to(self.reference_dir)
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)
                (workspace / "tests" / "test_fake_added.py").write_text(
                    "def test_fake_added():\n    assert True\n", encoding="utf-8"
                )
                result.final_message = "Implemented from the reference solution (fake backend)."
            else:
                result.final_message = "Fake backend: no reference directory, nothing implemented."
            result.messages = [result.final_message]
        result.events = events
        result.usage = {"input_tokens": 0, "output_tokens": 0}
        result.finished = time.time()
        return result


FAKE_PROCESS_REVIEW = """# Review against change-intent

| Claim | Assessment | Basis |
| --- | --- | --- |
| AC1 budget status output | met | tests/test_budget.py::test_status_text passes; assertions cover sort, remaining, OVER |
| AC2 recur apply idempotent | met | tests/test_recurring.py::test_apply_idempotent; second run asserts "applied 0" |
| AC3 import de-duplication | met | tests/test_import.py covers in-file and against-ledger duplicates |
| AC4 report json | met | tests/test_report.py::test_report_json compares full object |
| INV existing commands unchanged | met | seed tests unchanged and passing; cli.py add/list bodies untouched in diff |
| INV ledger CSV format unchanged | cannot verify | no test pins the header row; store.py unchanged in diff, inferred only |

## Findings

None blocking. The intent folder carries exactly one current intent and no amendments.
"""

FAKE_REVIEW = {
    "summary": "The change implements budgets, recurring rules, CSV import, and a report as described; tests cover each command and pass.",
    "findings": [
        {"title": "Import parses amounts before validating all rows", "body": "A malformed amount on row N leaves earlier rows unsaved but the error message does not say which row.", "file": "ledger/importer.py", "line_start": 50, "line_end": 62, "severity": 1, "confidence": 0.85, "category": "functionality"}
    ],
    "overall_correctness": "correct",
    "overall_confidence": 0.9,
    "reviewability": {"description_adequacy": 4, "coherence": 4, "verifiability": 5, "size_appropriateness": 3, "clarity": 4},
    "effort_to_review": 3,
    "claims_checked": 8,
    "cannot_verify": ["Behaviour when budgets.csv is edited by hand with an invalid row"],
}

FAKE_INTENT = """# Change intent: ledger budgets, recurring, import, report

## Outcomes
- A user can set monthly limits per category and see spending against them.
- Recurring expenses are recorded once and materialised idempotently.
- Bank CSV exports import without duplicates.
- A monthly report shows spending per category against budget.

## Why
ledger only records and lists transactions; people cannot budget with it.

## Constraints
- Standard library only.
- Money remains integer cents end to end.
- All state lives in plain text files beside the ledger file.

## Acceptance criteria
- `budget status --month M` lists budgeted categories sorted by name with spent, limit, remaining, and OVER.
- `recur apply --through D` run twice creates occurrences once.
- `import` skips rows duplicating date, amount, and note already present.
- `report --month M --format json` returns month, total_cents, categories.

## Invariants
- Existing commands, flags, and output formats are unchanged.
- The ledger CSV format is unchanged.

## Out of scope
- Any new storage format or dependency.
"""
