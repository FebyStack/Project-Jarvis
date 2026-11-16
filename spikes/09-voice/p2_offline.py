"""P2: model load and first synthesis offline. Run via p2_run.sh (HF_HUB_OFFLINE + dead proxy)."""
import os, time
import _common as c

assert os.environ.get("HF_HUB_OFFLINE") == "1", "run p2_run.sh"
t = time.perf_counter(); c.stt(); a = time.perf_counter() - t
t = time.perf_counter(); c.tts(); b = time.perf_counter() - t
t = time.perf_counter(); n = len(c.speak("Good evening, Febriel.")); d = time.perf_counter() - t
import en_core_web_sm
print(f"P2 stt_load={a:.2f}s tts_load={b:.2f}s first_synth={d:.2f}s samples={n} en_core_web_sm={en_core_web_sm.__version__} PASS (nothing downloaded: offline + dead proxy)")
