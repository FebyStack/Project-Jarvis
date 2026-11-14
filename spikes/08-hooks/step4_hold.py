"""Step 4: hold a decision 90 s (hook entry timeout 660), then allow. argv[1]: pre (hold in PreToolUse) | perm (hold in PermissionRequest)."""
import os, sys
from probe import Child, TMP, short, tool_results

where = sys.argv[1]
target = os.path.join(TMP, f"step4-{where}.txt")
if os.path.exists(target):
    os.remove(target)
env = {"PROBE_PRE": "allow", "PROBE_HOLD_PRE": "90"} if where == "pre" else {"PROBE_PRE": "none", "PROBE_PERM": "allow", "PROBE_HOLD_PERM": "90"}
c = Child(f"step4-{where}", ["--model", "sonnet"], env)
c.send(f"Run exactly this with the Bash tool, nothing else: touch tmp/step4-{where}.txt . Then say in one line whether it ran.")
r = c.result(400); c.close()
print(f"--- hold in {where}: file exists={os.path.exists(target)}  total={c.t():.1f}s")
for h in c.hooks():
    print(f"  {h['payload']['hook_event_name']:17} held {h['answered'] - h['started']:.1f}s reply={short(h['reply'], 140)}")
print("  tool_result:", [short(x.get('content'), 200) for x in tool_results(c.events)])
