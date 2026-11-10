"""Ask-first gate (spec §6.5): fixed rules only, no model inside.

A Decision's `pattern` is what a "yes, always" stores in the trusted list.
An empty pattern means the decision can never be remembered (sudo, protected
paths, paths that cannot be resolved, commands that run other commands).
"""
import glob
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from jarvis.brain.trusted import TrustedList

Verdict = Literal["allow", "ask", "never"]
_RANK = {"allow": 0, "ask": 1, "never": 2}


@dataclass
class Decision:
    verdict: Verdict
    reason: str
    pattern: str = ""


@dataclass
class GateConfig:
    free_write: list[Path]
    protected: list[Path]
    trusted: TrustedList
    read_tools: set[str] = field(default_factory=set)


def _strictest(decisions: list[Decision]) -> Decision:
    # max() keeps the first of equals, so the earliest offending part names the pattern.
    return max(decisions, key=lambda d: _RANK[d.verdict]) if decisions else Decision("allow", "nothing to run")


def _ask_unless_trusted(d: Decision, cfg: GateConfig) -> Decision:
    if d.pattern and cfg.trusted.contains(d.pattern):
        return Decision("allow", f"trusted: {d.pattern}", d.pattern)
    return d


# ── paths ────────────────────────────────────────────────────────────────────

_SAFE_DEVICES = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty"}
_UNRESOLVABLE = re.compile(r"[$`{}]")  # variables, substitutions, brace expansion
_GLOB = re.compile(r"[*?\[]")


def _inside(real: Path, roots: list[Path]) -> bool:
    return any(real.is_relative_to(Path(r).expanduser().resolve()) for r in roots)


def _where(real: Path, cfg: GateConfig) -> str:
    if _inside(real, cfg.protected):
        return "protected"
    return "free" if _inside(real, cfg.free_write) else "out"


def classify_path_write(path: Path, cfg: GateConfig) -> Decision:
    real = Path(os.path.expanduser(str(path))).resolve()
    where = _where(real, cfg)
    if where == "free":
        return Decision("allow", f"inside a free-write area: {real}")
    if where == "protected":
        return Decision("ask", f"protected path: {real}")
    return _ask_unless_trusted(Decision("ask", f"outside the free-write areas: {real}", f"write:{real.parent}"), cfg)


def _resolve(token: str, cwd: Path) -> list[Path] | None:
    """Real paths a shell word can touch, or None if code cannot know."""
    if token in _SAFE_DEVICES:
        return []
    if _UNRESOLVABLE.search(token):
        return None
    expanded = os.path.expanduser(token)
    base = Path(expanded) if os.path.isabs(expanded) else cwd / expanded
    folder, name = os.path.split(str(base))
    if _GLOB.search(folder):
        return None  # a glob over folders can pass through symlinks we cannot see
    reals = [base.resolve()]
    if _GLOB.search(name):
        reals += [Path(m).resolve() for m in glob.glob(str(base))]
    return reals


def _judge_targets(cmd: str, targets: list[str], cwd: Path, cfg: GateConfig) -> Decision:
    for token in targets:
        reals = _resolve(token, cwd)
        if reals is None:
            return Decision("ask", f"{cmd}: cannot tell where {token!r} points")
        for real in reals:
            where = _where(real, cfg)
            if where == "protected":
                return Decision("ask", f"{cmd} touches protected path {real}")
            if where == "out":
                d = _ask_unless_trusted(
                    Decision("ask", f"{cmd} writes outside the free-write areas: {real}", f"shell:{cmd}:{real.parent}"), cfg)
                if d.verdict == "ask":
                    return d
    return Decision("allow", f"{cmd} stays inside the free-write areas")


# ── shell ────────────────────────────────────────────────────────────────────

_READ_ONLY = {"ls", "cat", "head", "tail", "grep", "rg", "pwd", "echo", "date", "which", "wc", "stat", "file", "du", "df", "ps"}
_GIT_READ = {"status", "log", "diff", "show", "branch"}
_BRANCH_LIST_FLAGS = {"-a", "-r", "-v", "-vv", "--all", "--remotes", "--list", "--show-current"}
_PATH_CMDS = {"rm", "mv", "cp", "mkdir", "touch", "tee"}
_SUBCOMMAND_CMDS = {"git", "brew", "npm", "pip", "pip3", "uv"}
_INSTALLS = {("brew", "install"), ("npm", "install"), ("npm", "i"), ("pip", "install"), ("pip3", "install"),
             ("uv", "add"), ("uv", "pip")}
_FIND_UNSAFE = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"}
_SUDO = re.compile(r"(?<![\w-])sudo(?![\w-])")
_SUBST = re.compile(r"[$<>]\(([^()]*)\)|`([^`]*)`")
_SUB_PLACEHOLDER = "$__jarvis_sub__"  # contains $, so as a path it is unresolvable
_PUNCT = set("();<>|&")


def _git_read_only(args: list[str]) -> bool:
    sub, rest = args[0], args[1:]
    if sub not in _GIT_READ or any(a.startswith("--output") for a in rest):
        return False
    return sub != "branch" or all(a in _BRANCH_LIST_FLAGS for a in rest)


def _classify_part(tokens: list[str], cwd: Path, cfg: GateConfig) -> Decision:
    cmd, args = os.path.basename(tokens[0]), tokens[1:]
    if cmd in _READ_ONLY:
        if cmd == "rg" and any(a.startswith("--pre") for a in args):
            return Decision("ask", "rg --pre runs another program")
        return Decision("allow", f"{cmd} is read-only")
    if cmd == "find":
        if any(a in _FIND_UNSAFE for a in args):
            return Decision("ask", "find that deletes, writes, or runs commands")
        return Decision("allow", "find is read-only")
    if cmd in _PATH_CMDS:
        targets = [a for a in args if not a.startswith("-")]
        return _judge_targets(cmd, targets[-1:] if cmd == "cp" else targets, cwd, cfg)
    if cmd in _SUBCOMMAND_CMDS:
        if cmd == "git" and args and _git_read_only(args):
            return Decision("allow", f"git {args[0]} is read-only")
        sub = next((a for a in args if not a.startswith("-")), "")
        why = "installs software" if (cmd, sub) in _INSTALLS else f"{cmd} {sub} changes state".replace("  ", " ")
        return _ask_unless_trusted(Decision("ask", why, f"shell:{cmd} {sub}".rstrip()), cfg)
    return _ask_unless_trusted(Decision("ask", f"unrecognised command: {cmd}", f"shell:{cmd}"), cfg)


def classify_shell(command: str, cwd: Path, cfg: GateConfig) -> Decision:
    if _SUDO.search(command):
        return Decision("never", "needs sudo; Febriel runs it himself")
    cwd = Path(os.path.expanduser(str(cwd)))

    decisions: list[Decision] = []
    while m := _SUBST.search(command):  # innermost $(...), <(...), >(...), `...` first
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        decisions.append(classify_shell(inner, cwd, cfg))
        command = f"{command[:m.start()]} {_SUB_PLACEHOLDER} {command[m.end():]}"

    try:
        lex = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""  # a '#' must not hide what follows it
        tokens = list(lex)
    except ValueError:
        return Decision("ask", "could not parse the command")

    parts: list[list[str]] = [[]]
    redirects: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t and set(t) <= _PUNCT:
            nxt = tokens[i + 1] if i + 1 < len(tokens) else None
            if ">" in t:
                if nxt is None or set(nxt) <= _PUNCT:
                    return Decision("ask", "could not parse a redirect")
                if not (t.endswith("&") and (nxt.isdigit() or nxt == "-")):
                    redirects.append(nxt)
                i += 2
                continue
            if "<" in t:
                i += 2  # input or heredoc delimiter: read only
                continue
            parts.append([])
        else:
            parts[-1].append(t)
        i += 1

    decisions += [_classify_part(p, cwd, cfg) for p in parts if p]
    if redirects:
        decisions.append(_judge_targets(">", redirects, cwd, cfg))
    return _strictest(decisions)
