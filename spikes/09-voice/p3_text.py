"""P3: what Parakeet returns for synthesized speech (digits, capitals, punctuation) and time for ~15 s and ~60 s."""
import numpy as np
import _common as c

S = ["Jervis, set a timer for 10 minutes.", "Hey Jarvis, what's the capital of Australia?",
     "Jarvis, remind me at 3:30 PM to call Dr. Smith about the 2 invoices.",
     "Jarvis, open Safari and search for flights to Cebu on December 5th."]
for v in ("bm_daniel", "bf_emma", "am_adam", "af_heart"):
    for s in S:
        t, sec = c.transcribe(c.to16k(c.speak(s, v)))
        print(f"{v:10} {sec:.2f}s | {s!r} -> {t!r}")
base = c.to16k(c.speak(" ".join(S[:3]) + " Please also tell me what the weather will be like tomorrow morning in Manila."))
for target in (15, 60):
    clip = np.tile(base, int(np.ceil(target * 16000 / len(base))))[: target * 16000]
    t, sec = c.transcribe(clip)
    print(f"P3 {target}s utterance: {sec:.2f}s ({len(t.split())} words) {'PASS' if target < 60 or sec < 2 else 'FAIL'}")
