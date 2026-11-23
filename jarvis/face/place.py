"""Where the circle sits, in AppKit screen points (origin bottom-left), saved in <home>/face.json; and that it sits
there once."""

import fcntl
import json
import math
from pathlib import Path

MARGIN = 40


def load(home: Path) -> tuple[float, float] | None:
    try:
        data = json.loads((home / "face.json").read_text())
        x, y = data["x"], data["y"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (x, y)):
        return x, y
    return None


def save(home: Path, x: float, y: float) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "face.json").write_text(json.dumps({"x": x, "y": y}))


def on_screen(x, y, size, screen_w, screen_h) -> tuple[float, float]:
    return min(max(x, 0), screen_w - size), min(max(y, 0), screen_h - size)


def default(size, screen_w, screen_h) -> tuple[float, float]:
    return screen_w - size - MARGIN, MARGIN


def takes_click(px, py, x, y, size) -> bool:
    """Whether the pointer is over the round circle in its square panel at (x, y): the corners pass clicks through."""
    return math.hypot(px - x - size / 2, py - y - size / 2) <= size / 2


def single(home: Path):
    """The one-face lock, held while the returned file stays open; None while another face holds it."""
    home.mkdir(parents=True, exist_ok=True)
    f = open(home / "face.lock", "a")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return None
    return f
