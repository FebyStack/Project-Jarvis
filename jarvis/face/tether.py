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
    far = cx - screen.x if left else screen.x + screen.w - cx
    room = screen.y + screen.h - cy if up else cy - screen.y
    for step in (config.TETHER_STEP, 0):
        spans, fits = _spans(sizes, up, reach, far, {1: room, -1: screen.h - room}, step)
        if fits:
            break
    frames = tuple(Rect(cx + edge - w if left else cx - edge, cy + low if up else cy - low - h, w, h)
                   for (w, h), (edge, low) in zip(sizes, spans))
    if not fits:   # the last resort: on the screen, even over another bead, rather than a Yes nobody can reach
        frames = tuple(Rect(min(max(f.x, screen.x), screen.x + screen.w - f.w),
                            min(max(f.y, screen.y), screen.y + screen.h - f.h), f.w, f.h) for f in frames)
    anchors = tuple((f.x + f.w - 18 if left else f.x + 18, f.y + f.h - 18) for f in frames)
    half = config.CIRCLE_SIZE / 2
    rects = [Rect(cx - half, cy - half, config.CIRCLE_SIZE, config.CIRCLE_SIZE), *frames]
    x0, y0 = min(r.x for r in rects) - 24, min(r.y for r in rects) - 24
    x1, y1 = max(r.x + r.w for r in rects) + 24, max(r.y + r.h for r in rects) + 24
    return Plume(frames, anchors, "left" if left else "right", "up" if up else "down", Rect(x0, y0, x1 - x0, y1 - y0))


def _spans(sizes, up, reach, far, rooms, step):
    """Each bead's circle-side edge and lower edge, the circle's centre at the origin and the beads up and to its left.

    Branch 1 grows up from the first bead; a bead with no room there hangs in branch -1, below the first bead, which
    is worked out flipped so it grows up too. A bead beyond the ring sits far enough right for its thread to clear the
    bead before it in its branch. On the last try (no step), a bead with room in neither branch wraps, with everything
    after it, into a column just left of all before it, growing up from the first bead's height; its thread runs to
    the circle behind the nearer column, the only way there is.
    """
    at, prev, beyond = {1: -22, -1: 22 + config.CARD_GAP}, {}, {1: 0, -1: 0}
    spans, fits, out = [], True, None

    def edge(d, h):
        b = at[d]
        near = max(b, -b - h, 0)
        if near < config.TETHER_CLEAR:
            return -math.sqrt(config.TETHER_CLEAR ** 2 - near ** 2) - 6
        e = -28 + beyond[d] * step
        if d in prev:
            pe, plo, phi = prev[d]
            lift = h - 18 if (d == 1) == up else 18
            e = max(e, (pe + 6) * (b + lift) / (phi if pe + 6 <= 0 else plo) + 18)
        return e

    for w, h in sizes:
        d = None if out is not None else next(
            (d for d in ((1, -1) if spans else (1,)) if at[d] + h <= rooms[d] and edge(d, h) <= reach), None)
        if d is None and spans and not step:
            if out is None or at[1] + h > rooms[1]:
                out, at[1] = min(e - pw for (e, _), (pw, _) in zip(spans, sizes)) - config.CARD_GAP, -22
            fits = fits and at[1] + h <= rooms[1] and out - w >= -far
            spans.append((out, at[1]))
            at[1] += h + config.CARD_GAP
            continue
        if d is None:
            fits, d = False, 1
        e, b = min(edge(d, h), reach), at[d]
        beyond[d] += max(b, -b - h, 0) >= config.TETHER_CLEAR
        prev[d] = (e, b, b + h)
        if not spans:
            prev[-1] = (e, -b - h, -b)
        at[d] = b + h + config.CARD_GAP
        spans.append((e, b if d == 1 else -b - h))
    return spans, fits


def thread(anchor: P, centre: P, sway: float = 0.0, side: Literal["left", "right"] = "left") -> tuple[P, P, P]:
    (ax, ay), (cx, cy) = anchor, centre
    d = math.dist(anchor, centre)
    ux, uy = (ax - cx) / d, (ay - cy) / d
    sx, sy = ax - ux * 13, ay - uy * 13
    ex, ey = cx + ux * config.TETHER_RIM, cy + uy * config.TETHER_RIM
    bend = (12 + sway) * (1 if side == "left" else -1) * (1 if uy >= 0 else -1)
    return (sx, sy), ((sx + ex) / 2 + uy * bend, (sy + ey) / 2 - ux * bend), (ex, ey)
