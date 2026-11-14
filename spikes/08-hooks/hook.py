"""Probe hook for PreToolUse and PermissionRequest. Logs every payload; answers Bash calls from env.

PROBE_PRE   allow | deny | ask | none   (PreToolUse answer for Bash; none = no output)
PROBE_PERM  allow | deny               (PermissionRequest answer)
PROBE_HOLD_PRE / PROBE_HOLD_PERM       seconds to wait before answering
PROBE_LOG   log file name in tmp/
"""
import json, os, sys, time

here = os.path.dirname(os.path.abspath(__file__))
p = json.load(sys.stdin)
t0 = time.time()
ev = p.get("hook_event_name")
out = None
if p.get("tool_name") == "Bash":
    if ev == "PreToolUse":
        time.sleep(float(os.environ.get("PROBE_HOLD_PRE", 0)))
        d = os.environ.get("PROBE_PRE", "none")
        if d != "none":
            out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": d, "permissionDecisionReason": "probe"}}
    elif ev == "PermissionRequest":
        time.sleep(float(os.environ.get("PROBE_HOLD_PERM", 0)))
        d = os.environ.get("PROBE_PERM", "deny")
        dec = {"behavior": "allow"} if d == "allow" else {"behavior": "deny", "message": "probe said no"}
        out = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": dec}}
with open(os.path.join(here, "tmp", os.environ.get("PROBE_LOG", "hooks.jsonl")), "a") as f:
    f.write(json.dumps({"started": t0, "answered": time.time(), "reply": out, "payload": p}) + "\n")
if out:
    print(json.dumps(out))
