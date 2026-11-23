import difflib
import itertools
import random

from jarvis.daemon import names
from jarvis.daemon.names import NAMES, match, pick
from jarvis.voice import wake


def test_the_list_is_long_and_its_names_cannot_be_confused():
    assert len(NAMES) >= 60 and len(set(NAMES)) == len(NAMES)
    assert {"Nova", "Orin", "Vesper", "Kite", "Lumen"} <= set(NAMES)
    for a, b in itertools.combinations(NAMES, 2):
        assert difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() < 0.7, (a, b)
    for n in NAMES:
        assert n.isalpha() and 4 <= len(n) <= 6 and not wake.sounds_like_name(n)
        assert n.lower() not in {"yes", "no", "stop", "always", "cancel", "mute", "status"}


def test_pick_avoids_names_in_use():
    assert pick(set(NAMES) - {"Kite"}) == "Kite"


def test_pick_when_every_name_is_taken_adds_a_number():
    assert pick(set(NAMES), random.Random(0)).split()[-1] == "2"
    taken = set(NAMES) | {f"{n} 2" for n in NAMES}
    assert pick(taken, random.Random(0)).split()[-1] == "3"


def test_match_is_loose_but_only_among_the_running():
    assert match("nova", ["Nova", "Orin"]) == "Nova" and match("NOVA", ["Nova"]) == "Nova"
    assert match("novah", ["Nova", "Orin"]) == "Nova"
    assert match("never", ["Nova", "Orin"]) is None
    assert match("vesper", ["Nova", "Orin"]) is None
    assert match("nova", []) is None


def test_match_refuses_to_choose_between_two_close_names():
    assert match("nora", ["Nova", "Nori"]) is None


def test_without_the_word_list_only_the_exact_name_counts(monkeypatch, tmp_path):
    monkeypatch.setattr(names, "WORDS", tmp_path / "missing")
    names._words.cache_clear()
    try:
        assert match("novah", ["Nova"]) is None and match("nova", ["Nova"]) == "Nova"
    finally:
        names._words.cache_clear()
