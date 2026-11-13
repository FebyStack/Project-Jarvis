"""Spike 1 step 5: worker as a background subagent for 60 s; a new user message meanwhile. Who answers first?"""
import json, os, queue, subprocess, threading, time
from clean import clean_env
here = os.path.dirname(os.path.abspath(__file__))
p = subprocess.Popen(["claude", "-p", "--agent", "jarvis", "--setting-sources", "project", "--settings", os.path.join(here, "spike-settings.json"),
                      "--input-format", "stream-json", "--output-format", "stream-json", "--verbose"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=here, env=clean_env() | {"SPIKE_DECISION": "allow"})
q = queue.Queue(); T0 = time.time()
threading.Thread(target=lambda: [q.put(json.loads(l)) for l in p.stdout], daemon=True).start()
log = open(os.path.join(here, "tmp", "step5.jsonl"), "w")
def send(t):
    p.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": t}}) + "\n"); p.stdin.flush()
    print(f"{time.time()-T0:6.1f}s SENT {t[:70]!r}")
send("Dispatch the `slow` agent with run_in_background set to true (do not wait for it), then tell me in one line that it has started.")
sent2 = False
while time.time() - T0 < 200:
    try: ev = q.get(timeout=1)
    except queue.Empty: ev = None
    if ev:
        log.write(json.dumps(ev) + "\n")
        t = time.time() - T0
        if ev.get("type") == "assistant":
            for c in ev["message"].get("content", []):
                if c.get("type") == "tool_use": print(f"{t:6.1f}s TOOL {c['name']} {json.dumps(c['input'])[:110]}")
                if c.get("type") == "text": print(f"{t:6.1f}s TEXT {c['text'][:110]!r}")
        if ev.get("type") == "system" and ev.get("subtype") not in ("init",): print(f"{t:6.1f}s SYSTEM {ev.get('subtype')} {json.dumps(ev)[:160]}")
        if ev.get("type") == "result": print(f"{t:6.1f}s RESULT {str(ev.get('result'))[:110]!r}")
    if not sent2 and time.time() - T0 > 25:
        send("Quick question while that runs: what is 17 + 25? One line."); sent2 = True
p.stdin.close(); p.wait(timeout=60)
