import asyncio

from jarvis import config
from jarvis.daemon.names import NAMES
from tests.conftest import until
from tests.conftest import FakeSpeaker
from tests.daemon.events import (GOOD_VERDICT, agent_call, agent_done, agent_start, call_from, rows, tool, tool_result,
                                  turn)


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


async def test_an_ended_row_keeps_its_title_and_channel_after_its_request_is_gone(jarvis, bridge):
    await start_worker(jarvis, bridge, channel="phone")
    bridge.emit(agent_done("t1", "completed", "ok", tool_use_id="tu9")); bridge.emit(turn("Fixed."))
    await until(lambda: jarvis._find("1") is None)
    row = rows(jarvis)["t1"]
    assert row["state"] == "done" and row["channel"] == "phone" and row["title"] == "Fix export bug"


async def triaged(jarvis, bridge, text="fix the export bug"):
    t = asyncio.create_task(jarvis.submit(text, "mac")); await bridge.got(text)
    bridge.emit(tool("Agent", {"subagent_type": "triage"})); bridge.emit(tool_result(GOOD_VERDICT))
    return t


async def test_the_name_is_chosen_when_the_dispatch_is_allowed(jarvis, bridge):
    t = await triaged(jarvis, bridge)
    out = await jarvis.hook(agent_call("coder", tool_use_id="tu9", description="Fix export bug", prompt="Do it."))
    name = out["input"]["description"].split(":")[0]
    assert name in NAMES and out["input"]["description"] == f"{name}: Fix export bug"
    assert out["input"]["prompt"].startswith(f"Your name is {name}.\n\n") and out["input"]["subagent_type"] == "coder"
    bridge.emit(agent_start("t1", "coder", background=True, tool_use_id="tu9"))
    assert rows(jarvis)["t1"]["call"] == name and rows(jarvis)["t1"]["title"] == "Fix export bug"
    bridge.emit(turn("Started.")); await t


async def test_triage_and_a_refused_dispatch_get_no_name(jarvis, bridge):
    t = asyncio.create_task(jarvis.submit("fix the export bug", "mac")); await bridge.got("fix the export bug")
    out = await jarvis.hook(agent_call("triage", tool_use_id="tu0", description="Triage", prompt="Judge."))
    assert out["verdict"] == "allow" and "input" not in out
    denied = await jarvis.hook(agent_call("coder", tool_use_id="tu8", description="Fix", prompt="Do it."))
    assert denied["verdict"] == "deny" and "input" not in denied and not jarvis._named
    bridge.emit(tool("Agent", {"subagent_type": "triage"})); bridge.emit(tool_result(GOOD_VERDICT))
    out = await jarvis.hook(agent_call("coder", tool_use_id="tu9", description="Fix", prompt="Do it."))
    assert len(jarvis._named) == 1 and out["input"]["description"].split(":")[0] in NAMES
    bridge.emit(turn("ok")); await t


async def test_two_dispatches_before_either_starts_get_different_names(jarvis, bridge):
    t = await triaged(jarvis, bridge)
    a = await jarvis.hook(agent_call("coder", tool_use_id="tu1", description="A", prompt="p"))
    b = await jarvis.hook(agent_call("researcher", tool_use_id="tu2", description="B", prompt="p"))
    assert a["input"]["description"].split(":")[0] != b["input"]["description"].split(":")[0]
    bridge.emit(turn("ok")); await t


async def test_a_worker_the_hook_never_saw_still_gets_a_name(jarvis, bridge):
    await start_worker(jarvis, bridge)
    assert rows(jarvis)["t1"]["call"] in NAMES


async def test_a_question_is_announced_with_the_name(make, bridge_of, tmp_path):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    await start_worker(j, b)
    name = rows(j)["t1"]["call"]
    h = asyncio.create_task(j.hook(call_from("t1", "Write", outside_write(tmp_path))))
    await until(lambda: j.asks.pending())
    say = next(c[1] for c in sp.calls if c[0] == "say" and "Yes or no?" in c[1])
    assert say.startswith(f"{name} has a question. ") and say.endswith(" Yes or no?")
    j.answer("no"); await h


async def test_jarvis_own_question_keeps_its_wording(make, bridge_of, tmp_path):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    t = asyncio.create_task(j.submit("make a file", "mac")); await b.got("make a file")
    h = asyncio.create_task(j.hook(call_from(None, "Write", outside_write(tmp_path))))
    r = await t
    assert "has a question" not in r.say and r.say.endswith("Yes or no?")
    j.answer("no"); await h


async def test_several_open_questions_are_named_not_counted(jarvis, bridge, tmp_path):
    await start_worker(jarvis, bridge, workers=(("t1", "coder", "tu1"), ("t2", "researcher", "tu2"),
                                                ("t3", "coder", "tu3")))
    n = {k: rows(jarvis)[k]["call"] for k in ("t1", "t2", "t3")}
    hs = [asyncio.create_task(jarvis.hook(call_from(k, "Write", outside_write(tmp_path)))) for k in ("t1", "t2")]
    await until(lambda: len(jarvis.asks.pending()) == 2)
    r = await jarvis.submit("yes", "mac")
    assert r.say == (f"{n['t1']} and {n['t2']} each have a question. Say yes or no to one by name, or answer on its "
                     "card.")
    hs.append(asyncio.create_task(jarvis.hook(call_from("t3", "Write", outside_write(tmp_path)))))
    await until(lambda: len(jarvis.asks.pending()) == 3)
    r = await jarvis.submit("yes", "mac")
    assert r.say.startswith(f"{n['t1']}, {n['t2']} and {n['t3']} each have a question. ")
    for a in jarvis.asks.pending():
        jarvis.answer("no", ask_id=a.id)
    await asyncio.gather(*hs)


async def test_a_new_workers_doing_line_does_not_repeat_its_name(jarvis, bridge):   # the final review's M3
    t = await triaged(jarvis, bridge)
    out = await jarvis.hook(agent_call("coder", tool_use_id="tu9", description="Fix export bug", prompt="Do it."))
    bridge.emit(agent_start("t1", "coder", True, "tu9") | {"description": out["input"]["description"]})
    assert rows(jarvis)["t1"]["doing"] == "Fix export bug"
    bridge.emit(turn("Started.")); await t


async def test_a_dispatch_that_never_starts_frees_its_name_when_the_child_goes(jarvis, bridge):   # M15
    t = await triaged(jarvis, bridge)
    await jarvis.hook(agent_call("coder", tool_use_id="tu9", description="Fix export bug", prompt="Do it."))
    assert jarvis._named
    bridge.emit({"kind": "exited"})
    assert not jarvis._named
    await t


async def drained(events) -> list[dict]:
    out = []
    try:
        while True:
            out.append(await asyncio.wait_for(anext(events), 0.05))
    except TimeoutError:
        return out


async def test_the_face_key_hides_and_shows_the_face_and_says_so(jarvis):   # Ctrl-Option-J, Febriel 2026-11-23
    events = jarvis.subscribe()
    assert (await anext(events))["face_hidden"] is False   # jarvisd starts with the face shown
    jarvis.toggle_face()
    assert [(e["type"], e["hidden"]) for e in await drained(events)] == [("face", True)]
    assert jarvis.face_hidden and (await anext(jarvis.subscribe()))["face_hidden"] is True
    events = jarvis.subscribe(); await anext(events)
    jarvis.toggle_face()
    assert [(e["type"], e["hidden"]) for e in await drained(events)] == [("face", False)]


async def test_a_question_brings_the_hidden_face_back_before_its_bead(jarvis, bridge, tmp_path):
    await start_worker(jarvis, bridge, workers=(("t1", "coder", "tu1"), ("t2", "researcher", "tu2")))
    jarvis.toggle_face()
    events = jarvis.subscribe(); await anext(events)
    h1 = asyncio.create_task(jarvis.hook(call_from("t1", "Write", outside_write(tmp_path))))
    await until(lambda: jarvis.asks.pending())
    h2 = asyncio.create_task(jarvis.hook(call_from("t2", "Write", outside_write(tmp_path))))   # while shown: no news
    await until(lambda: len(jarvis.asks.pending()) == 2)
    seen = await drained(events)
    faces = [i for i, e in enumerate(seen) if e["type"] == "face"]
    asked = next(i for i, e in enumerate(seen) if e["type"] == "agents" and any(r["question"] for r in e["items"]))
    assert len(faces) == 1 and seen[faces[0]]["hidden"] is False and faces[0] < asked and not jarvis.face_hidden
    for a in jarvis.asks.pending():
        jarvis.answer("no", ask_id=a.id)
    await h1; await h2
