"""Instant answers (spec §6.2): the fixed phrases jarvisd answers itself, before anything reaches Claude Code."""
import re
from collections.abc import Collection
from datetime import datetime
from typing import Literal

from jarvis.daemon import names

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


def _normal(utterance: str) -> str:
    return _LEAD.sub("", " ".join(re.sub(r"[^a-z0-9' ]", "", utterance.lower()).split()))


def match(utterance: str, pending: bool) -> Action | None:
    text = _normal(utterance)
    return _PHRASES.get(text) or (_ANSWERS.get(text) if pending else None)


NamedAction = Literal["stop", "yes", "no", "always"]
_NAMED = re.compile(r"(?:(?:i|meant|said|mean|okay|ok|sorry|um|uh|er|well|so|and|then|actually|oh|alright|right"
                    r"|yeah) )*"
                    r"(?:(?P<stop>stop)|(?P<always>yes always)(?: to)?|(?P<yes>yes)(?: to)?|(?P<no>no)(?: to)?) "
                    r"(?P<name>[a-z']+)")   # only a short lead-in before it: never after "don't", "why did you"


def named_shape(utterance: str) -> bool:
    """Stop, yes, no or yes always (to) and one word, after at most a short lead-in ("I meant", "okay"): a name
    phrase, whether or not the word names anyone."""
    return bool(_NAMED.fullmatch(_normal(utterance)))


def match_named(utterance: str, running: Collection[str]) -> tuple[NamedAction, str] | None:
    m = _NAMED.fullmatch(_normal(utterance))
    name = m and names.match(m["name"], running)
    return (next(k for k, v in m.groupdict().items() if v and k != "name"), name) if name else None


_ACKS = {"okay", "ok", "huh", "thanks", "thank you", "got it", "cool", "alright", "all right", "great", "nice"}


def is_ack(utterance: str) -> bool:
    """A bare reaction ("Okay.", "Huh?"): in the follow-up window it ends the exchange instead of reaching Claude."""
    return " ".join(re.sub(r"[^a-z0-9' ]", "", utterance.lower()).split()) in _ACKS


def say_time(now: datetime) -> str:
    return f"It's {now.hour % 12 or 12}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'}."


def say_date(now: datetime) -> str:
    return f"{now:%A}, {now.day} {now:%B}."
