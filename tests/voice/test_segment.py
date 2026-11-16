import numpy as np

from jarvis.voice.segment import Segmenter


def frame(v: float) -> np.ndarray:
    return np.full(480, int(v * 1000), dtype=np.int16)


def seg() -> Segmenter:
    return Segmenter(lambda f: float(f[0]) / 1000)


def run(s: Segmenter, *parts):
    """Feed (value, count) runs; return every non-None result."""
    return [u for v, n in parts for _ in range(n) if (u := s.feed(frame(v))) is not None]


def test_silence_yields_nothing_and_keeps_only_the_pre_roll():
    s = seg()
    assert run(s, (0.0, 200)) == []
    assert len(s.buf) <= 10


def test_speech_then_silence_is_one_utterance():
    s = seg()
    run(s, (0.9, 34), (0.0, 26))
    u = s.feed(frame(0.0))  # the 27th silent frame
    assert u is not None and not u.cut and len(u.pcm) == (34 + 3) * 480


def test_a_short_pause_does_not_cut():
    out = run(seg(), (0.9, 10), (0.0, 16), (0.9, 10), (0.0, 27))
    assert len(out) == 1 and len(out[0].pcm) == (10 + 16 + 10 + 3) * 480


def test_the_cap_cuts_and_says_so():
    s = seg()
    assert run(s, (0.9, 499)) == []
    u = s.feed(frame(0.9))
    assert u is not None and u.cut and len(u.pcm) == 500 * 480


def test_speaking_flag_follows_the_utterance():
    s = seg()
    assert not s.speaking
    run(s, (0.0, 5))
    assert not s.speaking
    s.feed(frame(0.9))
    assert s.speaking
    run(s, (0.0, 27))
    assert not s.speaking


def test_pre_roll_is_kept():
    s = seg()
    run(s, (0.007, 10), (0.9, 5))
    u = run(s, (0.0, 27))[0]
    assert (u.pcm[:480] == 7).all()


def test_hold_keeps_everything_whatever_the_detector_says():
    s = seg()
    s.hold()
    run(s, (0.0, 50))
    assert len(s.release().pcm) == 50 * 480


def test_release_with_nothing_held_is_none():
    s = seg()
    run(s, (0.9, 5))
    assert s.release() is None  # never held
    s = seg()
    s.hold()
    assert s.release() is None  # held, nothing heard


def test_hold_stops_at_the_held_cap():
    s = seg()
    s.hold()
    assert run(s, (0.0, 1999)) == []
    u = s.feed(frame(0.0))
    assert u is not None and u.cut and len(u.pcm) == 2000 * 480


def test_tap_turns_the_held_frames_into_speech_in_progress():
    s = seg()
    s.hold()
    run(s, (0.9, 5))
    s.tap()
    out = run(s, (0.0, 27))
    assert len(out) == 1 and not out[0].cut and len(out[0].pcm) == (5 + 3) * 480


def test_reset_forgets_speech_in_progress():
    s = seg()
    run(s, (0.9, 10))
    s.reset()
    assert run(s, (0.0, 27)) == [] and not s.speaking


def test_a_tap_with_no_speech_waits_for_the_detector():
    s = seg()
    s.hold()
    run(s, (0.0, 5))
    s.tap()
    assert run(s, (0.0, 27)) == [] and not s.speaking
    out = run(s, (0.9, 34), (0.0, 27))
    assert len(out) == 1 and not out[0].cut
