"""Spike 4 Step 3: stream a paragraph sentence by sentence through one engine, bm_daniel.

Usage: python stream_race.py mlx|onnx [passes]
Sentences are synthesized back to back from t=0 (they arrive faster than synthesis).
Playback is simulated from audio lengths: each sentence starts when it is ready and the
previous one has finished; a gap is how long playback stalls waiting for the next one.
"""
import json
import statistics as st
import sys
import time
from pathlib import Path

import numpy as np
from scipy.io import wavfile

HERE = Path(__file__).parent
SENTENCES = [
    "Good evening, Febriel.",
    "I've finished reading the three emails that came in this afternoon.",
    "The one from your accountant needs a reply by Friday, and the other two can wait.",
    "Your build on the Jarvis branch passed, but one test took longer than usual.",
    "I've put the details in a note on your desktop.",
    "Tomorrow you have a meeting at nine, so I'd suggest an early night.",
    "Shall I draft the reply to your accountant now?",
]
VOICE = "bm_daniel"


def load(engine):
    if engine == "mlx":
        from mlx_audio.tts.utils import load_model
        m = load_model("mlx-community/Kokoro-82M-bf16")
        synth = lambda s: np.concatenate([np.array(r.audio) for r in m.generate(s, voice=VOICE, lang_code="b")])
        return synth, m.sample_rate
    from kokoro_onnx import Kokoro
    k = Kokoro(str(HERE / "data/kokoro-v1.0.onnx"), str(HERE / "data/voices-v1.0.bin"))
    assert VOICE in k.get_voices()
    return (lambda s: k.create(s, voice=VOICE, speed=1.0, lang="en-gb")[0]), 24000


def run(synth, sr):
    t0 = time.perf_counter()
    ready, audio = [], []
    for s in SENTENCES:
        a = np.asarray(synth(s), dtype=np.float32).reshape(-1)
        ready.append(time.perf_counter() - t0)
        audio.append(a)
    gaps, end = [], ready[0]
    for i, a in enumerate(audio):
        start = max(ready[i], end)
        if i:
            gaps.append(start - end)
        end = start + len(a) / sr
    return ready, gaps, audio


engine = sys.argv[1]
passes = int(sys.argv[2]) if len(sys.argv) > 2 else 5
t = time.perf_counter()
synth, sr = load(engine)
load_s = time.perf_counter() - t
t = time.perf_counter()
synth("Warming up.")
warm_s = time.perf_counter() - t

firsts, maxgaps = [], []
for p in range(passes):
    ready, gaps, audio = run(synth, sr)
    firsts.append(ready[0])
    maxgaps.append(max(gaps))
    print(json.dumps({"pass": p + 1, "first_audio_s": round(ready[0], 3), "ready_s": [round(r, 3) for r in ready],
                      "gaps_s": [round(g, 3) for g in gaps]}))

# Last pass as heard: each sentence followed by its simulated stall.
out = []
for a, g in zip(audio, gaps + [0.0]):
    out += [a, np.zeros(int(g * sr), dtype=np.float32)]
(HERE / "tmp").mkdir(exist_ok=True)
wav = HERE / f"tmp/stream_{engine}.wav"
wavfile.write(wav, sr, np.concatenate(out))

speech_s = sum(len(a) for a in audio) / sr
print(json.dumps({
    "engine": engine, "load_s": round(load_s, 3), "first_synth_after_load_s": round(warm_s, 3),
    "first_audio_median_s": round(st.median(firsts), 3), "first_audio_range_s": [round(min(firsts), 3), round(max(firsts), 3)],
    "max_gap_median_s": round(st.median(maxgaps), 3), "max_gap_range_s": [round(min(maxgaps), 3), round(max(maxgaps), 3)],
    "total_synth_s_last": round(ready[-1], 3), "speech_s": round(speech_s, 2), "wav": str(wav),
}))
