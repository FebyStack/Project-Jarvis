import asyncio
import threading

import numpy as np

from jarvis import config
from jarvis.voice.engines import Engines, ModelsMissing


class Fakes:
    """Fake loaders: each returns an engine that records the thread it ran on."""
    def __init__(self, fail=None):
        self.threads, self.calls, self.fail = [], [], fail

    def _here(self, what):
        self.threads.append(threading.get_ident())
        self.calls.append(what)

    def load_stt(self):
        self._here("load_stt")
        if self.fail:
            raise self.fail

        def transcribe(pcm):
            self._here("transcribe")
            return "hello" if pcm.any() else ""
        return transcribe

    def load_tts(self):
        self._here("load_tts")

        def synth(text):
            self._here("synth")
            return np.zeros(len(text), dtype=np.float32)
        return synth


def engines(f: Fakes) -> Engines:
    return Engines(load_stt=f.load_stt, load_tts=f.load_tts)


async def test_every_engine_call_runs_on_the_one_worker_thread():
    f = Fakes()
    e = engines(f)
    assert await e.load() is None
    for _ in range(3):
        assert await e.transcribe(np.ones(480, dtype=np.int16)) == "hello"
        assert len(await e.synth("Hi.")) == 3
    e.close()
    assert len(set(f.threads)) == 1 and f.threads[0] != threading.get_ident()


async def test_load_warms_both_engines():
    f = Fakes()
    await engines(f).load()
    assert f.calls.count("transcribe") == 1 and f.calls.count("synth") == 1


async def test_missing_models_are_named_not_raised():
    assert await engines(Fakes(fail=ModelsMissing("parakeet"))).load() == "no models"


async def test_a_failed_load_names_the_error():
    assert await engines(Fakes(fail=RuntimeError("boom"))).load() == "RuntimeError"


def test_importing_the_voice_modules_loads_no_audio_or_model_package():
    import subprocess
    import sys
    code = ("import sys, jarvis.voice.engines, jarvis.voice.audio, jarvis.voice.speaker; "
            "print([m for m in ('mlx', 'mlx_audio', 'parakeet_mlx', 'sounddevice', 'openwakeword') if m in sys.modules])")
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip() == "[]"


def test_the_voice_detector_can_forget_what_it_heard(monkeypatch):
    import sys
    from types import SimpleNamespace
    from jarvis.voice.engines import vad

    class FakeVAD:
        resets = 0
        def predict(self, frame, frame_size): return 0.9
        def reset_states(self): FakeVAD.resets += 1
    monkeypatch.setitem(sys.modules, "openwakeword", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "openwakeword.vad", SimpleNamespace(VAD=FakeVAD))
    predict = vad()
    assert predict(np.zeros(480, dtype=np.int16)) == 0.9
    predict.reset(); assert FakeVAD.resets == 1


async def test_an_unused_voice_is_kept_warm(monkeypatch):
    monkeypatch.setattr(config, "WARM_SECONDS", 0.05)  # macOS swaps an idle voice out; its first reply then waits 3-11 s
    f = Fakes()
    e = engines(f)
    await e.load()
    await asyncio.sleep(0.18)
    e.close()
    assert f.calls.count("synth") >= 3 and f.calls.count("transcribe") == 1  # load's warm-up, then the keeper's


async def test_a_voice_in_use_gets_no_warm_up(monkeypatch):
    monkeypatch.setattr(config, "WARM_SECONDS", 0.05)
    f = Fakes()
    e = engines(f)
    await e.load()
    for _ in range(6):
        await e.synth("Hi.")
        await asyncio.sleep(0.03)
    e.close()
    assert f.calls.count("synth") == 7  # load's one and the six replies
