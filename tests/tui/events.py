"""Daemon events shared by the HUD tests (Task 10's shapes)."""

SNAPSHOT = {
    "type": "snapshot",
    "at": "2026-11-14T20:14:00",
    "state": {"voice": "IDLE", "muted": False},
    "agents": [{"id": "jarvis", "name": "jarvis", "model": "sonnet", "doing": "talking to you", "since": 0.0, "background": False}],
    "queue": [],
    "memory": [{"op": "r", "path": "wiki/preferences.md"}],
    "limits": {"status": "near", "weekly": 0.33, "resets_at": 1_763_400_000.0},
    "health": {"brain": "online", "vault": "ok", "mic": "off", "phone": "not linked", "awake": "n/a", "checklist": []},
    "last_heard": "",
}
