"""Spike 2: feed synthetic "Hey Jarvis" (macOS say) through the model to check the pipeline. Deletes the audio."""
import os, subprocess, sys, wave
import numpy as np
from openwakeword.model import Model
here = os.path.dirname(os.path.abspath(__file__))
for voice in sys.argv[1:]:
    wav = os.path.join(here, "tmp", "synthetic.wav")
    subprocess.run(["say", "-v", voice, "-o", wav, "--data-format=LEI16@16000", "Hey Jarvis"], check=True)
    pcm = np.frombuffer(wave.open(wav).readframes(10**7), dtype=np.int16)
    os.remove(wav)
    audio = np.concatenate([np.zeros(16000, np.int16), pcm, np.zeros(16000, np.int16)])
    m = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx"); key = next(iter(m.models))
    scores = [float(m.predict(audio[i:i + 1280])[key]) for i in range(0, len(audio) - 1279, 1280)]
    print(f"{voice:10s} max score {max(scores):.3f}")
