from datetime import datetime

import pytest

from jarvis.daemon.instant import match, match_named, named_shape, say_date, say_time
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


def test_a_name_works_without_to():   # Febriel's live run: "Jarvis, yes to Finch" was heard as "yes, Pinch."
    run = {"Nova", "Orin", "Fable"}
    assert match_named("Jarvis, yes, Pable.", run) == ("yes", "Fable") and match_named("yes Nova", run) == ("yes", "Nova")
    assert match_named("no Orin", run) == ("no", "Orin") and match_named("Hey Jarvis, no, nova.", run) == ("no", "Nova")
    assert match_named("yes always Nova", run) == ("always", "Nova")
    assert match_named("yes always to Nova", run) == ("always", "Nova")


def test_a_name_phrase_at_the_end_of_a_sentence_counts():   # Febriel's live run: "I meant no to Slate" missed
    run = {"Nova", "Orin", "Slate"}
    assert match_named("I meant no to Slate.", run) == ("no", "Slate")
    assert match_named("Okay, yes Nova.", run) == ("yes", "Nova")
    assert match_named("Sorry, stop Orin.", run) == ("stop", "Orin")
    assert match_named("I said yes always to Nova", run) == ("always", "Nova")
    assert match_named("tell Nova to stop", run) is None and match_named("stop Nova for now", run) is None
    assert match_named("I know Nova", run) is None and match_named("casino Nova", run) is None
    for said in ("stop the music", "yes please", "no thanks", "I said no to her", "we have to stop working",
                 "let's say yes to everything", "okay, yes to each", "sorry, stop quiet"):
        for name in NAMES:
            assert match_named(said, {name}) is None, (said, name)


def test_a_bare_yes_or_no_at_the_end_of_a_sentence_answers_nothing():
    for said in ("I said yes", "okay, no", "I meant yes always", "sorry, stop"):
        assert match(said, pending=True) is None, said


def test_a_plain_yes_or_no_never_names_an_agent():
    for name in NAMES:
        for said in ("yes please", "no thanks", "yes always", "Yes, always.", "no problem", "yes sir", "no way"):
            assert match_named(said, {name}) is None, (said, name)


def test_the_shape_of_a_name_phrase():
    for said in ("yes, Pinch.", "Jarvis, stop Kelp", "no to Nobody", "yes always to Nova", "yes please",
                 "I meant no to Slate"):
        assert named_shape(said), said
    for said in ("tell Nova to stop", "stop the music", "stop", "yes", "never mind", "what time is it"):
        assert not named_shape(said), said


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


def test_b_and_v_p_and_f_count_as_one_first_letter():   # Febriel's ruling: his Bisaya accent
    assert match_named("stop besper", {"Vesper", "Nova"}) == ("stop", "Vesper")
    assert match_named("yes to pable", {"Fable", "Nova"}) == ("yes", "Fable")
    assert match_named("stop vasil", {"Basil", "Nova"}) == ("stop", "Basil")
    assert match_named("stop fine", {"Pine", "Nova"}) is None


def test_only_a_common_word_is_refused():   # Febriel's live run: Wisp was heard as "whisp"; his choice, the 10,000 commonest
    assert match_named("yes to whisp", {"Wisp", "Nova"}) == ("yes", "Wisp")
    assert match_named("stop pinch", {"Finch", "Nova"}) == ("stop", "Finch")


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
            assert match_named(f"I meant no to {word}", {name}) is None, (word, name)
