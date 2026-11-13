"""Spike 2: open the mic, run openWakeWord "hey jarvis", log each detection. No audio is stored.

usage: wake.py SECONDS LABEL [THRESHOLD]
"""
import json, os, resource, sys, time
import numpy as np
import sounddevice as sd
from openwakeword.model import Model

secs, label = float(sys.argv[1]), sys.argv[2]
threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
here = os.path.dirname(os.path.abspath(__file__))
log = open(os.path.join(here, "tmp", f"{label}.jsonl"), "w")
def note(**kw):
    kw["t"] = round(time.time() - T0, 2); log.write(json.dumps(kw) + "\n"); log.flush(); print(json.dumps(kw), flush=True)

model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
key = next(iter(model.models))
ru0 = resource.getrusage(resource.RUSAGE_SELF); cpu0 = ru0.ru_utime + ru0.ru_stime
T0 = time.time(); last_hit = -10.0; infer_ms = []; peak = 0.0; top = 0.0; hits = 0
note(event="start", model=key, threshold=threshold, device=sd.query_devices(kind="input")["name"])
with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=1280) as stream:
    window = time.time()
    while time.time() - T0 < secs:
        frame, _ = stream.read(1280)
        pcm = frame[:, 0]
        peak = max(peak, float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2))))
        t = time.perf_counter(); score = float(model.predict(pcm)[key]); infer_ms.append((time.perf_counter() - t) * 1000)
        top = max(top, score)
        now = time.time() - T0
        if score >= threshold and now - last_hit > 2.0:
            hits += 1; last_hit = now; note(event="detect", n=hits, score=round(score, 3))
        if time.time() - window >= 5:
            note(event="level", rms_peak=round(peak, 1), top_score=round(top, 3)); peak = 0.0; top = 0.0; window = time.time()
ru = resource.getrusage(resource.RUSAGE_SELF)
cpu = ru.ru_utime + ru.ru_stime - cpu0  # detection loop only, model loading excluded
note(event="end", detections=hits, infer_ms_median=round(float(np.median(infer_ms)), 2), infer_ms_p99=round(float(np.percentile(infer_ms, 99)), 2),
     cpu_seconds=round(cpu, 1), cpu_pct_of_one_core=round(100 * cpu / (time.time() - T0), 1))
