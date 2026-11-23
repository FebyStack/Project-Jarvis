"""P4-P6 hook. Agent dispatches are allowed with a name edited in (PROBE_RENAME=1); calls from an agent_id in tmp/deny.txt are denied."""
import json, os, re, sys, time

here = os.path.dirname(os.path.abspath(__file__))
SAFE = re.compile(r"^(ls \| wc -l|sleep \d+)$")   # the only commands the probes run
NAMES = ["Nova", "Orin", "Vesper", "Kite"]
p = json.load(sys.stdin)
ev, tool = p.get("hook_event_name"), p.get("tool_name")
deny_file = os.path.join(here, "tmp", "deny.txt")
deny = set(open(deny_file).read().split()) if os.path.exists(deny_file) else set()
out = None
if ev == "PreToolUse":
    if p.get("agent_id") and p["agent_id"] in deny:
        out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                      "permissionDecisionReason": "Febriel stopped this agent."}}
    elif tool == "Agent" and os.environ.get("PROBE_RENAME") == "1":
        count = os.path.join(here, "tmp", "names.txt")
        used = open(count).read().split() if os.path.exists(count) else []
        name = NAMES[len(used) % len(NAMES)]
        open(count, "a").write(name + "\n")
        inp = dict(p["tool_input"])
        inp["description"] = f"{name}: {inp.get('description', '')}"
        inp["prompt"] = f"Your name is {name}.\n\n{inp.get('prompt', '')}"
        out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                      "permissionDecisionReason": "probe", "updatedInput": inp}}
    else:
        ok = tool == "Agent" or (tool == "Bash" and SAFE.match(str(p.get("tool_input", {}).get("command", ""))))
        out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow" if ok else "deny",
                                      "permissionDecisionReason": "probe"}}
elif ev == "PermissionRequest":
    ok = p.get("tool_name") == "Bash" and SAFE.match(str(p.get("tool_input", {}).get("command", "")))
    out = {"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                                  "decision": {"behavior": "allow"} if ok else {"behavior": "deny", "message": "probe"}}}
with open(os.path.join(here, "tmp", os.environ.get("PROBE_LOG", "hooks.jsonl")), "a") as f:
    f.write(json.dumps({"t": time.time(), "reply": out, "payload": p}) + "\n")
if out:
    print(json.dumps(out))
