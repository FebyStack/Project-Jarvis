from datetime import datetime

import pytest

from jarvis.daemon.instant import match, match_named, say_date, say_time


@pytest.mark.parametrize("said,action", [
    ("What time is it?", "time"), ("Hey Jarvis, what's the time", "time"), ("jarvis please what day is it", "date"),
    ("what's the date", "date"), ("Stop listening.", "mute"), ("mute", "mute"), ("start listening", "unmute"),
    ("unmute", "unmute"), ("Never mind", "cancel"), ("cancel", "cancel"), ("stop", "cancel"),
    ("repeat that", "repeat"), ("say that again", "repeat"), ("status", "status"), ("what are you working on", "status"),
])
def test_phrases(said, action):
    assert match(said, pending=False) == action


@pytest.mark.parametrize("said", ["what time is it in Tokyo", "stop the build", "status of the export", "", "jarvis"])
def test_extra_words_go_to_the_model(said):
    assert match(said, pending=False) is None


def test_yes_no_only_while_a_question_is_open():
    assert [match(s, pending=True) for s in ("Yes.", "no", "yes always", "Yes, always")] == ["yes", "no", "always", "always"]
    assert match("yes", pending=False) is None


def test_sentences():
    at = datetime(2026, 11, 14, 20, 4)
    assert say_time(at) == "It's 8:04 PM."
    assert say_date(at) == "Saturday, 14 November."


def test_named_phrases():
    run = ["Nova", "Orin"]
    assert match_named("Jarvis, stop Nova.", run) == ("stop", "Nova")
    assert match_named("yes to Orin", run) == ("yes", "Orin") and match_named("no to nova", run) == ("no", "Nova")
    assert match_named("yes always to Nova", run) == ("always", "Nova")
    assert match_named("stop", run) is None and match_named("stop the music", run) is None
    assert match_named("stop Vesper", run) is None
    assert match_named("tell Nova to stop", run) is None
