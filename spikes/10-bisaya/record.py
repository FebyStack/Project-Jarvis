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
LINES = {  # Febriel asked for lines to read (2026-11-22); saying them his own way is fine, he types what he said
    "bisaya": ["Ablihi ang Safari.", "Pagbutang ug timer sa napulo ka minuto.", "Pakusga gamay ang volume.",
               "Unsa na ang oras karon?", "Pangitaa ang file nga resume sa akong Downloads.",
               "Ablihi ang akong email ug basaha ang pinakabag-o.", "Hinayi ang volume, palihug.",
               "Unsa ang panahon sa Cebu karon?", "I-close ang tanan nga Chrome windows.",
               "Pahinumdumi ko ugma sa alas otso sa buntag nga naa koy meeting.",
               "Pila ang lima ka gatos ka dolyar sa peso?", "Ablihi ang Spotify ug i-play ang akong playlist."],
    "english": ["Open Notes.", "Set a timer for five minutes.", "What's on my calendar tomorrow?",
                "Turn the volume down to thirty percent.", "Find the PDF I downloaded yesterday.",
                "Open the Project Jarvis folder in Finder.", "How many days until Christmas?",
                "Read me the latest email in my inbox."],
    "wake": ["Jarvis, ablihi ang Calendar.", "Jarvis, pagbutang ug timer sa lima ka minuto.",
             "Jarvis, unsa akong schedule ugma?"],
    "mixed": ["I-open daw ang Chrome, then i-search ang weather sa Cebu.",  # Febriel: Bisaya-English too
              "Pwede nimo i-check akong calendar for tomorrow?", "Paki-set ug alarm at six thirty in the morning.",
              "Unsa man ang latest nga email sa akong inbox?", "I-mute sa ang volume kay naa koy call.",
              "I-show ang mga files nga akong gi-download today."]}
ITEMS = [(kind, n) for kind, lines in LINES.items() for n in range(1, len(lines) + 1)]
SAY = {"bisaya": "", "english": "", "wake": " (in one breath, no pause after Jarvis)", "mixed": ""}


def listen(mic: Mic, seg: Segmenter, frames: queue.Queue):
    seg.reset()
    mic.start()
    shown = False
    try:
        while (u := seg.feed(frames.get())) is None:
            if seg.speaking and not shown:
                print("  ● hearing you... (stops when you pause)", flush=True)
                shown = True
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
    input(f"{len(meant)} of {len(ITEMS)} done. Mute Jarvis first (ctrl+l in the HUD), then press Enter to start.")
    for kind, n in ITEMS:
        name = f"{kind}-{n:02d}.wav"
        if name in meant:
            continue
        while True:
            line = LINES[kind][n - 1]
            print(f"\n[{kind} {n} of {len(LINES[kind])}] Say{SAY[kind]}:\n    {line}", flush=True)
            u = listen(mic, seg, frames)
            print(f"  got {len(u.pcm) / config.SAMPLE_RATE:.1f} s{' (cut at the length limit)' if u.cut else ''}")
            said = input("  Enter = said it as written · or type what you said · r = record again: ").strip()
            if said.lower() != "r":
                said = said or line
                break
        sf.write(DATA / name, u.pcm, config.SAMPLE_RATE, subtype="PCM_16")
        meant[name] = {"kind": kind, "meant": said}
        MEANT.write_text(json.dumps(meant, ensure_ascii=False, indent=1))
    print(f"\ndone: {len(meant)} of {len(ITEMS)} in {DATA}")


try:
    main()
except KeyboardInterrupt:
    print("\nstopped; what was kept is in meant.json, run again to go on")
