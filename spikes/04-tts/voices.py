"""Spike 4 Step 2: the same three lines in each Kokoro British male voice, plus `say -v Daniel`."""
import subprocess
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from mlx_audio.tts.utils import load_model

TEXT = (
    "Good evening, Febriel. All systems are online. "
    "You have three unread emails and one meeting at nine tomorrow. "
    "Shall I open a new Claude Code session for the wake word work?"
)
VOICES = ["bm_george", "bm_lewis", "bm_daniel", "bm_fable"]
OUT = Path(__file__).parent / "tmp"
OUT.mkdir(exist_ok=True)

model = load_model("mlx-community/Kokoro-82M-bf16")
for v in VOICES:
    audio = np.concatenate([np.array(r.audio) for r in model.generate(TEXT, voice=v, lang_code="b")])
    wavfile.write(OUT / f"{v}.wav", model.sample_rate, audio.astype(np.float32))
    print(OUT / f"{v}.wav")

subprocess.run(["say", "-v", "Daniel", "-o", str(OUT / "say_daniel.aiff"), TEXT], check=True)
print(OUT / "say_daniel.aiff")
