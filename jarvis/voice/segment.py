"""Cuts the 30 ms mic frames into utterances; the voice detector is injected."""
import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

from jarvis import config

START, STOP = 0.5, 0.35
PRE_ROLL = 10  # frames, 0.3 s
KEEP_QUIET = 3  # frames of trailing silence kept
_FRAME_S = config.FRAME / config.SAMPLE_RATE
END_FRAMES = math.ceil(config.END_SILENCE_SECONDS / _FRAME_S)
MAX_FRAMES = round(config.MAX_UTTERANCE_SECONDS / _FRAME_S)
MAX_HELD_FRAMES = round(config.MAX_HELD_SECONDS / _FRAME_S)


@dataclass
class Utterance:
    pcm: np.ndarray  # int16, 16 kHz, mono
    cut: bool  # ended by the length cap, not by silence


class Segmenter:
    def __init__(self, predict: Callable[[np.ndarray], float]):
        self.predict = predict
        self.speaking = False
        self.reset()

    def reset(self) -> None:
        self.buf: list[np.ndarray] = []
        self.speaking = False
        self.held = False
        self.heard = False  # the detector found speech in the held frames
        self.quiet = 0

    def _take(self, keep: int, cut: bool) -> Utterance:
        pcm = np.concatenate(self.buf[:keep])
        self.reset()
        return Utterance(pcm, cut)

    def feed(self, frame: np.ndarray) -> Utterance | None:
        self.buf.append(frame)
        if self.held:
            self.heard |= self.predict(frame) >= START
            if len(self.buf) < MAX_HELD_FRAMES:
                return None
            return self._take(len(self.buf), True) if self.heard else self.reset()  # nothing said: dropped
        p = self.predict(frame)
        if not self.speaking:
            if p >= START:
                self.speaking, self.quiet = True, 0
            else:
                self.buf = self.buf[-PRE_ROLL:]
            return None
        self.quiet = self.quiet + 1 if p < STOP else 0
        capped = len(self.buf) >= MAX_FRAMES
        if self.quiet >= END_FRAMES or capped:
            return self._take(len(self.buf) - self.quiet + KEEP_QUIET, capped and self.quiet < END_FRAMES)
        return None

    def hold(self) -> None:
        self.held, self.heard = True, self.speaking

    def release(self) -> Utterance | None:
        if not (self.held and self.heard):  # the detector never fired: room sound, not a request
            self.held = False
            return None
        return self._take(len(self.buf), False)

    def tap(self) -> None:
        """Speech in the held frames goes on as speech in progress; none (a tap, then the request): keep only the
        pre-roll and let the detector find the start."""
        self.held = False
        if self.heard:
            self.speaking, self.quiet = True, 0
        else:
            self.buf = self.buf[-PRE_ROLL:]
