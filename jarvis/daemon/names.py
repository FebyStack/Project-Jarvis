"""Names for running agents (Plan 4): short, unlike each other, and none close enough to "Jarvis" to wake it."""
import difflib
import random
from collections.abc import Collection

from jarvis import config

NAMES = (
    "Nova", "Orin", "Vesper", "Kite", "Lumen", "Atlas", "Briar", "Cedar", "Delta", "Ember", "Fable", "Gale", "Harbor",
    "Indigo", "Juno", "Larch", "Maple", "Nimbus", "Onyx", "Pearl", "Quill", "Raven", "Tundra", "Wren", "Xenon",
    "Yarrow", "Zephyr", "Basil", "Cobalt", "Dune", "Echo", "Flint", "Garnet", "Heron", "Iris", "Jasper", "Koda",
    "Lark", "Moss", "Neon", "Opal", "Pike", "Quartz", "Rowan", "Sage", "Thorn", "Ursa", "Vega", "Willow", "Birch",
    "Cinder", "Drift", "Fern", "Hazel", "Jade", "Kelp", "Linden", "Mesa", "Noor", "Olive", "Poppy", "Quince",
    "Sorrel", "Tansy", "Umbra", "Violet", "Wisp", "Yucca", "Zinc", "Bryn", "Clove", "Dawn", "Eden", "Finch", "Grove",
)


def pick(in_use: Collection[str], rng: random.Random = random) -> str:
    free = [n for n in NAMES if n not in in_use]
    if free:
        return rng.choice(free)
    number = 2
    while all(f"{n} {number}" in in_use for n in NAMES):
        number += 1
    return rng.choice([n for n in NAMES if f"{n} {number}" not in in_use]) + f" {number}"


def match(heard: str, running: Collection[str]) -> str | None:
    scored = sorted(((difflib.SequenceMatcher(None, heard.lower(), n.lower()).ratio(), n) for n in running),
                    reverse=True)
    if not scored or scored[0][0] < config.NAME_SIMILARITY:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.1:
        return None
    return scored[0][1]
