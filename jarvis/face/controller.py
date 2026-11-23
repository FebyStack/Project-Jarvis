"""The face's controller: events in; the circle's payload, the bead stack, the alert sound and hidden or shown out.
No AppKit."""

import json
import math
import time
from collections.abc import Callable
from pathlib import Path

from jarvis import config
from jarvis.face import place
from jarvis.face.model import FaceView, Stack, circle, more_text, new_alerts, reduce, stack


class Controller:
    def __init__(self, client, show_circle: Callable[[str], None], show_stack: Callable[[Stack, str], None],
                 play: Callable[[], None], home: Path, now: Callable[[], float] = time.time,
                 show_hidden: Callable[[bool], None] = lambda hidden: None):
        self.client, self.show_circle, self.show_stack, self.play, self.home, self.now = client, show_circle, show_stack, play, home, now
        self.show_hidden = show_hidden
        self.view = FaceView.empty()
        self._key = self._level = self._stack = None
        self._level_at = 0.0

    async def run(self) -> None:
        async for event in self.client.events():
            self._apply(event)

    def _apply(self, event: dict) -> None:
        before, self.view = self.view, reduce(self.view, event)
        if self.view.hidden != before.hidden:
            self.show_hidden(self.view.hidden)
        self._show_circle()
        if event.get("type") != "level":
            self._show_stack()
        if new_alerts(before, self.view):
            self.play()

    def _show_circle(self) -> None:
        c, now = circle(self.view), self.now()
        key = (c.mode, c.ring, c.word)
        if key != self._key or (c.level != self._level and now - self._level_at >= 1 / config.FACE_FPS):
            self._key, self._level, self._level_at = key, c.level, now
            self.show_circle(json.dumps({"mode": c.mode, "ring": c.ring, "word": c.word, "level": c.level}, ensure_ascii=True))

    def _show_stack(self) -> Stack:
        s = stack(self.view, self.now())
        if (s, more_text(s)) != self._stack:
            self._stack = (s, more_text(s))
            self.show_stack(s, more_text(s))
        return s

    def _cards(self):
        """The cards a click or a hover can act on: none while the face is hidden."""
        return () if self.view.hidden else stack(self.view, self.now()).cards

    async def answer(self, reply: str, ask_id: str) -> None:
        if reply in ("yes", "no", "always") and any(c.ask_id == ask_id and c.question for c in self._cards()):
            await self.client.answer(reply, ask_id)

    async def stop(self, agent: str) -> None:
        card = next((c for c in self._cards() if c.id == agent and c.stop), None)
        if card is None:
            return
        if agent == "jarvis":
            await self.client.answer("no", card.ask_id)
        else:
            await self.client.stop(agent)

    def hover(self, agent: str, on: bool) -> None:
        """Entering opens only a bead on show; leaving is always heard, so a hidden card never comes back stuck open."""
        if not on or any(c.id == agent for c in self._cards()):
            self._apply({"type": "hover", "agent": agent, "on": on})

    async def on_message(self, msg: object) -> None:
        if not (isinstance(msg, dict) and msg.get("type") == "moved"):
            return
        x, y = msg.get("x"), msg.get("y")
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (x, y)):
            place.save(self.home, x, y)

    def tick(self) -> None:
        self._show_stack()
