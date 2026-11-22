"""`jarvis daemon | hud | ask | doctor | shortlist | models` (plan 2, Task 12; plan 3, Task 12)."""
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
ALLOW = "allow \"Python\" in System Settings > Privacy & Security > {}, then restart jarvisd (launchd/README.md)"
VOICE_LINES = {
    "no permission": "jarvisd cannot hear: " + ALLOW.format("Microphone"),
    "on, no key": "the talk key is off: " + ALLOW.format("Input Monitoring"),
    "no models": "the voice models are missing: run jarvis models",
    "loading": "the voice models are still loading; ask again in a few seconds",
    "off": f"the mic is off (no input device, or the voice did not start); see {config.HOME_DIR / 'jarvisd.log'}",
}


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
    from jarvis.brain.env import PATH

    if not os.environ.get("JARVIS_CLAUDE_BIN") and not shutil.which("claude", path=PATH):
        print("claude is not on PATH. Install Claude Code and log in, then check with: jarvis doctor", file=sys.stderr)
        return 1
    import asyncio
    import logging

    from jarvis.remote.token import load_token

    token = load_token(config.HOME_DIR)
    os.environ["HF_HUB_OFFLINE"] = "1"  # the models load from the cache; only `jarvis models` downloads
    _log_to(config.HOME_DIR / "jarvisd.log")
    vault = Vault(config.VAULT)
    vault.ensure_map()
    from jarvis.brain import desktop_skills

    logging.getLogger("jarvisd").info("linked %d desktop skills", len(desktop_skills.link(config.DESKTOP_SKILLS)))
    try:
        asyncio.run(_run(vault, token))
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


def _log_to(path) -> None:
    """jarvisd's own lines, and only errors from other packages: Kokoro logs the phonemes of long sentences, the
    words Jarvis says, at WARNING."""
    import logging

    handler = logging.FileHandler(path, delay=True)
    handler.addFilter(lambda r: r.name == "jarvisd" or r.levelno >= logging.ERROR)
    logging.basicConfig(handlers=[handler], level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _build_voice():
    """The speaker for the core, and a function that makes the `Voice` once the core exists."""
    from jarvis.voice.audio import Mic, Player
    from jarvis.voice.engines import Engines, vad
    from jarvis.voice.loop import Voice
    from jarvis.voice.segment import Segmenter
    from jarvis.voice.speaker import VoiceSpeaker

    engines = Engines()
    return VoiceSpeaker(engines.synth, Player()), lambda jarvis: Voice(jarvis, engines, Mic(), Segmenter(vad()))


async def _voice(jarvis, make_voice) -> None:
    """Runs the voice until cancelled. One that fails to start is logged and leaves the rest of jarvisd running."""
    import asyncio
    import logging

    voice = None
    try:
        voice = make_voice(jarvis)
        await voice.start()  # loads the models, 4-14 s
        await asyncio.Future()
    except Exception:
        logging.exception("voice did not start")
        jarvis.set_mic("off")
    finally:
        if voice is not None:
            await voice.stop()


async def _run(vault: Vault, token: str, build_voice=_build_voice) -> None:
    import asyncio
    import signal
    import time
    from datetime import datetime

    from jarvis.brain.bridge import Bridge
    from jarvis.daemon.core import Jarvis
    from jarvis.remote.api import make_app, serve

    speaker, make_voice = build_voice()
    jarvis = Jarvis(vault, Bridge, time.time, datetime.now, checklist=lambda: checklist(slow=False), speaker=speaker)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await jarvis.start()
    server = asyncio.create_task(serve(make_app(jarvis, token)))
    voice = asyncio.create_task(_voice(jarvis, make_voice))  # in the background, so the API is up meanwhile
    try:
        await asyncio.wait([server, asyncio.create_task(stop.wait())], return_when=asyncio.FIRST_COMPLETED)
        if server.done():
            server.result()  # "port … is taken" surfaces here
    finally:
        voice.cancel()  # the mic and the talk key stop before the core does
        await asyncio.gather(voice, return_exceptions=True)
        await jarvis.stop()  # answers and records every open request first, then stops the claude child
        server.cancel()  # so the API's open requests have finished and its shutdown is quick
        await asyncio.gather(server, return_exceptions=True)


def _call(path: str, body: dict | None = None) -> dict:
    from jarvis.remote.token import load_token

    req = urllib.request.Request(
        f"http://127.0.0.1:{config.PORT}{path}", data=body and json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {load_token(config.HOME_DIR)}", "Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # the token goes to 127.0.0.1 only
    with opener.open(req) as resp:
        return json.loads(resp.read())


def ask(text: str) -> int:
    try:
        print(_call("/ask", {"text": text, "channel": "mac"})["say"])
    except urllib.error.HTTPError as e:
        print(f"jarvisd answered {e.code}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, ConnectionError):
        print(NOT_RUNNING, file=sys.stderr)
        return 1
    return 0


def voice_lines(mic: str) -> list[str]:
    """What to do about the mic word jarvisd reports; empty when the voice works (or Febriel muted it)."""
    if mic in ("on", "muted"):
        return []
    return [VOICE_LINES.get(mic, f"the voice did not load ({mic}); see {config.HOME_DIR / 'jarvisd.log'}")]


def doctor() -> int:
    lines = checklist(slow=True)
    try:
        lines += voice_lines(_call("/health")["mic"])
    except urllib.error.HTTPError as e:
        lines.append(f"jarvisd answered {e.code} to /health")
    except (urllib.error.URLError, ConnectionError):  # the grants belong to jarvisd's process, not this terminal
        lines.append("jarvisd is not running, so the mic and the talk key cannot be checked. Start it, then ask again")
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
    sub.add_parser("models", help="download the speech models (once)")
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
    if args.cmd == "models":
        from jarvis.voice.engines import download
        download()
        print("Models ready.")
        return 0
    from jarvis.brain.shortlist import run as shortlist
    return shortlist(config.VAULT)
