"""Parses triage's verdict block. Pure; model output in, `Verdict` or `None` out, never an exception."""
import re
from dataclasses import dataclass

WORKERS = {"coder", "researcher", "none"}
TIERS = {"haiku", "sonnet", "opus", "fable"}
_LINE = re.compile(r"^[ \t]*(worker|tier|why|risks|ask|title)[ \t]*:[ \t]*(.*?)[ \t]*$", re.I | re.M)


@dataclass(frozen=True)
class Verdict:
    worker: str
    tier: str
    why: str
    risks: str
    ask: list[str]
    title: str


def parse_verdict(text) -> Verdict | None:
    if not isinstance(text, str):
        return None
    found = {}
    for key, value in _LINE.findall(text):
        found.setdefault(key.lower(), value)  # first block wins over any later echo
    worker, tier, title = found.get("worker"), found.get("tier"), found.get("title")
    if worker not in WORKERS or tier not in TIERS or not title:
        return None
    ask = found.get("ask", "")
    questions = [] if ask.lower() == "none" else [q.strip() for q in ask.split("|") if q.strip()]
    return Verdict(worker, tier, found.get("why", ""), found.get("risks", ""), questions, title)
