"""Step 2 control: PreToolUse gives no answer, so Claude Code itself asks. Does PermissionRequest fire then?"""
import os
from probe import Child, TMP, short, tool_results

target = os.path.join(TMP, "step2b.txt")
if os.path.exists(target):
    os.remove(target)
c = Child("step2b", ["--model", "sonnet"], {"PROBE_PRE": "none", "PROBE_PERM": "allow"})
c.send("Run exactly this with the Bash tool, nothing else: touch tmp/step2b.txt . Then say in one line whether it ran.")
r = c.result(240); c.close()
print(f"--- PreToolUse=none, PermissionRequest=allow: file exists={os.path.exists(target)}  hooks={[h['payload']['hook_event_name'] for h in c.hooks()]}")
print("  tool_result:", [short(x.get('content'), 200) for x in tool_results(c.events)])
pr = next((h["payload"] for h in c.hooks() if h["payload"]["hook_event_name"] == "PermissionRequest"), None)
if pr:
    print("  PermissionRequest fields:", sorted(pr))
