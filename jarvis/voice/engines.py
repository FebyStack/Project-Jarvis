"""The speech models on one MLX thread (load, warm, transcribe, synth), the voice detector, and `jarvis models`."""
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import numpy as np

from jarvis import config

log = logging.getLogger("jarvisd")
RATE_OUT = 24000


class ModelsMissing(Exception):
    """A model is not in the Hugging Face cache (jarvisd loads with HF_HUB_OFFLINE=1 and never downloads)."""


def _load_parakeet() -> Callable[[np.ndarray], str]:
    try:
        from parakeet_mlx import from_pretrained
        model = from_pretrained(config.STT_MODEL)
    except FileNotFoundError as e:  # what a repo missing from the cache gives offline
        raise ModelsMissing(config.STT_MODEL) from e

    def transcribe(pcm: np.ndarray) -> str:
        import mlx.core as mx
        from parakeet_mlx.audio import get_logmel
        audio = mx.array(pcm.astype(np.float32) / 32768.0)
        return model.generate(get_logmel(audio, model.preprocessor_config))[0].text.strip()
    return transcribe


def _load_kokoro() -> Callable[[str], np.ndarray]:
    try:
        from mlx_audio.tts.utils import load_model
        model = load_model(config.TTS_MODEL)
    except FileNotFoundError as e:  # huggingface_hub's LocalEntryNotFoundError is one
        raise ModelsMissing(config.TTS_MODEL) from e

    def synth(text: str) -> np.ndarray:
        parts = model.generate(text, voice=config.TTS_VOICE, lang_code=config.TTS_LANG)
        return np.concatenate([np.array(r.audio, dtype=np.float32).reshape(-1) for r in parts])
    return synth


class Engines:
    """MLX is not shared across threads, so every model call goes through one worker."""
    def __init__(self, load_stt=_load_parakeet, load_tts=_load_kokoro):
        self._loaders = (load_stt, load_tts)
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mlx")
        self._stt = self._tts = None
        self._spoke = 0.0  # when the voice last made speech
        self._keeper: asyncio.Task | None = None

    async def _run(self, fn, *args):
        return await asyncio.get_running_loop().run_in_executor(self._pool, fn, *args)

    def _load(self) -> None:
        self._stt, self._tts = self._loaders[0](), self._loaders[1]()
        self._stt(np.zeros(config.SAMPLE_RATE, dtype=np.int16))
        self._tts("Ready.")  # the first synthesis is ~5 s cold (pipeline, spaCy); pay it now

    async def load(self) -> str | None:
        try:
            await self._run(self._load)
        except ModelsMissing as e:
            log.error("voice models missing: %s (run `jarvis models`)", e)
            return "no models"
        except Exception as e:
            log.exception("voice models did not load")
            return type(e).__name__
        self._spoke = time.monotonic()
        self._keeper = asyncio.get_running_loop().create_task(self._keep_warm())
        return None

    async def transcribe(self, pcm: np.ndarray) -> str:
        return await self._run(self._stt, pcm)

    async def synth(self, text: str) -> np.ndarray:
        self._spoke = time.monotonic()
        return await self._run(self._tts, text)

    async def _keep_warm(self) -> None:
        """macOS swaps an unused voice out, and its next reply waits seconds for it: a line nobody hears keeps it in."""
        while True:
            await asyncio.sleep(self._spoke + config.WARM_SECONDS - time.monotonic())
            if time.monotonic() - self._spoke >= config.WARM_SECONDS:
                try:
                    await self.synth("Ready.")
                except Exception as e:  # replies fall back to `say` on their own; no warning every two minutes
                    log.warning("voice warm-up stopped: %s", type(e).__name__)
                    return

    def close(self) -> None:
        if self._keeper:
            self._keeper.cancel()
        self._pool.shutdown(wait=False, cancel_futures=True)


def vad() -> Callable[[np.ndarray], float]:
    """The voice detector; its `reset` forgets the speech it was in (the model keeps state across frames)."""
    from openwakeword.vad import VAD
    model = VAD()

    def predict(frame: np.ndarray) -> float:
        return float(model.predict(frame, frame_size=config.FRAME))
    predict.reset = model.reset_states
    return predict


def download() -> None:
    from huggingface_hub import snapshot_download
    for repo in (config.STT_MODEL, config.TTS_MODEL):
        snapshot_download(repo)
