from datetime import datetime

import pytest

from jarvis.memory.scribe import Sweeper, scribe_argv
from jarvis.memory.vault import Exchange, Vault

AT = datetime(2026, 11, 14, 20, 14)


@pytest.fixture
def vault(tmp_path):
    (tmp_path / "vault").mkdir()
    return Vault(tmp_path / "vault")


def test_sweeper_waits_for_quiet_and_growth(tmp_path, vault):
    s = Sweeper(vault, tmp_path); log = vault.log_exchange(Exchange(AT, "mac", "q", "a", []))
    assert s.due(now=1000, last_request=0, busy=False) is None            # under 1200 s
    assert s.due(now=1300, last_request=0, busy=True) is None
    assert s.due(now=1300, last_request=0, busy=False) == log
    s.mark(log); assert s.due(now=9999, last_request=0, busy=False) is None
    vault.log_exchange(Exchange(AT, "mac", "q2", "a2", [])); assert s.due(now=9999, last_request=0, busy=False) == log


def test_scribe_argv(vault):
    a = scribe_argv(vault, vault.root / "raw" / "2026-11-14-2014-fix-export-bug.md")
    assert a[a.index("--agent") + 1] == "scribe" and a[a.index("--model") + 1] == "haiku"
    assert "--input-format" not in a and a[-1].startswith("Distil this note into wiki/: ")


def test_run_starts_scribe_detached_with_the_scrubbed_environment(tmp_path, monkeypatch, vault):
    """Review finding 15: scribe.run had no test. A stand-in claude records how it was started."""
    import json, sys, time
    from jarvis.memory import scribe
    out = tmp_path / "started.json"
    script, fake = tmp_path / "fake.py", tmp_path / "claude"
    script.write_text("import json, os, sys\n"
                      f"json.dump({{'argv': sys.argv[1:], 'cwd': os.getcwd(), 'env': sorted(os.environ)}}, open({str(out)!r}, 'w'))\n")
    fake.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n'); fake.chmod(0o755)   # the venv path has a space
    monkeypatch.setenv("JARVIS_CLAUDE_BIN", str(fake)); monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://x")
    proc = scribe.run(vault, vault.root / "raw" / "note.md")
    for _ in range(300):
        if proc.poll() is not None and out.exists():
            break
        time.sleep(0.01)
    got = json.loads(out.read_text())
    assert got["argv"][got["argv"].index("--agent") + 1] == "scribe" and got["argv"][-1].endswith("raw/note.md")
    assert not any(k.startswith(("ANTHROPIC", "CLAUDE")) for k in got["env"]) and proc.returncode == 0
