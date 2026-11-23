"""Where the circle sits, in AppKit screen points (origin bottom-left), saved in <home>/face.json."""

import json
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
