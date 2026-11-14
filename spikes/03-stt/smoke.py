"""Spike 3 smoke test: synthetic sentence (macOS say) through both engines; audio deleted at once."""
import os, subprocess, sys, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engines import transcribe
here = os.path.dirname(os.path.abspath(__file__)); wav = os.path.join(here, "tmp", "smoke.wav")
subprocess.run(["say", "-v", "Daniel", "-o", wav, "--data-format=LEI16@16000", "Jarvis, open the captions repo and run the tests."], check=True)
pcm = np.frombuffer(wave.open(wav).readframes(10**7), dtype=np.int16); os.remove(wav)
silence = np.zeros(16000 * 2, np.int16)
for engine in ("parakeet", "whisper"):
    transcribe(engine, pcm)  # warm up / download
    for name, x in (("speech", pcm), ("silence", silence)):
        text, secs = transcribe(engine, x)
        print(f"{engine:8s} {name:7s} {secs:.2f}s {text!r}")
