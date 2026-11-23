import io
import itertools
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from jarvis.brain import hook
from jarvis.brain.hook import render

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"},
           "tool_use_id": "toolu_1"}


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "jarvis-home"
    home.mkdir()
    (home / "token").write_text("s3cret-token")
    monkeypatch.setenv("JARVIS_HOME", str(home))
    return home


@pytest.fixture
def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def stub_server():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            srv = self.server
            srv.last_auth = self.headers.get("Authorization")
            srv.last_path = self.path
            srv.last_body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            time.sleep(srv.delay)
            self.send_response(srv.status)
            self.send_header("Content-Length", str(len(srv.reply)))
            self.end_headers()
            self.wfile.write(srv.reply)

        def log_message(self, *args):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.daemon_threads = True
    srv.port = srv.server_address[1]
    srv.reply, srv.delay, srv.status, srv.last_auth = b"{}", 0.0, 200, None
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def run_main(payload, port, timeout=None):
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(hook, "PORT", port)
        if timeout is not None:
            mp.setattr(hook, "TIMEOUT", timeout)
        stdin = io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))
        stdout = io.StringIO()
        assert hook.main(stdin, stdout) == 0
    return json.loads(stdout.getvalue())


def decision(out):
    return out["hookSpecificOutput"]["permissionDecision"]


def test_render_shapes():
    assert render("PreToolUse", "ask", "why")["hookSpecificOutput"] == {
        "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "why"}
    assert render("PreToolUse", "allow", "ok")["hookSpecificOutput"] == {
        "hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": "ok"}
    assert render("PermissionRequest", "allow", "")["hookSpecificOutput"] == {
        "hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}
    assert render("PermissionRequest", "ask", "why")["hookSpecificOutput"]["decision"] == {"behavior": "deny", "message": "why"}
    assert render("PermissionRequest", "deny", "no")["hookSpecificOutput"]["decision"] == {"behavior": "deny", "message": "no"}


def test_an_allow_can_carry_an_edited_input():
    out = render("PreToolUse", "allow", "ok", {"description": "Nova: x"})
    assert out["hookSpecificOutput"]["updatedInput"] == {"description": "Nova: x"}
    assert "updatedInput" not in render("PreToolUse", "deny", "no", {"description": "x"})["hookSpecificOutput"]
    assert "updatedInput" not in render("PreToolUse", "allow", "ok")["hookSpecificOutput"]


def test_the_edited_input_comes_from_the_daemons_reply(home, stub_server):
    stub_server.reply = b'{"verdict": "allow", "reason": "ok", "input": {"description": "Nova: x"}}'
    out = run_main(PAYLOAD, port=stub_server.port)
    assert out["hookSpecificOutput"]["updatedInput"] == {"description": "Nova: x"}


def test_an_edited_input_that_is_not_an_object_means_no(home, stub_server):
    stub_server.reply = b'{"verdict": "allow", "reason": "ok", "input": "Nova: x"}'
    assert decision(run_main(PAYLOAD, port=stub_server.port)) == "deny"


def test_render_never_says_ask():
    events = ["PreToolUse", "PermissionRequest", "PostToolUse", "", None]
    verdicts = ["allow", "deny", "ask", "Allow", "", None, "maybe"]
    for event, verdict in itertools.product(events, verdicts):
        out = render(event, verdict, "r")
        assert '"ask"' not in json.dumps(out)
        spec = out["hookSpecificOutput"]
        allowed = spec.get("permissionDecision") == "allow" or spec.get("decision") == {"behavior": "allow"}
        assert allowed == (verdict == "allow" and event in ("PreToolUse", "PermissionRequest"))


def test_no_daemon_means_no(home, free_port):          # nothing listens on free_port
    out = run_main(PAYLOAD, port=free_port)
    assert decision(out) == "deny"
    assert "not running" in out["hookSpecificOutput"]["permissionDecisionReason"]


@pytest.mark.parametrize("body", [
    b"not json", b'{"verdict": "maybe"}', b"{}", b'{"verdict": "ask", "reason": "r"}',
    b'{"verdict": "ALLOW", "reason": "r"}', b'{"verdict": "allow", "reason": 5}', b'{"verdict": "allow"}',
    b'["allow"]', b'"allow"', b"",
])
def test_bad_reply_means_no(home, stub_server, body):
    stub_server.reply = body
    assert decision(run_main(PAYLOAD, port=stub_server.port)) == "deny"


@pytest.mark.parametrize("status", [401, 403, 500])
def test_error_status_means_no_even_with_an_allow_body(home, stub_server, status):
    stub_server.status = status
    stub_server.reply = b'{"verdict": "allow", "reason": "ok"}'
    assert decision(run_main(PAYLOAD, port=stub_server.port)) == "deny"


def test_slow_daemon_means_no(home, stub_server):
    stub_server.delay = 2.0
    stub_server.reply = b'{"verdict": "allow", "reason": "ok"}'
    start = time.monotonic()
    assert decision(run_main(PAYLOAD, port=stub_server.port, timeout=0.3)) == "deny"
    assert time.monotonic() - start < 1.5


def test_timeout_is_below_the_hook_timeout():
    from jarvis import config
    assert hook.TIMEOUT == config.HOOK_TIMEOUT - 10


@pytest.mark.parametrize("token", [None, "", "  \n"])
def test_no_token_means_no(home, stub_server, token):
    if token is None:
        (home / "token").unlink()
    else:
        (home / "token").write_text(token)
    stub_server.reply = b'{"verdict": "allow", "reason": "ok"}'
    assert decision(run_main(PAYLOAD, port=stub_server.port)) == "deny"
    assert stub_server.last_auth is None


@pytest.mark.parametrize("stdin", ["", "not json", "[]", '{"tool_name": "Bash"}',
                                   '{"hook_event_name": "PostToolUse", "tool_name": "Bash"}'])
def test_bad_or_unknown_payload_means_no(home, stub_server, stdin):
    stub_server.reply = b'{"verdict": "allow", "reason": "ok"}'
    assert decision(run_main(stdin, port=stub_server.port)) == "deny"
    assert stub_server.last_auth is None


def test_good_reply_passes_through_with_the_token(home, stub_server):
    stub_server.reply = b'{"verdict": "allow", "reason": "ok"}'
    assert decision(run_main(PAYLOAD, port=stub_server.port)) == "allow"
    assert stub_server.last_auth == "Bearer " + (home / "token").read_text()
    assert stub_server.last_path == "/hook"
    assert stub_server.last_body == PAYLOAD


def test_deny_reply_carries_the_reason(home, stub_server):
    stub_server.reply = b'{"verdict": "deny", "reason": "Febriel said no."}'
    out = run_main(PAYLOAD, port=stub_server.port)
    assert out["hookSpecificOutput"] == {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                         "permissionDecisionReason": "Febriel said no."}


def test_permission_request_is_judged_the_same_way(home, stub_server):
    payload = {**PAYLOAD, "hook_event_name": "PermissionRequest"}
    stub_server.reply = b'{"verdict": "allow", "reason": "ok"}'
    assert run_main(payload, port=stub_server.port)["hookSpecificOutput"] == {
        "hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}
    stub_server.reply = b"oops"
    assert run_main(payload, port=stub_server.port)["hookSpecificOutput"]["decision"]["behavior"] == "deny"


def test_ignores_proxy_settings(home, stub_server, monkeypatch):
    for var in ("http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.setenv(var, "http://127.0.0.1:9")    # a proxy would get the token, or nothing
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    stub_server.reply = b'{"verdict": "allow", "reason": "ok"}'
    assert decision(run_main(PAYLOAD, port=stub_server.port)) == "allow"


def test_imports_only_the_standard_library():
    import subprocess
    import sys
    code = ("import sys; import jarvis.brain.hook; "
            "bad = [m for m in sys.modules if m.split('.')[0] in ('aiohttp', 'textual') or m == 'jarvis.brain.gate']; "
            "print(bad)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "[]"


def test_settings_file_hooks_everything():
    settings = json.loads((ROOT / ".claude" / "jarvis-settings.json").read_text())
    hooks = settings["hooks"]
    assert set(hooks) == {"PreToolUse", "PermissionRequest"}
    for event in ("PreToolUse", "PermissionRequest"):
        (entry,) = hooks[event]
        (h,) = entry["hooks"]
        assert entry["matcher"] == "*" and h["type"] == "command" and h["timeout"] == 660
        assert h["command"] == "'/Users/febrielotud/Developer/Project Jarvis/.venv/bin/python' -m jarvis.brain.hook"
    assert not (ROOT / ".claude" / "settings.json").exists()


def test_settings_file_keeps_personal_rules_and_dev_memory_out():
    settings = json.loads((ROOT / ".claude" / "jarvis-settings.json").read_text())
    assert settings["autoMemoryEnabled"] is False
    assert settings["claudeMdExcludes"] == ["/Users/febrielotud/.claude/CLAUDE.md"]
