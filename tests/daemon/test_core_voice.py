import asyncio

from jarvis.daemon.instant import say_time
from jarvis.daemon.state import State
from tests.conftest import NOW, FakeSpeaker, states, until
from tests.daemon.events import turn


def outside_write(bridge, tmp_path):
    return {"hook_event_name": "PreToolUse", "session_id": bridge.session_id, "cwd": str(tmp_path),
            "tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "outside.txt")}}


async def test_a_streamed_reply_is_fed_then_finished(make, bridge_of):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    t = asyncio.create_task(j.submit("how are you", "mac")); await b.got("how are you")
    b.emit({"kind": "delta", "text": "Fine. "}); b.emit(turn("Fine.")); await t
    assert sp.calls == [("feed", "Fine. "), ("say", "Fine.")]


async def test_phone_replies_are_not_spoken(make, bridge_of):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j); seen = states(j)
    t = asyncio.create_task(j.submit("capital of Peru", "phone")); await b.got("capital of Peru")
    b.emit({"kind": "delta", "text": "Lima."}); b.emit(turn("Lima.")); await t
    assert sp.calls == [] and j.state is State.IDLE and seen() == []


async def test_instant_answers_and_questions_are_spoken(make, bridge_of, tmp_path):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    await j.submit("what time is it", "mac"); assert sp.calls[-1] == ("say", say_time(NOW))
    t = asyncio.create_task(j.submit("make a file", "mac")); await b.got("make a file")
    h = asyncio.create_task(j.hook(outside_write(b, tmp_path)))
    r = await t; assert r.loop and sp.calls[-1] == ("say", r.say)
    j.answer("no", channel="mac"); await h


async def test_the_state_follows_one_spoken_exchange(make, bridge_of):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j); seen = states(j)
    assert j.wake(); j.heard("capital of Australia"); await b.got("capital of Australia")
    sp.on_start(); b.emit(turn("Canberra.")); await until(lambda: ("say", "Canberra.") in sp.calls)
    sp.on_done()
    assert seen() == ["LISTENING", "THINKING", "SPEAKING", "IDLE"]   # a plain answer: the name is needed again


async def test_only_a_reply_that_asks_opens_the_follow_up_window(make, bridge_of):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    t = asyncio.create_task(j.submit("remind me", "mac")); await b.got("remind me")
    b.emit(turn("For when?")); await t
    sp.on_start(); sp.on_done(); assert j.state is State.FOLLOW_UP
    t = asyncio.create_task(j.submit("at five", "mac")); await b.got("at five")
    b.emit(turn("Done.")); await t
    sp.on_start(); sp.on_done(); assert j.state is State.IDLE


async def test_speech_that_runs_out_mid_turn_goes_back_to_thinking(make, bridge_of):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    t = asyncio.create_task(j.submit("check the build", "mac")); await b.got("check the build")
    b.emit({"kind": "delta", "text": "Let me check. "}); sp.on_start(); assert j.state is State.SPEAKING
    sp.on_done(); assert j.state is State.THINKING
    b.emit(turn("All green.")); await t


async def test_cancelled_is_said_once(make, bridge_of):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    t = asyncio.create_task(j.submit("write a poem", "mac")); await b.got("write a poem")
    j.wake(key=True); j.heard("never mind"); await until(lambda: ("say", "Cancelled.") in sp.calls)
    b.emit(turn("", cancelled=True)); await t
    assert ("stop",) in sp.calls and sp.calls.count(("say", "Cancelled.")) == 1


async def test_without_a_speaker_nothing_sticks(make, bridge_of):
    j = await make(); b = bridge_of(j)
    t = asyncio.create_task(j.submit("capital of Peru", "mac")); await b.got("capital of Peru")
    assert j.state is State.THINKING
    b.emit(turn("Lima.")); await t; assert j.state is State.IDLE


async def test_the_key_stops_speech_and_listens(make):
    j = await make(speaker=(sp := FakeSpeaker()))
    await j.submit("what time is it", "mac"); sp.on_start(); assert j.state is State.SPEAKING
    sp.calls.clear()
    assert j.wake(key=True) and sp.calls == [("stop",), ("hold", True)] and j.state is State.LISTENING


async def test_jarvis_does_not_talk_over_a_listening_mic(make, bridge_of):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    j.wake(); b.emit({"kind": "turn_start"}); b.emit(turn("The export is fixed."))
    assert sp.calls == [("hold", True), ("say", "The export is fixed.")] and j.state is State.LISTENING
    j.heard("thanks Jarvis"); assert sp.calls[-1] == ("hold", False)
    await b.got("thanks Jarvis")


async def test_a_workers_announcement_that_asks_opens_the_follow_up_window(make, bridge_of):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    b.emit({"kind": "turn_start"}); b.emit(turn("Is the Desktop one the file to delete?"))
    await until(lambda: ("say", "Is the Desktop one the file to delete?") in sp.calls)
    sp.on_start(); sp.on_done(); assert j.state is State.FOLLOW_UP


async def test_an_empty_hearing_gives_up_quietly(make, vault):
    j = await make(speaker=FakeSpeaker()); events = j.subscribe(); await anext(events)
    j.wake(); j.heard("")
    assert j.state is State.IDLE and not list(vault.raw.glob("*.md"))
    seen = []
    while not (q := j._subs[0]).empty():
        seen.append(q.get_nowait()["type"])
    assert "heard" not in seen and j._last_heard == ""


async def test_listening_times_out_through_tick(make, clock):
    j = await make(); j.wake(); seen = states(j)
    clock.advance(8); await j.tick()
    assert j.state is State.IDLE and seen() == ["IDLE"]


async def test_the_tone_only_when_asked(make):
    j = await make(speaker=(sp := FakeSpeaker()))
    j.wake(); assert ("cue",) not in sp.calls
    j.cue(); assert sp.calls[-1] == ("cue",)
    (await make()).cue()                                       # no speaker: nothing to do, nothing breaks


async def test_level_and_mic_reach_subscribers(make):
    j = await make(); events = j.subscribe(); await anext(events)
    j.level(0.4); e = await anext(events); assert (e["type"], e["rms"]) == ("level", 0.4)
    assert j.health()["mic"] == "off"
    j.set_mic("on"); e = await anext(events); assert (e["type"], e["mic"]) == ("health", "on")
    assert j.health()["mic"] == "on"


async def test_a_typed_request_shows_thinking(make, bridge_of):
    j = await make(); b = bridge_of(j); seen = states(j)
    asyncio.create_task(j.submit("capital of Peru", "mac")); await b.got("capital of Peru")
    assert seen()[0] == "THINKING"


async def test_a_request_parked_by_the_limit_does_not_keep_jarvis_thinking(make, bridge_of, clock):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    b.emit({"kind": "limits", "status": "reached", "weekly": 1.0, "resets_at": clock() + 3600})
    r = await j.submit("fix it", "mac"); assert sp.calls[-1] == ("say", r.say)
    sp.on_start(); sp.on_done(); assert j.state is State.IDLE    # its wait may be hours: the name must work


async def test_a_spoken_question_opens_the_follow_up_window_so_yes_needs_no_name(make, bridge_of, tmp_path):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    t = asyncio.create_task(j.submit("make a file", "mac")); await b.got("make a file")
    h = asyncio.create_task(j.hook(outside_write(b, tmp_path)))
    r = await t; assert r.loop and sp.calls[-1] == ("say", r.say)
    sp.on_start(); sp.on_done(); assert j.state is State.FOLLOW_UP   # the turn still runs, but the question waits on you
    j.speech_started(); assert j.state is State.LISTENING
    j.heard("yes"); assert (await asyncio.wait_for(h, 1))["verdict"] == "allow"
    b.emit(turn("Done.")); await until(lambda: ("say", "Done.") in sp.calls)


def test_hint_for_names_what_jarvis_is_doing():
    from jarvis.daemon.core import hint_for
    assert hint_for("WebSearch", "") == hint_for("WebFetch", "") == hint_for("Agent", "researcher") == "Looking that up."
    assert hint_for("Agent", "triage") == hint_for("Task", "coder") == "On it."
    assert hint_for("Bash", "") == hint_for("", "") == "One moment."


def web_search(bridge):
    return {"hook_event_name": "PreToolUse", "session_id": bridge.session_id, "cwd": "/tmp",
            "tool_name": "WebSearch", "tool_input": {"query": "Tokyo weather this week"}}


async def test_a_slow_request_gets_one_holding_line(make, bridge_of, monkeypatch):
    monkeypatch.setattr("jarvis.config.HOLD_SECONDS", 0.01)
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    t = asyncio.create_task(j.submit("look up the weather in Tokyo", "mac")); await b.got("look up the weather in Tokyo")
    await j.hook(web_search(b)); await asyncio.sleep(0.05)
    assert [c for c in sp.calls if c[0] == "hint"] == [("hint", "Looking that up.")]
    b.emit(turn("Cool and dry.")); await t


async def test_no_holding_line_once_the_reply_has_started(make, bridge_of, monkeypatch):
    monkeypatch.setattr("jarvis.config.HOLD_SECONDS", 0.01)
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    t = asyncio.create_task(j.submit("capital of Peru", "mac")); await b.got("capital of Peru")
    b.emit({"kind": "delta", "text": "Lima."}); await asyncio.sleep(0.05)
    b.emit(turn("Lima.")); await t
    assert not [c for c in sp.calls if c[0] == "hint"]


async def test_no_holding_line_for_the_phone(make, bridge_of, monkeypatch):
    monkeypatch.setattr("jarvis.config.HOLD_SECONDS", 0.01)
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    t = asyncio.create_task(j.submit("capital of Peru", "phone")); await b.got("capital of Peru")
    await asyncio.sleep(0.05); b.emit(turn("Lima.")); await t
    assert sp.calls == []


async def test_no_holding_line_after_a_cancel(make, bridge_of, monkeypatch):
    monkeypatch.setattr("jarvis.config.HOLD_SECONDS", 0.01)
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    t = asyncio.create_task(j.submit("look up the weather in Tokyo", "mac")); await b.got("look up the weather in Tokyo")
    await j.submit("never mind", "mac"); await asyncio.sleep(0.05)
    assert not [c for c in sp.calls if c[0] == "hint"]
    b.emit(turn("", cancelled=True)); await t


async def test_the_talk_key_holds_the_speaker_until_it_engages_or_lets_go(make):
    j = await make(speaker=(sp := FakeSpeaker()))
    j.key(True); assert sp.calls[-1] == ("hold", True)
    j.key(False); assert sp.calls[-1] == ("hold", False)


async def test_a_workers_tool_does_not_word_the_holding_line(make, bridge_of, monkeypatch):
    monkeypatch.setattr("jarvis.config.HOLD_SECONDS", 0.05)
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    t = asyncio.create_task(j.submit("fix the export bug", "mac")); await b.got("fix the export bug")
    base = {"hook_event_name": "PreToolUse", "session_id": b.session_id, "cwd": "/tmp"}
    await j.hook(base | {"tool_name": "Agent", "tool_input": {"subagent_type": "triage"}})
    await j.hook(base | {"agent_id": "triage-1", "tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}})
    await asyncio.sleep(0.1)
    assert [c for c in sp.calls if c[0] == "hint"] == [("hint", "On it.")]
    b.emit(turn("Fixed.")); await t


async def test_the_holding_lines_are_made_ahead(make):
    j = await make(speaker=(sp := FakeSpeaker()))
    await j.warm_hints()
    assert sp.calls == [("warm", ("Looking that up.", "On it.", "One moment."))]


async def test_a_late_done_from_speech_the_key_stopped_keeps_listening(make, bridge_of):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    await j.submit("what time is it", "mac"); sp.on_start()
    j.key(True); j.wake(key=True); sp.on_done()   # the stopped reply's done reaches the core after it listens
    assert j.state is State.LISTENING
    j.heard("open Mail"); await b.got("open Mail")


async def no_network(*args):
    return False


async def test_offline_a_second_spoken_request_is_answered_at_once(make, bridge_of, monkeypatch):
    from jarvis.daemon.core import OFFLINE
    monkeypatch.setattr("jarvis.daemon.core.reachable", no_network)
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    t = asyncio.create_task(j.submit("fix it", "mac")); await b.got("fix it")
    b.emit(turn("", is_error=True)); assert (await t).say == OFFLINE
    sp.on_start(); sp.on_done(); assert j.state is State.IDLE
    assert (await asyncio.wait_for(j.submit("open Mail", "mac"), 1)).say == OFFLINE
    sp.on_start(); sp.on_done(); assert j.state is State.IDLE    # not THINKING until the network is back


async def test_health_says_offline_before_any_turn_fails(make, monkeypatch, clock):
    net = {"up": False}

    async def reachable(*args):
        return net["up"]
    monkeypatch.setattr("jarvis.daemon.core.reachable", reachable)
    j = await make()
    await j.tick(); assert j.health()["brain"] == "offline"
    net["up"] = True; clock.advance(30); await j.tick(); assert j.health()["brain"] == "online"


async def test_hinting_is_the_speakers(make):
    j = await make(speaker=(sp := FakeSpeaker()))
    assert not j.hinting
    sp.hinting = True; assert j.hinting
    assert not (await make()).hinting   # no speaker: nothing plays
