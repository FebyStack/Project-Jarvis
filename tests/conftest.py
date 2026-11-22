"""Shared fixtures: a fake clock, a temporary vault and a `Jarvis` on a fake bridge (daemon and voice tests)."""
import asyncio
from datetime import datetime

import pytest

from jarvis.daemon.core import Jarvis
from jarvis.memory.vault import Vault

class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


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


class FakeSpeaker:
    """Records what the core asks of the speaker; tests call `on_start` / `on_done` to play the speaker's part."""
    def __init__(self):
        self.calls = []
        self.on_start = self.on_done = lambda: None

    def feed(self, delta):
        self.calls.append(("feed", delta))

    def say(self, text):
        self.calls.append(("say", text))

    def stop(self):
        self.calls.append(("stop",))

    def hold(self, on):
        self.calls.append(("hold", on))

    def cue(self):
        self.calls.append(("cue",))

    def hint(self, text):
        self.calls.append(("hint", text))

    async def warm(self, texts):
        self.calls.append(("warm", tuple(texts)))


def states(j):
    """From now on, the `voice` of every `state` event `j` publishes; call the result to read them."""
    q = asyncio.Queue(); j._subs.append(q)
    seen = []

    def read():
        while not q.empty():
            if (e := q.get_nowait())["type"] == "state":
                seen.append(e["voice"])
        return seen
    return read
