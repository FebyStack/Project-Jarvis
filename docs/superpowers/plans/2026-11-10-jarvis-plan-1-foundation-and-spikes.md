# Jarvis Plan 1 — Foundation and Spikes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Jarvis repository with the three pieces of logic that do not depend on any unknown (memory writer, ask-first gate, voice state machine), then run the seven spikes that settle every risk in the design before anything else is built.

**Architecture:** One Python package, `jarvis/`, laid out as the spec's §8. This plan builds only pure, unit-tested modules plus throwaway spike scripts under `spikes/`. Nothing here starts a daemon, opens the microphone permanently, or exposes a port beyond a spike's lifetime.

**Tech Stack:** Python 3.12, `uv` for environment and dependencies, `pytest`. Spikes additionally use `openwakeword`, `sounddevice`, `parakeet-mlx`, `mlx-audio`, `agent-desktop`, Tailscale.

**Spec:** `docs/superpowers/specs/2026-11-10-jarvis-design.md` — read it first; section numbers below refer to it.

## Where this plan sits

| Plan | Delivers | Written when |
|---|---|---|
| **1 (this)** | Repo, memory writer, gate rules, state machine, spike findings | now |
| 2 | Typed-request Jarvis: daemon, Claude Code bridge, gate wired to the permission hook, agents and skills, gold HUD | after Task 13, from spike 1's findings |
| 3 | Voice: wake word, speech-to-text, spoken replies | after plan 2 |
| 4 | Phone route and keep-awake | after plan 3 |
| 5 | On-screen control, reverse engineering, spawned sessions | after plan 4 |

Plans 2–5 are not written yet on purpose: each spike can change their interfaces.

### Carried into later plans (added 2026-11-13)

Spec amendments of 2026-11-13 that this plan does not build. Whoever writes the plan named must include them.

| Item (spec section) | Plan |
|---|---|
| Instant answers: the fixed phrase list answered by code, logged to the day's log (§6.2) | 2 |
| `CLAUDE.md` map file at the vault root (§6.3) | 2 |
| Skill shortlist from Febriel's last 30 days of sessions, for him to pick from (§6.2) | 2 |
| HUD: `LIMITS` usage share if Claude Code reports it, Enter opens a spawned session, `/` skill list, vault-missing state (§7) | 2 |
| `CANCEL` event in `jarvis/daemon/state.py`, Escape and "cancel" wired to it (§6.1) | 2 for the event and Escape, 3 for the spoken form |
| Tap-to-talk and hold-to-talk on one key, system-wide (§6.1) | 3 |
| Speech engines: use the winners recorded by Tasks 8 and 9 | 3 |

## Global Constraints

- Subscription login only. Never pass `--bare`. `ANTHROPIC_API_KEY` must be unset in every process this project starts; a spike that finds it set stops.
- Any server binds `127.0.0.1` only. Tailscale Funnel is never used.
- No audio is written to disk outside a spike's own temp folder, and spikes delete theirs.
- No `sudo`. No change to system security settings. Each install is named to Febriel before it runs.
- Vault root: `/Users/febrielotud/Obsidian/Jarvis` (`raw/`, `wiki/`, `outputs/`). Overridable with env `JARVIS_VAULT` for tests.
- Free-write areas: `~/Developer` and the vault. Protected even inside them: this project's `.claude/` and `~/.jarvis/`.
- Ask words (§6.5), exact: `send, submit, post, publish, pay, buy, delete, remove, confirm, sign`.
- Follow-up window: 6.0 s. End-of-speech silence: 0.8 s. Confirmation timeouts: 60 s Mac, 600 s phone.
- Wake word for v1: "Hey Jarvis". Triage model: `claude-opus-5-5`. Front door: `sonnet`.
- English only.
- Commits carry no Claude credit: no `Co-Authored-By: Claude` line, no "Generated with Claude Code" (Febriel, 2026-11-13; the earlier trailers were stripped from history the same day).

## Review Focus

1. **A risky command hidden inside a harmless one** (`ls && rm -rf ~/Documents`, `$(...)`, a `>` redirect): the strictest part decides. Pinned in Task 3.
2. **A path that escapes by trickery** (`..`, a symlink inside `~/Developer` pointing out, a quoted `~`): judged by its resolved real path. Pinned in Task 3.
3. **Two tasks with the same title in the same minute, or a title with `/` or emoji:** each gets its own safe filename; nothing is overwritten. Pinned in Task 2.
4. **An exchange at 23:59 written at 00:00, or multi-line answers:** the day's log is chosen by when the exchange happened, and each entry stays one line. Pinned in Task 2.
5. **Jarvis hearing itself or a late reply:** a wake word while speaking is ignored; speech after the 6 s window needs the wake word again. Pinned in Task 5.

---

## Part A — Foundation (no input from Febriel needed)

### Task 1: Repository and tooling

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `jarvis/__init__.py`, `jarvis/{daemon,voice,brain,memory,remote,tui}/__init__.py`, `tests/test_smoke.py`

**Interfaces:**
- Produces: importable package `jarvis`; `uv run pytest` as the test command for every later task.

- [ ] **Step 1:** Tell Febriel `uv` will be installed, then `brew install uv`. Verify: `uv --version` prints a version.
- [ ] **Step 2:** `git init -b main` in the project folder. `.gitignore`: `.venv/`, `__pycache__/`, `spikes/**/tmp/`, `*.wav`, `.DS_Store`.
- [ ] **Step 3:** `pyproject.toml`: project `jarvis`, `requires-python = ">=3.12,<3.13"`, dev dependency `pytest`. No runtime dependencies yet.
- [ ] **Step 4:** `tests/test_smoke.py` with `def test_import(): import jarvis`. Run `uv run pytest -q`. Expected: `1 passed`.
- [ ] **Step 5:** Commit everything including `PROJECT.md` and `docs/`: `chore: scaffold jarvis package`.

### Task 2: Memory writer

**Files:**
- Create: `jarvis/memory/vault.py`
- Test: `tests/memory/test_vault.py`

**Interfaces:**
- Produces:
  - `Exchange(at: datetime, channel: Literal["mac","phone"], asked: str, answered: str, notes_read: list[str])`
  - `TaskRecord(at: datetime, channel: Literal["mac","phone"], title: str, asked: str, done: str, agents: list[tuple[str, str]], confirmations: list[tuple[str, bool]], files: list[str], notes_read: list[str])` — `agents` is `(agent, model)`, `confirmations` is `(question, answered_yes)`.
  - `slugify(title: str) -> str`
  - `Vault(root: Path)` with `log_exchange(ex: Exchange) -> Path`, `write_task_note(rec: TaskRecord) -> Path`, `read_index() -> str`
  - `default_vault() -> Vault` reading `JARVIS_VAULT`, else the path in Global Constraints.

- [ ] **Step 1: Write the failing tests**

```python
AT = datetime(2026, 11, 10, 20, 14)

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
```

`record(**overrides)` is a test helper building a `TaskRecord` at `AT` on channel `"mac"`.

- [ ] **Step 2:** Run `uv run pytest tests/memory -q`. Expected: fails on import.
- [ ] **Step 3:** Implement `jarvis/memory/vault.py` to the Interfaces block. `raw/` is created on demand. Appends open the file in append mode and write one whole line per call. `notes_read` entries are written as wiki-links by file stem.
- [ ] **Step 4:** Run `uv run pytest tests/memory -q`. Expected: `8 passed`.
- [ ] **Step 5:** Commit: `feat: vault writer for day log and task notes`.

### Task 3: Gate — shell commands and file paths

**Files:**
- Create: `jarvis/brain/gate.py`, `jarvis/brain/trusted.py`
- Test: `tests/brain/test_gate_shell.py`, `tests/brain/test_trusted.py`

**Interfaces:**
- Produces:
  - `Decision(verdict: Literal["allow","ask","never"], reason: str, pattern: str)` — `pattern` is the key a "yes, always" stores.
  - `TrustedList(path: Path)` with `contains(pattern: str) -> bool`, `add(pattern: str) -> None`. Plain text, one pattern per line, blank lines and `#` comments ignored, no duplicates. Default path `~/.jarvis/trusted.txt`.
  - `GateConfig(free_write: list[Path], protected: list[Path], trusted: TrustedList, read_tools: set[str])`
  - `classify_path_write(path: Path, cfg: GateConfig) -> Decision`
  - `classify_shell(command: str, cwd: Path, cfg: GateConfig) -> Decision`

Rules the tests do not fully determine:
- Split a command on `;`, `&&`, `||`, `|`; treat `$(...)`, backticks and each `>`/`>>` target as further parts. Classify every part; the strictest verdict wins (`never` > `ask` > `allow`).
- Read-only (allow): `ls cat head tail grep rg pwd echo date which wc stat file du df ps`, `find` without `-delete`/`-exec`, and `git status|log|diff|show|branch`.
- Path-judged: `rm mv cp mkdir touch tee` and redirects — allow only if every target resolves (`Path.resolve()`, after `~` expansion relative to `cwd`) inside a free-write area and outside every protected path.
- Always ask: `git push`, and installs (`brew install`, `npm install`/`npm i`, `pip install`, `uv add`, `uv pip install`).
- `sudo` anywhere: `never`, and a trusted pattern cannot override `never`.
- Anything else: `ask`. A command that fails to parse: `ask`.
- `pattern`, the key a "yes, always" stores, is built from the part that caused the `ask`:
  - `git`, `brew`, `npm`, `pip`, `uv`: command plus first argument that does not start with `-` → `shell:git push`, `shell:brew install`.
  - Path-judged commands: command plus the resolved parent folder of the first out-of-area target → `shell:rm:/Users/febrielotud/Documents`. A bare `shell:rm` is never produced, so one yes cannot unlock deleting everywhere.
  - Anything else: command name only → `shell:frobnicate`.
- A trusted pattern turns `ask` into `allow` for that part only.

- [ ] **Step 1: Write the failing tests**

```python
HOME = Path.home()

@pytest.mark.parametrize("cmd,verdict", [
    ("ls -la ~/Documents", "allow"),
    ("git status", "allow"),
    ("rm ~/Developer/scratch/tmp.txt", "allow"),
    ("rm ~/Documents/tax.pdf", "ask"),
    ("git push origin main", "ask"),
    ("brew install tmux", "ask"),
    ("frobnicate --all", "ask"),
    ("sudo rm -rf /", "never"),
    ("ls && rm -rf ~/Documents", "ask"),
    ("echo hi > ~/Documents/a.txt", "ask"),
    ("cat $(rm ~/Documents/a.txt)", "ask"),
    ("rm ~/Developer/../Documents/a.txt", "ask"),
    ("find ~/Developer -name '*.tmp' -delete", "ask"),
    ("echo 'unterminated", "ask"),
    ("ls; sudo ls", "never"),
])
def test_shell_verdicts(cmd, verdict, cfg):
    assert classify_shell(cmd, HOME, cfg).verdict == verdict

def test_protected_paths_ask_even_inside_free_write(cfg):
    target = HOME / "Developer" / "Project Jarvis" / ".claude" / "settings.json"
    assert classify_path_write(target, cfg).verdict == "ask"

def test_symlink_out_of_free_write_asks(tmp_path, cfg_for):
    free, outside = tmp_path / "free", tmp_path / "outside"
    free.mkdir(); outside.mkdir(); (free / "link").symlink_to(outside)
    assert classify_path_write(free / "link" / "a.txt", cfg_for(free)).verdict == "ask"

def test_trusted_pattern_allows_but_never_stays_never(cfg):
    cfg.trusted.add("shell:git push"); cfg.trusted.add("shell:sudo")
    assert classify_shell("git push", HOME, cfg).verdict == "allow"
    assert classify_shell("sudo ls", HOME, cfg).verdict == "never"
```

```python
def test_trusted_file_is_hand_editable(tmp_path):
    f = tmp_path / "trusted.txt"; f.write_text("# mine\n\nshell:git push\n")
    t = TrustedList(f)
    assert t.contains("shell:git push") and not t.contains("# mine")
    t.add("shell:git push"); t.add("screen:Mail:send")
    assert f.read_text().count("shell:git push") == 1 and t.contains("screen:Mail:send")
```

Fixtures `cfg` (free-write `~/Developer` and a temp vault; protected `~/Developer/Project Jarvis/.claude` and `~/.jarvis`; trusted list in `tmp_path`) and `cfg_for(free_dir)` live in `tests/brain/conftest.py`.

- [ ] **Step 2:** Run `uv run pytest tests/brain -q`. Expected: fails on import.
- [ ] **Step 3:** Implement `trusted.py`, then `gate.py`, using `shlex` for tokenising.
- [ ] **Step 4:** Run `uv run pytest tests/brain -q`. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: ask-first gate for shell commands and paths`.

### Task 4: Gate — on-screen actions and connector tools

**Files:**
- Modify: `jarvis/brain/gate.py`
- Test: `tests/brain/test_gate_screen.py`

**Interfaces:**
- Consumes: `Decision`, `GateConfig`, `TrustedList` from Task 3.
- Produces:
  - `ASK_WORDS: tuple[str, ...]` — the ten words in Global Constraints.
  - `classify_screen(action: Literal["click","type","press","scroll","open","drag"], app: str, cfg: GateConfig, role: str = "", label: str = "", key: str = "") -> Decision`
  - `classify_tool(name: str, cfg: GateConfig) -> Decision`

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("label,verdict", [
    ("Send", "ask"), ("Send Message", "ask"), ("Delete…", "ask"), ("CONFIRM", "ask"),
    ("Sender", "allow"), ("Reply", "allow"), ("Postpone", "allow"), ("", "allow"),
])
def test_click_judged_by_whole_word_label(label, verdict, cfg):
    assert classify_screen("click", "Mail", cfg, role="button", label=label).verdict == verdict

def test_typing_scrolling_opening_are_free(cfg):
    for action in ("type", "scroll", "open"):
        assert classify_screen(action, "Finder", cfg, role="textfield", label="Search").verdict == "allow"

def test_return_asks_until_app_is_trusted(cfg):
    d = classify_screen("press", "Messages", cfg, key="Return")
    assert d.verdict == "ask" and d.pattern == "screen:Messages:key:return"
    cfg.trusted.add(d.pattern)
    assert classify_screen("press", "Messages", cfg, key="Return").verdict == "allow"

def test_click_pattern_is_app_plus_word(cfg):
    assert classify_screen("click", "Mail", cfg, role="button", label="Send Message").pattern == "screen:Mail:send"

def test_other_keys_are_free(cfg):
    assert classify_screen("press", "Messages", cfg, key="Tab").verdict == "allow"

def test_drag_asks(cfg):
    assert classify_screen("drag", "Finder", cfg).verdict == "ask"

def test_tools_free_only_if_listed_as_read(cfg):
    cfg.read_tools.add("mcp__gmail__search_threads")
    assert classify_tool("mcp__gmail__search_threads", cfg).verdict == "allow"
    assert classify_tool("mcp__gmail__create_draft", cfg).verdict == "ask"
    assert classify_tool("mcp__unknown__thing", cfg).verdict == "ask"
```

Drag asks because a drop can move or delete files and the gate cannot see the destination (not stated in the spec; consistent with "anything it cannot classify asks").

- [ ] **Step 2:** Run `uv run pytest tests/brain/test_gate_screen.py -q`. Expected: fails on import.
- [ ] **Step 3:** Implement both functions. Label matching is case-insensitive on whole words after stripping punctuation.
- [ ] **Step 4:** Run `uv run pytest tests/brain -q`. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: gate rules for on-screen actions and connector tools`.

### Task 5: Voice state machine

**Files:**
- Create: `jarvis/daemon/state.py`
- Test: `tests/daemon/test_state.py`

**Interfaces:**
- Produces:
  - `State` enum: `IDLE, LISTENING, THINKING, SPEAKING, FOLLOW_UP`
  - `Event` enum: `WAKE, SPEECH_START, SPEECH_END, REPLY_START, REPLY_END, TICK, MUTE, UNMUTE`
  - `FOLLOW_UP_SECONDS = 6.0`
  - `StateMachine(clock: Callable[[], float])` with `state: State`, `muted: bool`, `mic_open: bool`, `on(event: Event) -> State`

- [ ] **Step 1: Write the failing tests**

```python
def test_happy_path(sm):
    assert [sm.on(e) for e in (Event.WAKE, Event.SPEECH_END, Event.REPLY_START, Event.REPLY_END)] == \
        [State.LISTENING, State.THINKING, State.SPEAKING, State.FOLLOW_UP]

def test_follow_up_needs_no_wake_word(sm, clock):
    reach(sm, State.FOLLOW_UP); clock.advance(5.9)
    assert sm.on(Event.SPEECH_START) == State.LISTENING

def test_follow_up_expires_after_six_seconds(sm, clock):
    reach(sm, State.FOLLOW_UP); clock.advance(6.0)
    assert sm.on(Event.TICK) == State.IDLE
    assert sm.on(Event.SPEECH_START) == State.IDLE

def test_wake_ignored_while_speaking_or_thinking(sm):
    reach(sm, State.THINKING); assert sm.on(Event.WAKE) == State.THINKING
    sm.on(Event.REPLY_START); assert sm.on(Event.WAKE) == State.SPEAKING

def test_mic_closed_while_speaking(sm):
    reach(sm, State.SPEAKING); assert sm.mic_open is False
    sm.on(Event.REPLY_END); assert sm.mic_open is True

def test_mute_closes_mic_and_ignores_wake(sm):
    sm.on(Event.MUTE)
    assert sm.mic_open is False and sm.on(Event.WAKE) == State.IDLE
    sm.on(Event.UNMUTE); assert sm.on(Event.WAKE) == State.LISTENING

def test_unexpected_events_do_not_move_state(sm):
    assert sm.on(Event.REPLY_END) == State.IDLE and sm.on(Event.SPEECH_END) == State.IDLE
```

`clock` is a fake with `advance(seconds)`; `reach(sm, state)` drives the happy path to that state.

- [ ] **Step 2:** Run `uv run pytest tests/daemon -q`. Expected: fails on import.
- [ ] **Step 3:** Implement as a transition table; `WAKE` is accepted only in `IDLE`. Follow-up expiry is checked on every event, not only `TICK`.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: whole suite passes.
- [ ] **Step 5:** Commit: `feat: voice state machine with follow-up window and mic gating`.

---

## Part B — Spikes (Febriel is needed where marked 👤)

Spike code is throwaway, lives in `spikes/NN-name/`, has no tests, and is never imported by `jarvis/`. Each spike ends by appending a section to `docs/spikes/findings.md`: what was run, the numbers, pass or fail against the bar below, and what it means for the design. Before any spike that opens a port, check the port is free (`lsof -i :8787`).

### Task 6: Spike 1 — Claude Code as the brain, on the subscription

Settles §10 risk 1 and decides Plan 2's bridge. Most important spike; do it first.

- [x] **Step 1 (done 2026-11-13: pass):** Assert `ANTHROPIC_API_KEY` is unset. Start `claude -p --model sonnet --input-format stream-json --output-format stream-json --verbose` as a child process; send two user messages a minute apart on stdin. **Bar:** both answered in one process, second remembers the first, `system/init` shows subscription auth and no API key.
- [x] **Step 2 (done: pass):** Add `spikes/01-brain/.claude/agents/` with `jarvis` (sonnet), `triage` (`model: claude-opus-5-5`), `quick` (haiku). Run with `--agent jarvis`; ask something that makes it call `triage`, then dispatch `quick` passing a per-call model. **Bar:** stream shows each agent on the expected model.
- [x] **Step 3 (done: pass, hook and prompt tool both work):** Permission bridge. Try a `PermissionRequest` hook that calls a local script, and `--permission-prompt-tool`; the script waits 5 s then answers. Ask for `touch ~/Documents/jarvis-spike.txt`. **Bar:** the command is held until the script answers; deny prevents it; allow runs it. Record which mechanism works and the exact payload the script receives. Delete the file afterwards.
- [x] **Step 4 (done: pass):** Start a second session in `/tmp` with `--settings <path to the spike's settings>`. **Bar:** the same hook fires there.
- [x] **Step 5 (done: pass):** Run a worker as a background subagent for 60 s and send a new user message meanwhile. **Bar:** the front door answers before the worker finishes. If not, record whether one process per channel is needed.
- [x] **Step 6 (done: detached `-p` + `--resume` works; `--bg` needs folder trust, untested):** Try `claude --bg "<task>"` and a detached `claude -p` resumed by session ID. Record which gives a session that survives the parent and shows in the Claude app's Code tab.
- [x] **Step 7 (done: 0.79 s median first token):** Record time from sending a short message to first text token, ten runs. Write findings. Commit.

**If the bar in Step 1 or 3 fails:** stop the plan and bring it to Febriel; the design's engine choice is in question.

### Task 7: Spike 2 — microphone and wake word 👤

- [x] **Step 1 (done 2026-11-13):** Name the installs (`openwakeword`, `sounddevice`, `onnxruntime`), then add them to a spike-only dependency group.
- [x] **Step 2 (done: fail, 3 of 10; custom training also failed; Febriel chose wake by transcription, tested in Task 8):** Script: open the mic, run the "hey jarvis" model, print a timestamp per detection. 👤 Febriel grants the microphone prompt and says "Hey Jarvis" ten times from about 2 m. **Bar:** 9 of 10 detected.
- [x] **Step 3 (moved to Task 8, done 2026-11-14: 0 false wakes in 29 min):** 👤 Leave it running 30 min with a video or music playing. **Bar:** at most 1 false trigger.
- [x] **Step 4 (done 2026-11-13: pass, mic opens from a launchd agent):** Run the same script from a `launchd` user agent. Record whether the mic opens. If not, Plan 3 starts `jarvisd` from a Terminal login item.
- [x] **Step 5 (done: 6–10 % with openWakeWord; 2–4 % with wake by transcription):** Record idle CPU. Write findings. Commit.

### Task 8: Spike 3 — speech-to-text and end of speech 👤

- [x] **Step 1:** Name the installs (`parakeet-mlx`, a voice-activity detector, model download size), then install.
- [x] **Step 2 (done 2026-11-14; 8 of the 10 requests were captured, Parakeet 0.17 s median, 1 meaning error):** 👤 Febriel speaks ten typical requests. Detect end of speech at 0.8 s of silence and transcribe. **Bar:** median transcription under 0.7 s for utterances up to 5 s; at most 1 of 10 with an error that changes the meaning; silence produces no text.
- [x] **Step 3 (amended 2026-11-13; done 2026-11-14, winner Parakeet; live wake test and 30-minute false-trigger run (moved here from Task 7) done 2026-11-14: about 88 % wake, 0 false wakes in 29 min, CPU 2–4 %):** Name the install (`faster-whisper`, model `small.en`), then run the same ten recordings through it with `compute_type="int8"`. Record both engines side by side: median time, and meaning-changing errors out of 10. The one that meets the bar with fewer errors wins; on a tie, Parakeet. Only if both fail, repeat with whisper.cpp. The recordings live in the spike's temp folder and are deleted when the spike ends. Write findings, naming the winner. Commit.

### Task 9: Spike 4 — spoken replies 👤

- [x] **Step 1 (amended 2026-11-13; all installed 2026-11-13):** Name the installs (`mlx-audio`, `kokoro-onnx`, Kokoro model files for each), then install.
- [x] **Step 2:** List Kokoro's British male presets; synthesize the same three sentences in each and in `say -v Daniel`. 👤 Febriel picks one by ear. **Picked: `bm_daniel` (2026-11-13).**
- [x] **Step 3 (amended 2026-11-13; done 2026-11-13, winner `mlx-audio`: first audio 0.19 s, no gaps; `kokoro-onnx` 0.65 s fails the bar):** Stream a paragraph sentence by sentence in the chosen voice, once through `mlx-audio` and once through `kokoro-onnx`. **Bar:** first audio within 0.5 s of the first sentence arriving; no audible gap over 0.3 s between sentences. Record both; the one faster to first audio that meets the bar wins, and on a tie the one with fewer dependencies.
- [x] **Step 4 (done 2026-11-14: 1.95 s on the bare sum, about 2.2–2.8 s with the first-sentence wait):** Add Spike 1's first-token time and Spike 3's transcription time. **Bar (§11):** about 2.5 s from end of speech to first spoken word. Write findings, including the chosen voice. Commit.

### Task 10: Spike 5 — on-screen control 👤

- [x] **Step 1 (done 2026-11-13, 1.3.0; Accessibility granted to the Claude app):** Name the install, then `npm install -g agent-desktop`. 👤 Febriel grants Accessibility via `agent-desktop permissions --guide`.
- [x] **Step 2:** In TextEdit: snapshot, click, type a line. In Finder: `drag` a scratch file between two scratch folders, reading the syntax from `agent-desktop drag --help`. Record exact commands.
- [x] **Step 3:** Record what a snapshot gives for a button (role and label fields) and confirm it is enough for Task 4's `classify_screen`. If field names differ, note the mapping.
- [x] **Step 4 (done 2026-11-14: fail while locked; lock is "immediately", so asleep means locked; decision for Febriel):** 👤 With the session unlocked, run `pmset displaysleepnow`, wait 2 min, repeat Step 2 from a delayed script, and take a screenshot. **Bar:** actions succeed with the display asleep. Record whether the screenshot is usable.
- [x] **Step 5 (done 2026-11-14: findings written, brought to Febriel):** Write findings. If the bar fails, remote on-screen control needs the display awake; bring it to Febriel. Commit.

### Task 11: Spike 6 — phone round trip 👤

- [ ] **Step 1:** 👤 Febriel creates a Tailscale account, installs it on the Mac and iPhone, and signs in on both. (Jarvis does not create accounts.)
- [x] **Step 2:** Spike server on `127.0.0.1:8787`: `POST /ask` with header `Authorization: Bearer <token>` and JSON `{"text": "..."}` returns `{"say": "...", "needs_reply": false}`; a wrong or missing token returns 401. The token is generated into `~/.jarvis/token` (mode 600) and never printed in chat.
- [ ] **Step 3:** `tailscale serve` it over HTTPS to the tailnet. Verify from the Mac that it is not reachable without Tailscale.
- [ ] **Step 4:** 👤 Febriel builds the Shortcut from `shortcuts/README.md` (written in this step): Dictate Text → Get Contents of URL → Speak Text → repeat while `needs_reply` is true. Febriel pastes the token in personally.
- [ ] **Step 5:** 👤 Test on mobile data with Wi-Fi off, by icon and by "Hey Siri, Jarvis". Make the server answer the first request with `needs_reply: true`. **Bar:** request to spoken answer under 4 s; the reply loop works hands-free; 401 without the token.
- [ ] **Step 6:** Send an iMessage to Febriel's own Apple ID from the Mac with `osascript`. 👤 Febriel confirms it arrives as a notification. Record whether macOS prompted for Automation permission.
- [ ] **Step 7:** Stop the server and `tailscale serve reset`. Write findings. Commit.

### Task 12: Spike 7 — staying awake 👤

- [ ] **Step 1 (first run 2026-11-13 23:38 → 09:13 inconclusive: other apps kept the Mac awake and the log was lost; repeat on a clean night, with the tailnet check once Tailscale exists):** 👤 Plugged in, lid open: run `caffeinate -i` overnight with a script that logs a timestamp and a tailnet reachability check every 5 min. **Bar:** no gap over 6 min in the log; `pmset -g log` shows no system sleep.
- [ ] **Step 2:** 👤 On battery for 2 h, same script. **Bar:** same. Record battery drop per hour.
- [ ] **Step 3:** Confirm the display slept during both runs. Write findings. Commit.

### Task 13: Checkpoint

- [ ] **Step 1:** Read `docs/spikes/findings.md` end to end. For every bar that failed or finding that contradicts the spec, amend the spec and mark the amendment with the date.
- [ ] **Step 2:** Update `PROJECT.md`: replace the "Verified for the design" entry with measured facts, record dead ends.
- [ ] **Step 3:** File the findings to Obsidian per Febriel's global rule. Commit.
- [ ] **Step 4:** Bring Febriel a short summary: what held, what changed, and anything needing a decision. Then write Plan 2.
