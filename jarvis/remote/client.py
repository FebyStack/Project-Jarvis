"""The local client of jarvisd's API, shared by the terminal HUD and the face."""

import asyncio
import json
from collections.abc import AsyncIterator

import aiohttp

from jarvis import config


class Client:
    """jarvisd's local API (Task 11) on the `mac` channel. Errors mean the daemon is away; the HUD shows that."""

    def __init__(self, token: str, base: str = f"http://127.0.0.1:{config.PORT}", retry: float = 2.0):
        self.base, self.retry = base, retry
        self.headers = {"Authorization": f"Bearer {token}"}
        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(headers=self.headers, timeout=aiohttp.ClientTimeout(total=None, connect=5))
        return self._session

    async def _post(self, path: str, body: dict | None = None) -> dict | None:
        try:
            async with self.session.post(self.base + path, json=body) as r:
                return await r.json()
        except (aiohttp.ClientError, OSError, ValueError):
            return None

    async def ask(self, text: str) -> dict | None:
        return await self._post("/ask", {"text": text, "channel": "mac"})

    async def answer(self, reply: str, ask_id: str | None) -> None:
        await self._post("/answer", {"answer": reply, "ask_id": ask_id, "channel": "mac"})

    async def stop(self, agent_id: str) -> dict | None:
        return await self._post("/stop", {"agent": agent_id})

    async def cancel(self) -> None:
        await self._post("/cancel")

    async def events(self) -> AsyncIterator[dict]:
        """Daemon events, plus `link` events of our own; reconnects every `retry` seconds."""
        yield {"type": "link", "state": "connecting"}
        while True:
            try:
                async with self.session.ws_connect(self.base + "/events") as ws:
                    async for msg in ws:
                        if msg.type is aiohttp.WSMsgType.TEXT:
                            yield json.loads(msg.data)
            except (aiohttp.ClientError, OSError, ValueError):
                pass
            yield {"type": "link", "state": "no daemon"}
            await asyncio.sleep(self.retry)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
