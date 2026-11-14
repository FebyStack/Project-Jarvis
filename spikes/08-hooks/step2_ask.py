"""Step 2: PreToolUse answers 'ask'; does PermissionRequest fire in -p mode, and does its answer decide?"""
import os
from probe import Child, TMP, short, tool_results

target = os.path.join(TMP, "step2.txt")
for d in ("deny", "allow"):
    if os.path.exists(target):
        os.remove(target)
    c = Child(f"step2-{d}", ["--model", "sonnet"], {"PROBE_PRE": "ask", "PROBE_PERM": d})
    c.send("Run exactly this with the Bash tool, nothing else: touch tmp/step2.txt . Then say in one line whether it ran, quoting any reason you were given.")
    r = c.result(240); c.close()
    hooks = c.hooks()
    print(f"--- PermissionRequest={d}: file exists={os.path.exists(target)}  hooks={[h['payload']['hook_event_name'] for h in hooks]}")
    print("  tool_result:", [short(x.get('content'), 200) for x in tool_results(c.events)])
    print("  reply:", short(r and r.get('result'), 200), "| denials:", short(r and r.get('permission_denials'), 200))
    pr = next((h["payload"] for h in hooks if h["payload"]["hook_event_name"] == "PermissionRequest"), None)
    if pr:
        print("  PermissionRequest fields:", sorted(pr))
