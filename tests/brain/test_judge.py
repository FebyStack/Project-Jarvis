from pathlib import Path
from unittest.mock import ANY

import pytest

from jarvis.brain.gate import Decision, GateConfig
from jarvis.brain.judge import judge, load_config
from jarvis.brain.trusted import TrustedList


@pytest.fixture
def cfg(tmp_path):
    """Shaped like load_config(): free-write [Developer, vault], protected [project, state dir]."""
    free = tmp_path / "Developer"
    project = free / "Project Jarvis"
    home = tmp_path / ".jarvis"
    vault = tmp_path / "vault"
    for d in (project, home, vault):
        d.mkdir(parents=True)
    return GateConfig(free_write=[free, vault], protected=[project, home],
                      trusted=TrustedList(home / "trusted.txt"), read_tools=set())


def v(name, inp, cfg, cwd=None): return judge(name, inp, cwd or cfg.free_write[0], cfg)


def test_reads_and_dispatch_are_free(cfg):
    for name, inp in [("Read", {"file_path": "/etc/hosts"}), ("Grep", {"pattern": "x"}), ("Agent", {"subagent_type": "triage"}),
                      ("WebSearch", {"query": "x"}), ("WebFetch", {"url": "https://example.com/a"})]:
        assert v(name, inp, cfg).verdict == "allow"


def test_writes_follow_the_path_rules(cfg):
    free = cfg.free_write[0]
    assert v("Write", {"file_path": str(free / "app" / "a.py")}, cfg).verdict == "allow"
    assert v("Edit", {"file_path": "notes.md"}, cfg, cwd=free / "app").verdict == "allow"   # relative to cwd
    assert v("Write", {"file_path": str(free.parent / "Documents" / "a.txt")}, cfg).verdict == "ask"
    assert v("NotebookEdit", {"notebook_path": str(free.parent / "x.ipynb")}, cfg).verdict == "ask"
    assert v("Write", {}, cfg) == Decision("ask", ANY, "")


@pytest.mark.parametrize("rel", ["jarvis/brain/gate.py", ".venv/bin/python", ".claude/jarvis-settings.json", "README.md"])
def test_jarvis_cannot_edit_itself_quietly(cfg, rel):
    d = v("Edit", {"file_path": str(cfg.protected[0] / rel)}, cfg)
    assert d.verdict == "ask" and d.pattern == ""


def test_trusted_list_and_token_are_protected(cfg):
    for name in ("trusted.txt", "token"):
        d = v("Write", {"file_path": str(cfg.protected[1] / name)}, cfg)
        assert d.verdict == "ask" and d.pattern == ""
    assert v("Bash", {"command": f"echo x >> {cfg.protected[1] / 'trusted.txt'}"}, cfg).pattern == ""


@pytest.mark.parametrize("url", ["http://127.0.0.1:8787/answer", "http://localhost:8787/ask", "http://[::1]/x",
                                 "http://192.168.1.10/", "http://10.0.0.2/", "https://jarvis-mac.tail80d4ef.ts.net/ask", "http://printer.local/"])
def test_fetching_a_local_address_asks_and_is_not_remembered(cfg, url):
    d = v("WebFetch", {"url": url}, cfg)
    assert d.verdict == "ask" and d.pattern == ""


def test_shell_goes_through_the_shell_rules(cfg):
    assert v("Bash", {"command": "ls -la"}, cfg).verdict == "allow"
    assert v("Bash", {"command": "sudo ls"}, cfg).verdict == "never"
    assert v("Bash", {"command": "curl -X POST http://127.0.0.1:8787/answer"}, cfg).verdict == "ask"


def test_unknown_and_connector_tools_ask(cfg):
    assert v("Frobnicate", {}, cfg) == Decision("ask", ANY, "tool:Frobnicate")
    assert v("mcp__gmail__send", {}, cfg).pattern == "tool:mcp__gmail__send"


def test_load_config_protects_the_project_and_state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_HOME", str(tmp_path / "j")); monkeypatch.setenv("JARVIS_VAULT", str(tmp_path / "v"))
    cfg = load_config()
    assert cfg.protected[:2] == [Path.home() / "Developer" / "Project Jarvis", tmp_path / "j"]
    assert {Path.home() / ".local" / "bin", Path.home() / ".local" / "share" / "claude", Path("/opt/homebrew")} <= set(cfg.protected)
    assert cfg.free_write == [Path.home() / "Developer", tmp_path / "v"]


# ── cases the table implies ──────────────────────────────────────────────────

def test_multiedit_into_the_project_asks_unremembered(cfg):
    d = v("MultiEdit", {"file_path": str(cfg.protected[0] / "jarvis" / "brain" / "judge.py"), "edits": []}, cfg)
    assert d.verdict == "ask" and d.pattern == ""


def test_symlink_or_dotdot_out_of_the_free_area_into_the_project_asks(cfg):
    free = cfg.free_write[0]
    (free / "innocent").symlink_to(cfg.protected[0])
    for p in (free / "innocent" / "jarvis" / "brain" / "gate.py", free / "app" / ".." / "Project Jarvis" / "x.py"):
        d = v("Write", {"file_path": str(p)}, cfg)
        assert d.verdict == "ask" and d.pattern == ""


def test_letter_case_does_not_unlock_the_project(cfg):
    d = v("Write", {"file_path": str(cfg.free_write[0] / "project jarvis" / "jarvis" / "brain" / "gate.py")}, cfg)
    assert d.verdict == "ask" and d.pattern == ""


def test_a_yes_always_never_reaches_a_protected_path(cfg):
    cfg.trusted.add(f"write:{cfg.protected[0]}")
    cfg.trusted.add(f"write:{cfg.protected[1]}")
    for p in (cfg.protected[0] / "a.py", cfg.protected[1] / "trusted.txt"):
        assert v("Write", {"file_path": str(p)}, cfg).verdict == "ask"


def test_trusted_unknown_tool_is_allowed(cfg):
    cfg.trusted.add("tool:Frobnicate")
    assert v("Frobnicate", {}, cfg).verdict == "allow"


@pytest.mark.parametrize("inp", [{}, {"command": ""}, {"command": None}, {"command": ["rm", "-rf", "/"]}])
def test_bash_without_a_command_asks_unremembered(cfg, inp):
    d = v("Bash", inp, cfg)
    assert d.verdict == "ask" and d.pattern == ""


@pytest.mark.parametrize("inp", [{"file_path": ""}, {"file_path": None}, {"file_path": 3}, {"notebook_path": "/tmp/x.ipynb"}])
def test_write_without_a_usable_path_asks_unremembered(cfg, inp):
    d = v("Write", inp, cfg)
    assert d.verdict == "ask" and d.pattern == ""


@pytest.mark.parametrize("inp", [{}, {"url": ""}, {"url": None}, {"url": "not a url"}, {"url": "file:///etc/passwd"},
                                 {"url": "http://[::1/"}, {"url": "http:///nohost"}])
def test_webfetch_without_a_usable_url_asks_unremembered(cfg, inp):
    d = v("WebFetch", inp, cfg)
    assert d.verdict == "ask" and d.pattern == ""


@pytest.mark.parametrize("url", [
    "http://LOCALHOST/", "http://localhost./", "http://api.localhost/", "http://127.1/", "http://2130706433/",
    "http://0x7f000001/", "http://0.0.0.0:8787/", "http://[::ffff:127.0.0.1]/", "http://[fe80::1]/",
    "http://169.254.169.254/latest", "http://100.101.102.103/", "http://example.com@127.0.0.1/",
    "http://127.0.0.1\\@example.com/", "http://%31%32%37.0.0.1/", "http://ｌｏｃａｌｈｏｓｔ/", "http://printer.LOCAL./",
    "http://jarvis-mac:8787/ask",  # dotless: local search domain or Tailscale MagicDNS
])
def test_disguised_local_addresses_ask_unremembered(cfg, url):
    d = v("WebFetch", {"url": url}, cfg)
    assert d.verdict == "ask" and d.pattern == ""


def test_config_follows_env_set_after_import(monkeypatch, tmp_path):
    from jarvis import config
    monkeypatch.setenv("JARVIS_HOME", str(tmp_path / "h")); monkeypatch.setenv("JARVIS_VAULT", str(tmp_path / "w"))
    assert (config.HOME_DIR, config.VAULT) == (tmp_path / "h", tmp_path / "w")
    monkeypatch.delenv("JARVIS_HOME"); monkeypatch.setenv("JARVIS_VAULT", "")
    assert config.HOME_DIR == Path.home() / ".jarvis"
    assert config.VAULT == Path("/Users/febrielotud/Obsidian/Jarvis")


@pytest.mark.parametrize("rel", [".claude/settings.json", ".obsidian/plugins/x/main.js", ".vscode/tasks.json", ".envrc"])
def test_write_tool_into_run_later_paths_asks_unremembered(cfg, rel):
    for root in (cfg.free_write[0] / "repo", cfg.free_write[1]):
        for name in ("Write", "Edit", "MultiEdit"):
            d = v(name, {"file_path": str(root / rel)}, cfg)
            assert d.verdict == "ask" and d.pattern == "", (name, root, rel)
