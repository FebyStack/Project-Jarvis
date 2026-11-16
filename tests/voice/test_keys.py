import subprocess
import sys

from jarvis.voice import keys


def test_no_permission_means_no_listener(monkeypatch):
    monkeypatch.setattr(keys, "allowed", lambda: False)
    assert keys.listen(lambda kind: None) is None


def test_importing_the_key_listener_and_the_loop_loads_no_quartz():
    code = ("import sys, jarvis.voice.keys, jarvis.voice.loop; "
            "print([m for m in ('Quartz', 'mlx', 'sounddevice', 'openwakeword') if m in sys.modules])")
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip() == "[]"
