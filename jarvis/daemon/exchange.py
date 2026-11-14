"""One request's exchange or task, followed from bridge events; the memory rule; the vault record (plan 2, Task 9)."""
import re
from datetime import datetime
from pathlib import Path

from jarvis import config
from jarvis.brain.verdict import Verdict, parse_verdict
from jarvis.memory.vault import Channel, Exchange, TaskRecord, Vault

FREE_AGENTS = {"triage", "scribe"}  # any other subagent type is a worker
WRITE_KEYS = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
NEED_TRIAGE = "Call triage before dispatching a worker."
NEED_NOTES = "Open the relevant wiki notes before dispatching a worker."


def agent_model(name: str) -> str:
    """The `model:` of `.claude/agents/<name>.md`: for an agent that called no tool and was given no tier."""
    try:
        text = (config.PROJECT / ".claude" / "agents" / f"{name}.md").read_text()
    except (OSError, ValueError):
        return "unknown"
    m = re.search(r"^model:\s*(\S+)", text, re.M)
    return m.group(1) if m else "unknown"


class Tracker:
    def __init__(self, vault: Vault, request_id: str, channel: Channel, asked: str, at: datetime):
        self.vault, self.request_id, self.channel, self.asked, self.at = vault, request_id, channel, asked, at
        self.is_task = False
        self.verdict: Verdict | None = None
        self.open_agents: set[str] = set()
        self.notes_read: list[str] = []
        self.files: list[str] = []
        self.summaries: list[str] = []
        self._agents: dict[str, dict] = {}  # Agent tool_use_id -> {"name", "model", "asked_model"}, first seen first
        self._turn_ended = self._finished = False

    @property
    def closed(self) -> bool:
        return self._turn_ended and not self.open_agents

    def _agent(self, tool_use_id: str, name: str, asked_model: str | None = None) -> None:
        self._agents.setdefault(tool_use_id, {"name": name, "model": None, "asked_model": asked_model})

    def feed(self, event: dict) -> None:
        kind = event.get("kind")
        if kind == "tool":
            name, inp = event.get("name"), event.get("input") or {}
            if event.get("parent") in self._agents and self._agents[event["parent"]]["model"] is None:
                self._agents[event["parent"]]["model"] = event.get("model")
            if name == "Agent":
                self._agent(event.get("id"), inp.get("subagent_type") or "general-purpose", inp.get("model"))
                if inp.get("subagent_type") == "triage":
                    self.is_task = True
            elif name == "Read":
                note = self._in_vault(inp.get("file_path"))
                if note and note not in self.notes_read:
                    self.notes_read.append(note)
            elif name in WRITE_KEYS:
                path = inp.get(WRITE_KEYS[name])
                if isinstance(path, str) and path not in self.files:
                    self.files.append(path)
        elif kind == "tool_result" and self.verdict is None and event.get("parent") is None:
            self.verdict = parse_verdict(event.get("text"))
        elif kind == "agent_start":
            self._agent(event.get("tool_use_id"), event.get("agent"))
            if event.get("background"):
                self.open_agents.add(event.get("task_id"))
        elif kind == "agent_done" and event.get("task_id") in self.open_agents:
            self.open_agents.discard(event["task_id"])
            if event.get("summary"):
                self.summaries.append(event["summary"])
        elif kind == "turn":
            self._turn_ended = True

    def _in_vault(self, path) -> str | None:
        if not isinstance(path, str):
            return None
        try:
            return str(Path(path).resolve().relative_to(self.vault.root.resolve()))
        except (ValueError, OSError):
            return None

    def owns(self, event: dict) -> bool:
        """True for an event from one of this request's agents (a background worker can outlive the request)."""
        parent, task = event.get("parent"), event.get("task_id")
        return (parent is not None and parent in self._agents) or (task is not None and task in self.open_agents)

    def may_dispatch(self, subagent_type: str) -> tuple[bool, str]:
        if subagent_type in FREE_AGENTS:
            return True, ""
        if not self.is_task:
            return False, NEED_TRIAGE
        if not self.notes_read and self.vault.wiki_notes():
            return False, NEED_NOTES
        return True, ""

    def finish(self, answered: str, confirmations: list[tuple[str, bool]]) -> Path:
        if self._finished or not self.closed:
            raise RuntimeError("the request is still open or already recorded")
        self._finished = True
        if not self.is_task:
            return self.vault.log_exchange(Exchange(self.at, self.channel, self.asked, answered, self.notes_read))
        title = self.verdict.title if self.verdict else " ".join(self.asked.split()[:6])
        agents = [("jarvis", "sonnet")] + [(a["name"], a["model"] or a["asked_model"] or agent_model(a["name"])) for a in self._agents.values()]
        return self.vault.write_task_note(TaskRecord(
            self.at, self.channel, title, self.asked, "\n\n".join([answered, *self.summaries]), agents,
            confirmations, self.files, self.notes_read))
