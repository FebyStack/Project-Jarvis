"""Spike 3: wake-by-transcription on Febriel's recorded Spike 2 session (positives = takes, negatives = talk + room)."""
import json, os, statistics, sys, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engines import transcribe
from wake_stt import FRAME, Segmenter, is_wake

rec = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "02-wake", "tmp", "rec")
audio = np.frombuffer(wave.open(os.path.join(rec, "session.wav")).readframes(10**9), dtype=np.int16)
markers = json.load(open(os.path.join(rec, "markers.json")))
def loudness(x):
    r = np.sqrt(np.mean(x[: len(x) // 320 * 320].astype(np.float64).reshape(-1, 320) ** 2, axis=1))
    return "clear" if r.max() >= 5 * np.percentile(r, 10) else "medium" if r.max() >= 2.5 * np.percentile(r, 10) else "faint"

report = {}
for engine in sys.argv[1:]:
    transcribe(engine, audio[:16000])
    hits, times, examples = {}, [], []
    for m in markers:
        if m["part"] not in ("hey_jarvis", "jarvis"):
            continue
        x = audio[m["start"]:m["end"]]; text, secs = transcribe(engine, x); times.append(secs)
        cls = loudness(x); ok = is_wake(text)[0]
        hits.setdefault(f'{m["part"]}/{cls}', []).append(ok)
        if not ok and cls == "clear": examples.append(text)
    false_wakes, seg_texts = [], 0
    for part in ("talk", "room"):
        seg = Segmenter()
        for m in (m for m in markers if m["part"] == part):
            x = audio[m["start"]:m["end"]]
            for i in range(0, len(x) - FRAME, FRAME):
                if (s := seg.feed(x[i:i + FRAME])) is not None:
                    text, secs = transcribe(engine, s); seg_texts += 1; times.append(secs)
                    if is_wake(text)[0]: false_wakes.append(text)
    report[engine] = {"wake_rate": {k: f"{sum(v)}/{len(v)}" for k, v in sorted(hits.items())},
                      "missed_clear_takes_heard_as": examples[:6],
                      "negative_utterances": seg_texts, "false_wakes": false_wakes,
                      "transcribe_s_median": round(statistics.median(times), 3), "transcribe_s_max": round(max(times), 3)}
print(json.dumps(report, indent=1))
