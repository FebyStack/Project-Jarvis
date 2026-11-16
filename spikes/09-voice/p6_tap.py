"""P6: listen-only event tap for flagsChanged and keyDown, 30 s. Logs key codes, flags and event types only; for keyDown just "keyDown"."""
import os, time
import Quartz as Q

LOG = os.path.expanduser("~/.jarvis/probe-p6.log")
OPTION, RIGHT_OPTION_BIT = 0x80000, 0x40
seen = {"rdown": 0, "rup": 0, "optkeydown": 0, "keydown": 0}
out = open(LOG, "w", buffering=1)


def log(s):
    out.write(f"{time.strftime('%H:%M:%S')} {s}\n")


def cb(proxy, etype, event, refcon):
    flags = Q.CGEventGetFlags(event)
    if etype == Q.kCGEventFlagsChanged:
        code = Q.CGEventGetIntegerValueField(event, Q.kCGKeyboardEventKeycode)
        log(f"flagsChanged keycode={code} flags={flags:#x}")
        if code == 61:
            seen["rdown" if flags & RIGHT_OPTION_BIT else "rup"] += 1
    elif etype == Q.kCGEventKeyDown:
        seen["keydown"] += 1
        seen["optkeydown"] += bool(flags & OPTION)
        log(f"keyDown option_held={bool(flags & OPTION)}")
    else:
        log(f"tap event type={etype}")  # e.g. disabled by timeout/user input
    return event


mask = (1 << Q.kCGEventFlagsChanged) | (1 << Q.kCGEventKeyDown)
tap = Q.CGEventTapCreate(Q.kCGSessionEventTap, Q.kCGHeadInsertEventTap, Q.kCGEventTapOptionListenOnly, mask, cb, None)
if tap is None:
    log("RESULT tap=None: no Input Monitoring permission for this program")
    raise SystemExit
src = Q.CFMachPortCreateRunLoopSource(None, tap, 0)
Q.CFRunLoopAddSource(Q.CFRunLoopGetCurrent(), src, Q.kCFRunLoopCommonModes)
Q.CGEventTapEnable(tap, True)
log("tap created, listening for 30 s: press Right Option down+up, then Option+E, then type a few keys")
Q.CFRunLoopRunInMode(Q.kCFRunLoopDefaultMode, 30, False)
ok = seen["rdown"] and seen["rup"] and seen["optkeydown"]
log(f"RESULT right_option down={seen['rdown']} up={seen['rup']} (bit {RIGHT_OPTION_BIT:#x}) option+key keyDown={seen['optkeydown']} "
    f"total_keyDown={seen['keydown']} {'PASS' if ok else 'FAIL: some events did not arrive'}")
