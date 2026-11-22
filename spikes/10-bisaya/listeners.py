"""Bisaya plan Task 3: the candidate listeners. Each loader returns a function: 16 kHz mono int16 PCM -> text.
Imports stay inside the loaders, so one process pays only for the listener it runs. The Cebuano models live on
Febriel's external SSD (his choice, 2026-11-22: the internal disk has 11 GiB free). Whisper turbo and
Omnilingual were not okayed for download, so they are not here."""
from typing import Callable

import numpy as np

BUZZ, MMS = "BuzzASR/cebuano", "facebook/mms-1b-all"
SSD = "/Volumes/PortableSSD/Jarvis/hf-cache"
MMS_FILES = ["model.safetensors", "adapter.ceb.safetensors", "config.json", "preprocessor_config.json",
             "tokenizer_config.json", "special_tokens_map.json", "vocab.json"]


def _f32(pcm: np.ndarray) -> np.ndarray:
    return pcm.astype(np.float32) / 32768.0


def parakeet() -> Callable[[np.ndarray], str]:
    from jarvis.voice.engines import _load_parakeet
    return _load_parakeet()


def buzz() -> Callable[[np.ndarray], str]:
    """The model card's own call: its generation config carries the Cebuano prompt."""
    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor
    model = WhisperForConditionalGeneration.from_pretrained(BUZZ, cache_dir=SSD, dtype=torch.float16).to("mps").eval()
    proc = WhisperProcessor.from_pretrained(BUZZ, cache_dir=SSD)

    def run(pcm):
        feats = proc(_f32(pcm), sampling_rate=16000, return_tensors="pt").input_features.to("mps", torch.float16)
        with torch.inference_mode():
            ids = model.generate(feats, num_beams=1, no_repeat_ngram_size=3, repetition_penalty=1.2)
        return proc.batch_decode(ids, skip_special_tokens=True)[0].strip()
    return run


def mms() -> Callable[[np.ndarray], str]:
    import torch
    from transformers import AutoProcessor, Wav2Vec2ForCTC
    proc = AutoProcessor.from_pretrained(MMS, cache_dir=SSD)
    proc.tokenizer.set_target_lang("ceb")
    model = Wav2Vec2ForCTC.from_pretrained(MMS, cache_dir=SSD)
    model.load_adapter("ceb", cache_dir=SSD)
    model = model.to("mps", torch.float16).eval()

    def run(pcm):
        x = proc(_f32(pcm), sampling_rate=16000, return_tensors="pt").input_values.to("mps", torch.float16)
        with torch.inference_mode():
            ids = model(x).logits[0].argmax(-1)
        return proc.decode(ids).strip()
    return run


def _buzz_mlx(bits: int) -> Callable[[], Callable[[np.ndarray], str]]:
    """BuzzASR converted with mlx-examples' whisper/convert.py and quantized (Febriel okayed, 2026-11-22; run with
    `uv run --with mlx-whisper==0.4.3`). Its generation config decodes with the Tagalog token, so that is given here;
    greedy, like the model card."""
    def load():
        import mlx_whisper
        opts = dict(path_or_hf_repo=MLX.format(bits), language="tl", task="transcribe", temperature=0.0,
                    condition_on_previous_text=False, without_timestamps=True)
        return lambda pcm: mlx_whisper.transcribe(_f32(pcm), **opts)["text"].strip()
    return load


def _buzz_short(bits: int, least_s: int = 0) -> Callable[[], Callable[[np.ndarray], str]]:
    """As _buzz_mlx, but the encoder sees the utterance plus about 1 s instead of Whisper's padded 30 s (whisper.cpp's
    audio_ctx idea): its time is what the 30 s window costs. least_s: the shortest window, in seconds."""
    def load():
        import mlx.core as mx
        from mlx_whisper.audio import log_mel_spectrogram, pad_or_trim
        from mlx_whisper.decoding import DecodingOptions, decode
        from mlx_whisper.load_models import load_model
        model = load_model(MLX.format(bits), dtype=mx.float16)
        full = model.encoder._positional_embedding
        opts = DecodingOptions(language="tl", task="transcribe", temperature=0.0, without_timestamps=True)

        def run(pcm):
            mel = log_mel_spectrogram(_f32(pcm), n_mels=model.dims.n_mels)
            frames = min(3000, max(least_s * 100, (mel.shape[0] // 100 + 2) * 100))  # whole s, >= 1 s past speech
            model.encoder._positional_embedding = full[: frames // 2]
            return decode(model, pad_or_trim(mel, frames, axis=-2), opts).text.strip()
        return run
    return load


MLX = "/Volumes/PortableSSD/Jarvis/mlx/buzzasr-cebuano-q{}"
LOADERS: dict[str, Callable[[], Callable[[np.ndarray], str]]] = {
    "parakeet": parakeet, "buzz": buzz, "mms": mms, "buzz8": _buzz_mlx(8), "buzz4": _buzz_mlx(4),
    "buzz8s": _buzz_short(8), "buzz4s": _buzz_short(4), "buzz8w10": _buzz_short(8, 10), "buzz4w10": _buzz_short(4, 10),
    "buzz8w15": _buzz_short(8, 15)}
