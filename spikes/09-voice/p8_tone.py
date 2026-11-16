"""P8: 880 Hz, 80 ms sine at 1/4 full scale through the speakers with the mic open: does the VAD fire, does Parakeet return text?"""
import time
import numpy as np
import sounddevice as sd
from openwakeword.vad import VAD
import _common as c

vad, mic, ev = VAD(), [], []
buf = np.zeros(0, dtype=np.int16)


def cb(indata, frames, t, status):
    global buf
    mic.append(indata[:, 0].copy()); buf = np.concatenate([buf, indata[:, 0]])
    while len(buf) >= 480:
        ev.append(vad.predict(buf[:480], frame_size=480)); buf = buf[480:]


tone = (0.25 * np.sin(2 * np.pi * 880 * np.arange(int(0.08 * 48000)) / 48000)).astype(np.float32)
c.transcribe(np.zeros(16000, dtype=np.float32))
with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=480, callback=cb):
    time.sleep(1.0); ev.clear(); mic.clear()
    for _ in range(5):
        sd.play(tone, 48000); sd.wait(); time.sleep(0.6)
    time.sleep(0.5)
pcm = np.concatenate(mic)
rms = float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))
if rms == 0:
    print("P8 mic gives all-zero samples for this process: NOT MEASURABLE from here"); raise SystemExit
text, _ = c.transcribe(pcm.astype(np.float32) / 32768)
print(f"P8 mic_rms={rms:.1f} vad_max={max(ev):.3f} vad_fired={max(ev) >= 0.5} text={text!r} "
      f"{'PASS' if max(ev) < 0.5 and not text else 'FAIL'} (bar: neither)")
