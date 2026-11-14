"""Open yes/no questions: one Future each, answered by channel or id, or timed out as no."""
import asyncio
import itertools
from dataclasses import dataclass, field
from typing import Callable, Literal

from jarvis.brain.gate import Decision
from jarvis.brain.trusted import TrustedList
from jarvis.memory.vault import Channel


@dataclass
class Ask:
    id: str
    question: str
    pattern: str
    channel: Channel
    request_id: str
    future: asyncio.Future = field(repr=False, compare=False, default=None)


class Asks:
    def __init__(self, trusted: TrustedList, timeouts: dict[str, float], on_change: Callable[[], None]):
        self.trusted, self.timeouts, self.on_change = trusted, timeouts, on_change
        self._open: list[Ask] = []  # oldest first
        self._history: list[tuple[str, str, bool]] = []
        self._ids = itertools.count(1)

    async def ask(self, decision: Decision, channel: Channel, request_id: str) -> bool:
        a = Ask(str(next(self._ids)), decision.reason + ". Yes or no?", decision.pattern, channel, request_id,
                asyncio.get_running_loop().create_future())
        self._open.append(a)
        self.on_change()
        try:
            yes = await asyncio.wait_for(a.future, self.timeouts[channel])
        except asyncio.TimeoutError:
            yes = False
        finally:
            self._open.remove(a)
        self._history.append((request_id, a.question, yes))
        self.on_change()
        return yes

    def answer(self, reply: Literal["yes", "no", "always"], channel: Channel | None = None,
               ask_id: str | None = None) -> Ask | None:
        if reply not in ("yes", "no", "always"):  # fail closed: only an exact yes/always approves
            raise ValueError(f"unknown reply: {reply!r}")
        a = next((a for a in self._open if not a.future.done() and
                  (a.id == ask_id if ask_id is not None else channel in (None, a.channel))), None)
        if a is None:
            return None
        if reply == "always" and a.pattern:
            self.trusted.add(a.pattern)
        a.future.set_result(reply in ("yes", "always"))
        return a

    def pending(self, channel: Channel | None = None) -> list[Ask]:
        return [a for a in self._open if channel in (None, a.channel)]

    def history(self) -> list[tuple[str, str, bool]]:
        return list(self._history)
