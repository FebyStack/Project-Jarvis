"""Task 14: live tuning of the name match. In memory only: per utterance, did the current rule wake, and which
words scored >= 0.6 against "jarvis" (with its position), plus numbers only: length, peak level, word count,
best score. No audio, no other words, nothing written.
usage: uv run python spikes/09-voice/wake_tune.py [--minutes N] [--label positives|negatives]"""
import argparse, asyncio, collections, difflib, re, time
import numpy as np
from jarvis import config
from jarvis.voice import engines, wake
from jarvis.voice.audio import Mic
from jarvis.voice.segment import Segmenter

ap = argparse.ArgumentParser()
ap.add_argument("--minutes", type=float)
ap.add_argument("--label", choices=["positives", "negatives"], default="positives")
args = ap.parse_args()
near: collections.Counter = collections.Counter()  # (word, score, woke) -> count
utts = wakes = 0


def scores(text: str) -> list[tuple[int, str, float]]:
    out = []
    for i, m in enumerate(wake._WORD.finditer(text), 1):
        w = re.sub(r"'s$", "", "".join(re.findall(r"[a-z']", m.group().lower())))
        out.append((i, w, round(difflib.SequenceMatcher(None, w, "jarvis").ratio(), 2)))
    return out


async def main() -> None:
    global utts, wakes
    eng = engines.Engines()
    if err := await eng.load():
        raise SystemExit(f"models: {err}")
    loop, frames = asyncio.get_running_loop(), asyncio.Queue()
    seg, mic = Segmenter(engines.vad()), Mic()
    mic.on_frame = lambda f: loop.call_soon_threadsafe(frames.put_nowait, f)
    mic.start()
    end = time.time() + args.minutes * 60 if args.minutes is not None else float("inf")
    print("listening, Ctrl-C to stop", flush=True)
    try:
        while time.time() < end:
            try:
                frame = await asyncio.wait_for(frames.get(), 0.5)
            except asyncio.TimeoutError:
                continue
            if (u := seg.feed(frame)) is None:
                continue
            text = await eng.transcribe(u.pcm)
            sc = scores(text)
            woke, nm = wake.split(text) is not None, [(i, w, s) for i, w, s in sc if s >= 0.6]
            utts += 1; wakes += woke
            near.update((w, s, woke) for i, w, s in nm if i <= config.WAKE_WORDS)
            best = max((s for _, _, s in sc), default=0.0)
            print(f"{utts:3d} woke={'yes' if woke else 'no '} {len(u.pcm) / config.SAMPLE_RATE:4.1f}s "
                  f"peak={int(np.abs(u.pcm).max()):5d} words={len(sc):2d} best={best:.2f} "
                  f"{' '.join(f'{w}@{i}:{s}' for i, w, s in nm)}", flush=True)
    finally:
        mic.stop(); eng.close()


try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
print(f"\n== {args.label}: {utts} utterances, {wakes} woke ==")
for (w, s, woke), n in sorted(near.items(), key=lambda kv: -kv[0][1]):
    print(f"{n:3d}x {w:12s} {s:.2f} {'woke' if woke else 'no wake'}")
