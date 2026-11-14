"""Vault writer: day logs and task notes, written by code so memory never depends on the model."""
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

Channel = Literal["mac", "phone"]
DEFAULT_ROOT = Path("/Users/febrielotud/Obsidian/Jarvis")
MAP = """# Jarvis vault map

- `raw/` — what happened. `YYYY-MM-DD.md` is the day's log, one line per exchange. `YYYY-MM-DD-HHMM-title.md` is one task. Written by jarvisd; do not edit.
- `wiki/` — what is known. One topic per note, linked with [[wiki-links]]. `wiki/index.md` lists every note.
- `outputs/` — what Jarvis made for Febriel: reports, plans, drafts.

Rule: read the relevant `wiki/` notes before acting on a task, and leave what you learned in `wiki/` after it.
"""


@dataclass
class Exchange:
    at: datetime
    channel: Channel
    asked: str
    answered: str
    notes_read: list[str] = field(default_factory=list)


@dataclass
class TaskRecord:
    at: datetime
    channel: Channel
    title: str
    asked: str
    done: str
    agents: list[tuple[str, str]]
    confirmations: list[tuple[str, bool]]
    files: list[str]
    notes_read: list[str]


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:56].rstrip("-") or "task"  # filenames stay short


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _link(note: str) -> str:
    return f"[[{Path(note).stem}]]"


class Vault:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.raw = self.root / "raw"

    def _append_day(self, at: datetime, line: str) -> Path:
        self.raw.mkdir(parents=True, exist_ok=True)
        path = self.raw / f"{at:%Y-%m-%d}.md"
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return path

    def log_exchange(self, ex: Exchange) -> Path:
        line = f"- {ex.at:%H:%M} · {ex.channel} · {_one_line(ex.asked)} → {_one_line(ex.answered)}"
        if ex.notes_read:
            line += " · read " + ", ".join(_link(n) for n in ex.notes_read)
        return self._append_day(ex.at, line)

    def write_task_note(self, rec: TaskRecord) -> Path:
        self.raw.mkdir(parents=True, exist_ok=True)
        stem = f"{rec.at:%Y-%m-%d-%H%M}-{slugify(rec.title)}"
        body = "\n".join([
            "---", f"at: {rec.at:%Y-%m-%d %H:%M}", f"channel: {rec.channel}", "---",
            f"# {_one_line(rec.title)}", "",
            "## Asked", rec.asked, "",
            "## Done", rec.done, "",
            "## Agents", *(f"- {a} ({m})" for a, m in rec.agents), "",
            "## Confirmations", *(f"- {q} — {'yes' if ok else 'no'}" for q, ok in rec.confirmations), "",
            "## Files", *(f"- {p}" for p in rec.files), "",
            "## Notes read", *(f"- {_link(n)}" for n in rec.notes_read), "",
        ])
        n = 1
        while True:
            path = self.raw / (f"{stem}.md" if n == 1 else f"{stem}-{n}.md")
            try:
                with path.open("x", encoding="utf-8") as f:  # exclusive: never overwrite
                    f.write(body)
                break
            except FileExistsError:
                n += 1
        self._append_day(rec.at, f"- {rec.at:%H:%M} · {rec.channel} · task {_link(path.name)}")
        return path

    def read_index(self) -> str:
        index = self.root / "wiki" / "index.md"
        return index.read_text(encoding="utf-8") if index.exists() else ""

    def status(self) -> Literal["ok", "missing", "read-only"]:
        if not self.root.is_dir():
            return "missing"
        probe = self.raw / ".jarvis-probe"
        try:
            self.raw.mkdir(exist_ok=True)
            probe.touch()
            probe.unlink()
        except OSError:
            return "read-only"
        return "ok"

    def ensure_map(self) -> None:
        """Writes `CLAUDE.md` and an empty `wiki/index.md` when absent; never creates the vault itself."""
        if not self.root.is_dir():
            return
        if not (self.root / "CLAUDE.md").exists():
            (self.root / "CLAUDE.md").write_text(MAP, encoding="utf-8")
        (self.root / "wiki").mkdir(exist_ok=True)
        (self.root / "wiki" / "index.md").touch(exist_ok=True)

    def wiki_notes(self) -> list[str]:
        wiki = self.root / "wiki"
        return sorted(str(p.relative_to(self.root)) for p in wiki.rglob("*.md") if p != wiki / "index.md")

    def memory_map(self) -> str:
        claude_md = self.root / "CLAUDE.md"
        return (claude_md.read_text(encoding="utf-8") if claude_md.exists() else MAP) + "\n\n" + self.read_index()


def default_vault() -> Vault:
    return Vault(Path(os.environ.get("JARVIS_VAULT", DEFAULT_ROOT)))
