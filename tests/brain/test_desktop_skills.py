import json
import os
from pathlib import Path

import pytest

from jarvis import config
from jarvis.brain import desktop_skills
from jarvis.brain.env import claude_argv


def skill(folder: Path, name: str, body: str = "") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {name} skill\n---\n{body}\n")
    return folder


@pytest.fixture
def desktop(tmp_path, monkeypatch):
    """A fake ~/.claude shaped like Febriel's: own skills, claude.ai skills, Claude Code plugins, synced plugins."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    c = home / ".claude"
    skill(c / "skills" / "video-use", "video-use")
    skill(c / "skills" / "sev-write-post", "sev-write-post")
    skill(c / "skills" / "vault", "vault")                                  # Jarvis has its own vault skill
    skill(c / "skills" / "synced" / "acct" / "sev-write-post", "sev-write-post", "claude.ai copy")
    skill(c / "skills" / "synced" / "acct" / "docx", "docx")
    skill(c / "skills" / "synced" / "acct" / "computer-use", "computer-use")  # the desktop app's own tool
    (c / "settings.json").write_text(json.dumps({"enabledPlugins": {
        "superpowers@claude-plugins-official": True, "honey@greenpt": True, "chatcut@chatcut-inc": True, "off@x": False}}))
    sp = c / "plugins" / "cache" / "claude-plugins-official" / "superpowers"
    old = skill(sp / "5.0.0" / "skills" / "brainstorming", "brainstorming", "old").parent.parent
    skill(sp / "5.1.0" / "skills" / "brainstorming", "brainstorming", "new")
    os.utime(old, (1, 1))
    skill(c / "plugins" / "cache" / "greenpt" / "honey" / "1.0" / "skills" / "honey", "honey")
    skill(c / "plugins" / "cache" / "chatcut-inc" / "chatcut" / "1.0" / "skills" / "export", "export")
    acct = c / "plugins" / "synced" / "org_acct"
    skill(acct / "sev-reels-studio~g4" / "skills" / "edit-reel", "edit-reel")
    skill(acct / "sev-reels-studio" / "skills" / "edit-reel", "edit-reel", "stale generation")
    skill(acct / "figma~g5" / "skills" / "figma-use", "figma-use")
    skill(acct / "design-craft-skills" / "skills" / "impeccable", "impeccable")
    (acct / "manifest.json").write_text(json.dumps({"plugins": [
        {"name": "sev-reels-studio", "generation": 4}, {"name": "figma", "generation": 5}, {"name": "design-craft-skills"}]}))
    (c / "plugins" / "synced" / ".bucket-org_acct").write_text("")        # not a folder: ignored
    return home


def links(dest):
    folder = dest / ".claude" / "skills"
    return {p.name: Path(os.readlink(p)) for p in folder.iterdir() if p.is_symlink()}


def test_links_the_skills_that_work_and_nothing_else(desktop, tmp_path):
    dest = tmp_path / "jarvis-home" / "desktop-skills"
    names = desktop_skills.link(dest)
    c = desktop / ".claude"
    assert links(dest) == {
        "video-use": c / "skills" / "video-use",
        "sev-write-post": c / "skills" / "sev-write-post",                  # his own copy wins over the claude.ai one
        "docx": c / "skills" / "synced" / "acct" / "docx",
        "brainstorming": c / "plugins" / "cache" / "claude-plugins-official" / "superpowers" / "5.1.0" / "skills" / "brainstorming",
        "edit-reel": c / "plugins" / "synced" / "org_acct" / "sev-reels-studio~g4" / "skills" / "edit-reel",
        "impeccable": c / "plugins" / "synced" / "org_acct" / "design-craft-skills" / "skills" / "impeccable",
    }
    assert names == sorted(links(dest))      # no vault (Jarvis's own), honey, chatcut, figma or computer-use


def test_relinking_drops_stale_links_and_never_touches_real_files(desktop, tmp_path):
    dest = tmp_path / "desktop-skills"
    desktop_skills.link(dest)
    folder = dest / ".claude" / "skills"
    (folder / "gone").symlink_to(tmp_path / "nowhere")
    (folder / "README.txt").write_text("mine")
    (desktop / ".claude" / "skills" / "video-use" / "SKILL.md").unlink()
    desktop_skills.link(dest)
    assert "gone" not in links(dest) and "video-use" not in links(dest)
    assert (folder / "README.txt").read_text() == "mine"


def test_no_desktop_install_links_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "empty")
    assert desktop_skills.link(tmp_path / "d") == []


def test_the_brain_gets_the_links_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_HOME", str(tmp_path / "j"))
    a = claude_argv("MAP")
    assert a[a.index("--add-dir") + 1] == str(tmp_path / "j" / "desktop-skills") == str(config.DESKTOP_SKILLS)


def test_skills_that_would_run_commands_outside_the_gate_are_left_out(desktop, tmp_path):
    own = desktop / ".claude" / "skills"
    skill(own / "hooked", "hooked").joinpath("SKILL.md").write_text("---\nname: hooked\nhooks:\n  PreToolUse: []\n---\nx\n")
    skill(own / "banged", "banged", "Repo state: !`git status`")      # runs when the skill loads, not as a tool call
    names = desktop_skills.link(tmp_path / "d")
    assert "hooked" not in names and "banged" not in names and "video-use" in names


@pytest.mark.parametrize("text", [
    '---\nname: q\n"hooks":\n  Stop: []\n---\nx\n',             # quoted key
    "---\nname: q\nHooks:\n  Stop: []\n---\nx\n",                # other case
    "---\nname: q\nmeta: {hooks: {Stop: []}}\n---\nx\n",         # flow style
    "﻿---\nname: q\nhooks: {}\n---\nx\n",                   # byte order mark
    "---\nname: q\ndescription: never closes\nx\n",              # frontmatter that never ends: fail closed
    "---\nname: q\n---\n```!\ngit status\n```\n",                # a fenced command block
    "---\nname: q\n---\nGlued: `#VALUE!`touch x`\n",             # ! against a backtick, anywhere
])
def test_anything_that_might_run_outside_the_gate_is_left_out(desktop, tmp_path, text):
    folder = desktop / ".claude" / "skills" / "q"; folder.mkdir()
    (folder / "SKILL.md").write_text(text)
    assert "q" not in desktop_skills.link(tmp_path / "d")


def test_a_file_reviewed_by_hand_may_hold_a_bang_in_prose(desktop, tmp_path, monkeypatch):
    import hashlib
    folder = skill(desktop / ".claude" / "skills" / "sheets", "sheets", "Unquoted, it evaluates to `#VALUE!`. See `xl/`.")
    assert "sheets" not in desktop_skills.link(tmp_path / "d")
    digest = hashlib.sha256((folder / "SKILL.md").read_bytes()).hexdigest()
    monkeypatch.setitem(desktop_skills.REVIEWED, digest, "sheets: prose")
    assert "sheets" in desktop_skills.link(tmp_path / "d")
