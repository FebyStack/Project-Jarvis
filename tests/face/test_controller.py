import asyncio
import json

import pytest

from jarvis import config
from jarvis.face import place
from jarvis.face.controller import Controller
from tests.face.events import agents, asking, face, front, hover, level, snapshot, state, worker


class FakeClient:
    def __init__(self):
        self.answers, self.stops = [], []
        self.q = asyncio.Queue()

    async def answer(self, reply, ask_id): self.answers.append((reply, ask_id))
    async def stop(self, agent_id): self.stops.append(agent_id)
    def push(self, event): self.q.put_nowait(event)

    async def events(self):
        while True:
            yield await self.q.get()


class Rig:
    def __init__(self, tmp_path):
        self.fake, self.clock, self.shown, self.stacks, self.played, self.hidden = FakeClient(), [1001.0], [], [], [], []
        self.ctl = Controller(self.fake, self.shown.append, lambda s, m: self.stacks.append((s, m)),
                              lambda: self.played.append(1), tmp_path, now=lambda: self.clock[0],
                              show_hidden=self.hidden.append)

    async def push(self, *events):
        for e in events:
            self.fake.push(e)
        for _ in range(5):
            await asyncio.sleep(0)


@pytest.fixture
async def rig(tmp_path):
    r = Rig(tmp_path)
    task = asyncio.create_task(r.ctl.run())
    yield r
    task.cancel()


async def test_events_become_a_circle_and_a_stack(rig):
    await rig.push(snapshot(worker()))
    assert len(rig.shown) == 1 and len(rig.stacks) == 1
    assert json.loads(rig.shown[0])["mode"] == "work"
    assert rig.stacks[0][0].cards[0].id == "t1"


async def test_an_unchanged_view_is_not_shown_again(rig):
    await rig.push(snapshot(worker()), agents(worker()), state("IDLE"))
    assert len(rig.shown) == 1 and len(rig.stacks) == 1


async def test_levels_are_capped_at_the_frame_rate(rig):
    await rig.push(snapshot(), state("LISTENING"))
    before, stacks = len(rig.shown), len(rig.stacks)
    for i in range(100):
        rig.clock[0] += 0.01
        await rig.push(level((i + 1) / 101))
    assert 1 < len(rig.shown) - before <= config.FACE_FPS
    assert len(rig.stacks) == stacks


async def test_the_timer_moves_once_a_second(rig):
    await rig.push(snapshot(worker(since=900.0)))
    rig.ctl.tick()
    assert len(rig.stacks) == 1
    rig.clock[0] += 61
    rig.ctl.tick()
    assert len(rig.stacks) == 2
    await rig.push(agents())
    n = len(rig.stacks)
    rig.ctl.tick()
    assert len(rig.stacks) == n


async def test_a_pop_ends_on_a_tick(rig):
    rig.clock[0] = 1003.5
    await rig.push(snapshot(worker()))
    assert rig.stacks[-1][0].cards[0].open
    rig.clock[0] += 1
    rig.ctl.tick()
    assert not rig.stacks[-1][0].cards[0].open


async def test_hover_opens_and_shows(rig):
    rig.clock[0] = 1100.0
    await rig.push(snapshot(worker()))
    assert not rig.stacks[-1][0].cards[0].open
    rig.ctl.hover("t1", True)
    assert rig.stacks[-1][0].cards[0].open
    rig.ctl.hover("ghost", True)
    assert len(rig.stacks) == 2


async def test_a_new_question_plays_the_sound_once(rig):
    await rig.push(snapshot(worker()))
    assert rig.played == []
    await rig.push(agents(asking()), agents(asking()))
    assert rig.played == [1]


async def test_hostile_text_reaches_the_bead_unchanged(rig):
    hostile = '");alert(1)//</script><img src=x onerror=y>'
    await rig.push(snapshot(worker("working", doing=hostile)))
    assert rig.stacks[-1][0].cards[0].doing == hostile


async def test_the_circle_payload_is_plain_ascii_json(rig):
    await rig.push(snapshot(worker(doing="é </script>")), state("THINKING"))
    assert all(s.isascii() for s in rig.shown)
    assert set(json.loads(rig.shown[-1])) == {"mode", "ring", "word", "level"}


async def test_answer_goes_to_the_question_on_the_card(rig):
    await rig.push(snapshot(asking()))
    await rig.ctl.answer("yes", "kt1")
    assert rig.fake.answers == [("yes", "kt1")]


async def test_stop_goes_to_the_agent_on_the_card(rig):
    await rig.push(snapshot(worker()))
    await rig.ctl.stop("t1")
    assert rig.fake.stops == ["t1"]


async def test_stop_on_the_jarvis_card_answers_no(rig):
    await rig.push(snapshot(front("needs_you", question="Run it?", ask_id="kj", ask_until=1060.0)))
    await rig.ctl.stop("jarvis")
    assert rig.fake.answers == [("no", "kj")] and rig.fake.stops == []


async def test_a_stale_click_does_nothing(rig):
    await rig.push(snapshot(asking(), worker(id="t2", state="done")))
    await rig.ctl.answer("yes", "gone")
    await rig.ctl.stop("gone")
    await rig.ctl.stop("t2")
    assert rig.fake.answers == [] and rig.fake.stops == []


async def test_a_reply_that_is_not_yes_no_always_is_dropped(rig):
    await rig.push(snapshot(asking()))
    await rig.ctl.answer("maybe", "kt1")
    await rig.ctl.answer(["yes"], "kt1")
    assert rig.fake.answers == []


@pytest.mark.parametrize("msg", [None, "x", 3, {"type": "eval"}, {"type": "answer", "reply": "yes", "ask_id": "kt1"},
                                 {"type": "stop", "agent": "t1"}, {"type": "moved", "x": "1", "y": 2},
                                 {"type": "moved", "x": True, "y": 2}, {"type": "moved", "x": 1},
                                 {"type": "moved", "x": float("nan"), "y": 2}])
async def test_anything_but_moved_from_the_page_is_dropped(rig, tmp_path, msg):
    await rig.push(snapshot(asking(), worker(id="t2")))
    await rig.ctl.on_message(msg)
    assert rig.fake.answers == [] and rig.fake.stops == []
    assert place.load(tmp_path) is None


async def test_moved_saves_the_place(rig, tmp_path):
    await rig.ctl.on_message({"type": "moved", "x": 10, "y": 20.5})
    assert place.load(tmp_path) == (10, 20.5)


async def test_leaving_a_bead_is_heard_even_while_its_card_is_hidden(rig):   # the final review's M7
    rig.clock[0] = 1100.0
    await rig.push(snapshot(worker(since=1.0)))
    rig.ctl.hover("t1", True)
    await rig.push(agents(worker(since=1.0), *[worker(id=f"n{i}", since=50.0 + i) for i in range(5)]))
    assert "t1" not in {c.id for c in rig.stacks[-1][0].cards}
    rig.ctl.hover("t1", False)
    await rig.push(agents(worker(since=1.0)))
    assert not rig.stacks[-1][0].cards[0].open


async def test_the_face_hides_and_shows_only_on_a_change(rig):   # Ctrl-Option-J
    await rig.push(snapshot(worker(), hidden=True), face(True), agents(worker()), face(False), face(False),
                   snapshot(worker()), face(True))
    assert rig.hidden == [True, False, True]


async def test_nothing_on_a_hidden_face_can_be_clicked(rig):
    await rig.push(snapshot(asking(), worker(id="t2", since=1.0), hidden=True))
    await rig.ctl.answer("yes", "kt1")
    await rig.ctl.stop("t1")
    await rig.ctl.stop("t2")
    rig.ctl.hover("t2", True)
    assert rig.fake.answers == rig.fake.stops == [] and not rig.stacks[-1][0].cards[1].open
    await rig.push(face(False))
    await rig.ctl.answer("yes", "kt1")
    assert rig.fake.answers == [("yes", "kt1")]
