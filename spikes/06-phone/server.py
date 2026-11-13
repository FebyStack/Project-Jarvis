"""Spike 6 server: POST /ask on 127.0.0.1:8787 with a bearer token.

Usage: python3 server.py [--ask-first]
  --ask-first  the first request answers needs_reply: true (reply-loop test)
The token lives in ~/.jarvis/token (mode 600) and is never printed.
"""
import hmac, json, os, secrets, socket, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST, PORT = "127.0.0.1", 8787
TOKEN_FILE = Path.home() / ".jarvis" / "token"


def load_token():
    if not TOKEN_FILE.exists():
        TOKEN_FILE.parent.mkdir(mode=0o700, exist_ok=True)
        fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_urlsafe(32))
    os.chmod(TOKEN_FILE, 0o600)
    return TOKEN_FILE.read_text().strip().encode()


TOKEN = load_token()
ask_first = "--ask-first" in sys.argv


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        global ask_first
        if self.path != "/ask":
            return self.reply(404, {"error": "not found"})
        auth = self.headers.get("Authorization", "").encode()
        if not hmac.compare_digest(auth, b"Bearer " + TOKEN):
            return self.reply(401, {"error": "unauthorized"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            text = json.loads(self.rfile.read(n))["text"]
            assert isinstance(text, str) and text.strip()
        except Exception:
            return self.reply(400, {"error": "expected JSON {\"text\": \"...\"}"})
        if ask_first:
            ask_first = False
            return self.reply(200, {"say": f"You said: {text}. Shall I go ahead?", "needs_reply": True})
        return self.reply(200, {"say": f"You said: {text}", "needs_reply": False})

    def log_message(self, fmt, *args):  # never log headers; path and status only
        sys.stderr.write(f"{self.log_date_time_string()} {self.command} {self.path} {args[1] if len(args) > 1 else ''}\n")


if __name__ == "__main__":
    with socket.socket() as s:
        if s.connect_ex((HOST, PORT)) == 0:
            sys.exit(f"port {PORT} is taken; not starting")
    print(f"listening on http://{HOST}:{PORT}/ask (ask-first={ask_first})", flush=True)
    HTTPServer.allow_reuse_address = False  # bind fails if anything holds the port
    HTTPServer((HOST, PORT), Handler).serve_forever()
