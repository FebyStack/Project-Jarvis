"""The talk key: a listen-only Quartz event tap that reads Right Option and nothing else. Any other key pressed, a
click or a scroll counts only as "another key"; which key it was, or what was clicked, is never read."""
import threading
import time
from typing import Callable

from jarvis import config
from jarvis.voice.gesture import Gesture, Kind

RIGHT_OPTION = 0x40  # device bit in the flags: set while Right Option is down (probe P6)


def allowed() -> bool:
    """Input Monitoring is granted to this process (checked only; never asks)."""
    import Quartz
    return bool(Quartz.CGPreflightListenEventAccess())


def listen(on_kind: Callable[[Kind], None], keycode: int = config.TALK_KEYCODE) -> Callable[[], None] | None:
    """Starts a listen-only tap on its own thread; `on_kind` is called on that thread. Returns a stop function,
    or None when the tap cannot be made (no permission)."""
    if not allowed():
        return None
    import Quartz as Q
    gesture, made, box = Gesture(), threading.Event(), {}
    others = (Q.kCGEventKeyDown, Q.kCGEventLeftMouseDown, Q.kCGEventRightMouseDown, Q.kCGEventOtherMouseDown,
              Q.kCGEventScrollWheel)

    def callback(proxy, etype, event, refcon):
        if etype in (Q.kCGEventTapDisabledByTimeout, Q.kCGEventTapDisabledByUserInput):
            Q.CGEventTapEnable(box["tap"], True)  # macOS switched it off for being slow, or for secure input
            if kind := gesture.lost():
                on_kind(kind)
            return event
        now = time.monotonic()
        if etype in others:
            kind = gesture.other_key(now)
        elif Q.CGEventGetIntegerValueField(event, Q.kCGKeyboardEventKeycode) != keycode:
            kind = None  # another modifier alone is not typing
        elif Q.CGEventGetFlags(event) & RIGHT_OPTION:
            kind = gesture.key_down(now)
        else:
            kind = gesture.key_up(now)
        if kind:
            on_kind(kind)
        return event

    def run():
        mask = sum(1 << t for t in (Q.kCGEventFlagsChanged, *others))
        tap = Q.CGEventTapCreate(Q.kCGSessionEventTap, Q.kCGHeadInsertEventTap, Q.kCGEventTapOptionListenOnly,
                                 mask, callback, None)
        box["tap"], box["loop"] = tap, Q.CFRunLoopGetCurrent()
        if tap is not None:
            Q.CFRunLoopAddSource(box["loop"], Q.CFMachPortCreateRunLoopSource(None, tap, 0), Q.kCFRunLoopCommonModes)
            Q.CGEventTapEnable(tap, True)
        made.set()
        if tap is not None:
            Q.CFRunLoopRun()

    thread = threading.Thread(target=run, name="keys", daemon=True)
    thread.start()
    made.wait(2.0)
    if box.get("tap") is None:
        return None

    def stop() -> None:
        Q.CGEventTapEnable(box["tap"], False)
        Q.CFMachPortInvalidate(box["tap"])
        Q.CFRunLoopStop(box["loop"])
        thread.join(timeout=2.0)
    return stop
