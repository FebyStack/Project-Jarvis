"""Regression tests for gate bypasses found by the automated security review (Part A fix pass)."""
from pathlib import Path

import pytest

from jarvis.brain.gate import classify_screen, classify_shell
from jarvis.brain.trusted import TrustedList

HOME = Path.home()
DEV = HOME / "Developer"


# ── shell ──
@pytest.mark.parametrize("cmd", [
    "ls ;< /dev/null rm ~/Documents/a.txt",      # separator glued to a redirect
    "ls |> ~/Documents/x",
    "ls &&< /dev/null rm ~/Documents/a.txt",
])
def test_mixed_operator_tokens_split_parts(cmd, cfg):
    assert classify_shell(cmd, DEV, cfg).verdict == "ask"


def test_git_options_before_subcommand_cannot_be_trusted(cfg):
    cfg.trusted.add("shell:git push")
    d = classify_shell("git --exec-path=/tmp/evil push", DEV, cfg)
    assert d.verdict == "ask" and d.pattern == ""


def test_git_exec_options_cannot_be_trusted(cfg):
    cfg.trusted.add("shell:git push")
    assert classify_shell("git push --receive-pack=/tmp/evil origin", DEV, cfg).verdict == "ask"


@pytest.mark.parametrize("cmd", ["bash -c 'rm -rf ~'", "python3 -c 'x'", "env rm ~/Documents/a", "xargs rm",
                                 "osascript -e 'x'", "eval ls", "PATH=/tmp ls"])
def test_command_runners_are_never_rememberable(cmd, cfg):
    d = classify_shell(cmd, DEV, cfg)
    assert d.verdict == "ask" and d.pattern == ""


def test_trusting_a_runner_name_does_not_unlock_it(cfg):
    cfg.trusted.add("shell:bash")
    assert classify_shell("bash -c 'rm -rf ~'", DEV, cfg).verdict == "ask"


def test_command_word_with_a_path_outside_system_bins_is_unknown(cfg):
    d = classify_shell("./ls", DEV, cfg)
    assert d.verdict == "ask" and d.pattern == ""
    assert classify_shell("/bin/ls", DEV, cfg).verdict == "allow"


def test_cd_makes_later_relative_paths_unresolvable(cfg):
    assert classify_shell("cd ~/Documents && rm a.txt", DEV, cfg).verdict == "ask"
    assert classify_shell("cd ~/Developer/x", DEV, cfg).verdict == "allow"
    assert classify_shell("rm ~+/a.txt", DEV, cfg).verdict == "ask"


@pytest.mark.parametrize("cmd", ["s''udo ls", "'su'do ls", "su -c ls", "doas ls"])
def test_obfuscated_sudo_is_never(cmd, cfg):
    cfg.trusted.add("shell:sudo")
    assert classify_shell(cmd, DEV, cfg).verdict == "never"


def test_trusted_list_rejects_line_breaks(tmp_path):
    t = TrustedList(tmp_path / "t.txt")
    t.add("shell:rm:/Users/x/a shell:bash")
    t.add("shell:rm:/a\nshell:bash")
    assert not t.contains("shell:bash")
    (tmp_path / "t.txt").write_text("shell:rm:/a shell:bash\n")
    assert not t.contains("shell:bash")


# ── on screen ──
@pytest.mark.parametrize("key", ["cmd+Return", "Return ", "KP_Enter", "shift+enter", "\n", "\r"])
def test_return_variants_ask(key, cfg):
    assert classify_screen("press", "Messages", cfg, key=key).verdict == "ask"


@pytest.mark.parametrize("key", ["cmd+Delete", "cmd+backspace", "ctrl+d", "alt+cmd+Escape"])
def test_modifier_combos_ask(key, cfg):
    assert classify_screen("press", "Finder", cfg, key=key).verdict == "ask"


@pytest.mark.parametrize("key", ["Tab", "Down", "Escape", "a", "shift+a"])
def test_plain_keys_free(key, cfg):
    assert classify_screen("press", "Finder", cfg, key=key).verdict == "allow"


def test_typed_newline_counts_as_return(cfg):
    d = classify_screen("type", "Messages", cfg, role="textfield", text="hi\n")
    assert d.verdict == "ask" and d.pattern == "screen:Messages:key:return"
    assert classify_screen("type", "Messages", cfg, role="textfield", text="hi").verdict == "allow"


@pytest.mark.parametrize("label", ["Sending", "Deleted", "Signs", "Paying", "Posted", "Buys"])
def test_inflected_ask_words_ask(label, cfg):
    assert classify_screen("click", "Mail", cfg, role="button", label=label).verdict == "ask"


@pytest.mark.parametrize("label", ["Ѕend", "Dеlete"])  # Cyrillic look-alikes
def test_non_ascii_letters_in_label_ask(label, cfg):
    d = classify_screen("click", "Mail", cfg, role="button", label=label)
    assert d.verdict == "ask" and d.pattern == ""


# ── Part A reviewer findings ──
PJ = DEV / "Project Jarvis"


def test_backslash_newline_joins_lines(cfg):
    assert classify_shell("rm -rf \\\ncat ~/Documents", PJ, cfg).verdict == "ask"


@pytest.mark.parametrize("cmd", ["rm -rf -- -/../../../Documents", "rm -rf -/../../../Documents",
                                 "rm a -/../../../Documents", "cp a -- -/../../../Documents"])
def test_dash_arguments_are_judged_as_paths(cmd, cfg):
    assert classify_shell(cmd, PJ, cfg).verdict == "ask"


def test_path_cmd_flags_still_work(cfg):
    assert classify_shell("rm -rf ~/Developer/scratch", PJ, cfg).verdict == "allow"
    assert classify_shell("mkdir -p ~/Developer/scratch/a", PJ, cfg).verdict == "allow"


@pytest.mark.parametrize("cmd", ["echo '{}' > ~/Developer/'Project Jarvis'/.CLAUDE/settings.json",
                                 "rm -rf ~/Developer/'Project Jarvis'",
                                 "mv ~/Developer/'Project Jarvis' ~/Developer/pj2",
                                 "cp -R ~/Developer/evil/ ~/Developer/'Project Jarvis'/",
                                 "rm -rf ~/DEVELOPER/'project jarvis'/.claude"])
def test_protected_paths_by_case_and_by_parent(cmd, cfg):
    assert classify_shell(cmd, HOME, cfg).verdict == "ask"


def test_protected_path_write_case_insensitive(cfg):
    from jarvis.brain.gate import classify_path_write
    assert classify_path_write(PJ / ".CLAUDE" / "settings.json", cfg).verdict == "ask"


def test_uv_pip_pattern_names_the_pip_command(cfg):
    assert classify_shell("uv pip list", PJ, cfg).pattern == "shell:uv pip list"
    cfg.trusted.add("shell:uv pip list")
    assert classify_shell("uv pip install evil", PJ, cfg).verdict == "ask"


def test_file_compile_mode_asks(cfg):
    assert classify_shell("file -C -m x", PJ, cfg).verdict == "ask"


@pytest.mark.parametrize("cmd", ["export PATH=~/Developer/x:$PATH", "set -x", "unset HOME", "hash -p /tmp/x ls"])
def test_shell_state_builtins_never_rememberable(cmd, cfg):
    d = classify_shell(cmd, PJ, cfg)
    assert d.verdict == "ask" and d.pattern == ""


@pytest.mark.parametrize("cmd", ["echo x > ~/Developer/repo/.git/config", "cp evil ~/Developer/repo/.GIT/hooks/pre-commit",
                                 "rm -rf ~/Developer/repo/.git"])
def test_writes_into_git_folders_ask(cmd, cfg):
    d = classify_shell(cmd, DEV, cfg)
    assert d.verdict == "ask" and d.pattern == ""


def test_write_tool_into_git_folder_asks(cfg):
    from jarvis.brain.gate import classify_path_write
    d = classify_path_write(DEV / "repo" / ".git" / "config", cfg)
    assert d.verdict == "ask" and d.pattern == ""


# ── second automated security pass ──
def test_cd_poisons_relative_paths_inside_substitutions(cfg):
    assert classify_shell("cd ~/Documents && cat $(rm a.txt)", DEV, cfg).verdict == "ask"


@pytest.mark.parametrize("cmd", ["uv run x.py", "npm exec evil", "npm run build", "npm x evil", "uv tool run evil",
                                 "pip3 download x"])
def test_subcommand_runners_never_rememberable(cmd, cfg):
    d = classify_shell(cmd, DEV, cfg)
    assert d.verdict == "ask" and (d.pattern == "" or cmd.startswith("pip3"))


@pytest.mark.parametrize("cmd", ["if true; then rm ~/Documents/a; fi", "! rm ~/Documents/a", "{ rm ~/Documents/a; }",
                                 "while true; do rm ~/Documents/a; done"])
def test_reserved_words_do_not_hide_commands(cmd, cfg):
    for word in ("if", "then", "!", "{", "while", "do"):
        cfg.trusted.add(f"shell:{word}")
    assert classify_shell(cmd, DEV, cfg).verdict == "ask"


def test_reserved_words_around_safe_commands_allow(cfg):
    assert classify_shell("if true; then ls; fi", DEV, cfg).verdict == "ask"  # `true` is not on the read-only list
    assert classify_shell("{ ls; }", DEV, cfg).verdict == "allow"


@pytest.mark.parametrize("label", ["Se­nd", "Del​ete", "Send‍"])
def test_invisible_characters_in_label_ask(label, cfg):
    d = classify_screen("click", "Mail", cfg, role="button", label=label)
    assert d.verdict == "ask" and d.pattern == ""


# ── third automated security pass ──
def test_quoted_cd_still_poisons_substitutions(cfg):
    assert classify_shell("c''d ~/Documents && cat $(rm a.txt)", DEV, cfg).verdict == "ask"


@pytest.mark.parametrize("cmd", ["npm rum build", "npm explore x -- sh", "npm run-script x", "git difftool",
                                 "brew sh", "uv tool run x", "pip3 wheel x"])
def test_only_listed_subcommands_are_rememberable(cmd, cfg):
    d = classify_shell(cmd, DEV, cfg)
    assert d.verdict == "ask" and d.pattern == ""


@pytest.mark.parametrize("cmd,pattern", [("git push", "shell:git push"), ("brew install tmux", "shell:brew install"),
                                         ("uv add x", "shell:uv add"), ("pip install x", "shell:pip install"),
                                         ("uv pip install x", "shell:uv pip install")])
def test_listed_subcommands_keep_their_pattern(cmd, pattern, cfg):
    assert classify_shell(cmd, DEV, cfg).pattern == pattern


def test_cd_after_a_keyword_still_poisons_relative_paths(cfg):
    assert classify_shell("{ cd ~/Documents; } && rm a.txt", DEV, cfg).verdict == "ask"
    assert classify_shell("if true; then cd ~/Documents; fi; rm a.txt", DEV, cfg).verdict == "ask"


# ── Task 4b: folders whose files run code later (Claude Code hooks, Obsidian plugins, VS Code tasks, direnv) ──
_RUN_LATER = [".claude/settings.json", ".obsidian/plugins/x/main.js", ".vscode/tasks.json", ".envrc",
              ".CLAUDE/settings.local.json", ".Obsidian/community-plugins.json", ".VSCode/settings.json", ".ENVRC",
              ".claude"]  # a file merely named .claude asks too: it holds the name a folder needs, and mv/mkdir make one


@pytest.mark.parametrize("rel", _RUN_LATER)
def test_run_later_paths_ask_in_developer_and_vault(rel, cfg):
    from jarvis.brain.gate import classify_path_write
    for root in (DEV / "repo", cfg.free_write[1]):
        d = classify_path_write(root / rel, cfg)
        assert d.verdict == "ask" and d.pattern == "", (root, rel)


@pytest.mark.parametrize("cmd", ["echo x > ~/Developer/repo/.claude/settings.json", "cp evil ~/Developer/repo/.vscode/tasks.json",
                                 "mv x ~/Developer/repo/.envrc", "tee ~/Developer/repo/.Obsidian/app.json",
                                 "mkdir ~/Developer/repo/.claude", "cp -R hooks ~/Developer/repo/.claude",
                                 "mv ~/Developer/repo/claude ~/Developer/repo/.claude"])
def test_shell_writes_into_run_later_paths_ask(cmd, cfg):
    d = classify_shell(cmd, DEV, cfg)
    assert d.verdict == "ask" and d.pattern == ""


def test_a_yes_always_does_not_unlock_run_later_paths(cfg):
    from jarvis.brain.gate import classify_path_write
    for rel in (".claude", ".obsidian", ".vscode"):
        cfg.trusted.add(f"write:{DEV / 'repo' / rel}")
    cfg.trusted.add(f"write:{DEV / 'repo'}")
    for rel in (".claude/settings.json", ".obsidian/app.json", ".vscode/tasks.json", ".envrc"):
        assert classify_path_write(DEV / "repo" / rel, cfg).verdict == "ask"


def test_symlink_into_a_run_later_folder_is_caught(tmp_path, cfg_for):
    from jarvis.brain.gate import classify_path_write
    free = tmp_path / "free"
    (free / "repo" / ".vscode").mkdir(parents=True)
    (free / "link").symlink_to(free / "repo" / ".vscode")
    (free / "env").symlink_to(free / "repo" / ".envrc")  # dangling: the .envrc does not exist yet
    c = cfg_for(free)
    for p in (free / "link" / "tasks.json", free / "env"):
        d = classify_path_write(p, c)
        assert d.verdict == "ask" and d.pattern == "", p
    assert classify_shell(f"cp x {free / 'link' / 'tasks.json'}", free, c).verdict == "ask"


@pytest.mark.parametrize("rel", [".clauderc", "claude/settings.json", "my.vscode.md", ".envrc.example", "notes/obsidian.md",
                                 "docs/.claude.md"])
def test_run_later_neighbours_stay_free(rel, cfg):
    from jarvis.brain.gate import classify_path_write
    assert classify_path_write(DEV / "repo" / rel, cfg).verdict == "allow"
