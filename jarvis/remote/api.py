"""jarvisd's local HTTP and WebSocket API on 127.0.0.1 (plan 2, Task 11). Never logs bodies, headers or the token."""
import asyncio
import hmac
import json

from aiohttp import web

from jarvis import config

CHANNELS = ("mac", "phone")
ANSWERS = ("yes", "no", "always")


def _bad(why: str) -> web.Response:
    return web.json_response({"error": why}, status=400)


async def _body(request: web.Request) -> dict | None:
    try:
        body = json.loads(await request.read() or b"{}")
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def make_app(jarvis, token: str) -> web.Application:
    expected = f"Bearer {token}".encode()

    @web.middleware
    async def guard(request: web.Request, handler):
        if request.host not in {f"127.0.0.1:{config.PORT}", f"localhost:{config.PORT}", *config.EXTRA_HOSTS}:
            return web.json_response({"error": "forbidden"}, status=403)
        if not hmac.compare_digest(request.headers.get("Authorization", "").encode(), expected):
            return web.json_response({"error": "unauthorized"}, status=401)
        return await handler(request)

    async def ask(request):
        body = await _body(request)
        text, channel = (body or {}).get("text"), (body or {}).get("channel", "phone")
        if not isinstance(text, str) or not text.strip() or channel not in CHANNELS:
            return _bad("send {\"text\": ...}")
        reply = await jarvis.submit(text.strip(), channel)
        return web.json_response({"say": reply.say} | ({"loop": "yes"} if reply.loop else {}))

    async def answer(request):
        body = await _body(request) or {}
        reply, channel, ask_id = body.get("answer"), body.get("channel"), body.get("ask_id")
        if reply not in ANSWERS or channel not in (None, *CHANNELS) or not isinstance(ask_id, (str, type(None))):
            return _bad("send {\"answer\": \"yes\" | \"no\" | \"always\"}")
        return web.json_response({"answered": jarvis.answer(reply, channel=channel, ask_id=ask_id)})

    async def cancel(request):
        await jarvis.cancel()
        return web.json_response({"ok": True})

    async def hook(request):
        body = await _body(request)
        if body is None:
            return _bad("send the hook payload")
        return web.json_response(await jarvis.hook(body))

    async def health(request):
        return web.json_response(jarvis.health())

    async def events(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        async def pump():
            async for ev in jarvis.subscribe():
                await ws.send_json(ev)
        task = asyncio.create_task(pump())
        try:
            async for _ in ws:  # nothing to read; this ends when the client goes
                pass
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        return ws

    app = web.Application(middlewares=[guard])
    app.add_routes([web.post("/ask", ask), web.post("/answer", answer), web.post("/cancel", cancel),
                    web.post("/hook", hook), web.get("/health", health), web.get("/events", events)])
    return app


async def serve(app: web.Application) -> None:
    """Serves on 127.0.0.1:PORT until cancelled."""
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    try:
        try:
            await web.TCPSite(runner, "127.0.0.1", config.PORT).start()
        except OSError as e:
            raise RuntimeError(f"port {config.PORT} is taken") from e
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
