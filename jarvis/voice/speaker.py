"""Replies spoken sentence by sentence as they stream; `say` (Daniel) when synthesis or the player fails."""
import asyncio
import logging
from typing import Awaitable, Callable

import numpy as np

from jarvis.voice.audio import Player
from jarvis.voice.engines import RATE_OUT
from jarvis.voice.sentences import Splitter

log = logging.getLogger("jarvisd")
TONE = (0.25 * np.sin(2 * np.pi * 880 * np.arange(round(0.08 * RATE_OUT)) / RATE_OUT)).astype(np.float32)


async def say_daniel(text: str) -> None:
    # The text goes on stdin: as an argument, a reply starting with "-" would be read as an option (`-o` writes a file).
    proc = await asyncio.create_subprocess_exec("say", "-v", "Daniel", "-f", "-", stdin=asyncio.subprocess.PIPE)
    try:
        await proc.communicate(text.encode())
    except asyncio.CancelledError:
        proc.kill()
        raise


def _chunks(text: str) -> list[str]:
    s = Splitter()
    return s.feed(text) + s.flush()


def _overlap(fed: str, said: str) -> int:
    """How much of the start of `said` the end of `fed` already holds."""
    return next((k for k in range(min(len(fed), len(said)), 0, -1) if fed.endswith(said[:k])), 0)


class VoiceSpeaker:
    """Implements the core's `Speaker`. Built on the running loop; the player's callbacks hop to it."""
    def __init__(self, synth: Callable[[str], Awaitable[np.ndarray]], player: Player,
                 fallback: Callable[[str], Awaitable[None]] = say_daniel):
        self._loop = asyncio.get_running_loop()
        self._synth, self.player, self._fallback = synth, player, fallback
        self.on_start: Callable[[], None] = lambda: None
        self.on_done: Callable[[], None] = lambda: None
        player.on_start = lambda: self._loop.call_soon_threadsafe(self._player_started, self._gen)
        player.on_done = lambda: self._loop.call_soon_threadsafe(self._player_done)
        self._gen = 0  # bumped by stop(), so a start from before it is ignored
        self._split, self._fed = Splitter(), ""
        self._free = asyncio.Event()
        self._free.set()
        self._active = self._speaking = self._working = False
        self._hints: dict[str, np.ndarray] = {}  # holding lines, synthesized once
        self._hinting = False  # a holding line's run is playing: a reply joining it starts no run of its own
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._task = self._loop.create_task(self._consume())
        self._loop.call_later(1, self._watch)

    def _watch(self) -> None:
        """Once a second: a run whose output device vanished never ends by itself, so it is stopped here."""
        self._loop.call_later(1, self._watch)
        if self.player.stalled():
            log.warning("the speaker stopped playing; its run was ended")
            self.player.stop()

    @property
    def hinting(self) -> bool:
        """A holding line's run is playing (read-only)."""
        return self._hinting

    def feed(self, delta: str) -> None:
        self._fed += delta
        self._push(self._split.feed(delta))

    def say(self, text: str) -> None:
        """The complete reply. What was fed already covers its start (the stream lags) or all of it (a turn's text
        is its last message); if it covers none of it, the reply is something else and is spoken whole."""
        fed, said = " ".join(self._fed.split()), " ".join(text.split())
        k = _overlap(fed, said)
        chunks = self._split.feed(said[k:]) + self._split.flush() if k else self._split.flush() + _chunks(said)
        self._split, self._fed = Splitter(), ""
        self._active = True
        self._push(chunks)
        self._loop.call_soon(self._maybe_done)  # nothing speakable is done at once

    def stop(self) -> None:
        self._gen += 1
        self._task.cancel()  # throws away a synthesis in flight; kills `say`
        self._queue, self._working = asyncio.Queue(), False
        self._split, self._fed = Splitter(), ""
        self.player.stop()
        self._task = self._loop.create_task(self._consume())
        self._loop.call_soon(self._maybe_done)

    def hold(self, on: bool) -> None:
        self._free.clear() if on else self._free.set()
        if on and self._hinting and not self._active:
            self.player.stop()  # the talk key cuts a holding line short

    def cue(self) -> None:
        """Not held and not speech: it plays while listening and leaves the core's state alone."""
        try:
            self.player.play(TONE)
        except Exception as e:
            log.warning("cue did not play: %s", type(e).__name__)

    def hint(self, text: str) -> None:
        """A holding line while the brain works. Like the tone, it leaves the core's state alone."""
        if self._active or not self._free.is_set():
            return
        self._hint_task = self._loop.create_task(self._hint(text, self._gen))  # kept, so it is not collected

    async def warm(self, texts) -> None:
        """Makes the holding lines ahead, so none waits on synthesis when it is needed."""
        for text in texts:
            try:
                await self._made(text)
            except Exception as e:
                log.warning("hint not made: %s", type(e).__name__)

    async def _made(self, text: str) -> np.ndarray:
        if text not in self._hints:
            self._hints[text] = await self._synth(text)
        return self._hints[text]

    async def _hint(self, text: str, gen: int) -> None:
        try:
            pcm = await self._made(text)
            if gen == self._gen and self._free.is_set() and not self._active:  # no stop, hold or reply meanwhile
                self._hinting = True
                self.player.play(pcm)
        except Exception as e:
            log.warning("hint did not play: %s", type(e).__name__)

    def _push(self, chunks: list[str]) -> None:
        for c in chunks:
            self._active = True
            self._queue.put_nowait(c)

    def _begin(self) -> None:
        if not self._speaking:
            self._speaking = True
            self.on_start()

    def _player_started(self, gen: int) -> None:
        if gen == self._gen and self._active:
            self._begin()

    def _player_done(self) -> None:
        if not self.player.busy:  # not a new run's: a hint may have just started one
            self._hinting = False
        self.player.close()
        self._maybe_done()

    def _maybe_done(self) -> None:
        if self._active and not self._working and self._queue.empty() and not self.player.busy:
            self._active = self._speaking = False
            self.on_done()

    async def _consume(self) -> None:
        while True:
            text = await self._queue.get()
            self._working = True
            try:
                pcm = await self._synth(text)
                await self._free.wait()
                self.player.play(pcm)
                if self._hinting:  # queued behind a holding line: the player's start has already gone
                    self._begin()
            except Exception as e:
                log.warning("speech fell back to say: %s", type(e).__name__)
                await self._free.wait()
                self._begin()
                try:
                    await self._fallback(text)
                except Exception as e:
                    log.error("say failed too: %s", type(e).__name__)
            self._working = False
            self._loop.call_soon(self._maybe_done)  # after the player's own start/done, already on the loop's queue
