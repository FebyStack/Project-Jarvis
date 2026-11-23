"""Plan 4 Task 1 throwaway face: P1 (budget), P2 (clicks, hover, focus), P3 (glass), P7 (payloads), P8 (motion).

Run: uv run python spikes/10-face/probe.py <command-file>
Drive it by writing one command per line into <command-file> (it is read and emptied every 0.2 s):
  mode idle|listen|work|talk   beads 0..5   fps N   anim   open N   ask on|off   fallback on|off
  move X Y   p7   quit
Everything it sees (clicks, hover, which app is in front) is printed, one line each.
"""

import json
import math
import random
import sys
import time
from pathlib import Path

import objc
from AppKit import (
    NSApp, NSApplication, NSApplicationActivationPolicyAccessory, NSBackingStoreBuffered, NSButton,
    NSColor, NSFont, NSFontWeightRegular, NSFontWeightSemibold, NSPanel, NSScreen, NSTextField, NSTrackingArea,
    NSView, NSVisualEffectView, NSWindowAbove, NSWindowBelow, NSWorkspace, NSAnimationContext,
)
import os
from Foundation import NSObject, NSProcessInfo, NSTimer, NSURL, NSMakeRect
from Quartz import (
    CABasicAnimation, CAKeyframeAnimation, CALayer, CAMediaTimingFunction, CAShapeLayer, CATransaction,
    CGPathAddLineToPoint, CGPathAddQuadCurveToPoint, CGPathCloseSubpath, CGPathCreateMutable, CGPathMoveToPoint,
)
from WebKit import WKContentWorld, WKUserContentController, WKWebView, WKWebViewConfiguration

Glass = objc.lookUpClass("NSGlassEffectView")
HERE = Path(__file__).resolve().parent
CMD = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "cmd.txt"
SIZE, GAP, MOVE = 160.0, 10.0, 0.45
BORDERLESS, NONACTIVATING = 0, 1 << 7
BEHAVIOUR = (1 << 0) | (1 << 4) | (1 << 8) | (1 << 6)   # all Spaces, stationary, full-screen auxiliary, ignores cycle
FLOATING = 3
NAMES = ["Nova", "Orin", "Vesper", "Kite", "Lumen"]
DOING = ["Running the test suite", "Reading the export code", "Searching the web", "Writing the summary", "Checking prices"]
RED = NSColor.colorWithSRGBRed_green_blue_alpha_(1.0, 59 / 255, 48 / 255, 1.0)


def log(*a):
    front = NSWorkspace.sharedWorkspace().frontmostApplication()
    print(f"{time.strftime('%H:%M:%S')}", *a, f"| front={front.localizedName() if front else '?'} active={bool(NSApp.isActive())}",
          flush=True)


class Panel(NSPanel):
    def canBecomeKeyWindow(self):
        return False

    def canBecomeMainWindow(self):
        return False


def panel(frame, mouse=True):
    p = Panel.alloc().initWithContentRect_styleMask_backing_defer_(frame, BORDERLESS | NONACTIVATING, NSBackingStoreBuffered, False)
    p.setOpaque_(False)
    p.setBackgroundColor_(NSColor.clearColor())
    p.setLevel_(FLOATING)
    p.setCollectionBehavior_(BEHAVIOUR)
    p.setHidesOnDeactivate_(False)
    p.setIgnoresMouseEvents_(not mouse)
    p.setHasShadow_(False)
    return p


class FirstButton(NSButton):
    def acceptsFirstMouse_(self, e):
        return True


class HoverView(NSView):
    def acceptsFirstMouse_(self, e):
        return True

    def mouseEntered_(self, e):
        log("hover on", self.who)

    def mouseExited_(self, e):
        log("hover off", self.who)


class Target(NSObject):
    def clicked_(self, sender):
        log("click", sender.title() or "Stop", sender.identifier())

    def tick_(self, timer):
        app.tick()

    def poll_(self, timer):
        app.poll()


class Handler(NSObject, protocols=[objc.protocolNamed("WKScriptMessageHandler")]):
    def userContentController_didReceiveScriptMessage_(self, ucc, msg):
        app.message(msg.body())


def path_rose(petals, depth, off, r):
    p = CGPathCreateMutable()
    for i in range(73):
        th = i / 72 * 2 * math.pi
        rr = r * ((1 - depth) + depth * math.cos(petals * th + off))
        x, y = 12 + rr * math.cos(th), 12 + rr * math.sin(th)
        (CGPathMoveToPoint if i == 0 else CGPathAddLineToPoint)(p, None, x, y)
    CGPathCloseSubpath(p)
    return p


def mark_view(seed, asking):
    v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 24, 24))
    v.setWantsLayer_(True)
    rnd = random.Random(seed)
    for layer in range(3):
        s = CAShapeLayer.layer()
        s.setFrame_(((0, 0), (24, 24)))
        s.setPath_(path_rose(rnd.randint(3, 7), rnd.uniform(0.3, 0.5), rnd.uniform(0, 6.28), 10.5))
        s.setFillColor_(None)
        s.setStrokeColor_(NSColor.systemRedColor().CGColor())
        s.setLineWidth_(1.0)
        s.setOpacity_(0.85)
        a = CABasicAnimation.animationWithKeyPath_("transform.rotation.z")
        a.setFromValue_(0.0)
        a.setToValue_(2 * math.pi * (1 if layer % 2 else -1))
        a.setDuration_((14 if asking else 5) + layer * 2.3)
        a.setRepeatCount_(1e9)
        s.addAnimation_forKey_(a, "turn")
        v.layer().addSublayer_(s)
    return v


def label(text, size=13, weight=NSFontWeightRegular, secondary=False, rounded=False):
    t = NSTextField.labelWithString_(text)
    f = NSFont.monospacedDigitSystemFontOfSize_weight_(size, weight) if rounded else NSFont.systemFontOfSize_weight_(size, weight)
    if rounded:
        d = f.fontDescriptor().fontDescriptorWithDesign_("NSCTFontUIFontDesignRounded")
        f = NSFont.fontWithDescriptor_size_(d, size) if d else f
    t.setFont_(f)
    t.setTextColor_(NSColor.secondaryLabelColor() if secondary else NSColor.labelColor())
    t.setLineBreakMode_(4)   # truncate tail
    t.setAlignment_(2)       # right: the circle is on the right
    return t


def button(title, ident, red=False, h=28):
    b = FirstButton.alloc().initWithFrame_(NSMakeRect(0, 0, 64, h))
    b.setTitle_(title)
    b.setIdentifier_(ident)
    b.setBezelStyle_(1)
    b.setControlSize_(1 if h < 28 else 0)
    if red:
        b.setBezelColor_(NSColor.systemRedColor())
        b.setKeyEquivalent_("")
    b.setTarget_(app.target)
    b.setAction_("clicked:")
    return b


class Bead:
    def __init__(self, i, open_, asking, fallback):
        self.i, self.open, self.asking, self.name = i, open_, asking, NAMES[i]
        self.w, self.h = (300.0, 150.0 if asking else 84.0) if open_ else (214.0, 36.0)
        self.win = panel(NSMakeRect(0, 0, self.w, self.h))
        self.win.setHasShadow_(True)
        if fallback:
            g = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, self.w, self.h))
            g.setMaterial_(13)  # hudWindow
            g.setState_(1)      # active
            g.setBlendingMode_(0)
            g.setWantsLayer_(True)
            g.layer().setCornerRadius_(18)
            g.layer().setMasksToBounds_(True)
            content = g
        else:
            g = Glass.alloc().initWithFrame_(NSMakeRect(0, 0, self.w, self.h))
            g.setCornerRadius_(18)
            if asking:
                g.setTintColor_(NSColor.systemRedColor().colorWithAlphaComponent_(0.2))
            content = HoverView.alloc().initWithFrame_(NSMakeRect(0, 0, self.w, self.h))
            g.setContentView_(content)
        hover = content if isinstance(content, HoverView) else HoverView.alloc().initWithFrame_(NSMakeRect(0, 0, self.w, self.h))
        if hover is not content:
            content.addSubview_(hover)
        hover.who = self.name
        hover.addTrackingArea_(NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            NSMakeRect(0, 0, self.w, self.h), 0x01 | 0x80 | 0x200, hover, None))   # entered/exited, active always, in visible rect
        if asking and not fallback:
            g.setWantsLayer_(True)
        self.build(hover)
        self.win.setContentView_(g)
        if asking:
            g.setWantsLayer_(True)
            g.layer().setBorderColor_(NSColor.systemRedColor().CGColor())
            g.layer().setBorderWidth_(1.5)
            g.layer().setCornerRadius_(18)

    def build(self, v):
        w, h = self.w, self.h
        m = mark_view(self.name, self.asking)
        m.setFrameOrigin_((w - 6 - 24 - 6, h - 30))
        v.addSubview_(m)
        self.time = label("00:04", rounded=True, secondary=True)
        self.time.setAlignment_(0)
        self.time.setFrame_(NSMakeRect(12 if not self.open else 40, h - 28, 50, 18))
        v.addSubview_(self.time)
        top = label(self.name if self.open else f"{self.name}  {DOING[self.i]}", weight=NSFontWeightSemibold)
        top.setFrame_(NSMakeRect(62 if not self.open else 92, h - 28, w - 62 - 42 - (30 if self.open else 0), 18))
        v.addSubview_(top)
        if not self.open:
            return
        stop = button("", f"stop:{self.name}", h=22)
        stop.setImage_(objc.lookUpClass("NSImage").imageWithSystemSymbolName_accessibilityDescription_("stop.fill", f"Stop {self.name}"))
        stop.setBezelStyle_(15)   # circular
        stop.setFrame_(NSMakeRect(10, h - 30, 24, 22))
        v.addSubview_(stop)
        role = label("coder · opus", secondary=True)
        role.setFrame_(NSMakeRect(12, h - 50, w - 50, 18))
        v.addSubview_(role)
        doing = label(f"Fix export bug — {DOING[self.i]}", secondary=True)
        doing.setFrame_(NSMakeRect(12, h - 70, w - 50, 18))
        v.addSubview_(doing)
        if not self.asking:
            return
        q = label('Run `git push origin main`? <img src=x onerror=alert(1)> ");alert(1)//', weight=NSFontWeightSemibold)
        q.setMaximumNumberOfLines_(2)
        q.setLineBreakMode_(0)
        q.setFrame_(NSMakeRect(12, h - 108, w - 50, 36))
        v.addSubview_(q)
        x = w - 12 - 24 - 6
        for t, red in (("Yes", True), ("No", False), ("Always", False)):
            b = button(t, f"{t}:{self.name}", red)
            b.sizeToFit()
            bw = b.frame().size.width
            x -= bw
            b.setFrameOrigin_((x, 12))
            x -= 6
            v.addSubview_(b)
        self.cd = label("No in 42 s", rounded=True, secondary=True)
        self.cd.setAlignment_(0)
        self.cd.setFrame_(NSMakeRect(12, 16, 90, 18))
        v.addSubview_(self.cd)


class Probe:
    def __init__(self):
        self.target = Target.alloc().init()
        self.handler = Handler.alloc().init()
        self.beads, self.order, self.n, self.fallback, self.ask, self.t0 = [], [], 0, False, True, time.time()
        vis = NSScreen.mainScreen().visibleFrame()
        self.cx = vis.origin.x + vis.size.width - 40 - SIZE / 2
        self.cy = vis.origin.y + 40 + SIZE / 2
        self.circle = panel(NSMakeRect(self.cx - SIZE / 2, self.cy - SIZE / 2, SIZE, SIZE))
        cfg = WKWebViewConfiguration.alloc().init()
        ucc = WKUserContentController.alloc().init()
        ucc.addScriptMessageHandler_name_(self.handler, "face")
        cfg.setUserContentController_(ucc)
        self.web = WKWebView.alloc().initWithFrame_configuration_(NSMakeRect(0, 0, SIZE, SIZE), cfg)
        self.web.setValue_forKey_(False, "drawsBackground")
        page = Path(os.environ.get("PROBE_PAGE", HERE / "page"))   # PROBE_PAGE=jarvis/face/page shows the shipped page
        self.web.loadFileURL_allowingReadAccessToURL_(NSURL.fileURLWithPath_(str(page / "circle.html")),
                                                      NSURL.fileURLWithPath_isDirectory_(str(page), True))
        self.circle.setContentView_(self.web)
        self.threads = panel(NSMakeRect(0, 0, 10, 10), mouse=False)
        tv = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
        tv.setWantsLayer_(True)
        self.threads.setContentView_(tv)
        self.circle.orderFrontRegardless()
        self.circle.addChildWindow_ordered_(self.threads, NSWindowBelow)
        self.lines = []
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(1.0, self.target, "tick:", None, True)
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(0.2, self.target, "poll:", None, True)
        log("ready", f"circle at {self.cx:.0f},{self.cy:.0f}")

    # ---- layout: a rough plume, circle bottom-right, beads to its left going up
    def frames(self):
        out, y = [], self.cy - 22
        for k, b in enumerate(self.order):
            if y < self.cy + 88:
                right = self.cx - 88 - 6
            else:
                right = self.cx - 28 + 46 * (k - 1)
            out.append(NSMakeRect(right - b.w, y, b.w, b.h))
            y += b.h + GAP
        return out

    def anchor(self, f):
        return (f.origin.x + f.size.width - 18, f.origin.y + f.size.height - 18)

    def thread_path(self, a, sway=0.0):
        f = self.field
        ax, ay = a[0] - f.origin.x, a[1] - f.origin.y
        cx, cy = self.cx - f.origin.x, self.cy - f.origin.y
        d = math.hypot(cx - ax, cy - ay) or 1
        ex, ey = cx - (cx - ax) / d * 68, cy - (cy - ay) / d * 68
        sx, sy = ax + (cx - ax) / d * 13, ay + (cy - ay) / d * 13
        mx, my = (sx + ex) / 2 + sway, (sy + ey) / 2 - 18 + sway
        p = CGPathCreateMutable()
        CGPathMoveToPoint(p, None, sx, sy)
        CGPathAddQuadCurveToPoint(p, None, mx, my, ex, ey)
        return p

    def rebuild(self):
        for b in self.beads:
            self.circle.removeChildWindow_(b.win)
            b.win.orderOut_(None)
        self.beads = [Bead(i, i == 0 or i == self.open_i, i == 0 and self.ask, self.fallback) for i in range(self.n)]
        self.order = list(self.beads)
        self.lay(animate=False)

    open_i = -1

    def set_field(self, frames):
        xs = [f.origin.x for f in frames] + [self.cx - SIZE / 2]
        ys = [f.origin.y for f in frames] + [self.cy - SIZE / 2]
        xe = [f.origin.x + f.size.width for f in frames] + [self.cx + SIZE / 2]
        ye = [f.origin.y + f.size.height for f in frames] + [self.cy + SIZE / 2]
        self.field = NSMakeRect(min(xs) - 24, min(ys) - 24, max(xe) - min(xs) + 48, max(ye) - min(ys) + 48)
        self.threads.setFrame_display_(self.field, False)
        self.threads.contentView().setFrame_(NSMakeRect(0, 0, self.field.size.width, self.field.size.height))

    def lay(self, animate):
        frames = self.frames()
        old = [self.thread_path(self.anchor(b.win.frame())) if animate else None for b in self.order]
        if not animate:
            self.set_field(frames)
        else:   # field must cover both old and new places while moving
            self.set_field(frames + [b.win.frame() for b in self.order])
            old = [self.thread_path(self.anchor(b.win.frame())) for b in self.order]
        root = self.threads.contentView().layer()
        for ln in self.lines:
            ln.removeFromSuperlayer()
        self.lines = []
        curve = CAMediaTimingFunction.functionWithControlPoints____(0.25, 1.25, 0.4, 1.0)
        for k, (b, f) in enumerate(zip(self.order, frames)):
            s = CAShapeLayer.layer()
            asking = b.asking
            new = self.thread_path(self.anchor(f))
            s.setPath_(new)
            s.setFillColor_(None)
            s.setStrokeColor_(RED.CGColor())
            s.setLineWidth_(1.8 if asking else 1.0)
            s.setOpacity_(1.0 if asking else 0.6)
            if animate:
                m = CABasicAnimation.animationWithKeyPath_("path")
                m.setFromValue_(old[k])
                m.setToValue_(new)
                m.setDuration_(MOVE)
                m.setTimingFunction_(curve)
                s.addAnimation_forKey_(m, "move")
            else:
                sw = CABasicAnimation.animationWithKeyPath_("path")
                sw.setFromValue_(self.thread_path(self.anchor(f), -5))
                sw.setToValue_(self.thread_path(self.anchor(f), 5))
                sw.setDuration_(3.2 + k * 0.4)
                sw.setAutoreverses_(True)
                sw.setRepeatCount_(1e9)
                sw.setTimingFunction_(CAMediaTimingFunction.functionWithName_("easeInEaseOut"))
                s.addAnimation_forKey_(sw, "sway")
            root.addSublayer_(s)
            self.lines.append(s)
            for d in range(2 if asking else 1):
                dot = CALayer.layer()
                dot.setBounds_(((0, 0), (4, 4)))
                dot.setCornerRadius_(2)
                dot.setBackgroundColor_(NSColor.colorWithSRGBRed_green_blue_alpha_(1, 0.55, 0.5, 1).CGColor())
                a = CAKeyframeAnimation.animationWithKeyPath_("position")
                a.setPath_(new)
                a.setDuration_(1.25 if asking else 2.5)
                a.setTimeOffset_(d * 0.6)
                a.setRepeatCount_(1e9)
                a.setCalculationMode_("paced")
                dot.addAnimation_forKey_(a, "travel")
                root.addSublayer_(dot)
                self.lines.append(dot)
        if not animate:
            for b, f in zip(self.order, frames):
                b.win.setFrame_display_(f, True)
                if b.win.parentWindow() is None:
                    self.circle.addChildWindow_ordered_(b.win, NSWindowAbove)
                b.win.orderFrontRegardless()
            return

        def changes(ctx):
            ctx.setDuration_(MOVE)
            ctx.setTimingFunction_(curve)
            ctx.setAllowsImplicitAnimation_(True)
            for b, f in zip(self.order, frames):
                b.win.animator().setFrame_display_(f, True)

        def done():
            log("anim done", f"{time.time() - self.anim_t:.3f}s")
            self.lay(animate=False)

        self.anim_t = time.time()
        NSAnimationContext.runAnimationGroup_completionHandler_(changes, done)

    # ---- commands
    def poll(self):
        try:
            text = CMD.read_text()
        except FileNotFoundError:
            return
        if not text.strip():
            return
        CMD.write_text("")
        for line in text.splitlines():
            if line.strip():
                self.command(line.split())

    def command(self, c):
        log("cmd", " ".join(c))
        if c[0] == "mode":
            self.js({"mode": c[1]})
        elif c[0] == "timer":
            self.js({"timer": c[1] == "on"})
        elif c[0] == "batch":
            self.js({"batch": c[1] == "on"})
        elif c[0] == "reload":
            self.web.reload()
        elif c[0] == "fps":
            self.js({"fps": int(c[1])})
        elif c[0] == "beads":
            self.n = int(c[1])
            self.rebuild()
        elif c[0] == "ask":
            self.ask = c[1] == "on"
            self.rebuild()
        elif c[0] == "fallback":
            self.fallback = c[1] == "on"
            self.rebuild()
        elif c[0] == "open":
            self.open_i = int(c[1])
            self.rebuild()
        elif c[0] == "anim":
            random.shuffle(self.order)
            self.lay(animate=True)
        elif c[0] == "move":
            self.cx, self.cy = float(c[1]), float(c[2])
            self.circle.setFrameOrigin_((self.cx - SIZE / 2, self.cy - SIZE / 2))
            self.lay(animate=False)
        elif c[0] == "pause":
            self.web.evaluateJavaScript_completionHandler_(f"window.face.pause({'true' if c[1] == 'on' else 'false'})", None)
            for b in self.beads:
                b.win.contentView().layer() and None
        elif c[0] == "p7":
            self.p7()
        elif c[0] == "quit":
            NSApp.terminate_(None)

    def js(self, payload):
        self.web.evaluateJavaScript_completionHandler_(f"window.face.show({json.dumps(payload, ensure_ascii=True)})", None)

    # ---- P7
    P7 = 'quote " single \' </script> line sep para  emoji 🦊 backslash \\ nul-free <img src=x onerror=1>'

    def p7(self):
        self.p7_sent = self.P7
        self.web.evaluateJavaScript_completionHandler_(f"window.face.echo({json.dumps(self.P7, ensure_ascii=True)})", None)
        self.web.callAsyncJavaScript_arguments_inFrame_inContentWorld_completionHandler_(
            "window.face.echo(p)", {"p": self.P7}, None, WKContentWorld.pageWorld(), None)
        self.web.evaluateJavaScript_completionHandler_(f"window.face.echo('{self.P7}')", None)   # naive, expected to break

    def message(self, body):
        if body.get("type") == "echo":
            log("p7 echo", "EXACT" if body["s"] == self.P7 else f"DIFFERENT {body['s']!r}", f"len={body['len']} want={len(self.P7.encode('utf-16-le')) // 2}")
        else:
            log("page", dict(body))

    def tick(self):
        s = int(time.time() - self.t0)
        if s % 30 == 0:
            log("alive", s)
        for b in self.beads:
            b.time.setStringValue_(f"{s // 60:02d}:{s % 60:02d}")
            if getattr(b, "cd", None):
                b.cd.setStringValue_(f"No in {max(0, 60 - s % 60)} s")


NSApplication.sharedApplication()
NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
if os.environ.get("PROBE_NAP") != "1":   # user-initiated, idle sleep allowed: no App Nap
    ACTIVITY = NSProcessInfo.processInfo().beginActivityWithOptions_reason_(0x00EFFFFF, "Jarvis face")
app = Probe()
NSApp.run()
