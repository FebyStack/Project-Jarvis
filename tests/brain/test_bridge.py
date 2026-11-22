import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from jarvis.brain import bridge
from jarvis.brain.bridge import Bridge, parse
from jarvis.brain.env import claude_argv, clean_env

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return [json.loads(line) for line in (FIXTURES / name).read_text().splitlines() if line.strip()]


async def until(pred, timeout=5.0):
    end = asyncio.get_running_loop().time() + timeout
    while not pred():
        if asyncio.get_running_loop().time() > end:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.01)


class FakeClaude:
    """Handle on tests/brain/fake_claude.py: settings in, starts and stdin out (all under JARVIS_HOME)."""

    def __init__(self, home: Path):
        self.home = home

    def _set(self, key, value):
        f = self.home / "fake-config.json"
        cfg = json.loads(f.read_text()) if f.exists() else {}
        f.write_text(json.dumps(cfg | {key: value}))

    api_key_source = property(None, lambda self, v: self._set("api_key_source", v))
    turn_api_key_source = property(None, lambda self, v: self._set("turn_api_key_source", v))
    exit_after_init = property(None, lambda self, v: self._set("exit_after_init", v))
    stubborn = property(None, lambda self, v: self._set("stubborn", v))

    def _starts(self):
        f = self.home / "fake-starts.jsonl"
        return [json.loads(line) for line in f.read_text().splitlines()] if f.exists() else []

    @property
    def starts(self):
        return len(self._starts())

    @property
    def last_argv(self):
        s = self._starts()
        return s[-1]["argv"] if s else []

    @property
    def pid(self):
        return self._starts()[-1]["pid"]

    @property
    def stdin(self):
        f = self.home / "fake-stdin.jsonl"
        return [json.loads(line) for line in f.read_text().splitlines()] if f.exists() else []

    def kill(self):
        os.kill(self.pid, 9)


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    wrapper = tmp_path / "claude"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{Path(__file__).parent / "fake_claude.py"}" "$@"\n')
    wrapper.chmod(0o755)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("JARVIS_CLAUDE_BIN", str(wrapper))
    monkeypatch.setenv("JARVIS_HOME", str(tmp_path))
    return FakeClaude(tmp_path)


async def no_wait(_seconds):
    await asyncio.sleep(0)


# --- environment and argv ---------------------------------------------------------------------------------------

def test_env_is_scrubbed(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_SIMPLE", "1"); monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://x")
    env = clean_env()
    assert not any(k.startswith(("CLAUDE", "ANTHROPIC")) for k in env) and env["PATH"].startswith("/opt/homebrew/bin:")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    with pytest.raises(RuntimeError): clean_env()


def test_env_keeps_only_the_named_variables(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("SECRET_TOKEN", "s"); monkeypatch.setenv("JARVIS_HOME", "/tmp/jh"); monkeypatch.setenv("JARVIS_VAULT", "")
    env = clean_env()
    from jarvis.brain.env import GIT_SAFE
    assert set(env) <= {"HOME", "USER", "LOGNAME", "SHELL", "TERM", "LANG", "TMPDIR", "PATH", "JARVIS_HOME", "JARVIS_VAULT",
                        *GIT_SAFE}
    assert env["JARVIS_HOME"] == "/tmp/jh" and "JARVIS_VAULT" not in env
    assert env["PATH"].endswith(os.path.expanduser("~/.local/bin"))


def test_argv_is_exact(monkeypatch):
    monkeypatch.delenv("JARVIS_CLAUDE_BIN", raising=False)
    a = claude_argv("MAP")
    assert a[:6] == ["claude", "-p", "--agent", "jarvis", "--model", "sonnet"] and a[a.index("--effort") + 1] == "low"
    assert "--bare" not in a and a[a.index("--setting-sources") + 1] == "project"
    assert a[a.index("--settings") + 1].endswith(".claude/jarvis-settings.json")
    assert "--strict-mcp-config" in a and "--mcp-config" not in a and a[a.index("--append-system-prompt") + 1] == "MAP"
    assert claude_argv("MAP", resume="abc")[-2:] == ["--resume", "abc"]
    assert "--resume" not in a and claude_argv("M", agent="scribe")[3] == "scribe"


def test_argv_binary_from_env(monkeypatch):
    monkeypatch.setenv("JARVIS_CLAUDE_BIN", "/x/fake")
    assert claude_argv("MAP")[0] == "/x/fake"


# --- parsing ----------------------------------------------------------------------------------------------------

def events(name):
    return [e for line in fixture(name) for e in parse(line)]


def test_parse_fixture_lines():
    kinds = [e["kind"] for line in fixture("stream.jsonl") for e in parse(line)]
    assert {"init", "tool", "tool_result", "agent_start", "agent_progress", "agent_done", "limits", "turn"} <= set(kinds)
    tool = next(e for line in fixture("stream.jsonl") for e in parse(line) if e["kind"] == "tool")
    assert tool["name"] == "Agent" and tool["input"]["subagent_type"] and tool["model"].startswith("claude-")
    lim = next(e for line in fixture("stream.jsonl") for e in parse(line) if e["kind"] == "limits")
    assert lim["status"] in ("ok", "near", "reached") and 0 <= lim["weekly"] <= 1
    assert "".join(e["text"] for line in fixture("partial.jsonl") for e in parse(line) if e["kind"] == "delta").strip()
    assert parse({"type": "system", "subtype": "hook_started"}) == [] and parse({}) == []


def test_parse_fields_match_the_table():
    ev = events("stream.jsonl")
    by = lambda kind: [e for e in ev if e["kind"] == kind]  # noqa: E731
    assert by("init") == [{"kind": "init", "session_id": "da88ba51-7ffe-4b0a-84f3-20d1c839e2ee",
                           "api_key_source": "none", "mcp_servers": []}]
    agent, bash = by("tool")
    assert agent == {"kind": "tool", "id": "toolu_01QuSF1bXyNZGyhL8uUa8WaJ", "name": "Agent", "input": agent["input"],
                     "model": "claude-sonnet-5-5", "parent": None}
    assert bash["name"] == "Bash" and bash["parent"] == "toolu_0187TGeSwKYt2TmgxLYSogjZ" and bash["model"] == "claude-haiku-5-5"
    sub_result, front_result = by("tool_result")
    assert sub_result == {"kind": "tool_result", "tool_use_id": "toolu_014yfEs1e52E5FoP8YvcoaXo",
                          "text": "(Bash completed with no output)", "parent": "toolu_0187TGeSwKYt2TmgxLYSogjZ",
                          "is_error": False}
    assert front_result["parent"] is None and "tier: sonnet" in front_result["text"]
    assert by("agent_start") == [{"kind": "agent_start", "task_id": "a62c8189d5f7535d2",
                                  "tool_use_id": "toolu_01QuSF1bXyNZGyhL8uUa8WaJ", "agent": "triage",
                                  "description": "Triage task", "background": False}]
    assert by("agent_progress") == [{"kind": "agent_progress", "task_id": "a1a53915dc07a2a4f",
                                     "description": "Running Sleep for 60 seconds using Python"}]
    assert {"kind": "agent_done", "task_id": "a62c8189d5f7535d2", "tool_use_id": "toolu_01QuSF1bXyNZGyhL8uUa8WaJ",
            "status": "completed", "summary": "tier: sonnet — spike override (running as Opus 5.5)"} in by("agent_done")
    assert by("limits") == [{"kind": "limits", "status": "near", "weekly": 0.33, "resets_at": 1795129200}]
    (turn,) = by("turn")
    assert turn["is_error"] is False and turn["session_id"] == "32a879ab-71b1-48fe-9749-08a6a2ff3209"
    assert turn["text"].startswith("- **triage:**") and turn["cancelled"] is False


def test_background_bash_is_not_an_agent_start():
    bash_start = next(line for line in fixture("stream.jsonl") if line.get("task_type") == "local_bash")
    assert parse(bash_start) == []


def test_partial_deltas_are_only_the_front_door_text():
    deltas = [e for e in events("partial.jsonl") if e["kind"] == "delta"]
    assert all(set(e) == {"kind", "text"} for e in deltas)
    final = next(e for e in events("partial.jsonl") if e["kind"] == "turn")["text"]
    assert "".join(e["text"] for e in deltas) == final
    sub = {"type": "stream_event", "parent_tool_use_id": "toolu_x",
           "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "inside a worker"}}}
    assert parse(sub) == []


def test_interrupt_lines():
    ev = events("interrupt.jsonl")
    assert [e["kind"] for e in ev] == ["turn", "init", "turn"]
    assert ev[0]["is_error"] is True and ev[0]["text"] == ""


def test_limit_statuses():
    def status(s):
        return parse({"type": "rate_limit_event", "rate_limit_info": {"status": s}})[0]
    assert status("allowed")["status"] == "ok" and status("allowed_warning")["status"] == "near"
    assert status("rejected")["status"] == "reached" and status("allowed")["weekly"] is None


@pytest.mark.parametrize("line", [
    None, 5, "text", [], {"type": None}, {"type": "assistant"}, {"type": "assistant", "message": None},
    {"type": "assistant", "message": {"content": "x"}}, {"type": "assistant", "message": {"content": [None, 3, "a"]}},
    {"type": "user", "message": {"content": [None, {"type": "tool_result", "content": [None, 1]}]}},
    {"type": "rate_limit_event", "rate_limit_info": []}, {"type": "rate_limit_event", "rate_limit_info": {"unifiedWindows": 3}},
    {"type": "stream_event", "event": "x"}, {"type": "stream_event", "event": {"type": "content_block_delta", "delta": 1}},
    {"type": "system", "subtype": "task_started"}, {"type": "result", "result": 5}, {"type": "control_response"},
])
def test_parse_never_raises_and_ignores_the_unknown(line):
    out = parse(line)
    assert isinstance(out, list) and all(isinstance(e, dict) and "kind" in e for e in out)


def test_unknown_real_lines_are_ignored():
    known = {"init", "delta", "tool", "tool_result", "agent_start", "agent_progress", "agent_done", "limits", "turn"}
    for name in ("stream.jsonl", "partial.jsonl", "interrupt.jsonl"):
        for line in fixture(name):
            if line["type"] in ("control_response",) or line.get("subtype") in (
                    "status", "thinking_tokens", "task_updated", "background_tasks_changed"):
                assert parse(line) == [], line
            assert {e["kind"] for e in parse(line)} <= known


# --- the child process ------------------------------------------------------------------------------------------

async def test_bridge_round_trip_and_restart(fake_claude):
    events = []; b = Bridge(events.append, lambda: "MAP", sleep=no_wait); await b.start(); await b.send("hi")
    await until(lambda: any(e["kind"] == "turn" for e in events))
    assert b.session_id == "fake-session"
    fake_claude.kill(); await until(lambda: b.alive and fake_claude.last_argv[-2:] == ["--resume", "fake-session"])
    await b.stop()


async def test_send_writes_a_user_message_and_later_inits_are_not_starts(fake_claude):
    events = []; b = Bridge(events.append, lambda: "MAP", sleep=no_wait); await b.start()
    await b.send("one"); await b.send("two")
    await until(lambda: sum(e["kind"] == "turn" for e in events) == 2)
    assert fake_claude.stdin == [{"type": "user", "message": {"role": "user", "content": t}} for t in ("one", "two")]
    assert [e["kind"] for e in events] == ["init", "turn_start", "turn_start", "turn", "turn_start", "turn"]
    assert [e["text"] for e in events if e["kind"] == "turn"] == ["one", "two"]
    assert fake_claude.last_argv[-2:] == ["--append-system-prompt", "MAP"] and fake_claude.starts == 1
    await b.stop()


async def test_api_key_source_stops_the_brain(fake_claude):
    fake_claude.api_key_source = "ANTHROPIC_API_KEY"
    events = []; b = Bridge(events.append, lambda: "MAP", sleep=no_wait); await b.start()
    await until(lambda: any(e == {"kind": "down", "reason": "api key in use"} for e in events)); assert not b.alive
    assert not any(e["kind"] == "init" for e in events)
    await asyncio.sleep(0.2); assert fake_claude.starts == 1
    await b.stop()


async def test_api_key_source_is_checked_on_every_turn(fake_claude):
    fake_claude.turn_api_key_source = "ANTHROPIC_API_KEY"
    events = []; b = Bridge(events.append, lambda: "MAP", sleep=no_wait); await b.start(); await b.send("hi")
    await until(lambda: any(e["kind"] == "down" for e in events))
    assert events[-1] == {"kind": "down", "reason": "api key in use"} and not b.alive
    assert not any(e["kind"] == "turn" for e in events) and fake_claude.starts == 1
    await b.stop()


async def test_restart_waits_one_second_and_gives_up_after_three_a_minute(fake_claude):
    fake_claude.exit_after_init = True
    waits = []

    async def sleep(seconds):
        waits.append(seconds); await asyncio.sleep(0)

    events = []; b = Bridge(events.append, lambda: "MAP", clock=lambda: 100.0, sleep=sleep); await b.start()
    await until(lambda: any(e["kind"] == "down" for e in events))
    assert waits == [1.0, 1.0, 1.0] and fake_claude.starts == 4 and not b.alive
    assert [e for e in events if e["kind"] == "down"] == [{"kind": "down", "reason": "claude keeps exiting"}]
    assert fake_claude.last_argv[-2:] == ["--resume", "fake-session"]
    await b.stop()


async def test_restarts_spread_over_minutes_keep_going(fake_claude):
    fake_claude.exit_after_init = True
    now = [0.0]

    async def sleep(seconds):
        now[0] += 30; await asyncio.sleep(0)

    events = []; b = Bridge(events.append, lambda: "MAP", clock=lambda: now[0], sleep=sleep); await b.start()
    await until(lambda: fake_claude.starts >= 7)
    await b.stop()
    assert not any(e["kind"] == "down" for e in events)


async def test_interrupt_writes_the_control_request_and_marks_the_turn_cancelled(fake_claude):
    events = []; b = Bridge(events.append, lambda: "MAP", sleep=no_wait); await b.start()
    await b.interrupt()
    await until(lambda: any(e["kind"] == "turn" for e in events))
    req = fake_claude.stdin[0]
    assert req["type"] == "control_request" and req["request"] == {"subtype": "interrupt"} and req["request_id"]
    await b.send("again"); await until(lambda: sum(e["kind"] == "turn" for e in events) == 2)
    assert [e["cancelled"] for e in events if e["kind"] == "turn"] == [True, False]
    assert b.alive and fake_claude.starts == 1
    await b.stop()


async def test_reset_starts_fresh_with_a_new_memory_map(fake_claude):
    maps = iter(["MAP1", "MAP2"])
    events = []; b = Bridge(events.append, lambda: next(maps), sleep=no_wait); await b.start()
    await until(lambda: b.session_id == "fake-session")
    await b.reset()
    await until(lambda: fake_claude.starts == 2 and b.alive)
    assert fake_claude.last_argv[-2:] == ["--append-system-prompt", "MAP2"] and "--resume" not in fake_claude.last_argv
    await b.stop()


async def test_stop_leaves_no_child_behind(fake_claude):
    events = []; b = Bridge(events.append, lambda: "MAP", sleep=no_wait); await b.start()
    await until(lambda: b.session_id is not None)
    pid = fake_claude.pid
    await b.stop()
    assert not b.alive
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    await asyncio.sleep(0.2); assert fake_claude.starts == 1 and not any(e["kind"] == "down" for e in events)


def gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


async def test_stop_kills_a_child_that_will_not_exit_and_its_group(fake_claude, monkeypatch):
    monkeypatch.setattr(bridge, "STOP_GRACE", 0.2)
    fake_claude.stubborn = True
    b = Bridge(lambda e: None, lambda: "MAP", sleep=no_wait); await b.start()
    await until(lambda: b.session_id is not None)
    pid, grandchild = fake_claude.pid, int((fake_claude.home / "fake-grandchild").read_text())
    await asyncio.wait_for(b.stop(), 5)  # the grandchild holds stdout open: only a group kill lets wait() return
    assert gone(pid) and not b.alive
    await until(lambda: gone(grandchild))


# ── Plan 2 review pass ──

async def test_a_child_that_dies_is_reported_before_it_is_resumed(fake_claude):          # daemon finding 1
    events = []; b = Bridge(events.append, lambda: "MAP"); await b.start()
    await until(lambda: fake_claude.starts == 1)
    fake_claude.kill()
    await until(lambda: {"kind": "exited"} in events and b.alive and fake_claude.starts == 2)
    await b.stop()


async def test_an_error_in_the_listener_does_not_stop_the_reader(fake_claude):           # daemon finding 2
    seen = []

    def listener(ev):
        seen.append(ev)
        if ev["kind"] == "turn" and len([e for e in seen if e["kind"] == "turn"]) == 1:
            raise RuntimeError("boom")
    b = Bridge(listener, lambda: "MAP"); await b.start()
    await b.send("one"); await b.send("two")
    await until(lambda: [e["text"] for e in seen if e["kind"] == "turn"] == ["one", "two"])
    await b.stop()


async def test_every_turn_start_is_reported(fake_claude):
    events = []; b = Bridge(events.append, lambda: "MAP"); await b.start()
    await b.send("one"); await b.send("two")
    await until(lambda: [e["kind"] for e in events if e["kind"] in ("turn_start", "turn")].count("turn") == 2)
    kinds = [e["kind"] for e in events if e["kind"] in ("init", "turn_start", "turn")]
    assert kinds == ["init", "turn_start", "turn_start", "turn", "turn_start", "turn"]       # the start init, then two turns
    await b.stop()


def test_tool_results_say_when_they_failed():
    line = {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t", "content": "no such file",
                                                     "is_error": True}]}}
    assert parse(line)[0]["is_error"] is True
