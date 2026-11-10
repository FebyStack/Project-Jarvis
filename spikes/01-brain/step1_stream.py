"""Spike 1 step 1: one long-lived claude -p stream-json process, two messages a minute apart."""
import json, os, subprocess, sys, threading, time, queue

assert "ANTHROPIC_API_KEY" not in os.environ, "ANTHROPIC_API_KEY is set — stop"
GAP = float(sys.argv[1]) if len(sys.argv) > 1 else 60
here = os.path.dirname(os.path.abspath(__file__))
log = open(os.path.join(here, "tmp", "step1.jsonl"), "w")
p = subprocess.Popen(["claude", "-p", "--model", "sonnet", "--input-format", "stream-json",
                      "--output-format", "stream-json", "--verbose"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=here)
q = queue.Queue()
threading.Thread(target=lambda: [q.put(json.loads(l)) for l in p.stdout], daemon=True).start()

def send(text):
    p.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n"); p.stdin.flush()
    t0 = time.time(); first = None
    while True:
        ev = q.get(timeout=180); log.write(json.dumps(ev) + "\n"); log.flush()
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            print("INIT", {k: ev.get(k) for k in ("apiKeySource", "model", "session_id", "permissionMode", "claude_code_version")})
        if ev.get("type") == "assistant" and first is None:
            first = time.time() - t0
        if ev.get("type") == "result":
            print(f"RESULT after {time.time()-t0:.1f}s (first assistant msg {first:.1f}s):", repr(ev.get("result")), "| session", ev.get("session_id"))
            return

send("Remember the codeword PLUM. Reply with just: OK")
time.sleep(GAP)
send("What codeword did I give you earlier? Reply with one word.")
p.stdin.close(); p.wait(timeout=30)
print("exit", p.returncode, "pid stayed one process:", p.pid)
