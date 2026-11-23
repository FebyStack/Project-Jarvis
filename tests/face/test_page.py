from importlib import resources

PAGE = resources.files("jarvis.face") / "page"


def test_the_page_has_the_policy_and_loads_only_its_own_files():
    html = (PAGE / "circle.html").read_text()
    assert "default-src 'none'; script-src 'self'; style-src 'self'" in html
    assert "http://" not in html and "https://" not in html and "<script>" not in html


def test_the_page_script_cannot_turn_text_into_markup_or_reach_out():
    src = (PAGE / "circle.js").read_text()
    for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "Function(",
                   "fetch(", "XMLHttpRequest", "WebSocket", "localStorage", "http://", "https://"):
        assert banned not in src, banned


def test_the_page_draws_no_cards_and_posts_nothing():
    assert sorted(p.name for p in PAGE.iterdir() if p.suffix in (".html", ".js", ".css")) == ["circle.html", "circle.js", "face.css"]
    src = (PAGE / "circle.js").read_text()
    assert '"answer"' not in src and '"stop"' not in src and "'answer'" not in src and "'stop'" not in src
    assert "webkit" not in src and "postMessage" not in src


def test_the_colours_are_the_three_reds_and_no_gold():
    css = (PAGE / "face.css").read_text().upper() + (PAGE / "circle.js").read_text().upper()
    assert all(c in css for c in ("#FF3B30", "#C2241B", "#6B1512")) and "#D4AF37" not in css and "#FFD700" not in css


def test_the_page_files_ship_with_the_package():
    assert all((PAGE / n).is_file() for n in ("circle.html", "face.css", "circle.js"))


def test_slow_frames_are_timed_by_a_timer_not_by_the_display():   # the final review's recommendation 3
    src = (PAGE / "circle.js").read_text()
    assert "setTimeout(" in src and "requestAnimationFrame(" in src
