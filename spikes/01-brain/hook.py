"""PermissionRequest hook for the spike: log the payload, wait 5 s, answer from SPIKE_DECISION."""
import json, os, sys, time
here = os.path.dirname(os.path.abspath(__file__))
payload = json.load(sys.stdin)
t0 = time.time()
time.sleep(5)
decision = os.environ.get("SPIKE_DECISION", "deny")
with open(os.path.join(here, "tmp", "hook-log.jsonl"), "a") as f:
    f.write(json.dumps({"started": t0, "answered": time.time(), "decision": decision, "payload": payload}) + "\n")
out = {"behavior": decision} if decision == "allow" else {"behavior": "deny", "message": "Febriel said no (spike)"}
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": out}}))
