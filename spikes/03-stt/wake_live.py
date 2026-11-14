"""Spike 3: live wake-by-transcription for N seconds; logs every utterance's text and each wake. No audio stored.
usage: wake_live.py SECONDS LABEL"""
import json, os, resource, sys, time
import numpy as np
import sounddevice as sd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engines import load, transcribe
from wake_stt import FRAME, Segmenter, is_wake
secs, label = float(sys.argv[1]), sys.argv[2]
log = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp", f"{label}.jsonl"), "w")
load("parakeet"); transcribe("parakeet", np.zeros(16000, np.int16))
seg = Segmenter(end_silence=0.8)
ru0 = resource.getrusage(resource.RUSAGE_SELF); cpu0 = ru0.ru_utime + ru0.ru_stime; T0 = time.time()
utts = wakes = 0; speech_s = 0.0
win_t, win_cpu, win_utts = T0, cpu0, 0
def cpu_now():
    r = resource.getrusage(resource.RUSAGE_SELF); return r.ru_utime + r.ru_stime
with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=FRAME) as stream:
    while time.time() - T0 < secs:
        if time.time() - win_t >= 60:  # per-minute cost, so quiet and noisy stretches can be told apart
            c = cpu_now(); log.write(json.dumps({"minute": round((time.time() - T0) / 60), "cpu_pct": round(100 * (c - win_cpu) / (time.time() - win_t), 1),
                                                 "utterances": win_utts}) + "\n"); log.flush()
            win_t, win_cpu, win_utts = time.time(), c, 0
        if (got := seg.feed(stream.read(FRAME)[0][:, 0])) is None:
            continue
        text, t = transcribe("parakeet", got); utts += 1; win_utts += 1; speech_s += len(got) / 16000
        wake, rest = is_wake(text); wakes += wake
        log.write(json.dumps({"t": round(time.time() - T0, 1), "len_s": round(len(got) / 16000, 1), "transcribe_s": round(t, 3),
                              "wake": wake, "text": text}) + "\n"); log.flush()
ru = resource.getrusage(resource.RUSAGE_SELF); cpu = ru.ru_utime + ru.ru_stime - cpu0
log.write(json.dumps({"end": True, "seconds": round(time.time() - T0), "utterances": utts, "wakes": wakes,
                      "speech_seconds": round(speech_s), "cpu_pct_of_one_core": round(100 * cpu / (time.time() - T0), 1)}) + "\n")
