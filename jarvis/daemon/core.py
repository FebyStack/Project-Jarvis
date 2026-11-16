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
from typing import Protocol

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
CHILD_DIED = "Claude stopped while answering. Ask me again."
SERVE_FAILED = "Something went wrong on my side while answering. Ask me again."
STOPPING = "Jarvis is stopping, so this one wasn't answered. Ask again once it's back."
OFFLINE = "I can't reach Claude right now. I'll answer when the connection is back."
VAULT_TOOLS = {"Read": "file_path", "Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path"}


class Speaker(Protocol):
    on_start: Callable[[], None]  # set by the core: the first sound of a run of speech is going out
    on_done: Callable[[], None]  # set by the core: speech ran out (also when there was nothing to say)

    def feed(self, delta: str) -> None: ...  # reply text as it streams
    def say(self, text: str) -> None: ...  # a complete reply
    def stop(self) -> None: ...  # silence now; forget what was queued
    def hold(self, on: bool) -> None: ...  # while on, start no new sound
    def cue(self) -> None: ...  # the listening tone


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
                 checklist: Callable[[], list[str]] = list, speaker: Speaker | None = None):
        self.vault, self.clock, self.now, self.run_scribe, self.checklist = vault, clock, now, run_scribe, checklist
        self.sm = StateMachine(clock)
        self.speaker = speaker
        if speaker:
            speaker.on_start, speaker.on_done = lambda: self._drive(Event.REPLY_START), self._spoke
        self._mic = "off"
        self._hearing: set[asyncio.Task] = set()  # requests started by heard(), kept so they are not collected
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
        self._offline = self._turn_open = self._cancelling = False
        self._unprompted_owner: str | None = None  # the request an unprompted turn belongs to, by id
        self._causes: deque[str] = deque()  # requests whose background worker ended and await their announcement
        self._sweep: tuple[Path, object] | None = None  # (day log, scribe process) of a running idle sweep
        self._down: str | None = None
        self._last_activity = clock()
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
        """Every open request is answered and recorded before the child stops, so nothing waits and nothing is lost."""
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        for a in self.asks.pending():
            self.asks.answer("no", ask_id=a.id)
        still_open = [r for r in (self._current, *self._pending, *self._waiting) if r]
        self._current, self._pending, self._waiting = None, [], deque()
        for req in still_open:
            req.tracker.abandon("jarvisd stopped")
            if req.waiters:
                self._resolve(req, STOPPING, False)
            try:
                req.tracker.finish(req.answer or "(not answered: jarvisd stopped)", self._confirmations(req))
            except Exception:
                log.exception("recording an open request on stop failed")
        await self.bridge.stop()

    async def _every_second(self) -> None:
        while True:
            await asyncio.sleep(1)
            try:
                await self.tick()
            except Exception:
                log.exception("tick failed")

    async def tick(self) -> None:
        self._drive(Event.TICK)
        now = self.clock()
        resets_at = self._limits.get("resets_at")
        if self._limits["status"] == "reached" and resets_at is not None and now >= resets_at:
            self._limits = {"status": "ok", "weekly": self._limits.get("weekly"), "resets_at": None}
            self._publish("limits", **self._limits)
            self._wake.set()
        # Quiet: no turn running, nothing queued, every request recorded (a worker's note waits for its announcement).
        quiet = self._current is None and not self._turn_open and not self._waiting and not self._pending
        if not self._reset_done and quiet and now - self._last_activity >= config.RESET_IDLE_SECONDS:
            self._reset_done = True
            await self.bridge.reset()
            log.info("conversation reset after %.0f s idle", now - self._last_activity)
        self._sweep_step(now, quiet)
        if self._waiting:  # e.g. the child came back after dying: nothing else would wake the queue
            self._wake.set()
        full = now >= self._next_check
        if full:
            self._next_check = now + CHECK_EVERY
            if self._offline and await reachable():
                self._offline = False
                self._wake.set()
        self._publish_health(full)

    def _sweep_step(self, now: float, quiet: bool) -> None:
        """The idle sweep: only when quiet and the brain is usable; a day log is marked swept only if scribe worked."""
        if self._sweep is not None:
            day, proc = self._sweep
            code = proc.poll() if proc is not None else 0
            if code is None:
                return
            self._sweep = None
            if code == 0:
                self.sweeper.mark(day)
            else:
                log.error("scribe sweep exited with %s", code)
                self.sweeper.retry_after = now + config.SWEEP_IDLE_SECONDS
            return
        usable = self._limits["status"] != "reached" and not self._offline and not self._down
        if (day := self.sweeper.due(now, self._last_activity, not (quiet and usable))) is not None:
            try:
                self._sweep = (day, self.run_scribe(self.vault, day))
            except Exception:
                log.exception("starting the scribe sweep failed")
                self.sweeper.retry_after = now + config.SWEEP_IDLE_SECONDS

    # ---- requests --------------------------------------------------------------------------------------------

    async def submit(self, text: str, channel: Channel) -> Reply:
        self._last_heard = text
        self._publish("heard", text=text, channel=channel)
        if channel == "mac":
            self._drive(Event.REQUEST)
        status = self.vault.status()
        if status != "ok":
            self._publish_health(full=True)
            return self._reply(channel, VAULT_SAYS[status], False)
        action = instant.match(text, pending=bool(self.asks.pending(channel)))
        if action:
            reply = await self._instant(action, channel)
            self.vault.log_exchange(Exchange(self.now(), channel, text, reply.say))
            self._last_activity = self.clock()
            return reply
        rid = str(next(self._ids))
        req = _Request(rid, text, channel, Tracker(self.vault, rid, channel, text, self.now()))
        fut = asyncio.get_running_loop().create_future()
        req.waiters.append(fut)
        self._waiting.append(req)
        self._last_activity, self._reset_done = self.clock(), False
        self._wake.set()
        self._publish_queue()
        if self._limits["status"] == "reached":
            return self._reply(channel, self._limit_sentence(), False)
        return await fut

    def _limit_sentence(self) -> str:
        at = self._limits.get("resets_at")
        when = datetime.fromtimestamp(at).strftime("%H:%M") if at is not None else "the reset"
        return f"I've hit the subscription limit. I'll pick this up when it resets at {when}."

    async def _instant(self, action: str, channel: Channel) -> Reply:
        match action:
            case "time":
                say = instant.say_time(self.now())
            case "date":
                say = instant.say_date(self.now())
            case "mute" | "unmute":
                self._drive(Event.MUTE if action == "mute" else Event.UNMUTE)
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
        """Stops the turn that is running and any background worker; queued requests stay queued."""
        self._drive(Event.CANCEL)
        if self.speaker:
            self.speaker.stop()
        mine = {r.id for r in (self._current, *self._pending) if r}
        for a in self.asks.pending():
            if a.request_id in mine:
                self.asks.answer("no", ask_id=a.id)
        if any(r.tracker.open_agents for r in (self._current, *self._pending) if r):
            self._cancelling = True
            await self.bridge.restart()  # the workers die with the child; it resumes the same conversation
        elif self._current is not None or self._turn_open:
            with contextlib.suppress(RuntimeError):
                await self.bridge.interrupt()

    async def _serve(self) -> None:
        """Serves requests one at a time, in arrival order, while the brain is usable."""
        while True:
            while (not self._waiting or self._turn_open or self._limits["status"] == "reached" or self._offline
                   or (not self.bridge.alive and not self._down)):  # a dead child comes back in a second: wait for it
                self._wake.clear()
                await self._wake.wait()
            req = self._waiting.popleft()
            try:
                await self._serve_one(req)
            except Exception:  # logged, never request text; the queue goes on
                log.exception("serving a request failed")
                if self._current is req:
                    self._current = None
                if req.waiters:
                    self._resolve(req, SERVE_FAILED, False)

    async def _serve_one(self, req: _Request) -> None:
        self._current = req
        self._publish_queue()
        self._publish_agents()
        try:
            self._sent_at, self._first_token = self.clock(), False
            await self.bridge.send(req.text)
        except RuntimeError:
            self._current = None
            self._resolve(req, NO_BRAIN, False)
            req.answer = NO_BRAIN
            req.tracker.abandon("Claude was not running")
            self._pending.append(req)
            return self._record_closed()
        await req.done.wait()
        ev = req.turn
        if ev["is_error"] and not ev["cancelled"]:
            if self._limits["status"] == "reached":  # run it again once the limit resets
                return self._requeue(req, self._limit_sentence())
            if not await reachable():
                self._offline = True
                self._requeue(req, OFFLINE)
                return self._publish_health()
        log.info("turn %.2f s", self.clock() - self._sent_at)
        text = "Cancelled." if ev["cancelled"] else ev["text"]
        req.tracker.feed(ev)
        req.answer = text
        self._agents = {k: a for k, a in self._agents.items() if a["background"]}
        self._current = None
        self._last_activity = self.clock()
        self._resolve(req, text, text.rstrip().endswith("?"), speak=not ev["cancelled"])  # cancel() said it already
        self._pending.append(req)
        self._record_closed()
        self._publish_queue()
        self._publish_agents()

    def _requeue(self, req: _Request, say: str) -> None:
        self._current = None
        req.done.clear()
        req.turn = None
        self._waiting.appendleft(req)
        self._resolve(req, say, False)

    def _resolve(self, req: _Request, text: str, loop: bool, speak: bool = True) -> None:
        self._reply(req.channel, text, loop, speak)
        waiters, req.waiters = req.waiters, []
        for f in waiters:
            if not f.done():
                f.set_result(Reply(text, loop))

    def _reply(self, channel: Channel, text: str, loop: bool, speak: bool = True) -> Reply:
        self._last_reply[channel] = text
        self._publish("reply", text=text, channel=channel, loop=loop)
        if channel == "mac" and speak:
            self.speaker.say(text) if self.speaker else self._spoke()  # no speaker: done at once
        return Reply(text, loop)

    def _record_closed(self) -> None:
        """Writes the vault record of every request whose turn and background workers are over."""
        for req in [r for r in self._pending if r.tracker.closed]:
            self._pending.remove(req)
            path = req.tracker.finish(req.answer, self._confirmations(req))
            if req.tracker.is_task:
                self.run_scribe(self.vault, path)

    def _confirmations(self, req: _Request) -> list[tuple[str, bool]]:
        return [(q, yes) for rid, q, yes in self.asks.history() if rid == req.id]

    def _owner(self, event: dict) -> _Request | None:
        """The request an event or hook call belongs to, always by id: the one whose agent it is, else the request
        whose turn is running, else the one whose finished worker the running unprompted turn announces."""
        if owner := next((r for r in self._pending if r.tracker.owns(event)), None):
            return owner
        if self._current is not None:
            return self._current
        return self._find(self._unprompted_owner) if self._turn_open and self._unprompted_owner else None

    def _turn_channel(self) -> Channel:
        """The channel of the running turn: its request's, or for a turn nobody asked for, its owner's or mac."""
        owner = self._find(self._unprompted_owner) if self._unprompted_owner else None
        req = self._current if self._in_flight() else owner
        return req.channel if req else "mac"

    def _in_flight(self) -> bool:
        return self._current is not None and not self._current.done.is_set()

    def _find(self, request_id: str) -> _Request | None:
        return next((r for r in [self._current, *self._pending, *self._waiting] if r and r.id == request_id), None)

    # ---- bridge events ---------------------------------------------------------------------------------------

    def _on_event(self, ev: dict) -> None:
        kind = ev.get("kind")
        if kind == "init":
            self._down = None
            log.info("brain online; %d MCP servers", len(ev.get("mcp_servers") or []))
        elif kind == "turn_start":
            if not self._in_flight():  # Claude started a turn of its own: a worker's announcement
                self._open_unprompted()
        elif kind == "exited":
            self._child_gone(CHILD_DIED, "Claude restarted")
        elif kind == "down":
            self._down = ev.get("reason")
            log.error("brain down: %s", self._down)
            self._child_gone(NO_BRAIN, "Claude stopped")
        elif kind == "limits":
            self._limits = {k: ev.get(k) for k in ("status", "weekly", "resets_at")}
            self._publish("limits", **self._limits)
            self._wake.set()
        elif kind == "delta":
            if not self._in_flight():
                self._open_unprompted()
            if not self._first_token:
                self._first_token = True
                log.info("first token %.2f s", self.clock() - self._sent_at)
            self._publish("reply_delta", text=ev["text"])
            if self.speaker and self._turn_channel() == "mac":
                self.speaker.feed(ev["text"])
        elif kind == "turn":
            if self._in_flight():
                self._current.turn = ev
                self._current.done.set()
            else:
                self._close_unprompted(ev.get("text") or "")
        else:
            if kind == "tool" and not ev.get("parent") and not self._in_flight():
                self._open_unprompted()
            self._track(ev)
        self._publish_health()

    def _track(self, ev: dict) -> None:
        owner = self._owner(ev)
        kind = ev.get("kind")
        ended = kind == "agent_done" and owner is not None and ev.get("task_id") in owner.tracker.open_agents
        if owner:
            owner.tracker.feed(ev)
        if ended and owner is not self._current:  # the front door will announce it in a turn of its own
            self._causes.append(owner.id)
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

    def _open_unprompted(self) -> None:
        """A turn nobody asked for has started: it belongs to the oldest request whose worker ended unannounced."""
        if self._turn_open:
            return
        self._turn_open, self._unprompted_owner = True, None
        while self._causes:
            rid = self._causes.popleft()
            if self._find(rid):
                self._unprompted_owner = rid
                break

    def _close_unprompted(self, text: str) -> None:
        """The front door's own turn ended, announcing a worker that finished."""
        self._open_unprompted()
        req = self._find(self._unprompted_owner) if self._unprompted_owner else None
        self._turn_open, self._unprompted_owner = False, None
        channel = req.channel if req else "mac"
        if req:
            req.answer += "\n\n" + text
        self._last_activity = self.clock()
        if text.strip():  # an empty turn (e.g. right after a restart) has nothing to say or log
            self._reply(channel, text, False)
            self.vault.log_exchange(Exchange(self.now(), channel, "(worker finished)", text))
        self._record_closed()
        self._publish_queue()
        self._wake.set()

    def _child_gone(self, say: str, why: str) -> None:
        """The child died or stopped: the turn in flight ends now, its workers are gone, and requests are recorded."""
        why = "cancelled" if self._cancelling else why
        cur = self._current
        if self._in_flight():
            cur.tracker.abandon(why)
            cur.turn = {"kind": "turn", "text": "Cancelled." if self._cancelling else say, "is_error": False,
                        "cancelled": self._cancelling, "session_id": None}
            cur.done.set()
        for req in self._pending:
            req.tracker.abandon(why)
        self._turn_open, self._unprompted_owner, self._cancelling = False, None, False
        self._causes.clear()
        self._agents = {}
        self._record_closed()
        self._publish_queue()
        self._publish_agents()
        self._wake.set()

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

    # ---- voice -----------------------------------------------------------------------------------------------

    def wake(self, key: bool = False) -> bool:
        """The name (WAKE) or the talk key (PUSH, which also cuts speech short). True if now listening."""
        if key and self.speaker and self.sm.state is State.SPEAKING:
            self.speaker.stop()
        self._drive(Event.PUSH if key else Event.WAKE)
        return self.sm.state is State.LISTENING

    def cue(self) -> None:
        if self.speaker:
            self.speaker.cue()

    def speech_started(self) -> None:
        self._drive(Event.SPEECH_START)

    def heard(self, text: str) -> None:
        """A spoken request; nothing heard leaves no trace. The reply is not awaited."""
        if not text.strip():
            return self.give_up()
        self._drive(Event.SPEECH_END)
        task = asyncio.create_task(self.submit(text, "mac"))
        self._hearing.add(task)
        task.add_done_callback(self._hearing.discard)

    def give_up(self) -> None:
        if self.sm.state is State.LISTENING:
            self._drive(Event.CANCEL)

    def level(self, rms: float) -> None:
        self._publish("level", rms=rms)

    def set_mic(self, word: str) -> None:
        self._mic = word
        self._publish_health()

    def _spoke(self) -> None:
        """Speech ran out: the turn goes on if a mac request is still running or about to be served."""
        blocked = self._limits["status"] == "reached" or self._offline  # its wait may be hours: don't sit in THINKING
        busy = [self._current] if self._current else []
        busy += [] if blocked else list(self._waiting)
        self._drive(Event.REPLY_PAUSE if any(r.channel == "mac" for r in busy) else Event.REPLY_END)

    def _drive(self, event: Event) -> None:
        """Feeds the state machine; a change publishes one state event and holds speech while listening."""
        was = (self.sm.state, self.sm.muted)
        self.sm.on(event)
        if (self.sm.state, self.sm.muted) == was:
            return
        listening = self.sm.state is State.LISTENING
        if self.speaker and listening != (was[0] is State.LISTENING):
            self.speaker.hold(listening)
        self._publish_state()

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
        return "online" if self.bridge.alive else "starting"  # its first init comes only with the first message

    def _health_body(self) -> dict:
        return {"brain": self._brain(), "vault": self.vault.status(), "mic": self._mic, "phone": "not linked",
                "awake": "n/a", "checklist": self.checklist()}

    def _publish_health(self, full: bool = False) -> None:
        """`full` re-reads the vault and the checklist (every CHECK_EVERY s); otherwise only the brain changes."""
        body = self._health_body() if full or not self._health else self._health | {"brain": self._brain(),
                                                                                       "mic": self._mic}
        if body != self._health:
            self._health = body
            self._publish("health", **body)

    def health(self) -> dict:
        return self._health_body()

    def _agent_rows(self) -> list[dict]:
        front = {"id": "jarvis", "name": "jarvis", "model": "sonnet", "since": self._last_activity,
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
