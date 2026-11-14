import asyncio
import socket
import stat

import pytest
from aiohttp.test_utils import TestClient, TestServer, unused_port

from jarvis import config
from jarvis.daemon.core import Reply
from jarvis.remote.api import make_app, serve
from jarvis.remote.token import load_token

TOKEN = "t" * 43


class FakeJarvis:
    def __init__(self):
        self.reply, self.submitted, self.answers, self.cancelled, self._subs = Reply("ok", False), [], [], 0, []

    async def submit(self, text, channel):
        self.submitted.append((text, channel)); return self.reply

    def answer(self, reply, channel=None, ask_id=None):
        self.answers.append((reply, channel, ask_id)); return True

    async def cancel(self):
        self.cancelled += 1

    async def hook(self, payload):
        return {"verdict": "deny", "reason": payload.get("tool_name", "")}

    def health(self):
        return {"brain": "online", "vault": "ok", "mic": "off", "phone": "not linked", "awake": "n/a", "checklist": []}

    async def subscribe(self):
        q = asyncio.Queue(); self._subs.append(q)
        yield {"type": "snapshot"}
        while True:
            yield await q.get()

    def publish(self, ev):
        for q in self._subs:
            q.put_nowait(ev)


@pytest.fixture
def fake():
    return FakeJarvis()


async def _client(fake, monkeypatch, headers):
    port = unused_port(); monkeypatch.setattr(config, "PORT", port)
    c = TestClient(TestServer(make_app(fake, TOKEN), host="127.0.0.1", port=port), headers=headers)
    await c.start_server()
    return c


@pytest.fixture
async def client(fake, monkeypatch):
    c = await _client(fake, monkeypatch, {"Authorization": f"Bearer {TOKEN}"}); yield c; await c.close()


@pytest.fixture
async def client_no_auth(fake, monkeypatch):
    c = await _client(fake, monkeypatch, {}); yield c; await c.close()


async def test_every_route_needs_the_token(client_no_auth):
    for method, path in [("post", "/ask"), ("post", "/answer"), ("post", "/cancel"), ("post", "/hook"), ("get", "/health"), ("get", "/events")]:
        assert (await getattr(client_no_auth, method)(path)).status == 401
    assert (await client_no_auth.post("/ask", headers={"Authorization": "Bearer wrong"}, json={"text": "x"})).status == 401


async def test_a_foreign_host_name_is_refused_before_the_token(client):
    assert (await client.get("/health", headers={"Host": "jarvis.example.com"})).status == 403
    assert (await client.get("/health", headers={"Host": f"localhost:{config.PORT}"})).status == 200


async def test_answer_cannot_be_reached_by_a_plain_get(client):
    assert (await client.get("/answer")).status == 405


async def test_ask_contract(client, fake):
    fake.reply = Reply("Which repo?", True)
    assert await (await client.post("/ask", json={"text": "fix it"})).json() == {"say": "Which repo?", "loop": "yes"}
    assert fake.submitted == [("fix it", "phone")]
    fake.reply = Reply("Done.", False)
    assert await (await client.post("/ask", json={"text": "go", "channel": "mac"})).json() == {"say": "Done."}
    for bad in (b"nope", b'{"text": "  "}', b"{}", b'{"text": "x", "channel": "tv"}', b"[]"):
        assert (await client.post("/ask", data=bad)).status == 400


async def test_answer_cancel_hook_health(client, fake):
    assert await (await client.post("/answer", json={"answer": "yes", "ask_id": "k1", "channel": "mac"})).json() == {"answered": True}
    assert fake.answers == [("yes", "mac", "k1")] and (await client.post("/answer", json={"answer": "sure"})).status == 400
    assert await (await client.post("/cancel")).json() == {"ok": True} and fake.cancelled == 1
    assert await (await client.post("/hook", json={"tool_name": "Bash"})).json() == {"verdict": "deny", "reason": "Bash"}
    assert (await (await client.get("/health")).json())["mic"] == "off"


async def test_events_stream_starts_with_the_snapshot(client, fake):
    ws = await client.ws_connect("/events"); assert (await ws.receive_json())["type"] == "snapshot"
    fake.publish({"type": "heard", "text": "hi", "channel": "mac"}); assert (await ws.receive_json())["type"] == "heard"
    await ws.close()


def test_token_file_is_private(tmp_path):
    t = load_token(tmp_path / "j"); assert load_token(tmp_path / "j") == t and len(t) >= 40
    assert stat.S_IMODE((tmp_path / "j" / "token").stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "j").stat().st_mode) == 0o700


@pytest.fixture
def unused_port_taken(monkeypatch):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen()
    monkeypatch.setattr(config, "PORT", s.getsockname()[1])
    yield
    s.close()


async def test_binds_loopback_only_and_refuses_a_taken_port(unused_port_taken):
    with pytest.raises(RuntimeError, match="is taken"): await serve(make_app(FakeJarvis(), "t"))
