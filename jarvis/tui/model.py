"""HUD view state: daemon events in, one immutable View out. Pure; no Textual."""

from dataclasses import dataclass, field, replace
from typing import Literal

MEMORY_ROWS = 50
LEVELS = 28  # the waveform's width
MIC_ON = ("on", "on, no key")


@dataclass(frozen=True)
class AgentRow:
    id: str
    name: str
    model: str
    doing: str
    since: float
    background: bool
    call: str = ""
    title: str = ""
    state: str = "working"


@dataclass(frozen=True)
class QueueRow:
    id: str
    title: str
    status: Literal["running", "waiting", "needs_you"]
    question: str | None = None
    ask_id: str | None = None


@dataclass(frozen=True)
class View:
    link: Literal["connecting", "online", "no daemon"]
    voice: str
    muted: bool
    last_heard: str
    reply: str
    agents: tuple[AgentRow, ...]
    queue: tuple[QueueRow, ...]
    memory: tuple[tuple[str, str], ...]  # (op, path), newest first
    limits: str
    health: dict
    screen: Literal["main", "starting", "offline", "vault", "limit", "first-run", "no-daemon"]
    resets_at: float | None = None  # for "LIMIT REACHED: resumes at HH:MM"
    levels: tuple[float, ...] = ()  # the mic's last LEVELS levels, 0..1, newest last
    reply_done: bool = field(default=False, repr=False)  # the next reply_delta starts a new reply

    @classmethod
    def empty(cls) -> "View":
        return cls("connecting", "IDLE", False, "", "", (), (), (), "", {}, "main")


def limits_text(limits: dict) -> str:
    weekly = limits.get("weekly")
    if isinstance(weekly, (int, float)):
        return f"LIMITS ● {round(weekly * 100)}%"
    return f"LIMITS ● {limits.get('status', 'ok')}"


def needs_you(view: View) -> QueueRow | None:
    return next((q for q in view.queue if q.status == "needs_you"), None)


def elapsed(since: float, now: float) -> str:
    m, s = divmod(max(0, int(now - since)), 60)
    return f"{m:02d}:{s:02d}"


def _screen(v: View) -> str:
    h = v.health
    if v.link == "no daemon":
        return "no-daemon"
    if h.get("checklist"):
        return "first-run"
    if h.get("vault", "ok") != "ok":
        return "vault"
    return {"starting": "starting", "offline": "offline", "down": "offline", "limit": "limit"}.get(h.get("brain"), "main")


def _fields(event: dict) -> dict:
    return {k: v for k, v in event.items() if k not in ("type", "at")}


def _agents(items) -> tuple[AgentRow, ...]:
    known = AgentRow.__dataclass_fields__
    return tuple(AgentRow(**{k: v for k, v in i.items() if k in known}) for i in items)


def _queue(items) -> tuple[QueueRow, ...]:
    return tuple(QueueRow(**i) for i in items)


def _limits(limits: dict) -> dict:
    return {"limits": limits_text(limits), "resets_at": limits.get("resets_at")}


def reduce(view: View, event: dict) -> View:
    match event.get("type"):
        case "link":
            ch = {"link": event["state"]}
        case "snapshot":
            ch = {
                "link": "online", "voice": event["state"]["voice"], "muted": event["state"]["muted"],
                "agents": _agents(event["agents"]), "queue": _queue(event["queue"]),
                "memory": tuple((m["op"], m["path"]) for m in event["memory"])[:MEMORY_ROWS],
                "health": dict(event["health"]), "last_heard": event["last_heard"], **_limits(event["limits"]),
            }
        case "state":
            ch = {"voice": event["voice"], "muted": event["muted"]}
        case "heard":
            ch = {"last_heard": event["text"], "reply": "", "reply_done": False}
        case "reply_delta":
            ch = {"reply": ("" if view.reply_done else view.reply) + event["text"], "reply_done": False}
        case "reply":
            ch = {"reply": event["text"], "reply_done": True}
        case "agents":
            ch = {"agents": _agents(event["items"])}
        case "queue":
            ch = {"queue": _queue(event["items"])}
        case "memory":
            ch = {"memory": ((event["op"], event["path"]), *view.memory)[:MEMORY_ROWS]}
        case "limits":
            ch = _limits(event)
        case "health":
            ch = {"health": view.health | _fields(event)}
            if event.get("mic", "on") not in MIC_ON:
                ch["levels"] = ()
        case "level":
            ch = {"levels": (*view.levels, event["rms"])[-LEVELS:]}
        case _:
            return view
    v = replace(view, **ch)
    return replace(v, screen=_screen(v))
