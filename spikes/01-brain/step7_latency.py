"""Spike 1 step 7: send-to-first-text-token latency, ten runs, one warm stream-json process."""
import json, os, queue, statistics, subprocess, threading, time
from clean import clean_env
here = os.path.dirname(os.path.abspath(__file__))
T = time.time()
p = subprocess.Popen(["claude", "-p", "--model", "sonnet", "--setting-sources", "project", "--input-format", "stream-json",
                      "--output-format", "stream-json", "--verbose", "--include-partial-messages"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=here, env=clean_env())
q = queue.Queue()
threading.Thread(target=lambda: [q.put(json.loads(l)) for l in p.stdout], daemon=True).start()
firsts, totals = [], []
for i in range(10):
    p.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": f"Say hello in three words. ({i})"}}) + "\n"); p.stdin.flush()
    t0 = time.time(); first = None
    while True:
        ev = q.get(timeout=120)
        if first is None and ev.get("type") == "stream_event" and ev["event"].get("type") == "content_block_delta" \
                and ev["event"].get("delta", {}).get("type") == "text_delta":
            first = time.time() - t0
        if ev.get("type") == "result":
            totals.append(time.time() - t0); break
    firsts.append(first)
    print(f"run {i}: first token {first:.2f}s, done {totals[-1]:.2f}s" + ("  (includes process start)" if i == 0 else ""))
p.stdin.close(); p.wait(timeout=30)
warm = firsts[1:]
print(f"first-token median (all 10) {statistics.median(firsts):.2f}s | warm runs 2-10: median {statistics.median(warm):.2f}s, min {min(warm):.2f}s, max {max(warm):.2f}s")
