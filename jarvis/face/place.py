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


NEAR = 40   # points from the circle's edge within which the pointer is followed at the display's pace


def takes_click(px, py, x, y, size) -> bool:
    """Whether the circle's square panel at (x, y) takes the mouse: everywhere but its corners, which pass clicks
    through, so it already takes them when the pointer reaches the circle from outside the square."""
    inside = x <= px <= x + size and y <= py <= y + size
    return not inside or math.hypot(px - x - size / 2, py - y - size / 2) <= size / 2


def follow_every(px, py, x, y, size) -> float:
    """Seconds until the pointer is asked again: a 60th near the circle, where a click must not reach the corners'
    app beneath, a tenth elsewhere."""
    return 1 / 60 if math.hypot(px - x - size / 2, py - y - size / 2) <= size / 2 + NEAR else 0.1


def left(px, py, inside, rects) -> list[str]:
    """The beads the pointer went into (`inside`) that it is now over neither the bead nor where it came in (M6), or
    whose bead is gone. `rects`: agent -> (its frame, where the pointer came in), each with x, y, w, h. Asked with the
    pointer, not only on AppKit's exit, which never comes when a bead moves, resizes, is covered or closes under a
    still pointer."""
    return [a for a in inside if not any(r.x <= px <= r.x + r.w and r.y <= py <= r.y + r.h for r in rects.get(a, ()))]


def single(home: Path, wait: bool = False):
    """The one-face lock, held while the returned file stays open; None while another face holds it, unless it waits
    until that face lets go."""
    home.mkdir(parents=True, exist_ok=True)
    f = open(home / "face.lock", "a")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
    except BlockingIOError:
        f.close()
        return None
    return f
