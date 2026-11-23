"""P4-P6: naming a worker through the hook's updatedInput, refusing one worker's calls, ending one worker.

Run from this folder: python3 agents.py p4|p5|p6   (logs in tmp/)
"""
import json, os, queue, subprocess, sys, threading, time, uuid

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "01-brain"))
from clean import clean_env  # noqa: E402

TMP = os.path.join(here, "tmp")
BASE = ["claude", "-p", "--agent", "jarvis", "--model", "sonnet", "--setting-sources", "project",
        "--settings", os.path.join(here, "probe-settings.json"), "--strict-mcp-config",
        "--input-format", "stream-json", "--output-format", "stream-json", "--verbose"]


class Child:
    def __init__(self, name, env=None):
        for f in ("deny.txt", "names.txt", f"{name}.jsonl", f"{name}-hooks.jsonl"):
            if os.path.exists(os.path.join(TMP, f)):
                os.remove(os.path.join(TMP, f))
        self.name, self.t0, self.q, self.events = name, time.time(), queue.Queue(), []
        self.hooklog = os.path.join(TMP, f"{name}-hooks.jsonl")
        self.p = subprocess.Popen(BASE, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=here,
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

    def raw(self, obj):
        self.p.stdin.write(json.dumps(obj) + "\n"); self.p.stdin.flush()

    def send(self, text):
        self.raw({"type": "user", "message": {"role": "user", "content": text}})

    def pump(self, seconds, stop=lambda: False):
        end = time.time() + seconds
        while time.time() < end and not stop():
            try:
                ev = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            if ev is None:
                return
            self.events.append(ev)

    def hooks(self):
        return [json.loads(l) for l in open(self.hooklog)] if os.path.exists(self.hooklog) else []

    def sys(self, sub):
        return [e for e in self.events if e.get("type") == "system" and e.get("subtype") == sub]

    def close(self):
        try:
            self.p.stdin.close(); self.p.wait(timeout=20)
        except Exception:
            self.p.kill()


def short(o, n=300):
    return (json.dumps(o) if not isinstance(o, str) else o)[:n]


def texts(c, parent=None):
    """Text the front door (parent None) or a worker (its tool_use_id) wrote."""
    out = []
    for e in c.events:
        if e.get("type") == "assistant" and e.get("parent_tool_use_id") == parent:
            out += [b["text"] for b in e["message"].get("content", []) if b.get("type") == "text"]
    return out


def p4():
    for bg in (False, True):
        c = Child(f"p4-{'bg' if bg else 'fg'}", {"PROBE_RENAME": "1"})
        c.send(f"Use the Agent tool once: subagent_type `namer`, run_in_background {str(bg).lower()}, "
               f"description \"count files\", prompt \"Run: ls | wc -l. Report the count.\" "
               f"When it has reported, tell me in one line what it found.")
        c.pump(240, lambda: len([e for e in c.events if e.get("type") == "result"]) >= (2 if bg else 1)
               and (not bg or c.sys("task_notification")))
        c.pump(15 if bg else 0)
        c.close()
        print(f"=== P4 {'background' if bg else 'foreground'}")
        for h in c.hooks():
            if h["payload"].get("tool_name") == "Agent":
                print("  hook in :", short(h["payload"]["tool_input"], 200))
                print("  hook out:", short(h["reply"]["hookSpecificOutput"].get("updatedInput"), 200))
        for e in c.sys("task_started"):
            print("  task_started:", short({k: e.get(k) for k in ("task_id", "tool_use_id", "description", "subagent_type")}, 300))
        tid = [b["id"] for e in c.events if e.get("type") == "assistant" for b in e["message"].get("content", []) if b.get("type") == "tool_use" and b["name"] == "Agent"]
        for e in c.events:   # the prompt the worker actually got
            if e.get("type") == "user" and e.get("parent_tool_use_id") in tid:
                cont = e["message"].get("content")
                if isinstance(cont, str) or (isinstance(cont, list) and any(b.get("type") == "text" for b in cont)):
                    print("  worker got:", short(cont, 200))
        for t in tid:
            print("  worker said:", short(texts(c, t), 300))
        print("  front door said:", short(texts(c), 600))
        for e in c.sys("task_notification"):
            print("  task_notification:", short({k: e.get(k) for k in ("task_id", "status", "summary")}, 300))


def two_sleepers(name):
    c = Child(name)
    c.send("Use the Agent tool twice in one message, both subagent_type `sleeper` with run_in_background true: "
           "description \"sleeper A\", prompt \"Start.\"; and description \"sleeper B\", prompt \"Start.\". "
           "Then say only: started.")
    def both():
        ids = {h["payload"].get("agent_id") for h in c.hooks() if h["payload"].get("tool_name") == "Bash"}
        return len(ids - {None}) >= 2
    c.pump(180, both)
    c.pump(3)
    started = {e["description"]: e for e in c.sys("task_started")}
    first_agent = next(h["payload"]["agent_id"] for h in c.hooks() if h["payload"].get("tool_name") == "Bash")
    return c, started, first_agent


def report_after(c, T, victim):
    print("  task_started:", short([{k: e.get(k) for k in ("task_id", "tool_use_id", "description")} for e in c.sys("task_started")], 500))
    for h in c.hooks():
        p = h["payload"]
        if p.get("tool_name") == "Bash" and h["t"] > T:
            print(f"   +{h['t'] - T:6.1f}s Bash from {p.get('agent_id')} -> {h['reply']['hookSpecificOutput']['permissionDecision']}")
    for e in c.sys("task_notification"):
        print(f"  task_notification t={e['_t'] - (T - c.t0):.1f}s after: task={e.get('task_id')} status={e.get('status')} summary={short(e.get('summary'), 120)}")
    print("  victim agent_id:", victim)
    print("  front door said after:", short([e for e in texts(c)], 800))


def p5():
    c, started, victim = two_sleepers("p5")
    T = time.time()
    open(os.path.join(TMP, "deny.txt"), "w").write(victim + "\n")
    print(f"=== P5: denying every call from {victim} at {T - c.t0:.1f}s")
    c.pump(150, lambda: len(c.sys("task_notification")) >= 2)
    c.pump(10)
    c.close()
    report_after(c, T, victim)


def p6():
    c, started, victim = two_sleepers("p6")
    # which task is the victim's? the hook payload's agent_id is matched to task_started's task_id if they agree
    tasks = [e.get("task_id") for e in c.sys("task_started")]
    print("=== P6: task ids", tasks, "victim agent_id", victim, "agent_id is a task id:", victim in tasks)
    task = victim if victim in tasks else tasks[0]
    T = time.time()
    rid = str(uuid.uuid4())
    c.raw({"type": "control_request", "request_id": rid, "request": {"subtype": "stop_task", "task_id": task}})
    c.pump(5, lambda: any(e.get("type") == "control_response" for e in c.events))
    resp = [e for e in c.events if e.get("type") == "control_response"]
    print("  stop_task control_response:", short(resp, 400))
    ok = resp and resp[-1].get("response", {}).get("subtype") == "success"
    c.pump(12, lambda: any(e.get("task_id") == task for e in c.sys("task_notification")))
    ended = any(e.get("task_id") == task for e in c.sys("task_notification"))
    print(f"  ended by control request: {ended} ({time.time() - T:.1f}s)")
    if not ended:
        T2 = time.time()
        print("  sending the notice instead")
        c.send(f"[jarvisd] Febriel stopped sleeper A (task {task}). End that agent and say nothing.")
        c.pump(30, lambda: any(e.get("task_id") == task for e in c.sys("task_notification")))
        print(f"  ended by notice: {any(e.get('task_id') == task for e in c.sys('task_notification'))} ({time.time() - T2:.1f}s)")
    c.pump(150, lambda: len(c.sys("task_notification")) >= 2)
    c.pump(10)
    c.close()
    report_after(c, T, victim)
    print("  front door tool calls:", short([b["name"] + ":" + short(b["input"], 80) for e in c.events if e.get("type") == "assistant"
                                            and e.get("parent_tool_use_id") is None for b in e["message"].get("content", []) if b.get("type") == "tool_use"], 600))


{"p4": p4, "p5": p5, "p6": p6}[sys.argv[1]]()
