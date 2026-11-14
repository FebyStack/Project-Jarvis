"""The scrubbed environment and the exact argv for the `claude` child (subscription login only, never --bare)."""
import os

from jarvis import config

KEEP = ("HOME", "USER", "LOGNAME", "SHELL", "TERM", "LANG", "TMPDIR")
# Git settings above any config file: a found bare repository is refused (a planted one could name programs that a
# "read-only" git diff or status runs), and no fsmonitor hook runs.
GIT_SAFE = {"GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "safe.bareRepository", "GIT_CONFIG_VALUE_0": "explicit",
            "GIT_CONFIG_KEY_1": "core.fsmonitor", "GIT_CONFIG_VALUE_1": "false"}
PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + os.path.expanduser("~/.local/bin")


def clean_env() -> dict[str, str]:
    if "ANTHROPIC_API_KEY" in os.environ:
        raise RuntimeError("ANTHROPIC_API_KEY is set; Jarvis runs on the subscription login only")
    env = {k: os.environ[k] for k in KEEP if k in os.environ}
    env["PATH"] = PATH
    env |= {k: os.environ[k] for k in ("JARVIS_HOME", "JARVIS_VAULT") if os.environ.get(k)}
    return env | GIT_SAFE


def claude_argv(memory_map: str, agent: str = "jarvis", resume: str | None = None) -> list[str]:
    argv = [os.environ.get("JARVIS_CLAUDE_BIN") or "claude", "-p", "--agent", agent, "--model", "sonnet",
            "--input-format", "stream-json", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
            "--setting-sources", "project", "--settings", str(config.SETTINGS), "--strict-mcp-config",
            "--add-dir", str(config.DESKTOP_SKILLS), "--append-system-prompt", memory_map]
    return argv + ["--resume", resume] if resume else argv
