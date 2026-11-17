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
