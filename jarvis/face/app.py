"""`jarvis face`: the circle's panel and web view, the beads and threads around it, and the asyncio side."""

import asyncio
import json
import os
import signal
import threading
import traceback
from pathlib import Path

import objc
from AppKit import (
    NSAnimationContext, NSApp, NSApplication, NSApplicationActivationPolicyAccessory,
    NSApplicationDidChangeScreenParametersNotification, NSDistributedNotificationCenter, NSMakeRect,
    NSEvent, NSNotificationCenter, NSScreen, NSSound, NSView, NSWindowDidMoveNotification, NSWorkspace,
    NSWorkspaceAccessibilityDisplayOptionsDidChangeNotification, NSWorkspaceScreensDidSleepNotification,
    NSWorkspaceScreensDidWakeNotification, NSWorkspaceSessionDidBecomeActiveNotification,
    NSWorkspaceSessionDidResignActiveNotification,
)
from Foundation import NSURL, NSObject, NSProcessInfo, NSTimer
from PyObjCTools import AppHelper
from Quartz import CGSessionCopyCurrentDictionary
from WebKit import WKContentWorld, WKWebView, WKWebViewConfiguration

from jarvis import config
from jarvis.face import place, tether
from jarvis.face.beads import Bead, Chip, Press, panel
from jarvis.face.controller import Controller
from jarvis.face.threads import CURVE, Threads
from jarvis.remote.client import Client
from jarvis.remote.token import load_token

PAGE = Path(__file__).with_name("page")
SIZE = config.CIRCLE_SIZE
NO_APP_NAP = 0x00EFFFFF   # user-initiated, idle system sleep allowed
LOCKED, UNLOCKED = "com.apple.screenIsLocked", "com.apple.screenIsUnlocked"
HOLDS = {NSWorkspaceScreensDidSleepNotification: ("sleep", True), NSWorkspaceScreensDidWakeNotification: ("sleep", False),
         NSWorkspaceSessionDidResignActiveNotification: ("session", True),
         NSWorkspaceSessionDidBecomeActiveNotification: ("session", False), LOCKED: ("lock", True), UNLOCKED: ("lock", False)}


class Grip(NSView):
    def acceptsFirstMouse_(self, event):
        return True

    def mouseDown_(self, event):
        self.window().performWindowDragWithEvent_(event)


class Hub(NSObject, protocols=[objc.protocolNamed("WKNavigationDelegate")]):
    def note_(self, note):
        self.app.note(note.name())

    def settle_(self, _):
        self.app.settled()

    def follow_(self, _):
        self.app.follow()

    def webView_didFinishNavigation_(self, web, navigation):
        self.app.loaded()

    def webViewWebContentProcessDidTerminate_(self, web):
        web.reload()


def _rect(r: tether.Rect):
    return NSMakeRect(r.x, r.y, r.w, r.h)


def _box(f) -> tether.Rect:
    return tether.Rect(f.origin.x, f.origin.y, f.size.width, f.size.height)


def _union(a: tether.Rect, b: tether.Rect) -> tether.Rect:
    x, y = min(a.x, b.x), min(a.y, b.y)
    return tether.Rect(x, y, max(a.x + a.w, b.x + b.w) - x, max(a.y + a.h, b.y + b.h) - y)


def _died(future) -> None:
    traceback.print_exception(future.exception())
    os._exit(1)   # launchd starts the face again


class App:
    def __init__(self):
        self.activity = NSProcessInfo.processInfo().beginActivityWithOptions_reason_(NO_APP_NAP, "Jarvis face")
        self.hub, self.press = Hub.alloc().init(), Press.alloc().init()
        self.hub.app, self.press.act = self, self.act
        self.sound = NSSound.alloc().initWithContentsOfFile_byReference_("/System/Library/Sounds/Glass.aiff", True)
        self.beads, self.chip, self.cards, self.more, self.payload, self.off, self.gen = {}, None, (), "", None, False, 0
        self.inside = set()   # the beads the pointer went into whose hover-off is not sent yet
        self.held = {"lock"} if (CGSessionCopyCurrentDictionary() or {}).get("CGSSessionScreenIsLocked") else set()
        self.circle = panel(NSMakeRect(0, 0, SIZE, SIZE))
        view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, SIZE, SIZE))
        self.web = WKWebView.alloc().initWithFrame_configuration_(view.bounds(), WKWebViewConfiguration.alloc().init())
        self.web.setValue_forKey_(False, "drawsBackground")
        self.web.setNavigationDelegate_(self.hub)
        self.web.loadFileURL_allowingReadAccessToURL_(NSURL.fileURLWithPath_(str(PAGE / "circle.html")),
                                                      NSURL.fileURLWithPath_isDirectory_(str(PAGE), True))
        view.addSubview_(self.web)
        view.addSubview_(Grip.alloc().initWithFrame_(view.bounds()))
        self.circle.setContentView_(view)
        s = self._screen()
        dx, dy = place.default(SIZE, s.w, s.h)
        x, y = place.load(config.HOME_DIR) or (s.x + dx, s.y + dy)
        self.circle.setFrameOrigin_((x, y))
        self.circle.setFrameOrigin_(self._keep(x, y))
        self.circle.orderFrontRegardless()
        self.pointer = None
        self.follow()
        self.threads = self._new(Threads(self.circle))
        own, ws = NSNotificationCenter.defaultCenter(), NSWorkspace.sharedWorkspace().notificationCenter()
        for centre, name, sender in (
                (own, NSApplicationDidChangeScreenParametersNotification, None), (own, NSWindowDidMoveNotification, self.circle),
                *((ws, n, None) for n in HOLDS if n.startswith("NSWorkspace")),
                (ws, NSWorkspaceAccessibilityDisplayOptionsDidChangeNotification, None),
                *((NSDistributedNotificationCenter.defaultCenter(), n, None) for n in (LOCKED, UNLOCKED))):
            centre.addObserver_selector_name_object_(self.hub, "note:", name, sender)
        main = lambda fn: lambda *a: AppHelper.callAfter(fn, *a)
        self.ctl = Controller(Client(load_token(config.HOME_DIR)), main(self.show_circle), main(self.show_stack),
                              main(self.play), config.HOME_DIR, show_hidden=main(self.show_hidden))
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        asyncio.run_coroutine_threadsafe(self._work(), self.loop).add_done_callback(_died)

    async def _work(self) -> None:
        async def tick():
            while True:
                await asyncio.sleep(1)
                self.ctl.tick()
        await asyncio.gather(self.ctl.run(), tick())

    def _screen(self) -> tether.Rect:
        return _box((self.circle.screen() or NSScreen.mainScreen()).visibleFrame())

    def _keep(self, x, y):
        s = self._screen()
        x, y = place.on_screen(x - s.x, y - s.y, SIZE, s.w, s.h)
        return x + s.x, y + s.y

    def _js(self, code, args):
        self.web.callAsyncJavaScript_arguments_inFrame_inContentWorld_completionHandler_(
            code, args, None, WKContentWorld.pageWorld(), None)

    def show_circle(self, payload: str) -> None:
        self.payload, self.off = payload, json.loads(payload)["mode"] == "off"
        self._js("window.face.show(JSON.parse(p))", {"p": payload})

    def loaded(self) -> None:
        if self.payload:
            self.show_circle(self.payload)
        if self.held:
            self._js("window.face.pause(p)", {"p": True})

    def show_hidden(self, hidden) -> None:
        """Ctrl-Option-J: the circle goes, its beads and threads with it (child panels follow their parent), and all is
        held as while the screen is locked; back, they come where they were and the plume is laid again."""
        if hidden:
            self.circle.orderOut_(None)
        else:
            self.circle.orderFrontRegardless()
        self.hold("hidden", hidden)
        if not hidden:
            self.lay()

    def play(self) -> None:
        self.sound.stop()
        self.sound.play()

    def act(self, what, agent) -> None:
        if what == "in":
            self.inside.add(agent)
            self.loop.call_soon_threadsafe(self.ctl.hover, agent, True)
        elif what == "left":
            self.left(NSEvent.mouseLocation())
        elif what == "stop":
            asyncio.run_coroutine_threadsafe(self.ctl.stop(agent), self.loop)
        elif agent in self.beads:
            asyncio.run_coroutine_threadsafe(self.ctl.answer(what, self.beads[agent].card.ask_id), self.loop)

    def left(self, p) -> None:
        """Hover-off for each bead the pointer has left (place.left): asked on AppKit's exit, and with the pointer for
        the exits AppKit never sends, so a bead that moved, resized, was covered or closed under it does not stay open."""
        rects = {a: (_box(b.win.frame()), _box(b.holder.zone)) for a, b in self.beads.items()}
        for agent in place.left(p.x, p.y, self.inside, rects):
            self.inside.discard(agent)
            self.loop.call_soon_threadsafe(self.ctl.hover, agent, False)

    def note(self, name) -> None:
        if name in HOLDS:
            self.hold(*HOLDS[name])
        elif name == NSWindowDidMoveNotification:
            NSObject.cancelPreviousPerformRequestsWithTarget_selector_object_(self.hub, "settle:", None)
            self.hub.performSelector_withObject_afterDelay_("settle:", None, 0.3)
        elif name == NSApplicationDidChangeScreenParametersNotification:
            self.settled()
        else:
            self.lay()

    def follow(self) -> None:
        """The square panel takes clicks only over the round circle: in its corners it ignores the mouse, so a click
        there reaches the app beneath (the final review's M11). Asked 60 times a second near the circle, 10 elsewhere,
        and not at all while the face is held. Each time, a bead the pointer has left gets its hover-off."""
        p, o = NSEvent.mouseLocation(), self.circle.frame().origin
        through = not place.takes_click(p.x, p.y, o.x, o.y, SIZE)
        if through != self.circle.ignoresMouseEvents():
            self.circle.setIgnoresMouseEvents_(through)
        if self.inside:
            self.left(p)
        self.pointer = None
        if not self.held:
            every = place.follow_every(p.x, p.y, o.x, o.y, SIZE)
            self.pointer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                every, self.hub, "follow:", None, False)
            self.pointer.setTolerance_(every / 10)

    def settled(self) -> None:
        o = self.circle.frame().origin
        x, y = self._keep(o.x, o.y)
        if (x, y) != (o.x, o.y):
            self.circle.setFrameOrigin_((x, y))
        asyncio.run_coroutine_threadsafe(self.ctl.on_message({"type": "moved", "x": x, "y": y}), self.loop)
        self.lay()

    def hold(self, reason, on) -> None:
        was = bool(self.held)
        self.held = self.held | {reason} if on else self.held - {reason}
        if bool(self.held) != was:
            self._js("window.face.pause(p)", {"p": bool(self.held)})
            if self.held and self.pointer:
                self.pointer.invalidate()
            elif not self.held:
                self.follow()
            for piece in (*self.beads.values(), *([self.chip] if self.chip else []), self.threads):
                piece.hold(bool(self.held))

    def show_stack(self, stack, more) -> None:
        self.cards, self.more = stack.cards, more
        self.lay()

    def _new(self, piece):
        piece.hold(bool(self.held))
        return piece

    def lay(self) -> None:
        ws = NSWorkspace.sharedWorkspace()
        still, opaque = ws.accessibilityDisplayShouldReduceMotion(), ws.accessibilityDisplayShouldIncreaseContrast()
        f, screen = self.circle.frame(), self._screen()
        centre = (f.origin.x + SIZE / 2, f.origin.y + SIZE / 2)
        side = tether.plume(centre, screen, ()).side
        gone = [self.beads.pop(a) for a in [a for a in self.beads if a not in {c.id for c in self.cards}]]
        pieces = []
        for card in self.cards:
            if card.id not in self.beads:
                self.beads[card.id] = self._new(Bead(self.circle, self.press, card.id))
            bead = self.beads[card.id]
            bead.show(card, side, still)
            pieces.append(bead)
        if self.more:
            self.chip = self.chip or self._new(Chip(self.circle))
            self.chip.show(self.more)
            pieces.append(self.chip)
        elif self.chip:
            gone.append(self.chip)
            self.chip = None
        p = tether.plume(centre, screen, [x.size for x in pieces])
        lines = []
        for bead, anchor in zip(pieces[:len(self.cards)], p.anchors):
            was = None
            if bead.frame is not None:
                o = bead.win.frame().origin
                was = (bead.anchor[0] + o.x - bead.frame.x, bead.anchor[1] + o.y - bead.frame.y)
            lines.append((bead.card.id, was, anchor, bead.card.state))
            bead.anchor = anchor
        moves = [(x, r) for x, r in zip(pieces, p.frames) if r != x.frame]
        if moves or gone:
            self.threads.place(_union(self.threads.rect(), p.field))
        self.threads.lay(centre, p.side, lines, still, opaque)
        if not (moves or gone):
            return
        self.gen += 1
        gen = self.gen
        home = lambda x: NSMakeRect(centre[0] - x.size[0] / 2, centre[1] - x.size[1] / 2, *x.size)
        for x, r in moves:
            if x.frame is None:
                x.win.setFrame_display_(home(x), False)
            x.frame = r

        def changes(ctx):
            ctx.setDuration_(0.2 if still else config.FACE_MOVE_SECONDS)
            ctx.setTimingFunction_(None if still else CURVE)
            for x, r in moves:
                if still:
                    x.win.setAlphaValue_(0.0)
                    x.win.setFrame_display_(_rect(r), True)
                else:
                    x.win.animator().setFrame_display_(_rect(r), True)
                x.win.animator().setAlphaValue_(1.0)
            for x in gone:
                if not still:
                    x.win.animator().setFrame_display_(home(x), True)
                x.win.animator().setAlphaValue_(0.0)

        def done():
            for x in gone:
                x.close()
            if gen == self.gen:
                self.threads.place(p.field)

        if self.held or self.off:   # nobody sees it and window animations wait for the screen; or jarvisd went away
            for x, r in moves:
                x.win.setFrame_display_(_rect(r), False)
                x.win.setAlphaValue_(1.0)
            done()
        else:
            NSAnimationContext.runAnimationGroup_completionHandler_(changes, done)


def run() -> None:
    NSApplication.sharedApplication()
    NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    app = App()   # noqa: F841 (held for the app's life)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    NSApp.run()
