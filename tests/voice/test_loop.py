import asyncio
import logging
from collections import deque

import numpy as np
import pytest

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
        self.texts, self.calls, self.load_says = deque(), 0, None

    def hears(self, *texts):
        self.texts.extend(texts)

    async def load(self):
        return self.load_says

    async def transcribe(self, pcm):
        self.calls += 1
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


@pytest.fixture
async def voice(jarvis, engines, mic):
    v = Voice(jarvis, engines, mic, Segmenter(lambda f: 1.0 if f.any() else 0.0))
    await v.start()
    yield v
    await v.stop()


async def speaking(jarvis, speaker):
    """Jarvis answers a typed "what time is it" and is speaking it."""
    await jarvis.submit("what time is it", "mac"); speaker.on_start()
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


async def test_a_request_in_one_breath(voice, jarvis, engines, speaker, vault):
    engines.hears("Jervis, what time is it?"); await voice.on_utterance(utt())
    await until(lambda: ("say", say_time(NOW)) in speaker.calls)
    assert "what time is it?" in day_log(vault)


async def test_the_name_alone_listens_and_the_next_utterance_is_the_request(voice, jarvis, engines, speaker, bridge):
    engines.hears("Jarvis.", "open Mail")
    await voice.on_utterance(utt()); assert jarvis.state is State.LISTENING and ("cue",) in speaker.calls
    await voice.on_utterance(utt()); await bridge.got("open Mail")


async def test_the_follow_up_window_needs_no_name(voice, jarvis, engines, speaker, bridge):
    await speaking(jarvis, speaker); speaker.on_done(); assert jarvis.state is State.FOLLOW_UP
    await feed(voice, SPEECH, 1); assert jarvis.state is State.LISTENING
    engines.hears("yes"); await voice.on_utterance(utt()); await bridge.got("yes")


async def test_noise_in_the_follow_up_window_goes_back_to_idle(voice, jarvis, engines, speaker, bridge):
    await speaking(jarvis, speaker); speaker.on_done()
    await feed(voice, SPEECH, 1); assert jarvis.state is State.LISTENING
    engines.hears(""); await voice.on_utterance(utt())
    assert jarvis.state is State.IDLE and bridge.sent == []


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


async def test_frames_while_speaking_are_dropped_and_the_cutter_reset(voice, jarvis, engines, speaker):
    await feed(voice, SPEECH, 10)  # speech in progress when Jarvis starts talking
    await speaking(jarvis, speaker)
    await feed(voice, SPEECH, 40)
    speaker.on_done(); assert jarvis.state is State.FOLLOW_UP
    await feed(voice, SILENCE, 40)
    assert engines.calls == 0 and jarvis.state is State.FOLLOW_UP


async def test_muting_stops_the_mic_and_unmuting_starts_it(voice, jarvis, engines, mic):
    assert mic.running and jarvis.health()["mic"] == "on"
    engines.hears("Jarvis, stop listening"); await voice.on_utterance(utt())
    await until(lambda: not mic.running); assert jarvis.health()["mic"] == "muted"
    await jarvis.submit("start listening", "mac")
    await until(lambda: mic.running); assert jarvis.health()["mic"] == "on"


async def test_engines_that_will_not_load_leave_typed_jarvis_working(jarvis, engines, mic):
    engines.load_says = "no models"
    v = Voice(jarvis, engines, mic, Segmenter(lambda f: 0.0))
    await v.start()
    assert mic.starts == 0 and jarvis.health()["mic"] == "no models"
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
