from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VENDORED_MARK = "<!-- vendored skills -->"


def frontmatter(path):
    """Top-level `key: value` and `key:` + `  - item` lists; folded/nested values are skipped."""
    _, head, body = path.read_text().split("---\n", 2)
    fm, key = {}, None
    for line in head.splitlines():
        if line.startswith("  - ") and key:
            fm[key].append(line[4:].strip())
        elif line and not line[0].isspace() and ":" in line:
            key, value = (s.strip() for s in line.split(":", 1))
            fm[key] = value or []
    return fm, body


def split(tools):
    return [t.strip() for t in tools.split(",")]


# Plan 2 Task 1 probe Step 6 (docs/spikes/findings.md, "Plan 2 probes"): `skills:` does not load on the
# `--agent` main thread, so jarvis has no skills key; humanizer and grill-me are pasted below VENDORED_MARK.
EXPECT = {"jarvis": ("sonnet", None, []), "triage": ("sonnet", ["Read", "Glob", "Grep"], []),
          "coder": ("sonnet", None, ["ponytail"]), "researcher": ("haiku", ["Read", "Glob", "Grep", "WebSearch", "WebFetch"], []),
          "scribe": ("haiku", ["Read", "Glob", "Grep", "Write", "Edit"], ["vault"])}


@pytest.mark.parametrize("name", EXPECT)
def test_agent_frontmatter(name):
    fm, body = frontmatter(ROOT / ".claude" / "agents" / f"{name}.md")
    model, tools, skills = EXPECT[name]
    assert fm["name"] == name and fm["model"] == model and fm.get("skills", []) == skills
    assert (split(fm["tools"]) if "tools" in fm else None) == tools
    assert len(body.split(VENDORED_MARK)[0].splitlines()) <= 60


def test_triage_thinks_at_medium_effort():
    fm, _ = frontmatter(ROOT / ".claude" / "agents" / "triage.md")
    assert fm["effort"] == "medium"


def test_jarvis_carries_its_skills_inline():
    _, body = frontmatter(ROOT / ".claude" / "agents" / "jarvis.md")
    own, vendored = body.split(VENDORED_MARK)
    assert "# Humanizer" in vendored and "design tree" in vendored  # humanizer, and grill-me's grilling body


def test_jarvis_knows_febriel_speaks_bisaya():
    _, body = frontmatter(ROOT / ".claude" / "agents" / "jarvis.md")
    own = body.split(VENDORED_MARK)[0]
    assert "Bisaya (Cebuano) accent" in own and "Reply in English even when he speaks Bisaya" in own


def test_making_files_is_never_small():
    _, body = frontmatter(ROOT / ".claude" / "agents" / "jarvis.md")
    small = body.split("## Small things")[1].split("##")[0]
    assert "Making or changing a file is never small" in small    # Task 15 row 3: a poem went to a file without triage


def test_every_named_skill_exists():
    for name in ("vault", "system", "humanizer", "grill-me", "grilling", "ponytail"):
        assert frontmatter(ROOT / ".claude" / "skills" / name / "SKILL.md")[0]["name"] == name


def test_vendored_skills_keep_their_licence():
    for name in ("humanizer", "grill-me", "grilling", "ponytail"):
        assert "MIT License" in (ROOT / ".claude" / "skills" / name / "LICENSE").read_text()
        assert name in (ROOT / ".claude" / "skills" / "VENDORED.md").read_text()


def test_no_agent_for_later_plans():
    assert sorted(p.stem for p in (ROOT / ".claude" / "agents").glob("*.md")) == sorted(EXPECT)
