import asyncio
import json
import socket

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from jarvis.tui.app import Client, Hud, skills
from tests.tui.events import SNAPSHOT

QUEUE_WITH_NEEDS_YOU = {"type": "queue", "items": [
    {"id": "a", "title": "fix export bug", "status": "running"},
    {"id": "b", "title": "delete 14 files", "status": "needs_you", "question": "Delete 14 files? Yes or no?", "ask_id": "k1"}]}


class FakeClient:
    def __init__(self):
        self.asked, self.answers, self.cancelled = [], [], 0
        self.q = asyncio.Queue(); self.q.put_nowait(SNAPSHOT)

    async def ask(self, text): self.asked.append(text)
    async def answer(self, reply, ask_id): self.answers.append((reply, ask_id))
    async def cancel(self): self.cancelled += 1
    def push(self, event): self.q.put_nowait(event)

    async def events(self):
        while True:
            yield await self.q.get()


def screen_text(app):
    return "\n".join(s.text for s in app.screen._compositor.render_strips())


def make_skills(root):
    for name, desc in (("vault", "Read and tidy the vault."), ("system", "Check the Mac.")):
        (root / name).mkdir(parents=True)
        (root / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n\nBody.\n")
    return root


@pytest.fixture
def fake():
    return FakeClient()


@pytest.fixture
async def running(fake, tmp_path):
    app = Hud(fake, skills_dir=make_skills(tmp_path / "skills"), now=lambda: 1000.0)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        yield app, pilot


@pytest.fixture
def hud(running): return running[0]


@pytest.fixture
def pilot(running): return running[1]


async def test_fits_80_by_24_with_every_panel(hud):
    for wid in ("#header", "#voice", "#agents", "#queue", "#memory", "#ask", "#footer"):
        w = hud.query_one(wid); assert w.region.right <= 80 and w.region.bottom <= 24 and w.region.height >= 1
    text = screen_text(hud)
    for word in ("J . A . R . V . I . S .", "ONLINE", "VOICE", "IDLE", "AGENTS", "QUEUE", "MEMORY", "MIC ○ off", "PHONE ○ not linked", "LIMITS ● 33%"):
        assert word in text


async def test_typing_a_request(hud, pilot, fake):
    await pilot.click("#ask"); await pilot.press(*"hello", "enter")
    assert fake.asked == ["hello"] and hud.query_one("#ask").value == ""


async def test_answering_a_question_with_keys(hud, pilot, fake):
    fake.push(QUEUE_WITH_NEEDS_YOU); await pilot.pause(); assert "NEEDS YOU" in screen_text(hud)
    await pilot.press("y"); assert fake.answers == [("yes", "k1")]
    await pilot.click("#ask"); await pilot.press("y"); assert fake.answers == [("yes", "k1")]      # typing a "y" is not an answer


async def test_escape_cancels_and_slash_lists_skills(hud, pilot, fake):
    await pilot.press("escape"); assert fake.cancelled == 1
    await pilot.press("slash"); assert "vault" in screen_text(hud) and "system" in screen_text(hud)
    await pilot.press("enter"); assert fake.asked[-1].startswith("Use your ")


@pytest.mark.parametrize("event,first_line", [
    ({"type": "health", "brain": "online", "vault": "missing", "checklist": []}, "VAULT MISSING"),
    ({"type": "health", "brain": "limit", "vault": "ok", "checklist": []}, "LIMIT REACHED"),
    ({"type": "health", "brain": "online", "vault": "ok", "checklist": ["claude is not on PATH"]}, "FIRST RUN"),
    ({"type": "link", "state": "no daemon"}, "NO DAEMON")])
async def test_notices(hud, pilot, fake, event, first_line):
    fake.push(event); await pilot.pause(); assert first_line in screen_text(hud)


async def test_states_are_words_not_only_colour(hud, pilot, fake):
    fake.push({"type": "state", "voice": "THINKING", "muted": True}); await pilot.pause()
    assert "THINKING" in screen_text(hud) and "MIC ○ off" in screen_text(hud)


# Beyond the plan's list

async def test_keys_do_nothing_without_a_question(hud, pilot, fake):
    await pilot.press("y", "n", "a"); assert fake.answers == []


async def test_always_answers_the_oldest_question(hud, pilot, fake):
    fake.push(QUEUE_WITH_NEEDS_YOU); await pilot.pause(); await pilot.press("a")
    assert fake.answers == [("always", "k1")] and "Delete 14 files? Yes or no?" in screen_text(hud)


async def test_slash_in_a_typed_request_is_text(hud, pilot, fake):
    await pilot.click("#ask"); await pilot.press("a", "slash", "b", "enter"); assert fake.asked == ["a/b"]


async def test_notice_lines_are_exact(hud, pilot, fake):
    fake.push({"type": "health", "brain": "starting", "vault": "ok", "checklist": []}); await pilot.pause()
    assert "STARTING UP" in screen_text(hud)
    fake.push({"type": "health", "brain": "offline", "vault": "ok", "checklist": []}); await pilot.pause()
    assert "OFFLINE: no connection to Claude" in screen_text(hud)
    fake.push({"type": "health", "brain": "online", "vault": "ok", "checklist": ["claude is not on PATH"]}); await pilot.pause()
    assert "FIRST RUN: still to do" in screen_text(hud) and "claude is not on PATH" in screen_text(hud)
    fake.push({"type": "health", "brain": "online", "vault": "missing", "checklist": []}); await pilot.pause()
    assert "VAULT MISSING: Jarvis is refusing requests until the vault is back" in screen_text(hud)
    fake.push({"type": "link", "state": "no daemon"}); await pilot.pause()
    assert "NO DAEMON: start it with: jarvis daemon" in screen_text(hud)


async def test_limit_notice_names_the_reset_time(hud, pilot, fake):
    fake.push({"type": "limits", "status": "reached", "weekly": None, "resets_at": 1_763_400_000.0})
    fake.push({"type": "health", "brain": "limit", "vault": "ok", "checklist": []}); await pilot.pause()
    import time
    assert f"LIMIT REACHED: resumes at {time.strftime('%H:%M', time.localtime(1_763_400_000.0))}" in screen_text(hud)


async def test_panels_show_rows(hud, pilot, fake):
    fake.push(QUEUE_WITH_NEEDS_YOU)
    fake.push({"type": "agents", "items": [{"id": "c", "name": "coder", "model": "sonnet", "doing": "fixing export bug", "since": 748.0, "background": True}]})
    fake.push({"type": "heard", "text": "open the captions repo", "channel": "mac"})
    fake.push({"type": "reply", "text": "Opening it now.", "channel": "mac", "loop": False}); await pilot.pause()
    text = screen_text(hud)
    for word in ("▶ fix export bug", "? delete 14 files", "coder", "fixing export bug", "04:12", '"open the captions repo"', "Opening it now.", "r wiki/preferences.md"):
        assert word in text


def test_skills_reads_frontmatter(tmp_path):
    assert skills(make_skills(tmp_path)) == [("system", "Check the Mac."), ("vault", "Read and tidy the vault.")]
    assert skills(tmp_path / "absent") == []


# The real client

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


async def test_client_reports_no_daemon():
    events = Client("t", base=f"http://127.0.0.1:{free_port()}", retry=0.01).events()
    assert await anext(events) == {"type": "link", "state": "connecting"}
    assert await anext(events) == {"type": "link", "state": "no daemon"}
    await events.aclose()


async def test_client_speaks_the_api_with_the_token():
    seen = []

    async def post(request):
        seen.append((request.path, request.headers["Authorization"], await request.json() if request.can_read_body else None))
        return web.json_response({"say": "ok"})

    async def events(request):
        seen.append((request.path, request.headers["Authorization"], None))
        ws = web.WebSocketResponse(); await ws.prepare(request)
        await ws.send_str(json.dumps(SNAPSHOT)); await ws.close(); return ws

    app = web.Application()
    app.router.add_post("/ask", post); app.router.add_post("/answer", post); app.router.add_post("/cancel", post)
    app.router.add_get("/events", events)
    async with TestServer(app, host="127.0.0.1") as server:
        c = Client("tok", base=str(server.make_url("")).rstrip("/"), retry=0.01)
        await c.ask("hello"); await c.answer("yes", "k1"); await c.cancel()
        stream = c.events()
        assert [await anext(stream) for _ in range(3)] == [
            {"type": "link", "state": "connecting"}, SNAPSHOT, {"type": "link", "state": "no daemon"}]
        await stream.aclose(); await c.close()
    assert seen[:3] == [("/ask", "Bearer tok", {"text": "hello", "channel": "mac"}),
                        ("/answer", "Bearer tok", {"answer": "yes", "ask_id": "k1", "channel": "mac"}),
                        ("/cancel", "Bearer tok", None)]
    assert seen[3][:2] == ("/events", "Bearer tok")


async def test_client_survives_a_daemon_that_is_down():
    c = Client("t", base=f"http://127.0.0.1:{free_port()}")
    assert await c.ask("hello") is None; await c.answer("no", "k1"); await c.cancel(); await c.close()
