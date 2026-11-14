"""Every path, port and timing constant (plan 2, Global Constraints). Nothing else defines them.

HOME_DIR and VAULT are read from the environment on each access (module __getattr__),
so `JARVIS_HOME` / `JARVIS_VAULT` set after import still take effect. An empty value counts as unset.
"""
import os
from pathlib import Path

PROJECT = Path.home() / "Developer" / "Project Jarvis"
SETTINGS = PROJECT / ".claude" / "jarvis-settings.json"
DEFAULT_HOME_DIR = Path.home() / ".jarvis"
DEFAULT_VAULT = Path("/Users/febrielotud/Obsidian/Jarvis")

PORT = 8787
EXTRA_HOSTS: tuple[str, ...] = ()  # Host names the API also answers to; Plan 4 adds the tailnet name
ASK_TIMEOUT = {"mac": 60.0, "phone": 600.0}
HOOK_TIMEOUT = 660
RESET_IDLE_SECONDS = 1800
SWEEP_IDLE_SECONDS = 1200

_FROM_ENV = {"HOME_DIR": ("JARVIS_HOME", DEFAULT_HOME_DIR), "VAULT": ("JARVIS_VAULT", DEFAULT_VAULT)}


def __getattr__(name: str) -> Path:
    if name == "DESKTOP_SKILLS":  # links to Febriel's desktop skills, rebuilt at each daemon start
        return __getattr__("HOME_DIR") / "desktop-skills"
    if name not in _FROM_ENV:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    var, default = _FROM_ENV[name]
    value = os.environ.get(var)
    return Path(value).expanduser() if value else default
