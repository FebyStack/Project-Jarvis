"""Instant answers (spec §6.2): the fixed phrases jarvisd answers itself, before anything reaches Claude Code."""
import re
from datetime import datetime
from typing import Literal

Action = Literal["time", "date", "mute", "unmute", "cancel", "repeat", "status", "yes", "no", "always"]

_PHRASES: dict[str, Action] = {
    "what time is it": "time", "what's the time": "time",
    "what's the date": "date", "what day is it": "date",
    "stop listening": "mute", "mute": "mute",
    "start listening": "unmute", "unmute": "unmute",
    "cancel": "cancel", "never mind": "cancel", "stop": "cancel",
    "repeat that": "repeat", "say that again": "repeat",
    "status": "status", "what are you working on": "status",
}
_ANSWERS: dict[str, Action] = {"yes": "yes", "no": "no", "yes always": "always"}
_LEAD = re.compile(r"^(?:(?:hey jarvis|jarvis|please)(?: |$))+")


def match(utterance: str, pending: bool) -> Action | None:
    text = " ".join(re.sub(r"[^a-z0-9' ]", "", utterance.lower()).split())
    text = _LEAD.sub("", text)
    return _PHRASES.get(text) or (_ANSWERS.get(text) if pending else None)


def say_time(now: datetime) -> str:
    return f"It's {now.hour % 12 or 12}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'}."


def say_date(now: datetime) -> str:
    return f"{now:%A}, {now.day} {now:%B}."
