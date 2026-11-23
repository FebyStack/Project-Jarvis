import asyncio
import logging
from collections import deque

import numpy as np
import pytest

from jarvis import config
from jarvis.daemon.instant import say_time
from jarvis.daemon.state import State
from jarvis.voice.loop import Voice
from jarvis.voice.segment import Segmenter, Utterance
from tests.conftest import NOW, FakeSpeaker, day_log, until
from tests.daemon.events import turn

SPEECH = np.full(480, 1000, dtype=np.int16)
SILENCE = np.zeros(480, dtype=np.int16)


class FakeEngines:
    """Transcribes to the next queued text ("" when none is queued); a queued exception is raised instead."""
    def __init__(self):
        self.texts, self.calls, self.load_says, self.lengths = deque(), 0, None, []

    def hears(self, *texts):
        self.texts.extend(texts)

    async def load(self):
        return self.load_says

    def close(self):
        self.closed = True

    async def transcribe(self, pcm):
        self.calls += 1
        self.lengths.append(len(pcm))
        t = self.texts.popleft() if self.texts else ""
        if isinstance(t, Exception):
            raise t
        return t


class FakeMic:
    def __init__(self):
        self.on_frame = self.on_word = None
        self.running, self.starts, self.stops = False, 0, 0

    def start(self):
        if not self.running:
            self.running, self.starts = True, self.starts + 1
            self.on_word("on")

    def stop(self):
        if self.running:
            self.running, self.stops = False, self.stops + 1


def utt(seconds=1.0, cut=False):
    return Utterance(np.zeros(int(seconds * 16000), dtype=np.int16), cut)


def collect(j):
    """Every event `j` publishes from now on."""
    q = asyncio.Queue(); j._subs.append(q)
    seen = []

    def read():
        while not q.empty():
            seen.append(q.get_nowait())
        return seen
    return read


async def feed(voice, frame, n):
    for _ in range(n):
        voice.on_frame(frame)
    await asyncio.sleep(0.01)  # let the hops to the loop run


@pytest.fixture
def speaker():
    return FakeSpeaker()


@pytest.fixture
async def jarvis(make, speaker):
    return await make(speaker=speaker)


@pytest.fixture
def engines():
    return FakeEngines()


@pytest.fixture
def mic():
    return FakeMic()


class FakeKeys:
    """`listen` for Voice: keeps the callback; never a real key listener."""
    def __init__(self):
        self.on_kind = self.on_face = None
        self.stopped = False

    def __call__(self, on_kind, on_face):
        self.on_kind, self.on_face = on_kind, on_face
        return lambda: setattr(self, "stopped", True)


@pytest.fixture
def keys():
    return FakeKeys()


@pytest.fixture
async def voice(jarvis, engines, mic, keys):
    v = Voice(jarvis, engines, mic, Segmenter(lambda f: 1.0 if f.any() else 0.0), listen=keys)
    await v.start()
    yield v
    await v.stop()


async def speaking(jarvis, speaker):
    """Jarvis answers a typed "what time is it" and is speaking it."""
    await jarvis.submit("what time is it", "mac"); speaker.on_start()
    assert jarvis.state is State.SPEAKING


async def asking(jarvis, speaker, bridge):
    """Jarvis answers a typed request with a question and is speaking it: the follow-up window comes next."""
    t = asyncio.create_task(jarvis.submit("remind me", "mac")); await bridge.got("remind me")
    bridge.emit(turn("For when?")); await t; speaker.on_start()
    assert jarvis.state is State.SPEAKING


async def test_speech_without_the_name_leaves_no_trace(voice, jarvis, engines, vault, caplog):
    caplog.set_level(logging.DEBUG)
    seen = collect(jarvis); engines.hears("I told Travis the door code is 4417")
    await voice.on_utterance(utt()); await asyncio.sleep(0.01)
    assert seen() == [] and "4417" not in caplog.text and caplog.text == "" and not list(vault.raw.glob("*.md"))


async def test_a_failed_transcription_leaves_no_trace_and_no_stuck_state(voice, jarvis, engines, bridge, vault, caplog):
    engines.hears("Jarvis."); await voice.on_utterance(utt()); assert jarvis.state is State.LISTENING
    seen = collect(jarvis); engines.hears(RuntimeError("Jarvis, the door code is 4417"))
    await voice.on_utterance(utt()); await asyncio.sleep(0.01)
    assert jarvis.state is State.IDLE and bridge.sent == [] and not list(vault.raw.glob("*.md"))
    assert "RuntimeError" in caplog.text and "4417" not in caplog.text
    assert [e["type"] for e in seen()] == ["state"]


async def test_a_failed_transcription_of_speech_nobody_asked_for_is_not_logged(voice, jarvis, engines, caplog):
    caplog.set_level(logging.DEBUG)
    engines.hears(RuntimeError("the door code is 4417")); await voice.on_utterance(utt()); await asyncio.sleep(0.01)
    assert jarvis.state is State.IDLE and caplog.text == ""


async def test_a_request_in_one_breath(voice, jarvis, engines, speaker, vault):
    engines.hears("Jervis, what time is it?"); await voice.on_utterance(utt())
    await until(lambda: ("say", say_time(NOW)) in speaker.calls)
    assert "what time is it?" in day_log(vault)


async def test_the_name_alone_listens_and_the_next_utterance_is_the_request(voice, jarvis, engines, speaker, bridge):
    engines.hears("Jarvis.", "open Mail")
    await voice.on_utterance(utt()); assert jarvis.state is State.LISTENING and ("cue",) in speaker.calls
    await voice.on_utterance(utt()); await bridge.got("open Mail")


async def test_the_follow_up_window_needs_no_name(voice, jarvis, engines, speaker, bridge):
    await asking(jarvis, speaker, bridge); speaker.on_done(); assert jarvis.state is State.FOLLOW_UP
    await feed(voice, SPEECH, 1); assert jarvis.state is State.LISTENING
    engines.hears("yes"); await voice.on_utterance(utt()); await bridge.got("yes")


async def test_noise_in_the_follow_up_window_goes_back_to_idle(voice, jarvis, engines, speaker, bridge):
    await asking(jarvis, speaker, bridge); speaker.on_done()
    await feed(voice, SPEECH, 1); assert jarvis.state is State.LISTENING
    engines.hears(""); await voice.on_utterance(utt())
    assert jarvis.state is State.IDLE and bridge.sent == ["remind me"]


async def test_a_cough_after_the_name_keeps_listening(voice, jarvis, engines, bridge, clock):
    engines.hears("Jarvis.", "", "open Mail")
    await voice.on_utterance(utt()); await feed(voice, SPEECH, 1)   # the cough starts speech
    await voice.on_utterance(utt()); assert jarvis.state is State.LISTENING
    await voice.on_utterance(utt()); await bridge.got("open Mail")


async def test_a_cough_after_the_name_still_gives_up_after_8_s(voice, jarvis, engines, clock):
    engines.hears("Jarvis.", "")
    await voice.on_utterance(utt()); await feed(voice, SPEECH, 1); await voice.on_utterance(utt())
    clock.advance(8.0); await jarvis.tick(); assert jarvis.state is State.IDLE


async def test_a_hold_that_transcribes_to_nothing_gives_up(voice, jarvis, engines, bridge):
    engines.hears("")
    voice.key("down"); await feed(voice, SPEECH, 10); await until(lambda: jarvis.state is State.LISTENING)
    voice.key("hold_end"); await until(lambda: engines.calls == 1); await asyncio.sleep(0.01)
    assert jarvis.state is State.IDLE and bridge.sent == []


@pytest.mark.parametrize("ack", ["Okay.", "Huh?", "Thanks!", "got it", "Cool"])
async def test_a_bare_ack_in_the_follow_up_window_ends_it_quietly(voice, jarvis, engines, speaker, bridge, ack):
    await asking(jarvis, speaker, bridge); speaker.on_done()
    await feed(voice, SPEECH, 1); assert jarvis.state is State.LISTENING
    engines.hears(ack); await voice.on_utterance(utt())
    assert jarvis.state is State.IDLE and bridge.sent == ["remind me"]
    engines.hears("okay so open Mail"); await voice.on_utterance(utt())   # longer than an ack: no name, IDLE → dropped
    engines.hears("Jarvis, okay"); await voice.on_utterance(utt())         # said with the name: a request
    await bridge.got("okay")


async def test_a_kept_start_is_dropped_when_listening_ends(voice, jarvis, engines, bridge, clock):
    engines.hears("Jarvis, write an email to"); await voice.on_utterance(utt(15.0, cut=True))
    assert jarvis.state is State.LISTENING and bridge.sent == []
    clock.advance(8.0); await jarvis.tick(); assert jarvis.state is State.IDLE
    await asyncio.sleep(0.01)
    engines.hears("Jarvis.", "open Mail"); await voice.on_utterance(utt()); await voice.on_utterance(utt())
    await bridge.got("open Mail"); assert bridge.sent == ["open Mail"]


async def test_thinking_hears_only_cancel(voice, jarvis, engines, bridge):
    t = asyncio.create_task(jarvis.submit("write a poem", "mac")); await bridge.got("write a poem")
    assert jarvis.state is State.THINKING
    engines.hears("Jarvis, open Mail"); await voice.on_utterance(utt()); await asyncio.sleep(0.01)
    assert bridge.sent == ["write a poem"] and not bridge.interrupted
    engines.hears("Jarvis, never mind"); await voice.on_utterance(utt()); await until(lambda: bridge.interrupted)
    bridge.emit(turn("", cancelled=True)); await t


async def test_a_cut_request_continues_into_the_next_utterance(voice, jarvis, engines, bridge):
    engines.hears("Jarvis, write an email to", "the accountant about Friday")
    await voice.on_utterance(utt(15.0, cut=True)); await voice.on_utterance(utt())
    await bridge.got("write an email to the accountant about Friday"); assert len(bridge.sent) == 1


async def test_a_cut_request_takes_one_more_piece_and_no_more(voice, jarvis, engines, bridge):
    engines.hears("Jarvis, write an email to", "the accountant about", "Friday and the invoices")
    for _ in range(3):  # continuous talk: every piece ends at the 15 s cap
        await voice.on_utterance(utt(15.0, cut=True))
    await bridge.got("write an email to the accountant about"); await asyncio.sleep(0.01)
    assert bridge.sent == ["write an email to the accountant about"]


async def test_frames_while_speaking_are_dropped_and_the_cutter_reset(voice, jarvis, engines, speaker, bridge):
    await feed(voice, SPEECH, 10)  # speech in progress when Jarvis starts talking
    await asking(jarvis, speaker, bridge)
    await feed(voice, SPEECH, 40)
    speaker.on_done(); assert jarvis.state is State.FOLLOW_UP
    await feed(voice, SILENCE, 40)
    assert engines.calls == 0 and jarvis.state is State.FOLLOW_UP


async def test_a_holding_line_is_not_heard(voice, jarvis, engines, speaker, bridge):
    t = asyncio.create_task(jarvis.submit("look up the weather", "mac")); await bridge.got("look up the weather")
    speaker.hinting = True; await feed(voice, SPEECH, 20); speaker.hinting = False   # the mic hears "On it."
    await feed(voice, SILENCE, 30)
    assert engines.calls == 0 and jarvis.state is State.THINKING
    bridge.emit(turn("Dry.")); await t


async def test_a_holding_line_held_before_the_key_engages_is_not_sent(voice, jarvis, engines, speaker, bridge):
    t = asyncio.create_task(jarvis.submit("look up the weather", "mac")); await bridge.got("look up the weather")
    speaker.hinting = True
    voice.key("down"); await feed(voice, SPEECH, 20)   # "On it.", through the held capture
    await until(lambda: jarvis.state is State.LISTENING); speaker.hinting = False   # the engage cut it
    await feed(voice, SILENCE, 5); voice.key("hold_end"); await asyncio.sleep(0.01)
    assert engines.calls == 0 and bridge.sent == ["look up the weather"]
    bridge.emit(turn("Dry.")); await t


async def test_muting_stops_the_mic_and_unmuting_starts_it(voice, jarvis, engines, mic):
    assert mic.running and jarvis.health()["mic"] == "on"
    engines.hears("Jarvis, stop listening"); await voice.on_utterance(utt())
    await until(lambda: not mic.running); assert jarvis.health()["mic"] == "muted"
    await jarvis.submit("start listening", "mac")
    await until(lambda: mic.running); assert jarvis.health()["mic"] == "on"


async def test_the_mic_dying_mid_request_ends_the_listen(voice, jarvis, engines, mic):
    engines.hears("Jarvis."); await voice.on_utterance(utt()); assert jarvis.state is State.LISTENING
    await feed(voice, SPEECH, 10)   # speech under way, so the 8 s give-up is off
    mic.on_word("off"); await asyncio.sleep(0.01)
    assert jarvis.state is State.IDLE and voice.seg.buf == [] and not voice.seg.speaking


async def test_engines_that_will_not_load_leave_typed_jarvis_working(jarvis, engines, mic):
    engines.load_says = "no models"
    v = Voice(jarvis, engines, mic, Segmenter(lambda f: 0.0), listen=(keys := FakeKeys()))
    await v.start()
    assert mic.starts == 0 and keys.on_kind is None and jarvis.health()["mic"] == "no models"
    assert (await jarvis.submit("what time is it", "mac")).say == say_time(NOW)
    await v.stop()


async def test_levels_are_published_while_the_mic_is_open(voice, jarvis, speaker):
    seen = collect(jarvis)
    await feed(voice, np.full(480, 3277, dtype=np.int16), 6)
    await feed(voice, np.full(480, -32768, dtype=np.int16), 3)
    assert [round(e["rms"], 3) for e in seen() if e["type"] == "level"] == [0.1, 0.1, 1.0]
    await speaking(jarvis, speaker); seen().clear()
    await feed(voice, SPEECH, 6)
    assert [e for e in seen() if e["type"] == "level"] == []


async def test_the_log_has_timings_and_never_text(voice, jarvis, engines, bridge, caplog):
    caplog.set_level(logging.INFO, logger="jarvisd")
    engines.hears("Jarvis, open the secret plans 7731"); await voice.on_utterance(utt(1.5))
    await bridge.got("open the secret plans 7731")
    assert "transcribe " in caplog.text and "for 1.5 s of speech" in caplog.text
    assert "7731" not in caplog.text and "secret" not in caplog.text


# ---- the talk key ------------------------------------------------------------------------------------------------

async def test_hold_sends_what_was_said_with_no_name_and_no_silence_wait(voice, jarvis, engines, bridge):
    engines.hears("open Mail")
    voice.key("down"); await feed(voice, SPEECH, 20); await until(lambda: jarvis.state is State.LISTENING)
    voice.key("hold_end"); await bridge.got("open Mail")


async def test_speech_under_way_when_the_key_goes_down_is_not_sent(voice, jarvis, engines, bridge):
    engines.hears("open Mail")
    await feed(voice, SPEECH, 100)  # 3 s of someone talking, no name
    voice.key("down"); await until(lambda: jarvis.state is State.LISTENING)
    await feed(voice, SPEECH, 10); voice.key("hold_end"); await bridge.got("open Mail")
    assert engines.lengths == [(10 + 10) * 480]  # the pre-roll and what was said with the key


async def test_a_press_let_go_inside_the_grace_does_nothing(voice, jarvis, engines, speaker):   # 0.3-0.8 s
    await speaking(jarvis, speaker); speaker.calls.clear(); seen = collect(jarvis)
    voice.key("down"); await feed(voice, SPEECH, 20); voice.key("hold_end")   # Jarvis's own voice, held
    await asyncio.sleep(config.KEY_GRACE_SECONDS + 0.1)
    assert ("stop",) not in speaker.calls and [e for e in seen() if e["type"] in ("state", "heard")] == []
    assert jarvis.state is State.SPEAKING and engines.calls == 0 and voice.seg.buf == [] and not voice.seg.held


async def test_jarvis_own_voice_held_before_the_key_engages_is_not_sent(voice, jarvis, engines, speaker):
    await speaking(jarvis, speaker)
    voice.key("down"); await feed(voice, SPEECH, 20); await until(lambda: jarvis.state is State.LISTENING)
    await feed(voice, SILENCE, 5); voice.key("hold_end"); await asyncio.sleep(0.01)
    assert engines.calls == 0 and jarvis.state is State.IDLE


async def test_tap_listens_and_a_pause_sends(voice, jarvis, engines, speaker, bridge):
    engines.hears("open Mail")
    voice.key("down"); voice.key("tap")
    assert jarvis.state is State.LISTENING and ("cue",) in speaker.calls
    await feed(voice, SPEECH, 10); await feed(voice, SILENCE, 30); await bridge.got("open Mail")


async def test_a_tap_then_a_pause_still_listens(voice, jarvis, engines, bridge):
    engines.hears("open Mail")
    voice.key("down"); await feed(voice, SILENCE, 3); voice.key("tap")
    await feed(voice, SILENCE, 50)  # 1.5 s before Febriel starts talking
    assert jarvis.state is State.LISTENING and engines.calls == 0 and bridge.sent == []
    await feed(voice, SPEECH, 10); await feed(voice, SILENCE, 30); await bridge.got("open Mail")


async def test_a_tap_with_nothing_said_gives_up_after_8_s(voice, jarvis, clock):
    voice.key("down"); await feed(voice, SILENCE, 3); voice.key("tap")
    await feed(voice, SILENCE, 30); assert jarvis.state is State.LISTENING
    clock.advance(8.0); await jarvis.tick(); assert jarvis.state is State.IDLE


async def test_a_long_hold_is_not_cut_by_the_listening_timeout(voice, jarvis, clock):
    voice.key("down"); await until(lambda: jarvis.state is State.LISTENING)
    await feed(voice, SPEECH, 10)
    clock.advance(9.0); await jarvis.tick(); assert jarvis.state is State.LISTENING


async def test_a_silent_hold_is_not_timed_out_while_the_key_is_down(voice, jarvis, speaker, clock):
    voice.key("down"); await until(lambda: jarvis.state is State.LISTENING); speaker.calls.clear()
    await feed(voice, SILENCE, 10)
    clock.advance(9.0); await jarvis.tick()
    assert jarvis.state is State.LISTENING and ("hold", False) not in speaker.calls   # nothing plays into it


async def test_typing_with_the_key_does_nothing(voice, jarvis, speaker):   # Review Focus 5
    await speaking(jarvis, speaker); speaker.calls.clear(); seen = collect(jarvis)
    voice.key("down"); await feed(voice, SPEECH, 3); voice.key("chord")
    await asyncio.sleep(config.KEY_GRACE_SECONDS + 0.1)  # past the grace
    assert ("stop",) not in speaker.calls and [e for e in seen() if e["type"] in ("state", "level")] == []
    assert jarvis.state is State.SPEAKING and voice.seg.buf == [] and not voice.seg.held


async def test_a_chord_as_slow_as_febriels_typing_does_nothing(voice, jarvis, speaker):
    await speaking(jarvis, speaker); speaker.calls.clear(); seen = collect(jarvis)
    voice.key("down"); await asyncio.sleep(0.6); voice.key("chord")  # his slowest of 25 é/ñ/⌥← measured (603 ms), 2026-11-18
    assert ("stop",) not in speaker.calls and [e for e in seen() if e["type"] == "state"] == []
    assert jarvis.state is State.SPEAKING


async def test_a_chord_after_the_grace_gives_up_quietly(voice, jarvis, bridge):
    voice.key("down"); await until(lambda: jarvis.state is State.LISTENING)
    await feed(voice, SPEECH, 3); voice.key("chord")
    assert jarvis.state is State.IDLE and voice.seg.buf == []
    await asyncio.sleep(0.01); assert bridge.sent == []


async def test_the_key_works_while_muted_and_the_mic_shuts_again(voice, jarvis, engines, speaker, bridge, mic):
    await jarvis.submit("stop listening", "mac"); await until(lambda: not mic.running)
    engines.hears("open Mail")
    voice.key("down"); assert mic.running
    await feed(voice, SPEECH, 20); await until(lambda: jarvis.state is State.LISTENING)
    voice.key("hold_end"); await bridge.got("open Mail")
    bridge.emit(turn("Opened.")); await until(lambda: ("say", "Opened.") in speaker.calls)
    speaker.on_start(); speaker.on_done(); assert jarvis.state is State.IDLE
    await until(lambda: not mic.running); assert jarvis.health()["mic"] == "muted"


async def test_a_tap_that_stopped_speech_still_hears_the_request(voice, jarvis, engines, speaker, bridge):
    await speaking(jarvis, speaker)
    voice.key("down"); voice.key("tap"); speaker.on_done()   # the stopped reply's done comes after the tap
    assert jarvis.state is State.LISTENING
    engines.hears("open Mail"); await voice.on_utterance(utt()); await bridge.got("open Mail")


async def test_the_key_stops_speech(voice, jarvis, speaker):
    await speaking(jarvis, speaker)
    voice.key("down"); await until(lambda: jarvis.state is State.LISTENING)
    assert ("stop",) in speaker.calls


async def test_holding_with_nothing_said_gives_up(voice, jarvis, engines, bridge):
    voice.key("down"); await feed(voice, SILENCE, 20); await until(lambda: jarvis.state is State.LISTENING)
    voice.key("hold_end"); await asyncio.sleep(0.01)
    assert jarvis.state is State.IDLE and engines.calls == 0 and bridge.sent == []


async def test_without_a_listener_the_footer_says_so(jarvis, engines, mic):
    v = Voice(jarvis, engines, mic, Segmenter(lambda f: 0.0), listen=lambda on_kind, on_face: None)
    await v.start(); await asyncio.sleep(0.01)
    assert jarvis.health()["mic"] == "on, no key"
    await v.stop()


async def test_a_key_gesture_hops_to_the_loop_and_stop_ends_the_listener(voice, jarvis, keys):
    await asyncio.to_thread(keys.on_kind, "down")  # the listener calls back on its own thread
    await until(lambda: voice.seg.held)
    await voice.stop(); assert keys.stopped


async def test_the_face_key_hops_to_the_loop_and_hides_the_face(voice, jarvis, keys):
    await asyncio.to_thread(keys.on_face)   # Ctrl-Option-J, on the listener's thread
    await until(lambda: jarvis.face_hidden)


async def test_the_key_holds_speech_from_the_moment_it_goes_down(voice, jarvis, speaker):
    voice.key("down"); assert ("hold", True) in speaker.calls
    speaker.calls.clear(); voice.key("chord"); assert speaker.calls[-1] == ("hold", False)


async def test_stop_closes_the_engines(voice, engines):
    await voice.stop(); assert engines.closed


async def test_start_makes_the_holding_lines_ahead(jarvis, engines, mic, speaker):
    v = Voice(jarvis, engines, mic, Segmenter(lambda f: 0.0), listen=lambda on_kind, on_face: None)
    await v.start(); await asyncio.sleep(0.01)
    assert ("warm", ("Looking that up.", "On it.", "One moment.")) in speaker.calls
    await v.stop()
