"""The real `jarvis face`, fed made-up jarvisd events, for the live probes P2, P3 and P8 (no jarvisd change needed).

Run: JARVIS_HOME=<scratch dir> uv run --frozen python spikes/10-face/demo.py <command-file>
Commands, one per line (the file is read and emptied every 0.2 s):
  add N            N more working workers          ask ID | work ID | done ID | stopped ID | failed ID
  clear            every worker gone               mode idle|listen|work|talk|muted    level X (0–1)
  nodaemon | back  jarvisd gone / back             cycle on|off   every 2 s one bead asks or stops asking (P8)
Clicks on Yes / No / Always / Stop are printed and acted on, as jarvisd would.
"""

import asyncio
import random
import sys
import time
from pathlib import Path

from jarvis.face import app

CMD = Path(sys.argv[1])
NAMES = ["Nova", "Orin", "Vesper", "Kite", "Lumen", "Juno", "Wren", "Talon"]
DOING = ["Running the test suite", "Reading the export code", "Searching the web for prices", "Writing the summary",
         "Checking the build", "Comparing two files", "Waiting for a download", "Drafting the reply"]


def row(i, state="working"):
    return {"id": f"t{i}", "name": "coder" if i % 2 else "researcher", "call": NAMES[i % len(NAMES)], "model": "opus",
            "doing": DOING[i % len(DOING)], "since": time.time(), "background": True, "title": "Fix export bug",
            "state": state, "question": None, "ask_id": None, "ask_until": None, "channel": "mac"}


class Demo:
    def __init__(self, token=None):
        self.rows, self.n, self.q, self.cycling = {}, 0, asyncio.Queue(), False

    def push(self):
        self.q.put_nowait({"type": "agents", "items": list(self.rows.values())})

    def set(self, rid, state):
        r = self.rows.get(rid)
        if not r:
            return
        asking = state == "needs_you"
        r.update(state=state, question='Run `git push origin main`? <img src=x onerror=alert(1)> ");alert(1)//' if asking else None,
                 ask_id="k" + rid if asking else None, ask_until=time.time() + 60 if asking else None)
        if state in ("done", "stopped", "failed"):
            asyncio.get_running_loop().call_later(8, lambda: (self.rows.pop(rid, None), self.push()))
        self.push()

    async def answer(self, reply, ask_id):
        print(f"{time.strftime('%T')} answer {reply} {ask_id}", flush=True)
        self.set(ask_id[1:], "working")

    async def stop(self, agent_id):
        print(f"{time.strftime('%T')} stop {agent_id}", flush=True)
        self.set(agent_id, "stopped")
        return {"stopped": True}

    async def cancel(self):
        pass

    def command(self, c):
        print(f"{time.strftime('%T')} cmd {' '.join(c)}", flush=True)
        if c[0] == "add":
            for _ in range(int(c[1])):
                self.rows[f"t{self.n}"] = row(self.n)
                self.n += 1
            self.push()
        elif c[0] in ("ask", "work", "done", "stopped", "failed"):
            self.set(c[1], {"ask": "needs_you", "work": "working"}.get(c[0], c[0]))
        elif c[0] == "clear":
            self.rows.clear()
            self.push()
        elif c[0] == "mode":
            voice = {"idle": "IDLE", "listen": "LISTENING", "work": "THINKING", "talk": "SPEAKING", "muted": "IDLE"}[c[1]]
            self.q.put_nowait({"type": "state", "voice": voice, "muted": c[1] == "muted"})
        elif c[0] == "level":
            self.q.put_nowait({"type": "level", "rms": float(c[1]), "source": "voice"})
        elif c[0] == "nodaemon":
            self.q.put_nowait({"type": "link", "state": "no daemon"})
        elif c[0] == "back":
            self.q.put_nowait({"type": "link", "state": "online"})
            self.push()
        elif c[0] == "cycle":
            self.cycling = c[1] == "on"

    async def events(self):
        yield {"type": "link", "state": "online"}
        loop, last = asyncio.get_running_loop(), 0.0

        async def feed():
            nonlocal last
            while True:
                await asyncio.sleep(0.2)
                text = CMD.read_text() if CMD.exists() else ""
                if text.strip():
                    CMD.write_text("")
                    for line in text.splitlines():
                        if line.split():
                            self.command(line.split())
                if self.cycling and time.time() - last > 2 and self.rows:
                    last = time.time()
                    rid = random.choice([k for k, r in self.rows.items() if r["state"] in ("working", "needs_you")] or [None])
                    if rid:
                        self.set(rid, "working" if self.rows[rid]["state"] == "needs_you" else "needs_you")

        loop.create_task(feed())
        while True:
            yield await self.q.get()


app.Client = Demo
app.load_token = lambda home: ""
app.run()
