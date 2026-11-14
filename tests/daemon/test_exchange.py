from datetime import datetime

import pytest

from jarvis.daemon.exchange import Tracker
from jarvis.memory.vault import Vault
from tests.daemon.events import GOOD_VERDICT, agent_done, agent_start, tool, tool_result, turn

AT = datetime(2026, 11, 14, 20, 14)


@pytest.fixture
def vault(tmp_path):
    (tmp_path / "vault").mkdir()
    return Vault(tmp_path / "vault")


@pytest.fixture
def tracker(vault):
    return Tracker(vault, "r1", "mac", "fix the export bug now please", AT)


def test_small_exchange_is_one_log_line(tracker, vault):
    tracker.feed(turn("Canberra.")); assert tracker.closed and not tracker.is_task
    assert tracker.finish("Canberra.", []).name == f"{AT:%Y-%m-%d}.md"


def test_worker_needs_triage_then_notes(tracker, vault):
    (vault.root / "wiki").mkdir(); (vault.root / "wiki" / "prefs.md").write_text("x")
    assert tracker.may_dispatch("coder") == (False, "Call triage before dispatching a worker.")
    assert tracker.may_dispatch("triage") == (True, "")
    tracker.feed(tool("Agent", {"subagent_type": "triage"}))
    assert tracker.may_dispatch("coder") == (False, "Open the relevant wiki notes before dispatching a worker.")
    tracker.feed(tool("Read", {"file_path": str(vault.root / "wiki" / "prefs.md")}))
    assert tracker.may_dispatch("coder") == (True, "")


def test_empty_wiki_does_not_block(tracker):
    tracker.feed(tool("Agent", {"subagent_type": "triage"})); assert tracker.may_dispatch("researcher") == (True, "")


def test_any_other_agent_is_a_worker(tracker):
    assert tracker.may_dispatch("general-purpose") == (False, "Call triage before dispatching a worker.")
    assert tracker.may_dispatch("scribe") == (True, "")


def test_task_stays_open_until_its_background_worker_ends(tracker, vault):
    tracker.feed(tool("Agent", {"subagent_type": "triage"})); tracker.feed(tool_result(GOOD_VERDICT))
    tracker.feed(agent_start("t1", "coder", background=True))
    tracker.feed(tool("Write", {"file_path": "/x/y.py"}, model="claude-opus-5-5", parent="tu1"))
    tracker.feed(turn("Started.")); assert not tracker.closed
    with pytest.raises(RuntimeError): tracker.finish("Started.", [])
    tracker.feed(agent_done("t1", "completed", "Fixed the exporter.")); assert tracker.closed
    text = tracker.finish("Started.", [("Delete 14 files?", False)]).read_text()
    for needle in ("# Fix export bug", "jarvis (sonnet)", "triage (claude-opus-5-5)", "coder (claude-opus-5-5)",
                   "/x/y.py", "Fixed the exporter.", "Delete 14 files? — no"):
        assert needle in text


def test_title_falls_back_to_the_first_six_words(tracker, vault):
    tracker.feed(tool("Agent", {"subagent_type": "triage"})); tracker.feed(turn("Done."))
    assert tracker.finish("Done.", []).name == "2026-11-14-2014-fix-the-export-bug-now-please.md"


def test_a_background_triage_gives_its_verdict_in_its_summary(tracker):
    tracker.feed(tool("Agent", {"subagent_type": "triage"}, id="tuT"))
    tracker.feed(agent_start("t0", "triage", background=True, tool_use_id="tuT")); tracker.feed(turn("Waiting."))
    tracker.feed(agent_done("t0", "completed", GOOD_VERDICT, tool_use_id="tuT"))
    assert tracker.verdict.title == "Fix export bug" and tracker.closed
