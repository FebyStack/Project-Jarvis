"""Step 3: PreToolUse (argv[1]: none|allow|deny, default none) + PermissionRequest (allow) for a Bash call made inside a subagent, foreground and background."""
import os, sys, time
from probe import Child, TMP, short, tool_uses

PRE = sys.argv[1] if len(sys.argv) > 1 else "none"
for mode in ("fg", "bg"):
    target = os.path.join(TMP, f"step3-{mode}.txt")
    if os.path.exists(target):
        os.remove(target)
    c = Child(f"step3-{mode}-{PRE}", ["--model", "sonnet"], {"PROBE_PRE": PRE, "PROBE_PERM": "allow"})
    bg = "true" if mode == "bg" else "false"
    c.send(f"Use the Agent tool to dispatch the `worker` agent with run_in_background set to {bg}. Its prompt: "
           f"\"Run: touch tmp/step3-{mode}.txt\". Do not run any command yourself. Then say in one line what happened.")
    c.result(300)
    if mode == "bg":  # keep the process up until the background worker has finished
        end = time.time() + 180
        while time.time() < end and not (os.path.exists(target) and any(e.get("subtype") == "task_notification" for e in c.events)):
            c.next(2)
        c.until(lambda e: e.get("type") == "result", 60)
    c.close()
    hooks = c.hooks()
    print(f"--- {mode} PreToolUse={PRE}: file exists={os.path.exists(target)}")
    for h in hooks:
        p = h["payload"]
        print(f"  {p['hook_event_name']:17} {p['tool_name']:6} agent_id={p.get('agent_id')} agent_type={p.get('agent_type')} reply={short(h['reply'], 120)}")
    for par, u in tool_uses(c.events):
        print(f"  tool_use {u['name']} parent={par} input={short(u['input'], 140)}")
    sub = next((h["payload"] for h in hooks if h["payload"]["tool_name"] == "Bash"), None)
    if sub:
        print("  Bash hook fields:", sorted(sub))
        print("  example:", short(sub, 800))
