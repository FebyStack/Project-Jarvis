"""The threads (tether design §5): one click-through panel, one red silk line from each threaded bead's mark to the circle's rim."""

import math

from AppKit import NSColor, NSMakeRect, NSView, NSWindowBelow
from Quartz import (
    CABasicAnimation, CACurrentMediaTime, CAKeyframeAnimation, CALayer, CAMediaTimingFunction, CAShapeLayer,
    CATransaction, CGPathAddQuadCurveToPoint, CGPathCreateMutable, CGPathMoveToPoint, kCAAnimationPaced,
    kCALineCapRound, kCAMediaTimingFunctionEaseInEaseOut,
)

from jarvis import config
from jarvis.face import tether
from jarvis.face.beads import panel

CURVE = CAMediaTimingFunction.functionWithControlPoints____(0.25, 1.25, 0.4, 1.0)
LOOK = {"working": (1.0, 0.6, 1), "needs_you": (1.8, 1.0, 2), "done": (1.0, 0.2, 0)}   # width, opacity, dots; others are cut
SWAY = 4.0


def _path(a, c, b):
    p = CGPathCreateMutable()
    CGPathMoveToPoint(p, None, *a)
    CGPathAddQuadCurveToPoint(p, None, *c, *b)
    return p


def _line(t):
    return _path(t[2], t[1], t[0])   # from the rim to the bead, so a cut runs back into the circle


def _anim(key, a, b, seconds, timing=None):
    anim = CABasicAnimation.animationWithKeyPath_(key)
    anim.setFromValue_(a)
    anim.setToValue_(b)
    anim.setDuration_(seconds)
    anim.setTimingFunction_(timing)
    return anim


class Threads:
    def __init__(self, parent):
        self.win = panel(parent.frame(), mouse=False)
        view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 1, 1))
        view.setWantsLayer_(True)
        self.world = CALayer.layer()
        self.world.setAnchorPoint_((0.0, 0.0))
        view.layer().addSublayer_(self.world)
        self.win.setContentView_(view)
        parent.addChildWindow_ordered_(self.win, NSWindowBelow)
        rgb = (int(config.RED_ACTIVE[i:i + 2], 16) / 255 for i in (1, 3, 5))
        self.red = NSColor.colorWithSRGBRed_green_blue_alpha_(*rgb, 1.0).CGColor()
        self.lines = {}
        self.place(self.rect())

    def rect(self) -> tether.Rect:
        f = self.win.frame()
        return tether.Rect(f.origin.x, f.origin.y, f.size.width, f.size.height)

    def place(self, r: tether.Rect) -> None:
        """Covers `r`; the lines keep screen coordinates."""
        self.win.setFrame_display_(NSMakeRect(r.x, r.y, r.w, r.h), False)
        CATransaction.begin()
        CATransaction.setDisableActions_(True)
        self.world.setPosition_((-r.x, -r.y))
        CATransaction.commit()

    def hold(self, on):
        self.world.setSpeed_(0.0 if on else 1.0)

    def lay(self, centre, side, items, still, opaque):
        """items: (agent, where its anchor is now or None for a new bead, its anchor in the plume, state)."""
        seconds = config.FACE_MOVE_SECONDS
        for agent in [a for a in self.lines if a not in {i[0] for i in items}]:
            shape, dots, _ = self.lines.pop(agent)
            for layer in (shape, *dots):
                layer.removeFromSuperlayer()
        CATransaction.begin()
        CATransaction.setDisableActions_(True)
        for k, (agent, was, anchor, state) in enumerate(items):
            key = (anchor, centre, side, state, still, opaque)
            old = self.lines.get(agent)
            if old and old[2] == key:
                continue
            t = tether.thread(anchor, centre, 0.0, side)
            width, alpha, n = LOOK.get(state, LOOK["working"][:2] + (0,))
            cut, alpha = state not in LOOK, 1.0 if opaque else alpha
            if old:
                shape, dots, before = old
                for d in dots:
                    d.removeFromSuperlayer()
            else:
                shape, before = CAShapeLayer.layer(), None
                shape.setFillColor_(None)
                shape.setStrokeColor_(self.red)
                shape.setLineCap_(kCALineCapRound)
                self.world.addSublayer_(shape)
            moved = before is None or before[:3] != key[:3]
            if not still and moved:
                if before is None and not cut:
                    shape.addAnimation_forKey_(_anim("strokeEnd", 0.0, 1.0, seconds, CURVE), "move")
                elif before is not None and was is not None:
                    then = _line(tether.thread(was, centre, 0.0, before[2]))
                    shape.addAnimation_forKey_(_anim("path", then, _line(t), seconds, CURVE), "move")
            if before is not None and abs(shape.opacity() - alpha) > 0.01:
                shape.addAnimation_forKey_(_anim("opacity", shape.opacity(), alpha, seconds), "fade")
            shape.setPath_(_line(t))
            shape.setLineWidth_(width)
            shape.setOpacity_(alpha)
            shape.removeAnimationForKey_("sway")
            if cut:
                if before is not None and before[3] in LOOK:
                    shape.addAnimation_forKey_(_anim("strokeEnd", 1.0, 0.0, 0.25), "cut")
                shape.setStrokeEnd_(0.0)
            elif not still:
                period = 3.2 + 0.4 * k
                sway = _anim("path", _line(tether.thread(anchor, centre, -SWAY, side)),
                             _line(tether.thread(anchor, centre, SWAY, side)), period,
                             CAMediaTimingFunction.functionWithName_(kCAMediaTimingFunctionEaseInEaseOut))
                sway.setAutoreverses_(True)
                sway.setRepeatCount_(math.inf)
                sway.setTimeOffset_(period / 2)
                if moved:
                    sway.setBeginTime_(shape.convertTime_fromLayer_(CACurrentMediaTime(), None) + seconds)
                shape.addAnimation_forKey_(sway, "sway")
            dots = [] if still or cut else [self._dot(t, n, j) for j in range(n)]
            self.lines[agent] = (shape, dots, key)
        CATransaction.commit()

    def _dot(self, t, n, j):
        dot = CALayer.layer()
        dot.setBounds_(((0, 0), (4, 4)))
        dot.setCornerRadius_(2)
        dot.setBackgroundColor_(self.red)
        dot.setPosition_(t[0])
        period = 2.5 / n
        travel = CAKeyframeAnimation.animationWithKeyPath_("position")
        travel.setPath_(_path(*t))
        travel.setDuration_(period)
        travel.setRepeatCount_(math.inf)
        travel.setTimeOffset_(j * period / n)
        travel.setCalculationMode_(kCAAnimationPaced)
        dot.addAnimation_forKey_(travel, "travel")
        self.world.addSublayer_(dot)
        return dot
