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
