"""Bridge events (Task 7's shapes) for the tracker and core tests."""
import itertools

_ids = itertools.count(1)

GOOD_VERDICT = "worker: coder\ntier: opus\nwhy: touches the export pipeline\nrisks: none\nask: none\ntitle: Fix export bug"


def tool(name, inp, model="claude-sonnet-5-5", parent=None, id=None):
    return {"kind": "tool", "id": id or f"toolu_{next(_ids)}", "name": name, "input": inp, "model": model, "parent": parent}


def tool_result(text, tool_use_id="toolu_x", parent=None):
    return {"kind": "tool_result", "tool_use_id": tool_use_id, "text": text, "parent": parent}


def agent_start(task_id, agent, background=False, tool_use_id="tu1"):
    return {"kind": "agent_start", "task_id": task_id, "tool_use_id": tool_use_id, "agent": agent,
            "description": agent, "background": background}


def agent_done(task_id, status, summary, tool_use_id="tu1"):
    return {"kind": "agent_done", "task_id": task_id, "tool_use_id": tool_use_id, "status": status, "summary": summary}


def turn(text, is_error=False, cancelled=False, session_id="fake-session"):
    return {"kind": "turn", "text": text, "is_error": is_error, "session_id": session_id, "cancelled": cancelled}
