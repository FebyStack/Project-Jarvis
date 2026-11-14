"""Hook client Claude Code runs before every tool call: asks jarvisd for the verdict and prints it.

Started once per tool call, so it imports only the standard library and jarvis.config.
Fails closed: any error prints a deny and exits 0. It never prints `ask`: in `-p` mode that is a
silent deny (plan 2, amendments after Task 1).
"""
import json
import sys
import urllib.request

from jarvis import config

PORT = config.PORT
TIMEOUT = config.HOOK_TIMEOUT - 10
EVENTS = ("PreToolUse", "PermissionRequest")
NOT_RUNNING = "Jarvis is not running, so the answer is no."
UNKNOWN_EVENT = "Jarvis does not judge this hook event, so the answer is no."
# No proxies: the token goes to 127.0.0.1 and nowhere else.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def render(event, verdict, reason):
    allow = verdict == "allow" and event in EVENTS
    if event == "PermissionRequest":
        decision = {"behavior": "allow"} if allow else {"behavior": "deny", "message": reason}
        return {"hookSpecificOutput": {"hookEventName": event, "decision": decision}}
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "allow" if allow else "deny",
                                   "permissionDecisionReason": reason}}


def _ask_jarvisd(payload):
    token = (config.HOME_DIR / "token").read_text().strip()
    if not token:
        raise ValueError("empty token")
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/hook", data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with _OPENER.open(req, timeout=TIMEOUT) as resp:
        if resp.status != 200:
            raise ValueError(resp.status)
        reply = json.loads(resp.read())
    verdict, reason = reply["verdict"], reply["reason"]
    if verdict not in ("allow", "deny") or not isinstance(reason, str):
        raise ValueError("bad reply")
    return verdict, reason


def main(stdin=sys.stdin, stdout=sys.stdout):
    event, verdict, reason = "PreToolUse", "deny", NOT_RUNNING
    try:
        payload = json.load(stdin)
        event = payload["hook_event_name"]
        if event in EVENTS:
            verdict, reason = _ask_jarvisd(payload)
        else:
            reason = UNKNOWN_EVENT
    except Exception:
        verdict = "deny"
    stdout.write(json.dumps(render(event, verdict, reason)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
