"""Environment for a jarvisd-style child: no inherited Claude/Anthropic variables (spike-only helper)."""
import os

KEEP = ("HOME", "USER", "LOGNAME", "SHELL", "TERM", "LANG", "TMPDIR")
PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + os.path.expanduser("~/.local/bin")


def clean_env() -> dict:
    env = {k: os.environ[k] for k in KEEP if k in os.environ}
    env["PATH"] = PATH
    assert not any(k.startswith(("ANTHROPIC_", "CLAUDE")) for k in env)
    return env
