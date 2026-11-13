"""Spike 2: guided recording session for training a custom wake model.

The Mac speaks each instruction, then plays a chime before every take. The whole session is
recorded to spikes/02-wake/tmp/rec/ (git-ignored) with markers, and deleted when the spike ends.
usage: record_session.py [TAKES_PER_PHRASE]
"""
import json, os, subprocess, sys, time, wave
import numpy as np
import sounddevice as sd

SR, TAKE_S = 16000, 2.3
takes = int(sys.argv[1]) if len(sys.argv) > 1 else 30
here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, "tmp", "rec"); os.makedirs(out, exist_ok=True)
chunks, markers = [], []
def cb(indata, frames, t, status): chunks.append(indata[:, 0].copy())
def pos(): return sum(len(c) for c in chunks)
def say(text): subprocess.run(["say", "-v", "Daniel", text])
def chime(): subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"])
def status(msg): open(os.path.join(out, "status.txt"), "a").write(f"{time.strftime('%H:%M:%S')} {msg}\n")

with sd.InputStream(samplerate=SR, channels=1, dtype="int16", callback=cb):
    for phrase, spoken in (("hey_jarvis", "Hey Jarvis"), ("jarvis", "Jarvis")):
        say(f"Now say: {spoken}. Once after each chime. {takes} times. Move around between takes.")
        status(f"part {phrase} started")
        for i in range(takes):
            chime(); start = pos(); time.sleep(TAKE_S)
            markers.append({"part": phrase, "take": i, "start": start, "end": pos()})
        status(f"part {phrase} done")
    for part, spoken, secs in (("talk", "Now talk normally for two minutes. Say anything at all, but never say the wake word.", 120),
                               ("room", "Now stay quiet for one minute. Normal room sounds are fine.", 60)):
        secs = 3 if os.environ.get("SPIKE_SHORT") else secs
        say(spoken); chime(); start = pos(); status(f"part {part} started"); time.sleep(secs)
        markers.append({"part": part, "start": start, "end": pos()}); status(f"part {part} done")
    say("Done. Thank you.")
audio = np.concatenate(chunks)
with wave.open(os.path.join(out, "session.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(audio.tobytes())
json.dump(markers, open(os.path.join(out, "markers.json"), "w"))
status(f"saved {len(audio) / SR:.0f} s, {len(markers)} markers")
