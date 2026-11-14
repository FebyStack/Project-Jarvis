import asyncio
import plistlib
import socket
from pathlib import Path

import pytest

from jarvis.cli import checklist, main

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_checklist_names_what_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_VAULT", str(tmp_path / "nope")); monkeypatch.setenv("JARVIS_HOME", str(tmp_path / "j"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    lines = checklist(slow=False)
    assert any("ANTHROPIC_API_KEY" in l for l in lines) and any("vault" in l.lower() for l in lines)
    assert any("token" in l for l in lines)


def test_checklist_is_empty_when_ready(tmp_path, monkeypatch):
    (tmp_path / "v").mkdir(); (tmp_path / "j").mkdir(mode=0o700)
    (tmp_path / "j" / "token").write_text("x"); (tmp_path / "j" / "token").chmod(0o600)
    monkeypatch.setenv("JARVIS_VAULT", str(tmp_path / "v")); monkeypatch.setenv("JARVIS_HOME", str(tmp_path / "j"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("shutil.which", lambda name, path=None: "/opt/homebrew/bin/claude")
    assert checklist(slow=False) == []


def test_ask_without_a_daemon_says_how_to_start_it(capsys, free_port, monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_HOME", str(tmp_path / "j"))
    monkeypatch.setattr("jarvis.config.PORT", free_port)
    assert main(["ask", "hello"]) == 1 and "jarvis daemon" in capsys.readouterr().err


def test_daemon_refuses_with_an_api_key(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k"); assert main(["daemon"]) == 1
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_daemon_refuses_a_taken_port(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False); monkeypatch.setenv("JARVIS_HOME", str(tmp_path / "j"))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); s.listen(); monkeypatch.setattr("jarvis.config.PORT", s.getsockname()[1])
        assert main(["daemon"]) == 1 and "is taken" in capsys.readouterr().err


def test_plist_runs_the_daemon_with_no_secrets():
    p = plistlib.loads((ROOT / "launchd" / "com.febriel.jarvisd.plist").read_bytes())
    assert p["ProgramArguments"] == ["/Users/febrielotud/Developer/Project Jarvis/.venv/bin/jarvis", "daemon"]
    assert p["RunAtLoad"] is True and "EnvironmentVariables" not in p


def test_daemon_links_the_desktop_skills_before_starting(monkeypatch, tmp_path):
    import jarvis.cli as cli
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("JARVIS_HOME", str(tmp_path / "j")); monkeypatch.setenv("JARVIS_VAULT", str(tmp_path / "v"))
    monkeypatch.setattr(cli, "_port_taken", lambda: False)
    linked = []
    monkeypatch.setattr("jarvis.brain.desktop_skills.link", lambda dest: linked.append(dest) or ["a"])

    async def no_run(vault, token):
        assert linked, "skills must be linked before the brain starts"
    monkeypatch.setattr(cli, "_run", no_run)
    assert cli.main(["daemon"]) == 0 and linked == [tmp_path / "j" / "desktop-skills"]


# ── Plan 2 review pass, daemon finding 14 ──

def test_daemon_without_claude_says_what_to_do(monkeypatch, capsys, tmp_path):
    import jarvis.cli as cli
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False); monkeypatch.delenv("JARVIS_CLAUDE_BIN", raising=False)
    monkeypatch.setenv("JARVIS_HOME", str(tmp_path / "j"))
    monkeypatch.setattr(cli, "_port_taken", lambda: False)
    monkeypatch.setattr("shutil.which", lambda name, path=None: None)
    assert cli.main(["daemon"]) == 1
    err = capsys.readouterr().err
    assert "claude is not on PATH" in err and "jarvis doctor" in err and "Traceback" not in err


async def test_stopping_with_a_request_in_flight_is_quick(monkeypatch, tmp_path):
    import os, signal, time
    import aiohttp
    from aiohttp.test_utils import unused_port
    import jarvis.cli as cli
    from jarvis.memory.vault import Vault
    from jarvis.remote.token import load_token
    from tests.daemon.test_core import FakeBridge
    monkeypatch.setenv("JARVIS_HOME", str(tmp_path / "j")); monkeypatch.setenv("JARVIS_VAULT", str(tmp_path / "v"))
    (tmp_path / "v").mkdir()
    port = unused_port(); monkeypatch.setattr("jarvis.config.PORT", port)
    monkeypatch.setattr("jarvis.brain.bridge.Bridge", FakeBridge)                 # never the real claude
    token = load_token(tmp_path / "j")
    run = asyncio.create_task(cli._run(Vault(tmp_path / "v"), token))
    async with aiohttp.ClientSession(headers={"Authorization": f"Bearer {token}"}) as s:
        for _ in range(200):
            try:
                await (await s.get(f"http://127.0.0.1:{port}/health")).release(); break
            except aiohttp.ClientConnectionError:
                await asyncio.sleep(0.02)
        ask = asyncio.create_task(s.post(f"http://127.0.0.1:{port}/ask", json={"text": "long thing", "channel": "mac"}))
        await asyncio.sleep(0.2)
        started = time.monotonic(); os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(run, 10)
        assert time.monotonic() - started < 5                                      # launchd waits 20 s, then kills
        assert (await (await asyncio.wait_for(ask, 2)).json())["say"].startswith("Jarvis is stopping")
