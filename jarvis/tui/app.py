"""The gold terminal HUD: a thin client of jarvisd that redraws one View (spec §7)."""

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import aiohttp
from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from jarvis import config
from jarvis.tui.model import LEVELS, MIC_ON, View, elapsed, needs_you, reduce

SKILLS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "skills"
ACTIVE, IDLE = "#FFD700", "#8A7424"
MARKS = {"running": ("▶", "running", ACTIVE), "waiting": ("◦", "waiting", IDLE), "needs_you": ("?", "NEEDS YOU", f"bold {ACTIVE}")}
OFF_WORDS = {"", "off", "n/a", "not linked"}
BARS = "▁▂▃▄▅▆▇█"
NOTICES = {
    "starting": "STARTING UP",
    "offline": "OFFLINE: no connection to Claude",
    "vault": "VAULT MISSING: Jarvis is refusing requests until the vault is back",
    "first-run": "FIRST RUN: still to do",
    "no-daemon": "NO DAEMON: start it with: jarvis daemon",
}


ANSWER_DELAY = 0.4  # seconds a lone y/n/a waits for a second letter before it counts as an answer


class Client:
    """jarvisd's local API (Task 11) on the `mac` channel. Errors mean the daemon is away; the HUD shows that."""

    def __init__(self, token: str, base: str = f"http://127.0.0.1:{config.PORT}", retry: float = 2.0):
        self.base, self.retry = base, retry
        self.headers = {"Authorization": f"Bearer {token}"}
        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(headers=self.headers, timeout=aiohttp.ClientTimeout(total=None, connect=5))
        return self._session

    async def _post(self, path: str, body: dict | None = None) -> dict | None:
        try:
            async with self.session.post(self.base + path, json=body) as r:
                return await r.json()
        except (aiohttp.ClientError, OSError, ValueError):
            return None

    async def ask(self, text: str) -> dict | None:
        return await self._post("/ask", {"text": text, "channel": "mac"})

    async def answer(self, reply: str, ask_id: str | None) -> None:
        await self._post("/answer", {"answer": reply, "ask_id": ask_id, "channel": "mac"})

    async def cancel(self) -> None:
        await self._post("/cancel")

    async def events(self) -> AsyncIterator[dict]:
        """Daemon events, plus `link` events of our own; reconnects every `retry` seconds."""
        yield {"type": "link", "state": "connecting"}
        while True:
            try:
                async with self.session.ws_connect(self.base + "/events") as ws:
                    async for msg in ws:
                        if msg.type is aiohttp.WSMsgType.TEXT:
                            yield json.loads(msg.data)
            except (aiohttp.ClientError, OSError, ValueError):
                pass
            yield {"type": "link", "state": "no daemon"}
            await asyncio.sleep(self.retry)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()


def skills(folder: Path) -> list[tuple[str, str]]:
    """(name, description) from each `<folder>/*/SKILL.md` frontmatter, sorted by name."""
    found = []
    for f in sorted(folder.glob("*/SKILL.md")):
        meta, lines = {}, f.read_text().splitlines()
        if lines and lines[0].strip() == "---":
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip().strip("\"'")
        found.append((meta.get("name") or f.parent.name, meta.get("description", "")))
    return sorted(found)


def _status(word: str, value: str) -> str:
    return f"{word} {'○' if value in OFF_WORDS else '●'} {value}"


def _grid() -> Table:
    """Two columns: a text that shortens with an ellipsis, and a right-aligned word."""
    t = Table.grid(expand=True, padding=(0, 1))
    t.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    t.add_column(justify="right", no_wrap=True)
    return t


class Hud(App):
    CSS_PATH = "jarvis.tcss"
    TITLE = "Jarvis"
    AUTO_FOCUS = None  # keys reach the HUD until Febriel clicks or starts typing
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("y", "answer('yes')", show=False, priority=True),
        Binding("n", "answer('no')", show=False, priority=True),
        Binding("a", "answer('always')", show=False, priority=True),
        Binding("slash", "skills", show=False, priority=True),
        Binding("escape", "escape", show=False, priority=True),
        Binding("ctrl+l", "mic", show=False, priority=True),
        Binding("ctrl+q", "quit", show=False, priority=True),
    ]

    def __init__(self, client, skills_dir: Path = SKILLS_DIR, now: Callable[[], float] = time.time):
        super().__init__()
        self.client, self.skills_dir, self.now = client, skills_dir, now
        self.view = View.empty()
        self._answer = None  # (reply, ask_id, timer) while a lone answer key waits out ANSWER_DELAY

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            yield Static("J . A . R . V . I . S .", id="title")
            yield Static(id="link")
        with Horizontal(id="top", classes="panels"):
            yield Static(id="voice", classes="panel")
            yield Static(id="agents", classes="panel")
        with Horizontal(id="bottom", classes="panels"):
            yield Static(id="queue", classes="panel")
            yield Static(id="memory", classes="panel")
        yield Static(id="notice")
        yield Static(id="question")
        yield OptionList(id="skills")
        yield Input(placeholder="Type to Jarvis…   / skills   ^L mic   esc cancel", id="ask", select_on_focus=False)
        yield Static(id="footer")

    def on_mount(self) -> None:
        for wid in ("voice", "agents", "queue", "memory"):
            self.query_one(f"#{wid}").border_title = wid.upper()
        self.redraw()
        self.set_interval(1, self.redraw)
        self.run_worker(self._listen(), exclusive=True)

    async def _listen(self) -> None:
        async for event in self.client.events():
            self.view = reduce(self.view, event)
            self.redraw()

    def _send(self, coro) -> None:
        self.run_worker(coro)

    # Drawing

    def redraw(self) -> None:
        v = self.view
        link = {"no daemon": "○ NO DAEMON", "connecting": "○ CONNECTING"}.get(v.link) or (
            "○ OFFLINE" if v.health.get("brain") in ("offline", "down") else "● ONLINE")
        self.query_one("#link", Static).update(Text(f"{link}   {time.strftime('%H:%M', time.localtime(self.now()))}"))

        voice = Text(v.voice, style=IDLE if v.voice == "IDLE" else f"bold {ACTIVE}")
        wave = "".join(BARS[round(level * (len(BARS) - 1))] for level in v.levels).rjust(LEVELS, BARS[0])
        voice.append(f"\n{wave}\n", style=IDLE)
        if v.last_heard:
            voice.append(f'"{v.last_heard}"\n')
        voice.append(v.reply, style=ACTIVE)
        self.query_one("#voice", Static).update(voice)

        agents = _grid()
        for a in v.agents:
            style = IDLE if a.doing == "idle" else None
            agents.add_row(Text(f"{a.name:<8} {a.model.removeprefix('claude-'):<9} {a.doing}", style=style),
                           elapsed(a.since, self.now()) if a.background else "")
        self.query_one("#agents", Static).update(agents)

        queue = _grid()
        for q in v.queue:
            mark, word, style = MARKS.get(q.status, ("◦", q.status, IDLE))
            queue.add_row(Text(f"{mark} {q.title}", style=style), Text(word, style=style))
        self.query_one("#queue", Static).update(queue)
        question = self.query_one("#question", Static)  # full width, so the whole question shows at 80×24
        ask = needs_you(v)
        question.display = bool(ask) and v.screen == "main"
        if ask:
            question.update(Group(Text(ask.question or "", style=ACTIVE), Text("y yes · n no · a always", style=IDLE)))

        self.query_one("#memory", Static).update(Text("\n".join(f"{op} {path}" for op, path in v.memory)))

        mic = "muted" if v.muted else v.health.get("mic", "off")
        footer = [_status("AWAKE", v.health.get("awake", "n/a")), _status("PHONE", v.health.get("phone", "not linked")),
                  f"MIC {'●' if mic in MIC_ON else '○'} {mic}", v.limits or "LIMITS ○ unknown"]
        self.query_one("#footer", Static).update(Text("    ".join(footer)))

        main = v.screen == "main"
        self.query_one("#top").display = self.query_one("#bottom").display = main
        notice = self.query_one("#notice", Static)
        notice.display = not main
        if not main:
            notice.update(Text(self._notice(v)))  # daemon text is never markup

    def _notice(self, v: View) -> str:
        if v.screen == "limit":
            at = time.strftime("%H:%M", time.localtime(v.resets_at)) if isinstance(v.resets_at, (int, float)) else "--:--"
            return f"LIMIT REACHED: resumes at {at}"
        lines = [NOTICES[v.screen]]
        if v.screen == "first-run":
            lines += [f"  ☐ {item}" for item in v.health.get("checklist", [])]
        return "\n".join(lines)

    # Keys

    def _ask_box(self) -> Input:
        return self.query_one("#ask", Input)

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        box, menu = self._ask_box(), self.query_one("#skills", OptionList)
        if action == "answer":
            return (self.view.screen == "main" and not box.has_focus and not box.value and not menu.display
                    and needs_you(self.view) is not None)
        if action == "skills":
            return not box.value and not menu.display
        return True

    def action_answer(self, reply: str) -> None:
        """A lone y, n or a answers once ANSWER_DELAY passes with no other letter: "add…" is typing, not "always"."""
        if ask := needs_you(self.view):
            self._drop_answer()
            self._answer = (reply, ask.ask_id, self.set_timer(ANSWER_DELAY, self._send_answer))

    def _send_answer(self) -> None:
        if self._answer:
            reply, ask_id, _ = self._answer
            self._answer = None
            self._send(self.client.answer(reply, ask_id))

    def _drop_answer(self) -> str:
        """Cancels a waiting answer and returns its key, to be typed instead."""
        if not self._answer:
            return ""
        reply, _, timer = self._answer
        timer.stop()
        self._answer = None
        return {"yes": "y", "no": "n", "always": "a"}[reply]

    def action_skills(self) -> None:
        menu = self.query_one("#skills", OptionList)
        menu.clear_options()
        menu.add_options([Option(Text(f"{name:<16} {desc}"), id=name) for name, desc in skills(self.skills_dir)] or [Option("No skills found.", disabled=True)])
        menu.display = True
        menu.highlighted = 0
        menu.focus()

    def action_escape(self) -> None:
        menu = self.query_one("#skills", OptionList)
        if menu.display:
            menu.display = False
            self.set_focus(None)
        else:
            self._send(self.client.cancel())

    def action_mic(self) -> None:
        self._send(self.client.ask("start listening" if self.view.muted else "stop listening"))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.option_list.display = False
        self.set_focus(None)
        self._send(self.client.ask(f"Use your {event.option.id} skill."))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if text := event.value.strip():
            self._send(self.client.ask(text))
        event.input.value = ""
        self.set_focus(None)  # so a y/n/a that follows answers a question; any other key starts typing again

    def on_key(self, event) -> None:
        """With nothing focused, a printable key starts a typed request."""
        if self.focused is None and event.is_printable and event.character:
            box = self._ask_box()
            box.focus()
            box.insert_text_at_cursor(self._drop_answer() + event.character)
            event.stop()


def run() -> None:
    """`jarvis hud`: connect to the local jarvisd with the token in JARVIS_HOME."""
    from jarvis.remote.token import load_token

    Hud(Client(load_token(config.HOME_DIR))).run()
