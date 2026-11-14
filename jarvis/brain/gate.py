"""Ask-first gate (spec §6.5): fixed rules only, no model inside.

A Decision's `pattern` is what a "yes, always" stores in the trusted list.
An empty pattern means the decision can never be remembered (sudo, protected
paths, paths that cannot be resolved, commands that run other commands).
"""
import glob
import ipaddress
import os
import re
import shlex
import socket
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

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
    """The strictest verdict. When several parts ask, the question names every one of them, and since one "yes,
    always" could not cover them all, it is never remembered."""
    if not decisions:
        return Decision("allow", "nothing to run")
    top = max(decisions, key=lambda d: _RANK[d.verdict])
    asking = [d for d in decisions if d.verdict == "ask"]
    if top.verdict != "ask" or len(asking) == 1:
        return top
    return Decision("ask", "; ".join(dict.fromkeys(d.reason for d in asking)))


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


def _locations(p: Path) -> list[Path]:
    """Where a write to `p` can land: the name itself (its folder resolved), and the target of any symlink."""
    norm = Path(os.path.normpath(p))
    lexical, real = norm.parent.resolve() / norm.name, p.resolve()
    return [lexical] if lexical == real else [lexical, real]


def _scope(real: Path) -> Path:
    """What a "yes, always" covers: the file's folder, or the file alone when that folder is the home folder or above."""
    home = Path.home().resolve()
    return real if real.parent in (home, *home.parents) else real.parent


def classify_path_write(path: Path, cfg: GateConfig) -> Decision:
    *_, real = locs = _locations(Path(os.path.expanduser(str(path))))
    if any(_where(loc, cfg) == "protected" for loc in locs):
        return Decision("ask", f"protected path: {locs[0]}")
    if _where(real, cfg) == "free":
        return Decision("allow", f"inside a free-write area: {real}")
    return _ask_unless_trusted(Decision("ask", f"outside the free-write areas: {real}", f"write:{_scope(real)}"), cfg)


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
    reals = _locations(base)
    if _GLOB.search(name):
        reals += [loc for m in glob.glob(str(base)) for loc in _locations(Path(m))]
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
                    Decision("ask", f"{cmd} writes outside the free-write areas: {real}", f"shell:{cmd}:{_scope(real)}"), cfg)
                if d.verdict == "ask":
                    return d
    return Decision("allow", f"{cmd} stays inside the free-write areas")


# ── local addresses ──────────────────────────────────────────────────────────

_DNS_NAME = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)*")
_LOCAL_SUFFIXES = (".localhost", ".local", ".ts.net")
# Public DNS services whose names resolve to any address written into them (127.0.0.1.nip.io, localtest.me …).
_WILDCARD_DNS = ("nip.io", "sslip.io", "xip.io", "localtest.me", "lvh.me", "vcap.me", "traefik.me", "localhost.direct")
_EMBEDDED_V4 = re.compile(r"(?<!\d)(\d{1,3})[.-](\d{1,3})[.-](\d{1,3})[.-](\d{1,3})(?!\d)")


def local_host(host: str) -> bool:
    """True for a host that reaches this Mac, the LAN or the tailnet. `host` is ASCII, lower-case, no trailing dot.
    Raises ValueError for a name code cannot read; callers ask."""
    if ":" in host:  # urlsplit strips the brackets from an IPv6 literal
        ip = ipaddress.IPv6Address(host)
        ip = ip.ipv4_mapped or ip
    else:
        try:  # inet_aton also reads the forms fetchers accept: 127.1, 2130706433, 0x7f000001
            ip = ipaddress.IPv4Address(socket.inet_aton(host))
        except OSError:
            if not _DNS_NAME.fullmatch(host):
                raise ValueError(host)  # %-escapes, underscores, odd characters: a fetcher may read them differently
            if any(host == w or host.endswith("." + w) for w in _WILDCARD_DNS):
                return True
            if (m := _EMBEDDED_V4.search(host)) and all(int(g) < 256 for g in m.groups()) \
                    and not ipaddress.IPv4Address(".".join(m.groups())).is_global:
                return True  # a name carrying a private address, the way those services build theirs
            # A dotless name only resolves through local search domains, mDNS or Tailscale MagicDNS.
            return "." not in host or host == "localhost" or host.endswith(_LOCAL_SUFFIXES)
    return not ip.is_global  # loopback, private, link-local, unspecified, 100.64/10 (tailnet), reserved


# ── shell ────────────────────────────────────────────────────────────────────

_READ_ONLY = {"ls", "cat", "head", "tail", "grep", "rg", "pwd", "echo", "date", "which", "wc", "stat", "file", "du", "df", "ps",
              "[", "test", "od"}
# The only commands whose "yes, always" is remembered by name (everything else not judged above asks every time).
# Even when remembered, their arguments must not reach a protected path or a local address (_check_args).
# sed, ffmpeg and the like are left out: their scripts and inputs name files in ways the gate cannot follow.
_REMEMBER = {"ln", "chmod", "defaults", "say"}
_SECURITY_CMDS = {"spctl", "csrutil", "fdesetup"}
# Spec §6.5 "without asking": open an app, set the volume, a timer; only these exact forms (the system skill teaches them).
# An app opens only by its full path in the system's app folders: by bare name macOS may pick a planted copy.
_APP_DIRS = (Path("/Applications"), Path("/Applications/Utilities"), Path("/System/Applications"),
             Path("/System/Applications/Utilities"))
_OSASCRIPT = (re.compile(r"set volume output volume (100|[1-9]?\d)"), re.compile(r"set volume output muted (true|false)"),
              re.compile(r'display notification "[^"\\]*"(?: with title "[^"\\]*")?'))
_SECURITY_KEYS = ("quarantine", "com.apple.security", "gatekeeper", "askforpassword", "com.apple.screensaver",
                  "com.apple.alf", "loginwindow")
# zsh and bash syntax the parser cannot model exactly: $'…' and $"…" quoting, ${…} (it can assign), arithmetic,
# zsh's >! and >| clobbering redirects, and any control character (shlex splits on some the shells do not).
_UNMODELLED = re.compile(r"\$['\"]|\$\{|\$\(\(|\$\[|>[!|]|[\x00-\x08\x0b-\x1f\x7f]")
_GIT_READ = {"status", "log", "diff", "show", "branch"}
_BRANCH_LIST_FLAGS = {"-a", "-r", "-v", "-vv", "--all", "--remotes", "--list", "--show-current"}
_PATH_CMDS = {"rm", "mv", "cp", "mkdir", "touch", "tee"}
_SUBCOMMAND_CMDS = {"git", "brew", "npm", "pip", "pip3", "uv"}
_INSTALLS = {("brew", "install"), ("npm", "install"), ("npm", "i"), ("pip", "install"), ("pip3", "install"),
             ("uv", "add"), ("uv", "pip install")}
_EXEC_OPTIONS = ("--receive-pack", "--upload-pack", "--exec", "--config", "-c", "--template")
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


def _candidates(arg: str) -> list[str]:
    """What in one argument could be a path or an address: the word, an option's value, an @file."""
    if arg.startswith("-"):
        out = [arg.split("=", 1)[1]] if "=" in arg else ([arg[2:]] if len(arg) > 2 and arg[1] != "-" else [])
    else:
        out = [arg]
    return [c[1:] if c.startswith("@") else c for c in out if c]


_HOSTISH = re.compile(r"(localhost|\[[0-9a-fA-F:.]+\]|\d{1,3}(?:\.\d{1,3}){3})(?::\d+)?(?:/.*)?", re.I)


def _check_args(cmd: str, args: list[str], cwd: Path | None, cfg: GateConfig) -> Decision | None:
    """Even a remembered command must not reach a protected path or a local address. None when nothing does."""
    for arg in args:
        for c in _candidates(arg):
            if "://" in c:
                parts = urlsplit(c)
                if parts.scheme.lower() not in ("http", "https") or not re.fullmatch(r"[A-Za-z0-9.:\[\]-]+", parts.netloc) \
                        or any(ch in c for ch in "@#\\"):
                    return Decision("ask", f"{cmd}: cannot tell what {c!r} reaches")
                host = parts.hostname
            elif ":" in c.split("/")[0]:  # file:/x, concat:/a|/b, host:path, [user@]host:path: a prefix that hides where
                return Decision("ask", f"{cmd}: cannot tell what {c!r} reaches")
            else:
                host = m.group(1).strip("[]") if (m := _HOSTISH.fullmatch(c)) else None
            if host is not None:
                try:
                    local = local_host(host.lower().rstrip("."))
                except ValueError:
                    local = True
                if local:
                    return Decision("ask", f"{cmd} reaches a local or private address: {c}")
            if c.startswith(("/", "~")) or cwd is None or _where(cwd.resolve(), cfg) == "protected" \
                    or (cwd / c.split("/")[0]).exists():
                reals = _resolve(c, cwd)
                if reals is None:
                    return Decision("ask", f"{cmd}: cannot tell where {c!r} points")
                if any(_where(r, cfg) == "protected" for r in reals):
                    return Decision("ask", f"{cmd} touches protected path {c}")
    return None


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
    if cmd in _SECURITY_CMDS or (cmd == "defaults" and {"write", "delete", "import", "rename"} & set(args)
                                 and any(k in " ".join(args).casefold() for k in _SECURITY_KEYS)):
        return Decision("never", "changes a system security setting; Febriel does that himself")
    if "=" in word or "$" in word:
        return Decision("ask", f"cannot tell what command {word!r} runs")
    if "/" in word and os.path.dirname(word) not in _SYSTEM_BINS:
        return Decision("ask", f"program outside the system folders: {word}")
    if cmd == "open" and len(args) == 2 and args[0] == "-a" and args[1].endswith(".app") \
            and Path(args[1]).parent in _APP_DIRS and Path(args[1]).exists():
        return Decision("allow", f"opens {Path(args[1]).stem}")
    if cmd == "osascript" and len(args) == 2 and args[0] == "-e" and any(r.fullmatch(args[1]) for r in _OSASCRIPT):
        return Decision("allow", "sets the volume or shows a notification")
    if cmd == "sleep" and len(args) == 1 and args[0].isdigit():
        return Decision("allow", "waits")
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
        return _check_args(cmd, args[1:], cwd, cfg) or _ask_unless_trusted(
            Decision("ask", why, f"shell:{cmd} {sub}".rstrip()), cfg)
    if cmd in _REMEMBER:
        return _check_args(cmd, args, cwd, cfg) or _ask_unless_trusted(
            Decision("ask", f"{cmd} may change files or settings", f"shell:{cmd}"), cfg)
    return Decision("ask", f"unrecognised command: {cmd}")


def classify_shell(command: str, cwd: Path | None, cfg: GateConfig) -> Decision:
    command = command.replace("\\\n", "")  # backslash-newline joins lines, as in the shell
    if _SUDO.search(command):
        return Decision("never", "needs sudo; Febriel runs it himself")
    if m := _UNMODELLED.search(command):
        return Decision("ask", f"uses shell syntax the gate cannot read safely: {m.group()!r}")
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
    if any(t.startswith("=") for t in tokens):  # zsh replaces =name with the program's full path
        return Decision("ask", "uses zsh's =name expansion, which the gate cannot follow")

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
