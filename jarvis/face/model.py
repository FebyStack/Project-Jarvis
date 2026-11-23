"""The face's view state: daemon events in, what the circle does and which beads show out. Pure; no AppKit."""

import math
from dataclasses import dataclass, replace
from typing import Literal

from jarvis import config
from jarvis.daemon.exchange import FREE_AGENTS
from jarvis.tui.model import elapsed

LIVE = ("working", "needs_you")


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    role: str
    model: str
    title: str
    doing: str
    elapsed: str
    state: str
    question: str | None
    ask_id: str | None
    stop: bool
    open: bool
    left: float | None
    left_text: str


@dataclass(frozen=True)
class Stack:
    cards: tuple[Card, ...]
    more_working: int
    more_asking: int


@dataclass(frozen=True)
class Circle:
    mode: Literal["idle", "listen", "work", "talk", "muted", "off"]
    ring: bool
    word: str
    level: float


@dataclass(frozen=True)
class FaceView:
    link: str
    voice: str
    muted: bool
    brain: str
    rows: tuple[dict, ...]
    hovered: frozenset[str]
    mic: float
    speech: float
    hidden: bool   # Ctrl-Option-J: the circle, its beads and threads are gone

    @classmethod
    def empty(cls) -> "FaceView":
        return cls("connecting", "IDLE", False, "online", (), frozenset(), 0.0, 0.0, False)


def _rows(view: FaceView, items) -> dict:
    rows = tuple(i for i in items if isinstance(i, dict) and "id" in i)
    return {"rows": rows, "hovered": view.hovered & {r["id"] for r in rows}}


def reduce(view: FaceView, event: dict) -> FaceView:
    """A missing field takes its default; an event whose fields have the wrong shape is dropped (a jarvisd of
    another version must not crash the face into a restart loop)."""
    try:
        return _reduce(view, event)
    except (AttributeError, KeyError, TypeError, ValueError):
        return view


def _reduce(view: FaceView, event: dict) -> FaceView:
    match event.get("type"):
        case "link":
            ch = {"link": event["state"]}
            if event["state"] == "no daemon":   # shown: the hide key lives in jarvisd, which starts with the face shown
                ch |= {"rows": (), "hovered": frozenset(), "hidden": False}
        case "snapshot":
            st = event.get("state") or {}
            ch = {"link": "online", "voice": st.get("voice", "IDLE"), "muted": bool(st.get("muted")),
                  "brain": (event.get("health") or {}).get("brain", "online"),
                  "hidden": bool(event.get("face_hidden"))} | _rows(view, event.get("agents") or ())
        case "state":
            ch = {"voice": event.get("voice", view.voice), "muted": bool(event.get("muted", view.muted))}
        case "health":
            ch = {"brain": event.get("brain", view.brain)}
        case "face":
            ch = {"hidden": bool(event.get("hidden", view.hidden))}
        case "level":
            rms = min(1.0, max(0.0, float(event.get("rms", 0.0))))
            ch = {"speech": rms} if event.get("source") == "voice" else {"mic": rms}
        case "agents":
            ch = _rows(view, event.get("items") or ())
        case "hover":
            ids = {r["id"] for r in view.rows}
            ch = {"hovered": view.hovered | {event["agent"]} if event["on"] and event["agent"] in ids else view.hovered - {event["agent"]}}
        case _:
            return view
    return replace(view, **ch)


def _workers(view: FaceView) -> list[dict]:
    return [r for r in view.rows if r["id"] != "jarvis" and r.get("name") not in FREE_AGENTS]


def circle(view: FaceView) -> Circle:
    ring = any(r.get("state") == "needs_you" for r in view.rows)
    word = "NO DAEMON" if view.link == "no daemon" else {"offline": "OFFLINE", "down": "OFFLINE", "limit": "LIMIT"}.get(view.brain, "")
    if word:   # no ring: there is no bead to answer on (tether design §9)
        return Circle("off", False, word, 0.0)
    if view.voice == "SPEAKING":
        return Circle("talk", ring, "", view.speech)
    if view.voice == "LISTENING":
        return Circle("listen", ring, "", view.mic)
    jarvis = any(r["id"] == "jarvis" and r.get("state") == "working" for r in view.rows)   # a turn, the phone's too
    if view.voice == "THINKING" or jarvis or any(r.get("state") in LIVE for r in _workers(view)):
        return Circle("work", ring, "", 0.0)
    return Circle("muted" if view.muted else "idle", ring, "", 0.0)


def _asked(row: dict) -> float:
    until = row.get("ask_until")
    return until - config.ASK_TIMEOUT.get(row.get("channel"), config.ASK_TIMEOUT["mac"]) if until else row.get("since", 0.0)


def _card(row: dict, view: FaceView, now: float) -> Card:
    state, since, question = row.get("state", "working"), row.get("since", now), row.get("question")
    left, left_text, until = None, "", row.get("ask_until")
    if question and until:
        remaining = until - now
        total = config.ASK_TIMEOUT.get(row.get("channel"), config.ASK_TIMEOUT["mac"])
        left = min(1.0, max(0.0, remaining / total))
        left_text = f"No in {math.ceil(max(0.0, remaining))} s" if remaining < 60 else f"No in {math.ceil(remaining / 60)} min"
    live = state in LIVE
    is_open = bool(question) or (state == "working" and (row["id"] in view.hovered or now - since < config.CARD_POP_SECONDS))
    role = row.get("name", "")
    model = (row.get("model") or "").removeprefix("claude-")   # "coder · opus-5-5", as the HUD shows it
    return Card(row["id"], row.get("call") or role, role, model, row.get("title", ""), row.get("doing", ""),
                elapsed(since, now), state, question, row.get("ask_id"), live, is_open, left, left_text)


def stack(view: FaceView, now: float) -> Stack:
    if circle(view).mode == "off":   # tether design §9: every bead goes while jarvisd is gone, offline or limited
        return Stack((), 0, 0)
    rows = _workers(view) + [r for r in view.rows if r["id"] == "jarvis" and r.get("state") == "needs_you"]
    asking = sorted((r for r in rows if r.get("state") == "needs_you"), key=_asked)
    working = sorted((r for r in rows if r.get("state") == "working"), key=lambda r: -r.get("since", 0.0))
    ended = sorted((r for r in rows if r.get("state") not in LIVE), key=lambda r: -r.get("since", 0.0))
    ordered = asking + working + ended
    shown, hidden = ordered[:config.CARD_MAX], ordered[config.CARD_MAX:]
    return Stack(tuple(_card(r, view, now) for r in shown),
                 sum(r.get("state") == "working" for r in hidden), sum(r.get("state") == "needs_you" for r in hidden))


def more_text(s: Stack) -> str:
    parts = []
    if s.more_asking:
        parts.append(f"+{s.more_asking} more {'needs' if s.more_asking == 1 else 'need'} you")
    if s.more_working:
        parts.append(f"+{s.more_working} more working")
    return " · ".join(parts)


def new_alerts(before: FaceView, after: FaceView) -> bool:
    known = {r.get("ask_id") for r in before.rows}
    return any(r.get("state") == "needs_you" and r.get("channel", "mac") == "mac" and r.get("ask_id") not in known
               for r in after.rows)
