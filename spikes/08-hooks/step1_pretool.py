"""Step 1: PreToolUse on a Bash call. deny → command blocked, model sees 'probe'; allow → runs, no PermissionRequest."""
import os
from probe import Child, TMP, short, tool_results

target = os.path.join(TMP, "step1.txt")
for d in ("deny", "allow"):
    if os.path.exists(target):
        os.remove(target)
    c = Child(f"step1-{d}", ["--model", "sonnet"], {"PROBE_PRE": d})
    c.send(f"Run exactly this with the Bash tool, nothing else: touch tmp/step1.txt . Then say in one line whether it ran, quoting any reason you were given.")
    r = c.result(240); c.close()
    hooks = c.hooks()
    print(f"--- {d}: file exists={os.path.exists(target)}  events={[h['payload']['hook_event_name'] for h in hooks]}")
    print("  tool_result:", [short(x.get('content'), 200) for x in tool_results(c.events)])
    print("  reply:", short(r and r.get('result'), 200))
    pre = next((h["payload"] for h in hooks if h["payload"]["hook_event_name"] == "PreToolUse"), None)
    if pre:
        print("  PreToolUse fields:", sorted(pre))
        print("  example:", short(pre, 700))
