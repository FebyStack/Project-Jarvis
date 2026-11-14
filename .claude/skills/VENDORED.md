# Vendored skills

Copied on 2026-11-14 at the commits below (Plan 2 Task 8). Each folder keeps the source's `LICENSE`, as the MIT licence requires. Files are unchanged. To update, copy the folder again from a newer commit and change its row.

| Folder | Repository | Path in repository | Commit | Licence |
|---|---|---|---|---|
| `humanizer/` | https://github.com/blader/humanizer | `SKILL.md` | `b48c832f0f809c1b5658edbb838c2521b72f2413` | MIT, © 2025 Siqi Chen |
| `grill-me/` | https://github.com/mattpocock/skills | `skills/productivity/grill-me/SKILL.md` | `5863806dd4e15c63174bee4e7515a4256792ecfa` | MIT, © 2026 Matt Pocock |
| `grilling/` | https://github.com/mattpocock/skills | `skills/productivity/grilling/SKILL.md` | `5863806dd4e15c63174bee4e7515a4256792ecfa` | MIT, © 2026 Matt Pocock |
| `ponytail/` | https://github.com/DietrichGebert/ponytail | `skills/ponytail/SKILL.md` | `96608e078b2d5ea607c5c3b8b5a54d1c1fba6846` | MIT, © 2026 DietrichGebert |

Notes:

- `grill-me` only says to call the `grilling` skill, so `grilling` is copied with it.
- Left out: each source's `agents/openai.yaml` (Codex metadata) and ponytail's `/ponytail` commands and sibling skills (`ponytail-audit`, `-debt`, `-gain`, `-help`, `-review`). Ponytail's text mentions `/ponytail lite|full|ultra`; that command does not exist here, so it runs at its default level, `full`.
- `skills:` in frontmatter does not load on the `--agent` main thread (Plan 2 probe Step 6), so the `humanizer` and `grilling` bodies are also pasted into `.claude/agents/jarvis.md` below `<!-- vendored skills -->`. Update both places together.
