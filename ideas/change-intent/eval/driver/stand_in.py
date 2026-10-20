"""Stand-in authors: the "human" side of the authoring dialogue, automated.

The stand-in is part of the *harness*, not of the process under test, so it must behave identically
for every process version. Two implementations:

* ``ScriptedStandIn`` answers from fixed rules and never calls a model. It is the default because it
  is free, deterministic, and easy to defend.
* ``ModelStandIn`` asks a second model to answer in character, given the brief. Approval is decided by
  a separate structured yes/no call, not by scanning the reply. Outside the author stage it answers
  exactly as the scripted stand-in does, so every arm gets the same non-author answers.

Both log every exchange, with the rule that produced each answer, so the dialogue can be audited.

Rules (shared):
- The dialogue is over once the artifact file exists and has been committed during the stage.
- Approval is granted only when the agent PRESENTS the artifact: the text the author would see (the
  whole turn, or the ask_user question plus the assistant text before it) contains most of the
  artifact's required section headings, or a large share of its lines. Mentions of approval do not
  count. A Phase-1 style "Intent brief" preview does not count unless it also carries the sections.
- After approval: a re-presented or re-asked artifact is approved again; an agent that has not yet
  written or committed the file is nudged to do so, at most twice, then the stage is allowed to end.
- An existing but unpresented draft gets one request to show it.
- Every other message gets an information-neutral reply that defers to the brief.
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

QUESTION_HINTS = ("?", "approve", "confirm", "which", "should i", "do you want", "let me know", "shall i")
APPROVE_WORDS = re.compile(r"\b(approve|approved|yes|confirm|proceed|looks good|go ahead|write it|recommended)\b", re.I)
ASKS_APPROVAL = re.compile(r"\b(approv|confirm|sign.?off|ok to (write|commit)|ready to (write|commit))", re.I)
INTENT_BRIEF_HEADING = re.compile(r"^\s*#{1,6}\s*intent brief\b", re.I | re.M)
NON_AUTHOR_REPLY = "The brief is everything I have decided; anything it does not state is your call. Continue without waiting for me."


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

    MAX_POST_APPROVAL_NUDGES = 2

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
        self._post_approval_nudges = 0
        self.end_reason: str | None = None

    # -- recording -----------------------------------------------------------
    def _record(self, kind: str, prompt: str, choices: list[str] | None, answer: str, cue: str | None = None) -> None:
        self.exchanges.append(Exchange(self.stage, kind, prompt, choices, answer, cue))
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.write_text(json.dumps([e.__dict__ for e in self.exchanges], indent=2), encoding="utf-8")

    # -- presentation detection ---------------------------------------------
    def _section_hits(self, text: str) -> int:
        lowered = text.lower()
        hits = 0
        for s in self.required_sections:
            pat = rf"(^\s*#{{1,6}}\s*{re.escape(s)}\b|^\s*\*\*{re.escape(s)}\*\*|^\s*{re.escape(s)}\s*:\s*$)"
            if re.search(pat, lowered, re.M):
                hits += 1
        return hits

    def presents_artifact(self, text: str, artifact_text: str | None) -> bool:
        """Does this text show the artifact? Structural: section headings first, then line overlap."""
        if self.required_sections:
            need = max(3, math.ceil(len(self.required_sections) / 2))
            if self._section_hits(text) >= need:
                return True
        if INTENT_BRIEF_HEADING.search(text) and not self.required_sections:
            return False
        if artifact_text:
            lines = [l.strip() for l in artifact_text.splitlines() if len(l.strip()) > 12]
            if lines:
                shown = sum(1 for l in lines if l in text)
                if shown / len(lines) >= 0.6:
                    return True
        return bool(re.search(r"^\s*#{1,6}\s*proposed\b", text, re.I | re.M)) and "```" in text

    # -- ask_user tool -------------------------------------------------------
    def answer_question(self, question: str, choices: list[str] | None, artifact_text: str | None = None,
                        context: str | None = None) -> tuple[str, bool]:
        """Return (answer, was_freeform) for the ask_user tool. ``context`` is the assistant text the author
        would have read before the question (the backend supplies it); presentation is judged on both."""
        seen = (context or "") + "\n" + question
        if self.stage == "author" and self.presents_artifact(seen, artifact_text):
            self.presented = True
        if choices:
            pick = self._pick(choices)
            cue = None
            if self.stage == "author" and self.presented and APPROVE_WORDS.search(pick):
                if not self.approved:
                    self.approved = True
                    cue = "ask_user:approve-after-presentation"
            self._record("ask_user", question, choices, pick, cue)
            return pick, False
        text, cue = self._freeform(question)
        self._record("ask_user", question, None, text, cue)
        return text, True

    # -- prose questions at end of turn --------------------------------------
    def reply_to_message(self, message: str, intent_exists: bool, intent_committed: bool, artifact_text: str | None = None) -> str | None:
        """Decide the next user turn after the agent goes idle. ``None`` means the dialogue is done.
        ``message`` should be the whole turn's assistant text, not only its last message."""
        if intent_committed:
            self.end_reason = "committed"
            return None
        presents_now = self.stage == "author" and self.presents_artifact(message, artifact_text)
        if presents_now:
            self.presented = True
        if self.approved:
            if self._post_approval_nudges >= self.MAX_POST_APPROVAL_NUDGES:
                self.end_reason = "stand_in_stopped"
                return None
            self._post_approval_nudges += 1
            if presents_now or ASKS_APPROVAL.search(message):
                reply = (f"Approved as presented. Write the {self.noun} file under {self.intent_dir}/ exactly as shown, "
                         "commit it, tell me the path, and stop. Do not start implementation.")
                self._record("message", message[-2000:], None, reply, "reapprove")
                return reply
            reply = f"Write the approved {self.noun} under {self.intent_dir}/ and commit it now. Then stop."
            self._record("message", message[-2000:], None, reply, "write-nudge")
            return reply
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
        if self.stage != "author":
            return (NON_AUTHOR_REPLY, "non-author:defer")
        if self.presented and not self.approved:
            self.approved = True
            return (
                f"Approved as presented. Write the {self.noun} file under {self.intent_dir}/ exactly as shown, "
                "commit it, tell me the path, and stop. Do not start implementation.",
                "approve:presented",
            )
        if not self.presented and INTENT_BRIEF_HEADING.search(prompt):
            return ("Yes, that brief is correct. Proceed.", "confirm-brief")
        return (
            "Where you offer options, take the one you recommend. The brief is everything I have decided; "
            f"anything it does not state is your call. When the {self.noun} is ready, show me the complete file "
            "for approval. Do not implement.",
            "default:defer-to-brief",
        )


class ModelStandIn(ScriptedStandIn):
    """Same contract, but open author-stage questions are answered by a model playing the author.

    ``ask`` is an async callable ``(system_prompt, user_prompt) -> str`` supplied by the backend so this
    module stays free of SDK imports. Presentation detection, the stopping rule, the post-approval rules
    and every non-author answer are inherited unchanged; approval is a separate structured yes/no call.
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

    async def answer_question_async(self, question: str, choices: list[str] | None, artifact_text: str | None = None,
                                    context: str | None = None) -> tuple[str, bool]:
        if self.stage != "author":
            return ScriptedStandIn.answer_question(self, question, choices, artifact_text, context)
        seen = (context or "") + "\n" + question
        if self.presents_artifact(seen, artifact_text):
            self.presented = True
        if choices:
            prompt = f"{question}\n\nOptions:\n" + "\n".join(f"- {c}" for c in choices) + "\n\nReply with exactly one option text."
            raw = (await self._ask(self._system(), prompt)).strip()
            pick = next((c for c in choices if c.lower() in raw.lower()), None) or self._pick(choices)
            cue = "model:choice"
            if self.presented and not self.approved and APPROVE_WORDS.search(pick):
                self.approved = True
                cue = "model:approve-after-presentation"
            self._record("ask_user", question, choices, pick, cue)
            return pick, False
        text = (await self._ask(self._system(), question)).strip()
        cue = "model"
        if self.presented and not self.approved and await self._grants_approval(text):
            self.approved = True
            cue = "model:approve"
        self._record("ask_user", question, None, text, cue)
        return text, True

    async def reply_to_message_async(self, message: str, intent_exists: bool, intent_committed: bool, artifact_text: str | None = None) -> str | None:
        if intent_committed:
            self.end_reason = "committed"
            return None
        if self.stage == "author" and self.presents_artifact(message, artifact_text):
            self.presented = True
        if self.approved:
            return self.reply_to_message(message, intent_exists, intent_committed, artifact_text)  # reapprove / nudge / stop
        if intent_exists and not self.presented and not self._asked_for_file:
            return self.reply_to_message(message, intent_exists, intent_committed, artifact_text)  # ask for the file
        reply = (await self._ask(self._system(), message[-6000:])).strip()
        cue = "model"
        if self.stage == "author" and self.presented and not self.approved and await self._grants_approval(reply):
            self.approved = True
            cue = "model:approve"
        self._record("message", message[-2000:], None, reply, cue)
        return reply
