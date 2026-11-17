"""`Voice`: what an utterance means in each state, the mic's health, and muting. Speech without the name leaves no
trace: no event, no log line, no vault write."""
import asyncio
import logging
import threading
import time

import numpy as np

from jarvis import config
from jarvis.daemon import instant
from jarvis.daemon.state import State
from jarvis.voice import keys, wake
from jarvis.voice.gesture import Kind
from jarvis.voice.segment import Utterance

log = logging.getLogger("jarvisd")


class Voice:
    def __init__(self, jarvis, engines, mic, segmenter, listen=keys.listen):
        self.jarvis, self.engines, self.mic, self.seg, self._listen = jarvis, engines, mic, segmenter, listen
        self._lock = threading.Lock()  # the segmenter, shared by the mic thread and the loop
        self._loop: asyncio.AbstractEventLoop | None = None
        self._open = True  # the mic was open at the last frame
        self._frames = 0
        self._word = "loading"  # the mic's own word
        self._start = ""  # the start of a request cut at the length cap
        self._task: asyncio.Task | None = None
        self._stop_keys = None  # the key listener's stop function; None: no listener
        self._key_down = self._engaged = False
        self._grace: asyncio.TimerHandle | None = None
        self._keyed: set[asyncio.Task] = set()  # utterances from the key, kept so they are not collected
        mic.on_frame = self.on_frame
        mic.on_word = lambda word: self._loop.call_soon_threadsafe(self._mic_word, word)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self.jarvis.set_mic("loading")
        if reason := await self.engines.load():
            return self.jarvis.set_mic(reason)
        self._stop_keys = self._listen(lambda kind: self._loop.call_soon_threadsafe(self.key, kind))
        self._sync()
        self._task = asyncio.create_task(self._follow())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        if self._stop_keys:
            self._stop_keys()
        self.mic.stop()

    async def _follow(self) -> None:
        async for ev in self.jarvis.subscribe():
            if ev["type"] in ("snapshot", "state"):
                self._sync()

    def _sync(self) -> None:
        """On every state change: the kept start lives only while listening; muted, the mic stream is stopped."""
        sm = self.jarvis.sm
        if sm.state is not State.LISTENING:
            self._start = ""
        if sm.muted and sm.state is not State.LISTENING and not self._key_down:
            self.mic.stop()
            with self._lock:
                self.seg.reset()
        else:
            self.mic.start()
        self.jarvis.set_mic(self._shown())

    def _mic_word(self, word: str) -> None:
        self._word = word
        self.jarvis.set_mic(self._shown())

    def _shown(self) -> str:
        if self.jarvis.sm.muted:
            return "muted"
        return "on, no key" if self._word == "on" and self._stop_keys is None else self._word

    def on_frame(self, frame: np.ndarray) -> None:
        """On the mic thread: feeds the cutter while the mic is open; the rest hops to the loop."""
        j, loop = self.jarvis, self._loop
        mic_open = j.sm.mic_open
        with self._lock:
            if not (self.seg.held or mic_open):  # held: the talk key is down
                if self._open:  # Jarvis is speaking (or muted): forget what was being cut
                    self.seg.reset()
                    self._open = False
                return
            self._open = True
            held, quiet = self.seg.held, not (self.seg.speaking or self.seg.heard)
            utt = self.seg.feed(frame)
            started = quiet and (self.seg.speaking or self.seg.heard)
        self._frames += 1
        if self._frames % 3 == 0 and mic_open:  # not while the key waits out its grace: typing shows nothing
            rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
            loop.call_soon_threadsafe(j.level, min(rms / 32768, 1.0))
        if started:
            loop.call_soon_threadsafe(j.speech_started)
        if utt is not None:
            asyncio.run_coroutine_threadsafe(self.on_utterance(utt, by_key=held), loop)

    async def on_utterance(self, utt: Utterance, by_key: bool = False) -> None:
        t0 = time.monotonic()
        try:
            text = await self.engines.transcribe(utt.pcm)
        except Exception as e:
            log.error("transcription failed: %s", type(e).__name__)
            text = ""
        if not text.strip():
            return self.jarvis.give_up()
        if self._act(text, utt.cut, by_key):
            log.info("transcribe %.2f s for %.1f s of speech", time.monotonic() - t0, len(utt.pcm) / config.SAMPLE_RATE)

    def _act(self, text: str, cut: bool, by_key: bool) -> bool:
        """What an utterance means in the state it ended in; False: discarded, leaving no trace."""
        j, r, state = self.jarvis, wake.split(text), self.jarvis.sm.state
        if by_key:
            j.heard(text)
        elif state is State.LISTENING:
            if r == "":  # the name alone again: listen afresh
                j.wake()
            elif r is None and not self._start and instant.is_ack(text) and not j.asks.pending("mac"):
                j.give_up()  # "Okay." as an answer ends: nothing to send
                return False
            else:
                start, self._start = self._start, ""
                j.heard(" ".join(filter(None, (start, r or text))))
        elif state is State.IDLE and r is not None:
            if not j.wake():
                return False
            self._start = r if cut else ""
            if r == "":
                j.cue()
            elif not cut:
                j.heard(r)
        elif state is State.THINKING and r and instant.match(r, pending=False) == "cancel":
            j.heard(r)
        else:
            return False
        return True

    # ---- the talk key ------------------------------------------------------------------------------------------

    def key(self, kind: Kind) -> None:
        """On the loop. Capture starts at once, so no first word is lost; Jarvis engages only after the grace, so
        Right Option used for typing (a chord) stops nothing and shows nothing."""
        if kind == "down":
            self._key_down, self._engaged = True, False
            with self._lock:
                self.seg.hold()
            self._sync()  # starts the mic if muted
            self._grace = self._loop.call_later(config.KEY_GRACE_SECONDS, self._engage)
            return
        self._key_down = False
        if kind == "chord":
            if self._engaged:
                self.jarvis.give_up()
            elif self._grace:
                self._grace.cancel()
            with self._lock:
                self.seg.reset()
        elif kind == "tap":
            self._engage()
            with self._lock:
                self.seg.tap()
            self.jarvis.cue()
        else:  # hold_end
            self._engage()
            with self._lock:
                utt = self.seg.release()
            if utt is None:
                self.jarvis.give_up()
            else:
                task = asyncio.create_task(self.on_utterance(utt, by_key=True))
                self._keyed.add(task)
                task.add_done_callback(self._keyed.discard)
        self._sync()

    def _engage(self) -> None:
        if self._grace:
            self._grace.cancel()
            self._grace = None
        if not self._engaged:
            self._engaged = True
            self.jarvis.wake(key=True)
            with self._lock:
                talking = self.seg.speaking or self.seg.heard
            if talking:  # speech already under way: no 8 s give-up while it runs
                self.jarvis.speech_started()
