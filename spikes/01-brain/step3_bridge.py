"""Spike 1 step 3: does the PermissionRequest hook hold a command until it answers? deny then allow."""
import json, os, subprocess, sys, time
from clean import clean_env
here = os.path.dirname(os.path.abspath(__file__))
target = os.path.expanduser("~/Documents/jarvis-spike.txt")
cwd = sys.argv[2] if len(sys.argv) > 2 else here
for decision in sys.argv[1].split(","):
    env = clean_env() | {"SPIKE_DECISION": decision}
    t0 = time.time()
    r = subprocess.run(["claude", "-p", "--model", "sonnet", "--setting-sources", "project", "--settings", os.path.join(here, "spike-settings.json"),
                        "--output-format", "stream-json", "--verbose",
                        f"Run exactly this with the Bash tool, nothing else: touch {target} . Then say in one line whether it ran."],
                       capture_output=True, text=True, cwd=cwd, env=env, timeout=240)
    evs = [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
    tool_results = [c for e in evs if e.get("type") == "user" for c in e["message"].get("content", []) if isinstance(c, dict) and c.get("type") == "tool_result"]
    result = next((e for e in evs if e.get("type") == "result"), {})
    print(f"--- {decision} in {cwd}: {time.time()-t0:.1f}s  file exists: {os.path.exists(target)}")
    print("tool_result:", [str(c.get("content"))[:160] for c in tool_results])
    print("result:", repr(result.get("result"))[:200], "| denials:", result.get("permission_denials"))
    if os.path.exists(target):
        os.remove(target)
