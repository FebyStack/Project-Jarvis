"""P4: sounddevice output latency, abort() to silence, InputStream stop()/start() time."""
import time, statistics as st
import numpy as np
import sounddevice as sd

SR = 24000
t440 = (0.3 * np.sin(2 * np.pi * 440 * np.arange(SR * 5) / SR)).astype(np.float32)
plays, aborts = [], []
for _ in range(5):
    first = {}
    def cb(out, frames, t, status):
        n = len(out) if "pos" not in first else 0
        pos = first.setdefault("pos", 0)
        out[:, 0] = t440[pos:pos + frames] if pos + frames <= len(t440) else 0
        first.setdefault("t", time.perf_counter()); first["pos"] = pos + frames
    s = sd.OutputStream(samplerate=SR, channels=1, dtype="float32", callback=cb)
    t0 = time.perf_counter(); s.start()
    while "t" not in first: time.sleep(0.001)
    plays.append(first["t"] - t0)
    time.sleep(0.3)
    t0 = time.perf_counter(); s.abort(); aborts.append(time.perf_counter() - t0); s.close()
ins = sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=480, callback=lambda *a: None)
ins.start(); time.sleep(0.5)
stops, starts = [], []
for _ in range(10):
    t = time.perf_counter(); ins.stop(); stops.append(time.perf_counter() - t)
    t = time.perf_counter(); ins.start(); starts.append(time.perf_counter() - t)
    time.sleep(0.1)
ins.close()
m = st.median
print(f"P4 play->first_callback={m(plays):.3f}s abort()={m(aborts):.3f}s (max {max(aborts):.3f}) "
      f"in.stop={m(stops):.3f}s (max {max(stops):.3f}) in.start={m(starts):.3f}s (max {max(starts):.3f}) "
      f"{'PASS' if max(aborts) < 0.1 and max(stops) < 0.1 and max(starts) < 0.15 else 'FAIL'} (bar: stop < 0.1, restart < 0.15)")
print("note: abort() returning is the API-level silence; the hardware buffer adds <= output latency:", sd.query_devices(kind='output')['default_low_output_latency'])
