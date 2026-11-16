"""P1: Parakeet and Kokoro alternating 20x each on one worker thread of an asyncio process, mic callback running."""
import asyncio, statistics as st
from concurrent.futures import ThreadPoolExecutor
import sounddevice as sd
import time, numpy as np
import _common as c

calls = 0


def cb(indata, frames, t, status):
    global calls
    calls += 1


def work():
    c.stt(); c.tts()
    clip = c.to16k(c.speak("Jarvis, set a timer for ten minutes."))
    c.transcribe(clip); c.speak("Warm.")
    s, k = [], []
    for _ in range(20):
        t = time.perf_counter(); c.speak("Good evening, Febriel."); k.append(time.perf_counter() - t)
        s.append(c.transcribe(clip)[1])
    return st.median(s), st.median(k), max(s), max(k)


async def main():
    with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=480, callback=cb):
        r = await asyncio.get_running_loop().run_in_executor(ThreadPoolExecutor(1), work)
    stt_m, tts_m, stt_x, tts_x = r
    ok = stt_m <= 0.17 * 1.5 and tts_m <= 0.19 * 1.5 and calls > 0
    print(f"P1 stt_median={stt_m:.3f}s (max {stt_x:.3f}) tts_median={tts_m:.3f}s (max {tts_x:.3f}) mic_callbacks={calls} "
          f"{'PASS' if ok else 'FAIL'} (bar: no crash, medians <= 0.255 / 0.285)")

asyncio.run(main())
