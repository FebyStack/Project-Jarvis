from jarvis.brain.verdict import Verdict, parse_verdict

GOOD = "worker: coder\ntier: opus\nwhy: touches the export pipeline\nrisks: none\nask: Which repo? | Overwrite the old file?\ntitle: Fix export bug"


def test_verdict_parses():
    assert parse_verdict(GOOD) == Verdict("coder", "opus", "touches the export pipeline", "none", ["Which repo?", "Overwrite the old file?"], "Fix export bug")
    assert parse_verdict(GOOD.replace("ask: Which repo? | Overwrite the old file?", "ask: none")).ask == []
    assert parse_verdict("Sure! Here is my verdict:\n" + GOOD.upper().replace("CODER", "coder").replace("OPUS", "opus")) is not None
    for bad in ("", "tier: opus", GOOD.replace("opus", "gpt"), GOOD.replace("coder", "operator")):
        assert parse_verdict(bad) is None


def test_verdict_tolerates_spacing_and_fences():
    text = "```\n  Worker :  none \nTIER:sonnet\nwhy:  just a question  \nrisks: none\nask: none\ntitle:   Explain the cache  \n```\nDone."
    assert parse_verdict(text) == Verdict("none", "sonnet", "just a question", "none", [], "Explain the cache")


def test_verdict_missing_optional_lines_default_empty():
    v = parse_verdict("worker: researcher\ntier: haiku\ntitle: Look up flight times")
    assert v == Verdict("researcher", "haiku", "", "", [], "Look up flight times")


def test_verdict_never_raises_on_odd_input():
    for odd in (None, 42, b"worker: coder", "worker: coder\ntier: opus\ntitle:   ", ":::\n\x00\n", "ask: | | \nworker: coder\ntier: fable\ntitle: x"):
        parse_verdict(odd)
    assert parse_verdict("worker: coder\ntier: fable\nask:  | a |  \ntitle: x").ask == ["a"]
