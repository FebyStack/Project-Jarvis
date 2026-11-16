import asyncio
from types import SimpleNamespace

import numpy as np
import pytest

from jarvis.voice import speaker as speaker_mod
from jarvis.voice.speaker import VoiceSpeaker


class FakeSynth:
    """Returns len(text) samples and records its texts; a text in `block` waits for `gate`."""
    def __init__(self):
        self.texts, self.fail, self.block, self.gate = [], False, set(), asyncio.Event()

    async def __call__(self, text):
        self.texts.append(text)
        if text in self.block:
            await self.gate.wait()
        if self.fail:
            raise RuntimeError("synthesis failed")
        return np.zeros(len(text), dtype=np.float32)


class FakePlayer:
    """Busy from play() until its done, which comes a loop turn later; start fires inside play()."""
    def __init__(self):
        self.played, self.stops, self.busy = [], 0, False
        self.on_start = self.on_done = lambda: None

    def play(self, pcm):
        self.played.append(len(pcm))
        self.busy = True
        self.on_start()
        asyncio.get_running_loop().call_soon(self._done)

    def _done(self):
        if self.busy:
            self.busy = False
            self.on_done()

    def stop(self):
        self.stops += 1
        self.busy = False


class FakeFallback:
    def __init__(self):
        self.texts, self.fail = [], False

    async def __call__(self, text):
        self.texts.append(text)
        if self.fail:
            raise FileNotFoundError("say")


async def idle(sp):
    for _ in range(50):
        await asyncio.sleep(0)


@pytest.fixture
async def rig():
    synth, player, fallback, events = FakeSynth(), FakePlayer(), FakeFallback(), []
    sp = VoiceSpeaker(synth, player, fallback)
    sp.on_start, sp.on_done = lambda: events.append("start"), lambda: events.append("done")
    yield SimpleNamespace(sp=sp, synth=synth, player=player, fallback=fallback, events=events)
    sp._task.cancel()


async def test_chunks_are_spoken_in_order_as_they_complete(rig):
    sp, synth = rig.sp, rig.synth
    sp.feed("Right. I'll che"); sp.feed("ck now. "); await idle(sp)
    assert synth.texts == ["Right.", "I'll check now."]
    assert rig.player.played == [6, 15] and rig.events == ["start", "done"]  # done: speech ran out, for now


async def test_say_after_feed_speaks_only_the_tail(rig):
    sp, synth = rig.sp, rig.synth
    sp.feed("Fine. And y"); sp.say("Fine. And you?"); await idle(sp)
    assert synth.texts == ["Fine.", "And you?"]
    assert rig.events == ["start", "done"]


async def test_text_before_a_tool_call_is_not_spoken_twice(rig):
    sp, synth = rig.sp, rig.synth
    sp.feed("Let me check. "); sp.feed("Done."); sp.say("Done."); await idle(sp)  # the turn's text is its last message only
    assert synth.texts == ["Let me check.", "Done."]


async def test_say_alone_speaks_it_all(rig):
    rig.sp.say("Mic off."); await idle(rig.sp)
    assert rig.synth.texts == ["Mic off."] and rig.events == ["start", "done"]


async def test_a_different_say_after_feed_speaks_both(rig):
    rig.sp.feed("Deleting. "); rig.sp.say("Delete 14 files?"); await idle(rig.sp)
    assert rig.synth.texts == ["Deleting.", "Delete 14 files?"]


async def test_the_next_reply_starts_afresh(rig):
    rig.sp.feed("One. "); rig.sp.say("One."); rig.sp.say("One."); await idle(rig.sp)
    assert rig.synth.texts == ["One.", "One."]


async def test_stop_forgets_the_rest(rig):
    sp, synth = rig.sp, rig.synth
    synth.block = {"Two."}
    sp.feed("One. Two. Three. "); await idle(sp)
    assert rig.player.played == [4] and synth.texts == ["One.", "Two."]  # "Two." is being synthesized
    sp.stop(); await idle(sp)
    synth.gate.set(); await idle(sp)
    assert rig.player.stops == 1 and rig.player.played == [4] and synth.texts == ["One.", "Two."]
    assert rig.events == ["start", "done"]
    sp.say("Next."); await idle(sp)
    assert rig.player.played == [4, 5] and rig.events == ["start", "done", "start", "done"]


async def test_hold_starts_nothing_until_released(rig):
    rig.sp.hold(True); rig.sp.say("Hi."); await idle(rig.sp)
    assert rig.player.played == [] and rig.events == []
    rig.sp.hold(False); await idle(rig.sp)
    assert rig.player.played == [3] and rig.events == ["start", "done"]


async def test_synthesis_that_fails_falls_back_to_say(rig):
    rig.synth.fail = True
    rig.sp.say("Hi."); await idle(rig.sp)
    assert rig.fallback.texts == ["Hi."] and rig.player.played == [] and rig.events == ["start", "done"]


async def test_when_both_fail_done_still_fires(rig):
    rig.synth.fail = rig.fallback.fail = True
    rig.sp.say("Hi."); await idle(rig.sp)
    assert rig.events[-1] == "done" and not rig.sp._task.done()


async def test_a_player_that_will_not_play_falls_back_to_say(rig):
    def no_device(pcm):
        raise OSError("no output device")
    rig.player.play = no_device
    rig.sp.say("Hi."); await idle(rig.sp)
    assert rig.fallback.texts == ["Hi."] and rig.events == ["start", "done"]


async def test_nothing_speakable_is_done_without_a_start(rig):
    rig.sp.say("```"); await idle(rig.sp)
    assert rig.events == ["done"] and rig.synth.texts == []


async def test_cue_plays_a_tone(rig):
    rig.sp.cue(); await idle(rig.sp)
    assert rig.player.played == [1920] and rig.synth.texts == []  # 0.08 s at 24 kHz
    assert rig.events == []  # a tone is not speech: the core's state is left alone


async def test_a_late_start_from_before_a_stop_is_ignored(rig):
    def playing(pcm):  # mid-run: start and done come later, from its thread
        rig.player.played.append(len(pcm))
        rig.player.busy = True
    rig.player.play = playing
    rig.sp.say("Hi."); await idle(rig.sp)
    rig.player.on_start()  # fired on the audio thread just before the stop; reaches the loop after it
    rig.sp.stop(); await idle(rig.sp)
    assert rig.events == ["done"]


async def test_say_daniel_is_killed_by_stop(rig, monkeypatch):
    proc = SimpleNamespace(args=None, killed=False, done=asyncio.Event())
    proc.wait = proc.done.wait
    proc.kill = lambda: setattr(proc, "killed", True)

    async def exec_(*args):
        proc.args = args
        return proc
    monkeypatch.setattr(speaker_mod.asyncio, "create_subprocess_exec", exec_)
    sp = VoiceSpeaker(rig.synth, FakePlayer())
    rig.synth.fail = True
    sp.say("Hi."); await idle(sp)
    assert proc.args == ("say", "-v", "Daniel", "Hi.") and not proc.killed
    sp.stop(); await idle(sp)
    assert proc.killed
    sp._task.cancel()
