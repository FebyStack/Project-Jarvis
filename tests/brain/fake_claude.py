"""Stand-in for `claude -p` stream-json, run by tests through JARVIS_CLAUDE_BIN.

Reads its settings from $JARVIS_HOME/fake-config.json and logs to $JARVIS_HOME:
fake-starts.jsonl (one {"argv", "pid"} per start) and fake-stdin.jsonl (every stdin line).
Prints an init line, then for each user message an init line and a result echoing it, like the real CLI.
An interrupt control_request gets a control_response and an `error_during_execution` result.
`stubborn`: starts a grandchild (pid in fake-grandchild), and ignores stdin EOF and SIGTERM.
"""
import json, os, subprocess, sys, time
from pathlib import Path

home = Path(os.environ["JARVIS_HOME"])
cfg_file = home / "fake-config.json"
cfg = json.loads(cfg_file.read_text()) if cfg_file.exists() else {}
with open(home / "fake-starts.jsonl", "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "pid": os.getpid()}) + "\n")


def out(obj):
    print(json.dumps(obj), flush=True)


def init(source):
    out({"type": "system", "subtype": "init", "session_id": "fake-session", "apiKeySource": source, "mcp_servers": []})


if cfg.get("stubborn"):
    import signal
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    (home / "fake-grandchild").write_text(str(subprocess.Popen(["sleep", "60"]).pid))
init(cfg.get("api_key_source", "none"))
if cfg.get("exit_after_init"):
    sys.exit(0)
for line in sys.stdin:
    with open(home / "fake-stdin.jsonl", "a") as f:
        f.write(line)
    msg = json.loads(line)
    if msg.get("type") == "control_request":
        out({"type": "control_response", "response": {"subtype": "success", "request_id": msg["request_id"]}})
        out({"type": "result", "subtype": "error_during_execution", "is_error": True, "session_id": "fake-session"})
    elif msg.get("type") == "user":
        init(cfg.get("turn_api_key_source", "none"))
        out({"type": "result", "subtype": "success", "is_error": False, "result": msg["message"]["content"],
             "session_id": "fake-session"})
if cfg.get("stubborn"):
    time.sleep(60)
