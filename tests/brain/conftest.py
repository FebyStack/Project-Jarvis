from pathlib import Path

import pytest

from jarvis.brain.gate import GateConfig
from jarvis.brain.trusted import TrustedList

HOME = Path.home()


@pytest.fixture
def cfg(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    return GateConfig(
        free_write=[HOME / "Developer", vault],
        protected=[HOME / "Developer" / "Project Jarvis" / ".claude", HOME / ".jarvis"],
        trusted=TrustedList(tmp_path / "trusted.txt"),
        read_tools=set(),
    )


@pytest.fixture
def cfg_for(tmp_path):
    def make(free_dir):
        return GateConfig(free_write=[free_dir], protected=[],
                          trusted=TrustedList(tmp_path / "trusted-for.txt"), read_tools=set())
    return make
