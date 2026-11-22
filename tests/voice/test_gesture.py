from jarvis.voice.gesture import Gesture


def test_tap():
    g = Gesture()
    assert [g.key_down(0.0), g.key_up(0.29)] == ["down", "tap"]


def test_hold():
    g = Gesture()
    assert [g.key_down(0.0), g.key_up(0.30)] == ["down", "hold_end"]


def test_chord():
    g = Gesture()
    assert [g.key_down(0.0), g.other_key(0.1), g.other_key(0.2), g.key_up(0.5)] == ["down", "chord", None, None]


def test_key_repeat():
    g = Gesture()
    assert [g.key_down(0.0), g.key_down(0.1)] == ["down", None]


def test_stray_events():
    g = Gesture()
    assert g.key_up(1.0) is None and g.other_key(1.0) is None


def test_usable_again_after_a_chord():
    g = Gesture()
    assert [g.key_down(0.0), g.other_key(0.1), g.key_up(0.2), g.key_down(1.0)] == ["down", "chord", None, "down"]


def test_a_lost_tap_ends_a_press_under_way_as_a_chord():
    g = Gesture()
    assert g.lost() is None                       # nothing under way
    assert [g.key_down(0.0), g.lost(), g.key_up(0.5), g.key_down(1.0)] == ["down", "chord", None, "down"]
    assert [g.other_key(1.1), g.lost()] == ["chord", None]   # already a chord: said once
