"""Spike 2: live detector for the custom-trained head (train_wake.py). No audio is stored.

usage: wake_custom.py PHRASE SECONDS LABEL [THRESHOLD]
"""
import json, os, resource, sys, time
import joblib
import numpy as np
import sounddevice as sd
from openwakeword.utils import AudioFeatures

phrase, secs, label = sys.argv[1], float(sys.argv[2]), sys.argv[3]
threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
here = os.path.dirname(os.path.abspath(__file__))
clf = joblib.load(os.path.join(here, "data", f"wake_{phrase}.joblib"))
feat = AudioFeatures()
log = open(os.path.join(here, "tmp", f"{label}.jsonl"), "w")
def note(**kw):
    kw["t"] = round(time.time() - T0, 2); log.write(json.dumps(kw) + "\n"); log.flush()

ru0 = resource.getrusage(resource.RUSAGE_SELF); cpu0 = ru0.ru_utime + ru0.ru_stime
T0 = time.time(); last_hit = -10.0; infer_ms = []; peak = top = 0.0; hits = 0; frames = 0
note(event="start", phrase=phrase, threshold=threshold)
with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=1280) as stream:
    window = time.time()
    while time.time() - T0 < secs:
        pcm = stream.read(1280)[0][:, 0]
        peak = max(peak, float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2))))
        t = time.perf_counter()
        feat(pcm); frames += 1
        score = float(clf.predict_proba(feat.get_features(16).reshape(1, -1))[0, 1]) if frames > 25 else 0.0
        infer_ms.append((time.perf_counter() - t) * 1000)
        top = max(top, score); now = time.time() - T0
        if score >= threshold and now - last_hit > 2.0:
            hits += 1; last_hit = now; note(event="detect", n=hits, score=round(score, 3))
        if time.time() - window >= 5:
            note(event="level", rms_peak=round(peak, 1), top_score=round(top, 3)); peak = top = 0.0; window = time.time()
ru = resource.getrusage(resource.RUSAGE_SELF)
cpu = ru.ru_utime + ru.ru_stime - cpu0
note(event="end", detections=hits, infer_ms_median=round(float(np.median(infer_ms)), 2),
     cpu_pct_of_one_core=round(100 * cpu / (time.time() - T0), 1))
