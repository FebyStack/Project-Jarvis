"""Shared runner: one stream-json `claude` child with the scrubbed env and the probe settings (spike only)."""
import json, os, queue, subprocess, sys, threading, time

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "01-brain"))
from clean import clean_env  # noqa: E402

TMP = os.path.join(here, "tmp")
BASE = ["claude", "-p", "--setting-sources", "project", "--settings", os.path.join(here, "probe-settings.json"),
        "--strict-mcp-config", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose"]


class Child:
    def __init__(self, name, args=(), env=None):
        for f in (f"{name}.jsonl", f"{name}-hooks.jsonl"):
            if os.path.exists(os.path.join(TMP, f)):
                os.remove(os.path.join(TMP, f))
        self.name, self.t0, self.q, self.events = name, time.time(), queue.Queue(), []
        self.hooklog = os.path.join(TMP, f"{name}-hooks.jsonl")
        self.p = subprocess.Popen(BASE + list(args), stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=here,
                                  env=clean_env() | {"PROBE_LOG": f"{name}-hooks.jsonl"} | (env or {}))
        self.log = open(os.path.join(TMP, f"{name}.jsonl"), "w")
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            if line.strip():
                ev = json.loads(line); ev["_t"] = round(time.time() - self.t0, 2)
                self.log.write(json.dumps(ev) + "\n"); self.log.flush(); self.q.put(ev)
        self.q.put(None)

    def t(self):
        return time.time() - self.t0

    def send(self, text):
        self.p.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n"); self.p.stdin.flush()

    def raw(self, obj):
        self.p.stdin.write(json.dumps(obj) + "\n"); self.p.stdin.flush()

    def next(self, timeout):
        try:
            ev = self.q.get(timeout=timeout)
        except queue.Empty:
            return "timeout"
        if ev is not None:
            self.events.append(ev)
        return ev

    def until(self, pred, timeout=300):
        """Read events until pred(ev) is true; return that event (None on exit/timeout)."""
        end = time.time() + timeout
        while time.time() < end:
            ev = self.next(max(0.1, end - time.time()))
            if ev is None or ev == "timeout":
                return None
            if pred(ev):
                return ev
        return None

    def result(self, timeout=300):
        return self.until(lambda e: e.get("type") == "result", timeout)

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        try:
            self.p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.p.kill()

    def hooks(self):
        if not os.path.exists(self.hooklog):
            return []
        return [json.loads(l) for l in open(self.hooklog)]


def tool_results(events):
    return [c for e in events if e.get("type") == "user" for c in (e["message"].get("content") or [])
            if isinstance(c, dict) and c.get("type") == "tool_result"]


def tool_uses(events):
    return [(e.get("parent_tool_use_id"), c) for e in events if e.get("type") == "assistant"
            for c in e["message"].get("content", []) if c.get("type") == "tool_use"]


def short(obj, n=300):
    s = json.dumps(obj) if not isinstance(obj, str) else obj
    return s.replace(os.path.expanduser("~"), "~")[:n]
