from pathlib import Path

import pytest

from jarvis.brain.gate import classify_path_write, classify_shell

HOME = Path.home()


@pytest.mark.parametrize("cmd,verdict", [
    ("ls -la ~/Documents", "allow"),
    ("git status", "allow"),
    ("rm ~/Developer/scratch/tmp.txt", "allow"),
    ("rm ~/Documents/tax.pdf", "ask"),
    ("git push origin main", "ask"),
    ("brew install tmux", "ask"),
    ("frobnicate --all", "ask"),
    ("sudo rm -rf /", "never"),
    ("ls && rm -rf ~/Documents", "ask"),
    ("echo hi > ~/Documents/a.txt", "ask"),
    ("printf -v PATH /tmp/x; ls", "ask"),               # -v sets a shell variable: PATH would change what ls runs
    ("printf {-v,PATH} /tmp/x; ls", "ask"),             # brace expansion reaches -v too, so printf is not read-only
    ("cat $(rm ~/Documents/a.txt)", "ask"),
    ("rm ~/Developer/../Documents/a.txt", "ask"),
    ("find ~/Developer -name '*.tmp' -delete", "ask"),
    ("echo 'unterminated", "ask"),
    ("ls; sudo ls", "never"),
])
def test_shell_verdicts(cmd, verdict, cfg):
    assert classify_shell(cmd, HOME, cfg).verdict == verdict


def test_protected_paths_ask_even_inside_free_write(cfg):
    target = HOME / "Developer" / "Project Jarvis" / ".claude" / "settings.json"
    assert classify_path_write(target, cfg).verdict == "ask"


def test_symlink_out_of_free_write_asks(tmp_path, cfg_for):
    free, outside = tmp_path / "free", tmp_path / "outside"
    free.mkdir(); outside.mkdir(); (free / "link").symlink_to(outside)
    assert classify_path_write(free / "link" / "a.txt", cfg_for(free)).verdict == "ask"


def test_trusted_pattern_allows_but_never_stays_never(cfg):
    cfg.trusted.add("shell:git push"); cfg.trusted.add("shell:sudo")
    assert classify_shell("git push", HOME, cfg).verdict == "allow"
    assert classify_shell("sudo ls", HOME, cfg).verdict == "never"


DEV = HOME / "Developer"


@pytest.mark.parametrize("cmd,verdict", [
    ("ls\nrm ~/Documents/a.txt", "ask"),                  # newline is a separator
    ("rm $HOME/Documents/a.txt", "ask"),                  # variables cannot be resolved
    ("rm ~/Developer/{x,../../Documents}", "ask"),        # brace expansion cannot be resolved
    ("rm ~/Developer/*/../a.txt", "ask"),                 # glob in a folder part cannot be resolved
    ("ls 2>/dev/null", "allow"),
    ("cat <(rm ~/Documents/a.txt)", "ask"),               # process substitution
    ("cat `rm ~/Documents/a.txt`", "ask"),
    ("git branch -D main", "ask"),
    ("/bin/rm ~/Documents/a.txt", "ask"),
    ("echo sudo", "never"),                               # sudo anywhere
])
def test_shell_hardening(cmd, verdict, cfg):
    assert classify_shell(cmd, DEV, cfg).verdict == verdict


@pytest.mark.parametrize("cmd,pattern", [
    ("rm ~/Documents/tax.pdf", f"shell:rm:{(HOME / 'Documents').resolve()}"),
    ("git push origin main", "shell:git push"),
    ("brew install tmux", "shell:brew install"),
    ("npm -g install x", ""),  # options before the subcommand: never remembered
    ("frobnicate --all", "shell:frobnicate"),
    ("ls && rm ~/Documents/a.txt", f"shell:rm:{(HOME / 'Documents').resolve()}"),
])
def test_ask_patterns(cmd, pattern, cfg):
    assert classify_shell(cmd, HOME, cfg).pattern == pattern


def test_trusted_rm_folder_does_not_unlock_other_folders(cfg):
    cfg.trusted.add(f"shell:rm:{(HOME / 'Documents').resolve()}")
    assert classify_shell("rm ~/Documents/a.txt", HOME, cfg).verdict == "allow"
    assert classify_shell("rm ~/Documents/a.txt ~/Desktop/b.txt", HOME, cfg).verdict == "ask"


def test_protected_cannot_be_trusted(cfg):
    target = DEV / "Project Jarvis" / ".claude" / "settings.json"
    cfg.trusted.add(classify_path_write(target, cfg).pattern)
    assert classify_path_write(target, cfg).verdict == "ask"
    assert classify_shell(f"rm '{target}'", HOME, cfg).verdict == "ask"


def test_free_write_path_allowed(cfg):
    assert classify_path_write(DEV / "scratch" / "a.txt", cfg).verdict == "allow"


@pytest.mark.parametrize("cmd", ["printf 'gold' > ~/Developer/p.txt", "printf -v PATH /tmp/x", "read PATH <<< /tmp/x",
                                 "mapfile -t PATH < /tmp/x", "readarray PATH < /tmp/x"])
def test_builtins_that_set_variables_ask_and_are_never_remembered(cmd, cfg):
    d = classify_shell(cmd, HOME, cfg)
    assert d.verdict == "ask" and d.pattern == ""      # "always" for printf would later let printf -v PATH through


@pytest.mark.parametrize("cmd", ["print -v PATH /tmp/x", "noglob rm -rf ~/Documents", "- rm ~/Documents/a", "nocorrect rm x",
                                 "vared PATH", "zparseopts -A PATH", "getopts a PATH", "let PATH=1", "fc -e - ",
                                 "r", "autoload x", "zmodload zsh/files", "emulate sh -c 'rm x'", "functions -c a b", "disable rm",
                                 "repeat 1 rm x", "sched +1 rm x", "zpty a rm", "foreach f (x) rm $f; end", "integer PATH",
                                 "float PATH", "private PATH", "unsetopt x", "zle -N x", "bindkey x y", "zcompile x",
                                 "unalias ls", "unfunction x", "unhash ls"])
def test_zsh_builtins_that_run_or_set_things_are_never_remembered(cmd, cfg):
    d = classify_shell(cmd, HOME, cfg)
    assert d.verdict == "ask" and d.pattern == ""      # the Bash tool runs in Febriel's zsh
