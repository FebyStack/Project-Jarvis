"""Daemon events and rows shared by the face tests."""


def link(state): return {"type": "link", "state": state}
def health(**kw): return {"type": "health", "brain": "online", "vault": "ok", "mic": "on", "phone": "not linked", "awake": "n/a", "checklist": []} | kw
def state(voice, muted=False): return {"type": "state", "voice": voice, "muted": muted}
def level(rms, source="mic"): return {"type": "level", "rms": rms, "source": source}
def agents(*rows): return {"type": "agents", "items": list(rows)}
def hover(agent, on=True): return {"type": "hover", "agent": agent, "on": on}
def snapshot(*rows, voice="IDLE", muted=False, **h):
    return {"type": "snapshot", "state": {"voice": voice, "muted": muted}, "agents": list(rows), "queue": [], "memory": [],
            "limits": {}, "health": health(**h) | {"type": None}, "last_heard": ""}


def worker(state="working", id="t1", call="Nova", name="coder", since=1000.0, **kw):
    return {"id": id, "name": name, "call": call, "model": "opus", "doing": "Running tests", "since": since,
            "background": True, "title": "Fix export bug", "state": state, "question": None, "ask_id": None,
            "ask_until": None, "channel": "mac"} | kw


def asking(id="t1", until=1060.0, channel="mac", **kw):
    return worker("needs_you", id=id, question="Delete 14 files?", ask_id="k" + id, ask_until=until, channel=channel, **kw)


def front(state="idle", **kw):
    return worker(state, id="jarvis", call="Jarvis", name="jarvis", title="", **kw)
