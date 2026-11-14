"""One-shot `scribe` runs that distil raw notes into wiki/, and the idle sweep of day logs (plan 2, Task 9)."""
import json
import subprocess
from pathlib import Path

from jarvis import config
from jarvis.brain.env import claude_argv, clean_env
from jarvis.memory.vault import Vault


def scribe_argv(vault: Vault, target: Path) -> list[str]:
    argv = claude_argv(vault.memory_map(), agent="scribe")
    argv[argv.index("--model") + 1] = "haiku"
    i = argv.index("--input-format")
    del argv[i:i + 2]
    return argv + [f"Distil this note into wiki/: {target}"]


def run(vault: Vault, target: Path) -> subprocess.Popen:
    """Starts scribe detached and returns at once (the caller may poll it); its output is discarded."""
    return subprocess.Popen(scribe_argv(vault, target), cwd=config.PROJECT, env=clean_env(), start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Sweeper:
    """Picks a day log to distil once Jarvis has been quiet for SWEEP_IDLE_SECONDS and the log has grown."""

    def __init__(self, vault: Vault, home: Path):
        self.vault, self.file = vault, home / "scribe.json"
        self.retry_after = 0.0  # after a failed sweep, wait another quiet period before trying again

    def _sizes(self) -> dict[str, int]:
        try:
            return json.loads(self.file.read_text())
        except (OSError, ValueError):
            return {}

    def due(self, now: float, last_request: float, busy: bool) -> Path | None:
        if busy or now - last_request < config.SWEEP_IDLE_SECONDS or now < self.retry_after:
            return None
        sizes = self._sizes()
        return next((p for p in sorted(self.vault.raw.glob("????-??-??.md"))
                     if p.stat().st_size > sizes.get(p.name, 0)), None)

    def mark(self, path: Path) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(self._sizes() | {path.name: path.stat().st_size}))
