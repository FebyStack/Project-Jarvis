"""Minimal stdio MCP server exposing one permission-prompt tool (spike only, stdlib only)."""
import json, os, sys, time
here = os.path.dirname(os.path.abspath(__file__))
TOOL = {"name": "approve", "description": "Jarvis permission bridge (spike)",
        "inputSchema": {"type": "object", "properties": {"tool_name": {"type": "string"}, "input": {"type": "object"},
                                                         "tool_use_id": {"type": "string"}}}}
for line in sys.stdin:
    msg = json.loads(line)
    mid, method = msg.get("id"), msg.get("method")
    if mid is None:
        continue  # notification
    if method == "initialize":
        res = {"protocolVersion": msg["params"].get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
               "serverInfo": {"name": "bridge", "version": "0"}}
    elif method == "tools/list":
        res = {"tools": [TOOL]}
    elif method == "tools/call":
        args = msg["params"].get("arguments", {})
        t0 = time.time(); time.sleep(5)
        d = os.environ.get("SPIKE_DECISION", "deny")
        with open(os.path.join(here, "tmp", "prompt-tool-log.jsonl"), "a") as f:
            f.write(json.dumps({"held": time.time() - t0, "decision": d, "arguments": args}) + "\n")
        body = {"behavior": "allow", "updatedInput": args.get("input", {})} if d == "allow" else {"behavior": "deny", "message": "Febriel said no (spike)"}
        res = {"content": [{"type": "text", "text": json.dumps(body)}]}
    else:
        res = {}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": res}) + "\n"); sys.stdout.flush()
