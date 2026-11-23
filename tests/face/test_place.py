from jarvis.face import place
from jarvis.face.tether import Rect


def test_place_round_trips_and_survives_a_broken_file(tmp_path):
    assert place.load(tmp_path) is None
    place.save(tmp_path, 12.5, 30)
    assert place.load(tmp_path) == (12.5, 30)
    (tmp_path / "face.json").write_text("{nope")
    assert place.load(tmp_path) is None
    (tmp_path / "face.json").write_text('{"x": "a", "y": 1}')
    assert place.load(tmp_path) is None


def test_a_place_off_screen_is_pulled_back():
    assert place.on_screen(5000, -30, 160, 1440, 900) == (1280, 0)
    assert place.on_screen(-5, 950, 160, 1440, 900) == (0, 740)
    assert place.on_screen(100, 200, 160, 1440, 900) == (100, 200)


def test_the_default_is_bottom_right():
    assert place.default(160, 1440, 900) == (1240, 40)


def test_only_one_face_holds_the_lock(tmp_path):   # the final review's M10
    first = place.single(tmp_path)
    assert first is not None and place.single(tmp_path) is None
    first.close()
    again = place.single(tmp_path)
    assert again is not None
    again.close()


def test_the_circle_takes_clicks_only_inside_its_round():   # M11: the square's corners pass clicks through
    assert place.takes_click(80, 80, 0, 0, 160) and place.takes_click(159, 80, 0, 0, 160)
    assert not place.takes_click(5, 5, 0, 0, 160) and not place.takes_click(150, 152, 0, 0, 160)
    assert place.takes_click(1100, 220, 1020, 140, 160) and not place.takes_click(1025, 145, 1020, 140, 160)


def test_outside_the_square_the_panel_already_takes_clicks():   # re-review N2: no lag when the pointer comes in
    assert place.takes_click(-30, 80, 0, 0, 160) and place.takes_click(80, 400, 0, 0, 160)
    assert place.takes_click(-1, -1, 0, 0, 160) and not place.takes_click(1, 1, 0, 0, 160)


def test_the_pointer_is_followed_fast_only_near_the_circle():   # re-review N2
    assert place.follow_every(80, 80, 0, 0, 160) == place.follow_every(2, 2, 0, 0, 160) == 1 / 60
    assert place.follow_every(80, 80 + 80 + place.NEAR, 0, 0, 160) == 1 / 60
    assert place.follow_every(80, 80 + 80 + place.NEAR + 1, 0, 0, 160) == 0.1 == place.follow_every(900, 900, 0, 0, 160)


def test_a_bead_is_left_once_the_pointer_is_off_it_and_off_where_it_came_in():   # live, 2026-11-23: stuck open
    bead, came_in = Rect(40, 0, 100, 98), Rect(0, 0, 60, 36)   # it opened and moved: the pointer came in at the left
    rects = {"t1": (bead, came_in)}
    assert place.left(100, 50, {"t1"}, rects) == []            # on the bead
    assert place.left(20, 20, {"t1"}, rects) == []             # where it came in: still the hover (M6)
    assert place.left(20, 60, {"t1"}, rects) == ["t1"]         # off both, whatever moved under a still pointer
    assert place.left(100, 50, {"t1"}, {}) == ["t1"]           # its bead is gone: closed, or behind "+N more"
    assert place.left(20, 60, set(), rects) == []              # only a bead the pointer went into
