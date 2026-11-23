"""Where each bead hangs around the circle and how its thread runs (tether design §5, §6). Pure; no AppKit.

Screen points, origin bottom-left, as AppKit has it. Worked out for the circle in the lower right; the rest mirror it.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from jarvis import config

P = tuple[float, float]


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class Plume:
    frames: tuple[Rect, ...]
    anchors: tuple[P, ...]
    side: Literal["left", "right"]
    grow: Literal["up", "down"]
    field: Rect


def plume(centre: P, screen: Rect, sizes: Sequence[tuple[float, float]]) -> Plume:
    cx, cy = centre
    left = cx > screen.x + screen.w / 2
    up = cy < screen.y + screen.h / 2
    reach = (screen.x + screen.w - cx if left else cx - screen.x) - 16
    frames, anchors, bottom, above = [], [], -22, 0
    for w, h in sizes:
        near = max(bottom, -bottom - h, 0)
        if near < config.TETHER_CLEAR:
            edge = -math.sqrt(config.TETHER_CLEAR ** 2 - near ** 2) - 6
        else:
            edge = -28 + above * config.TETHER_STEP
            above += 1
        edge = min(edge, reach)
        f = Rect(cx + edge - w if left else cx - edge, cy + bottom if up else cy - bottom - h, w, h)
        frames.append(f)
        anchors.append((f.x + f.w - 18 if left else f.x + 18, f.y + f.h - 18))
        bottom += h + config.CARD_GAP
    half = config.CIRCLE_SIZE / 2
    rects = [Rect(cx - half, cy - half, config.CIRCLE_SIZE, config.CIRCLE_SIZE), *frames]
    x0, y0 = min(r.x for r in rects) - 24, min(r.y for r in rects) - 24
    x1, y1 = max(r.x + r.w for r in rects) + 24, max(r.y + r.h for r in rects) + 24
    return Plume(tuple(frames), tuple(anchors), "left" if left else "right", "up" if up else "down",
                 Rect(x0, y0, x1 - x0, y1 - y0))


def thread(anchor: P, centre: P, sway: float = 0.0) -> tuple[P, P, P]:
    (ax, ay), (cx, cy) = anchor, centre
    d = math.dist(anchor, centre)
    ux, uy = (ax - cx) / d, (ay - cy) / d
    sx, sy = ax - ux * 13, ay - uy * 13
    ex, ey = cx + ux * config.TETHER_RIM, cy + uy * config.TETHER_RIM
    bend = 12 + sway
    return (sx, sy), ((sx + ex) / 2 + uy * bend, (sy + ey) / 2 - ux * bend), (ex, ey)
