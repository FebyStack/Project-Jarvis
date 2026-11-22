"""Bisaya plan Task 4: the dry-run judge, then the measurements. For each recording, and for each case (Parakeet
alone, then Parakeet plus each other listener), one `claude -p` run with Jarvis's own prompt and model, no tools, asked to
say in one line what it would do. Replies go to data/judged-MODEL.json (re-runs skip what is there) and .md,
next to what Febriel meant; the scoring is by hand. Subscription login only (clean_env), one call at a time.
usage: uv run python spikes/10-bisaya/judge.py [--measure] [--listeners a,b]"""
import argparse, json, re, subprocess
from pathlib import Path

import numpy as np

from jarvis import config
from jarvis.brain.env import clean_env
from jarvis.voice import wake

DATA = Path(__file__).parent / "data"
VENDORED_MARK = "<!-- vendored skills -->"
HINT_END = "Reply in English even when he speaks Bisaya."
PART3 = ("When a line `(Bisaya ear: …)` follows, it is the same speech heard by a Cebuano transcriber; "
         "use whichever makes sense, or both.")
ASK = "Dry run: do nothing. In one line, say what you would do."


def _plain(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.lower()).split())


def with_alt(text: str, alt: str | None) -> str:
    """As Task 6 builds it in jarvisd."""
    return text if not alt or _plain(alt) == _plain(text) else f'{text}\n(Bisaya ear: "{alt}")'


def system_prompt() -> str:
    own = (config.PROJECT / ".claude" / "agents" / "jarvis.md").read_text().split("---", 2)[2].split(VENDORED_MARK)[0]
    assert HINT_END in own
    return own.replace(HINT_END, f"{HINT_END} {PART3}", 1)


def results(only: list[str] | None = None) -> dict[str, dict]:
    res = {p.stem.removeprefix("results-"): json.loads(p.read_text()) for p in sorted(DATA.glob("results-*.json"))}
    return {n: r for n, r in res.items() if not only or n in only or n == "parakeet"}


def request(file: str, kind: str, heard: str) -> str:
    """What jarvisd sends: for a one-breath wake, the words after the name."""
    return (wake.split(heard) or heard) if kind == "wake" else heard


def ask(prompt: str, message: str) -> str:
    argv = ["claude", "-p", "--model", config.FRONT_MODEL, "--effort", config.FRONT_EFFORT, "--tools", "",
            "--strict-mcp-config", "--setting-sources", "project",
            "--system-prompt", prompt, f"{message}\n\n{ASK}"]
    r = subprocess.run(argv, env=clean_env(), cwd=config.PROJECT, capture_output=True, text=True, timeout=180)
    return (r.stdout.strip() or f"(exit {r.returncode}: {r.stderr.strip()[:200]})").replace("\n", " ")


def judge(only: list[str] | None) -> None:
    meant, res = json.loads((DATA / "meant.json").read_text()), results(only)
    path = DATA / f"judged-{config.FRONT_MODEL}.json"
    done = json.loads(path.read_text()) if path.exists() else {}
    prompt = system_prompt()
    for file, m in meant.items():
        base = request(file, m["kind"], res["parakeet"]["files"][file]["text"])
        cases = {"parakeet": base} | {f"parakeet+{n}": with_alt(base, r["files"][file]["text"])
                                      for n, r in res.items() if n != "parakeet"}
        for case, message in cases.items():
            row = done.setdefault(file, {})
            if case in row:
                continue
            same = next((c for c, msg in cases.items() if msg == message and c in row), None)
            row[case] = {"sent": message, "reply": row[same]["reply"] if same else ask(prompt, message)}
            path.write_text(json.dumps(done, ensure_ascii=False, indent=1))
            print(f"{file} {case}: {row[case]['reply'][:120]}", flush=True)
    lines = []
    for file, row in done.items():
        lines += [f"## {file} ({meant[file]['kind']})", f"meant: {meant[file]['meant']}", ""]
        lines += [f"- **{case}** sent `{c['sent']!r}`\n  → {c['reply']}" for case, c in row.items()] + [""]
    (DATA / f"judged-{config.FRONT_MODEL}.md").write_text("\n".join(lines))


def measure(only: list[str] | None) -> None:
    """One-breath wakes on Parakeet; extra seconds at 5 s of audio (least-squares line); memory."""
    meant, res = json.loads((DATA / "meant.json").read_text()), results(only)
    woke = [f for f, m in meant.items() if m["kind"] == "wake" and wake.split(res["parakeet"]["files"][f]["text"])]
    print(f"one-breath wakes: {len(woke)}/{sum(m['kind'] == 'wake' for m in meant.values())}")
    for name, r in res.items():
        s, a = (np.array([f[k] for f in r["files"].values()]) for k in ("seconds", "audio_s"))
        slope, icept = np.polyfit(a, s, 1)
        print(f"{name:9s} s@5s {slope * 5 + icept:5.2f}  max {s.max():5.2f}  rss {r['rss_mb']} MB  "
              f"footprint {r['footprint_mb']} MB  model {r.get('model_mb', '?')} MB  load {r['load_s']} s")


ap = argparse.ArgumentParser()
ap.add_argument("--measure", action="store_true")
ap.add_argument("--listeners", type=lambda v: v.split(","), help="only these, beside parakeet")
a = ap.parse_args()
measure(a.listeners) if a.measure else judge(a.listeners)
