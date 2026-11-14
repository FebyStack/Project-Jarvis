"""The skills installed in Febriel's Claude desktop app, linked for Jarvis (plan 2, Task 16 amendment, his choice).

Skill folders only: never plugin hooks, permission rules or connectors, so the gate stays the only thing that approves
what Jarvis does. A skill that declares its own hooks, or holds a !`command` line (run as the skill loads, not as a
tool call), is never linked, for the same reason. Rebuilt at every daemon start into a folder passed with `--add-dir`,
so his edits and plugin updates carry over and his own Claude Code sessions in this repo do not load the copies.
"""
import json
import os
import re
from pathlib import Path

from jarvis import config

# Whole plugins left out: they need a connector Jarvis does not have, Cowork, or Febriel said no (honey).
SKIP_PLUGINS = {"chatcut", "figma", "cowork-plugin-management", "honey"}
SKIP = {
    "built-in-browser", "chrome-browser", "computer-use", "import-memory", "morning",  # the desktop app's own tools
    "docs", "google-workspace", "chief-of-staff",                                       # Google and Docs connectors
    "konsepto-competitor-watch", "konsepto-trend-scan",                                 # the Apify connector
    "reverse-engineer-anything",                                                        # the REA server (Plan 5)
    "deep-research",                                                                    # Claude Code ships its own
}


_BANG = re.compile(r"!`[^`]+`")


def _frontmatter(text: str) -> dict[str, str]:
    lines, meta = text.splitlines(), {}
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            key, _, value = line.partition(":")
            if key and not key[0].isspace():
                meta[key.strip()] = value.strip().strip("\"'")
    return meta


def _name(skill_md: Path) -> str:
    return _frontmatter(skill_md.read_text(encoding="utf-8", errors="replace")).get("name") or skill_md.parent.name


def _runs_commands(skill_md: Path) -> bool:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    return "hooks" in _frontmatter(text) or bool(_BANG.search(text))


def _json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def sources() -> list[Path]:
    """Folders that hold skill folders, the one to prefer first: his own, his claude.ai skills, Claude Code plugins,
    then plugins synced from his claude.ai account."""
    c = Path.home() / ".claude"
    roots = [c / "skills", *sorted(p for p in (c / "skills" / "synced").glob("*") if p.is_dir())]
    for key, on in sorted((_json(c / "settings.json").get("enabledPlugins") or {}).items()):
        plugin, _, market = key.partition("@")
        if on is True and plugin not in SKIP_PLUGINS:
            versions = sorted((c / "plugins" / "cache" / market / plugin).glob("*"), key=os.path.getmtime)
            roots += [versions[-1] / "skills"] if versions else []
    for account in sorted(p for p in (c / "plugins" / "synced").glob("*") if p.is_dir()):
        for plugin in _json(account / "manifest.json").get("plugins") or []:
            name, generation = plugin.get("name"), plugin.get("generation")
            if isinstance(name, str) and name not in SKIP_PLUGINS:
                roots.append(account / (f"{name}~g{generation}" if generation else name) / "skills")
    return roots


def link(dest: Path) -> list[str]:
    """Makes `dest/.claude/skills/<name>` a link to each usable desktop skill; returns the names linked."""
    folder = dest / ".claude" / "skills"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.iterdir():
        if old.is_symlink():  # only links are ours to remove
            old.unlink()
    own = config.PROJECT / ".claude" / "skills"
    taken = {_name(p) for p in own.glob("*/SKILL.md")} | SKIP  # Jarvis's own skills win over a same-named one
    linked = []
    for root in sources():
        for skill_md in sorted(root.glob("*/SKILL.md")):
            name = _name(skill_md)
            if name in taken or "/" in name or name.startswith(".") or _runs_commands(skill_md):
                continue
            taken.add(name)
            (folder / name).symlink_to(skill_md.parent)
            linked.append(name)
    return sorted(linked)
