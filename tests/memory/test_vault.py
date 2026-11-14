from datetime import datetime

from jarvis.memory.vault import Exchange, TaskRecord, Vault, slugify

AT = datetime(2026, 11, 10, 20, 14)


def record(**overrides):
    base = dict(at=AT, channel="mac", title="Fix export bug", asked="fix the export bug",
                done="patched exporter", agents=[], confirmations=[], files=[], notes_read=[])
    return TaskRecord(**{**base, **overrides})


def test_small_exchange_appends_one_line(tmp_path):
    p = Vault(tmp_path).log_exchange(Exchange(AT, "mac", "what time is it", "8:14 pm", []))
    assert p == tmp_path / "raw" / "2026-11-10.md"
    assert p.read_text().splitlines()[-1] == "- 20:14 · mac · what time is it → 8:14 pm"


def test_multiline_answer_stays_one_line(tmp_path):
    p = Vault(tmp_path).log_exchange(Exchange(AT, "phone", "list", "a\nb\nc", []))
    assert p.read_text().splitlines()[-1] == "- 20:14 · phone · list → a b c"


def test_day_log_uses_exchange_time(tmp_path):
    late = datetime(2026, 11, 10, 23, 59)
    assert Vault(tmp_path).log_exchange(Exchange(late, "mac", "q", "a", [])).name == "2026-11-10.md"


def test_task_note_named_and_linked(tmp_path):
    p = Vault(tmp_path).write_task_note(record(title="Fix export bug"))
    assert p.name == "2026-11-10-2014-fix-export-bug.md"
    assert "[[2026-11-10-2014-fix-export-bug]]" in (tmp_path / "raw" / "2026-11-10.md").read_text()


def test_same_minute_same_title_does_not_overwrite(tmp_path):
    v = Vault(tmp_path)
    a, b = v.write_task_note(record(title="Fix export bug")), v.write_task_note(record(title="Fix export bug"))
    assert b.name == "2026-11-10-2014-fix-export-bug-2.md" and a.exists()


def test_slugify_is_filename_safe():
    assert slugify("Fix a/b 🚀 bug!") == "fix-a-b-bug"
    assert slugify("///") == "task"


def test_task_note_sections(tmp_path):
    text = Vault(tmp_path).write_task_note(record(
        agents=[("coder", "opus")], confirmations=[("Delete 14 files?", False)],
        files=["/x/y.py"], notes_read=["wiki/preferences.md"])).read_text()
    for needle in ["# Fix export bug", "channel: mac", "## Asked", "## Done", "coder (opus)",
                   "Delete 14 files? — no", "/x/y.py", "[[preferences]]"]:
        assert needle in text


def test_read_index_missing_is_empty(tmp_path):
    assert Vault(tmp_path).read_index() == ""


def test_long_title_is_capped(tmp_path):
    p = Vault(tmp_path).write_task_note(record(title="word " * 80))
    assert p.exists() and len(p.name) <= 80


def test_exchange_logs_notes_read(tmp_path):
    p = Vault(tmp_path).log_exchange(Exchange(AT, "mac", "q", "a", ["wiki/preferences.md"]))
    assert p.read_text().splitlines()[-1] == "- 20:14 · mac · q → a · read [[preferences]]"


def test_status_and_map(tmp_path):
    assert Vault(tmp_path / "nope").status() == "missing"
    v = Vault(tmp_path); assert v.status() == "ok"
    v.ensure_map(); first = (tmp_path / "CLAUDE.md").read_text()
    assert first.startswith("# Jarvis vault map") and (tmp_path / "wiki" / "index.md").exists()
    (tmp_path / "CLAUDE.md").write_text("mine"); v.ensure_map(); assert (tmp_path / "CLAUDE.md").read_text() == "mine"
    (tmp_path / "raw").mkdir(exist_ok=True); (tmp_path / "raw").chmod(0o500)
    try: assert v.status() == "read-only"
    finally: (tmp_path / "raw").chmod(0o700)
    Vault(tmp_path / "nope").ensure_map(); assert not (tmp_path / "nope").exists()


def test_wiki_notes_and_memory_map(tmp_path):
    v = Vault(tmp_path); v.ensure_map(); assert v.wiki_notes() == []
    (tmp_path / "wiki" / "prefs.md").write_text("x"); (tmp_path / "wiki" / "index.md").write_text("- [[prefs]]")
    assert v.wiki_notes() == ["wiki/prefs.md"]
    assert v.memory_map() == (tmp_path / "CLAUDE.md").read_text() + "\n\n- [[prefs]]"


def test_ensure_map_leaves_an_existing_index_alone(tmp_path):
    import os
    v = Vault(tmp_path); v.ensure_map(); index = tmp_path / "wiki" / "index.md"
    os.utime(index, (1, 1)); v.ensure_map(); assert index.stat().st_mtime == 1


def test_a_write_never_recreates_a_missing_vault(tmp_path):
    """Review finding 11: a recreated vault would make Jarvis stop refusing."""
    import pytest
    v = Vault(tmp_path / "gone")
    with pytest.raises(OSError):
        v.log_exchange(Exchange(AT, "mac", "q", "a", []))
    with pytest.raises(OSError):
        v.write_task_note(record())
    assert not (tmp_path / "gone").exists()
