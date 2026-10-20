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
        response_schema: dict[str, Any] | None = None,
        read_only: bool = False,
        model: str | None = None,
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


USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "reasoning_tokens")


def _usage_from_events(events: list[dict[str, Any]]) -> dict[str, int]:
    """Sum the per-call usage counters from ``assistant.usage`` events (not the limit fields)."""
    totals: dict[str, int] = {}
    calls = 0
    for ev in events:
        t = str(ev.get("type", ""))
        if "usage" not in t:
            continue
        data = ev.get("data") or {}
        if not isinstance(data, dict):
            continue
        calls += 1
        for key in USAGE_KEYS:
            v = data.get(key)
            if v is None:
                v = data.get("".join(w.capitalize() if i else w for i, w in enumerate(key.split("_"))))  # camelCase from to_dict
            if isinstance(v, (int, float)):
                totals[key] = totals.get(key, 0) + int(v)
    if calls:
        totals["model_calls"] = calls
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

    async def run_stage(self, stage, workspace, prompt, *, system_append, skill_dirs, on_user_input, next_turn, max_turns, timeout_sec, response_schema=None, read_only=False, model=None) -> StageResult:
        from copilot.session import PermissionHandler

        await self._ensure()
        result = StageResult(stage=stage, final_message="", turns=0, started=time.time())

        async def user_input_handler(request: dict, _invocation: dict) -> dict:
            answer, freeform = await on_user_input(request.get("question", ""), request.get("choices"))
            return {"answer": answer, "wasFreeform": freeform}

        session_kwargs: dict[str, Any] = dict(
            on_permission_request=PermissionHandler.approve_all,
            model=model or self.model,
            provider=self.provider,
            working_directory=str(workspace),
            on_user_input_request=user_input_handler,
            enable_file_change_tracking=True,
        )
        if system_append:
            session_kwargs["system_message"] = {"mode": "append", "content": system_append}
        if skill_dirs:
            session_kwargs["skill_directories"] = skill_dirs
        if read_only:
            # Reviewer sessions: no edit/create tools. Tool names follow the Copilot SDK custom-agent
            # docs (view, grep, glob, bash); bash stays so the reviewer can run the tests. The driver
            # also resets the working tree after a read-only stage as a belt-and-braces measure.
            session_kwargs["excluded_tools"] = ["edit", "create", "write", "apply_patch", "multi_edit"]
        session = await self._client.create_session(**session_kwargs)
        try:
            message = prompt
            while True:
                result.turns += 1
                send_kwargs: dict[str, Any] = {"timeout": timeout_sec}
                if response_schema is not None:
                    send_kwargs["response_schema"] = response_schema
                ev = await session.send_and_wait(message, **send_kwargs)
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

    async def run_stage(self, stage, workspace, prompt, *, system_append, skill_dirs, on_user_input, next_turn, max_turns, timeout_sec, response_schema=None, read_only=False, model=None) -> StageResult:
        result = StageResult(stage=stage, final_message="", turns=0, started=time.time())
        events: list[dict[str, Any]] = [{"type": "fake.prompt", "data": {"content": prompt[:500]}}]
        if stage == "review":
            result.turns += 1
            (workspace / ".eval").mkdir(exist_ok=True)
            (workspace / ".eval" / "process_review.md").write_text(FAKE_PROCESS_REVIEW, encoding="utf-8")
            result.final_message = "Review written to .eval/process_review.md"
        elif stage == "fixed_review":
            result.turns += 1
            has_tests = any((workspace / "tests").glob("test_*.py"))
            result.final_message = json.dumps(FAKE_REVIEW if has_tests else {**FAKE_REVIEW, "overall_correctness": "uncertain"})
        elif stage == "author":
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
