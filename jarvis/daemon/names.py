"""Names for running agents (Plan 4): short, unlike each other, none close enough to "Jarvis" to wake it, and none
that a common English word could pass for."""
import difflib
import functools
import random
from collections.abc import Collection
from pathlib import Path

from jarvis import config

NAMES = (
    "Nova", "Orin", "Vesper", "Kite", "Lumen", "Atlas", "Briar", "Cedar", "Delta", "Ember", "Fable", "Gale", "Harbor",
    "Osprey", "Juno", "Larch", "Myrtle", "Nimbus", "Onyx", "Pearl", "Quill", "Raven", "Tundra", "Wren", "Xenon",
    "Yarrow", "Zephyr", "Basil", "Cobalt", "Dune", "Echo", "Tiger", "Garnet", "Heron", "Iris", "Jasper", "Koda",
    "Lark", "Nettle", "Neon", "Opal", "Pike", "Quartz", "Rowan", "Sage", "Thorn", "Ursa", "Lilac", "Willow", "Birch",
    "Cinder", "Drift", "Fern", "Hazel", "Jade", "Kelp", "Linden", "Laurel", "Noor", "Jaguar", "Dahlia", "Quince",
    "Lotus", "Tansy", "Umbra", "Violet", "Wisp", "Yucca", "Zinc", "Bryn", "Clove", "Dawn", "Eden", "Finch", "Grove",
)


def pick(in_use: Collection[str], rng: random.Random = random) -> str:
    free = [n for n in NAMES if n not in in_use]
    if free:
        return rng.choice(free)
    number = 2
    while all(f"{n} {number}" in in_use for n in NAMES):
        number += 1
    return rng.choice([n for n in NAMES if f"{n} {number}" not in in_use]) + f" {number}"


WORDS = Path("/usr/share/dict/words")
_ENDINGS = ("s", "es", "ed", "d", "er", "ing")
_ALIKE = str.maketrans("vf", "bp")   # Febriel's Bisaya accent: b and v, p and f, are one first letter


@functools.cache
def _words() -> str:
    try:
        return "\n" + WORDS.read_text().lower() + "\n"
    except OSError:
        return ""


def _ordinary(word: str) -> bool:
    """An English word, or one with a plural or verb ending. Without the word list, every word counts as one."""
    words = _words()
    return not words or any(f"\n{w}\n" in words for w in {word, *(word.removesuffix(e) for e in _ENDINGS)})


def match(heard: str, running: Collection[str]) -> str | None:
    """The running name heard, or a close mis-hearing of it: the same first letter (b and v, p and f, alike), a
    length within one letter, and not an English word."""
    heard = heard.lower()
    scored = sorted(((difflib.SequenceMatcher(None, heard, n.lower()).ratio(), n) for n in running), reverse=True)
    if not scored or scored[0][0] < config.NAME_SIMILARITY:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.1:
        return None
    best = scored[0][1]
    if heard == best.lower():
        return best
    close = (heard[0].translate(_ALIKE) == best[0].lower().translate(_ALIKE) and abs(len(heard) - len(best)) <= 1
             and not _ordinary(heard))
    return best if close else None
