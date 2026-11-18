"""The mic and the speaker. Both call back on their own threads; whoever sets a callback hops to its loop."""
import logging
import threading
from collections import deque
from typing import Callable

import numpy as np

from jarvis import config
from jarvis.voice.engines import RATE_OUT

log = logging.getLogger("jarvisd")
TICK = 0.5  # seconds between checks that frames still come
QUIET = 2.0  # seconds without a frame (reopen) or of all-zero samples (no permission)
MAX_WAIT = 30


def _open_input(on_frame: Callable[[np.ndarray], None]):
    import sounddevice as sd
    stream = sd.InputStream(samplerate=config.SAMPLE_RATE, channels=1, dtype="int16", blocksize=config.FRAME,
                            callback=lambda indata, frames, t, status: on_frame(indata[:, 0].copy()))
    try:
        stream.start()
    except Exception:
        stream.close()
        raise
    return stream


class Mic:
    def __init__(self, open_stream=_open_input, sleep: Callable[[float], object] | None = None):
        self.on_frame: Callable[[np.ndarray], None] = lambda frame: None
        self.on_word: Callable[[str], None] = lambda word: None
        self._open, self._sleep = open_stream, sleep  # sleep defaults to a wait that stop() cuts short
        self._thread: threading.Thread | None = None
        self._word = None

    def start(self) -> None:
        if self._thread is None:
            self._stopping = threading.Event()
            self._thread = threading.Thread(target=self._run, args=(self._stopping,), name="mic", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        if self._thread is not None:
            self._stopping.set()
            self._thread.join(timeout=2.0)
            self._thread = None

    def _say(self, word: str) -> None:
        if word != self._word:
            self._word = word
            self.on_word(word)

    def _frame(self, frame: np.ndarray) -> None:
        self._quiet, self._flowed = 0.0, True
        if frame.any():
            self._zeros = 0
            self._say("on")
        else:
            self._zeros += len(frame)
            if self._zeros >= QUIET * config.SAMPLE_RATE:  # what macOS gives a process without the grant
                self._say("no permission")
        self.on_frame(frame)

    def _run(self, stopping: threading.Event) -> None:
        sleep = self._sleep or stopping.wait
        wait = 1
        while not stopping.is_set():
            self._quiet, self._zeros, self._flowed = 0.0, 0, False
            try:
                stream = self._open(self._frame)
            except Exception as e:
                log.warning("mic did not open: %s", type(e).__name__)
            else:
                while not stopping.is_set() and self._quiet < QUIET:
                    sleep(TICK)
                    self._quiet += TICK
                try:
                    stream.close()
                except Exception as e:
                    log.warning("mic did not close: %s", type(e).__name__)
                if self._flowed:
                    wait = 1
            self._say("off")
            if not stopping.is_set():
                sleep(wait)
                wait = min(wait * 2, MAX_WAIT)


def _open_output(fill: Callable[[np.ndarray], bool]):
    import sounddevice as sd

    def callback(outdata, frames, t, status):
        fill(outdata[:, 0])  # never CallbackStop: its stop racing the loop's abort (Escape) deadlocks CoreAudio
    stream = sd.OutputStream(samplerate=RATE_OUT, channels=1, dtype="float32", callback=callback)
    try:
        stream.start()
    except Exception:
        stream.close()
        raise
    return stream


class Player:
    """A run: from the first play() until reopen_delay of silence after the last sample. A stream per run, so a
    changed output device is picked up; only the loop stops it (stop, close, the next play)."""
    def __init__(self, open_stream=_open_output, reopen_delay: float = config.MIC_REOPEN_DELAY):
        self.on_start: Callable[[], None] = lambda: None
        self.on_done: Callable[[], None] = lambda: None
        self.busy = False
        self._open, self._delay = open_stream, round(reopen_delay * RATE_OUT)
        self._lock = threading.Lock()  # the queue and run state, shared with the output callback
        self._queue: deque[np.ndarray] = deque()
        self._stream = None
        self._started, self._tail = False, 0

    def play(self, pcm: np.ndarray) -> None:
        with self._lock:
            self._queue.append(np.asarray(pcm, dtype=np.float32).reshape(-1))
            if self.busy:
                return
            self.busy, self._started, self._tail = True, False, 0
            old, self._stream = self._stream, None
        if old is not None:
            old.close()  # the last run's stream, if close() has not come yet
        try:
            self._stream = self._open(self._fill)
        except Exception:
            with self._lock:
                self._queue.clear()
                self.busy = False
            raise

    def stop(self) -> None:
        with self._lock:
            self._queue.clear()
            was, self.busy = self.busy, False
            stream, self._stream = self._stream, None
        if stream is not None:  # outside the lock: abort waits for a running callback
            stream.abort()
            stream.close()
        if was:
            self.on_done()

    def close(self) -> None:
        """On the loop, after a run's done: its stream stops here, never from its own callback."""
        with self._lock:
            if self.busy:
                return
            stream, self._stream = self._stream, None
        if stream is not None:
            stream.abort()
            stream.close()

    def _fill(self, out: np.ndarray) -> bool:
        """The output callback: fills `out`; True when the run is over (the loop then close()s its stream)."""
        start = done = False
        with self._lock:
            i = 0
            while i < len(out) and self._queue:
                head = self._queue[0]
                n = min(len(out) - i, len(head))
                out[i:i + n] = head[:n]
                if n == len(head):
                    self._queue.popleft()
                else:
                    self._queue[0] = head[n:]
                i += n
            out[i:] = 0
            if i:
                self._tail = len(out) - i
                start, self._started = not self._started, True
            elif self.busy:
                self._tail += len(out)
            if self.busy and not self._queue and self._tail >= self._delay:
                self.busy, done = False, True
            over = not self.busy
        if start:
            self.on_start()
        if done:
            self.on_done()
        return over
