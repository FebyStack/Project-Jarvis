"""The mic and the speaker. Both call back on their own threads; whoever sets a callback hops to its loop."""
import logging
import threading
import time
from collections import deque
from typing import Callable

import numpy as np

from jarvis import config
from jarvis.voice.engines import RATE_OUT

log = logging.getLogger("jarvisd")
TICK = 0.5  # seconds between checks that frames still come
QUIET = 2.0  # seconds without a frame (reopen) or of all-zero samples (no permission)
MAX_WAIT = 30
LEVEL_EVERY = round(0.09 * RATE_OUT)  # samples played between level reports
STALL = 2.0  # seconds a busy run may go without an output callback: past that, its device went away
# PortAudio is not thread-safe: the mic thread and the loop open, stop and close streams only under this lock.
# The stream callbacks never take it (abort waits for a running callback).
_portaudio = threading.Lock()


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
            self._sound = True
            self._say("on")
        elif not self._sound:  # silence after sound on the same stream is the room or the device, not the grant
            self._zeros += len(frame)
            if self._zeros >= QUIET * config.SAMPLE_RATE:  # what macOS gives a process without the grant
                self._say("no permission")
        self.on_frame(frame)

    def _run(self, stopping: threading.Event) -> None:
        sleep = self._sleep or stopping.wait
        wait, fails, why = 1, 0, None
        while not stopping.is_set():
            self._quiet, self._zeros, self._flowed, self._sound = 0.0, 0, False, False
            try:
                with _portaudio:
                    stream = self._open(self._frame)
            except Exception as e:
                fails += 1
                if type(e).__name__ != why or fails % 120 == 0:  # a new reason, else about hourly at the 30 s wait
                    why = type(e).__name__
                    log.warning("mic did not open: %s", why)
            else:
                fails, why = 0, None
                while not stopping.is_set() and self._quiet < QUIET:
                    sleep(TICK)
                    self._quiet += TICK
                try:
                    with _portaudio:
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
    def __init__(self, open_stream=_open_output, reopen_delay: float = config.MIC_REOPEN_DELAY,
                 clock: Callable[[], float] = time.monotonic):
        self.on_start: Callable[[], None] = lambda: None
        self.on_done: Callable[[], None] = lambda: None
        self.on_level: Callable[[float], None] = lambda rms: None
        self.busy = False
        self._open, self._delay, self._clock = open_stream, round(reopen_delay * RATE_OUT), clock
        self._called = 0.0  # when the output callback last ran (or the run began)
        self._lock = threading.Lock()  # the queue and run state, shared with the output callback
        self._queue: deque[np.ndarray] = deque()
        self._stream = None
        self._started, self._tail = False, 0
        self._sq, self._n = 0.0, 0  # sum of squares and count of the samples since the last level report

    def play(self, pcm: np.ndarray) -> None:
        with self._lock:
            self._queue.append(np.asarray(pcm, dtype=np.float32).reshape(-1))
            if self.busy:
                return
            self.busy, self._started, self._tail, self._called = True, False, 0, self._clock()
            self._sq, self._n = 0.0, 0
            old, self._stream = self._stream, None
        try:
            with _portaudio:
                if old is not None:
                    old.close()  # the last run's stream, if close() has not come yet
                self._stream = self._open(self._fill)
        except Exception:
            with self._lock:
                self._queue.clear()
                self.busy = False
            raise

    def stop(self) -> None:
        with self._lock:
            self._queue.clear()
            self._sq, self._n = 0.0, 0
            was, self.busy = self.busy, False
            stream, self._stream = self._stream, None
        if stream is not None:  # outside the lock: abort waits for a running callback
            try:
                with _portaudio:
                    stream.abort()
                    stream.close()
            except Exception as e:  # a vanished device may not abort; the run is over all the same
                log.warning("speaker stream did not stop: %s", type(e).__name__)
        if was:
            self.on_done()

    def stalled(self) -> bool:
        """Busy, but no output callback for STALL s: the device went away mid-run, so no done would come."""
        return self.busy and self._clock() - self._called > STALL

    def close(self) -> None:
        """On the loop, after a run's done: its stream stops here, never from its own callback."""
        with self._lock:
            if self.busy:
                return
            stream, self._stream = self._stream, None
        if stream is not None:
            with _portaudio:
                stream.abort()
                stream.close()

    def _fill(self, out: np.ndarray) -> bool:
        """The output callback: fills `out`; True when the run is over (the loop then close()s its stream)."""
        start = done = False
        level = None
        with self._lock:
            self._called = self._clock()
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
                self._sq += float(np.dot(out[:i], out[:i]))
                self._n += i
                if self._n >= LEVEL_EVERY:
                    level, self._sq, self._n = min(1.0, (self._sq / self._n) ** 0.5), 0.0, 0
                self._tail = len(out) - i
                start, self._started = not self._started, True
            elif self.busy:
                self._tail += len(out)
            if self.busy and not self._queue and self._tail >= self._delay:
                self.busy, done = False, True
            over = not self.busy
        if start:
            self.on_start()
        if level is not None:
            self.on_level(level)
        if done:
            self.on_done()
        return over
