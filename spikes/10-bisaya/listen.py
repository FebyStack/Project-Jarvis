"""Bisaya plan Task 3: run one listener over every recording, one listener per process so memory stays clean.
Writes data/results-NAME.json. rss_mb is ru_maxrss; footprint_mb is the peak physical footprint (what Activity
Monitor shows), which also counts the GPU memory that MLX and MPS take on this unified-memory Mac; model_mb is the
footprint the loaded listener keeps after the run, less the footprint before loading it (Python and imports).
usage: uv run python spikes/10-bisaya/listen.py --listener NAME"""
import argparse, ctypes, gc, json, os, resource, sys, time
from pathlib import Path

import numpy as np
import soundfile as sf

import listeners

DATA = Path(__file__).parent / "data"


def footprint_mb(peak: bool = False) -> int:
    """proc_pid_rusage(RUSAGE_INFO_V4): a 16-byte uuid, then uint64 fields; 7 is ri_phys_footprint,
    28 ri_lifetime_max_phys_footprint."""
    buf = (ctypes.c_uint64 * 40)()
    if ctypes.CDLL("libproc.dylib").proc_pid_rusage(os.getpid(), 4, buf) != 0:
        return -1
    return round(buf[2 + (28 if peak else 7)] / 1e6)


def settled_mb() -> int:
    gc.collect()
    try:
        import torch
        torch.mps.empty_cache()
    except ImportError:
        pass
    if "mlx.core" in sys.modules:
        sys.modules["mlx.core"].clear_cache()
    return footprint_mb()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listener", required=True, choices=sorted(listeners.LOADERS))
    name = ap.parse_args().listener
    base = settled_mb()  # imports torch first: the listener's cost excludes Python, numpy and torch themselves
    t = time.perf_counter()
    run = listeners.LOADERS[name]()
    load_s = time.perf_counter() - t
    run(np.zeros(16000, dtype=np.int16))
    files = {}
    for wav in sorted(DATA.glob("*.wav")):
        pcm, rate = sf.read(wav, dtype="int16")
        assert rate == 16000 and pcm.ndim == 1, wav
        t = time.perf_counter()
        text = run(pcm)
        files[wav.name] = {"text": text, "seconds": round(time.perf_counter() - t, 3), "audio_s": round(len(pcm) / rate, 2)}
        print(f"{wav.name:16s} {files[wav.name]['seconds']:5.2f} s  {text}", flush=True)
    out = {"load_s": round(load_s, 2), "rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6),
           "footprint_mb": footprint_mb(peak=True), "model_mb": settled_mb() - base, "files": files}
    (DATA / f"results-{name}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{name}: load {out['load_s']} s, rss {out['rss_mb']} MB, footprint {out['footprint_mb']} MB, "
          f"model {out['model_mb']} MB, {len(files)} files")


main()
