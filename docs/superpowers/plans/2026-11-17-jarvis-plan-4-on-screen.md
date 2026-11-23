# Jarvis Plan 4 — Jarvis on Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. One review pass at the end of the plan, not per task (Febriel's rule).

**Goal:** Jarvis is a floating red circle of silk lines that goes wild while it works and talks, and every working agent is a named glass bead hanging from it on a silk thread, where Febriel answers its question or stops it, by click or by voice.

**Architecture:** `jarvisd` learns to name agents, to know which agent asked a question, to stop one agent, and to report how loud its own speech is; all of that goes out on the event stream it already has. A new process, `jarvis face`, is a client of that stream like the terminal HUD: a pure Python model turns events into "what the circle does" and "which five beads show, open or as one line", pure arithmetic places them around the circle, a small controller pushes that out, and a thin AppKit shell shows it: the circle is a canvas in a web view, each bead is a native Liquid Glass panel, the threads are shape layers. Nothing that draws decides anything.

**Tech Stack:** Python 3.12, PyObjC (`pyobjc-framework-Cocoa` and Quartz, both installed since Plan 3; `pyobjc-framework-WebKit` is new), AppKit's Liquid Glass (`NSGlassEffectView`) and Core Animation for the beads and threads, a local HTML/canvas page for the circle only, the existing `aiohttp`, `textual`, `pytest` + `pytest-asyncio`.

**Spec:** `docs/superpowers/specs/2026-11-17-jarvis-screen-hud-design.md` (approved 2026-11-17); section numbers below refer to it. **Amended by `docs/superpowers/specs/2026-11-23-jarvis-face-tether-design.md`** ("the tether design"; Febriel chose Tether on 2026-11-23), which wins where they disagree. The look: the circle from `docs/superpowers/specs/assets/2026-11-17-jarvis-face-mockup.html`; the beads, threads and their motion from `docs/superpowers/specs/assets/2026-11-23-jarvis-face-directions.html`, direction Tether.

**Rewritten 2026-11-23 for Tether:** the header, decisions 8 and 10–15, the file structure, Global Constraints, Review Focus 6, probes P1–P3, P7 and P8, `ask_until` in Task 3, Tasks 7–10, the new Task 9A, and Task 12's rows. Tasks 2, 4, 5, 6 and 11 are as written on 2026-11-17. The main design: `docs/superpowers/specs/2026-11-10-jarvis-design.md`. Measured facts: `docs/spikes/findings.md`.

## Where this plan sits

| Plan | Delivers |
|---|---|
| 1, 2 (done) | Foundation, typed Jarvis, the terminal HUD |
| 3 (written) | Voice |
| **4 (this)** | **The circle, the agent beads on their threads, names, stop, the red terminal HUD** |
| 5 | Phone route, Reminder nudge, keep-awake, battery rule |
| 6 | On-screen control, reverse engineering, spawned sessions |

**This plan is built after Plan 3 and written against Plan 3's interfaces as planned** (`Jarvis.level`, the `state` and `level` events, `Speaker`, `Player`, `health.mic`, the fixtures in `tests/conftest.py`). Where Plan 3's own amendments changed one of them during its run, the amended form wins; Task 1 Step 1 checks.

## Decisions this plan makes

Left to the builder by the design (§10), settled here. Claude's calls.

1. **Names are chosen when the gate allows the dispatch**, keyed by the `Agent` call's `tool_use_id`, so the name exists before the worker starts. The row takes it at `agent_start`.
2. **The model learns the name from the dispatch itself**: the hook's allow carries an edited input whose `description` starts with the name ("Nova: Fix export bug") and whose prompt starts with "Your name is Nova." Task 1 probes whether Claude Code honours that; the fallbacks are in Task 4.
3. **Stop is the gate first, then the end.** `jarvisd` refuses every further call from that agent at once, then asks the front door to end it with a `[jarvisd]` notice, unless Task 1 finds a direct way to end one worker.
4. **Ended rows stay in `jarvisd`'s list for 8 s** with their final state, so the face and the terminal HUD both show "done" without keeping timers of their own.
5. **"Stopped Nova." is said when the stop came by voice or typing**, not when it came from a card (§7.6: he clicked it; he knows).
6. **A plain "stop" still cancels everything** (main design §6.2). "Stop Nova" is the narrow one. If the name is not heard, the sentence is the wide one; the card is the sure way.
7. **"Jarvis" is a name too** while Jarvis itself has a question open: "yes to Jarvis" answers it.
8. **What draws has no logic to test.** Order, the cap of five, open or one line, states, wording, elapsed times, the countdown and every position are computed in Python and handed over; the page and the native views show what they are given. So there is no JavaScript test runner in this project and no test opens a window.
9. **The alert sound is played by the face**, with macOS's own `Glass` sound.
10. **Beads are native, one small panel each** (tether design §8). A panel exactly the bead's size leaves no transparent area over his work that could swallow a click. The threads live in one panel that ignores the mouse.
11. **No Python runs per frame for the beads.** Panels move with AppKit's animation; threads, marks and the countdown are layer animations. Python acts on events and once a second.
12. **Hover is the face's own state.** It opens a bead and never reaches `jarvisd`.
13. **The four-second pop is counted from the agent's `since`**, so a restarted face does not pop every bead again.
14. **A stopped or failed agent's thread is cut at once**; a done one's fades (tether design §5).
15. **In code a bead is a `Card` and the plume a `Stack`**, as `CARD_MAX` and the rows already say.

## Amendments after Task 1

Probe results are in `docs/spikes/findings.md`, "Plan 4 probes". Where this table disagrees with a task, it wins.

| Probe | Found | Changes |
|---|---|---|
| P4 | `updatedInput` on an `Agent` allow is honoured, foreground and background | Decision 2 stands; Task 4 Step 5 (fallbacks) not built |
| P5 | The hook's `agent_id` is the worker's `task_id`; a denied worker ends itself in ~4 s | One-click stop is built; Task 5 Step 3's stop-all fallback is not |
| P6 | A `stop_task` control request ends one worker at once (`task_notification` status `stopped`) | Decision 3: the gate first, then `Bridge.stop_task`; no `[jarvisd]` notice. `agent_done` status `stopped` → row state `stopped` (Task 3) |
| P5/P6 | The front door announces a stopped worker on its own | Task 5 hushes the front door's next self-started turn when a stopped worker ends outside a turn |
| P1 | The mockup's one stroke per line costs ~20 % of a core working; batched by 12 opacity steps ~14–18 % | Task 9 draws batched only; idle at 10 fps; muted and off draw one still frame |
| P1a | App Nap freezes an accessory app's timers after ~90 s | Task 10 holds an `NSProcessInfo` activity (user-initiated, idle sleep allowed) |
| P7 | `callAsyncJavaScript` with arguments is exact | Task 10 pushes the payload that way |
| — | A page cannot move its own window | Dragging the circle is native (Task 10); the page posts no messages at all; the shell hands `{"type": "moved", x, y}` to `Controller.on_message` |
| P2, P3, P8 (live, on the built face) | One panel per bead passes every click, typing, full-screen and Spaces check; the system glass is right in light, dark and Reduce Transparency; the 0.45 s animation group is smooth with threads attached | Decision 10 and Task 10's motion stand; no timer spring |
| P1 (live, on the built face) | Idle 7.2 %, working/talking ~22 % at 30 fps; the circle's web view is ~19 % of it | Febriel kept 30 fps: budgets are now working/talking ≤ 25 %, idle ≤ 8 %, memory ≤ 200 MB |
| Live, Febriel | A working bead sometimes stays open after the pointer leaves; he wants a shortcut to hide the face | Fixed after Task 12 Step 1: hover reconciled with the real pointer; Ctrl-Option-J (detected in jarvisd's key tap) hides and shows the face; a question while hidden brings it back |

## File structure

| File | Responsibility |
|---|---|
| `jarvis/config.py` (modify) | The constants in Global Constraints. |
| `jarvis/daemon/names.py` | The name list; pick one not in use; match a heard word to a running name. Pure. |
| `jarvis/daemon/instant.py` (modify) | "stop Nova", "yes / no / yes always to Nova". Pure. |
| `jarvis/brain/asks.py` (modify) | A question records the agent that asked. |
| `jarvis/brain/hook.py` (modify) | Passes an edited input through on allow. |
| `jarvis/daemon/exchange.py`, `jarvis/memory/vault.py` (modify) | Names in the task note. |
| `jarvis/daemon/core.py` (modify) | Names, richer agent rows, lingering, stop, named answers, speech level. |
| `jarvis/remote/api.py` (modify) | `POST /stop`. |
| `jarvis/remote/client.py` | The API client, moved out of the terminal HUD so the face can use it without Textual. |
| `jarvis/voice/audio.py`, `jarvis/voice/speaker.py` (modify) | The loudness of what is being played. |
| `jarvis/face/model.py` | Events → circle mode and the card stack, each card open or one line, its countdown. Pure. |
| `jarvis/face/place.py` | Where the circle sits: load, save, keep on screen. Pure. |
| `jarvis/face/tether.py` | Where each bead hangs around the circle and how its thread runs. Pure. |
| `jarvis/face/mark.py` | A name → its silk mark. Pure. |
| `jarvis/face/controller.py` | Events in; the circle's payload, the stack and the sound out; answers, stops and hover from the beads; `moved` from the page. No AppKit. |
| `jarvis/face/page/` (`circle.html`, `face.css`, `circle.js`) | The circle, drawn. |
| `jarvis/face/beads.py` | One bead: a small glass panel with native labels and buttons, its mark, its countdown. AppKit. |
| `jarvis/face/threads.py` | The click-through panel of threads. AppKit. |
| `jarvis/face/app.py` | The Mac app shell: the circle's panel and web view, the two threads of work, laying the plume out. AppKit. |
| `jarvis/cli.py` (modify), `launchd/com.febriel.jarvis-face.plist`, `launchd/README.md` | `jarvis face` and its login agent. |
| `jarvis/tui/jarvis.tcss`, `jarvis/tui/app.py`, `jarvis/tui/model.py` (modify) | Red; names in AGENTS. |
| `.claude/agents/jarvis.md` (modify) | One line: workers have names. |
| `spikes/10-face/` | Task 1's probes. |

## Global Constraints

- Subscription login only. The face calls no model.
- Exact values, in `jarvis/config.py`: `CARD_MAX = 5`, `CARD_LINGER_SECONDS = 8.0`, `CIRCLE_SIZE = 160` (points), `FACE_FPS = 30`, `FACE_EASE_SECONDS = 2.0`, `NAME_SIMILARITY = 0.7`, `RED_ACTIVE = "#FF3B30"`, `RED = "#C2241B"`, `RED_DIM = "#6B1512"`, `CARD_POP_SECONDS = 4.0`, `CARD_OPEN_WIDTH = 300`, `CARD_LINE_HEIGHT = 36`, `CARD_GAP = 10` (points), `TETHER_RIM = 68`, `TETHER_CLEAR = 88`, `TETHER_STEP = 46` (points, for a 160-point circle), `FACE_MOVE_SECONDS = 0.45`. The three reds are for the circle, the threads and the terminal HUD; a bead takes its colours from the system. Gold (`#D4AF37`, `#FFD700`, `#8A7424`) appears nowhere after this plan.
- Budgets (§8), counting every process the face starts: idle ≤ 5 % of one core, working or talking ≤ 15 %, memory ≤ 200 MB, a card on screen ≤ 0.5 s after its agent starts.
- The page: loaded from files inside the package, never from a URL; a Content-Security-Policy of `default-src 'none'; script-src 'self'; style-src 'self'`; never given the token; never given an agent's text (it draws the circle only); its one word set with `textContent`. It can send exactly one message: `moved`.
- A bead: every string from `jarvisd` is set as a plain string on a native label or button, never through HTML or an attributed string. Colours are `labelColor`, `secondaryLabelColor` and `systemRedColor`, so light mode, dark mode, Reduce Transparency and Increase Contrast are the system's work. One text size, 13 points; the name and the question are semibold.
- The face's windows never become the key window and never show a Dock icon. Clicks outside a bead or the circle pass through. A bead's button acts on the first click while another app is in front.
- Nothing is drawn where there is nothing to show: no agents means the circle alone.
- `jarvisd` never imports AppKit or WebKit. `jarvis face` never imports `mlx`, `sounddevice` or `openwakeword`. Importing `jarvis.cli` imports none of them.
- Unit tests never open a window, a web view or a sound.
- Cards are for workers: every agent type except `triage` and `scribe` (the same rule as `exchange.FREE_AGENTS`). A `Jarvis` card exists only while Jarvis itself has a question open.
- A question, a stop or an answer always names its target by id on the wire. Names are for people; ids are for code.
- Installs, each named to Febriel before it runs: `pyobjc-framework-WebKit`. `pyobjc-framework-Cocoa` is already there (it came with Quartz) and becomes a declared dependency.
- The log holds timings and errors only. English only. Commits carry no Claude credit line.

## Review Focus

1. **An agent's text run as code.** A doing-line or question such as `<img src=x onerror=…>` or `");alert(1)//` must show as those characters. Pinned in Tasks 8, 9 and 10.
2. **A stop or an answer landing on the wrong agent.** A mis-heard name, two names that sound alike, a name that matches no one. It reaches the right agent or no agent, never another one. Pinned in Tasks 2 and 5.
3. **A stopped agent that can still act.** A call it already had waiting for a yes, a call it makes a second later, its result arriving afterwards and being announced. Pinned in Task 5.
4. **A face showing what is no longer true.** `jarvisd` restarts or dies: no card keeps a live button for an agent that is gone, and a click on a stale card does nothing harmful. Pinned in Tasks 7 and 8.
5. **More than five at once.** Seven workers with the two questions among the oldest: a card with a question is never the one hidden, and the counts on the chip are right. Pinned in Task 7.
6. **A bead where it must not be.** Off the screen, over the circle, over another bead, or with a thread running through a bead, for any place he can drag the circle to and any mix of open and one-line beads. Pinned in Task 9A.

---

### Task 1: Dependencies and probes 👤

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `docs/spikes/findings.md`
- Create: `spikes/10-face/`

**Interfaces:**
- Produces: the two packages; a "Plan 4 probes" section in the findings; if a probe contradicts this plan, an "Amendments after Task 1" table under "Decisions this plan makes" (where it disagrees with a task, it wins).

- [x] **Step 1: Check Plan 3 landed as planned.** `Jarvis.level`, `Jarvis.set_mic`, the `level` and `state` events, `Player`, `VoiceSpeaker` and `tests/conftest.py` exist with the shapes Plan 3 names, or its amendments say how they differ. Note any difference in the amendments table. Run `uv run pytest -q` and record the count as this plan's baseline.

- [x] **Step 2: Name the install to Febriel, then** `uv add pyobjc-framework-Cocoa pyobjc-framework-WebKit` (Cocoa is already installed; this declares it), `uv sync`. Run `uv run python -c "import AppKit, WebKit, Quartz; import objc; objc.lookUpClass('NSGlassEffectView')"` → no error; `uv run pytest -q` → baseline.

- [x] **Step 3: Run the probes**

| # | Probe | Bar | Changes |
|---|---|---|---|
| P1 | 👤 A throwaway face: the circle's panel with a web view showing the mockup's circle at 160 points, five glass bead panels around it (one open with three buttons), and five threads with their sway and travelling dots. Measure CPU and memory of the process and its WebKit helpers for two minutes each: idle (no beads), working (five beads), talking | The budgets in Global Constraints. If missed, in this order (§8): idle at 10 frames a second; no sway on the threads; memory limit 300 MB; bring it to Febriel if working still costs over 25 % | Go or no-go; `FACE_FPS` |
| P2 | 👤 The same throwaway: type in another app while beads appear; click a bead's button once; move the pointer over a bead; click just outside a bead and between a bead and the circle; open a full-screen app; switch Spaces | Typing is never interrupted; the button acts on that first click; the hover is reported while the other app stays in front; the clicks outside reach the app underneath; everything shows over full screen and on every Space. If one panel per bead fails any of these, try one large panel that turns mouse handling on only over a bead | Decision 10, Task 10 |
| P3 | 👤 Liquid Glass from Python: an `NSGlassEffectView` with 18-point corners and a red tint, in a borderless panel that is never key, over a white document, a dark video and a busy wallpaper, in light and dark mode, and with Reduce Transparency on | It is real glass, not the dimmed look of an inactive window; text on it stays readable in every case; it has a soft shadow. If not: `NSVisualEffectView` (material `hudWindow`, state active, masked to the same corners). Recorded: whether the system glass has its own pointer highlight | Task 10 |
| P4 | The hook allows an `Agent` call with an edited input (`hookSpecificOutput.updatedInput`: `description` "Nova: count files", prompt prefixed "Your name is Nova."), foreground and background | The worker's `task_started` shows the edited description; asked "what is your name?" the worker says Nova; when it finishes, the front door's own announcement says "Nova". If the edit is ignored: try a `PostToolUse` hook on `Agent` returning `additionalContext` "jarvisd named this worker Nova"; then a `[jarvisd]` notice | Decision 2, Task 4 |
| P5 | Two background workers running; the gate denies every call carrying the first one's `agent_id` | The first can do nothing more and the second is untouched. Recorded: how long the refused worker keeps going before it ends on its own | Decision 3, Task 5 |
| P6 | Ending one background worker: a stream-json control request if one exists; else the notice `[jarvisd] Febriel stopped Nova (task <id>). End that agent and say nothing.` | The worker ends within 10 s, the other keeps working, the front door says nothing or one short line. Recorded: which way works | Task 5 |
| P7 | `evaluateJavaScript` against `callAsyncJavaScript` with arguments for pushing a payload holding quotes, `</script>`, U+2028 and an emoji | The page receives the exact string | Task 10 |
| P8 | 👤 Six child panels changing frame together in one animation group of 0.45 s with the timing curve (0.25, 1.25, 0.4, 1), their thread paths animating beside them, while the circle is wild | Smooth to the eye, the overshoot is visible, threads stay attached to their beads, no frame where a bead and its thread part. If not: a 60-a-second timer with a spring, running only while something moves | Task 10 |

- [x] **Step 4: Write "Plan 4 probes" into `docs/spikes/findings.md`**, and the amendments table here where a bar was missed. If P1 ends over budget after its fallbacks, or P3 ends without usable glass, stop and bring it to Febriel before Task 9.

- [x] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock spikes/10-face docs/spikes/findings.md docs/superpowers/plans/2026-11-17-jarvis-plan-4-on-screen.md
git commit -m "chore: PyObjC for the face, and the Plan 4 probes"
```

---

### Task 2: Names, and talking about an agent by name

**Files:**
- Modify: `jarvis/config.py`, `jarvis/daemon/instant.py`
- Create: `jarvis/daemon/names.py`
- Test: `tests/daemon/test_names.py`, `tests/daemon/test_instant.py` (add)

**Interfaces:**
- Produces:

```python
NAMES: tuple[str, ...]                                   # names.py: at least 60, capitalised
def pick(in_use: Collection[str], rng: random.Random = random) -> str
def match(heard: str, running: Collection[str]) -> str | None     # the running name this word means, or None

NamedAction = Literal["stop", "yes", "no", "always"]     # instant.py
def match_named(utterance: str, running: Collection[str]) -> tuple[NamedAction, str] | None
```

- [x] **Step 1: Write the failing tests**

```python
def test_the_list_is_long_and_its_names_cannot_be_confused():
    assert len(NAMES) >= 60 and len(set(NAMES)) == len(NAMES)
    assert {"Nova", "Orin", "Vesper", "Kite", "Lumen"} <= set(NAMES)             # the mockup's names
    for a, b in itertools.combinations(NAMES, 2):
        assert difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() < 0.7, (a, b)
    for n in NAMES:
        assert n.isalpha() and 4 <= len(n) <= 6 and not wake.sounds_like_name(n)  # none can wake Jarvis
        assert n.lower() not in {"yes", "no", "stop", "always", "cancel", "mute", "status"}

def test_pick_avoids_names_in_use():
    assert pick(set(NAMES) - {"Kite"}) == "Kite"
def test_pick_when_every_name_is_taken_adds_a_number():    # 61st agent: "Nova 2", never an exception
    assert pick(set(NAMES), random.Random(0)).split()[-1] == "2"

def test_match_is_loose_but_only_among_the_running():
    assert match("nova", ["Nova", "Orin"]) == "Nova" and match("NOVA", ["Nova"]) == "Nova"
    assert match("novah", ["Nova", "Orin"]) == "Nova"     # mis-heard (0.89)
    assert match("never", ["Nova", "Orin"]) is None       # too far (0.44)
    assert match("vesper", ["Nova", "Orin"]) is None      # a real name, but not running
    assert match("nova", []) is None

def test_match_refuses_to_choose_between_two_close_names():   # Review Focus 2
    assert match("nora", ["Nova", "Nori"]) is None

def test_named_phrases():
    run = ["Nova", "Orin"]
    assert match_named("Jarvis, stop Nova.", run) == ("stop", "Nova")
    assert match_named("yes to Orin", run) == ("yes", "Orin") and match_named("no to nova", run) == ("no", "Nova")
    assert match_named("yes always to Nova", run) == ("always", "Nova")
    assert match_named("stop", run) is None and match_named("stop the music", run) is None
    assert match_named("stop Vesper", run) is None        # not running: an ordinary request for the front door
    assert match_named("tell Nova to stop", run) is None  # only the four exact shapes
```

- [x] **Step 2: Run** `uv run pytest tests/daemon/test_names.py tests/daemon/test_instant.py -q` → the new ones fail.
- [x] **Step 3: Implement.** `match`: the running name with the highest `difflib` ratio to the heard word, if it is ≥ `NAME_SIMILARITY` and at least 0.1 above the next best. `match_named` normalises the utterance as `instant.match` does (lower case, punctuation dropped, a leading "hey jarvis", "jarvis" or "please" dropped) and accepts only `stop <word>`, `yes to <word>`, `no to <word>`, `yes always to <word>`.
- [x] **Step 4: Run** → pass. **Step 5: Commit** `git commit -m "feat: agents get names, and a name can be stopped or answered"`

---

### Task 3: Agent rows that a card can be drawn from

**Files:**
- Modify: `jarvis/brain/asks.py`, `jarvis/daemon/core.py`, `jarvis/tui/model.py`
- Test: `tests/brain/test_asks.py`, `tests/daemon/test_core_rows.py`, `tests/tui/test_model.py` (add)
- Test helpers, added to `tests/daemon/events.py` and used through Task 5: `rows(j)` = `{r["id"]: r for r in j._agent_rows()}`; `call_from(agent_id, tool, tool_input)` = a `PreToolUse` payload from that worker in session `fake-session`; `agent_call(subagent_type, tool_use_id, description, prompt)` = the front door's `PreToolUse` payload for an `Agent` dispatch

**Interfaces:**
- Consumes: `names.pick` (Task 2).
- Produces: `Ask.agent_id: str` (`""` for the front door) and `Asks.ask(decision, channel, request_id, agent_id="")`; every item of the `agents` event (and of the snapshot's `agents`) is

```python
{"id": str,            # the task id; "jarvis" for the front door
 "name": str,          # the role: "coder", "researcher", "jarvis", "triage", …
 "call": str,          # the given name: "Nova"; "Jarvis" for the front door; "" for triage and scribe
 "model": str, "doing": str, "since": float, "background": bool,
 "title": str,         # the job: the verdict's title once known, else the dispatch's description
 "state": "working" | "needs_you" | "done" | "stopped" | "failed" | "idle",   # "idle" is the front door's
 "question": str | None, "ask_id": str | None,
 "ask_until": float | None,        # when the open question becomes a no (asked + ASK_TIMEOUT[channel]); None with no question
 "channel": "mac" | "phone"}       # of the request it works for
```

A row whose agent ended keeps its final state for `CARD_LINGER_SECONDS`, then `tick()` drops it and publishes. `agent_done` with status `completed` is `done`; any other status is `failed`.

- [x] **Step 1: Write the failing tests**

```python
async def test_a_workers_row_has_what_a_card_needs(jarvis, bridge):
    # a task with a verdict (GOOD_VERDICT) and a background coder started with tool_use_id "tu9"
    row = rows(jarvis)["t1"]
    assert row["name"] == "coder" and row["call"] in NAMES and row["title"] == "Fix export bug"
    assert row["state"] == "working" and row["question"] is None and row["channel"] == "mac"

async def test_two_workers_never_share_a_name()
async def test_the_question_sits_on_the_agent_that_asked(jarvis, bridge, tmp_path):
    # hook payload from agent_id "t1" needing a yes → rows["t1"]["state"] == "needs_you", question and ask_id set;
    # ask_until == the time asked + ASK_TIMEOUT["mac"]; the other worker's row unchanged;
    # after answer("yes", ask_id=…) → "working", question None, ask_until None
async def test_jarvis_own_question_sits_on_the_jarvis_row()   # no agent_id → rows["jarvis"] needs_you; call == "Jarvis"
async def test_an_ended_row_lingers_eight_seconds(jarvis, bridge, clock):
    # agent_done completed → state "done"; clock.advance(7.9); tick → still listed; advance(0.1); tick → gone, one agents event
async def test_a_failed_worker_says_failed()                  # agent_done status "failed" → "failed"
async def test_triage_and_scribe_have_no_name()               # call == ""
async def test_a_phone_request_marks_its_rows()               # channel == "phone"

def test_the_terminal_hud_still_reads_the_richer_rows():      # tui/model.py: a snapshot with the new fields reduces
    # without error, AgentRow has call/title/state, and an unknown extra key is ignored
```

- [x] **Step 2: Run** → fail. **Step 3: Implement.** `Jarvis.hook` passes `payload.get("agent_id") or ""` to `asks.ask`. The name is picked here at `agent_start` for now (Task 4 moves the choice earlier). `tui/model.py`: `AgentRow` gains `call`, `title`, `state` with defaults, and `_agents` drops keys `AgentRow` does not have.
- [x] **Step 4: Run** `uv run pytest -q` → all pass. **Step 5: Commit** `git commit -m "feat: agent rows carry a name, a job, a state and their question"`

---

### Task 4: The name is known from the dispatch on

**Files:**
- Modify: `jarvis/daemon/core.py`, `jarvis/brain/hook.py`, `jarvis/daemon/exchange.py`, `jarvis/memory/vault.py`, `.claude/agents/jarvis.md`
- Test: `tests/daemon/test_core_rows.py`, `tests/brain/test_hook.py`, `tests/daemon/test_exchange.py`, `tests/memory/test_vault.py` (add)

**Interfaces:**
- Consumes: the rows of Task 3.
- Produces: `Jarvis.hook` may return `{"verdict": "allow", "reason": str, "input": dict}`; `hook.render(event, verdict, reason, input=None)` adds `"updatedInput": input` to a `PreToolUse` allow; `Tracker.named(tool_use_id: str, call: str) -> None`; the task note's agent lines read `- Nova · coder (opus)`.

- [x] **Step 1: Write the failing tests**

```python
async def test_the_name_is_chosen_when_the_dispatch_is_allowed(jarvis, bridge):
    out = await jarvis.hook(agent_call("coder", tool_use_id="tu9", description="Fix export bug", prompt="Do it."))
    name = out["input"]["description"].split(":")[0]
    assert name in NAMES and out["input"]["description"] == f"{name}: Fix export bug"
    assert out["input"]["prompt"].startswith(f"Your name is {name}.\n\n") and out["input"]["subagent_type"] == "coder"
    bridge.emit(agent_start("t1", "coder", background=True, tool_use_id="tu9"))
    assert rows(jarvis)["t1"]["call"] == name and rows(jarvis)["t1"]["title"] == "Fix export bug"   # no name twice

async def test_triage_and_a_refused_dispatch_get_no_name()     # triage: no "input"; a denied worker: no name is used up
async def test_a_worker_the_hook_never_saw_still_gets_a_name() # agent_start with an unknown tool_use_id → a picked name

def test_an_allow_can_carry_an_edited_input():
    out = hook.render("PreToolUse", "allow", "ok", {"description": "Nova: x"})
    assert out["hookSpecificOutput"]["updatedInput"] == {"description": "Nova: x"}
    assert "updatedInput" not in hook.render("PreToolUse", "deny", "no", {"description": "x"})["hookSpecificOutput"]
    assert "updatedInput" not in hook.render("PreToolUse", "allow", "ok")["hookSpecificOutput"]

def test_the_task_note_names_its_agents(vault):                # "- Nova · coder (opus)"; jarvis stays "- jarvis (sonnet)"
async def test_a_question_is_announced_with_the_name(make, bridge_of):
    # FakeSpeaker: a worker's question on mac → ("say", "Nova has a question. Run git push to origin main. Yes or no?")
    # Jarvis's own question keeps today's wording, with no name in front
async def test_several_open_questions_are_named_not_counted():
    # two open on mac, then a bare "yes" → "Nova and Orin each have a question. Say yes or no to one by name, or
    # answer on its card."  Three: "Nova, Orin and Kite each have a question. …"
```

- [x] **Step 2: Run** → fail.
- [x] **Step 3: Implement.** The hook client reads an optional `input` from `jarvisd`'s reply and fails closed as before if it is not a dict. The edited input is the original with only `description` and `prompt` changed. Replace the sentence "… questions are waiting, so I won't guess which one you mean. Answer each in the HUD." with the named one above.
- [x] **Step 4: `jarvis.md`**, under "Everything else: triage first", one line: `jarvisd gives each worker a name and puts it first in the dispatch's description ("Nova: Fix export bug"). Call the worker by that name when you tell Febriel about it.` The part above the marker stays within 60 lines.
- [x] **Step 5: If P4 found the edited input is ignored**, build what P4 found instead, in this order, and keep every test above except the two about `updatedInput`: a `PostToolUse` hook entry for `Agent` whose reply adds the context "jarvisd named this worker Nova."; else a `[jarvisd]` notice queued like a request with no reply shown or spoken; else nothing reaches the model and `jarvisd` puts "Nova: " in front of a worker's announcement itself (§7.4's fallback).
- [x] **Step 6: Run** `uv run pytest -q` → pass. **Step 7: Commit** `git commit -m "feat: a worker is named at dispatch, and Jarvis and the notes use the name"`

---

### Task 5: Stop one agent, and answer one by name

**Files:**
- Modify: `jarvis/daemon/core.py`, `jarvis/remote/api.py`
- Test: `tests/daemon/test_core_stop.py`, `tests/remote/test_api.py` (add)

**Interfaces:**
- Consumes: `instant.match_named` (Task 2), the rows (Task 3).
- Produces:

```python
async def stop_agent(self, agent_id: str) -> bool        # Jarvis: False if no such running worker
POST /stop  {"agent": "<id>"}  →  {"stopped": true | false}     # 400 without a string id; token and Host as every route
```

What stopping does, in order: the agent's id joins the stopped set, so `hook` denies every call carrying it with "Febriel stopped this agent."; a question that agent has open is answered no; its row's state becomes `stopped` (and lingers); it is ended the way P6 found (default: the notice, queued behind a running turn, its reply neither shown, spoken nor logged as a request); its request is recorded with "(stopped by Febriel)"; when its result still arrives, the front door's announcement of it is neither spoken nor shown.

In `submit`, before the fixed phrases: `match_named(text, running)` where `running` is the given names of working rows, plus "Jarvis" while Jarvis's own question is open.

| Said | Does | Says |
|---|---|---|
| "stop Nova" | `stop_agent` | "Stopped Nova." |
| "yes / no / yes always to Nova" with a question open | answers that question by its id | The turn's reply, as a bare yes does today; "Okay." when no turn follows |
| the same with none open | nothing | "Nova has no question open." |

Each is written to the day's log like the other instant answers.

- [x] **Step 1: Write the failing tests**

```python
async def test_a_stopped_agent_can_do_nothing_more(jarvis, bridge):               # Review Focus 3
    # two background workers t1 (Nova) and t2; await jarvis.stop_agent("t1")
    assert (await jarvis.hook(call_from("t1", "Bash", {"command": "ls"})))["verdict"] == "deny"
    assert (await jarvis.hook(call_from("t2", "Bash", {"command": "ls"})))["verdict"] == "allow"
    assert rows(jarvis)["t1"]["state"] == "stopped" and rows(jarvis)["t2"]["state"] == "working"

async def test_stopping_answers_its_open_question_no()        # the held hook call returns deny; the ask is gone
async def test_the_stop_notice_is_sent_and_never_shown(jarvis, bridge, vault):
    # bridge.sent ends with a "[jarvisd] Febriel stopped Nova (task t1)…" line; no "heard" event; the reply to it is not
    # published and not spoken; the day log has no line for it
async def test_the_notice_waits_for_a_running_turn()          # a turn in flight: the notice is sent only after it ends
async def test_a_stopped_agents_result_is_not_announced(make, bridge_of, vault):
    # FakeSpeaker; agent_done for t1 after the stop, then the front door's own turn "The export bug is fixed."
    # → no ("say", …), no ("feed", …), no reply event; the task note exists and holds "(stopped by Febriel)"
async def test_stop_by_voice_names_it_and_says_so()           # submit("Jarvis, stop Nova") → "Stopped Nova."; in the day log
async def test_yes_to_a_name_answers_that_question_only():    # Review Focus 2
    # Nova and Orin both asking; submit("yes to Orin") → Orin's hook call allowed, Nova's still held
async def test_a_name_with_no_question_says_so()              # "yes to Nova" → "Nova has no question open."
async def test_yes_to_jarvis_answers_jarvis_own_question()
async def test_plain_stop_still_cancels_everything()          # submit("stop") → bridge.restarted or interrupted, as today
async def test_stopping_twice_or_an_unknown_id_is_false()
async def test_a_second_answer_to_the_same_question_changes_nothing()   # card and voice race: the second returns False

async def test_stop_route(client):                            # 200 {"stopped": true}; unknown id → {"stopped": false};
                                                              # {"agent": 5} → 400; no token → 401
```

- [x] **Step 2: Run** → fail. **Step 3: Implement.** If P5 showed the gate cannot tell one worker's calls from another's, do not build one-click stop: `stop_agent` returns False for every id, `POST /stop` accepts `{"all": true}` and calls `cancel()`, and Task 7's cards say "This stops all N running agents" and need a second click (§7.6). Record that in the amendments table.
- [x] **Step 4: Run** `uv run pytest -q` → pass. **Step 5: Commit** `git commit -m "feat: one agent can be stopped, and answered by name"`

---

### Task 6: How loud Jarvis is speaking

**Files:**
- Modify: `jarvis/voice/audio.py`, `jarvis/voice/speaker.py`, `jarvis/daemon/core.py`
- Test: `tests/voice/test_audio.py`, `tests/daemon/test_core_voice.py` (add)

**Interfaces:**
- Consumes: Plan 3's `Player`, `VoiceSpeaker`, `Jarvis.level`.
- Produces: `Player.on_level: Callable[[float], None]` (default does nothing; called on the audio thread about every 90 ms while sound goes out, with the RMS of that stretch, 0–1); `Speaker.on_level`, set by the core; `Jarvis.level(rms: float, source: Literal["mic", "voice"] = "mic")`; the `level` event gains `"source"`.

- [x] **Step 1: Write the failing tests**

```python
def test_the_player_reports_the_loudness_of_what_it_plays()   # a full-scale square wave → levels near 1.0; silence → 0.0;
                                                              # none after the queue drains
def test_no_level_is_reported_after_stop()
async def test_speech_levels_reach_subscribers_marked_voice() # speaker.on_level(0.6) → {"type": "level", "rms": 0.6, "source": "voice"}
async def test_mic_levels_are_marked_mic()                    # level(0.4) → source "mic"
```

- [x] **Step 2: Run** → fail. **Step 3: Implement.** **Step 4: Run** → pass. **Step 5: Commit** `git commit -m "feat: jarvisd reports how loud its own speech is"`

---

### Task 7: The face's model

**Files:**
- Create: `jarvis/remote/client.py` (the `Client` class moved from `jarvis/tui/app.py`, which re-exports it), `jarvis/face/model.py`
- Modify: `jarvis/tui/app.py`
- Test: `tests/face/test_model.py`, `tests/tui/test_app.py` (add); event builders `link`, `health`, `state`, `level`, `agents`, `worker`, `hover` in `tests/face/events.py`; a `FakeClient` like the terminal HUD's, with `stops` beside `answers`

**Interfaces:**
- Consumes: the rows (Task 3, with `ask_until`), the `state`, `level` and `health` events, the `link` events `Client.events()` already emits, and one event of the face's own: `{"type": "hover", "agent": str, "on": bool}`.
- Produces: `Client.stop(agent_id: str) -> dict | None`, and

```python
@dataclass(frozen=True)
class Card:                           # shown as a bead
    id: str; name: str; role: str; model: str; title: str; doing: str; elapsed: str
    state: str; question: str | None; ask_id: str | None; stop: bool      # stop: show the Stop button
    open: bool                        # False: one line
    left: float | None                # 0–1 of the question's wait still to run; None with no question
    left_text: str                    # "No in 42 s", "No in 9 min"; "" with no question

@dataclass(frozen=True)
class Stack:                          # shown as the plume
    cards: tuple[Card, ...]           # at most CARD_MAX; the first is nearest the circle
    more_working: int; more_asking: int

@dataclass(frozen=True)
class Circle:
    mode: Literal["idle", "listen", "work", "talk", "muted", "off"]
    ring: bool                        # a question is open
    word: str                         # "", or "OFFLINE", "LIMIT", "NO DAEMON"
    level: float                      # 0–1: the mic's while listening, the voice's while talking, else 0

class FaceView: ...                   # frozen; FaceView.empty(); holds the rows and the ids hovered now
def reduce(view: FaceView, event: dict) -> FaceView
def circle(view: FaceView) -> Circle
def stack(view: FaceView, now: float) -> Stack
def more_text(s: Stack) -> str        # "", "+2 more working", "+1 more needs you", "+2 more need you · +2 more working"
def new_alerts(before: FaceView, after: FaceView) -> bool     # a question on the mac channel opened
```

Circle mode, first match wins: `off` (no daemon → `NO DAEMON`; brain `offline` or `down` → `OFFLINE`; brain `limit` → `LIMIT`); `talk` (voice `SPEAKING`); `listen` (`LISTENING`); `work` (`THINKING`, or any worker row `working` or `needs_you`); `muted`; `idle`.

Card order: `needs_you` cards, oldest question first; then `working`, newest first; then ended ones, newest first. The first `CARD_MAX` show; the rest are counted, `more_asking` for hidden ones with a question, `more_working` for hidden working ones. A card with a question is never hidden while one without is shown. The `Jarvis` row is a card only while its state is `needs_you`; its `stop` is true and means "no". Ended cards have `stop` false.

Open (tether design §4): a card with a question is open; a working card is open while its id is hovered or `now - since < CARD_POP_SECONDS`; an ended card is never open. Counting the pop from `since` means a restarted face does not pop every bead again.

The countdown: `left = clamp((ask_until - now) / ASK_TIMEOUT[channel], 0, 1)`. `left_text` is `No in <n> s` while under a minute remains (seconds rounded up), else `No in <n> min` (minutes rounded up).

A hover for an id that has no row is dropped, and a row that leaves takes its hover with it.

- [x] **Step 1: Write the failing tests**

```python
def test_only_workers_are_cards()                 # rows: jarvis idle, triage, scribe, coder, researcher → 2 cards
def test_a_card_shows_its_agent()                 # Card("t1", "Nova", "coder", "opus", "Fix export bug", "Running tests", "04:12", "working", None, None, True, False, None, "")
def test_jarvis_is_a_card_only_while_it_asks()
def test_questions_first_then_newest_working_then_ended()
def test_five_show_and_the_rest_are_counted():    # Review Focus 5
    # 7 working rows, the two oldest asking → cards[0:2] are the two asking; len(cards) == 5; more_working == 2; more_asking == 0
def test_a_sixth_question_is_counted_as_asking()  # 6 asking → 5 cards, more_asking == 1
def test_elapsed_counts_from_since()              # since 1000, now 1252 → "04:12"

def test_a_new_card_is_open_for_four_seconds_then_one_line()    # since 1000: now 1003.9 → open; now 1004.0 → not
def test_hover_opens_a_working_card_and_leaving_closes_it()
def test_a_question_is_open_however_old_and_unhovered()
def test_an_ended_card_is_one_line_even_hovered()
def test_hover_for_a_card_that_is_gone_is_forgotten()            # hover t9; t9's row leaves; it comes back as a new t9 → not open
def test_the_countdown_follows_ask_until():
    # mac, ask_until now+42 → left 0.7, "No in 42 s"; phone, now+540 → 0.9, "No in 9 min"; already past → 0.0, "No in 0 s"
@pytest.mark.parametrize("working, asking, text", [(0, 0, ""), (2, 0, "+2 more working"), (0, 1, "+1 more needs you"),
                                                   (2, 2, "+2 more need you · +2 more working")])
def test_the_more_line(working, asking, text)

@pytest.mark.parametrize("events, mode, word", [
    ([link("no daemon")], "off", "NO DAEMON"), ([health(brain="offline")], "off", "OFFLINE"),
    ([health(brain="limit")], "off", "LIMIT"), ([state("SPEAKING")], "talk", ""), ([state("LISTENING")], "listen", ""),
    ([state("THINKING")], "work", ""), ([agents(worker("working"))], "work", ""),
    ([state("IDLE", muted=True)], "muted", ""), ([], "idle", "")])
def test_circle_mode(events, mode, word)
def test_talking_beats_working_and_off_beats_everything()
def test_the_ring_is_on_while_any_question_is_open()
def test_level_follows_the_right_source()         # listen: the last mic level; talk: the last voice level; work: 0.0

def test_a_lost_daemon_clears_every_card()        # Review Focus 4: cards showing, then link "no daemon" → Stack((), 0, 0)
def test_a_snapshot_replaces_what_was_shown()     # reconnect: the snapshot's rows are the only rows
def test_unknown_or_missing_fields_do_not_break_it()   # a row without "call" or "ask_until", or with an extra key; an unknown event type
def test_a_new_mac_question_alerts_once_and_a_phone_one_never()
```

- [x] **Step 2: Run** → fail. **Step 3: Implement** (`reduce` in the style of `jarvis/tui/model.py`; `Client` moves unchanged plus `stop`). **Step 4: Run** `uv run pytest -q` → pass.
- [x] **Step 5: Commit** `git commit -m "feat: the face's model: what the circle does and which five beads show"`

---

### Task 8: The controller and the circle's place

**Files:**
- Create: `jarvis/face/controller.py`, `jarvis/face/place.py`
- Test: `tests/face/test_controller.py`, `tests/face/test_place.py`

**Interfaces:**
- Consumes: `Client`, the model (Task 7).
- Produces:

```python
def load(home: Path) -> tuple[float, float] | None       # place.py: from <home>/face.json; None if absent or unreadable
def save(home: Path, x: float, y: float) -> None
def on_screen(x, y, size, screen_w, screen_h) -> tuple[float, float]    # pulled back inside the screen
def default(size, screen_w, screen_h) -> tuple[float, float]            # bottom-right, 40 points in from each edge

class Controller:
    def __init__(self, client, show_circle: Callable[[str], None], show_stack: Callable[[Stack, str], None],
                 play: Callable[[], None], home: Path, now: Callable[[], float] = time.time): ...
    async def run(self) -> None              # consumes client.events() until cancelled
    async def answer(self, reply: str, ask_id: str) -> None     # from a bead's button
    async def stop(self, agent: str) -> None                    # from a bead's Stop
    def hover(self, agent: str, on: bool) -> None               # the pointer entered or left a bead
    async def on_message(self, msg: object) -> None             # from the circle's page
    def tick(self) -> None                   # once a second: elapsed times and countdowns move, a pop ends
```

`show_circle` receives one JSON string, the circle alone (`{"mode": …, "ring": …, "word": …, "level": …}`), made with `json.dumps(..., ensure_ascii=True)`, only when it differs from the last one sent, except levels: a changed `level` alone is sent at most `FACE_FPS` times a second. `show_stack` receives the `Stack` and its `more_text`, only when either differs from the last sent. `play` is called when `new_alerts` is true. The controller never imports AppKit.

What it accepts, and nothing else:

| From | Call | Does |
|---|---|---|
| a bead | `answer(reply, ask_id)` | `client.answer(reply, ask_id)` if `reply` is `yes`, `no` or `always` and that `ask_id` is on a card now |
| a bead | `stop(agent)` | `client.stop(agent)` if that agent has a card now whose `stop` is true; for the `Jarvis` card, `client.answer("no", its ask_id)` |
| a bead | `hover(agent, on)` | reduces a `hover` event; an id with no card is dropped |
| the page | `{"type": "moved", "x": number, "y": number}` | `place.save` |

- [x] **Step 1: Write the failing tests**

```python
async def test_events_become_a_circle_and_a_stack(ctl, fake)  # a snapshot → show_circle once, show_stack once
async def test_an_unchanged_view_is_not_shown_again()
async def test_levels_are_capped_at_the_frame_rate()         # 100 level events in 1 s → at most FACE_FPS show_circle calls, no show_stack
async def test_the_timer_moves_once_a_second()               # tick with a working card → show_stack; with no cards → none
async def test_a_pop_ends_on_a_tick()                        # a card 3.5 s old is open; clock +1; tick → shown again, not open
async def test_hover_opens_and_shows()                       # hover("t1", True) → show_stack with cards[0].open
async def test_a_new_question_plays_the_sound_once()
async def test_hostile_text_reaches_the_bead_unchanged(ctl, fake):    # Review Focus 1
    fake.push(agents(worker("working", doing='");alert(1)//</script><img src=x onerror=y>')))
    assert stacks[-1].cards[0].doing == '");alert(1)//</script><img src=x onerror=y>'
async def test_the_circle_payload_is_plain_ascii_json()      # a word or mode never carries agent text; shown[-1].isascii()

async def test_answer_goes_to_the_question_on_the_card()     # → fake.answers == [("yes", "k1")]
async def test_stop_goes_to_the_agent_on_the_card()          # → fake.stops == ["t1"]
async def test_stop_on_the_jarvis_card_answers_no()
async def test_a_stale_click_does_nothing():                 # Review Focus 4: an ask_id or agent no longer on a card
async def test_a_reply_that_is_not_yes_no_always_is_dropped()   # answer("maybe", "k1") → no call
async def test_anything_but_moved_from_the_page_is_dropped() # None, "x", {"type": "eval"}, {"type": "answer", …}, {"type": "stop", …},
                                                             # {"type": "moved", "x": "1"} → no call, no exception
async def test_moved_saves_the_place(tmp_path)

def test_place_round_trips_and_survives_a_broken_file(tmp_path)   # save then load; garbage in face.json → None
def test_a_place_off_screen_is_pulled_back()                 # (5000, -30) on 1440×900 → inside
```

- [x] **Step 2: Run** → fail. **Step 3: Implement.** **Step 4: Run** → pass.
- [x] **Step 5: Commit** `git commit -m "feat: the face's controller, and the circle remembers where it sits"`

---

### Task 9: The circle's page

**Files:**
- Create: `jarvis/face/page/circle.html`, `face.css`, `circle.js`
- Modify: `pyproject.toml` (the page files ship in the package)
- Test: `tests/face/test_page.py`

**Interfaces:**
- Consumes: the circle payload of Task 8.
- Produces: `window.face.show(payload)` (an object, already parsed) and `window.face.pause(on)`; one message, `window.webkit.messageHandlers.face.postMessage({type: "moved", x, y})`.

- [x] **Step 1: Write the failing tests** (they read the files; nothing is rendered)

```python
def test_the_page_has_the_policy_and_loads_only_its_own_files():
    html = (PAGE / "circle.html").read_text()
    assert "default-src 'none'; script-src 'self'; style-src 'self'" in html
    assert "http://" not in html and "https://" not in html and "<script>" not in html   # no inline script

def test_the_page_script_cannot_turn_text_into_markup_or_reach_out():   # Review Focus 1
    src = (PAGE / "circle.js").read_text()
    for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "Function(",
                   "fetch(", "XMLHttpRequest", "WebSocket", "localStorage", "http://", "https://"):
        assert banned not in src, banned

def test_the_page_draws_no_cards():                         # the beads are native: no card markup, one message type
    assert sorted(p.name for p in PAGE.iterdir() if p.suffix in (".html", ".js", ".css")) == ["circle.html", "circle.js", "face.css"]
    src = (PAGE / "circle.js").read_text()
    assert '"answer"' not in src and '"stop"' not in src and "'answer'" not in src and "'stop'" not in src

def test_the_colours_are_the_three_reds_and_no_gold():
    css = (PAGE / "face.css").read_text().upper() + (PAGE / "circle.js").read_text().upper()
    assert all(c in css for c in ("#FF3B30", "#C2241B", "#6B1512")) and "#D4AF37" not in css and "#FFD700" not in css

def test_the_page_files_ship_with_the_package()             # importlib.resources.files("jarvis.face") / "page" has all three
```

- [x] **Step 2: Run** → fail.
- [x] **Step 3: Write the page**, taking the circle and its animation from the 2026-11-17 mockup file. About 150 points, lines between near ones, four jagged rings, exactly as the mockup's script draws them, with its `energy` per mode (`idle` 0.12, `listen` 0.45, `work` 1.0, `talk` 0.85, `muted` and `off` 0 with no motion), `amp` taken from `level`. A change of mode eases in over `FACE_EASE_SECONDS` and never jumps (§7.2): energy moves toward its target a little each frame; every speed that depends on energy advances its own phase per frame (the mockup's `rot`, `wob`, `spin`), never `clock × speed`; loudness fades in through a gain. A pulsing outer ring when `ring` is true, grey instead of red and the word underneath when `mode` is `off`. It draws at `FACE_FPS` (10 a second in `idle` if Task 1 said so), stops while `pause(true)`, and honours `prefers-reduced-motion`. The word is set with `textContent`. Dragging the circle posts `moved` on release.
- [x] **Step 4: Run** → pass. **Step 5: Commit** `git commit -m "feat: the face's page: the circle"`

---

### Task 9A: The plume and the marks

Where every bead sits and what every mark looks like, as plain arithmetic (tether design §4 "The mark", §5, §6).

**Files:**
- Create: `jarvis/face/tether.py`, `jarvis/face/mark.py`
- Test: `tests/face/test_tether.py`, `tests/face/test_mark.py`

**Interfaces:**
- Consumes: the `TETHER_*` and `CARD_*` constants; `names.NAMES` (Task 2) in the tests.
- Produces:

```python
# tether.py: screen points, origin bottom-left, as AppKit has it
@dataclass(frozen=True)
class Rect: x: float; y: float; w: float; h: float

@dataclass(frozen=True)
class Plume:
    frames: tuple[Rect, ...]                    # one per size given, same order: the first is nearest the circle
    anchors: tuple[tuple[float, float], ...]    # the centre of each bead's mark, where its thread starts
    side: Literal["left", "right"]              # which side of the circle the beads are on
    grow: Literal["up", "down"]
    field: Rect                                 # covers the circle and every frame plus 24 points: the thread panel's frame

def plume(centre: tuple[float, float], screen: Rect, sizes: Sequence[tuple[float, float]]) -> Plume
def thread(anchor: tuple[float, float], centre: tuple[float, float], sway: float = 0.0) -> tuple[P, P, P]
    # a quadratic curve: start 13 points from the anchor toward the circle, control, end on the rim (TETHER_RIM from the centre)

# mark.py
@dataclass(frozen=True)
class Mark: petals: int; depth: float; offsets: tuple[float, float, float]; way: int    # petals 3–7; way +1 or -1, the turning direction
def mark(name: str) -> Mark                                  # from zlib.crc32(name.encode()): the same on every run and machine
def curve(m: Mark, layer: int, n: int = 72) -> tuple[tuple[float, float], ...]    # layer 0–2; closed; inside the unit circle
```

The plume, with the circle in the lower right (the other three cases are its mirror images): the first bead's lower edge is 22 points below the circle's centre; each next bead sits `CARD_GAP` above the one before. A bead whose height overlaps the ring `TETHER_CLEAR` from the centre has its right edge 6 points left of where that ring is widest across the bead's height. A bead wholly above that ring has its right edge 28 points left of the centre line, and each further one `TETHER_STEP` further right, never past 16 points from the screen edge. `side` is `left` when the centre is in the right half of the screen; `grow` is `up` when it is in the lower half. The anchor is 18 points in from the bead's circle-side edge and 18 points below its top. The last size may be the "+2 more" chip; the caller draws no thread for it.

`curve` is the rose `r = (1 - depth) + depth * cos(petals * θ + offsets[layer])` with `depth` between 0.30 and 0.50, so `r` stays between 0 and 1.

- [x] **Step 1: Write the failing tests**

```python
CORNERS = [(1300, 120), (140, 120), (1300, 780), (140, 780), (720, 450)]     # on a 1440×900 screen
STACKS = [[(190, 36)], [(300, 150), (190, 36), (210, 36)], [(190, 36)] * 5 + [(120, 24)], [(300, 150)] * 2 + [(190, 36)] * 3]

def test_the_first_bead_sits_beside_the_circle()             # lower right: its right edge ≤ cx - TETHER_CLEAR and its height spans cy
@pytest.mark.parametrize("centre", CORNERS)
@pytest.mark.parametrize("sizes", STACKS)
def test_beads_never_overlap_each_other_or_the_circle(centre, sizes)   # Review Focus 6: no two frames intersect; none within TETHER_RIM of the centre
def test_every_bead_is_on_the_screen(centre, sizes)          # Review Focus 6, same parameters
def test_no_thread_crosses_another_bead(centre, sizes)       # 20 points along each thread: none inside another bead's frame
def test_the_plume_grows_away_from_the_nearest_edges()       # (1300, 120) → left, up; (140, 780) → right, down
def test_the_anchor_is_the_marks_centre()                    # 18 in from the circle-side edge, 18 below the top, on both sides
def test_the_field_covers_the_circle_and_every_bead()
def test_no_beads_is_an_empty_plume()                        # frames == (); the field is the circle plus its margin
def test_a_thread_ends_on_the_rim_and_sways_only_its_control()

def test_a_name_always_gets_the_same_mark():
    assert mark("Nova") == mark("Nova") == Mark(...)        # the literal pinned once, so no per-run hash can creep in
def test_every_name_in_the_list_has_its_own_mark()           # len({mark(n) for n in NAMES}) == len(NAMES)
def test_a_curve_is_closed_and_inside_the_unit_circle()      # every name, every layer
```

- [x] **Step 2: Run** → fail. **Step 3: Implement.** If two names in the list share a mark, widen what the checksum feeds (more depth steps) until none do; do not change the list. **Step 4: Run** → pass.
- [x] **Step 5: Commit** `git commit -m "feat: where each bead hangs, and a mark for every name"`

---

### Task 10: The app, `jarvis face`, and its login agent

**Files:**
- Create: `jarvis/face/app.py`, `jarvis/face/beads.py`, `jarvis/face/threads.py`, `launchd/com.febriel.jarvis-face.plist`
- Modify: `jarvis/cli.py`, `launchd/README.md`
- Test: `tests/test_cli.py` (add), `tests/face/test_native_source.py`

**Interfaces:**
- Consumes: `Controller`, `place`, `tether`, `mark`, the page.
- Produces: `jarvis face`; `jarvis.face.app.run() -> None`.

- [x] **Step 1: Write the failing tests**

```python
def test_face_is_a_command(monkeypatch)                      # main(["face"]) calls jarvis.face.app.run once
def test_the_face_plist_runs_face_with_no_secrets():         # ProgramArguments end ["…/.venv/bin/jarvis", "face"]; RunAtLoad and
                                                             # KeepAlive true; LimitLoadToSessionType "Aqua"; no EnvironmentVariables
def test_importing_the_cli_or_the_daemon_never_loads_appkit()   # fresh interpreter: jarvis.cli, jarvis.daemon.core → no AppKit, WebKit
def test_the_faces_logic_loads_neither_appkit_nor_the_speech_stack()
    # jarvis.face.controller, model, tether, mark, place → no AppKit, WebKit, Quartz, mlx, sounddevice

NATIVE = (FACE / "beads.py").read_text() + (FACE / "threads.py").read_text()
def test_a_bead_never_builds_text_from_markup():             # Review Focus 1: a label shows characters, nothing else
    for banned in ("initWithHTML", "NSAttributedString", "setAttributedStringValue", "setAttributedTitle",
                   "WKWebView", "evaluateJavaScript", "setAllowsEditingTextAttributes_(True)"):
        assert banned not in NATIVE, banned
def test_a_bead_uses_the_systems_colours():                  # tether design §4: never a hex value or a made-up colour on a bead
    src = (FACE / "beads.py").read_text()
    assert not re.search(r"#[0-9A-Fa-f]{6}\b", src) and "colorWithRed" not in src and "colorWithSRGB" not in src and "RED" not in src
    assert all(c in src for c in ("systemRedColor", "labelColor", "secondaryLabelColor"))
```

- [x] **Step 2: Run** → fail.
- [x] **Step 3: Implement**, with what Task 1 measured. The app is an accessory (no Dock icon). Every panel is borderless, transparent, non-activating, at the floating level, on all Spaces and over full-screen apps, and can never become key or main.
  - **`app.py`: the shell.** The circle's panel, `CIRCLE_SIZE` square at `place.load` or `place.default`, holding a web view with a clear background, loaded with `loadFileURL` allowed to read only the `page` folder. The asyncio side (`Client`, `Controller.run`, the once-a-second `tick`) runs on its own thread; `show_circle`, `show_stack` and `play` hop to the main thread; button clicks, hover and the page's message hop to the asyncio thread. `show_circle` hands the payload to the page the way P7 found exact. `play` plays `/System/Library/Sounds/Glass.aiff`. The token is read with `load_token(config.HOME_DIR)` and stays on the Python side. On `moved`, on a screen change, and on every `show_stack`, it asks `tether.plume` for the frames (the circle's centre, the main screen's visible frame, each bead's fitting size, plus the chip's when `more_text` is not empty) and applies them. `pause(true)` goes to the page and every layer animation stops when the screens sleep or the session locks; they resume on wake.
  - **`beads.py`: one bead.** A panel exactly the bead's size, a child of the circle's panel so it follows a drag. Its content is an `NSGlassEffectView` with 18-point corners (or what P3 chose) holding native labels and buttons laid out as tether design §4, mirrored by `Plume.side`. Every string is set with `setStringValue_` or `setTitle_`. Fonts: the system font at 13 points, semibold for the name and the question; the timer and the countdown in the rounded design with fixed-width digits. Colours: `labelColor`, `secondaryLabelColor`, `systemRedColor`. Asking: the glass's tint is system red at 20 % and a 1.5-point red edge. Yes has a system-red bezel; No, Always and Stop are plain. Every view answers `acceptsFirstMouse_` with true, so one click acts while another app is in front. A tracking area (`mouseEnteredAndExited`, `activeAlways`) reports hover. Buttons carry accessibility labels ("Yes to Nova", "Stop Nova"). The mark is three shape layers from `mark.curve`, turning by layer animation at three speeds while working, slowly and breathing while asking, replaced by the `checkmark.circle` or `stop.circle` symbol in `secondaryLabelColor` when ended. The countdown line is a layer whose width moves to `left` over one second, linearly.
  - **`threads.py`: the threads.** One panel with `ignoresMouseEvents` true, a child of the circle's panel, framed to `Plume.field`. One shape layer per bead with a thread, its path from `tether.thread`, in `#FF3B30`, drawn as tether design §5: width and opacity by state, a slow sway as a repeating path animation between two `sway` values, the travelling dots as small layers animated along the path. Stopped or failed: `strokeEnd` runs to zero toward the circle in 0.25 s. No thread for the chip.
  - **Moving.** A new bead starts at the circle's centre, invisible. Every change of frames runs in one animation group of `FACE_MOVE_SECONDS` with the timing curve (0.25, 1.25, 0.4, 1); thread paths animate with the same duration and curve. A bead that leaves travels back to the centre, fades, and closes. If P8 found that jerky, drive the frames from a 60-a-second timer with a spring, only while something moves.
  - **Reduce Motion** (`accessibilityDisplayShouldReduceMotion`, and its change notice): frames change with a 0.2 s cross-fade, no sway, no dots, marks still. **Increase Contrast**: threads fully opaque.
- [x] **Step 4: `launchd/README.md`**: load and unload commands for the face agent, as for jarvisd; that it needs no permission; that it reconnects by itself when jarvisd restarts.
- [x] **Step 5: Run** `uv run pytest -q` → pass. **Step 6: Commit** `git commit -m "feat: jarvis face: the circle floats and the agents hang from it"`

---

### Task 11: The terminal HUD turns red and uses the names

**Files:**
- Modify: `jarvis/tui/jarvis.tcss`, `jarvis/tui/app.py`
- Test: `tests/tui/test_app.py` (add)

- [x] **Step 1: Write the failing tests**

```python
def test_the_theme_is_red_and_holds_no_gold():
    text = (TUI / "jarvis.tcss").read_text().upper() + (TUI / "app.py").read_text().upper()
    assert "#D4AF37" not in text and "#FFD700" not in text and "#8A7424" not in text
    assert all(c in text for c in ("#FF3B30", "#C2241B", "#6B1512"))

async def test_agents_show_their_given_names(hud, pilot, fake):
    # a coder row with call "Nova" → the AGENTS panel line starts "Nova"; triage (call "") still shows "triage"
async def test_still_fits_80_by_24(hud)
```

- [x] **Step 2: Run** → fail. **Step 3: Implement.** Text `RED`, active `RED_ACTIVE`, idle and borders `RED_DIM`, read from `config` in `app.py`. An AGENTS line is `<call or role> <role if named> <model> <doing>`.
- [x] **Step 4: Run** `uv run pytest -q` → pass. **Step 5: Commit** `git commit -m "feat: the terminal HUD is red and calls agents by name"`

---

### Task 12: End to end on the desktop, then the checkpoint 👤

**Files:**
- Modify: `docs/spikes/findings.md`, `docs/superpowers/specs/2026-11-10-jarvis-design.md`, `docs/superpowers/specs/2026-11-17-jarvis-screen-hud-design.md`, `PROJECT.md`, this plan (amendments)

- [x] **Step 1: Load the face agent** (`launchd/README.md`), restart jarvisd. The circle appears bottom-right.

- [x] **Step 2: 👤 Run the rows, record each in the findings.** A row that fails gets a failing test first where one can be written, then the fix, then the row again.

| # | Do | Pass when |
|---|---|---|
| 1 | Watch the circle idle; say "Jarvis" and a request; let it answer | Calm when idle; swells with his voice; wild while thinking; throbs with its own speech. Each change eases in over about two seconds with no lurch at its start. Febriel says it is the mockup. |
| 2 | Ask for a job that needs a worker | A bead buds out of the circle within half a second, open, with a name, the role, the model, the job and a moving timer, tied to the circle by a thread with a travelling dot. After about four seconds it shrinks to one line; the pointer over it opens it again. The circle stays wild while the agent runs. When it finishes, Jarvis says so using its name, the thread fades, and the bead sinks back into the circle after 8 s. |
| 3 | Make that worker need a yes (`git push` in a scratch repo) | Jarvis says "<Name> has a question" and the question; the sound plays once; the bead moves nearest the circle, open and tinted red; its thread burns bright; the red line counts down with "No in … s"; the ring pulses. |
| 4 | Click Yes on the bead; next time No; next time Always; next time leave it | Each does what the HUD's `y` / `n` / `a` do; the bead goes back to working; the ring stops. Left alone, the line runs out at 60 s and it counts as no. |
| 5 | Two workers asking at once; say "yes" | Jarvis names both and takes no guess. "Yes to <one>" answers that one only. |
| 6 | Click Stop on one of two running workers | That bead's thread snaps back into the circle at once; the bead says `stopped`, dimmed, and is gone after 8 s; the other keeps working; nothing is said; no result is announced for the stopped one later. |
| 7 | "Jarvis, stop <name>" | The same, and Jarvis says "Stopped <name>." |
| 8 | Something small that needs a yes with no worker (delete a scratch file) | A `Jarvis` bead with the question; Stop on it means no. |
| 9 | Start seven workers (a job split seven ways), one of the first asking | Five beads, the asking one nearest the circle, "+2 more working" at the far end of the plume. No bead covers another or the circle, and no thread runs through a bead. |
| 10 | Type in another app while beads come and go; move the pointer over one; click Yes on one; click beside a bead and between a bead and the circle; open a full-screen app; switch Spaces | Typing is never interrupted, not by the hover and not by the click; Yes acts on the first click; the clicks beside land on the app underneath; circle and beads are there everywhere. |
| 11 | With three beads showing, drag the circle to each corner of the screen and to the middle; restart the face | The beads and threads follow the drag; on release the plume re-forms away from the nearest edges with every bead on screen. After the restart the circle is where it was left and no bead pops open again. |
| 12 | `launchctl kickstart -k` jarvisd while two beads show | The beads and threads vanish, the circle goes grey with `NO DAEMON`, and all come back by themselves. |
| 13 | Kill the face while a worker asks | Jarvis still asks by voice; "yes" still works; the face comes back with the bead, its countdown where it should be. |
| 14 | Turn Wi-Fi off | Grey circle, `OFFLINE`. |
| 15 | Lock the Mac for a minute, unlock | The face used no CPU while locked and moves again. |
| 16 | Measure the face for two minutes each: idle, a worker running, a long spoken answer | The budgets in Global Constraints. |
| 17 | A worker whose doing-line or question holds `<b>bold</b>` and a quote (ask one to run `echo '<b>"hi"</b>'`) | Shown as those characters. |
| 18 | Open the terminal HUD | Red, no gold; AGENTS shows the names; a finished job's note in the vault names its agents. |
| 19 | Start a job from the phone route (`jarvis ask` with channel `phone` through the API) that needs a yes | Its bead has buttons and counts down in minutes; nothing is spoken and no sound plays on the Mac. |
| 20 | Switch macOS between light and dark; put a white document, a dark video and a busy wallpaper under the beads | The glass follows the mode by itself; every label is readable in each case; red is only on the mark, the question and Yes. |
| 21 | Turn on Reduce Motion, then Reduce Transparency, then Increase Contrast | Reduce Motion: beads cross-fade into place, threads do not sway, no dots travel, marks hold still. The other two: beads stay readable, threads go fully opaque. |
| 22 | Run the same agent name twice (two jobs a while apart) | Its mark is the same both times, and different from the other agents' marks. |
| 23 | Febriel looks at it beside the mockup's Tether | He says it is the one he chose. |

- [x] **Step 3: Amend the specs**, each change dated: in the main design, §7 points to the on-screen design and says red replaces gold; §8's tree gains `face/` and the second login agent; §15's lists gain `POST /stop`, the richer `agents` rows and `level`'s `source`; §6.2's instant table gains the name phrases. In the on-screen design: a note at its top that the tether design amends it, and what the probes settled (how the model learns a name, how one worker is ended, the frame rates and budgets as measured). In the tether design: its two open points (one panel per bead or one large panel; system glass or the fallback) as the probes settled them.
- [x] **Step 4: Update `PROJECT.md`** and copy this plan and its results to Obsidian (`Astro/Claude Code/Jarvis Plan 4 On Screen.md`, `Jarvis Plan 4 Results.md`), linked from `[[Jarvis On Screen Design]]` and `[[Jarvis Face Tether Design]]`. Write `DESIGN.md` from the built face (`/impeccable document`), as the tether design's contract asks.
- [x] **Step 5: One review pass over the whole branch**, the Review Focus list first. Findings go to Febriel before any fix.
- [x] **Step 6: Commit** `git commit -m "docs: Plan 4 results, spec amendments and PROJECT.md status"`
