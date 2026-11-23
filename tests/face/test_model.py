import pytest

from jarvis import config
from jarvis.face.model import Card, Circle, FaceView, Stack, circle, more_text, new_alerts, reduce, stack
from tests.face.events import agents, asking, face, front, health, hover, level, link, snapshot, state, worker


def view(*events):
    v = FaceView.empty()
    for e in events:
        v = reduce(v, e)
    return v


def cards(v, now=1500.0):
    return stack(v, now).cards


def test_only_workers_are_cards():
    rows = [front(), worker(id="a", name="triage", call=""), worker(id="b", name="scribe", call=""), worker(id="c"), worker(id="d", name="researcher")]
    assert {c.id for c in cards(view(agents(*rows)))} == {"c", "d"}


def test_a_card_shows_its_agent():
    assert cards(view(agents(worker())), now=1252.0)[0] == Card(
        "t1", "Nova", "coder", "opus", "Fix export bug", "Running tests", "04:12", "working", None, None, True, False, None, "")


def test_jarvis_is_a_card_only_while_it_asks():
    assert cards(view(agents(front("working")))) == ()
    c = cards(view(agents(front("needs_you", question="Delete?", ask_id="k", ask_until=1560.0))), now=1500.0)[0]
    assert (c.id, c.name, c.stop, c.open, c.question) == ("jarvis", "Jarvis", True, True, "Delete?")


def test_questions_first_then_newest_working_then_ended():
    rows = [worker(id="old", since=1.0), worker("done", id="end", since=5.0), worker(id="new", since=9.0),
            asking(id="q2", until=1100.0), asking(id="q1", until=1070.0)]
    assert [c.id for c in cards(view(agents(*rows)), now=1000.0)] == ["q1", "q2", "new", "old", "end"]


def test_five_show_and_the_rest_are_counted():
    rows = [asking(id=f"t{i}", until=1060.0 + i) if i < 2 else worker(id=f"t{i}", since=float(i)) for i in range(7)]
    s = stack(view(agents(*rows)), 1000.0)
    assert [c.id for c in s.cards[:2]] == ["t0", "t1"]
    assert (len(s.cards), s.more_working, s.more_asking) == (5, 2, 0)


def test_a_sixth_question_is_counted_as_asking():
    s = stack(view(agents(*[asking(id=f"t{i}", until=1060.0 + i) for i in range(6)])), 1000.0)
    assert (len(s.cards), s.more_working, s.more_asking) == (5, 0, 1)


def test_elapsed_counts_from_since():
    assert cards(view(agents(worker(since=1000.0))), now=1252.0)[0].elapsed == "04:12"


def test_a_new_card_is_open_for_four_seconds_then_one_line():
    v = view(agents(worker(since=1000.0)))
    assert cards(v, 1003.9)[0].open and not cards(v, 1004.0)[0].open


def test_hover_opens_a_working_card_and_leaving_closes_it():
    v = view(agents(worker(since=1000.0)), hover("t1"))
    assert cards(v, 1100.0)[0].open
    assert not cards(reduce(v, hover("t1", False)), 1100.0)[0].open


def test_a_question_is_open_however_old_and_unhovered():
    assert cards(view(agents(asking(since=1.0))), 1000.0)[0].open


def test_an_ended_card_is_one_line_even_hovered():
    c = cards(view(agents(worker("done", since=1000.0)), hover("t1")), 1001.0)[0]
    assert not c.open and not c.stop


def test_hover_for_a_card_that_is_gone_is_forgotten():
    v = view(agents(worker(id="t1")), hover("t9"), agents(worker(id="t9", since=1.0)))
    assert not cards(v, 1000.0)[0].open
    v = view(agents(worker(id="t9", since=1.0)), hover("t9"), agents(worker(id="t1")), agents(worker(id="t9", since=1.0)))
    assert not cards(v, 1000.0)[0].open


def test_the_countdown_follows_ask_until():
    def c(until, channel): return cards(view(agents(asking(until=until, channel=channel))), 1000.0)[0]
    assert (c(1042.0, "mac").left, c(1042.0, "mac").left_text) == (pytest.approx(0.7), "No in 42 s")
    assert (c(1540.0, "phone").left, c(1540.0, "phone").left_text) == (pytest.approx(0.9), "No in 9 min")
    assert (c(990.0, "mac").left, c(990.0, "mac").left_text) == (0.0, "No in 0 s")


@pytest.mark.parametrize("working, asking_, text", [(0, 0, ""), (2, 0, "+2 more working"), (0, 1, "+1 more needs you"),
                                                    (2, 2, "+2 more need you · +2 more working")])
def test_the_more_line(working, asking_, text):
    assert more_text(Stack((), working, asking_)) == text


@pytest.mark.parametrize("events, mode, word", [
    ([link("no daemon")], "off", "NO DAEMON"), ([health(brain="offline")], "off", "OFFLINE"),
    ([health(brain="limit")], "off", "LIMIT"), ([state("SPEAKING")], "talk", ""), ([state("LISTENING")], "listen", ""),
    ([state("THINKING")], "work", ""), ([agents(worker("working"))], "work", ""),
    ([state("IDLE", muted=True)], "muted", ""), ([], "idle", "")])
def test_circle_mode(events, mode, word):
    c = circle(view(*events))
    assert (c.mode, c.word) == (mode, word)


def test_talking_beats_working_and_off_beats_everything():
    assert circle(view(agents(worker()), state("SPEAKING"))).mode == "talk"
    assert circle(view(state("SPEAKING"), health(brain="down"))).mode == "off"
    assert circle(view(state("SPEAKING"), link("no daemon"))).word == "NO DAEMON"


def test_the_ring_is_on_while_any_question_is_open():
    assert not circle(view(agents(worker()))).ring
    assert circle(view(agents(worker(), asking(id="t2")))).ring


def test_level_follows_the_right_source():
    v = view(level(0.4, "mic"), level(0.7, "voice"))
    assert circle(reduce(v, state("LISTENING"))).level == 0.4
    assert circle(reduce(v, state("SPEAKING"))).level == 0.7
    assert circle(reduce(v, state("THINKING"))).level == 0.0


def test_a_lost_daemon_clears_every_card():
    v = view(agents(worker(), asking(id="t2")), hover("t1"))
    assert len(cards(v)) == 2
    assert stack(reduce(v, link("no daemon")), 1500.0) == Stack((), 0, 0)



@pytest.mark.parametrize("brain", ["offline", "down", "limit"])
def test_an_offline_or_limited_brain_shows_no_cards_until_it_is_back(brain):
    v = view(agents(worker(), asking(id="t2")), health(brain=brain))
    assert circle(v).mode == "off" and stack(v, 1500.0) == Stack((), 0, 0)
    assert len(cards(reduce(v, health(brain="online")))) == 2

def test_a_snapshot_replaces_what_was_shown():
    v = view(agents(worker(id="a")), link("no daemon"), snapshot(worker(id="b")))
    assert [c.id for c in cards(v)] == ["b"] and circle(v).mode == "work"


def test_unknown_or_missing_fields_do_not_break_it():
    row = {"id": "t1", "name": "coder", "state": "working", "since": 1000.0, "extra": 1}
    v = view(agents(row), {"type": "nope"}, {"type": "level", "rms": 0.2})
    c = cards(v, 1001.0)[0]
    assert (c.id, c.name, c.role, c.left) == ("t1", "coder", "coder", None)


def test_a_new_mac_question_alerts_once_and_a_phone_one_never():
    before = view(agents(worker()))
    after = reduce(before, agents(asking()))
    assert new_alerts(before, after) and not new_alerts(after, reduce(after, agents(asking())))
    assert not new_alerts(before, reduce(before, agents(asking(channel="phone"))))


def test_jarvis_working_on_a_request_is_work():   # the final review's M2: the front door's turn, a phone request
    assert circle(view(agents(front("working")))).mode == "work"
    assert circle(view(agents(front("idle")))).mode == "idle"


def test_off_draws_no_ring():   # M1: tether design §9, everything vanishes while jarvisd is gone, offline or limited
    assert not circle(view(agents(asking()), health(brain="offline"))).ring
    jarvis_asks = front("needs_you", question="Delete?", ask_id="k", ask_until=1560.0)
    assert circle(view(agents(jarvis_asks), state("IDLE", muted=True))) == Circle("muted", True, "", 0.0)


def test_a_bead_shows_the_model_without_claude():   # M4
    assert cards(view(agents(worker(model="claude-opus-5-5"))))[0].model == "opus-5-5"


def test_a_row_with_no_model_shows_none():   # re-review N3
    assert cards(view(agents(worker(model=None))))[0].model == ""
    row = worker(); row.pop("model", None)
    assert cards(view(agents(row)))[0].model == ""


@pytest.mark.parametrize("event", [
    {"type": "snapshot"}, {"type": "state"}, {"type": "level"}, {"type": "agents"}, {"type": "level", "rms": "loud"},
    {"type": "snapshot", "state": "x", "health": 3, "agents": 5}, {"type": "agents", "items": 7}])
def test_an_event_with_missing_or_broken_fields_never_breaks_it(event):   # M9: a jarvisd of another version
    v = reduce(view(agents(worker())), event)
    circle(v), stack(v, 1500.0)


def test_a_snapshot_with_missing_fields_is_read_with_defaults():   # M9
    v = view({"type": "snapshot", "state": {}, "agents": [worker()]})
    assert (v.link, v.voice, v.brain, [c.id for c in cards(v)]) == ("online", "IDLE", "online", ["t1"])


def test_the_face_is_hidden_as_jarvisd_says():   # Ctrl-Option-J, Febriel 2026-11-23
    assert view(snapshot(hidden=True)).hidden and not view(snapshot(hidden=True), face(False)).hidden
    assert view(snapshot(), face(True)).hidden and not view(snapshot()).hidden
    assert not view({"type": "snapshot"}).hidden   # a jarvisd without the key: shown
    assert not view(snapshot(hidden=True), link("no daemon")).hidden   # the key lives in jarvisd, which starts shown
