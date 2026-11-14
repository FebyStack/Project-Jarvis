"""The `Jarvis` object at the heart of jarvisd: request queue, instant answers, the bridge, hook decisions,
limits, reset and the event bus (plan 2, Task 10)."""
import asyncio
import contextlib
import itertools
import logging
from collections import deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from jarvis import config
from jarvis.brain.asks import Asks
from jarvis.brain.judge import judge, load_config
from jarvis.daemon import instant
from jarvis.daemon.exchange import FREE_AGENTS, NEED_TRIAGE, Tracker, agent_model
from jarvis.daemon.state import Event, State, StateMachine
from jarvis.memory import scribe
from jarvis.memory.scribe import Sweeper
from jarvis.memory.vault import Channel, Exchange, Vault

log = logging.getLogger("jarvisd")

CHECK_EVERY = 30.0  # seconds between offline re-tries and vault checks
VAULT_SAYS = {"missing": "The vault is missing, so I can't keep notes. Fix the vault and ask again.",
              "read-only": "The vault is read-only, so I can't keep notes. Fix the vault and ask again."}
NO_BRAIN = "Claude isn't running, so I can't do that now."
OFFLINE = "I can't reach Claude right now. I'll answer when the connection is back."
VAULT_TOOLS = {"Read": "file_path", "Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path"}


@dataclass
class Reply:
    say: str
    loop: bool


@dataclass(eq=False)
class _Request:
    id: str
    text: str
    channel: Channel
    tracker: Tracker
    waiters: list[asyncio.Future] = field(default_factory=list)
    turn: dict | None = None
    done: asyncio.Event = field(default_factory=asyncio.Event)
    answer: str = ""


async def reachable(host: str = "api.anthropic.com", port: int = 443) -> bool:
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), 5)
    except (OSError, TimeoutError):
        return False
    writer.close()
    return True


class Jarvis:
    def __init__(self, vault: Vault, bridge_factory, clock: Callable[[], float], now: Callable[[], datetime],
                 ask_timeouts: dict[str, float] = config.ASK_TIMEOUT,
                 run_scribe: Callable[[Vault, Path], None] = scribe.run,
                 checklist: Callable[[], list[str]] = list):
        self.vault, self.clock, self.now, self.run_scribe, self.checklist = vault, clock, now, run_scribe, checklist
        self.sm = StateMachine(clock)
        self.gate = load_config()
        self.asks = Asks(self.gate.trusted, ask_timeouts, self._asks_changed)
        self.bridge = bridge_factory(self._on_event, vault.memory_map)
        self.sweeper = Sweeper(vault, config.HOME_DIR)
        self._ids = itertools.count(1)
        self._waiting: deque[_Request] = deque()
        self._wake = asyncio.Event()
        self._current: _Request | None = None
        self._pending: list[_Request] = []  # turn over, background workers still running
        self._subs: list[asyncio.Queue] = []
        self._agents: dict[str, dict] = {}  # task id -> HUD row, plus "_tu" (its Agent tool_use_id)
        self._memory: deque[dict] = deque(maxlen=50)  # newest first
        self._limits = {"status": "ok", "weekly": None, "resets_at": None}
        self._init_seen = self._offline = False
        self._down: str | None = None
        self._last_request = clock()
        self._reset_done = True
        self._next_check = 0.0
        self._health: dict = {}
        self._last_reply: dict[str, str] = {}
        self._last_heard = ""
        self._announced: set[str] = set()
        self._tasks: list[asyncio.Task] = []
        self._sent_at = 0.0
        self._first_token = False

    # ---- lifecycle -------------------------------------------------------------------------------------------

    @property
    def state(self) -> State:
        return self.sm.state

    async def start(self) -> None:
        await self.bridge.start()
        self._tasks = [asyncio.create_task(self._serve()), asyncio.create_task(self._every_second())]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.bridge.stop()

    async def _every_second(self) -> None:
        while True:
            await asyncio.sleep(1)
            try:
                await self.tick()
            except Exception:
                log.exception("tick failed")

    async def tick(self) -> None:
        now = self.clock()
        resets_at = self._limits.get("resets_at")
        if self._limits["status"] == "reached" and resets_at is not None and now >= resets_at:
            self._limits = {"status": "ok", "weekly": self._limits.get("weekly"), "resets_at": None}
            self._publish("limits", **self._limits)
            self._wake.set()
        busy = self._current is not None or bool(self._waiting) or any(r.tracker.open_agents for r in self._pending)
        if (not self._reset_done and now - self._last_request >= config.RESET_IDLE_SECONDS
                and not any(r.tracker.open_agents for r in self._pending)):
            self._reset_done = True
            await self.bridge.reset()
            log.info("conversation reset after %.0f s idle", now - self._last_request)
        if (day := self.sweeper.due(now, self._last_request, busy)) is not None:
            self.run_scribe(self.vault, day)
            self.sweeper.mark(day)
        full = now >= self._next_check
        if full:
            self._next_check = now + CHECK_EVERY
            if self._offline and await reachable():
                self._offline = False
                self._wake.set()
        self._publish_health(full)

    # ---- requests --------------------------------------------------------------------------------------------

    async def submit(self, text: str, channel: Channel) -> Reply:
        self._last_heard = text
        self._publish("heard", text=text, channel=channel)
        status = self.vault.status()
        if status != "ok":
            self._publish_health(full=True)
            return self._reply(channel, VAULT_SAYS[status], False)
        action = instant.match(text, pending=bool(self.asks.pending(channel)))
        if action:
            reply = await self._instant(action, channel)
            self.vault.log_exchange(Exchange(self.now(), channel, text, reply.say))
            return reply
        rid = str(next(self._ids))
        req = _Request(rid, text, channel, Tracker(self.vault, rid, channel, text, self.now()))
        fut = asyncio.get_running_loop().create_future()
        req.waiters.append(fut)
        self._waiting.append(req)
        self._last_request, self._reset_done = self.clock(), False
        self._wake.set()
        self._publish_queue()
        if self._limits["status"] == "reached":
            at = self._limits.get("resets_at")
            when = datetime.fromtimestamp(at).strftime("%H:%M") if at is not None else "the reset"
            return self._reply(channel, f"I've hit the subscription limit. I'll pick this up when it resets at {when}.", False)
        return await fut

    async def _instant(self, action: str, channel: Channel) -> Reply:
        match action:
            case "time":
                say = instant.say_time(self.now())
            case "date":
                say = instant.say_date(self.now())
            case "mute" | "unmute":
                self.sm.on(Event.MUTE if action == "mute" else Event.UNMUTE)
                self._publish_state()
                say = "Mic off." if action == "mute" else "Mic on."
            case "cancel":
                await self.cancel()
                say = "Cancelled."
            case "repeat":
                say = self._last_reply.get(channel, "Nothing to repeat.")
            case "status":
                say = self._status_sentence()
            case _:  # yes, no, always
                ask = self.asks.answer(action, channel=channel)
                if ask is None and len(waiting := self.asks.pending(channel)) > 1:
                    return self._reply(channel, f"{len(waiting)} questions are waiting, so I won't guess which one you "
                                                "mean. Answer each in the HUD.", False)
                req = self._current if ask and self._current and ask.request_id == self._current.id else None
                if req is None:  # no turn will follow: a background worker's or another session's question
                    return self._reply(channel, "Okay.", False)
                fut = asyncio.get_running_loop().create_future()
                req.waiters.append(fut)
                return await fut
        return self._reply(channel, say, False)

    def answer(self, reply: str, channel: Channel | None = None, ask_id: str | None = None) -> bool:
        return self.asks.answer(reply, channel=channel, ask_id=ask_id) is not None

    async def cancel(self) -> None:
        self.sm.on(Event.CANCEL)
        self._publish_state()
        req = self._current
        if req is None:
            return
        for a in self.asks.pending():
            if a.request_id == req.id:
                self.asks.answer("no", ask_id=a.id)
        with contextlib.suppress(RuntimeError):
            await self.bridge.interrupt()

    async def _serve(self) -> None:
        """Serves requests one at a time, in arrival order, while the brain is usable."""
        while True:
            while not self._waiting or self._limits["status"] == "reached" or self._offline:
                self._wake.clear()
                await self._wake.wait()
            req = self._waiting.popleft()
            self._current = req
            self._publish_queue()
            self._publish_agents()
            try:
                self._sent_at, self._first_token = self.clock(), False
                await self.bridge.send(req.text)
            except RuntimeError:
                self._current = None
                self._resolve(req, NO_BRAIN, False)
                continue
            await req.done.wait()
            ev = req.turn
            if ev["is_error"] and not ev["cancelled"] and not await reachable():
                self._offline = True
                self._current = None
                req.done.clear()
                self._waiting.appendleft(req)
                self._resolve(req, OFFLINE, False)
                self._publish_health()
                continue
            log.info("turn %.2f s", self.clock() - self._sent_at)
            text = "Cancelled." if ev["cancelled"] else ev["text"]
            req.tracker.feed(ev)
            req.answer = text
            self._agents = {k: a for k, a in self._agents.items() if a["background"]}
            self._current = None
            self._resolve(req, text, text.rstrip().endswith("?"))
            self._pending.append(req)
            self._record_closed()
            self._publish_queue()
            self._publish_agents()

    def _resolve(self, req: _Request, text: str, loop: bool) -> None:
        self._reply(req.channel, text, loop)
        waiters, req.waiters = req.waiters, []
        for f in waiters:
            if not f.done():
                f.set_result(Reply(text, loop))

    def _reply(self, channel: Channel, text: str, loop: bool) -> Reply:
        self._last_reply[channel] = text
        self._publish("reply", text=text, channel=channel, loop=loop)
        return Reply(text, loop)

    def _record_closed(self) -> None:
        """Writes the vault record of every request whose turn and background workers are over."""
        for req in [r for r in self._pending if r.tracker.closed]:
            self._pending.remove(req)
            confirmations = [(q, yes) for rid, q, yes in self.asks.history() if rid == req.id]
            path = req.tracker.finish(req.answer, confirmations)
            if req.tracker.is_task:
                self.run_scribe(self.vault, path)

    def _owner(self, event: dict) -> _Request | None:
        """The request an event or hook call belongs to: the one whose agent it is, else the current request, else
        the latest open one (the front door also acts in turns nobody prompted, e.g. after a background triage)."""
        return (next((r for r in self._pending if r.tracker.owns(event)), None) or self._current
                or (self._pending[-1] if self._pending else None))

    def _find(self, request_id: str) -> _Request | None:
        return next((r for r in [self._current, *self._pending, *self._waiting] if r and r.id == request_id), None)

    # ---- bridge events ---------------------------------------------------------------------------------------

    def _on_event(self, ev: dict) -> None:
        kind = ev.get("kind")
        if kind == "init":
            self._init_seen, self._down = True, None
            log.info("brain online; %d MCP servers", len(ev.get("mcp_servers") or []))
        elif kind == "down":
            self._down = ev.get("reason")
            log.error("brain down: %s", self._down)
            if self._current and not self._current.done.is_set():
                self._current.turn = {"kind": "turn", "text": NO_BRAIN, "is_error": False, "cancelled": False}
                self._current.done.set()
        elif kind == "limits":
            self._limits = {k: ev.get(k) for k in ("status", "weekly", "resets_at")}
            self._publish("limits", **self._limits)
            self._wake.set()
        elif kind == "delta":
            if not self._first_token:
                self._first_token = True
                log.info("first token %.2f s", self.clock() - self._sent_at)
            self._publish("reply_delta", text=ev["text"])
        elif kind == "turn":
            if self._current and not self._current.done.is_set():
                self._current.turn = ev
                self._current.done.set()
            else:
                self._unprompted(ev.get("text") or "")
        else:
            self._track(ev)
        self._publish_health()

    def _track(self, ev: dict) -> None:
        owner = self._owner(ev)
        if owner:
            owner.tracker.feed(ev)
        kind = ev.get("kind")
        if kind == "agent_start":
            self._agents[ev["task_id"]] = {"id": ev["task_id"], "name": ev["agent"], "model": agent_model(ev["agent"]),
                                           "doing": ev.get("description") or "", "since": self.clock(),
                                           "background": bool(ev.get("background")), "_tu": ev.get("tool_use_id")}
        elif kind == "agent_progress" and ev.get("task_id") in self._agents:
            self._agents[ev["task_id"]]["doing"] = ev.get("description") or ""
        elif kind == "agent_done" and self._agents.get(ev.get("task_id"), {}).get("background"):
            del self._agents[ev["task_id"]]
        elif kind == "tool" and ev.get("parent"):
            for a in self._agents.values():
                if a["_tu"] == ev["parent"] and ev.get("model"):
                    a["model"] = ev["model"]
        elif kind == "tool_result" and owner and owner.tracker.verdict:
            for a in self._agents.values():
                if a["name"] == "triage":
                    a["doing"] = owner.tracker.verdict.why
            self._publish_queue()
        self._publish_agents()

    def _unprompted(self, text: str) -> None:
        """A turn nobody asked for: the front door announcing a worker that finished."""
        req = self._owner({})
        channel = req.channel if req else "mac"
        if req:
            req.answer += "\n\n" + text
        self._reply(channel, text, False)
        self.vault.log_exchange(Exchange(self.now(), channel, "(worker finished)", text))
        self._record_closed()
        self._publish_queue()

    # ---- hooks -----------------------------------------------------------------------------------------------

    async def hook(self, payload: dict) -> dict:
        tool, inp = payload.get("tool_name") or "", payload.get("tool_input") or {}
        cwd = Path(payload.get("cwd") or config.PROJECT)
        req = None
        if payload.get("session_id") == self.bridge.session_id:
            req = self._owner({"task_id": payload.get("agent_id")})
        decision = judge(tool, inp, cwd, self.gate)
        if decision.verdict == "never":
            return {"verdict": "deny", "reason": decision.reason}
        if decision.verdict == "allow" and tool in ("Agent", "Task"):
            sub = inp.get("subagent_type") or "general-purpose"
            ok, why = req.tracker.may_dispatch(sub) if req else (sub in FREE_AGENTS, NEED_TRIAGE)
            if not ok:
                return {"verdict": "deny", "reason": why}
        if decision.verdict == "ask":
            channel = req.channel if req else "mac"
            loop = asyncio.get_running_loop()
            started = loop.time()
            if not await self.asks.ask(decision, channel, req.id if req else ""):
                late = loop.time() - started >= self.asks.timeouts[channel]
                return {"verdict": "deny", "reason": "No answer in time, so no." if late else "Febriel said no."}
        self._memory_event(tool, inp, cwd)
        return {"verdict": "allow", "reason": decision.reason}

    def _memory_event(self, tool: str, inp: dict, cwd: Path) -> None:
        raw = inp.get(VAULT_TOOLS.get(tool, ""))
        if not isinstance(raw, str):
            return
        path = Path(raw).expanduser()
        path = path if path.is_absolute() else cwd / path
        try:
            rel = str(path.resolve().relative_to(self.vault.root.resolve()))
        except (ValueError, OSError):
            return
        op = "r" if tool == "Read" else "~" if path.exists() else "+"
        self._memory.appendleft({"op": op, "path": rel})
        self._publish("memory", op=op, path=rel)

    def _asks_changed(self) -> None:
        for a in self.asks.pending():
            if a.id in self._announced:
                continue
            self._announced.add(a.id)
            req = self._find(a.request_id)
            if req:
                self._resolve(req, a.question, True)
            else:
                self._reply(a.channel, a.question, True)
        self._publish_queue()

    # ---- events ----------------------------------------------------------------------------------------------

    async def subscribe(self) -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.append(q)
        try:
            yield self._event("snapshot", state=self._state_body(), agents=self._agent_rows(),
                              queue=self._queue_rows(), memory=list(self._memory), limits=dict(self._limits),
                              health=self._health_body(), last_heard=self._last_heard)
            while True:
                yield await q.get()
        finally:
            self._subs.remove(q)

    def _event(self, type_: str, **body) -> dict:
        return {"type": type_, "at": self.now().isoformat(timespec="seconds"), **body}

    def _publish(self, type_: str, **body) -> None:
        ev = self._event(type_, **body)
        for q in self._subs:
            q.put_nowait(ev)

    def _state_body(self) -> dict:
        return {"voice": self.sm.state.name, "muted": self.sm.muted}

    def _publish_state(self) -> None:
        self._publish("state", **self._state_body())

    def _brain(self) -> str:
        if self._down:
            return "down"
        if self._limits["status"] == "reached":
            return "limit"
        if self._offline:
            return "offline"
        return "online" if self._init_seen or self.bridge.alive else "starting"  # init comes with the first message

    def _health_body(self) -> dict:
        return {"brain": self._brain(), "vault": self.vault.status(), "mic": "off", "phone": "not linked",
                "awake": "n/a", "checklist": self.checklist()}

    def _publish_health(self, full: bool = False) -> None:
        """`full` re-reads the vault and the checklist (every CHECK_EVERY s); otherwise only the brain changes."""
        body = self._health_body() if full or not self._health else self._health | {"brain": self._brain()}
        if body != self._health:
            self._health = body
            self._publish("health", **body)

    def health(self) -> dict:
        return self._health_body()

    def _agent_rows(self) -> list[dict]:
        front = {"id": "jarvis", "name": "jarvis", "model": "sonnet", "since": self._last_request,
                 "doing": "working on your request" if self._current else "idle", "background": False}
        return [front] + [{k: v for k, v in a.items() if k != "_tu"} for a in self._agents.values()]

    def _publish_agents(self) -> None:
        self._publish("agents", items=self._agent_rows())

    @staticmethod
    def _title(req: _Request) -> str:
        v = req.tracker.verdict
        return v.title if v else " ".join(req.text.split())[:60]

    def _queue_rows(self) -> list[dict]:
        rows = []
        for req, status in ([(self._current, "running")] if self._current else []) + \
                [(r, "running") for r in self._pending] + [(r, "waiting") for r in self._waiting]:
            row = {"id": req.id, "title": self._title(req), "status": status}
            if a := next((a for a in self.asks.pending() if a.request_id == req.id), None):
                row |= {"status": "needs_you", "question": a.question, "ask_id": a.id}
            rows.append(row)
        known = {r["id"] for r in rows}
        rows += [{"id": f"ask-{a.id}", "title": "a question", "status": "needs_you", "question": a.question,
                  "ask_id": a.id} for a in self.asks.pending() if a.request_id not in known]
        return rows

    def _publish_queue(self) -> None:
        self._publish("queue", items=self._queue_rows())

    def _status_sentence(self) -> str:
        running = [self._title(r) for r in ([self._current] if self._current else []) + self._pending]
        parts = [f"Working on {', '.join(running)}."] if running else []
        if self._waiting:
            parts.append(f"{len(self._waiting)} waiting.")
        if n := len(self.asks.pending()):
            parts.append(f"{n} {'needs' if n == 1 else 'need'} your yes.")
        return " ".join(parts) or "Nothing is running."
