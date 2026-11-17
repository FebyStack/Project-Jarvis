import pytest

from jarvis import config
from jarvis.voice import wake


@pytest.mark.parametrize("word", ["jarvis", "Jervis", "jovis", "javis", "jarvas", "Jarvis's", "darvis", "carvis",
                                  "javi", "Javier"])  # Task 14: heard on his voice
def test_words_that_wake(word):
    assert wake.sounds_like_name(word)


@pytest.mark.parametrize("word", ["travis", "davis", "avis", "mavis", "paris", "jars", "jar", "pervis", "agries",
                                  "service", "harvest", "java", "jarring", ""])
def test_words_that_do_not(word):
    assert not wake.sounds_like_name(word)


def test_also_list_wakes_exactly(monkeypatch):
    monkeypatch.setattr(config, "WAKE_ALSO", frozenset({"pervis"}))
    assert wake.sounds_like_name("Pervis") and not wake.sounds_like_name("pervert")


def test_split_keeps_the_request_as_spoken():
    assert wake.split("Hey Jervis, set a timer for 10 minutes.") == "set a timer for 10 minutes."
    assert wake.split("Okay so Jarvis open Mail") == "open Mail"
    assert wake.split("Jarvis.") == "" and wake.split("Hey, Jarvis's") == ""


def test_split_without_the_comma_after_the_name():
    assert wake.split("Hey Javis set a timer for ten minutes") == "set a timer for ten minutes"


def test_split_finds_no_name():
    assert wake.split("I told Travis about it") is None
    assert wake.split("one two three Jarvis") is None  # only the first three words count
    assert wake.split("") is None
