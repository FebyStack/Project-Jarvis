import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FACE = ROOT / "jarvis" / "face"


def test_the_faces_logic_loads_neither_appkit_nor_the_speech_stack():
    code = ("import sys, jarvis.face.controller, jarvis.face.model, jarvis.face.tether, jarvis.face.mark, jarvis.face.place; "
            "print([m for m in ('AppKit', 'WebKit', 'Quartz', 'mlx', 'sounddevice') if m in sys.modules])")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


def native() -> str:
    return (FACE / "beads.py").read_text() + (FACE / "threads.py").read_text()


def test_a_bead_never_builds_text_from_markup():
    src = native()
    for banned in ("initWithHTML", "NSAttributedString", "setAttributedStringValue", "setAttributedTitle",
                   "WKWebView", "evaluateJavaScript", "setAllowsEditingTextAttributes_(True)"):
        assert banned not in src, banned


def test_a_bead_uses_the_systems_colours():
    src = (FACE / "beads.py").read_text()
    assert not re.search(r"#[0-9A-Fa-f]{6}\b", src) and "colorWithRed" not in src and "colorWithSRGB" not in src and "RED" not in src
    assert all(c in src for c in ("systemRedColor", "labelColor", "secondaryLabelColor"))
