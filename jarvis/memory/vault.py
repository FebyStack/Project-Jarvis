"""Vault writer: day logs and task notes, written by code so memory never depends on the model."""
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

Channel = Literal["mac", "phone"]
DEFAULT_ROOT = Path("/Users/febrielotud/Obsidian/Jarvis")


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


def default_vault() -> Vault:
    return Vault(Path(os.environ.get("JARVIS_VAULT", DEFAULT_ROOT)))
