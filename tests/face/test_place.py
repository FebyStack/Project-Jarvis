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
