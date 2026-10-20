"""Stand-in authors: the "human" side of the authoring dialogue, automated.

The stand-in is part of the *harness*, not of the process under test, so it must behave identically
for every process version. Two implementations:

* ``ScriptedStandIn`` answers from fixed rules and never calls a model. It is the default because it
  is free, deterministic, and easy to defend.
* ``ModelStandIn`` asks a second model to answer in character, given the brief. Approval is decided by
  a separate structured yes/no call, not by scanning the reply.

Both log every exchange, with the rule that produced each answer, so the dialogue can be audited.

Rules (shared):
- The dialogue is over once the artifact file exists and has been committed during the stage.
- Approval is granted only when the agent PRESENTS the artifact: the message contains the file's
  content (most of its required section headings, or a large share of its lines), or an ask_user
  question offers an affirmative choice right after such a presentation. "Intent brief" style
  previews never count, nor do messages that merely mention approval.
- After approval but before a commit, one nudge asks the agent to write the final file and commit.
- An existing but unpresented draft gets one request to show it.
- Every other message gets an information-neutral reply that defers to the brief.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

QUESTION_HINTS = ("?", "approve", "confirm", "which", "should i", "do you want", "let me know", "shall i")
APPROVE_WORDS = re.compile(r"\b(approve|approved|yes|confirm|proceed|looks good|go ahead|write it|recommended)\b", re.I)
PREVIEW_MARKERS = ("intent brief", "## intent brief")


@dataclass
class Exchange:
    stage: str
    kind: str  # "ask_user" | "message"
    prompt: str
    choices: list[str] | None
    answer: str
    cue: str | None = None  # which rule produced the answer
    at: float = field(default_factory=time.time)


class ScriptedStandIn:
    """Policy: confirm the brief, take the recommended option, defer to the brief, approve what is presented."""

    def __init__(self, brief: str, intent_dir: str = "change-intent", log_path: Path | None = None,
                 noun: str = "description document", required_sections: list[str] | None = None):
        self.brief = brief
        self.intent_dir = intent_dir
        self.noun = noun
        self.required_sections = [s.lower() for s in (required_sections or [])]
        self.log_path = log_path
        self.exchanges: list[Exchange] = []
        self.stage = "author"
        self.approved = False
        self.presented = False
        self._asked_for_file = False
        self._commit_nudged = False

    # -- recording -----------------------------------------------------------
    def _record(self, kind: str, prompt: str, choices: list[str] | None, answer: str, cue: str | None = None) -> None:
        self.exchanges.append(Exchange(self.stage, kind, prompt, choices, answer, cue))
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.write_text(json.dumps([e.__dict__ for e in self.exchanges], indent=2), encoding="utf-8")

    # -- presentation detection ---------------------------------------------
    def presents_artifact(self, message: str, artifact_text: str | None) -> bool:
        """Does this message show the artifact? Structural, not keyword-based."""
        lowered = message.lower()
        if any(m in lowered for m in PREVIEW_MARKERS):
            return False
        if self.required_sections:
            found = sum(1 for s in self.required_sections if re.search(rf"^\s*#{{1,3}}\s*{re.escape(s)}\b", lowered, re.M))
            if found >= max(3, (len(self.required_sections) + 1) // 2):
                return True
        if artifact_text:
            lines = [l.strip() for l in artifact_text.splitlines() if len(l.strip()) > 12]
            if lines:
                shown = sum(1 for l in lines if l in message)
                if shown / len(lines) >= 0.6:
                    return True
        return bool(re.search(r"^\s*#{1,3}\s*proposed\b", lowered, re.M)) and "```" in message

    # -- ask_user tool -------------------------------------------------------
    def answer_question(self, question: str, choices: list[str] | None, artifact_text: str | None = None) -> tuple[str, bool]:
        """Return (answer, was_freeform) for the ask_user tool."""
        if self.stage == "author" and self.presents_artifact(question, artifact_text):
            self.presented = True
        if choices:
            pick = self._pick(choices)
            cue = None
            if self.stage == "author" and self.presented and not self.approved and APPROVE_WORDS.search(pick):
                self.approved = True
                cue = "ask_user:approve-after-presentation"
            self._record("ask_user", question, choices, pick, cue)
            return pick, False
        text, cue = self._freeform(question)
        self._record("ask_user", question, None, text, cue)
        return text, True

    # -- prose questions at end of turn --------------------------------------
    def reply_to_message(self, message: str, intent_exists: bool, intent_committed: bool, artifact_text: str | None = None) -> str | None:
        """Decide the next user turn after the agent goes idle. ``None`` means the dialogue is done."""
        if intent_committed:
            return None
        if self.stage == "author" and self.presents_artifact(message, artifact_text):
            self.presented = True
        if self.approved and intent_exists and not self._commit_nudged:
            self._commit_nudged = True
            reply = f"Write the final {self.noun} file under {self.intent_dir}/ and commit it now. Then stop."
            self._record("message", message[-2000:], None, reply, "commit-nudge")
            return reply
        if self.approved and intent_exists:
            return None
        if intent_exists and not self.presented and not self._asked_for_file:
            self._asked_for_file = True
            reply = (
                f"Show me the complete {self.noun} file for approval before anything else. Do not implement. "
                "If it matches what we discussed, I will approve it and you should commit it."
            )
            self._record("message", message[-2000:], None, reply, "ask-for-file")
            return reply
        reply, cue = self._freeform(message)
        self._record("message", message[-2000:], None, reply, cue)
        return reply

    # -- policy --------------------------------------------------------------
    @staticmethod
    def _pick(choices: list[str]) -> str:
        for c in choices:
            if re.search(r"recommend|default", c, re.I):
                return c
        for c in choices:
            if APPROVE_WORDS.search(c):
                return c
        return choices[0]

    def _freeform(self, prompt: str) -> tuple[str, str]:
        """Return (reply, cue)."""
        lowered = prompt.lower()
        if self.stage != "author":
            return ("Your call. Keep it minimal, keep existing behaviour unchanged, and continue without waiting for me.", "non-author:your-call")
        if self.presented and not self.approved:
            self.approved = True
            return (
                f"Approved as presented. Write the {self.noun} file under {self.intent_dir}/ exactly as shown, "
                "commit it, tell me the path, and stop. Do not start implementation.",
                "approve:presented",
            )
        if "brief" in lowered and ("confirm" in lowered or "correct" in lowered or "accurate" in lowered):
            return ("Yes, that brief is correct. Proceed.", "confirm-brief")
        return (
            "Where you offer options, take the one you recommend. The brief is everything I have decided; "
            f"anything it does not state is your call. When the {self.noun} is ready, show me the complete file "
            "for approval. Do not implement.",
            "default:defer-to-brief",
        )


class ModelStandIn(ScriptedStandIn):
    """Same contract, but open questions are answered by a model playing the author.

    ``ask`` is an async callable ``(system_prompt, user_prompt) -> str`` supplied by the backend so this
    module stays free of SDK imports. Presentation detection and the stopping rule are inherited and are
    not delegated to the model; approval is a separate structured yes/no call on the model's own reply.
    """

    SYSTEM = (
        "You are the author of a software change, talking to an AI that is drafting a {noun} for you. "
        "You know what you want, which is written in the brief below, and nothing about the code. Answer in one to "
        "three sentences. Confirm restatements of the brief when accurate. When offered options, choose the "
        "recommended one, or the simplest one that keeps existing behaviour unchanged. The brief is everything you "
        "have decided; anything it does not state is the AI's call. When shown a complete {noun} that reflects the "
        "brief, approve it and ask for it to be written under {intent_dir}/ and committed without starting "
        "implementation. Never write code or technical designs yourself.\n\nBRIEF:\n{brief}"
    )
    APPROVAL_CHECK = (
        "You will be shown a reply written by the author of a software change. Answer with exactly one word, YES or NO: "
        "does the reply grant approval of the document as shown, now (not conditionally, not after further changes)?"
    )

    def __init__(self, brief: str, ask, intent_dir: str = "change-intent", log_path: Path | None = None,
                 noun: str = "description document", required_sections: list[str] | None = None):
        super().__init__(brief, intent_dir, log_path, noun, required_sections)
        self._ask = ask

    def _system(self) -> str:
        return self.SYSTEM.format(brief=self.brief, intent_dir=self.intent_dir, noun=self.noun)

    async def _grants_approval(self, reply: str) -> bool:
        verdict = (await self._ask(self.APPROVAL_CHECK, reply)).strip().upper()
        return verdict.startswith("YES")

    async def answer_question_async(self, question: str, choices: list[str] | None, artifact_text: str | None = None) -> tuple[str, bool]:
        if self.stage == "author" and self.presents_artifact(question, artifact_text):
            self.presented = True
        if choices:
            prompt = f"{question}\n\nOptions:\n" + "\n".join(f"- {c}" for c in choices) + "\n\nReply with exactly one option text."
            raw = (await self._ask(self._system(), prompt)).strip()
            pick = next((c for c in choices if c.lower() in raw.lower()), None) or self._pick(choices)
            cue = "model:choice"
            if self.stage == "author" and self.presented and not self.approved and APPROVE_WORDS.search(pick):
                self.approved = True
                cue = "model:approve-after-presentation"
            self._record("ask_user", question, choices, pick, cue)
            return pick, False
        text = (await self._ask(self._system(), question)).strip()
        cue = "model"
        if self.stage == "author" and self.presented and not self.approved and await self._grants_approval(text):
            self.approved = True
            cue = "model:approve"
        self._record("ask_user", question, None, text, cue)
        return text, True

    async def reply_to_message_async(self, message: str, intent_exists: bool, intent_committed: bool, artifact_text: str | None = None) -> str | None:
        if intent_committed:
            return None
        if self.stage == "author" and self.presents_artifact(message, artifact_text):
            self.presented = True
        if self.approved and intent_exists:
            return self.reply_to_message(message, intent_exists, intent_committed, artifact_text)  # commit nudge / stop
        if intent_exists and not self.presented and not self._asked_for_file:
            return self.reply_to_message(message, intent_exists, intent_committed, artifact_text)  # ask for the file
        reply = (await self._ask(self._system(), message[-6000:])).strip()
        cue = "model"
        if self.stage == "author" and self.presented and not self.approved and await self._grants_approval(reply):
            self.approved = True
            cue = "model:approve"
        self._record("message", message[-2000:], None, reply, cue)
        return reply
