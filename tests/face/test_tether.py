import math

import pytest

from jarvis import config
from jarvis.face import place
from jarvis.face.tether import Rect, plume, thread

SCREEN = Rect(0, 0, 1440, 900)
CORNERS = [(1300, 120), (140, 120), (1300, 780), (140, 780), (720, 450),
           (1360, 80), (80, 80), (1360, 820), (80, 820), (1360, 450), (80, 450), (720, 80), (720, 820)]
STACKS = [[(190, 36)], [(300, 150), (190, 36), (210, 36)], [(190, 36)] * 5 + [(120, 24)], [(300, 150)] * 2 + [(190, 36)] * 3,
          [(300, 150)] * 5]


def overlap(a, b):
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


def inside(point, r):
    return r.x < point[0] < r.x + r.w and r.y < point[1] < r.y + r.h


def gap(centre, r):
    return math.hypot(max(r.x - centre[0], 0, centre[0] - r.x - r.w), max(r.y - centre[1], 0, centre[1] - r.y - r.h))


def test_the_first_bead_sits_beside_the_circle():
    cx, cy = 1300, 120
    f = plume((cx, cy), SCREEN, [(190, 36)]).frames[0]
    assert f.x + f.w <= cx - config.TETHER_CLEAR and f.y < cy < f.y + f.h
    assert f == Rect(1016, 98, 190, 36)


@pytest.mark.parametrize("centre", CORNERS)
@pytest.mark.parametrize("sizes", STACKS)
def test_beads_never_overlap_each_other_or_the_circle(centre, sizes):
    frames = plume(centre, SCREEN, sizes).frames
    assert [(f.w, f.h) for f in frames] == list(sizes)
    for i, a in enumerate(frames):
        assert gap(centre, a) > config.TETHER_RIM
        assert not any(overlap(a, b) for b in frames[i + 1:])


@pytest.mark.parametrize("centre", CORNERS)
@pytest.mark.parametrize("sizes", STACKS)
def test_every_bead_is_on_the_screen(centre, sizes):
    for f in plume(centre, SCREEN, sizes).frames:
        assert SCREEN.x <= f.x and f.x + f.w <= SCREEN.x + SCREEN.w
        assert SCREEN.y <= f.y and f.y + f.h <= SCREEN.y + SCREEN.h


@pytest.mark.parametrize("centre", CORNERS)
@pytest.mark.parametrize("sizes", STACKS)
def test_no_thread_crosses_another_bead(centre, sizes):
    p = plume(centre, SCREEN, sizes)
    for i, anchor in enumerate(p.anchors):
        for sway in (-6, 0, 6):
            (sx, sy), (mx, my), (ex, ey) = thread(anchor, centre, sway, p.side)
            for t in (k / 19 for k in range(20)):
                q = 1 - t
                point = (q * q * sx + 2 * q * t * mx + t * t * ex, q * q * sy + 2 * q * t * my + t * t * ey)
                assert not any(inside(point, f) for j, f in enumerate(p.frames) if j != i)


def test_the_plume_grows_away_from_the_nearest_edges():
    sizes = STACKS[1]
    p = plume((1300, 120), SCREEN, sizes)
    assert (p.side, p.grow) == ("left", "up")
    assert p.frames[0].x + p.frames[0].w < 1300 and p.frames[0].y < p.frames[1].y < p.frames[2].y
    q = plume((140, 780), SCREEN, sizes)
    assert (q.side, q.grow) == ("right", "down")
    assert q.frames[0].x > 140 and q.frames[0].y > q.frames[1].y > q.frames[2].y
    assert plume((140, 120), SCREEN, sizes).frames == tuple(Rect(1440 - f.x - f.w, f.y, f.w, f.h) for f in p.frames)
    assert plume((1300, 780), SCREEN, sizes).frames == tuple(Rect(f.x, 900 - f.y - f.h, f.w, f.h) for f in p.frames)


def test_the_anchor_is_the_marks_centre():
    for centre, edge in (((1300, 120), lambda f: f.x + f.w - 18), ((140, 780), lambda f: f.x + 18)):
        p = plume(centre, SCREEN, [(300, 150), (190, 36)])
        assert p.anchors == tuple((edge(f), f.y + f.h - 18) for f in p.frames)


def test_the_field_covers_the_circle_and_every_bead():
    p = plume((1300, 120), SCREEN, STACKS[3])
    rects = [Rect(1220, 40, 160, 160), *p.frames]
    x0, y0 = min(r.x for r in rects) - 24, min(r.y for r in rects) - 24
    x1, y1 = max(r.x + r.w for r in rects) + 24, max(r.y + r.h for r in rects) + 24
    assert p.field == Rect(x0, y0, x1 - x0, y1 - y0)


def test_no_beads_is_an_empty_plume():
    p = plume((1300, 120), SCREEN, [])
    assert p.frames == () and p.anchors == ()
    assert p.field == Rect(1196, 16, 208, 208)


def test_a_thread_ends_on_the_rim_and_sways_only_its_control():
    anchor, centre = (1000, 400), (1300, 120)
    start, control, end = thread(anchor, centre)
    assert math.dist(anchor, start) == pytest.approx(13)
    assert math.dist(end, centre) == pytest.approx(config.TETHER_RIM)
    assert math.dist(anchor, start) + math.dist(start, end) + math.dist(end, centre) == pytest.approx(math.dist(anchor, centre))
    s, c, e = thread(anchor, centre, sway=6)
    assert (s, e) == (start, end) and c != control


def test_a_threads_bow_mirrors_with_the_plume():
    anchor, centre = (1000, 400), (1300, 120)
    across, over = (lambda p: (1440 - p[0], p[1])), (lambda p: (p[0], 900 - p[1]))
    for sway in (-6, 0, 6):
        drawn = thread(anchor, centre, sway, "left")
        assert thread(across(anchor), across(centre), sway, "right") == tuple(pytest.approx(across(p)) for p in drawn)
        assert thread(over(anchor), over(centre), sway, "left") == tuple(pytest.approx(over(p)) for p in drawn)


def test_a_plume_that_cannot_fit_still_keeps_every_bead_on_screen():   # the final review's M12, found at random
    s = Rect(0, 25, 1280, 775)
    sizes = [(300, 230), (182.8, 36), (300, 116), (237, 36), (300, 230), (110.5, 26)]
    for f in plume((896.25, 136.87), s, sizes).frames:
        assert s.x <= f.x and f.x + f.w <= s.x + s.w and s.y <= f.y and f.y + f.h <= s.y + s.h


LIVE = [(300, 150)] * 5 + [(150, 24)]   # row 9: five tall questions and "+2 more need you"
SCREENS = [SCREEN, Rect(0, 0, 1512, 982), Rect(0, 0, 1440, 875)]   # the last: a 1440x900 display under its menu bar


def homes(s):
    """The circle's default place, the same 40 points in at each other corner, and the middle."""
    dx, dy = place.default(config.CIRCLE_SIZE, s.w, s.h)
    x, y = dx + config.CIRCLE_SIZE / 2, dy + config.CIRCLE_SIZE / 2
    return [(s.x + x, s.y + y), (s.x + s.w - x, s.y + y), (s.x + x, s.y + s.h - y), (s.x + s.w - x, s.y + s.h - y),
            (s.x + s.w / 2, s.y + s.h / 2)]


def beyond(p, f):
    """Whether `f` hangs in a column further out than the first bead's."""
    first = p.frames[0]
    return f.x + f.w < first.x if p.side == "left" else f.x > first.x + first.w


def holds(centre, screen, sizes):
    """Every rule of the plume, a column further out included; returns the plume."""
    p = plume(centre, screen, sizes)
    assert [(f.w, f.h) for f in p.frames] == list(sizes)
    for i, a in enumerate(p.frames):
        assert gap(centre, a) > config.TETHER_RIM
        assert not any(overlap(a, b) for b in p.frames[i + 1:])
        assert screen.x <= a.x and a.x + a.w <= screen.x + screen.w and screen.y <= a.y and a.y + a.h <= screen.y + screen.h
    assert (p.side, p.grow) == ("left" if centre[0] > screen.x + screen.w / 2 else "right",
                                "up" if centre[1] < screen.y + screen.h / 2 else "down")
    out = [f for f in p.frames if beyond(p, f)]
    assert p.frames[len(p.frames) - len(out):] == tuple(out)   # once wrapped, every later item follows, the chip last
    assert [f.y for f in out] == sorted((f.y for f in out), reverse=p.grow == "down")
    for i, anchor in enumerate(p.anchors):
        for sway in (-6, 0, 6):
            (sx, sy), (mx, my), (ex, ey) = thread(anchor, centre, sway, p.side)
            for t in (k / 19 for k in range(20)):
                q = 1 - t
                point = (q * q * sx + 2 * q * t * mx + t * t * ex, q * q * sy + 2 * q * t * my + t * t * ey)
                for j, f in enumerate(p.frames):
                    if j != i and inside(point, f):   # only a further column's thread, behind a nearer bead
                        assert beyond(p, p.frames[i]) and not beyond(p, f)
    return p


@pytest.mark.parametrize("screen", SCREENS)
def test_five_tall_questions_and_a_chip_fit_wherever_the_circle_starts(screen):
    for centre in homes(screen):
        holds(centre, screen, LIVE)


def test_on_a_full_size_screen_five_tall_questions_need_no_second_column():
    for screen in SCREENS[:2]:
        for centre in homes(screen):
            p = holds(centre, screen, LIVE)
            assert not any(beyond(p, f) for f in p.frames)


def test_beads_that_do_not_fit_one_column_wrap_into_a_second_further_out():
    for centre in homes(SCREEN):
        p = holds(centre, SCREEN, [(300, 150)] * 7)
        assert any(beyond(p, f) for f in p.frames)
    p = holds((1320, 120), Rect(0, 0, 1440, 875), LIVE)
    assert [beyond(p, f) for f in p.frames] == [False] * 4 + [True] * 2
    assert p.frames[4].x + p.frames[4].w == p.frames[0].x - config.CARD_GAP and p.frames[4].y == p.frames[0].y
