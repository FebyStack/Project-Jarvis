"""P5 (needs Febriel, speakers at normal volume, mic open): how long after the last output sample does the VAD still fire?"""
import time, threading
import numpy as np
import sounddevice as sd
from openwakeword.vad import VAD
import _common as c

audio = c.speak("Good evening, Febriel. I have finished reading the three emails that came in this afternoon.")
vad, ev = VAD(), []  # (monotonic time, prob)
buf = np.zeros(0, dtype=np.int16)


def cb(indata, frames, t, status):
    global buf
    buf = np.concatenate([buf, indata[:, 0]])
    while len(buf) >= 480:
        ev.append((time.perf_counter(), vad.predict(buf[:480], frame_size=480))); buf = buf[480:]


with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=480, callback=cb):
    time.sleep(1)
    t0 = time.perf_counter(); sd.play(audio, 24000); sd.wait()
    end = time.perf_counter()  # sd.wait returns when the last block has been handed to the device
    time.sleep(1.5)
if not any(p >= 0.5 for t, p in ev if t0 <= t <= end):
    print("P5 VAD never fired while playing: mic does not hear the speakers (or zeros). INCONCLUSIVE")
else:
    last = max(t for t, p in ev if p >= 0.5)
    tail = max(0.0, last - end)
    print(f"P5 vad_fired_after_last_sample={tail:.2f}s {'PASS (keep 0.3 s)' if tail < 0.2 else 'FAIL (set MIC_REOPEN_DELAY >= %.2f)' % (tail + 0.1)}")
