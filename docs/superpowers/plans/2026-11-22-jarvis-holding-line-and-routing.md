# Holding Line and Model Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jarvis says a short holding line when a request is still working after 1.5 s, the front door runs on Haiku at low effort, and triage on Sonnet at medium effort.

**Architecture:** The core starts a timer when it sends a `mac` request. If the request is still `THINKING` with no reply token when the timer fires, it asks the speaker for a line worded by the last tool the hook saw. The speaker plays that line like the listening tone, so no state changes. Routing changes are argv and frontmatter.

**Tech Stack:** Python asyncio, pytest, Claude Code CLI 2.1.330 (`--effort`), agent frontmatter.

**Spec:** `docs/superpowers/specs/2026-11-22-jarvis-holding-line-and-routing-design.md`

## Global Constraints

- Subscription login only. No API key, no credit-based usage, no `--bare`, no fast mode.
- `config.HOLD_SECONDS = 1.5`; `config.FRONT_MODEL = "haiku"` (amended after Task 4: `"sonnet"`, see the ledger ruling); `config.FRONT_EFFORT = "low"`.
- Phrases, exactly: `"Looking that up."`, `"On it."`, `"One moment."`.
- Plan 4's interfaces stay. `Speaker` only gains `hint(text: str) -> None`.
- Unit tests never open a mic, speaker, key listener or model.
- Commits carry no Claude credit lines.

## Review Focus

1. A reply chunk queued behind a playing hint must still fire the speaker's `on_start` (SPEAKING closes the mic). Otherwise Jarvis talks with the mic open and hears itself. Test in Task 1.
2. Hint while the talk key is held (`hold(True)`): no sound. Test in Task 1.
3. A reply token, a spoken gate question, or a cancel before the timer means no hint. Test in Task 2.
4. A `phone` request never hints. Test in Task 2.
5. A request re-sent after a usage-limit pause hints at most once per send. Covered by the once-per-send timer; no extra test.

---

### Task 1: `VoiceSpeaker.hint`

**Files:**
- Modify: `jarvis/daemon/core.py` (the `Speaker` protocol), `jarvis/voice/speaker.py`, `tests/conftest.py` (`FakeSpeaker.hint` records `("hint", text)`)
- Test: `tests/voice/test_speaker.py`

**Interfaces:**
- Produces: `Speaker.hint(text: str) -> None`. It plays `text`, does not touch `on_start`/`on_done`, and does nothing while held or while reply speech is active.

- [ ] **Step 1: Write the failing tests** (use the file's `rig` and `idle`)
  - `test_a_hint_plays_without_starting_speech`: `rig.sp.hint("On it."); await idle(rig.sp)`, then `rig.synth.texts == ["On it."]`, `rig.player.played == [6]` and `rig.events == []`.
  - `test_a_hint_is_synthesized_once`: hint "On it." twice, with idle after each; `rig.synth.texts == ["On it."]` and `rig.player.played == [6, 6]`.
  - `test_a_hint_is_silent_while_held_or_speaking`:
    - `rig.sp.hold(True); rig.sp.hint("On it."); await idle(rig.sp)` gives `played == []`.
    - Then `hold(False)`, `rig.synth.block = {"One."}`, `rig.sp.feed("One. ")`, `rig.sp.hint("On it."); await idle(rig.sp)` gives `"On it." not in rig.synth.texts`.
  - First make `FakePlayer.play` fire `on_start` only when it was not already busy, as the real `Player` does (once per run). `_begin` is idempotent, so the existing tests are unaffected.
  - `test_a_reply_behind_a_hint_still_starts_speech`:
    - Make the `FakePlayer` stay busy after the hint by having `_done` not fire: set `rig.player._done = lambda: None` before the hint.
    - `rig.sp.hint("On it."); await idle(rig.sp); rig.sp.say("Lima."); await idle(rig.sp)`.
    - Expect `rig.events[:1] == ["start"]`.
- [ ] **Step 2: Run** `uv run pytest -q tests/voice/test_speaker.py -k hint` and expect FAIL (`AttributeError: hint`).
- [ ] **Step 3: Implement `hint(self, text: str) -> None` on `VoiceSpeaker`.**
  - Return at once if `not self._free.is_set()` or `self._active`.
  - Otherwise start a task that synthesizes `text` (cached in a dict) and calls `self.player.play(pcm)`, logging a warning if it fails (like `cue`).
  - Set `self._hinting = True` until the next `_player_done`.
  - In `_consume`, after `self.player.play(pcm)`, call `self._begin()` when `self._hinting`.
  - Add `hint` to the `Speaker` protocol with a one-line comment.
  - Add `hint` to `FakeSpeaker`.
- [ ] **Step 4: Run** `uv run pytest -q` and expect all pass.
- [ ] **Step 5: Commit** `feat: the speaker can play a holding line without starting speech`

### Task 2: The core says the holding line

**Files:**
- Modify: `jarvis/config.py` (`HOLD_SECONDS = 1.5`), `jarvis/daemon/core.py`
- Test: `tests/daemon/test_core_voice.py`

**Interfaces:**
- Consumes: `Speaker.hint` (Task 1).
- Produces: `core.hint_for(tool: str, sub: str) -> str`, which is pure:
  - `WebSearch`, `WebFetch`, or (`Agent`/`Task` with sub `researcher`) → `"Looking that up."`
  - any other `Agent`/`Task` → `"On it."`
  - else → `"One moment."`
  - `_Request` gains `tool: tuple[str, str] = ("", "")`, set in `hook()` for the owning request: `(tool, subagent_type or "")`.

- [ ] **Step 1: Write the failing tests** (monkeypatch `config.HOLD_SECONDS` to `0.01`, use the file's existing fixtures)
  - `test_hint_for_names_what_jarvis_is_doing`: the three mappings above, plus `("Bash", "")` → `"One moment."`.
  - `test_a_slow_request_gets_one_holding_line`:
    - Submit a `mac` request.
    - Feed a hook payload for `Agent` with `subagent_type: researcher` from the bridge's session.
    - `await asyncio.sleep(0.05)`; the speaker's calls then hold exactly one `("hint", "Looking that up.")`.
  - `test_no_holding_line_once_the_reply_has_started`: emit a reply delta before the sleep; no `"hint"` call.
  - `test_no_holding_line_for_the_phone`: a `phone` request; no `"hint"` call.
  - `test_no_holding_line_after_a_cancel`: "never mind" before the sleep; no `"hint"` call.
- [ ] **Step 2: Run** `uv run pytest -q tests/daemon/test_core_voice.py -k "hint or holding"` and expect FAIL.
- [ ] **Step 3: Implement.**
  - In `_serve_one`, after setting `_sent_at`: if `req.channel == "mac"` and `self.speaker`, then `asyncio.get_running_loop().call_later(config.HOLD_SECONDS, self._hold_line, req)`.
  - `_hold_line(req)` hints `hint_for(*req.tool)` only if `self._current is req`, `not self._first_token` and `self.sm.state is State.THINKING`.
- [ ] **Step 4: Run** `uv run pytest -q` and expect all pass.
- [ ] **Step 5: Commit** `feat: a slow request gets a short holding line`

### Task 3: Route the front door to Haiku and triage to Sonnet

**Files:**
- Modify:
  - `jarvis/config.py` (`FRONT_MODEL = "haiku"`, `FRONT_EFFORT = "low"`)
  - `jarvis/brain/env.py` (`claude_argv`)
  - `jarvis/daemon/core.py:670` and `jarvis/daemon/exchange.py:116` (`"sonnet"` → `config.FRONT_MODEL`)
  - `.claude/agents/jarvis.md`
  - `.claude/agents/triage.md`
- Test: `tests/brain/test_bridge.py:109-110`, `tests/daemon/test_exchange.py:60`

- [ ] **Step 1: Change the tests.**
  - `test_bridge.py`: `a[:6] == ["claude", "-p", "--agent", "jarvis", "--model", "haiku"]` and `a[a.index("--effort") + 1] == "low"`.
  - `test_exchange.py`: the needle `"jarvis (haiku)"`.
- [ ] **Step 2: Run** them and expect FAIL.
- [ ] **Step 3: Implement.**
  - `claude_argv` uses `config.FRONT_MODEL` and adds `"--effort", config.FRONT_EFFORT`.
  - The two HUD and task-note sites read `config.FRONT_MODEL`.
  - `jarvis.md` frontmatter gets `model: haiku`. Its line "If something will take more than about 5 seconds, say so in one short sentence first, then do it." becomes "jarvisd says a short holding line while you work, so do not open with one."
  - `triage.md` frontmatter gets `model: sonnet` and `effort: medium`.
- [ ] **Step 4: Run** `uv run pytest -q` and expect all pass.
- [ ] **Step 5: Commit** `feat: the front door runs on Haiku at low effort, triage on Sonnet at medium`

### Task 4: Live check

- [ ] Restart: `launchctl kickstart -k gui/$(id -u)/com.febriel.jarvisd`.
- [ ] Febriel asks "What's the capital of Peru". Expected: no holding line, and an answer. Note the `first token` time from `~/.jarvis/jarvisd.log`.
- [ ] Febriel asks "Look up this week's weather in Tokyo". Expected: "Looking that up." within about 2 s, then the result. Note the `first token` and `turn` times. The baseline is 17 s of silence on 2026-11-22 21:10.
- [ ] Check the task note's `## Agents` shows `jarvis (sonnet)` and `triage (sonnet)` (Sonnet after the Task 4 ruling).
- [ ] Record the results in `docs/spikes/findings.md` under "Holding line and routing (2026-11-22)", then update PROJECT.md.
