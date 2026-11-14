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
