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
