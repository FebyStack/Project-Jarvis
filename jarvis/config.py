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
# Folders holding the programs jarvisd and the hook run, or settings that make git run programs: writes there always
# ask. ~/.local/bin/claude is a symlink into ~/.local/share/claude; the venv's Python is Homebrew's.
RUN_PATH = (Path.home() / ".local" / "bin", Path.home() / ".local" / "share" / "claude", Path("/opt/homebrew"),
            Path("/usr/local"), Path.home() / ".config" / "git")

PORT = 8787
EXTRA_HOSTS: tuple[str, ...] = ()  # Host names the API also answers to; Plan 4 adds the tailnet name
ASK_TIMEOUT = {"mac": 60.0, "phone": 600.0}
HOOK_TIMEOUT = 660
RESET_IDLE_SECONDS = 1800
SWEEP_IDLE_SECONDS = 1200
SHUTDOWN_TIMEOUT = 3.0  # seconds the API waits for open requests on stop; launchd kills after 20

# Voice (plan 3)
SAMPLE_RATE = 16000
FRAME = 480  # 30 ms
END_SILENCE_SECONDS = 0.8
MAX_UTTERANCE_SECONDS = 15.0
MAX_HELD_SECONDS = 60.0
WAKE_SIMILARITY = 0.70
WAKE_STRICT = 0.80
WAKE_ALSO: frozenset[str] = frozenset()  # extra spellings of the name that always wake
WAKE_WORDS = 3  # the name must be among the first this many words
LISTEN_SECONDS = 8.0
TALK_KEYCODE = 61  # Right Option
TAP_SECONDS = 0.3
KEY_GRACE_SECONDS = 0.15
MIC_REOPEN_DELAY = 0.3
FIRST_CHUNK_CHARS = 60
STT_MODEL = "mlx-community/parakeet-tdt-0.6b-v2"
TTS_MODEL = "mlx-community/Kokoro-82M-bf16"
TTS_VOICE = "bm_daniel"
TTS_LANG = "b"

_FROM_ENV = {"HOME_DIR": ("JARVIS_HOME", DEFAULT_HOME_DIR), "VAULT": ("JARVIS_VAULT", DEFAULT_VAULT)}


def __getattr__(name: str) -> Path:
    if name == "DESKTOP_SKILLS":  # links to Febriel's desktop skills, rebuilt at each daemon start
        return __getattr__("HOME_DIR") / "desktop-skills"
    if name not in _FROM_ENV:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    var, default = _FROM_ENV[name]
    value = os.environ.get(var)
    return Path(value).expanduser() if value else default
