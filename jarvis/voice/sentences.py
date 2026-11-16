"""A streamed reply becomes chunks that can be spoken as they arrive."""
import re

from jarvis import config

_END = re.compile(r"[.!?](?=\s)|\n")
_URL = re.compile(r"https?://\S+")
_CLAUSE = (", ", "; ", " — ")


def speakable(text: str) -> str:
    text = _URL.sub("a link", text)
    text = re.sub(r"[*`#]", "", text).replace("_", " ")
    text = " ".join(text.split())
    return text if re.search(r"[A-Za-z0-9]", text) else ""


class Splitter:
    def __init__(self):
        self.buf, self.first = "", True

    def _emit(self, chunk: str) -> list[str]:
        said = speakable(chunk)
        if said:
            self.first = False
        return [said] if said else []

    def feed(self, delta: str) -> list[str]:
        self.buf += delta
        out: list[str] = []
        while True:
            m = _END.search(self.buf)
            if m:
                chunk, self.buf = self.buf[:m.end()], self.buf[m.end():]
            elif self.first and len(self.buf) >= config.FIRST_CHUNK_CHARS and any(c in self.buf for c in _CLAUSE):
                i, sep = max((self.buf.rfind(c), c) for c in _CLAUSE)
                chunk, self.buf = self.buf[:i + 1], self.buf[i + len(sep):]
            else:
                return out
            out += self._emit(chunk)

    def flush(self) -> list[str]:
        chunk, self.buf = self.buf, ""
        return self._emit(chunk)
