import asyncio

import pytest

from jarvis.daemon import names
from jarvis.daemon.state import State
from tests.conftest import NOW, FakeSpeaker, day_log, until
from tests.daemon.events import GOOD_VERDICT, agent_done, agent_start, call_from, rows, tool, tool_result, turn

STOPPED = {"verdict": "deny", "reason": "Febriel stopped this agent."}


@pytest.fixture(autouse=True)
def nova_then_orin(monkeypatch):
    calls = iter(("Nova", "Orin"))
    monkeypatch.setattr(names, "pick", lambda in_use: next(calls))


async def workers(j, bridge, *ids, text="fix the export bug"):
    t = asyncio.create_task(j.submit(text, "mac")); await bridge.got(text)
    bridge.emit(tool("Agent", {"subagent_type": "triage"})); bridge.emit(tool_result(GOOD_VERDICT))
    for i in ids:
        bridge.emit(agent_start(i, "coder", background=True, tool_use_id=f"tu-{i}"))
    bridge.emit(turn("Started.")); await t


def outside_write(tmp_path):
    return {"file_path": str(tmp_path / "outside.txt")}


async def say(j, text):
    return (await asyncio.wait_for(j.submit(text, "mac"), 1)).say


def published(j):
    q = asyncio.Queue(); j._subs.append(q)
    return lambda: [q.get_nowait() for _ in range(q.qsize())]


async def test_a_stopped_agent_can_do_nothing_more(jarvis, bridge):               # Review Focus 3
    await workers(jarvis, bridge, "t1", "t2")
    assert rows(jarvis)["t1"]["call"] == "Nova"
    assert await jarvis.stop_agent("t1")
    assert await jarvis.hook(call_from("t1", "Bash", {"command": "ls"})) == STOPPED
    assert (await jarvis.hook(call_from("t2", "Bash", {"command": "ls"})))["verdict"] == "allow"
    assert rows(jarvis)["t1"]["state"] == "stopped" and rows(jarvis)["t2"]["state"] == "working"


async def test_stopping_answers_its_open_question_no(jarvis, bridge, tmp_path):
    await workers(jarvis, bridge, "t1")
    h = asyncio.create_task(jarvis.hook(call_from("t1", "Write", outside_write(tmp_path))))
    await until(lambda: jarvis.asks.pending())
    assert await jarvis.stop_agent("t1")
    assert await h == STOPPED
    assert not jarvis.asks.pending() and jarvis.asks.history()[-1][2] is False


async def test_a_yes_that_lands_as_it_is_stopped_is_still_refused(jarvis, bridge, tmp_path):   # Review Focus 3
    await workers(jarvis, bridge, "t1")
    h = asyncio.create_task(jarvis.hook(call_from("t1", "Write", outside_write(tmp_path))))
    await until(lambda: jarvis.asks.pending())
    assert jarvis.answer("yes", ask_id=jarvis.asks.pending()[0].id)
    assert await jarvis.stop_agent("t1")
    assert await h == STOPPED


async def test_the_stop_task_request_is_sent(make, bridge_of, vault):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    await workers(j, b, "t1", "t2")
    seen, said, sent = published(j), len(sp.calls), list(b.sent)
    assert await j.stop_agent("t1")
    assert b.stopped_tasks == ["t1"] and b.sent == sent
    assert not any(e["type"] in ("heard", "reply") for e in seen()) and sp.calls[said:] == []
    log = vault.raw / f"{NOW:%Y-%m-%d}.md"
    assert not log.exists() or "stop" not in log.read_text().lower()


async def test_a_stopped_agents_result_is_not_announced(make, bridge_of, vault):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    await workers(j, b, "t1")
    assert await j.stop_agent("t1")
    seen, said = published(j), len(sp.calls)
    b.emit(agent_done("t1", "stopped", "Nova was stopped.", tool_use_id="tu-t1"))
    b.emit({"kind": "turn_start"}); b.emit({"kind": "delta", "text": "The export bug is fixed."})
    b.emit(turn("The export bug is fixed."))
    assert not [c for c in sp.calls[said:] if c[0] in ("say", "feed")]
    assert not [e for e in seen() if e["type"] in ("reply", "reply_delta")]
    note = next(vault.raw.glob("*-fix-export-bug.md")).read_text()
    assert "(stopped by Febriel)" in note and "The export bug is fixed." not in note
    assert "(worker finished)" not in day_log(vault) and rows(j)["t1"]["state"] == "stopped"


async def test_after_a_hushed_turn_the_next_one_is_heard(make, bridge_of):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    await workers(j, b, "t1", "t2")
    await j.stop_agent("t1")
    b.emit(agent_done("t1", "stopped", "stopped", tool_use_id="tu-t1"))
    b.emit({"kind": "turn_start"}); b.emit(turn("Nova was stopped."))
    b.emit(agent_done("t2", "completed", "Fixed.", tool_use_id="tu-t2"))
    b.emit({"kind": "turn_start"}); b.emit({"kind": "delta", "text": "Orin fixed it."}); b.emit(turn("Orin fixed it."))
    assert ("feed", "Orin fixed it.") in sp.calls and ("say", "Orin fixed it.") in sp.calls


async def test_stop_by_voice_names_it_and_says_so(jarvis, bridge, vault):
    await workers(jarvis, bridge, "t1", "t2")
    assert await say(jarvis, "Jarvis, stop Nova") == "Stopped Nova."
    assert bridge.stopped_tasks == ["t1"] and rows(jarvis)["t2"]["state"] == "working"
    assert "Jarvis, stop Nova → Stopped Nova." in day_log(vault) and "Jarvis, stop Nova" not in bridge.sent


async def test_a_card_stop_says_nothing(make, bridge_of):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    await workers(j, b, "t1")
    said = len(sp.calls)
    await j.stop_agent("t1")
    assert not [c for c in sp.calls[said:] if c[0] == "say"]


async def test_yes_to_a_name_answers_that_question_only(jarvis, bridge, tmp_path):   # Review Focus 2
    await workers(jarvis, bridge, "t1", "t2")
    nova = asyncio.create_task(jarvis.hook(call_from("t1", "Write", outside_write(tmp_path))))
    orin = asyncio.create_task(jarvis.hook(call_from("t2", "Write", outside_write(tmp_path))))
    await until(lambda: len(jarvis.asks.pending()) == 2)
    assert await say(jarvis, "yes to Orin") == "Okay."
    assert (await asyncio.wait_for(orin, 1))["verdict"] == "allow" and not nova.done()
    assert await say(jarvis, "no to Nova") == "Okay."
    assert (await asyncio.wait_for(nova, 1))["verdict"] == "deny"


async def test_a_name_with_no_question_says_so(jarvis, bridge, vault, tmp_path):
    await workers(jarvis, bridge, "t1", "t2")
    orin = asyncio.create_task(jarvis.hook(call_from("t2", "Write", outside_write(tmp_path))))
    await until(lambda: jarvis.asks.pending())
    assert await say(jarvis, "yes to Nova") == "Nova has no question open."
    assert not orin.done() and "yes to Nova → Nova has no question open." in day_log(vault)
    jarvis.answer("no", ask_id=jarvis.asks.pending()[0].id); await orin


async def test_yes_to_jarvis_answers_jarvis_own_question(jarvis, bridge, tmp_path):
    t = asyncio.create_task(jarvis.submit("make a file", "mac")); await bridge.got("make a file")
    h = asyncio.create_task(jarvis.hook(call_from(None, "Write", outside_write(tmp_path))))
    assert (await t).say.endswith("Yes or no?")
    t2 = asyncio.create_task(jarvis.submit("yes to Jarvis", "mac"))
    assert (await asyncio.wait_for(h, 1))["verdict"] == "allow"
    bridge.emit(turn("Done.")); assert (await t2).say == "Done."


async def test_stop_jarvis_answers_its_question_no(jarvis, bridge, tmp_path):
    t = asyncio.create_task(jarvis.submit("make a file", "mac")); await bridge.got("make a file")
    h = asyncio.create_task(jarvis.hook(call_from(None, "Write", outside_write(tmp_path))))
    await t
    t2 = asyncio.create_task(jarvis.submit("stop Jarvis", "mac"))
    assert (await asyncio.wait_for(h, 1))["verdict"] == "deny" and bridge.stopped_tasks == []
    bridge.emit(turn("Okay, I won't.")); assert (await t2).say == "Okay, I won't."


async def test_plain_stop_still_cancels_everything(jarvis, bridge):
    await workers(jarvis, bridge, "t1")
    assert await say(jarvis, "stop") == "Cancelled."
    assert bridge.restarted == 1 and bridge.stopped_tasks == [] and jarvis.state is State.IDLE


async def test_stopping_twice_or_an_unknown_id_is_false(jarvis, bridge):
    await workers(jarvis, bridge, "t1")
    assert await jarvis.stop_agent("t1")
    assert not await jarvis.stop_agent("t1")
    assert not await jarvis.stop_agent("nope") and not await jarvis.stop_agent("jarvis")
    assert bridge.stopped_tasks == ["t1"]


async def test_an_ended_agent_cannot_be_stopped_and_keeps_its_state(jarvis, bridge):
    await workers(jarvis, bridge, "t1", "t2")
    bridge.emit(agent_done("t1", "completed", "ok", tool_use_id="tu-t1"))
    assert not await jarvis.stop_agent("t1") and rows(jarvis)["t1"]["state"] == "done"
    await jarvis.stop_agent("t2")
    bridge.emit(agent_done("t2", "completed", "I stopped because the user did.", tool_use_id="tu-t2"))
    assert rows(jarvis)["t2"]["state"] == "stopped"


async def test_a_second_answer_to_the_same_question_changes_nothing(jarvis, bridge, tmp_path):   # card and voice race
    await workers(jarvis, bridge, "t1")
    h = asyncio.create_task(jarvis.hook(call_from("t1", "Write", outside_write(tmp_path))))
    await until(lambda: jarvis.asks.pending())
    aid = jarvis.asks.pending()[0].id
    assert jarvis.answer("yes", ask_id=aid)
    assert not jarvis.answer("no", ask_id=aid)
    assert await say(jarvis, "no to Nova") == "Nova has no question open."
    assert (await h)["verdict"] == "allow"
