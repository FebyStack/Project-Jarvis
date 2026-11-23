from jarvis.face import place


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
