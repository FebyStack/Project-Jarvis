"""One key, three gestures: tap, hold, and typing with it (a chord) left alone."""
from typing import Literal

from jarvis import config

Kind = Literal["down", "tap", "hold_end", "chord"]


class Gesture:
    def __init__(self):
        self.down_at: float | None = None
        self.chord = False

    def key_down(self, at: float) -> Kind | None:
        if self.down_at is not None:
            return None
        self.down_at, self.chord = at, False
        return "down"

    def key_up(self, at: float) -> Kind | None:
        if self.down_at is None:
            return None
        held, chord, self.down_at = at - self.down_at, self.chord, None
        if chord:
            return None
        return "tap" if held < config.TAP_SECONDS else "hold_end"

    def other_key(self, at: float) -> Kind | None:
        if self.down_at is None or self.chord:
            return None
        self.chord = True
        return "chord"

    def lost(self) -> Kind | None:
        """The event tap was off, so a key up may have been missed: a press under way ends as a chord."""
        was, self.down_at = self.down_at, None
        return None if was is None or self.chord else "chord"
