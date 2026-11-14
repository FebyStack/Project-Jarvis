"""Claude Code tool call -> gate Decision (plan 2, Task 4). Pure: no network, no DNS.

A tool the table does not name asks; nothing falls through to allow.
"""
import ipaddress
import os
import re
import socket
from pathlib import Path
from urllib.parse import urlsplit

from jarvis import config
from jarvis.brain.gate import (Decision, GateConfig, _ask_unless_trusted, classify_path_write, classify_shell,
                               classify_tool)
from jarvis.brain.trusted import TrustedList

_FREE = {"Read", "Glob", "Grep", "LS", "WebSearch", "TodoWrite", "Skill", "Agent", "Task", "TaskOutput", "ToolSearch"}
_PATH_KEY = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
_DNS_NAME = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)*")
_LOCAL_SUFFIXES = (".localhost", ".local", ".ts.net")


def load_config() -> GateConfig:
    home = config.HOME_DIR
    return GateConfig(free_write=[Path.home() / "Developer", config.VAULT], protected=[config.PROJECT, home],
                      trusted=TrustedList(home / "trusted.txt"), read_tools=set())


def _local_host(host: str) -> bool:
    """True for a host that reaches this Mac, the LAN or the tailnet. `host` is ASCII, lower-case, no trailing dot."""
    if ":" in host:  # urlsplit strips the brackets from an IPv6 literal
        ip = ipaddress.IPv6Address(host)  # ValueError for junk: the caller asks
        ip = ip.ipv4_mapped or ip
    else:
        try:  # inet_aton also reads the forms fetchers accept: 127.1, 2130706433, 0x7f000001
            ip = ipaddress.IPv4Address(socket.inet_aton(host))
        except OSError:
            if not _DNS_NAME.fullmatch(host):
                raise ValueError(host)  # %-escapes, underscores, odd characters: a fetcher may read them differently
            # A dotless name only resolves through local search domains, mDNS or Tailscale MagicDNS.
            return "." not in host or host == "localhost" or host.endswith(_LOCAL_SUFFIXES)
    return not ip.is_global  # loopback, private, link-local, unspecified, 100.64/10 (tailnet), reserved


def _judge_fetch(url) -> Decision:
    try:
        if not isinstance(url, str):
            raise ValueError(url)
        parts = urlsplit(url)
        netloc = parts.netloc
        if parts.scheme.lower() not in ("http", "https") or not netloc.isascii() or not netloc.isprintable() \
                or "\\" in netloc or not parts.hostname:
            raise ValueError(url)  # a backslash is a slash to browser-style parsers: the host would differ
        local = _local_host(parts.hostname.rstrip("."))
    except ValueError:
        return Decision("ask", f"cannot tell where this URL goes: {url!r}")
    if local:
        return Decision("ask", f"fetch of a local or private address: {parts.hostname}")
    return Decision("allow", f"fetch of a public address: {parts.hostname}")


def judge(tool_name: str, tool_input: dict, cwd: Path, cfg: GateConfig) -> Decision:
    if tool_name in _FREE:
        return Decision("allow", f"{tool_name} only reads or dispatches")
    if tool_name == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str) or not command.strip():
            return Decision("ask", "Bash call without a command")
        return classify_shell(command, cwd, cfg)
    if tool_name in _PATH_KEY:
        raw = tool_input.get(_PATH_KEY[tool_name])
        if not isinstance(raw, str) or not raw.strip():
            return Decision("ask", f"{tool_name} call without a path")
        path = Path(os.path.expanduser(raw))
        return classify_path_write(path if path.is_absolute() else Path(cwd) / path, cfg)
    if tool_name == "WebFetch":
        return _judge_fetch(tool_input.get("url"))
    if tool_name.startswith("mcp__"):
        return classify_tool(tool_name, cfg)
    return _ask_unless_trusted(Decision("ask", f"unknown tool: {tool_name}", f"tool:{tool_name}"), cfg)
