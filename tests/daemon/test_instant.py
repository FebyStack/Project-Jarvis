from datetime import datetime

import pytest

from jarvis.daemon.instant import match, match_named, say_date, say_time
from jarvis.daemon.names import NAMES


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


def test_an_ordinary_word_is_never_a_running_name():   # Review Focus 2; the final review's I1
    cases = [("Jarvis, stop working", "Orin"), ("stop Finder", "Cinder"), ("stop volume", "Lumen"), ("stop Mike", "Pike"),
             ("yes to her", "Heron"), ("yes to each", "Echo"), ("yes to ours", "Ursa"), ("stop, dude", "Dune"),
             ("no to sorry", "Sorrel"), ("stop quiet", "Quince")]
    for said, name in cases:
        assert match_named(said, {name, "Nova"}) is None, said


def test_a_close_mishearing_still_names_the_agent():
    run = {"Nova", "Orin", "Vesper"}
    assert match_named("stop nova", run) == ("stop", "Nova") and match_named("stop novah", run) == ("stop", "Nova")
    assert match_named("yes to orin", run) == ("yes", "Orin")


COMMON = ("it that this now there here please all both everything everyone none one each either her him them ours "
          "working talking listening playing recording reading running waiting typing music timer alarm alarms "
          "down done most when were same safe save keep kept pick great always clear close cover even only game gave "
          "goal hero heroes male males basic basics delay delays false failed thanks birth draft lines finish french "
          "launch kit kits june online vegan mega indie finest mapped popped newborn echoing fearing quicker dude "
          "sorry quiet volume mike finder").split()


def test_no_common_word_names_any_agent_in_the_list():
    for name in NAMES:
        for word in COMMON:
            assert match_named(f"stop {word}", {name}) is None, (word, name)
