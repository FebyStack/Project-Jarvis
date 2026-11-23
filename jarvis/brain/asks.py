"""Open yes/no questions: one Future each, answered by channel or id, or timed out as no."""
import asyncio
import time
import uuid
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
    agent_id: str = ""
    until: float = 0.0
    future: asyncio.Future = field(repr=False, compare=False, default=None)


class Asks:
    def __init__(self, trusted: TrustedList, timeouts: dict[str, float], on_change: Callable[[], None],
                 clock: Callable[[], float] = time.monotonic):
        self.trusted, self.timeouts, self.on_change, self.clock = trusted, timeouts, on_change, clock
        self._open: list[Ask] = []  # oldest first
        self._history: list[tuple[str, str, bool]] = []

    async def ask(self, decision: Decision, channel: Channel, request_id: str, agent_id: str = "") -> bool:
        a = Ask(uuid.uuid4().hex[:12], decision.reason + ". Yes or no?", decision.pattern, channel, request_id,
                agent_id, self.clock() + self.timeouts[channel], asyncio.get_running_loop().create_future())
        self._open.append(a)
        self.on_change()
        expiry = asyncio.get_running_loop().call_later(self.timeouts[channel], self._settle, a, False)
        try:
            return await a.future
        finally:
            expiry.cancel()
            self._open.remove(a)
            self.on_change()

    def _settle(self, a: Ask, yes: bool) -> None:
        """Answered or timed out: listed at once, so a note written in the same step has it."""
        if not a.future.done():
            a.future.set_result(yes)
            self._history.append((a.request_id, a.question, yes))

    def answer(self, reply: Literal["yes", "no", "always"], channel: Channel | None = None,
               ask_id: str | None = None) -> Ask | None:
        if reply not in ("yes", "no", "always"):  # fail closed: only an exact yes/always approves
            raise ValueError(f"unknown reply: {reply!r}")
        if ask_id is not None:
            a = next((a for a in self._open if a.id == ask_id and not a.future.done()), None)
        else:  # a bare answer applies only when one question is open on the channel: never guess (review finding 10)
            open_ = [a for a in self._open if not a.future.done() and channel in (None, a.channel)]
            a = open_[0] if len(open_) == 1 else None
        if a is None:
            return None
        if reply == "always" and a.pattern:
            self.trusted.add(a.pattern)
        self._settle(a, reply in ("yes", "always"))
        return a

    def pending(self, channel: Channel | None = None) -> list[Ask]:
        return [a for a in self._open if not a.future.done() and channel in (None, a.channel)]

    def history(self) -> list[tuple[str, str, bool]]:
        return list(self._history)
