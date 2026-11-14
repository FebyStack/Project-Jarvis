"""`jarvis daemon | hud | ask | doctor | shortlist` (plan 2, Task 12)."""
import argparse
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import urllib.error
import urllib.request

from jarvis import config
from jarvis.memory.vault import Vault

AGENTS = ("jarvis", "triage", "coder", "researcher", "scribe")
NOT_RUNNING = "jarvisd is not running. Start it with: jarvis daemon"
LOGIN_TIMEOUT = 30


def checklist(slow: bool = True) -> list[str]:
    """One line per thing still missing; empty when Jarvis is ready. `slow` adds the login check (up to 30 s)."""
    from jarvis.brain.env import PATH

    lines = []
    if not shutil.which("claude", path=PATH):
        lines.append("claude is not on PATH")
    if "ANTHROPIC_API_KEY" in os.environ:
        lines.append("ANTHROPIC_API_KEY is set; unset it, Jarvis runs on the subscription login only")
    if (status := Vault(config.VAULT).status()) != "ok":
        lines.append(f"the vault at {config.VAULT} is {status}")
    if not config.SETTINGS.exists():
        lines.append(f"{config.SETTINGS} is missing")
    if (config.PROJECT / ".claude" / "settings.json").exists():
        lines.append("remove .claude/settings.json; Jarvis's hooks live in .claude/jarvis-settings.json")
    lines += [f".claude/agents/{a}.md is missing" for a in AGENTS
              if not (config.PROJECT / ".claude" / "agents" / f"{a}.md").exists()]
    token = config.HOME_DIR / "token"
    if not token.exists() or stat.S_IMODE(token.stat().st_mode) != 0o600:
        lines.append(f"{token} is missing or not mode 600; jarvis daemon makes it")
    if slow and not lines and not _login_works():
        lines.append("claude did not answer within 30 s; run claude once in a terminal and log in")
    return lines


def _login_works() -> bool:
    from jarvis.brain.env import clean_env

    try:
        out = subprocess.run(["claude", "-p", "--model", "haiku", "--setting-sources", "project", "--strict-mcp-config",
                              "ok"], env=clean_env(), cwd=config.PROJECT, capture_output=True, text=True,
                             timeout=LOGIN_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return out.returncode == 0 and bool(out.stdout.strip())


def _port_taken() -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", config.PORT))
        except OSError:
            return True
    return False


def daemon() -> int:
    if "ANTHROPIC_API_KEY" in os.environ:
        print("ANTHROPIC_API_KEY is set. Unset it: Jarvis runs on the subscription login only.", file=sys.stderr)
        return 1
    if _port_taken():
        print(f"port {config.PORT} is taken. Is jarvisd already running?", file=sys.stderr)
        return 1
    import asyncio
    import logging

    from jarvis.remote.token import load_token

    token = load_token(config.HOME_DIR)
    logging.basicConfig(filename=config.HOME_DIR / "jarvisd.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    vault = Vault(config.VAULT)
    vault.ensure_map()
    try:
        asyncio.run(_run(vault, token))
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


async def _run(vault: Vault, token: str) -> None:
    import asyncio
    import signal
    import time
    from datetime import datetime

    from jarvis.brain.bridge import Bridge
    from jarvis.daemon.core import Jarvis
    from jarvis.remote.api import make_app, serve

    jarvis = Jarvis(vault, Bridge, time.time, datetime.now, checklist=lambda: checklist(slow=False))
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await jarvis.start()
    server = asyncio.create_task(serve(make_app(jarvis, token)))
    try:
        await asyncio.wait([server, asyncio.create_task(stop.wait())], return_when=asyncio.FIRST_COMPLETED)
        if server.done():
            server.result()  # "port … is taken" surfaces here
    finally:
        server.cancel()
        await asyncio.gather(server, return_exceptions=True)
        await jarvis.stop()  # stops the claude child too


def ask(text: str) -> int:
    from jarvis.remote.token import load_token

    req = urllib.request.Request(
        f"http://127.0.0.1:{config.PORT}/ask", data=json.dumps({"text": text, "channel": "mac"}).encode(),
        headers={"Authorization": f"Bearer {load_token(config.HOME_DIR)}", "Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # the token goes to 127.0.0.1 only
    try:
        with opener.open(req) as resp:
            print(json.loads(resp.read())["say"])
    except urllib.error.HTTPError as e:
        print(f"jarvisd answered {e.code}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, ConnectionError):
        print(NOT_RUNNING, file=sys.stderr)
        return 1
    return 0


def doctor() -> int:
    lines = checklist(slow=True)
    print("\n".join(lines) or "Ready.")
    return 1 if lines else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="jarvis")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("daemon", help="run jarvisd")
    sub.add_parser("hud", help="the gold terminal HUD")
    sub.add_parser("ask", help="ask jarvisd once").add_argument("text")
    sub.add_parser("doctor", help="what is still missing")
    sub.add_parser("shortlist", help="repeat tasks from your last 30 days")
    args = p.parse_args(argv)
    if args.cmd == "daemon":
        return daemon()
    if args.cmd == "hud":
        from jarvis.tui.app import run
        run()
        return 0
    if args.cmd == "ask":
        return ask(args.text)
    if args.cmd == "doctor":
        return doctor()
    print("jarvis shortlist comes with Plan 2 Task 16.", file=sys.stderr)
    return 1
