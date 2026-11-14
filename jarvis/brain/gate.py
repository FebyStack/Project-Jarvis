"""Ask-first gate (spec §6.5): fixed rules only, no model inside.

A Decision's `pattern` is what a "yes, always" stores in the trusted list.
An empty pattern means the decision can never be remembered (sudo, protected
paths, paths that cannot be resolved, commands that run other commands).
"""
import glob
import os
import re
import shlex
import unicodedata
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


# Files here run code later without Jarvis running anything: git config and hooks (they make later "read-only" git
# commands run programs), Claude Code settings and hooks, Obsidian plugins, VS Code tasks, direnv. A path with one of
# these names anywhere (the name itself too, so mv/mkdir cannot make one) is protected.
_RUN_LATER = {".git", ".claude", ".obsidian", ".vscode", ".envrc"}


def _protects(real: Path, cfg: GateConfig) -> bool:
    """A protected path, anything inside one, a folder that holds one (moving or deleting it moves the gate),
    or a path through a _RUN_LATER name.
    Compared case-folded: the Mac's disk ignores letter case."""
    r = Path(str(real).casefold())
    if _RUN_LATER & set(r.parts):
        return True
    for p in cfg.protected:
        pr = Path(str(Path(p).expanduser().resolve()).casefold())
        if r.is_relative_to(pr) or pr.is_relative_to(r):
            return True
    return False


def _where(real: Path, cfg: GateConfig) -> str:
    if _protects(real, cfg):
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


def _resolve(token: str, cwd: Path | None) -> list[Path] | None:
    """Real paths a shell word can touch, or None if code cannot know. cwd None means the folder is unknown."""
    if token in _SAFE_DEVICES:
        return []
    if _UNRESOLVABLE.search(token):
        return None
    expanded = os.path.expanduser(token)
    if expanded.startswith("~"):
        return None  # ~+, ~-, ~unknownuser: not a home folder code can name
    if not os.path.isabs(expanded) and cwd is None:
        return None
    base = Path(expanded) if os.path.isabs(expanded) else cwd / expanded
    folder, name = os.path.split(str(base))
    if _GLOB.search(folder):
        return None  # a glob over folders can pass through symlinks we cannot see
    reals = [base.resolve()]
    if _GLOB.search(name):
        reals += [Path(m).resolve() for m in glob.glob(str(base))]
    return reals


def _judge_targets(cmd: str, targets: list[str], cwd: Path | None, cfg: GateConfig) -> Decision:
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
             ("uv", "add"), ("uv", "pip install")}
_EXEC_OPTIONS = ("--receive-pack", "--upload-pack", "--exec", "--config", "-c")
_FIND_UNSAFE = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"}
_NEVER_CMDS = {"sudo", "su", "doas", "pkexec"}
# Commands that run other commands: a "yes, always" for one would unlock everything, so they are never remembered.
_RUNNERS = {"sh", "bash", "zsh", "dash", "fish", "ksh", "csh", "tcsh", "env", "xargs", "eval", "exec", "command",
            "builtin", "nohup", "timeout", "gtimeout", "time", "nice", "watch", "parallel", "osascript", "open",
            "script", "source", ".", "awk", "gawk", "nawk", "perl", "ruby", "php", "lua", "node", "deno", "bun",
            "npx", "uvx", "pipx", "alias", "function", "trap", "launchctl", "crontab", "at", "batch", "ssh",
            "caffeinate", "sandbox-exec", "arch", "login", "screen", "tmux", "expect", "make", "just",
            # builtins that change how later commands resolve
            "export", "set", "unset", "hash", "declare", "typeset", "readonly", "local", "enable", "shopt",
            "setopt", "ulimit", "umask", "printf", "read", "mapfile", "readarray",
            # zsh: precommand modifiers that run the next word, history re-runs, and more variable setters
            "noglob", "nocorrect", "-", "fc", "r", "print", "vared", "zparseopts", "getopts", "let", "autoload",
            "zmodload", "emulate", "functions", "disable", "repeat", "sched", "zpty", "foreach", "integer", "float",
            "private", "unsetopt", "zle", "bindkey", "zcompile", "unalias", "unfunction", "unhash"}
_OPTION = re.compile(r"-[A-Za-z]+|--[a-z][a-z-]*(=.*)?")
_NAV = {"cd", "pushd", "popd"}
_RESERVED = {"!", "if", "then", "else", "elif", "do", "while", "until", "case", "select", "{", "}", "coproc",
             "fi", "done", "esac"}
# Only these subcommands can be remembered with "yes, always"; any other (run, exec, explore, aliases…) asks every time.
_REMEMBERABLE = {
    "git": {"push", "pull", "fetch", "commit", "add", "checkout", "switch", "merge", "rebase", "stash", "tag", "restore",
            "reset", "rm", "mv", "init", "clone", "cherry-pick", "revert"},
    "brew": {"install", "uninstall", "reinstall", "upgrade", "update", "cleanup", "tap", "untap"},
    "npm": {"install", "i", "ci", "uninstall", "update"},
    "pip": {"install", "uninstall", "download"},
    "pip3": {"install", "uninstall", "download"},
    "uv": {"add", "remove", "sync", "lock", "venv", "pip install", "pip uninstall", "pip list"},
}
_SYSTEM_BINS = {"/bin", "/usr/bin", "/usr/sbin", "/sbin", "/opt/homebrew/bin", "/usr/local/bin"}
_SUDO = re.compile(r"(?<![\w-])sudo(?![\w-])")
_SUBST = re.compile(r"[$<>]\(([^()]*)\)|`([^`]*)`")
_SUB_PLACEHOLDER = "$__jarvis_sub__"  # contains $, so as a path or a command it is unresolvable
_PUNCT = set("();<>|&")
_OPS = re.compile(r"&>>|&>|>>|>\||>&|<>|<<<|<<-|<<|<&|&&|\|\||\|&|;;&|;;|;&|[;&|()<>]")


def _operands(args: list[str]) -> list[str]:
    """Arguments a path command treats as paths: options stop at "--" or at the first operand (BSD getopt)."""
    out, options = [], True
    for a in args:
        if options and a == "--":
            options = False
        elif options and _OPTION.fullmatch(a):
            continue
        else:
            options = False
            out.append(a)
    return out


def _git_read_only(args: list[str]) -> bool:
    sub, rest = args[0], args[1:]
    if sub not in _GIT_READ or any(a.startswith("--output") for a in rest):
        return False
    return sub != "branch" or all(a in _BRANCH_LIST_FLAGS for a in rest)


def _classify_part(tokens: list[str], cwd: Path | None, cfg: GateConfig) -> Decision:
    while tokens and tokens[0] in _RESERVED:  # `then rm …`, `! rm …`: judge the command, not the keyword
        tokens = tokens[1:]
    if not tokens:
        return Decision("allow", "shell keyword only")
    word, args = tokens[0], tokens[1:]
    cmd = os.path.basename(word)
    if cmd in _NEVER_CMDS or "sudo" in (os.path.basename(t) for t in tokens):
        return Decision("never", "needs root; Febriel runs it himself")
    if "=" in word or "$" in word:
        return Decision("ask", f"cannot tell what command {word!r} runs")
    if "/" in word and os.path.dirname(word) not in _SYSTEM_BINS:
        return Decision("ask", f"program outside the system folders: {word}")
    if cmd in _RUNNERS or re.fullmatch(r"(python|perl|ruby|php|node|lua)[\d.]*", cmd):
        return Decision("ask", f"{cmd} runs other commands")
    if cmd in _NAV:
        return Decision("allow", f"{cmd} only changes folder")
    if cmd in _READ_ONLY:
        if cmd == "rg" and any(a.startswith("--pre") for a in args):
            return Decision("ask", "rg --pre runs another program")
        if cmd == "file" and any(a.startswith("-C") or a == "--compile" for a in args):
            return Decision("ask", "file -C writes magic files")
        return Decision("allow", f"{cmd} is read-only")
    if cmd == "find":
        if any(a in _FIND_UNSAFE for a in args):
            return Decision("ask", "find that deletes, writes, or runs commands")
        return Decision("allow", "find is read-only")
    if cmd in _PATH_CMDS:
        targets = _operands(args)
        return _judge_targets(cmd, targets[-1:] if cmd == "cp" else targets, cwd, cfg)
    if cmd in _SUBCOMMAND_CMDS:
        if cmd == "git" and args and _git_read_only(args):
            return Decision("allow", f"git {args[0]} is read-only")
        sub = args[0] if args else ""
        if cmd == "uv" and sub == "pip" and len(args) > 1:
            sub = f"pip {args[1]}"
        why = "installs software" if (cmd, sub) in _INSTALLS else f"{cmd} {sub} changes state".replace("  ", " ")
        # Options before the subcommand, or options that run programs, change what the pattern means: never remember.
        if sub.startswith("-") or any(a.startswith(_EXEC_OPTIONS) for a in args[1:]):
            return Decision("ask", f"{cmd} with options that change what it runs")
        if sub not in _REMEMBERABLE[cmd]:
            return Decision("ask", f"{cmd} {sub} may run scripts or packages".replace("  ", " "))
        return _ask_unless_trusted(Decision("ask", why, f"shell:{cmd} {sub}".rstrip()), cfg)
    return _ask_unless_trusted(Decision("ask", f"unrecognised command: {cmd}", f"shell:{cmd}"), cfg)


def classify_shell(command: str, cwd: Path | None, cfg: GateConfig) -> Decision:
    command = command.replace("\\\n", "")  # backslash-newline joins lines, as in the shell
    if _SUDO.search(command):
        return Decision("never", "needs sudo; Febriel runs it himself")
    cwd = None if cwd is None else Path(os.path.expanduser(str(cwd)))

    decisions: list[Decision] = []
    while m := _SUBST.search(command):  # innermost $(...), <(...), >(...), `...` first
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        decisions.append(classify_shell(inner, None, cfg))  # a cd elsewhere may run first: folder unknown
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
        if not (t and set(t) <= _PUNCT):
            parts[-1].append(t)
            i += 1
            continue
        ops = _OPS.findall(t)  # shlex glues adjacent operators (";<"): take them one by one
        if "".join(ops) != t:
            return Decision("ask", "could not parse the operators")
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        for k, op in enumerate(ops):
            if "<" not in op and ">" not in op:
                parts.append([])
                continue
            if k != len(ops) - 1 or nxt is None or set(nxt) <= _PUNCT:
                return Decision("ask", "could not parse a redirect")
            if ">" in op and not (op.endswith("&") and (nxt.isdigit() or nxt == "-")):
                redirects.append(nxt)
            i += 1  # the redirect's word is consumed (input files and heredoc delimiters are only read)
        i += 1

    parts = [p for p in parts if p]
    # After cd/pushd/popd the working folder is unknown, so relative paths cannot be judged.
    words = (next((t for t in p if t not in _RESERVED), "") for p in parts)  # `{ cd x; }`: skip the keyword
    where = None if any(os.path.basename(w) in _NAV for w in words) else cwd
    decisions += [_classify_part(p, where, cfg) for p in parts]
    if redirects:
        decisions.append(_judge_targets(">", redirects, where, cfg))
    return _strictest(decisions)


# ── on screen and connector tools ────────────────────────────────────────────

ASK_WORDS: tuple[str, ...] = ("send", "submit", "post", "publish", "pay", "buy", "delete", "remove", "confirm", "sign")


def _forms(word: str) -> set[str]:
    stem = word[:-1] if word.endswith("e") else word
    return {word, word + "s", word + "es", word + "d", word + "ed", stem + "ing", word + "ing"}


_ASK_FORMS = {f: w for w in ASK_WORDS for f in _forms(w)} | {
    "sent": "send", "paid": "pay", "bought": "buy", "submitted": "submit", "submitting": "submit"}
_RETURN_KEYS = {"return", "enter", "kp_enter", "kpenter", "keypadenter", "numpadenter"}
_COMMAND_MODIFIERS = {"cmd", "command", "meta", "super", "win", "ctrl", "control", "alt", "option", "opt", "fn"}
# agent-desktop roles where a click only places focus, scrolls or selects (textarea/searchfield fold into textfield).
_PASSIVE_ROLES = {"textfield", "scrollarea", "scrollbar", "list", "outline", "cell"}


def _ask_return(app: str, cfg: GateConfig) -> Decision:
    return _ask_unless_trusted(Decision("ask", f"press Return in {app}", f"screen:{app}:key:return"), cfg)


def classify_screen(action: Literal["click", "type", "press", "scroll", "open", "drag"], app: str, cfg: GateConfig,
                    role: str = "", label: str = "", key: str = "", text: str = "") -> Decision:
    if action == "click":
        label = unicodedata.normalize("NFKC", label)
        if not label.isascii():  # look-alike letters, soft hyphens, zero-width marks: cannot be read reliably
            return Decision("ask", f"click {label!r} in {app}: label has characters the gate cannot read")
        if not label.strip():
            if role.strip().lower() in _PASSIVE_ROLES:
                return Decision("allow", f"click unlabelled {role} in {app}")
            return Decision("ask", f"click unlabelled {role or 'element'} in {app}: cannot tell what it does")
        word = next((_ASK_FORMS[w] for w in re.findall(r"[a-z]+", label.lower()) if w in _ASK_FORMS), None)
        if word is None:
            return Decision("allow", f"click {label!r} in {app}")
        return _ask_unless_trusted(Decision("ask", f"click {label!r} in {app}", f"screen:{app}:{word}"), cfg)
    if action == "type":
        return _ask_return(app, cfg) if ("\n" in text or "\r" in text) else Decision("allow", f"type in {app}")
    if action == "press":
        if "\n" in key or "\r" in key:
            return _ask_return(app, cfg)
        *mods, base = [k.strip().lower() for k in key.split("+")] if "+" in key.strip("+") else [key.strip().lower()]
        if base in _RETURN_KEYS:
            return _ask_return(app, cfg)
        if _COMMAND_MODIFIERS & set(mods):  # shortcuts can delete, send or quit; plain keys and Shift are free
            combo = "+".join(sorted(mods) + [base])
            return _ask_unless_trusted(Decision("ask", f"press {combo} in {app}", f"screen:{app}:key:{combo}"), cfg)
        return Decision("allow", f"press {key} in {app}")
    if action == "drag":  # a drop can move or delete files and the gate cannot see the destination
        return _ask_unless_trusted(Decision("ask", f"drag in {app}", f"screen:{app}:drag"), cfg)
    if action in ("scroll", "open"):
        return Decision("allow", f"{action} in {app}")
    return Decision("ask", f"unknown on-screen action {action!r}")


def classify_tool(name: str, cfg: GateConfig) -> Decision:
    if name in cfg.read_tools:
        return Decision("allow", f"{name} only reads")
    return _ask_unless_trusted(Decision("ask", f"{name} may write or send", f"tool:{name}"), cfg)
