"""Backends that run one agent stage.

``CopilotBackend`` drives the GitHub Copilot SDK. ``FakeBackend`` produces plausible artifacts
without a model so the pipeline, stand-in loop, and grading can be exercised offline.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

UserInputFn = Callable[[str, list[str] | None], Awaitable[tuple[str, bool]]]


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

    @property
    def seconds(self) -> float:
        return round(self.finished - self.started, 1)


class Backend:
    async def run_stage(
        self,
        stage: str,
        workspace: Path,
        prompt: str,
        *,
        system_append: str | None,
        skill_dirs: list[str],
        on_user_input: UserInputFn,
        next_turn: Callable[[str], Awaitable[str | None]],
        max_turns: int,
        timeout_sec: float,
    ) -> StageResult:
        raise NotImplementedError

    async def ask_once(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    async def close(self) -> None:
        pass


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


def _usage_from_events(events: list[dict[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for ev in events:
        t = str(ev.get("type", ""))
        if "usage" not in t:
            continue
        data = ev.get("data") or {}
        if not isinstance(data, dict):
            continue
        for k, v in data.items():
            if isinstance(v, int) and "token" in k.lower():
                totals[k] = totals.get(k, 0) + v
    return totals


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

    async def _ensure(self) -> None:
        if not self._started:
            await self._client.start()
            self._started = True

    async def close(self) -> None:
        if self._started:
            await self._client.stop()
            self._started = False

    async def ask_once(self, system_prompt: str, user_prompt: str) -> str:
        from copilot.session import PermissionHandler

        await self._ensure()
        session = await self._client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model=self.model,
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

    async def run_stage(self, stage, workspace, prompt, *, system_append, skill_dirs, on_user_input, next_turn, max_turns, timeout_sec) -> StageResult:
        from copilot.session import PermissionHandler

        await self._ensure()
        result = StageResult(stage=stage, final_message="", turns=0, started=time.time())

        async def user_input_handler(request: dict, _invocation: dict) -> dict:
            answer, freeform = await on_user_input(request.get("question", ""), request.get("choices"))
            return {"answer": answer, "wasFreeform": freeform}

        session_kwargs: dict[str, Any] = dict(
            on_permission_request=PermissionHandler.approve_all,
            model=self.model,
            provider=self.provider,
            working_directory=str(workspace),
            on_user_input_request=user_input_handler,
            enable_file_change_tracking=True,
        )
        if system_append:
            session_kwargs["system_message"] = {"mode": "append", "content": system_append}
        if skill_dirs:
            session_kwargs["skill_directories"] = skill_dirs
        session = await self._client.create_session(**session_kwargs)
        try:
            message = prompt
            while True:
                result.turns += 1
                ev = await session.send_and_wait(message, timeout=timeout_sec)
                result.final_message = _message_text(ev)
                if result.turns >= max_turns:
                    break
                follow_up = await next_turn(result.final_message)
                if follow_up is None:
                    break
                message = follow_up
        except Exception as exc:  # keep partial artifacts
            result.error = f"{type(exc).__name__}: {exc}"
        finally:
            try:
                result.events = [_event_to_dict(e) for e in session.get_events()]
            except Exception as exc:
                result.events = [{"type": "harness.error", "data": f"get_events failed: {exc}"}]
            result.usage = _usage_from_events(result.events)
            await session.disconnect()
            result.finished = time.time()
        return result


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


class FakeBackend(Backend):
    """Offline stand-in for the model. Writes a template intent, asks one question, and, when given a
    directory of reference files, copies them in as the "implementation"."""

    def __init__(self, reference_dir: Path | None, intent_dir: str = "change-intent"):
        self.reference_dir = reference_dir
        self.intent_dir = intent_dir

    async def ask_once(self, system_prompt: str, user_prompt: str) -> str:
        return "Yes, let's do that."

    async def run_stage(self, stage, workspace, prompt, *, system_append, skill_dirs, on_user_input, next_turn, max_turns, timeout_sec) -> StageResult:
        result = StageResult(stage=stage, final_message="", turns=0, started=time.time())
        events: list[dict[str, Any]] = [{"type": "fake.prompt", "data": {"content": prompt[:500]}}]
        if stage == "author":
            result.turns += 1
            ans, _ = await on_user_input("Is this brief accurate?", ["Yes, proceed", "No, let me restate"])
            events.append({"type": "fake.ask_user", "data": {"answer": ans}})
            msg = "Here is the proposed intent. Do you approve?"
            follow = await next_turn(msg)
            result.turns += 1
            events.append({"type": "fake.message", "data": {"content": msg, "reply": follow}})
            target = workspace / self.intent_dir
            target.mkdir(parents=True, exist_ok=True)
            (target / f"{time.strftime('%Y-%m-%d')}-ledger-budgets.md").write_text(FAKE_INTENT, encoding="utf-8")
            result.final_message = "Approved intent written to change-intent/ and committed."
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
        result.events = events
        result.usage = {"input_tokens": 0, "output_tokens": 0}
        result.finished = time.time()
        return result


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
