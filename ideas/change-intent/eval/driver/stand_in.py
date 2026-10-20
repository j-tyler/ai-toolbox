"""Stand-in authors: the "human" side of the authoring dialogue, automated.

The stand-in is part of the *harness*, not of the process under test, so it must behave identically
for every process version. Two implementations:

* ``ScriptedStandIn`` answers from fixed rules and never calls a model. It is the default because it
  is free, deterministic, and easy to defend.
* ``ModelStandIn`` asks a second model to answer in character, given the brief. Use it when the
  scripted rules prove too blunt for a skill that asks open questions.

Both log every exchange so the dialogue can be audited after the run.

Stopping rule (shared): the dialogue is over once the intent file exists and has been committed, no
matter what the agent asks next. Until then, an existing but unapproved file gets one request to show
the complete file for approval; everything else gets the scripted policy answer.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

QUESTION_HINTS = ("?", "approve", "confirm", "which", "should i", "do you want", "let me know", "shall i")
APPROVE_WORDS = re.compile(r"recommend|default|yes|approve|confirm|proceed|minimal", re.I)


@dataclass
class Exchange:
    stage: str
    kind: str  # "ask_user" | "message"
    prompt: str
    choices: list[str] | None
    answer: str
    at: float = field(default_factory=time.time)


class ScriptedStandIn:
    """Policy: confirm the brief, take the recommended or first option, keep scope minimal, approve."""

    def __init__(self, brief: str, intent_dir: str = "change-intent", log_path: Path | None = None):
        self.brief = brief
        self.intent_dir = intent_dir
        self.log_path = log_path
        self.exchanges: list[Exchange] = []
        self.stage = "author"
        self.approved = False
        self._asked_for_file = False

    # -- recording -----------------------------------------------------------
    def _record(self, kind: str, prompt: str, choices: list[str] | None, answer: str) -> None:
        self.exchanges.append(Exchange(self.stage, kind, prompt, choices, answer))
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.write_text(json.dumps([e.__dict__ for e in self.exchanges], indent=2), encoding="utf-8")

    # -- ask_user tool -------------------------------------------------------
    def answer_question(self, question: str, choices: list[str] | None) -> tuple[str, bool]:
        """Return (answer, was_freeform) for the ask_user tool."""
        if choices:
            pick = self._pick(question, choices)
            if self.stage == "author" and APPROVE_WORDS.search(pick) and "approv" in question.lower():
                self.approved = True
            self._record("ask_user", question, choices, pick)
            return pick, False
        text = self._freeform(question)
        self._record("ask_user", question, None, text)
        return text, True

    # -- prose questions at end of turn --------------------------------------
    def reply_to_message(self, message: str, intent_exists: bool, intent_committed: bool) -> str | None:
        """Decide the next user turn after the agent goes idle. ``None`` means the dialogue is done."""
        if intent_committed:
            return None
        if intent_exists and not self.approved and not self._asked_for_file:
            self._asked_for_file = True
            reply = (
                "Show me the complete intent file for approval before anything else. Do not implement. "
                "If it matches what we discussed, I will approve it and you should commit it."
            )
            self._record("message", message[-2000:], None, reply)
            return reply
        lowered = message.lower()
        asks = any(h in lowered for h in QUESTION_HINTS)
        if intent_exists and self.approved and not asks:
            return None
        reply = self._freeform(message)
        self._record("message", message[-2000:], None, reply)
        return reply

    # -- policy --------------------------------------------------------------
    @staticmethod
    def _pick(question: str, choices: list[str]) -> str:
        for c in choices:
            if APPROVE_WORDS.search(c):
                return c
        return choices[0]

    def _freeform(self, prompt: str) -> str:
        lowered = prompt.lower()
        if self.stage != "author":
            return "Your call. Keep it minimal, keep existing behaviour unchanged, and continue without waiting for me."
        if "approve" in lowered or "ready for approval" in lowered or "final" in lowered or "proposed intent" in lowered:
            self.approved = True
            return (
                f"Approved as proposed. Write the intent file under {self.intent_dir}/ exactly as shown, "
                "commit it, tell me the path, and stop. Do not start implementation."
            )
        if "brief" in lowered and ("confirm" in lowered or "correct" in lowered or "accurate" in lowered):
            return "Yes, that brief is correct. Proceed to explore the code."
        return (
            "Yes, let's do that. Where you offer options, take the one you recommend; otherwise take the "
            "simplest option that keeps the existing commands working exactly as they do today and stays "
            "inside the brief. Anything the brief does not mention is out of scope for this change. "
            "Continue, and when the intent is ready for approval show me the complete file. Do not implement."
        )


class ModelStandIn(ScriptedStandIn):
    """Same contract, but open questions are answered by a model playing the author.

    ``ask`` is an async callable ``(system_prompt, user_prompt) -> str`` supplied by the backend so this
    module stays free of SDK imports. The stopping rule is inherited and is not delegated to the model.
    """

    SYSTEM = (
        "You are the author of a software change, talking to an AI that is drafting a change intent for you. "
        "You know what you want, which is written in the brief below, and nothing about the code. Answer in one to "
        "three sentences. Confirm restatements of the brief when accurate. When offered options, choose the "
        "recommended one, or the simplest one that keeps existing behaviour unchanged. Decline scope the brief does "
        "not ask for. When shown a complete intent that reflects the brief, approve it and ask for it to be written "
        "under {intent_dir}/ and committed without starting implementation. Never write code or technical designs "
        "yourself.\n\nBRIEF:\n{brief}"
    )

    def __init__(self, brief: str, ask, intent_dir: str = "change-intent", log_path: Path | None = None):
        super().__init__(brief, intent_dir, log_path)
        self._ask = ask

    def _system(self) -> str:
        return self.SYSTEM.format(brief=self.brief, intent_dir=self.intent_dir)

    async def answer_question_async(self, question: str, choices: list[str] | None) -> tuple[str, bool]:
        if choices:
            prompt = f"{question}\n\nOptions:\n" + "\n".join(f"- {c}" for c in choices) + "\n\nReply with exactly one option text."
            raw = (await self._ask(self._system(), prompt)).strip()
            pick = next((c for c in choices if c.lower() in raw.lower()), None) or self._pick(question, choices)
            if self.stage == "author" and APPROVE_WORDS.search(pick) and "approv" in question.lower():
                self.approved = True
            self._record("ask_user", question, choices, pick)
            return pick, False
        text = (await self._ask(self._system(), question)).strip()
        if self.stage == "author" and re.search(r"\bapprov", text, re.I):
            self.approved = True
        self._record("ask_user", question, None, text)
        return text, True

    async def reply_to_message_async(self, message: str, intent_exists: bool, intent_committed: bool) -> str | None:
        if intent_committed:
            return None
        if intent_exists and not self.approved and not self._asked_for_file:
            return self.reply_to_message(message, intent_exists, intent_committed)
        lowered = message.lower()
        asks = any(h in lowered for h in QUESTION_HINTS)
        if intent_exists and self.approved and not asks:
            return None
        reply = (await self._ask(self._system(), message[-6000:])).strip()
        if re.search(r"\bapprov", reply, re.I):
            self.approved = True
        self._record("message", message[-2000:], None, reply)
        return reply
