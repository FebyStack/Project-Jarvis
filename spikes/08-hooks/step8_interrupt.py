"""Step 8: interrupt a long streaming reply with a control_request on stdin. Turn ends <2 s, process lives, memory kept?"""
import uuid
from probe import Child, short

c = Child("step8", ["--model", "sonnet", "--include-partial-messages"])
c.send("Count from 1 to 400, writing each number as an English word, one per line. No other text.")
first = c.until(lambda e: e.get("type") == "stream_event" and e["event"].get("type") == "content_block_delta", 120)
print(f"first text delta at {first and first['_t']}s")
while c.t() < first["_t"] + 3:
    c.next(0.2)
rid = str(uuid.uuid4()); ti = c.t()
c.raw({"type": "control_request", "request_id": rid, "request": {"subtype": "interrupt"}})
r = c.result(30)
print(f"interrupt sent at {ti:.2f}s; result at {r and r['_t']}s ({(r['_t'] - ti) if r else None:.2f}s) subtype={r and r.get('subtype')}")
resp = [e for e in c.events if e.get("type") == "control_response"]
print("  control_response:", short(resp, 300))
print("  alive after interrupt:", c.p.poll() is None, "| session:", r and r.get("session_id"))
c.send("What did I ask you to do in my first message? One line.")
r2 = c.result(120)
print("  follow-up reply:", short(r2 and r2.get("result"), 200), "| same session:", r2 and r2.get("session_id") == r.get("session_id"))
c.close()
