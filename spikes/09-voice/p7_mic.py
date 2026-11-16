"""P7: read the mic for 10 s, log RMS numbers only (never samples)."""
import os
import numpy as np
import sounddevice as sd

LOG = os.path.expanduser("~/.jarvis/probe-p7.log")
pcm = sd.rec(10 * 16000, samplerate=16000, channels=1, dtype="int16"); sd.wait()
x = pcm[:, 0].astype(np.float64)
rms = [float(np.sqrt(np.mean(x[i * 16000:(i + 1) * 16000] ** 2))) for i in range(10)]
with open(LOG, "w") as f:
    f.write(f"P7 rms_per_second={[round(r, 1) for r in rms]} max_abs={int(np.abs(x).max())} "
            f"{'FAIL all zeros: no Microphone permission for this program' if not x.any() else 'PASS real audio'}\n")
