"""Spike 3 Step 2: Febriel reads ten requests; VAD ends each at 0.8 s of silence; Parakeet transcribes live.
Each utterance is kept in tmp/ for the Whisper comparison and deleted when the spike ends."""
import json, os, subprocess, sys, time, wave
import numpy as np
import sounddevice as sd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engines import load, transcribe
from wake_stt import FRAME, Segmenter, is_wake

REQUESTS = ["Jarvis, what time is it?", "Jarvis, open the captions repo in VS Code.", "Jarvis, set a timer for twelve minutes.",
            "Jarvis, how much free space is on my disk?", "Jarvis, find the PDF about taxes I downloaded yesterday.",
            "Jarvis, turn the volume down to thirty percent.", "Jarvis, run the tests in Project Jarvis and tell me what fails.",
            "Jarvis, what's on my calendar tomorrow morning?", "Jarvis, remind me to call the clinic at four p.m.",
            "Jarvis, stop listening."]
here = os.path.dirname(os.path.abspath(__file__)); tmp = os.path.join(here, "tmp")
log = open(os.path.join(tmp, "requests.jsonl"), "w")
load("parakeet"); transcribe("parakeet", np.zeros(16000, np.int16))
seg = Segmenter(end_silence=0.8)
with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=FRAME) as stream:
    for i, expected in enumerate(REQUESTS, 1):
        subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"]); stream.read(stream.read_available)  # drop the chime
        t0 = time.time(); got = None
        while time.time() - t0 < 25 and got is None:
            got = seg.feed(stream.read(FRAME)[0][:, 0])
        if got is None:
            log.write(json.dumps({"n": i, "expected": expected, "heard": None}) + "\n"); log.flush(); continue
        ended = time.time()  # VAD has just seen 0.8 s of silence
        text, secs = transcribe("parakeet", got)
        wav = os.path.join(tmp, f"req{i:02d}.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(got.tobytes())
        wake, rest = is_wake(text)
        log.write(json.dumps({"n": i, "expected": expected, "heard": text, "wake": wake, "request": rest,
                              "utterance_s": round(len(got) / 16000, 2), "transcribe_s": round(secs, 3),
                              "end_of_speech_to_text_s": round(time.time() - ended + 0.8, 2)}) + "\n"); log.flush()
    subprocess.run(["say", "-v", "Daniel", "Done. Thank you."])
