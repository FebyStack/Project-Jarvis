"""Spike 1 step 2: --agent jarvis → triage (opus 5.5) → quick with a per-call model; record each message's model."""
import json, subprocess, os
from clean import clean_env
here = os.path.dirname(os.path.abspath(__file__))
p = subprocess.Popen(["claude", "-p", "--agent", "jarvis", "--input-format", "stream-json", "--output-format", "stream-json",
                      "--verbose", "--forward-subagent-text"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=here, env=clean_env())
p.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": "Route this task: what is the capital of Australia?"}}) + "\n"); p.stdin.flush()
log = open(os.path.join(here, "tmp", "step2.jsonl"), "w")
for line in p.stdout:
    ev = json.loads(line); log.write(line)
    if ev.get("type") == "system" and ev.get("subtype") == "init":
        print("INIT model", ev.get("model"), "agents", [a for a in ev.get("agents", []) if a in ("jarvis", "triage", "quick")])
    if ev.get("type") == "assistant":
        m = ev["message"]
        for c in m.get("content", []):
            if c.get("type") == "tool_use" and c.get("name") in ("Agent", "Task"):
                print("DISPATCH", {k: c["input"].get(k) for k in ("subagent_type", "model")})
            if c.get("type") == "text":
                print(f"[{m.get('model')}] parent={str(ev.get('parent_tool_use_id'))[:8]}:", c["text"][:120].replace("\n", " "))
    if ev.get("type") == "result":
        print("RESULT", repr(ev.get("result"))[:300]); break
p.stdin.close(); p.wait(timeout=30)
