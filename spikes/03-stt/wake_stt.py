"""Spike 3: wake by transcription. A VAD cuts utterances; each is transcribed; a "Jarvis" in the first words wakes."""
import difflib, re
import numpy as np
from openwakeword.vad import VAD

FRAME = 480  # 30 ms at 16 kHz


def is_wake(text: str) -> tuple[bool, str]:
    """True if one of the first three words sounds like "Jarvis"; returns the words after it (the request)."""
    words = re.findall(r"[a-z']+", text.lower())
    for i, w in enumerate(words[:3]):
        if difflib.SequenceMatcher(None, re.sub(r"'s$", "", w), "jarvis").ratio() >= 0.75:
            return True, " ".join(words[i + 1:])
    return False, ""


class Segmenter:
    """Feed 30 ms int16 frames; get whole utterances back once `end_silence` seconds of non-speech follow them."""

    def __init__(self, end_silence=0.8, start=0.5, stop=0.35, preroll=0.3, max_len=15.0):
        self.vad, self.end_frames = VAD(), int(end_silence / 0.03)
        self.start, self.stop, self.pre, self.max = start, stop, int(preroll / 0.03), int(max_len / 0.03)
        self.buf, self.speaking, self.quiet = [], False, 0

    def feed(self, frame: np.ndarray):
        p = self.vad.predict(frame, frame_size=FRAME)
        self.buf.append(frame)
        if not self.speaking:
            self.buf = self.buf[-self.pre:]
            if p >= self.start:
                self.speaking, self.quiet = True, 0
            return None
        self.quiet = self.quiet + 1 if p < self.stop else 0
        if self.quiet >= self.end_frames or len(self.buf) >= self.max:
            seg = np.concatenate(self.buf[: len(self.buf) - self.quiet + 3])
            self.buf, self.speaking, self.quiet = [], False, 0
            return seg
        return None
