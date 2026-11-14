"""Spike 3 Step 3: run faster-whisper (small.en, int8) on the same ten recordings; print both engines side by side."""
import json, os, statistics, sys, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engines import transcribe
from wake_stt import is_wake
tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
rows = [json.loads(l) for l in open(os.path.join(tmp, "requests.jsonl"))]
transcribe("whisper", np.zeros(16000, np.int16))
for r in rows:
    if r.get("heard") is None:
        continue
    pcm = np.frombuffer(wave.open(os.path.join(tmp, f"req{r['n']:02d}.wav")).readframes(10**7), dtype=np.int16)
    r["whisper"], r["whisper_s"] = transcribe("whisper", pcm)
    r["whisper_wake"] = is_wake(r["whisper"])[0]
    print(f"{r['n']:2d} {r['utterance_s']:4.1f}s | expected: {r['expected']}\n   parakeet {r['transcribe_s']:.2f}s wake={r['wake']}: {r['heard']}\n   whisper  {r['whisper_s']:.2f}s wake={r['whisper_wake']}: {r['whisper']}")
ok = [r for r in rows if r.get("heard") is not None]
print("median parakeet", round(statistics.median(r["transcribe_s"] for r in ok), 3), "| median whisper", round(statistics.median(r["whisper_s"] for r in ok), 3),
      "| end-of-speech→text (parakeet, incl. 0.8 s silence) median", round(statistics.median(r["end_of_speech_to_text_s"] for r in ok), 2))
json.dump(rows, open(os.path.join(tmp, "compare.json"), "w"), indent=1)
