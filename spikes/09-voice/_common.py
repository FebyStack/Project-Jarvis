"""Shared by the Plan 3 probes: Parakeet and Kokoro, audio kept in memory only."""
import time
import numpy as np
from scipy.signal import resample_poly

VOICE, LANG = "bm_daniel", "b"
_stt = _tts = None


def stt():
    global _stt
    if _stt is None:
        from parakeet_mlx import from_pretrained
        _stt = from_pretrained("mlx-community/parakeet-tdt-0.6b-v2")
    return _stt


def tts():
    global _tts
    if _tts is None:
        from mlx_audio.tts.utils import load_model
        _tts = load_model("mlx-community/Kokoro-82M-bf16")
    return _tts


def speak(text, voice=VOICE):
    """Kokoro float32 at 24 kHz."""
    m = tts()
    return np.concatenate([np.array(r.audio, dtype=np.float32).reshape(-1)
                           for r in m.generate(text, voice=voice, lang_code=LANG)])


def to16k(a24):
    return resample_poly(a24, 2, 3).astype(np.float32)


def transcribe(a16):
    """float32 16 kHz -> (text, seconds)."""
    import mlx.core as mx
    from parakeet_mlx.audio import get_logmel
    m = stt()
    t = time.perf_counter()
    text = m.generate(get_logmel(mx.array(a16), m.preprocessor_config))[0].text
    return text.strip(), time.perf_counter() - t
