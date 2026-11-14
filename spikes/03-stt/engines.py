"""Spike 3: the two speech-to-text engines behind one call: transcribe(engine, pcm_int16_16k) -> (text, seconds)."""
import time
import numpy as np

_models = {}


def load(engine):
    if engine not in _models:
        if engine == "parakeet":
            from parakeet_mlx import from_pretrained
            _models[engine] = from_pretrained("mlx-community/parakeet-tdt-0.6b-v2")
        else:
            from faster_whisper import WhisperModel
            _models[engine] = WhisperModel("small.en", device="cpu", compute_type="int8")
    return _models[engine]


def transcribe(engine, pcm):
    model, audio = load(engine), pcm.astype(np.float32) / 32768.0
    t = time.perf_counter()
    if engine == "parakeet":
        import mlx.core as mx
        from parakeet_mlx.audio import get_logmel
        text = model.generate(get_logmel(mx.array(audio), model.preprocessor_config))[0].text
    else:
        segments, _ = model.transcribe(audio, language="en", beam_size=1, vad_filter=False)
        text = " ".join(s.text for s in segments)
    return text.strip(), time.perf_counter() - t
