"""Spike 1 step 3b: --permission-prompt-tool via a local MCP server. deny then allow."""
import json, os, subprocess, time
from clean import clean_env
here = os.path.dirname(os.path.abspath(__file__))
target = os.path.expanduser("~/Documents/jarvis-spike.txt")
mcp = json.dumps({"mcpServers": {"bridge": {"command": "python3", "args": [os.path.join(here, "prompt_tool_server.py")]}}})
for decision in ("deny", "allow"):
    t0 = time.time()
    r = subprocess.run(["claude", "-p", "--model", "sonnet", "--setting-sources", "project", "--strict-mcp-config", "--mcp-config", mcp,
                        "--permission-prompt-tool", "mcp__bridge__approve", "--output-format", "json",
                        f"Run exactly this with the Bash tool, nothing else: touch {target} . Then say in one line whether it ran."],
                       capture_output=True, text=True, cwd=here, env=clean_env() | {"SPIKE_DECISION": decision}, timeout=240)
    out = json.loads(r.stdout or "{}")
    print(f"--- {decision}: {time.time()-t0:.1f}s file exists: {os.path.exists(target)} | {str(out.get('result'))[:150]!r} | denials: {len(out.get('permission_denials') or [])}")
    if os.path.exists(target):
        os.remove(target)
