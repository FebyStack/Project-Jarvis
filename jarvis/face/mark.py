"""Each name's own mark: three rose curves whose petals, depth and offsets come from the name (tether design §4)."""

import math
import zlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Mark:
    petals: int
    depth: float
    offsets: tuple[float, float, float]
    way: int


def mark(name: str) -> Mark:
    h, petals = divmod(zlib.crc32(name.encode()), 5)
    h, depth = divmod(h, 5)
    h, way = divmod(h, 2)
    offsets = tuple(math.tau * (h >> shift & 255) / 256 for shift in (0, 8, 16))
    return Mark(3 + petals, (30 + 5 * depth) / 100, offsets, 1 if way else -1)


def curve(m: Mark, layer: int, n: int = 72) -> tuple[tuple[float, float], ...]:
    points = []
    for i in range(n):
        theta = math.tau * i / n
        r = 1 - m.depth + m.depth * math.cos(m.petals * theta + m.offsets[layer])
        points.append((r * math.cos(theta), r * math.sin(theta)))
    return (*points, points[0])
