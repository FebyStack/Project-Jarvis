"""Does an utterance start with the name? Pure text; Parakeet's spelling of "Jarvis" varies."""
import difflib
import re

from jarvis import config

_WORD = re.compile(r"[A-Za-z']+")


def sounds_like_name(word: str) -> bool:
    w = re.sub(r"'s$", "", "".join(re.findall(r"[a-z']", word.lower())))
    if w in config.WAKE_ALSO:
        return True
    ratio = difflib.SequenceMatcher(None, w, "jarvis").ratio()
    return (ratio >= config.WAKE_SIMILARITY and w.startswith("j") and len(w) >= 5) or (
        ratio >= config.WAKE_STRICT and len(w) >= 6)


def split(text: str) -> str | None:
    """None: no name in the first WAKE_WORDS words. "": the name alone. Else the request after the name,
    exactly as transcribed (capitals, digits, punctuation), minus leading separators."""
    for m in list(_WORD.finditer(text))[:config.WAKE_WORDS]:
        if sounds_like_name(m.group()):
            return text[m.end():].lstrip(" \t\n,.:;!?-—")
    return None
