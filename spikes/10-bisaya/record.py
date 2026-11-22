"""Bisaya plan Task 2: record Febriel's requests for the listener test. Same 16 kHz mono path as jarvisd (Mic,
Segmenter with the Silero VAD). Each utterance goes to data/<kind>-<NN>.wav (git-ignored) and what he says he
said to data/meant.json, written after every item. Re-running skips the items already in meant.json.
Mute Jarvis first (ctrl+l in the HUD), or the "Jarvis, ..." items will wake it.
usage: uv run python spikes/10-bisaya/record.py"""
import json, queue
from pathlib import Path

import soundfile as sf

from jarvis import config
from jarvis.voice import engines
from jarvis.voice.audio import Mic
from jarvis.voice.segment import Segmenter

DATA = Path(__file__).parent / "data"
MEANT = DATA / "meant.json"
ITEMS = [("bisaya", n) for n in range(1, 13)] + [("english", n) for n in range(1, 9)] + [("wake", n) for n in range(1, 4)]
SAY = {"bisaya": "a request in Bisaya, or a Bisaya-English mix, the way you'd really ask Jarvis",
       "english": "a request in English, the way you'd really ask Jarvis",
       "wake": 'say "Jarvis, ..." then a Bisaya request, in one breath'}


def listen(mic: Mic, seg: Segmenter, frames: queue.Queue):
    seg.reset()
    mic.start()
    try:
        while (u := seg.feed(frames.get())) is None:
            pass
    finally:
        mic.stop()
        while not frames.empty():
            frames.get_nowait()
    return u


def main() -> None:
    DATA.mkdir(exist_ok=True)
    meant = json.loads(MEANT.read_text()) if MEANT.exists() else {}
    frames: queue.Queue = queue.Queue()
    mic, seg = Mic(), Segmenter(engines.vad())
    mic.on_frame = frames.put
    mic.on_word = lambda word: word != "on" and print(f"  (mic {word})", flush=True)
    for kind, n in ITEMS:
        name = f"{kind}-{n:02d}.wav"
        if name in meant:
            continue
        while True:
            print(f"\n[{kind} {n}] {SAY[kind]}. Speak now.", flush=True)
            u = listen(mic, seg, frames)
            print(f"  got {len(u.pcm) / config.SAMPLE_RATE:.1f} s{' (cut at the length limit)' if u.cut else ''}")
            said = input("  Type what you said (r = record again): ").strip()
            if said and said.lower() != "r":
                break
        sf.write(DATA / name, u.pcm, config.SAMPLE_RATE, subtype="PCM_16")
        meant[name] = {"kind": kind, "meant": said}
        MEANT.write_text(json.dumps(meant, ensure_ascii=False, indent=1))
    print(f"\ndone: {len(meant)} of {len(ITEMS)} in {DATA}")


try:
    main()
except KeyboardInterrupt:
    print("\nstopped; what was kept is in meant.json, run again to go on")
