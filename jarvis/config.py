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
WAKE_ALSO: frozenset[str] = frozenset({"javi", "javier"})  # how Febriel is heard (Task 14, 2026-11-17); never in the negatives
WAKE_WORDS = 3  # the name must be among the first this many words
LISTEN_SECONDS = 8.0
TALK_KEYCODE = 61  # Right Option
TAP_SECONDS = 0.3
KEY_GRACE_SECONDS = 0.8  # Febriel's é/ñ/⌥← chords: 87–603 ms after the key (25 measured, 2026-11-18); taps end sooner, on key up
HOLD_SECONDS = 1.5  # a mac request with nothing said by then gets a holding line (2026-11-22)
FRONT_MODEL, FRONT_EFFORT = "sonnet", "low"  # the front door; Haiku started its replies about twice as slowly (1.4–2.0 s against 0.75–0.9 s to the first token, 2026-11-22)
MIC_REOPEN_DELAY = 0.3
WARM_SECONDS = 120.0  # unused this long, the voice makes a line nobody hears: swapped out, it delayed a reply 3-11 s (2026-11-23)
FIRST_CHUNK_CHARS = 60
STT_MODEL = "mlx-community/parakeet-tdt-0.6b-v2"
TTS_MODEL = "mlx-community/Kokoro-82M-bf16"
TTS_VOICE = "bm_george"  # by measurement the clearest, least husky British male preset (2026-11-18); bm_daniel before
TTS_LANG = "b"

# On screen (plan 4)
CARD_MAX = 5
CARD_LINGER_SECONDS = 8.0
CIRCLE_SIZE = 160
FACE_FPS = 30
FACE_EASE_SECONDS = 2.0
NAME_SIMILARITY = 0.7
RED_ACTIVE = "#FF3B30"
RED = "#C2241B"
RED_DIM = "#6B1512"
CARD_POP_SECONDS = 4.0
CARD_OPEN_WIDTH = 300
CARD_LINE_HEIGHT = 36
CARD_GAP = 10
TETHER_RIM = 68
TETHER_CLEAR = 88
TETHER_STEP = 46
FACE_MOVE_SECONDS = 0.45

_FROM_ENV = {"HOME_DIR": ("JARVIS_HOME", DEFAULT_HOME_DIR), "VAULT": ("JARVIS_VAULT", DEFAULT_VAULT)}


def __getattr__(name: str) -> Path:
    if name == "DESKTOP_SKILLS":  # links to Febriel's desktop skills, rebuilt at each daemon start
        return __getattr__("HOME_DIR") / "desktop-skills"
    if name not in _FROM_ENV:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    var, default = _FROM_ENV[name]
    value = os.environ.get(var)
    return Path(value).expanduser() if value else default
