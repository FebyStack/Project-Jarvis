import pytest

from jarvis.daemon.state import FOLLOW_UP_SECONDS, Event, State

HAPPY = (Event.WAKE, Event.SPEECH_END, Event.REPLY_START, Event.REPLY_END)


def reach(sm, state):
    for event in HAPPY:
        if sm.state == state:
            return
        sm.on(event)
    assert sm.state == state


def test_follow_up_constant():
    assert FOLLOW_UP_SECONDS == 6.0


def test_happy_path(sm):
    assert [sm.on(e) for e in (Event.WAKE, Event.SPEECH_END, Event.REPLY_START, Event.REPLY_END)] == \
        [State.LISTENING, State.THINKING, State.SPEAKING, State.FOLLOW_UP]


def test_follow_up_needs_no_wake_word(sm, clock):
    reach(sm, State.FOLLOW_UP); clock.advance(5.9)
    assert sm.on(Event.SPEECH_START) == State.LISTENING


def test_follow_up_expires_after_six_seconds(sm, clock):
    reach(sm, State.FOLLOW_UP); clock.advance(6.0)
    assert sm.on(Event.TICK) == State.IDLE
    assert sm.on(Event.SPEECH_START) == State.IDLE


def test_follow_up_expiry_checked_on_any_event(sm, clock):
    reach(sm, State.FOLLOW_UP); clock.advance(6.5)
    assert sm.on(Event.SPEECH_START) == State.IDLE


def test_wake_ignored_while_speaking_or_thinking(sm):
    reach(sm, State.THINKING); assert sm.on(Event.WAKE) == State.THINKING
    sm.on(Event.REPLY_START); assert sm.on(Event.WAKE) == State.SPEAKING


def test_mic_closed_while_speaking(sm):
    reach(sm, State.SPEAKING); assert sm.mic_open is False
    sm.on(Event.REPLY_END); assert sm.mic_open is True


def test_mute_closes_mic_and_ignores_wake(sm):
    sm.on(Event.MUTE)
    assert sm.mic_open is False and sm.on(Event.WAKE) == State.IDLE
    sm.on(Event.UNMUTE); assert sm.on(Event.WAKE) == State.LISTENING


def test_mute_while_listening_returns_to_idle(sm):
    reach(sm, State.LISTENING)
    assert sm.on(Event.MUTE) == State.IDLE and sm.mic_open is False


def test_unexpected_events_do_not_move_state(sm):
    assert sm.on(Event.REPLY_END) == State.IDLE and sm.on(Event.SPEECH_END) == State.IDLE


def test_muted_reply_end_goes_idle_not_follow_up(sm):
    reach(sm, State.THINKING); sm.on(Event.MUTE)
    sm.on(Event.REPLY_START)
    assert sm.on(Event.REPLY_END) == State.IDLE
    assert sm.on(Event.SPEECH_START) == State.IDLE


def test_reply_end_without_speaking_leaves_thinking(sm):
    reach(sm, State.THINKING)
    assert sm.on(Event.REPLY_END) == State.IDLE


@pytest.mark.parametrize("start", [State.LISTENING, State.THINKING, State.SPEAKING, State.FOLLOW_UP])
def test_cancel_returns_to_idle(sm, start):
    reach(sm, start)
    assert sm.on(Event.CANCEL) is State.IDLE


def test_cancel_in_idle_and_while_muted(sm):
    assert sm.on(Event.CANCEL) is State.IDLE
    sm.on(Event.MUTE); sm.on(Event.CANCEL)
    assert sm.muted is True


@pytest.mark.parametrize("state", [State.IDLE, State.THINKING, State.SPEAKING, State.FOLLOW_UP])
def test_the_key_listens_from_every_state(sm, state):
    reach(sm, state); assert sm.on(Event.PUSH) is State.LISTENING


def test_the_key_listens_while_muted_and_only_then_is_the_mic_open(sm):
    sm.on(Event.MUTE); assert not sm.mic_open
    assert sm.on(Event.PUSH) is State.LISTENING and sm.mic_open
    sm.on(Event.SPEECH_END); assert not sm.mic_open            # back to shut once the request is in


def test_a_typed_request_thinks_then_speaks(sm):
    assert [sm.on(e) for e in (Event.REQUEST, Event.REPLY_START, Event.REPLY_END)] == \
        [State.THINKING, State.SPEAKING, State.FOLLOW_UP]


def test_an_announcement_speaks_from_idle(sm):
    assert sm.on(Event.REPLY_START) is State.SPEAKING and not sm.mic_open


def test_speech_that_runs_out_mid_turn_goes_back_to_thinking(sm):
    reach(sm, State.SPEAKING); assert sm.on(Event.REPLY_PAUSE) is State.THINKING


def test_listening_gives_up_after_eight_seconds(sm, clock):
    sm.on(Event.WAKE); clock.advance(7.9); assert sm.on(Event.TICK) is State.LISTENING
    clock.advance(0.1); assert sm.on(Event.TICK) is State.IDLE


def test_listening_does_not_give_up_mid_sentence(sm, clock):
    sm.on(Event.WAKE); sm.on(Event.SPEECH_START); clock.advance(30); assert sm.on(Event.TICK) is State.LISTENING


def test_a_name_still_wakes_only_from_idle(sm):
    reach(sm, State.THINKING); assert sm.on(Event.WAKE) is State.THINKING


def test_waking_again_while_listening_restarts_the_eight_seconds(sm, clock):
    sm.on(Event.WAKE); sm.on(Event.SPEECH_START); clock.advance(5); sm.on(Event.WAKE)
    clock.advance(7.9); assert sm.on(Event.TICK) is State.LISTENING
    clock.advance(0.1); assert sm.on(Event.TICK) is State.IDLE
