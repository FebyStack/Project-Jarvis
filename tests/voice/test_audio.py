import time
from types import SimpleNamespace

import numpy as np
import pytest

from jarvis.voice.audio import Mic, Player


def wait_for(pred, timeout=2.0):
    end = time.monotonic() + timeout
    while not pred():
        assert time.monotonic() < end, "condition not met in time"
        time.sleep(0.002)


class FakeInput:
    """open_stream for Mic: fails `fail` times, then hands back streams the test feeds by hand."""
    def __init__(self, fail=0):
        self.streams, self.fail = [], fail

    def __call__(self, on_frame):
        if self.fail:
            self.fail -= 1
            raise OSError("no input device")
        s = SimpleNamespace(feed=on_frame, closed=False)
        s.close = lambda: setattr(s, "closed", True)
        self.streams.append(s)
        return s


class FakeSleep:
    """Records each wait and passes a twentieth of it, so 2 s of quiet is 0.1 s of test."""
    def __init__(self):
        self.calls = []

    def __call__(self, seconds):
        self.calls.append(seconds)
        time.sleep(seconds / 20)


def loud():
    return np.full(480, 300, dtype=np.int16)


def zeros():
    return np.zeros(480, dtype=np.int16)


@pytest.fixture
def rig():
    fi, sl = FakeInput(), FakeSleep()
    mic = Mic(open_stream=fi, sleep=sl)
    frames, words = [], []
    mic.on_frame, mic.on_word = frames.append, words.append
    yield SimpleNamespace(mic=mic, fi=fi, sleep=sl, frames=frames, words=words)
    mic.stop()


def test_mic_delivers_frames_and_says_on(rig):
    rig.mic.start()
    wait_for(lambda: rig.fi.streams)
    rig.fi.streams[0].feed(loud())
    rig.fi.streams[0].feed(loud())
    assert len(rig.frames) == 2 and rig.frames[0].dtype == np.int16 and len(rig.frames[0]) == 480
    assert rig.words == ["on"]


def test_mic_reopens_after_an_error_with_a_growing_wait(rig):
    rig.fi.fail = 3
    rig.mic.start()
    wait_for(lambda: rig.fi.streams)
    assert rig.sleep.calls[:3] == [1, 2, 4] and rig.words == ["off"]
    rig.fi.streams[0].feed(loud())
    assert len(rig.frames) == 1 and rig.words == ["off", "on"]


def test_mic_reopens_when_frames_stop_coming(rig):
    rig.mic.start()
    wait_for(lambda: rig.fi.streams)
    rig.fi.streams[0].feed(loud())
    wait_for(lambda: len(rig.fi.streams) == 2)
    assert rig.fi.streams[0].closed and rig.words == ["on", "off"]
    assert sum(s for s in rig.sleep.calls if s < 1) >= 2  # it waited 2 s of quiet before giving up on the stream


def test_all_zero_audio_is_no_permission_then_on_when_it_returns(rig):
    rig.mic.start()
    wait_for(lambda: rig.fi.streams)
    s = rig.fi.streams[0]
    for _ in range(66):  # 1.98 s
        s.feed(zeros())
    assert rig.words == []
    s.feed(zeros())  # 2.01 s
    assert rig.words == ["no permission"]
    s.feed(loud())
    assert rig.words == ["no permission", "on"]


def test_mic_stop_ends_its_thread_and_says_off(rig):
    rig.mic.start()
    wait_for(lambda: rig.fi.streams)
    rig.fi.streams[0].feed(loud())
    thread = rig.mic._thread
    rig.mic.stop()
    assert not thread.is_alive() and rig.fi.streams[-1].closed and rig.words == ["on", "off"]


class FakeOutput:
    def __init__(self):
        self.streams = []

    def __call__(self, fill):
        s = SimpleNamespace(fill=fill, aborted=False, closed=False)
        s.abort = lambda: setattr(s, "aborted", True)
        s.close = lambda: setattr(s, "closed", True)
        self.streams.append(s)
        return s


def pull(stream, n):
    """One output callback of n samples: what went out, and whether the run is over."""
    out = np.full(n, 9.0, dtype=np.float32)
    over = stream.fill(out)
    return out, over


@pytest.fixture
def out():
    fo = FakeOutput()
    p = Player(open_stream=fo, reopen_delay=0.01)  # 240 samples at 24 kHz
    events = []
    p.on_start, p.on_done = lambda: events.append("start"), lambda: events.append("done")
    return SimpleNamespace(p=p, fo=fo, events=events)


def test_player_fires_start_once_per_run_and_done_after_the_delay(out):
    out.p.play(np.ones(100, dtype=np.float32))
    out.p.play(np.ones(100, dtype=np.float32))
    assert out.p.busy and len(out.fo.streams) == 1
    s = out.fo.streams[0]
    a, over = pull(s, 150)
    assert (a == 1).all() and out.events == ["start"] and not over
    a, over = pull(s, 150)
    assert (a[:50] == 1).all() and (a[50:] == 0).all() and out.events == ["start"]
    pull(s, 139)  # 239 samples since the last one
    assert out.events == ["start"] and out.p.busy
    _, over = pull(s, 1)
    assert out.events == ["start", "done"] and over and not out.p.busy


def test_player_stop_drops_what_is_queued_and_is_done_at_once(out):
    out.p.play(np.ones(1000, dtype=np.float32))
    out.p.play(np.ones(1000, dtype=np.float32))
    s = out.fo.streams[0]
    pull(s, 100)
    out.p.stop()
    assert out.events == ["start", "done"] and s.aborted and s.closed and not out.p.busy
    a, _ = pull(s, 100)  # a late callback finds nothing queued
    assert (a == 0).all() and out.events == ["start", "done"]


def test_player_starts_again_after_done(out):
    out.p.play(np.ones(10, dtype=np.float32))
    pull(out.fo.streams[0], 500)
    assert out.events == ["start", "done"]
    out.p.play(np.ones(10, dtype=np.float32))
    assert len(out.fo.streams) == 2 and out.fo.streams[0].closed
    pull(out.fo.streams[1], 5)
    assert out.events == ["start", "done", "start"]


def test_a_player_that_cannot_open_is_not_left_busy():
    def no_device(fill):
        raise OSError("no output device")
    p = Player(open_stream=no_device)
    with pytest.raises(OSError):
        p.play(np.ones(10, dtype=np.float32))
    assert not p.busy


def test_the_output_callback_never_stops_its_own_stream(monkeypatch):
    """Its own stop racing a stop from the loop (Escape) deadlocks CoreAudio: only the loop stops a stream."""
    import sounddevice as sd
    from jarvis.voice import audio
    made = []
    monkeypatch.setattr(sd, "OutputStream", lambda **kw: made.append(kw) or SimpleNamespace(start=lambda: None))
    audio._open_output(lambda out: True)  # the run is over
    made[0]["callback"](np.zeros((4, 1), dtype=np.float32), 4, None, None)  # raises nothing


def test_close_ends_a_finished_runs_stream_but_not_a_running_one(out):
    out.p.play(np.ones(10, dtype=np.float32))
    s = out.fo.streams[0]
    out.p.close()
    assert not s.closed and out.p.busy
    pull(s, 500)
    out.p.close()
    assert s.aborted and s.closed and out.events == ["start", "done"]


def test_a_run_whose_device_stopped_calling_back_is_stalled():
    fo, now = FakeOutput(), [0.0]
    p = Player(open_stream=fo, reopen_delay=0.01, clock=lambda: now[0])
    p.play(np.ones(10, dtype=np.float32))
    now[0] = 2.1; assert p.stalled()  # it never called back at all
    pull(fo.streams[0], 5); now[0] = 4.0; assert not p.stalled()  # 1.9 s since the last callback
    now[0] = 4.2; assert p.stalled()
    p.stop(); assert not p.stalled()


def test_stop_ends_the_run_even_if_the_stream_will_not_abort(out):
    out.p.play(np.ones(10, dtype=np.float32))

    def gone():
        raise OSError("device vanished")
    out.fo.streams[0].abort = gone
    out.p.stop()
    assert out.events == ["done"] and not out.p.busy


def test_streams_open_stop_and_close_under_one_lock():
    """PortAudio is not thread-safe: the mic thread and the loop must not open or stop streams at once."""
    from jarvis.voice import audio
    seen = []

    def note(what):
        lock = getattr(audio, "_portaudio", None)
        seen.append((what, bool(lock and lock.locked())))

    def open_in(on_frame):
        note("open in")
        return SimpleNamespace(close=lambda: note("close in"))

    def open_out(fill):
        note("open out")
        return SimpleNamespace(abort=lambda: note("abort out"), close=lambda: note("close out"))
    mic = Mic(open_stream=open_in, sleep=FakeSleep())
    mic.start(); wait_for(lambda: len(seen) >= 2); mic.stop()
    p = Player(open_stream=open_out); p.play(np.ones(10, dtype=np.float32)); p.stop()
    p.play(np.ones(10, dtype=np.float32)); p.busy = False; p.close()
    assert {w for w, _ in seen} == {"open in", "close in", "open out", "abort out", "close out"}
    assert all(locked for _, locked in seen), seen
