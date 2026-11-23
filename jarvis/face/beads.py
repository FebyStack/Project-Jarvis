"""One bead (tether design §4): a small Liquid Glass panel with native labels and buttons, its mark, its countdown.

Every string is set with setStringValue_ or setTitle_, so a label shows characters and nothing else.
"""

import math
import weakref

import objc
from AppKit import (
    NSBackingStoreBuffered, NSBezelStyleCircular, NSBezelStylePush, NSButton, NSColor, NSControlSizeLarge,
    NSFloatingWindowLevel, NSFont, NSFontDescriptorSystemDesignRounded, NSFontWeightRegular, NSFontWeightSemibold,
    NSImage, NSImageSymbolConfiguration, NSImageView, NSLineBreakByTruncatingTail, NSMakeRect, NSPanel,
    NSTextAlignmentLeft, NSTextAlignmentRight, NSTextField, NSTrackingActiveAlways, NSTrackingArea,
    NSTrackingInVisibleRect, NSTrackingMouseEnteredAndExited, NSView, NSViewHeightSizable, NSViewMaxXMargin,
    NSViewMinXMargin, NSViewMinYMargin, NSViewWidthSizable, NSWindowAbove, NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary, NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowCollectionBehaviorStationary, NSWindowStyleMaskBorderless, NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import NSObject
from Quartz import (
    CABasicAnimation, CALayer, CAMediaTimingFunction, CAShapeLayer, CATransaction, CGPathAddLineToPoint,
    CGPathCloseSubpath, CGPathCreateMutable, CGPathMoveToPoint, kCAMediaTimingFunctionEaseInEaseOut,
    kCAMediaTimingFunctionLinear,
)

from jarvis import config
from jarvis.face import mark
from jarvis.face.model import LIVE

Glass = objc.lookUpClass("NSGlassEffectView")
STYLE = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
EVERYWHERE = (NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorStationary
              | NSWindowCollectionBehaviorFullScreenAuxiliary | NSWindowCollectionBehaviorIgnoresCycle)
WIDE, HEAD, SIG, INDENT, PAD, GAP, DOING = config.CARD_OPEN_WIDTH, config.CARD_LINE_HEIGHT, 24, 38, 12, 8, 160
BODY = WIDE - INDENT - PAD
ENDED = {"done": "checkmark.circle"}


class Panel(NSPanel):
    def canBecomeKeyWindow(self):
        return False

    def canBecomeMainWindow(self):
        return False


def panel(frame, mouse=True):
    p = Panel.alloc().initWithContentRect_styleMask_backing_defer_(frame, STYLE, NSBackingStoreBuffered, False)
    p.setReleasedWhenClosed_(False)
    p.setOpaque_(False)
    p.setBackgroundColor_(NSColor.clearColor())
    p.setHasShadow_(False)
    p.setLevel_(NSFloatingWindowLevel)
    p.setCollectionBehavior_(EVERYWHERE)
    p.setHidesOnDeactivate_(False)
    p.setIgnoresMouseEvents_(not mouse)
    return p


class Pane(NSView):
    def acceptsFirstMouse_(self, event):
        return True

    def mouseEntered_(self, event):
        self.zone = self.window().frame()   # where the pointer came in: opening may move the bead from under it
        self.press.act("in", self.identifier())

    def mouseExited_(self, event):
        self.press.act("left", self.identifier())   # the face asks the pointer which beads it has left (place.left)

    def viewDidChangeEffectiveAppearance(self):
        """Light, dark or Increase Contrast: the layers' resolved system red is resolved again (M16)."""
        if (bead := getattr(self, "bead", lambda: None)()) is not None:
            self.effectiveAppearance().performAsCurrentDrawingAppearance_(bead.recolor)


class Button(NSButton):
    def acceptsFirstMouse_(self, event):
        return True


class Press(NSObject):
    def press_(self, sender):
        what, agent = sender.identifier().split(":", 1)
        self.act(what, agent)


def _round():
    f = NSFont.monospacedDigitSystemFontOfSize_weight_(13, NSFontWeightRegular)
    return NSFont.fontWithDescriptor_size_(f.fontDescriptor().fontDescriptorWithDesign_(NSFontDescriptorSystemDesignRounded), 13)


def _label(weight=NSFontWeightRegular, second=False, lines=1, font=None):
    t = NSTextField.wrappingLabelWithString_("") if lines > 1 else NSTextField.labelWithString_("")
    t.setFont_(font or NSFont.systemFontOfSize_weight_(13, weight))
    t.setTextColor_(NSColor.secondaryLabelColor() if second else NSColor.labelColor())
    if lines > 1:
        t.setMaximumNumberOfLines_(lines)
        t.setPreferredMaxLayoutWidth_(BODY)
        t.cell().setTruncatesLastVisibleLine_(True)
    else:
        t.setLineBreakMode_(NSLineBreakByTruncatingTail)
    return t


def _wide(label):
    return label.fittingSize().width if label.stringValue() else 0


def _tall(label):
    return label.fittingSize().height if label.stringValue() else 0


def _loop(key, a, b, seconds):
    anim = CABasicAnimation.animationWithKeyPath_(key)
    anim.setFromValue_(a)
    anim.setToValue_(b)
    anim.setDuration_(seconds)
    anim.setRepeatCount_(math.inf)
    return anim


def _curve(points):
    p = CGPathCreateMutable()
    for i, (x, y) in enumerate(points):
        (CGPathAddLineToPoint if i else CGPathMoveToPoint)(p, None, SIG / 2 + 10.5 * x, SIG / 2 + 10.5 * y)
    CGPathCloseSubpath(p)
    return p


class _Piece:
    """A glass panel, a child of the circle's panel so it follows a drag."""

    def __init__(self, parent, radius):
        self.win = panel(NSMakeRect(0, 0, 1, 1))
        self.win.setHasShadow_(True)
        self.win.setAlphaValue_(0.0)
        self.glass = Glass.alloc().initWithFrame_(NSMakeRect(0, 0, 1, 1))
        self.glass.setCornerRadius_(radius)
        self.holder = Pane.alloc().initWithFrame_(NSMakeRect(0, 0, 1, 1))
        self.holder.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        self.holder.setWantsLayer_(True)
        self.glass.setContentView_(self.holder)
        self.win.setContentView_(self.glass)
        parent.addChildWindow_ordered_(self.win, NSWindowAbove)
        self.frame = self.anchor = None

    def hold(self, on):
        self.holder.layer().setSpeed_(0.0 if on else 1.0)

    def close(self):
        if self.win.parentWindow():
            self.win.parentWindow().removeChildWindow_(self.win)
        self.win.close()


class Chip(_Piece):
    def __init__(self, parent):
        super().__init__(parent, 13)
        self.text = _label(second=True)
        self.holder.addSubview_(self.text)

    def show(self, text):
        self.text.setStringValue_(text)
        w = _wide(self.text)
        self.text.setFrame_(NSMakeRect(10, 5, w, 16))
        self.size = (math.ceil(w) + 20, 26)


class Bead(_Piece):
    def __init__(self, parent, press, agent):
        super().__init__(parent, 18)
        red = NSColor.systemRedColor()
        self.holder.press, self.holder.zone = press, NSMakeRect(0, 0, 0, 0)
        self.holder.setIdentifier_(agent)
        self.holder.addTrackingArea_(NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            NSMakeRect(0, 0, 0, 0), NSTrackingMouseEnteredAndExited | NSTrackingActiveAlways | NSTrackingInVisibleRect,
            self.holder, None))
        self.holder.layer().setBorderColor_(red.CGColor())
        self.holder.layer().setCornerRadius_(18)
        self.face = Pane.alloc().initWithFrame_(NSMakeRect(0, 0, 1, 1))
        self.face.setWantsLayer_(True)
        self.holder.addSubview_(self.face)
        rounded = _round()
        self.name, self.role = _label(NSFontWeightSemibold), _label(second=True)
        self.line, self.time = _label(second=True), _label(second=True, font=rounded)
        self.title, self.doing = _label(lines=2), _label(second=True, lines=2)
        self.question, self.left = _label(NSFontWeightSemibold, lines=4), _label(second=True, font=rounded)
        self.labels = (self.name, self.role, self.line, self.time, self.title, self.doing, self.question, self.left)
        self.stop = Button.buttonWithImage_target_action_(
            NSImage.imageWithSystemSymbolName_accessibilityDescription_("stop.fill", None), press, "press:")
        self.stop.setBezelStyle_(NSBezelStyleCircular)
        self.stop.setIdentifier_(f"stop:{agent}")
        self.answers = []
        for title in ("Yes", "No", "Always"):
            b = Button.buttonWithTitle_target_action_(title, press, "press:")
            b.setBezelStyle_(NSBezelStylePush)
            b.setControlSize_(NSControlSizeLarge)
            b.setIdentifier_(f"{title.lower()}:{agent}")
            self.answers.append(b)
        self.answers[0].setBezelColor_(red)
        self.views = (*self.labels, self.stop, *self.answers)
        for v in self.views:
            self.face.addSubview_(v)
        self.bar = CALayer.layer()
        self.bar.setBackgroundColor_(red.CGColor())
        self.bar.setCornerRadius_(1)
        self.face.layer().addSublayer_(self.bar)
        self.sig = self.sig_key = self.bar_for = None
        self.strokes = []
        self.holder.bead = weakref.ref(self)   # last: an appearance change may recolour from now on

    def show(self, card, side, still):
        self.card = card
        ended, asking = card.state not in LIVE, bool(card.question)
        self._sig(card, ended, asking, still)
        self.name.setStringValue_(card.name)
        self.role.setStringValue_(" · ".join(p for p in (card.role, card.model) if p))
        self.line.setStringValue_(card.title if ended else card.doing)
        self.time.setStringValue_(card.state if ended else card.elapsed)
        self.title.setStringValue_(card.title)
        self.doing.setStringValue_(card.doing)
        self.question.setStringValue_(card.question or "")
        self.left.setStringValue_(card.left_text)
        self.stop.setAccessibilityLabel_(f"Stop {card.name}")
        for b in self.answers:
            b.setAccessibilityLabel_(f"{b.title()} to {card.name}")
        for t in self.labels:
            t.setAlignment_(NSTextAlignmentRight if side == "left" else NSTextAlignmentLeft)
        shown = [self.sig]

        def at(view, n, y, w, h):   # n: how far the view's nearer edge is from the circle's side of the bead
            view.setFrame_(NSMakeRect(W - n - w if side == "left" else n, y, w, h))
            shown.append(view)

        if not card.open:
            parts = [(self.name, _wide(self.name)), (self.line, min(_wide(self.line), DOING)), (self.time, _wide(self.time))]
            W, H = math.ceil(INDENT + 2 + sum(w + GAP for _, w in parts if w)), HEAD
            if W > WIDE:
                parts[1], W = (self.line, max(0, parts[1][1] - (W - WIDE))), WIDE
            n = INDENT
            for v, w in parts:
                if w:
                    at(v, n, 10, w, 16)
                    n += w + GAP
        else:
            W, th, dh, qh = WIDE, _tall(self.title), _tall(self.doing), _tall(self.question)
            H = HEAD + th + (2 if th and dh else 0) + dh + PAD + (8 + qh + 10 + 28 + 10 + 16 if asking else 0)
            top, far = H - HEAD, 10
            if card.stop:
                at(self.stop, W - far - 22, top + 7, 22, 22)
                far += 22 + GAP
            tw = _wide(self.time)
            at(self.time, W - far - tw, top + 10, tw, 16)
            room = W - far - tw - GAP - INDENT
            nw = min(_wide(self.name), room)
            unit = [(self.name, nw), (self.role, max(0, min(_wide(self.role), room - nw - GAP)))]
            n = INDENT
            for v, w in (reversed(unit) if side == "left" else unit):
                at(v, n, top + 10, w, 16)
                n += w + GAP
            y = top
            for v, h, gap in ((self.title, th, 0), (self.doing, dh, 2 if th else 0)):
                if h:
                    y -= gap + h
                    at(v, INDENT, y, BODY, h)
            if asking:
                y -= 8 + qh
                at(self.question, INDENT, y, BODY, qh)
                y -= 10 + 28
                n = INDENT
                for b in (reversed(self.answers) if side == "left" else self.answers):
                    bw = b.fittingSize().width
                    at(b, n, y, bw, 28)
                    n += bw + 6
                y -= 10 + 16
                lw = _wide(self.left)
                at(self.left, INDENT + BODY - lw, y, lw, 16)
                self._bar(card, side, W, y + 8, (BODY - lw - GAP) * (card.left or 0))
        if not asking:
            self.bar_for = None
        self.bar.setHidden_(not asking)
        self.sig.setFrame_(NSMakeRect(W - 6 - SIG if side == "left" else 6, H - HEAD + 6, SIG, SIG))
        for v in self.views:
            v.setHidden_(v not in shown)
        size = self.holder.frame().size
        self.face.setAutoresizingMask_((NSViewMinXMargin if side == "left" else NSViewMaxXMargin) | NSViewMinYMargin)
        self.face.setFrame_(NSMakeRect(size.width - W if side == "left" else 0, size.height - H, W, H))
        self.face.setAlphaValue_(0.62 if ended else 1.0)
        self.glass.setTintColor_(NSColor.systemRedColor().colorWithAlphaComponent_(0.2) if asking else None)
        self.holder.layer().setBorderWidth_(1.5 if asking else 0.0)
        self.size = (W, H)

    def recolor(self):
        red = NSColor.systemRedColor().CGColor()
        self.holder.layer().setBorderColor_(red)
        self.bar.setBackgroundColor_(red)
        for s in self.strokes:
            s.setStrokeColor_(red)

    def _bar(self, card, side, W, y, width):
        CATransaction.begin()
        CATransaction.setDisableActions_(self.bar_for != card.ask_id)
        CATransaction.setAnimationDuration_(1.0)
        CATransaction.setAnimationTimingFunction_(CAMediaTimingFunction.functionWithName_(kCAMediaTimingFunctionLinear))
        self.bar.setAnchorPoint_((1.0 if side == "left" else 0.0, 0.5))
        self.bar.setPosition_((W - INDENT if side == "left" else INDENT, y))
        self.bar.setBounds_(((0, 0), (width, 2)))
        CATransaction.commit()
        self.bar_for = card.ask_id

    def _sig(self, card, ended, asking, still):
        key = (card.name, card.state if ended else asking, still)
        if key == self.sig_key:
            return
        if self.sig is not None:
            self.sig.removeFromSuperview()
        self.sig_key, self.strokes = key, []
        if ended:
            img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(ENDED.get(card.state, "stop.circle"), card.state)
            v = NSImageView.imageViewWithImage_(img.imageWithSymbolConfiguration_(
                NSImageSymbolConfiguration.configurationWithPointSize_weight_(20, NSFontWeightRegular)))
            v.setContentTintColor_(NSColor.secondaryLabelColor())
        else:
            v = Pane.alloc().initWithFrame_(NSMakeRect(0, 0, SIG, SIG))
            v.setWantsLayer_(True)
            box = CALayer.layer()
            box.setFrame_(((0, 0), (SIG, SIG)))
            v.layer().addSublayer_(box)
            m = mark.mark(card.name)
            for i in range(3):
                s = CAShapeLayer.layer()
                s.setFrame_(((0, 0), (SIG, SIG)))
                s.setPath_(_curve(mark.curve(m, i)))
                s.setFillColor_(None)
                s.setStrokeColor_(NSColor.systemRedColor().CGColor())
                s.setLineWidth_(1.0)
                self.strokes.append(s)
                if not still:
                    s.addAnimation_forKey_(_loop("transform.rotation.z", 0.0, m.way * math.tau, (18 if asking else 6) + 3 * i), "turn")
                box.addSublayer_(s)
            if asking and not still:
                breathe = _loop("transform.scale", 1.0, 1.12, 1.2)
                breathe.setAutoreverses_(True)
                breathe.setTimingFunction_(CAMediaTimingFunction.functionWithName_(kCAMediaTimingFunctionEaseInEaseOut))
                box.addAnimation_forKey_(breathe, "breathe")
        self.face.addSubview_(v)
        self.sig = v
