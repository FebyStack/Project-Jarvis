import asyncio

from jarvis import config
from jarvis.daemon.names import NAMES
from tests.conftest import until
from tests.daemon.events import GOOD_VERDICT, agent_done, agent_start, call_from, rows, tool, tool_result, turn


async def start_worker(jarvis, bridge, channel="mac", workers=(("t1", "coder", "tu9"),), text="fix the export bug"):
    t = asyncio.create_task(jarvis.submit(text, channel)); await bridge.got(text)
    bridge.emit(tool("Agent", {"subagent_type": "triage"})); bridge.emit(tool_result(GOOD_VERDICT))
    for task_id, agent, tu in workers:
        bridge.emit(agent_start(task_id, agent, background=True, tool_use_id=tu))
    bridge.emit(turn("Started.")); await t


def outside_write(tmp_path):
    return {"file_path": str(tmp_path / "outside.txt")}


async def test_a_workers_row_has_what_a_card_needs(jarvis, bridge):
    await start_worker(jarvis, bridge)
    row = rows(jarvis)["t1"]
    assert row["name"] == "coder" and row["call"] in NAMES and row["title"] == "Fix export bug"
    assert row["state"] == "working" and row["question"] is None and row["channel"] == "mac"
    assert row["ask_id"] is None and row["ask_until"] is None


async def test_two_workers_never_share_a_name(jarvis, bridge):
    await start_worker(jarvis, bridge, workers=(("t1", "coder", "tu1"), ("t2", "researcher", "tu2")))
    r = rows(jarvis)
    assert r["t1"]["call"] != r["t2"]["call"]


async def test_the_question_sits_on_the_agent_that_asked(jarvis, bridge, clock, tmp_path):
    await start_worker(jarvis, bridge, workers=(("t1", "coder", "tu1"), ("t2", "researcher", "tu2")))
    other = dict(rows(jarvis)["t2"])
    clock.advance(5)
    h = asyncio.create_task(jarvis.hook(call_from("t1", "Write", outside_write(tmp_path))))
    await until(lambda: jarvis.asks.pending())
    row = rows(jarvis)["t1"]
    assert row["state"] == "needs_you" and row["question"].endswith("Yes or no?") and row["ask_id"]
    assert row["ask_until"] == 5 + config.ASK_TIMEOUT["mac"] and rows(jarvis)["t2"] == other
    assert jarvis.answer("yes", ask_id=row["ask_id"])
    await h; await until(lambda: not jarvis.asks.pending())
    row = rows(jarvis)["t1"]
    assert row["state"] == "working" and row["question"] is None and row["ask_until"] is None


async def test_jarvis_own_question_sits_on_the_jarvis_row(jarvis, bridge, tmp_path):
    t = asyncio.create_task(jarvis.submit("make a file", "mac")); await bridge.got("make a file")
    h = asyncio.create_task(jarvis.hook(call_from(None, "Write", outside_write(tmp_path))))
    await until(lambda: jarvis.asks.pending())
    row = rows(jarvis)["jarvis"]
    assert row["state"] == "needs_you" and row["call"] == "Jarvis" and row["question"]
    jarvis.answer("no"); await h; await t


async def test_an_ended_row_lingers_eight_seconds(jarvis, bridge, clock):
    await start_worker(jarvis, bridge)
    events = jarvis.subscribe(); await anext(events)
    bridge.emit(agent_done("t1", "completed", "ok", tool_use_id="tu9")); await anext(events)
    assert rows(jarvis)["t1"]["state"] == "done"
    clock.advance(7.9); await jarvis.tick(); assert "t1" in rows(jarvis)
    clock.advance(0.1); await jarvis.tick(); assert "t1" not in rows(jarvis)
    while (e := await anext(events))["type"] != "agents":
        pass
    assert all(i["id"] != "t1" for i in e["items"])


async def test_a_failed_worker_says_failed(jarvis, bridge):
    await start_worker(jarvis, bridge)
    bridge.emit(agent_done("t1", "failed", "boom", tool_use_id="tu9"))
    assert rows(jarvis)["t1"]["state"] == "failed"


async def test_a_stopped_worker_says_stopped(jarvis, bridge):
    await start_worker(jarvis, bridge)
    bridge.emit(agent_done("t1", "stopped", "stopped", tool_use_id="tu9"))
    assert rows(jarvis)["t1"]["state"] == "stopped"


async def test_triage_and_scribe_have_no_name(jarvis, bridge):
    t = asyncio.create_task(jarvis.submit("fix the export bug", "mac")); await bridge.got("fix the export bug")
    bridge.emit(agent_start("t0", "triage", tool_use_id="tu0")); bridge.emit(agent_start("t5", "scribe", tool_use_id="tu5"))
    r = rows(jarvis)
    assert r["t0"]["call"] == "" and r["t5"]["call"] == ""
    bridge.emit(turn("ok")); await t


async def test_a_phone_request_marks_its_rows(jarvis, bridge):
    await start_worker(jarvis, bridge, channel="phone")
    assert rows(jarvis)["t1"]["channel"] == "phone"
