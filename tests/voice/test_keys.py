import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from jarvis.voice import keys


def test_no_permission_means_no_listener(monkeypatch):
    monkeypatch.setattr(keys, "allowed", lambda: False)
    assert keys.listen(lambda kind: None) is None


def test_importing_the_key_listener_and_the_loop_loads_no_quartz():
    code = ("import sys, jarvis.voice.keys, jarvis.voice.loop; "
            "print([m for m in ('Quartz', 'mlx', 'sounddevice', 'openwakeword') if m in sys.modules])")
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip() == "[]"


class FakeQuartz:
    """Stands in for Quartz: keeps the tap's mask and callback; never a real event tap. An event is a dict, so
    reading a field the listener must not read (a click's) raises."""
    kCGEventTapDisabledByTimeout, kCGEventTapDisabledByUserInput = 0xFFFFFFFE, 0xFFFFFFFF
    kCGEventLeftMouseDown, kCGEventRightMouseDown, kCGEventKeyDown = 1, 3, 10
    kCGEventFlagsChanged, kCGEventScrollWheel, kCGEventOtherMouseDown = 12, 22, 25
    kCGKeyboardEventKeycode = 9
    kCGSessionEventTap = kCGHeadInsertEventTap = kCGEventTapOptionListenOnly = kCFRunLoopCommonModes = 0

    def __init__(self):
        self.mask = self.callback = None
        self.stopped = threading.Event()

    def CGPreflightListenEventAccess(self): return True
    def CGEventTapCreate(self, where, place, option, mask, callback, refcon):
        self.mask, self.callback = mask, callback
        return "tap"
    def CFRunLoopGetCurrent(self): return "loop"
    def CFMachPortCreateRunLoopSource(self, alloc, tap, order): return "source"
    def CFRunLoopAddSource(self, loop, source, mode): pass
    def CGEventTapEnable(self, tap, on): pass
    def CFRunLoopRun(self): self.stopped.wait(2)
    def CFRunLoopStop(self, loop): self.stopped.set()
    def CFMachPortInvalidate(self, tap): pass
    def CGEventGetIntegerValueField(self, event, field): return event["keycode"]
    def CGEventGetFlags(self, event): return event["flags"]


@pytest.fixture
def tap(monkeypatch):
    q = FakeQuartz()
    monkeypatch.setitem(sys.modules, "Quartz", q)
    kinds = []
    stop = keys.listen(kinds.append)
    send = lambda etype, event=None: q.callback(None, etype, event, None)
    t = SimpleNamespace(q=q, kinds=kinds, send=send,
                        down=lambda: send(q.kCGEventFlagsChanged, {"keycode": 61, "flags": keys.RIGHT_OPTION}),
                        up=lambda: send(q.kCGEventFlagsChanged, {"keycode": 61, "flags": 0}))
    yield t
    stop()


@pytest.mark.parametrize("name", ["kCGEventLeftMouseDown", "kCGEventRightMouseDown", "kCGEventOtherMouseDown",
                                  "kCGEventScrollWheel"])
def test_a_click_or_a_scroll_with_the_key_down_is_a_chord(tap, name):
    etype = getattr(tap.q, name)
    assert tap.q.mask & (1 << etype)
    tap.down(); tap.send(etype, {}); tap.up()  # {}: what was clicked is never read
    assert tap.kinds == ["down", "chord"]


@pytest.mark.parametrize("name", ["kCGEventTapDisabledByTimeout", "kCGEventTapDisabledByUserInput"])
def test_a_press_under_way_when_macos_switches_the_tap_off_ends_as_a_chord(tap, name):
    tap.down(); tap.send(getattr(tap.q, name))   # the key up may be lost while the tap is off
    tap.down()                                    # and the key still works afterwards
    assert tap.kinds == ["down", "chord", "down"]


def test_the_tap_switched_off_with_the_key_up_says_nothing(tap):
    tap.send(tap.q.kCGEventTapDisabledByTimeout)
    assert tap.kinds == []
