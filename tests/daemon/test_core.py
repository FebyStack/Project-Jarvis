import asyncio
from datetime import datetime
from unittest.mock import ANY

import pytest

from jarvis.daemon.core import Jarvis, Reply
from jarvis.daemon.instant import say_time
from jarvis.daemon.state import State
from jarvis.memory.vault import Vault
from tests.daemon.events import GOOD_VERDICT, agent_done, agent_start, tool, tool_result, turn

NOW = datetime(2026, 11, 14, 20, 14)


async def until(pred, timeout=2.0):
    end = asyncio.get_running_loop().time() + timeout
    while not pred():
        if asyncio.get_running_loop().time() > end:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.005)


class FakeBridge:
    def __init__(self, on_event, memory_map):
        self.on_event, self.memory_map = on_event, memory_map
        self.sent, self.session_id, self.interrupted, self.resets, self.alive = [], "fake-session", False, 0, True
        self.restarted = 0

    async def start(self):
        self.on_event({"kind": "init", "session_id": self.session_id, "api_key_source": "none", "mcp_servers": []})

    async def send(self, text):
        if not self.alive:
            raise RuntimeError("the brain is not running")
        self.sent.append(text)

    async def interrupt(self):
        self.interrupted = True

    async def restart(self):  # the real one kills the child; its supervisor resumes the same session
        self.restarted += 1
        self.on_event({"kind": "exited"})

    async def reset(self):
        self.resets += 1

    async def stop(self):
        self.alive = False

    def emit(self, event):
        self.on_event(event)

    async def got(self, text):
        await until(lambda: text in self.sent)


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_HOME", str(tmp_path / "home")); monkeypatch.setenv("JARVIS_VAULT", str(tmp_path / "vault"))
    (tmp_path / "vault").mkdir()
    return Vault(tmp_path / "vault")


@pytest.fixture
def scribe_runs():
    return []


@pytest.fixture
async def make(vault, clock, scribe_runs):
    made = []

    async def build(v=vault, bridge=FakeBridge, **kw):
        kw.setdefault("run_scribe", lambda v, p: scribe_runs.append((v, p)))
        j = Jarvis(v, bridge, clock, lambda: NOW, **kw)
        await j.start(); made.append(j)
        return j
    yield build
    for j in made:
        await j.stop()


@pytest.fixture
async def jarvis(make):
    return await make()


@pytest.fixture
async def jarvis_fast_timeouts(make):
    return await make(ask_timeouts={"mac": 0.05, "phone": 0.2})


@pytest.fixture
async def jarvis_no_vault(make, tmp_path):
    return await make(Vault(tmp_path / "nope"))


@pytest.fixture
def bridge_of():
    return lambda j: j.bridge


@pytest.fixture
def bridge(request):
    for name in ("jarvis", "jarvis_fast_timeouts", "jarvis_no_vault"):
        if name in request.fixturenames:
            return request.getfixturevalue(name).bridge


def day_log(vault):
    return (vault.raw / f"{NOW:%Y-%m-%d}.md").read_text()


def outside_write(bridge, tmp_path):
    return {"hook_event_name": "PreToolUse", "session_id": bridge.session_id, "cwd": str(tmp_path),
            "tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "outside.txt")}}


async def test_instant_answer_never_reaches_the_model(jarvis, bridge, vault):
    r = await jarvis.submit("Jarvis, what time is it?", "mac")
    assert r == Reply(say_time(NOW), False) and bridge.sent == []
    assert "what time is it" in day_log(vault).lower()


async def test_small_request_round_trip_is_logged(jarvis, bridge, vault):
    t = asyncio.create_task(jarvis.submit("capital of Australia", "mac")); await bridge.got("capital of Australia")
    bridge.emit(turn("Canberra.")); assert await t == Reply("Canberra.", False)
    assert day_log(vault).rstrip().endswith("capital of Australia → Canberra.")


async def test_requests_are_served_in_arrival_order(jarvis, bridge):
    a = asyncio.create_task(jarvis.submit("first", "mac")); b = asyncio.create_task(jarvis.submit("second", "phone"))
    await bridge.got("first"); assert bridge.sent == ["first"]
    bridge.emit(turn("one")); await a; await bridge.got("second"); bridge.emit(turn("two")); assert (await b).say == "two"


async def test_question_ends_the_reply_with_loop(jarvis, bridge):
    t = asyncio.create_task(jarvis.submit("fix it", "phone")); await bridge.got("fix it")
    bridge.emit(turn("Which repo?")); assert await t == Reply("Which repo?", True)


async def test_gate_ask_yes_and_no(jarvis, bridge, tmp_path):
    t = asyncio.create_task(jarvis.submit("make a file", "mac")); await bridge.got("make a file")
    call = outside_write(bridge, tmp_path)
    h = asyncio.create_task(jarvis.hook(call))           # held inside PreToolUse (amendment, Task 10)
    r = await t; assert r.loop and r.say.endswith("Yes or no?")
    t2 = asyncio.create_task(jarvis.submit("yes", "mac")); assert (await h)["verdict"] == "allow"
    bridge.emit(turn("Done.")); assert (await t2).say == "Done."
    h = asyncio.create_task(jarvis.hook(call | {"hook_event_name": "PermissionRequest"}))
    await until(lambda: jarvis.asks.pending())
    assert jarvis.answer("no", channel="mac") and await h == {"verdict": "deny", "reason": "Febriel said no."}


async def test_no_answer_in_time_is_no(jarvis_fast_timeouts, bridge, tmp_path):
    asyncio.create_task(jarvis_fast_timeouts.submit("make a file", "mac")); await bridge.got("make a file")
    call = outside_write(bridge, tmp_path) | {"hook_event_name": "PermissionRequest"}
    assert await jarvis_fast_timeouts.hook(call) == {"verdict": "deny", "reason": "No answer in time, so no."}
    assert jarvis_fast_timeouts.asks.history() == [("1", ANY, False)] and not jarvis_fast_timeouts.asks.pending()


async def test_yes_with_nothing_pending_is_an_ordinary_request(jarvis, bridge):
    asyncio.create_task(jarvis.submit("yes", "mac")); await bridge.got("yes")


async def test_never_and_memory_rule_deny_without_asking(jarvis, bridge):
    asyncio.create_task(jarvis.submit("do it", "mac")); await bridge.got("do it")
    base = {"hook_event_name": "PreToolUse", "session_id": bridge.session_id, "cwd": "/tmp"}
    assert (await jarvis.hook(base | {"tool_name": "Bash", "tool_input": {"command": "sudo ls"}}))["verdict"] == "deny"
    d = await jarvis.hook(base | {"tool_name": "Agent", "tool_input": {"subagent_type": "coder"}})
    assert d == {"verdict": "deny", "reason": "Call triage before dispatching a worker."}


async def test_another_session_has_no_request_to_dispatch_for(jarvis, bridge):
    d = await jarvis.hook({"hook_event_name": "PreToolUse", "session_id": "other", "cwd": "/tmp",
                           "tool_name": "Agent", "tool_input": {"subagent_type": "researcher"}})
    assert d == {"verdict": "deny", "reason": "Call triage before dispatching a worker."}


async def test_vault_reads_and_writes_show_in_memory(jarvis, bridge, vault):
    events = jarvis.subscribe(); await anext(events)
    (vault.root / "wiki").mkdir(); (vault.root / "wiki" / "a.md").write_text("x")
    base = {"hook_event_name": "PreToolUse", "session_id": "other", "cwd": str(vault.root)}
    for name, path in (("Read", "wiki/a.md"), ("Edit", "wiki/a.md"), ("Write", "wiki/b.md")):
        assert (await jarvis.hook(base | {"tool_name": name, "tool_input": {"file_path": str(vault.root / path)}}))["verdict"] == "allow"
    seen = [await anext(events) for _ in range(3)]
    assert [(e["op"], e["path"]) for e in seen] == [("r", "wiki/a.md"), ("~", "wiki/a.md"), ("+", "wiki/b.md")]


async def test_vault_missing_refuses_everything(jarvis_no_vault, bridge):
    r = await jarvis_no_vault.submit("what time is it", "mac")
    assert r.say.startswith("The vault is missing") and bridge.sent == []


async def test_cancel(jarvis, bridge):
    t = asyncio.create_task(jarvis.submit("long thing", "mac")); await bridge.got("long thing")
    await jarvis.submit("never mind", "mac"); assert bridge.interrupted and jarvis.state is State.IDLE
    bridge.emit(turn("", is_error=True, cancelled=True)); assert (await t).say == "Cancelled."


async def test_status_repeat_and_mute(jarvis, bridge):
    assert (await jarvis.submit("status", "mac")).say == "Nothing is running."
    assert (await jarvis.submit("repeat that", "phone")).say == "Nothing to repeat."
    assert (await jarvis.submit("stop listening", "mac")).say == "Mic off."
    assert (await jarvis.submit("say that again", "mac")).say == "Mic off."
    t = asyncio.create_task(jarvis.submit("fix the export bug", "mac")); await bridge.got("fix the export bug")
    assert (await jarvis.submit("what are you working on", "phone")).say == "Working on fix the export bug."


async def test_limit_reached_keeps_the_request(jarvis, bridge, clock):
    bridge.emit({"kind": "limits", "status": "reached", "weekly": 1.0, "resets_at": clock() + 3600})
    r = await jarvis.submit("fix it", "mac"); assert r.say.startswith("I've hit the subscription limit") and bridge.sent == []
    clock.advance(3601); await jarvis.tick(); await bridge.got("fix it")


async def test_reset_waits_for_background_workers(jarvis, bridge, clock, vault, scribe_runs):
    t = asyncio.create_task(jarvis.submit("fix the export bug", "mac")); await bridge.got("fix the export bug")
    for e in (tool("Agent", {"subagent_type": "triage"}), tool_result(GOOD_VERDICT), agent_start("t1", "coder", background=True), turn("Started.")):
        bridge.emit(e)
    await t; clock.advance(1801); await jarvis.tick(); assert bridge.resets == 0
    bridge.emit(agent_done("t1", "completed", "ok")); bridge.emit(turn("The export is fixed."))
    clock.advance(1801); await jarvis.tick(); assert bridge.resets == 1
    note = next(vault.raw.glob("*-fix-export-bug.md")).name
    # the task note goes to scribe at once; the idle sweep then distils the grown day log (amendment, Task 10)
    assert "task [[" in day_log(vault) and [p.name for _, p in scribe_runs] == [note, f"{NOW:%Y-%m-%d}.md"]


async def test_subscribers_get_a_snapshot_first(jarvis):
    first = await anext(jarvis.subscribe()); assert first["type"] == "snapshot" and first["health"]["mic"] == "off"


async def test_yes_to_a_background_workers_question_answers_at_once(jarvis, bridge, tmp_path):
    t = asyncio.create_task(jarvis.submit("fix the export bug", "mac")); await bridge.got("fix the export bug")
    for e in (tool("Agent", {"subagent_type": "triage"}), tool_result(GOOD_VERDICT), agent_start("t1", "coder", background=True), turn("Started.")):
        bridge.emit(e)
    await t
    h = asyncio.create_task(jarvis.hook(outside_write(bridge, tmp_path) | {"agent_id": "t1"}))
    await until(lambda: jarvis.asks.pending())
    assert jarvis.asks.pending()[0].request_id == "1"
    assert (await asyncio.wait_for(jarvis.submit("yes", "mac"), 1)).say == "Okay."
    assert (await h)["verdict"] == "allow"


class QuietBridge(FakeBridge):
    async def start(self):  # the real CLI sends its first init only with the first message
        pass


async def test_brain_is_online_once_the_child_runs(make):
    j = await make(bridge=QuietBridge)
    assert (await anext(j.subscribe()))["health"]["brain"] == "online"


async def test_a_background_triage_lets_the_front_door_dispatch_later(jarvis, bridge, vault):
    """Task 15 row 3: triage ran in the background, and the worker was dispatched in a turn nobody prompted."""
    (vault.root / "wiki").mkdir(); (vault.root / "wiki" / "poetry.md").write_text("x")
    t = asyncio.create_task(jarvis.submit("write a poem", "phone")); await bridge.got("write a poem")
    for e in (tool("Agent", {"subagent_type": "triage"}, id="tuT"), agent_start("t0", "triage", background=True, tool_use_id="tuT"),
              turn("Triage is running.")):
        bridge.emit(e)
    await t
    bridge.emit(agent_done("t0", "completed", GOOD_VERDICT, tool_use_id="tuT"))
    bridge.emit(tool("Read", {"file_path": str(vault.root / "wiki" / "poetry.md")}, id="r1"))
    bridge.emit(tool_result("x", tool_use_id="r1"))
    d = await jarvis.hook({"hook_event_name": "PreToolUse", "session_id": bridge.session_id, "cwd": "/tmp",
                           "tool_name": "Agent", "tool_input": {"subagent_type": "coder"}})
    assert d["verdict"] == "allow"
    events = jarvis.subscribe(); await anext(events)
    for e in (agent_start("t1", "coder", background=True, tool_use_id="tuC"), turn("The worker has started."),
              agent_done("t1", "completed", "Wrote the poem.", tool_use_id="tuC"), turn("The poem is written.")):
        bridge.emit(e)
    replies = []
    while len(replies) < 2:
        if (e := await anext(events))["type"] == "reply":
            replies.append(e)
    assert [r["channel"] for r in replies] == ["phone", "phone"]
    text = next(vault.raw.glob("*-fix-export-bug.md")).read_text()
    assert "coder (" in text and "Wrote the poem." in text and "[[poetry]]" in text


async def test_with_two_questions_open_a_bare_yes_is_not_guessed(jarvis, bridge, tmp_path):
    t = asyncio.create_task(jarvis.submit("make two files", "mac")); await bridge.got("make two files")
    call = outside_write(bridge, tmp_path)
    h1 = asyncio.create_task(jarvis.hook(call)); h2 = asyncio.create_task(jarvis.hook(call))
    await until(lambda: len(jarvis.asks.pending()) == 2)
    r = await jarvis.submit("yes", "mac")
    assert r.say.startswith("2 questions are waiting") and not h1.done() and not h2.done()
    for a in jarvis.asks.pending():
        jarvis.answer("no", ask_id=a.id)
    await asyncio.gather(h1, h2); t.cancel()



# ── Plan 2 review pass, daemon findings ──

def task_with_background_worker(bridge, task="t1"):
    for e in (tool("Agent", {"subagent_type": "triage"}), tool_result(GOOD_VERDICT),
              agent_start(task, "coder", background=True, tool_use_id=f"tu-{task}"), turn("Started.")):
        bridge.emit(e)


async def test_a_child_that_dies_mid_turn_ends_that_request_and_frees_the_queue(jarvis, bridge):   # finding 1
    a = asyncio.create_task(jarvis.submit("long thing", "mac")); b = asyncio.create_task(jarvis.submit("next", "mac"))
    await bridge.got("long thing")
    bridge.emit({"kind": "exited"})
    assert "stopped" in (await asyncio.wait_for(a, 1)).say
    await bridge.got("next")
    bridge.emit(turn("Next done.")); assert (await b).say == "Next done."


async def test_an_error_while_serving_is_logged_and_the_queue_goes_on(jarvis, bridge, vault, monkeypatch, caplog):  # 2
    def broken(ex):
        raise OSError("disk full")
    monkeypatch.setattr(vault, "log_exchange", broken)
    a = asyncio.create_task(jarvis.submit("first", "mac")); await bridge.got("first")
    bridge.emit(turn("one")); assert (await a).say == "one"
    monkeypatch.undo()
    b = asyncio.create_task(jarvis.submit("second", "mac")); await bridge.got("second")
    bridge.emit(turn("two")); assert (await b).say == "two"
    assert any("failed" in r.getMessage() and "first" not in r.getMessage() for r in caplog.records)


async def test_an_unprompted_turn_belongs_to_the_request_whose_worker_finished(jarvis, bridge):   # finding 3
    events = jarvis.subscribe(); await anext(events)
    a = asyncio.create_task(jarvis.submit("fix the export bug", "mac")); await bridge.got("fix the export bug")
    task_with_background_worker(bridge); await a
    bridge.emit(agent_done("t1", "completed", "Fixed.", tool_use_id="tu-t1"))
    bridge.emit({"kind": "turn_start"})                        # the front door starts announcing it
    b = asyncio.create_task(jarvis.submit("capital of Peru", "phone")); await asyncio.sleep(0.05)
    assert "capital of Peru" not in bridge.sent                # not sent into the middle of that turn
    bridge.emit(turn("The export is fixed."))
    await bridge.got("capital of Peru"); bridge.emit(turn("Lima.")); assert (await b).say == "Lima."
    replies = []
    while len(replies) < 3:
        if (e := await anext(events))["type"] == "reply":
            replies.append((e["text"], e["channel"]))
    assert ("The export is fixed.", "mac") in replies and ("Lima.", "phone") in replies


async def test_no_latest_open_request_guess_for_unowned_activity(jarvis, bridge):                # finding 3
    a = asyncio.create_task(jarvis.submit("fix the export bug", "mac")); await bridge.got("fix the export bug")
    task_with_background_worker(bridge); await a
    d = await jarvis.hook({"hook_event_name": "PreToolUse", "session_id": bridge.session_id, "cwd": "/tmp",
                           "tool_name": "Agent", "tool_input": {"subagent_type": "coder"}})
    assert d == {"verdict": "deny", "reason": "Call triage before dispatching a worker."}   # no turn of its own runs


async def test_reset_waits_for_a_running_turn_and_for_the_note(jarvis, bridge, clock, vault):      # finding 4
    a = asyncio.create_task(jarvis.submit("long thing", "mac")); await bridge.got("long thing")
    clock.advance(1801); await jarvis.tick(); assert bridge.resets == 0
    bridge.emit(turn("Done.")); await a
    b = asyncio.create_task(jarvis.submit("fix the export bug", "mac")); await bridge.got("fix the export bug")
    task_with_background_worker(bridge); await b
    bridge.emit(agent_done("t1", "completed", "Fixed.", tool_use_id="tu-t1"))       # the note waits for the announcement
    clock.advance(1801); await jarvis.tick(); assert bridge.resets == 0
    bridge.emit({"kind": "turn_start"}); bridge.emit(turn("The export is fixed."))
    assert next(vault.raw.glob("*-fix-export-bug.md")).exists()
    clock.advance(1801); await jarvis.tick(); assert bridge.resets == 1


async def test_a_restart_records_the_request_whose_worker_died(jarvis, bridge, vault):            # finding 5
    a = asyncio.create_task(jarvis.submit("fix the export bug", "mac")); await bridge.got("fix the export bug")
    task_with_background_worker(bridge); await a
    bridge.emit({"kind": "exited"})
    assert "Claude restarted" in next(vault.raw.glob("*-fix-export-bug.md")).read_text()


async def test_stopping_records_every_open_request(make, bridge_of, vault):                        # finding 5
    j = await make(); bridge = bridge_of(j)
    a = asyncio.create_task(j.submit("fix the export bug", "mac")); await bridge.got("fix the export bug")
    task_with_background_worker(bridge); await a
    b = asyncio.create_task(j.submit("still thinking", "mac")); await bridge.got("still thinking")
    await j.stop()
    assert "jarvisd stopped" in next(vault.raw.glob("*-fix-export-bug.md")).read_text()
    assert "still thinking" in day_log(vault) and (await asyncio.wait_for(b, 1)).say.startswith("Jarvis is stopping")


async def test_never_mind_stops_background_work_too(jarvis, bridge, vault):                        # finding 8
    a = asyncio.create_task(jarvis.submit("fix the export bug", "mac")); await bridge.got("fix the export bug")
    task_with_background_worker(bridge); await a
    assert (await jarvis.submit("never mind", "mac")).say == "Cancelled."
    assert bridge.restarted == 1 and "cancelled" in next(vault.raw.glob("*-fix-export-bug.md")).read_text()


async def test_the_request_that_hits_the_limit_runs_again_after_the_reset(jarvis, bridge, clock):  # finding 9
    t = asyncio.create_task(jarvis.submit("fix it", "mac")); await bridge.got("fix it")
    bridge.emit({"kind": "limits", "status": "reached", "weekly": 1.0, "resets_at": clock() + 3600})
    bridge.emit(turn("You've hit your limit", is_error=True))
    assert (await t).say.startswith("I've hit the subscription limit")
    clock.advance(3601); await jarvis.tick()
    await until(lambda: bridge.sent.count("fix it") == 2)


async def test_the_idle_sweep_waits_for_real_quiet_and_a_scribe_that_worked(make, clock, vault):   # finding 13
    procs = []

    class Proc:
        def __init__(self, code): self.code = code
        def poll(self): return self.code

    def run(v, p):
        procs.append(p); return Proc(1 if len(procs) == 1 else 0)
    j = await make(run_scribe=run)
    clock.advance(1300); await j.submit("what time is it", "mac")    # an instant answer is activity too
    await j.tick(); assert procs == []
    clock.advance(1300); j._limits["status"] = "reached"; await j.tick(); assert procs == []   # not while limited
    j._limits["status"] = "ok"; await j.tick(); await j.tick()
    assert len(procs) == 1                                                             # failed: not marked swept
    clock.advance(1300); await j.tick(); await j.tick()
    assert len(procs) == 2 and j.sweeper.due(clock(), 0, False) is None                # worked: marked



async def test_a_request_queued_behind_a_dying_turn_waits_for_the_child_to_come_back(jarvis, bridge):   # re-run, row 9
    a = asyncio.create_task(jarvis.submit("long thing", "mac")); b = asyncio.create_task(jarvis.submit("next", "mac"))
    await bridge.got("long thing")
    bridge.alive = False; bridge.emit({"kind": "exited"})               # dead; its supervisor resumes it in a second
    assert "stopped" in (await a).say
    await asyncio.sleep(0.05); assert "next" not in bridge.sent and not b.done()
    bridge.alive = True; await jarvis.tick()
    await bridge.got("next"); bridge.emit(turn("Done.")); assert (await b).say == "Done."


async def test_a_request_the_brain_cannot_take_is_still_recorded(jarvis, bridge, vault):
    bridge.alive = False; bridge.emit({"kind": "down", "reason": "claude keeps exiting"})
    assert (await asyncio.wait_for(jarvis.submit("capital of Peru", "mac"), 1)).say == "Claude isn't running, so I can't do that now."
    assert "capital of Peru" in day_log(vault)
