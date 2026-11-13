import pytest

from jarvis.brain.gate import ASK_WORDS, classify_screen, classify_tool


def test_ask_words_are_the_spec_list():
    assert ASK_WORDS == ("send", "submit", "post", "publish", "pay", "buy", "delete", "remove", "confirm", "sign")


@pytest.mark.parametrize("label,verdict", [
    ("Send", "ask"), ("Send Message", "ask"), ("Delete…", "ask"), ("CONFIRM", "ask"),
    ("Sender", "allow"), ("Reply", "allow"), ("Postpone", "allow"),
])
def test_click_judged_by_whole_word_label(label, verdict, cfg):
    assert classify_screen("click", "Mail", cfg, role="button", label=label).verdict == verdict


@pytest.mark.parametrize("role", ["button", "menubutton", "image", "treeitem", "group", "unknown", "", "widget"])
@pytest.mark.parametrize("label", ["", "   "])
def test_unlabelled_click_asks_and_is_never_remembered(role, label, cfg):
    d = classify_screen("click", "Finder", cfg, role=role, label=label)
    assert d.verdict == "ask" and d.pattern == ""


@pytest.mark.parametrize("role", ["textfield", "scrollarea", "scrollbar", "list", "outline", "cell", "TextField"])
def test_unlabelled_click_on_passive_role_is_free(role, cfg):
    assert classify_screen("click", "TextEdit", cfg, role=role, label="").verdict == "allow"


def test_typing_scrolling_opening_are_free(cfg):
    for action in ("type", "scroll", "open"):
        assert classify_screen(action, "Finder", cfg, role="textfield", label="Search").verdict == "allow"


def test_return_asks_until_app_is_trusted(cfg):
    d = classify_screen("press", "Messages", cfg, key="Return")
    assert d.verdict == "ask" and d.pattern == "screen:Messages:key:return"
    cfg.trusted.add(d.pattern)
    assert classify_screen("press", "Messages", cfg, key="Return").verdict == "allow"


def test_click_pattern_is_app_plus_word(cfg):
    assert classify_screen("click", "Mail", cfg, role="button", label="Send Message").pattern == "screen:Mail:send"


def test_trusted_click_word_allows_only_that_app(cfg):
    cfg.trusted.add("screen:Mail:send")
    assert classify_screen("click", "Mail", cfg, role="button", label="Send").verdict == "allow"
    assert classify_screen("click", "Messages", cfg, role="button", label="Send").verdict == "ask"


def test_other_keys_are_free(cfg):
    assert classify_screen("press", "Messages", cfg, key="Tab").verdict == "allow"


def test_drag_asks(cfg):
    assert classify_screen("drag", "Finder", cfg).verdict == "ask"


def test_tools_free_only_if_listed_as_read(cfg):
    cfg.read_tools.add("mcp__gmail__search_threads")
    assert classify_tool("mcp__gmail__search_threads", cfg).verdict == "allow"
    assert classify_tool("mcp__gmail__create_draft", cfg).verdict == "ask"
    assert classify_tool("mcp__unknown__thing", cfg).verdict == "ask"
