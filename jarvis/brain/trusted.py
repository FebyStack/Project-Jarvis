"""Hand-editable list of patterns Febriel answered "yes, always" to."""
from pathlib import Path

DEFAULT_TRUSTED = Path.home() / ".jarvis" / "trusted.txt"


class TrustedList:
    def __init__(self, path: Path = DEFAULT_TRUSTED):
        self.path = Path(path)

    def _patterns(self) -> set[str]:
        if not self.path.exists():
            return set()
        lines = (l.strip() for l in self.path.read_text(encoding="utf-8").splitlines())
        return {l for l in lines if l and not l.startswith("#")}

    def contains(self, pattern: str) -> bool:
        return pattern in self._patterns()

    def add(self, pattern: str) -> None:
        if not pattern or self.contains(pattern):
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        lead = "\n" if text and not text.endswith("\n") else ""
        with self.path.open("a", encoding="utf-8") as f:
            f.write(lead + pattern + "\n")
