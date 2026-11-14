"""The warm `claude` child: stream-json in and out, each stream line turned into bridge events (plan 2, Task 7)."""
import asyncio
import contextlib
import json
import os
import signal
import time
import uuid
from collections.abc import Awaitable, Callable

from jarvis import config
from jarvis.brain.env import claude_argv, clean_env

RESTART_DELAY = 1.0
RESTARTS_PER_MINUTE = 3
STOP_GRACE = 3.0
LINE_LIMIT = 64 * 1024 * 1024  # one stream line can pass the 64 KiB default (commands_changed is ~65 KB)
LIMIT_STATUS = {"allowed": "ok", "allowed_warning": "near"}


def _get(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(c["text"] for c in content if isinstance(c, dict) and isinstance(c.get("text"), str))
    return ""


def _blocks(line: dict, block_type: str) -> list[dict]:
    content = _get(line, "message", "content")
    return [c for c in content if isinstance(c, dict) and c.get("type") == block_type] if isinstance(content, list) else []


def parse(line: dict) -> list[dict]:
    """Stream line → bridge events. Unknown or malformed lines give []; never raises (the stream is another program's)."""
    try:
        return _parse(line)
    except Exception:
        return []


def _parse(line) -> list[dict]:
    if not isinstance(line, dict):
        return []
    kind, sub = line.get("type"), line.get("subtype")
    if kind == "system" and sub == "init":
        return [{"kind": "init", "session_id": line.get("session_id"), "api_key_source": line.get("apiKeySource"),
                 "mcp_servers": line.get("mcp_servers") or []}]
    if kind == "system" and sub == "task_started" and line.get("subagent_type"):  # a background Bash task has none
        return [{"kind": "agent_start", "task_id": line.get("task_id"), "tool_use_id": line.get("tool_use_id"),
                 "agent": line["subagent_type"], "description": line.get("description"),
                 "background": bool(line.get("is_backgrounded"))}]
    if kind == "system" and sub == "task_progress":
        return [{"kind": "agent_progress", "task_id": line.get("task_id"), "description": line.get("description")}]
    if kind == "system" and sub == "task_notification":
        return [{"kind": "agent_done", "task_id": line.get("task_id"), "tool_use_id": line.get("tool_use_id"),
                 "status": line.get("status"), "summary": line.get("summary")}]
    if kind == "stream_event":
        delta = _get(line, "event", "delta")
        if (line.get("parent_tool_use_id") is None and _get(line, "event", "type") == "content_block_delta"
                and _get(delta, "type") == "text_delta" and isinstance(delta.get("text"), str)):
            return [{"kind": "delta", "text": delta["text"]}]
        return []
    if kind == "assistant":
        model, parent = _get(line, "message", "model"), line.get("parent_tool_use_id")
        return [{"kind": "tool", "id": b.get("id"), "name": b.get("name"), "input": b.get("input"), "model": model,
                 "parent": parent} for b in _blocks(line, "tool_use")]
    if kind == "user":
        return [{"kind": "tool_result", "tool_use_id": b.get("tool_use_id"), "text": _text(b.get("content")),
                 "parent": line.get("parent_tool_use_id")} for b in _blocks(line, "tool_result")]
    if kind == "rate_limit_event":
        info = line.get("rate_limit_info")
        if not isinstance(info, dict):
            return []
        return [{"kind": "limits", "status": LIMIT_STATUS.get(info.get("status"), "reached"),
                 "weekly": _get(info, "unifiedWindows", "seven_day", "utilization"), "resets_at": info.get("resetsAt")}]
    if kind == "result":
        text = line.get("result")
        return [{"kind": "turn", "text": text if isinstance(text, str) else "", "is_error": bool(line.get("is_error")),
                 "session_id": line.get("session_id"), "cancelled": False}]
    return []


class Bridge:
    """One `claude` child. Events go to `on_event`; a child that exits on its own is resumed (see `_supervise`)."""

    def __init__(self, on_event: Callable[[dict], None], memory_map: Callable[[], str], *,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        self._emit, self._memory_map, self._clock, self._sleep = on_event, memory_map, clock, sleep
        self._proc: asyncio.subprocess.Process | None = None
        self._task: asyncio.Task | None = None
        self._halt: str | None = None
        self._restarts: list[float] = []
        self._seen_init = self._interrupted = False
        self.session_id: str | None = None

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.returncode is None and self._halt is None

    async def start(self) -> None:
        self._halt, self._restarts = None, []
        await self._spawn(resume=None)
        self._task = asyncio.create_task(self._supervise())

    async def send(self, text: str) -> None:
        await self._write({"type": "user", "message": {"role": "user", "content": text}})

    async def interrupt(self) -> None:
        """Ends the current turn; the process and its session live on (Plan 2 probes, step 8)."""
        self._interrupted = True
        await self._write({"type": "control_request", "request_id": str(uuid.uuid4()), "request": {"subtype": "interrupt"}})

    async def reset(self) -> None:
        await self.stop()
        self.session_id = None
        await self.start()

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        proc = self._proc
        if proc is None:
            return
        if proc.returncode is None:
            with contextlib.suppress(Exception):
                proc.stdin.close()  # EOF lets claude save the session before it exits
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(proc.wait(), STOP_GRACE)
        self._kill(proc)
        await proc.wait()

    async def _spawn(self, resume: str | None) -> None:
        self._seen_init = self._interrupted = False
        self._proc = await asyncio.create_subprocess_exec(
            *claude_argv(self._memory_map(), resume=resume), stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, cwd=config.PROJECT, env=clean_env(),
            start_new_session=True, limit=LINE_LIMIT)

    async def _supervise(self) -> None:
        """Read the child; when it exits on its own, resume it after 1 s, at most 3 times a minute, then `down`."""
        while True:
            proc = self._proc
            async for raw in proc.stdout:
                self._handle(raw)
                if self._halt:
                    break
            self._kill(proc)
            await proc.wait()
            if self._halt:
                return self._emit({"kind": "down", "reason": self._halt})
            now = self._clock()
            self._restarts = [t for t in self._restarts if now - t < 60]
            if len(self._restarts) >= RESTARTS_PER_MINUTE:
                return self._emit({"kind": "down", "reason": "claude keeps exiting"})
            await self._sleep(RESTART_DELAY)
            self._restarts.append(self._clock())
            try:
                await self._spawn(resume=self.session_id)
            except Exception as e:  # e.g. the binary is gone, or ANTHROPIC_API_KEY appeared
                return self._emit({"kind": "down", "reason": f"cannot start claude: {e}"})

    def _handle(self, raw: bytes) -> None:
        try:
            line = json.loads(raw)
        except ValueError:
            return
        for ev in parse(line):
            if ev["kind"] == "init":
                if ev["api_key_source"] != "none":
                    self._halt = "api key in use"
                    return
                self.session_id = ev["session_id"] or self.session_id
                if self._seen_init:  # every turn starts with an init; only a process's first is a start
                    continue
                self._seen_init = True
            elif ev["kind"] == "turn":
                ev["cancelled"] = self._interrupted and line.get("subtype") == "error_during_execution"
                self._interrupted = False
                self.session_id = ev["session_id"] or self.session_id
            self._emit(ev)

    @staticmethod
    def _kill(proc: asyncio.subprocess.Process) -> None:
        """SIGKILL the child's whole process group (hook clients included)."""
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)

    async def _write(self, obj: dict) -> None:
        if not self.alive:
            raise RuntimeError("the brain is not running")
        self._proc.stdin.write(json.dumps(obj).encode() + b"\n")
        await self._proc.stdin.drain()
