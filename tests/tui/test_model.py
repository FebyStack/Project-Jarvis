import pytest

from jarvis.tui.model import View, elapsed, limits_text, needs_you, reduce
from tests.tui.events import SNAPSHOT


def test_snapshot_then_events():
    v = reduce(View.empty(), SNAPSHOT); assert v.link == "online" and v.screen == "main" and v.voice == "IDLE"
    v = reduce(v, {"type": "heard", "text": "open the captions repo", "channel": "mac"}); assert v.last_heard == "open the captions repo"
    v = reduce(v, {"type": "reply_delta", "text": "Open"}); v = reduce(v, {"type": "reply_delta", "text": "ing."}); assert v.reply == "Opening."
    v = reduce(v, {"type": "reply", "text": "Opening it now.", "channel": "mac", "loop": False}); assert v.reply == "Opening it now."
    v = reduce(v, {"type": "memory", "op": "r", "path": "wiki/preferences.md"}); assert v.memory[0] == ("r", "wiki/preferences.md")


def test_memory_keeps_the_newest_fifty():
    v = View.empty()
    for i in range(60): v = reduce(v, {"type": "memory", "op": "+", "path": f"raw/{i}.md"})
    assert len(v.memory) == 50 and v.memory[0][1] == "raw/59.md"


@pytest.mark.parametrize("health,screen", [
    ({"brain": "starting", "vault": "ok", "checklist": []}, "starting"), ({"brain": "offline", "vault": "ok", "checklist": []}, "offline"),
    ({"brain": "online", "vault": "missing", "checklist": []}, "vault"), ({"brain": "limit", "vault": "ok", "checklist": []}, "limit"),
    ({"brain": "online", "vault": "ok", "checklist": ["claude is not on PATH"]}, "first-run"), ({"brain": "online", "vault": "ok", "checklist": []}, "main")])
def test_screen_follows_health(health, screen):
    assert reduce(reduce(View.empty(), SNAPSHOT), {"type": "health", **health}).screen == screen


def test_small_helpers():
    assert limits_text({"status": "near", "weekly": 0.33}) == "LIMITS ● 33%" and limits_text({"status": "reached", "weekly": None}) == "LIMITS ● reached"
    assert elapsed(0, 252) == "04:12"
    v = reduce(reduce(View.empty(), SNAPSHOT), {"type": "queue", "items": [
        {"id": "a", "title": "fix export bug", "status": "running"},
        {"id": "b", "title": "delete 14 files", "status": "needs_you", "question": "Delete 14 files? Yes or no?", "ask_id": "k1"}]})
    assert needs_you(v).ask_id == "k1"
    assert reduce(v, {"type": "link", "state": "no daemon"}).screen == "no-daemon"


def test_empty_view_is_connecting():
    v = View.empty(); assert v.link == "connecting" and v.screen == "main" and needs_you(v) is None


def test_snapshot_fills_every_panel():
    v = reduce(View.empty(), SNAPSHOT)
    assert v.agents[0].name == "jarvis" and v.agents[0].doing == "talking to you"
    assert v.memory == (("r", "wiki/preferences.md"),) and v.limits == "LIMITS ● 33%" and v.health["mic"] == "off"


def test_a_new_turn_starts_a_new_reply():
    v = reduce(View.empty(), {"type": "reply", "text": "Done.", "channel": "mac", "loop": False})
    assert reduce(v, {"type": "reply_delta", "text": "The export"}).reply == "The export"
    assert reduce(v, {"type": "heard", "text": "next", "channel": "mac"}).reply == ""


def test_health_event_keeps_fields_it_does_not_send():
    v = reduce(reduce(View.empty(), SNAPSHOT), {"type": "health", "brain": "online", "vault": "ok", "checklist": []})
    assert v.health["phone"] == "not linked"


def test_limit_keeps_the_reset_time():
    v = reduce(View.empty(), {"type": "limits", "status": "reached", "weekly": None, "resets_at": 1000.0})
    assert v.limits == "LIMITS ● reached" and v.resets_at == 1000.0


def test_unknown_event_changes_nothing():
    v = reduce(View.empty(), SNAPSHOT)
    assert reduce(v, {"type": "phone_ring", "at": "x"}) is v


# ── Plan 3, Task 13: the voice ──

def test_levels_keep_the_last_28():
    v = reduce(View.empty(), SNAPSHOT)
    for i in range(40): v = reduce(v, {"type": "level", "rms": i / 100})
    assert len(v.levels) == 28 and v.levels[-1] == 0.39 and v.levels[0] == 0.12


def test_levels_clear_when_the_mic_goes_off():
    v = reduce(reduce(View.empty(), SNAPSHOT), {"type": "level", "rms": 0.5}); assert v.levels == (0.5,)
    assert reduce(v, {"type": "health", "mic": "muted"}).levels == ()
