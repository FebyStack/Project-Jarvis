# Jarvis Plan 3 — Voice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. One review pass at the end of the plan, not per task (Febriel's rule).

**Goal:** Febriel says "Jarvis, …" near the Mac, or holds or taps one key, and Jarvis answers out loud. Speech recognition and speech output both run on the Mac; nothing said without the name leaves a trace.

**Architecture:** Voice lives inside `jarvisd` (spec §6: one process owns the mic). Four threads sit beside the asyncio loop: the mic callback, one worker thread for every MLX call (Parakeet and Kokoro), the audio-output callback, and the key listener's run loop. Each of them only hands data to the loop; every decision (what an utterance means in the current state) is made on the loop in `Voice`, using pure helpers for the name match, utterance cutting, sentence splitting and key gestures. The core gains a `speaker` and drives the Plan 1 state machine, so replies on the `mac` channel are spoken as they stream.

**Tech Stack:** Python 3.12, `parakeet-mlx` (speech-to-text), `mlx-audio` + `misaki[en]` (Kokoro `bm_daniel`), Silero voice detection through `openwakeword.vad.VAD`, `sounddevice`, `pyobjc-framework-Quartz` (key listener), `numpy`; the existing `aiohttp`, `textual`, `pytest` + `pytest-asyncio`.

**Spec:** `docs/superpowers/specs/2026-11-10-jarvis-design.md` (as amended to 2026-11-15); section numbers below refer to it. Measured facts: `docs/spikes/findings.md` (Spikes 2–4). Spike code to lift from: `spikes/03-stt/wake_stt.py`, `spikes/03-stt/engines.py`, `spikes/04-tts/stream_race.py`.

## Where this plan sits

| Plan | Delivers |
|---|---|
| 1 (done) | Repo, vault writer, gate rules, state machine, spike findings |
| 2 (done) | Typed Jarvis: daemon, Claude Code bridge, gate, memory rule, agents, gold HUD |
| **3 (this)** | Voice: wake by transcription, Parakeet, Kokoro replies, hold/tap-to-talk, spoken cancel, live VOICE panel |
| 4 | Jarvis on screen: the red circle, agent cards, names, stop (added 2026-11-17; `2026-11-17-jarvis-plan-4-on-screen.md`) |
| 5 | Phone route on the same API, Reminder nudge, keep-awake, battery rule |
| 6 | On-screen control, reverse engineering, spawned sessions |

Plan 4 builds on this plan's `level` and `state` events, `Speaker` and `Player`, and recolours the terminal HUD red; nothing in this plan changes for it.

Carried in from Plan 1's table: tap-to-talk and hold-to-talk on one key; the spoken form of cancel; the speech engines Spikes 3–4 chose. Starting point: 647 tests pass on `main` (2026-11-16).

## Decisions this plan makes

Each was Claude's call. **Febriel confirmed all 14 as written on 2026-11-17** ("Yes, start Plan 3"). Task 15 writes them into the spec.

1. **The talk key is Right Option** (key code 61), as spec §6.1 suggested. It types nothing on its own. Right Option held with another key (é, a shortcut) is typing, not talking: nothing is heard and nothing is sent.
2. **Every reply on the `mac` channel is spoken**, typed requests and `jarvis ask` included, and so is a finished worker's announcement. Phone replies are never spoken on the Mac. There is no "quiet" switch; "mute" turns the mic off, not the voice.
3. **The key always listens**: idle, thinking, speaking, in the follow-up window, and while muted. Pressed while Jarvis speaks, it stops the speech (the rest of the reply stays in the HUD; the work goes on) and listens. A request made while another is running queues behind it, as typed ones already do.
4. **Saying "cancel" cannot stop Jarvis mid-sentence.** Spec §6.1 says both "the microphone is ignored while Jarvis is speaking" and "saying cancel stops it speaking"; the first wins, or Jarvis would obey its own voice. Speech is stopped by Escape or the key. While Jarvis is *thinking*, "Jarvis, cancel / never mind / stop" works; anything else said then is discarded (Plan 1: a wake by name only from idle).
5. **The name match is not similarity alone.** Scored with `difflib` against "jarvis": jervis 0.83, javis 0.91, jovis 0.73, but also davis 0.73, mavis 0.73, paris 0.73, avis 0.80, jars 0.80, travis 0.67, pervis 0.67. No single threshold keeps "Jovis" and drops "Davis", and the spike's 0.75 already let "Avis" and "jars" through. Starting rule: a word wakes if it is ≥ 0.70 similar **and** starts with "j" **and** has 5 letters or more, or is ≥ 0.80 similar with 6 letters or more. Task 14 tunes it on his voice.
6. **Muted means the mic stream is stopped**, so the orange mic indicator goes off and `MIC ○ muted` is true. A key press starts it again for that one request.
7. **All MLX work runs on one thread.** Parakeet and Kokoro are loaded, warmed and called on a single worker thread, one call at a time. A synthesis may wait about 0.2 s behind a transcription; in return nothing depends on MLX being thread-safe.
8. **Voice detection is `openwakeword.vad.VAD`**, the Silero model Spikes 2–3 measured. openWakeWord's wake-word models stay unused.
9. **The speech packages become real dependencies** (out of the `spike` group). `en_core_web_sm` 3.8.0, which misaki otherwise downloads at first use and `uv sync` then removes, is pinned by URL. `jarvisd` loads models with `HF_HUB_OFFLINE=1`: it never downloads at start-up. `jarvis models` downloads them (both are already in the cache from the spikes).
10. **A short tone when Jarvis starts listening with no request yet** (bare "Jarvis", or a tap), so he knows it heard him without looking at the HUD. Not in the spec. A request said in one breath gets no tone; the answer is the confirmation.
11. **Listening gives up after 8 s** if nothing is said after a bare "Jarvis" or a tap.
12. **Longest utterance: 15 s by name, 60 s while the key is held.** A request that woke Jarvis and was cut at 15 s continues into the next utterance instead of being sent half-finished.
13. **Voice problems never block typed Jarvis.** They show as one word after `MIC` in the footer (`loading`, `on`, `on, no key`, `muted`, `no permission`, `no models`, `off`) and in `jarvis doctor`, never on the first-run screen.
14. **A request may arrive mis-heard**, so `jarvis.md` gets one line telling the front door to read past plainly mis-heard words and to ask when a wrong guess would change what it does.

### Amendments after Task 1

Probes run 2026-11-17 (`docs/spikes/findings.md`, "Plan 3 probes"). Where this table disagrees with a task, it wins.

| Probe | Found | Change |
|---|---|---|
| P4 | `InputStream.stop()` 0.112 s and `OutputStream.abort()` 0.105 s, just over the 0.1 s stop bar; `start()` 0.054 s, under the 0.15 s restart bar | None to decision 6: the bar's fallback (keep the muted stream open) hangs on restart, which passes, and muting does not need to be fast. Escape/key → silence is ~0.1 s through `abort()`, inside row 10's 0.2 s. |
| P3 | Parakeet spells small numbers out and often drops the comma after the name | Task 2 adds one test in that form (`"Hey Javis set a timer for ten minutes"` → `"set a timer for ten minutes"`); the plan's tests stay. |
| P2 | `uv run` re-resolves the `en_core_web_sm` URL and fails with no network | Row 16 and offline checks use `.venv/bin/jarvis` (as the login agent does) or `uv run --frozen --no-sync`. |
| P6, P7 | macOS lists the venv interpreter as "Python" under Input Monitoring and Microphone; Right Option = 61, bit `0x40` | Task 11 uses them as planned; Task 12's README names "Python". |
| (Step 1) | Every package in the `spike` uv group became a product dependency | The `spike` group is removed and `default-groups = ["dev"]`. |

Found while building (2026-11-17):

| Task | Found | Change |
|---|---|---|
| 7 | With the pinned `on_done` rule, a spoken gate question ("Delete test.txt?") ends in `THINKING` (the turn is still running), where only "Jarvis, cancel" is heard, so row 5's spoken "yes" would be dropped | When speech runs out while a yes/no question is pending, `on_done` sends `REPLY_END` (the follow-up window), not `REPLY_PAUSE`. |
| 7 | A request parked by the usage limit or by the brain being offline would count as "still waiting" and hold the state in `THINKING` for hours | A parked request does not count for `REPLY_PAUSE`. |
| 8 | `Mic(..., sleep=time.sleep)` would make `stop()` wait out a reopen backoff of up to 30 s | `Mic(open_stream=_open_input, sleep=None)`: by default it waits on its stop event, so `stop()` ends it at once. |
| 9 | Task 9's rule for `say()` ("if the fed text ends with `text`") contradicts its own test (`feed("Let me check. ")`, `feed("Done.")`, `say("Done.")`) | `say()` speaks only what the longest overlap of the fed text and `text` leaves unspoken; the tests stand as written. |
| 9 | `say -v Daniel <text>` lets a reply that starts with "-" pass options to `say` (security review) | `say -v Daniel -f -`, the text on stdin. |
| 11 | `tap()` made the kept frames an utterance ended by silence, so a tap followed by the tone and a pause gave up after 0.8 s and the request then arrived in `IDLE` with no name | `Segmenter.tap()` with no speech in the kept frames falls back to normal listening; the state stays `LISTENING` until speech or the 8 s timeout. |
| 15 (rows 1–2) | Febriel's reflex "Okay." / "Huh?" as an answer ended was taken in the follow-up window and sent to Claude, whose reply opened another window | A bare acknowledgement (`instant.is_ack`) heard while `LISTENING` with no name, no kept start and no pending question ends the exchange silently (Febriel, 2026-11-17). |
| 15 (rows 3–5) | With other people talking in the room, the 6 s no-name window after every answer caught their speech and chained reply after reply | The follow-up window opens only after a reply that asks something (ends in "?") or while a yes/no waits; after a plain answer the state goes straight to `IDLE` (Febriel, 2026-11-17; spec §6.1 to amend). |
| 15 (row 10) | Escape during a long answer froze jarvisd (2026-11-18): the output callback's `CallbackStop` and the loop's `abort()` stopped the same stream at once and deadlocked on a CoreAudio lock (stack sample), so the state stayed `SPEAKING` and nothing more was heard | The callback never stops its stream; only the loop does: `Player.stop()`, the next `play()`, or the new `Player.close()`, which `VoiceSpeaker` calls when a run's done arrives. |
| 15 (row 13) | Typing é, ñ and ⌥← with Right Option woke Jarvis and twice cut off a reply: Febriel's chords come 87–603 ms after the key (25 measured over two passes, 2026-11-18), past the pinned 0.15 s grace; 0.5 s still let a 603 ms é through | `KEY_GRACE_SECONDS = 0.8` (Febriel's choice). Taps (111–136 ms) still engage at once on key up; a hold now stops speech and shows `LISTENING` 0.8 s after the press (capture still starts at once). |

**Known exposure, not solved here:** in the 6 s follow-up window no name is needed, so after Jarvis asks "Delete 14 files?", a "yes" from a video or another person in the room would count (spec §10 risk 8). The voice-print lock is in §14, later. Until then the question is also in the HUD, and a held key is the sure way to answer.

## File structure

| File | Responsibility |
|---|---|
| `jarvis/config.py` (modify) | The voice constants in Global Constraints. |
| `jarvis/voice/wake.py` | Does a word sound like "Jarvis"; split an utterance into name and request. Pure. |
| `jarvis/voice/segment.py` | Voice-detector probabilities in, whole utterances out; key-held capture. Pure given a `predict` function. |
| `jarvis/voice/sentences.py` | Streamed reply text in, speakable chunks out. Pure. |
| `jarvis/voice/gesture.py` | Key down/up times in, `down` / `tap` / `hold_end` / `chord` out. Pure. |
| `jarvis/voice/engines.py` | The one MLX thread: load, warm, `transcribe`, `synth`; the voice detector; `download`. |
| `jarvis/voice/audio.py` | `Mic` (input stream, reopen, silence check) and `Player` (output queue, stop). |
| `jarvis/voice/speaker.py` | `VoiceSpeaker`: sentences → synthesis → player, in order; stop, hold, tone, `say` fallback. |
| `jarvis/voice/keys.py` | The system-wide listener for the talk key (Quartz event tap). |
| `jarvis/voice/loop.py` | `Voice`: what an utterance or a key gesture means in each state; mic health. |
| `jarvis/daemon/state.py` (modify) | Key press, typed request, speech pause, listening timeout. |
| `jarvis/daemon/core.py` (modify) | `speaker`, state driving, `level` event, `health.mic`. |
| `jarvis/cli.py` (modify) | Builds the voice in `jarvis daemon`; `jarvis models`; voice lines in `jarvis doctor`. |
| `jarvis/tui/model.py`, `jarvis/tui/app.py` (modify) | Live waveform, mic word, `ctrl+l` mic toggle. |
| `.claude/agents/jarvis.md`, `launchd/README.md` (modify) | Mis-heard line; the two permissions. |
| `tests/conftest.py`, `tests/voice/` | Shared daemon fixtures; voice tests. |
| `spikes/09-voice/` | Task 1's probes and Task 14's tuning script. |

## Global Constraints

- Subscription login only; no API key, no `--bare`. Nothing in this plan calls a model except through the existing bridge.
- No audio is ever written to disk or sent anywhere. Utterances live in memory until transcribed, then are dropped.
- An utterance without the name is discarded at once: no event, no log line, no vault write, not shown. The log (`~/.jarvis/jarvisd.log`) holds timings and errors only, never heard or spoken text.
- Exact values, all in `jarvis/config.py`: `SAMPLE_RATE = 16000`, `FRAME = 480` (30 ms), `END_SILENCE_SECONDS = 0.8`, `MAX_UTTERANCE_SECONDS = 15.0`, `MAX_HELD_SECONDS = 60.0`, `WAKE_SIMILARITY = 0.70`, `WAKE_STRICT = 0.80`, `WAKE_ALSO: frozenset[str] = frozenset()`, `WAKE_WORDS = 3`, `LISTEN_SECONDS = 8.0`, `TALK_KEYCODE = 61`, `TAP_SECONDS = 0.3`, `KEY_GRACE_SECONDS = 0.15`, `MIC_REOPEN_DELAY = 0.3`, `FIRST_CHUNK_CHARS = 60`, `STT_MODEL = "mlx-community/parakeet-tdt-0.6b-v2"`, `TTS_MODEL = "mlx-community/Kokoro-82M-bf16"`, `TTS_VOICE = "bm_daniel"`, `TTS_LANG = "b"`. `FOLLOW_UP_SECONDS = 6.0` stays in `state.py`.
- Voice detector thresholds as measured in Spike 3: start 0.5, stop 0.35, pre-roll 0.3 s.
- Importing `jarvis.cli`, `jarvis.tui` or `jarvis.daemon.core` must not import `mlx`, `sounddevice`, `Quartz` or `openwakeword`: those imports sit inside the functions that use them, so `jarvis ask`, the HUD and the test suite stay fast.
- Unit tests never open a microphone, a speaker, a key listener or a model. Hardware is behind constructor arguments with fakes.
- Installs, each named to Febriel before it runs: `parakeet-mlx`, `pyobjc-framework-Quartz`, the `en_core_web_sm` 3.8.0 wheel (12 MB).
- No `sudo`, no change to system security settings. Febriel grants Microphone and Input Monitoring himself.
- English only. Commits carry no Claude credit line. Jarvis never repeats back what Febriel said.

## Review Focus

1. **Jarvis hearing itself.** The tail of its own speech, picked up in the follow-up window where no name is needed, must not become a request. The mic stays shut until `MIC_REOPEN_DELAY` after the last sample, and the cutter is reset when it reopens. Pinned in Tasks 8 and 10.
2. **Speech without the name leaving a trace.** Not in an event, the log, the vault or the HUD, including when transcription fails halfway. Pinned in Task 10.
3. **The mic going away or going silent** (AirPods disconnect, sleep and wake, permission revoked): it reopens with a growing wait, the footer says why, and no thread dies or spins. Pinned in Task 8.
4. **A state that never ends.** Empty transcription, synthesis that fails, no speaker at all, nothing said after "Jarvis": the state always gets back to `IDLE`, and the mic is never left shut. Pinned in Tasks 6, 7 and 9.
5. **The talk key used for typing.** Right Option + another key must not stop speech, flash the HUD or send a request, and the listener must read no key but its own. Pinned in Tasks 5 and 11.

---

### Task 1: Dependencies, and probes of what the spikes did not measure 👤

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `docs/spikes/findings.md`
- Create: `spikes/09-voice/` (one script per probe)

**Interfaces:**
- Produces: the packages every later task imports; a "Plan 3 probes" section in the findings; if a probe contradicts this plan, an "Amendments after Task 1" table added under "Decisions this plan makes" (where it disagrees with a task, it wins).

- [ ] **Step 1: Name the three installs to Febriel, then move the speech stack into the main dependencies**

`[project].dependencies` gains `numpy`, `sounddevice`, `onnxruntime`, `openwakeword`, `mlx-audio`, `misaki[en]`, `parakeet-mlx`, `pyobjc-framework-Quartz` and `en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl`. The `spike` group keeps only what no product code imports. After any `uv add` / `uv remove`, run `uv sync` and check nothing else changed version (findings, "kokoro-onnx removed", says why).

Run: `uv run pytest -q` → 647 passed. Run: `uv run python -c "import parakeet_mlx, Quartz, en_core_web_sm, mlx_audio, openwakeword.vad"` → no error.
If `parakeet-mlx` will not resolve beside `mlx-audio` 0.6.5, stop and report; do not change the engine.

- [ ] **Step 2: Run the probes, one script each, no audio kept**

| # | Probe | Bar | Changes |
|---|---|---|---|
| P1 | Parakeet and Kokoro loaded and called 20 times each, alternating, on one worker thread of an asyncio process while a `sounddevice` input callback runs | No crash; medians within 50 % of Spike 3's 0.17 s and Spike 4's 0.19 s | Decision 7 |
| P2 | Model load with `HF_HUB_OFFLINE=1` and Wi-Fi off; first Kokoro synthesis with `en_core_web_sm` from the lockfile | Loads; nothing is downloaded | Decision 9 |
| P3 | Parakeet on what Febriel says: does the text keep digits, capitals and punctuation ("10 minutes", "Jervis,")? Time for a 15 s and a 60 s utterance | Recorded; 60 s under 2 s | Task 2's tests, decision 12 |
| P4 | `sounddevice` output: time from `play` to sound, and from `abort()` to silence; `InputStream.stop()` → `start()` time | Stop under 0.1 s; restart under 0.15 s (else the muted stream stays open and frames are dropped instead) | Tasks 8, 10, decision 6 |
| P5 | 👤 A Kokoro sentence through the Mac speakers at normal volume: how long after the last sample does the voice detector still fire? | Sets `MIC_REOPEN_DELAY` (keep 0.3 s if under 0.2 s) | Review Focus 1 |
| P6 | 👤 A listen-only Quartz event tap for `flagsChanged` and `keyDown`, run from a temporary launchd agent started the way `com.febriel.jarvisd` is: which program macOS lists under Input Monitoring; Right Option's key code and flag bit (expected 61 and `0x40`); down and up both arrive; Option+E arrives as a `keyDown` | Febriel grants it once; events arrive | Task 11 |
| P7 | 👤 The mic from the real login agent (`launchctl kickstart` a build that only reads the mic for 10 s): real audio or all zeros; which program macOS lists under Microphone | Real audio | Task 12's README |
| P8 | The tone: an 880 Hz, 80 ms sine through the speakers with the mic open: does the voice detector fire, does Parakeet return text? | Neither | Decision 10 (else the mic shuts for the tone) |

- [ ] **Step 3: Write "Plan 3 probes" into `docs/spikes/findings.md`** (the table with measured values and verdicts, then "What later tasks must do"), and the amendments table here if any probe failed its bar.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock spikes/09-voice docs/spikes/findings.md docs/superpowers/plans/2026-11-16-jarvis-plan-3-voice.md
git commit -m "chore: speech packages become dependencies, and the Plan 3 probes"
```

---

### Task 2: Constants and the name match

**Files:**
- Modify: `jarvis/config.py`
- Create: `jarvis/voice/wake.py`
- Test: `tests/voice/test_wake.py`

**Interfaces:**
- Produces: every constant in Global Constraints, and

```python
def sounds_like_name(word: str) -> bool
def split(text: str) -> str | None
    """None: no name in the first WAKE_WORDS words. "": the name alone. Else the request after the name,
    exactly as transcribed (capitals, digits, punctuation), minus leading separators."""
```

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("word", ["jarvis", "Jervis", "jovis", "javis", "jarvas", "Jarvis's", "darvis", "carvis"])
def test_words_that_wake(word):
    assert wake.sounds_like_name(word)

@pytest.mark.parametrize("word", ["travis", "davis", "avis", "mavis", "paris", "jars", "jar", "pervis", "agries",
                                  "service", "harvest", "java", "jarring", ""])
def test_words_that_do_not(word):
    assert not wake.sounds_like_name(word)

def test_also_list_wakes_exactly(monkeypatch):
    monkeypatch.setattr(config, "WAKE_ALSO", frozenset({"pervis"}))
    assert wake.sounds_like_name("Pervis") and not wake.sounds_like_name("pervert")

def test_split_keeps_the_request_as_spoken():
    assert wake.split("Hey Jervis, set a timer for 10 minutes.") == "set a timer for 10 minutes."
    assert wake.split("Okay so Jarvis open Mail") == "open Mail"
    assert wake.split("Jarvis.") == "" and wake.split("Hey, Jarvis's") == ""

def test_split_finds_no_name():
    assert wake.split("I told Travis about it") is None
    assert wake.split("one two three Jarvis") is None      # only the first three words count
    assert wake.split("") is None
```

- [ ] **Step 2: Run** `uv run pytest tests/voice/test_wake.py -q` → fails, no module `jarvis.voice.wake`.

- [ ] **Step 3: Add the constants to `jarvis/config.py` and implement `wake.py`**

A word is compared in lower case, letters and apostrophes only, a trailing `'s` dropped. It wakes if it is in `WAKE_ALSO`, or `ratio >= WAKE_SIMILARITY` and it starts with "j" and has ≥ 5 letters, or `ratio >= WAKE_STRICT` and it has ≥ 6 letters (`difflib.SequenceMatcher(None, word, "jarvis").ratio()`). `split` finds words with their positions in the original text, so the request is a slice of it, not a rebuilt string.

- [ ] **Step 4: Run** `uv run pytest tests/voice/test_wake.py -q` → all pass.

- [ ] **Step 5: Commit** `git commit -m "feat: the name match keeps Jovis and drops Davis, and the request stays as spoken"`

---

### Task 3: Cutting the mic stream into utterances

**Files:**
- Create: `jarvis/voice/segment.py`
- Test: `tests/voice/test_segment.py`

**Interfaces:**
- Consumes: `config.FRAME`, `END_SILENCE_SECONDS`, `MAX_UTTERANCE_SECONDS`, `MAX_HELD_SECONDS`.
- Produces:

```python
@dataclass
class Utterance:
    pcm: np.ndarray   # int16, 16 kHz, mono
    cut: bool         # ended by the length cap, not by silence

class Segmenter:
    def __init__(self, predict: Callable[[np.ndarray], float]): ...
    speaking: bool                               # True from the first speech frame until the utterance ends
    def feed(self, frame: np.ndarray) -> Utterance | None
    def hold(self) -> None                       # key down: keep every frame from now, plus the pre-roll
    def release(self) -> Utterance | None        # key up after a hold: what was kept, at once; None if nothing
    def tap(self) -> None                        # key up after a tap: what was kept becomes an utterance in
                                                 # progress, ended by silence like any other
    def reset(self) -> None                      # drop everything, pre-roll included
```

- [ ] **Step 1: Write the failing tests.** `predict` is a fake that returns the frame's first sample / 1000, so `frame(0.9)` is speech and `frame(0.0)` is silence.

```python
def test_silence_yields_nothing_and_keeps_only_the_pre_roll()      # 200 silent frames → None each; buffer ≤ 10 frames
def test_speech_then_silence_is_one_utterance()                    # 34 speech + 27 silent → one Utterance, cut False,
                                                                   # len(pcm) == (34 + 3) * 480, the 27th silent frame yields it
def test_a_short_pause_does_not_cut()                              # 10 speech, 16 silent (0.48 s), 10 speech, 27 silent → one
def test_the_cap_cuts_and_says_so()                                # 600 speech frames → Utterance at frame 500, cut True
def test_speaking_flag_follows_the_utterance()                     # False, True on first speech frame, False once it ends
def test_pre_roll_is_kept()                                        # 10 silent frames of value 7 before speech → pcm starts with them
def test_hold_keeps_everything_whatever_the_detector_says()        # hold(); 50 silent frames; release() → 50 frames (+ pre-roll)
def test_release_with_nothing_held_is_none()
def test_hold_stops_at_the_held_cap()                              # held: the 2000th feed returns an Utterance, cut True
def test_tap_turns_the_held_frames_into_speech_in_progress()       # hold(); 5 speech; tap(); 27 silent → one Utterance
def test_reset_forgets_speech_in_progress()                        # 10 speech; reset(); 27 silent → None
```

- [ ] **Step 2: Run** `uv run pytest tests/voice/test_segment.py -q` → fails, no module.

- [ ] **Step 3: Implement `Segmenter`**, lifting the logic of `spikes/03-stt/wake_stt.py` (start 0.5, stop 0.35, pre-roll 0.3 s = 10 frames, three frames of trailing silence kept). Silent frames that end an utterance: `math.ceil(0.8 / 0.03)` = 27 (the spike's `int()` gave 26, 0.78 s). Caps: 500 frames by name, 2000 while held. It imports only `numpy`.

- [ ] **Step 4: Run** → all pass. **Step 5: Commit** `git commit -m "feat: the mic stream is cut into utterances, and a held key keeps everything"`

---

### Task 4: Reply text into speakable chunks

**Files:**
- Create: `jarvis/voice/sentences.py`
- Test: `tests/voice/test_sentences.py`

**Interfaces:**
- Produces:

```python
class Splitter:
    def feed(self, delta: str) -> list[str]      # the chunks this delta completed, already speakable
    def flush(self) -> list[str]                 # what is left, when the reply is over
def speakable(text: str) -> str                  # "" when nothing in it can be said
```

- [ ] **Step 1: Write the failing tests**

```python
def test_sentences_come_out_as_they_complete():
    s = Splitter()
    assert s.feed("Right. I'll che") == ["Right."]
    assert s.feed("ck now. ") == ["I'll check now."]
    assert s.flush() == []

def test_numbers_and_times_do_not_split():
    assert Splitter().feed("It's 3.5 GB at 10:05. ") == ["It's 3.5 GB at 10:05."]

def test_a_long_first_sentence_starts_at_a_clause_break():
    s = Splitter()
    assert s.feed("Well, " + "x" * 60) == ["Well,"]            # only the first chunk of a reply may do this
    assert s.feed(" and so, " + "y" * 80) == []

def test_flush_gives_the_tail():
    s = Splitter(); assert s.feed("No full stop") == [] and s.flush() == ["No full stop"]

def test_speakable():
    assert speakable("**Done** — see `notes.md` at https://example.com/a?b=1") == "Done — see notes.md at a link"
    assert speakable("```") == "" and speakable("  \n ") == ""
```

- [ ] **Step 2: Run** → fails, no module.

- [ ] **Step 3: Implement.** A chunk ends at `.`, `!` or `?` followed by white space, or at a newline. Until the first chunk of a reply is out, once `FIRST_CHUNK_CHARS` characters have arrived with no ending, cut at the last `, `, `; ` or ` — `. `speakable` removes `*`, `` ` `` and `#`, turns `_` into a space, replaces a URL with "a link", collapses white space, and returns "" if no letter or digit is left.

- [ ] **Step 4: Run** → all pass. **Step 5: Commit** `git commit -m "feat: a streamed reply becomes sentences that can be spoken as they arrive"`

---

### Task 5: Tap, hold and chord

**Files:**
- Create: `jarvis/voice/gesture.py`
- Test: `tests/voice/test_gesture.py`

**Interfaces:**
- Produces:

```python
Kind = Literal["down", "tap", "hold_end", "chord"]

class Gesture:
    def key_down(self, at: float) -> Kind | None      # "down"; None if already down (key repeat)
    def key_up(self, at: float) -> Kind | None        # "tap" under TAP_SECONDS, else "hold_end"; None after a chord
    def other_key(self, at: float) -> Kind | None     # "chord" while the talk key is down, else None
```

- [ ] **Step 1: Write the failing tests**

```python
def test_tap():           g = Gesture(); assert [g.key_down(0.0), g.key_up(0.29)] == ["down", "tap"]
def test_hold():          g = Gesture(); assert [g.key_down(0.0), g.key_up(0.30)] == ["down", "hold_end"]
def test_chord():         g = Gesture(); assert [g.key_down(0.0), g.other_key(0.1), g.other_key(0.2), g.key_up(0.5)] == ["down", "chord", None, None]
def test_key_repeat():    g = Gesture(); assert [g.key_down(0.0), g.key_down(0.1)] == ["down", None]
def test_stray_events():  g = Gesture(); assert g.key_up(1.0) is None and g.other_key(1.0) is None
def test_usable_again_after_a_chord()   # down, other, up, then down → "down"
```

- [ ] **Step 2: Run** → fails. **Step 3: Implement `Gesture`.** **Step 4: Run** → pass. **Step 5: Commit** `git commit -m "feat: one key, three gestures: tap, hold, and typing left alone"`

---

### Task 6: The state machine learns the key, typed requests and pauses

**Files:**
- Modify: `jarvis/daemon/state.py`
- Test: `tests/daemon/test_state.py` (add; every existing test stays green unchanged)

**Interfaces:**
- Produces: `Event.PUSH`, `Event.REQUEST`, `Event.REPLY_PAUSE`; `LISTEN_SECONDS` read from `config`; and these rules:

| From | Event | To |
|---|---|---|
| `IDLE`, `FOLLOW_UP`, `THINKING`, `SPEAKING` | `PUSH` (also while muted) | `LISTENING` |
| `IDLE`, `FOLLOW_UP` | `REQUEST` (a typed request on the Mac) | `THINKING` |
| `IDLE`, `FOLLOW_UP` | `REPLY_START` (an announcement, an instant answer) | `SPEAKING` |
| `SPEAKING` | `REPLY_PAUSE` (speech ran out, the turn goes on) | `THINKING` |
| `LISTENING` | any event, `LISTEN_SECONDS` after entering with no `SPEECH_START` since | `IDLE` |
| `LISTENING` | `WAKE` or `PUSH` | `LISTENING`, and the 8 s start again |

Entering `LISTENING` by `SPEECH_START` (from the follow-up window) counts as speech already seen. `mic_open` becomes: not `SPEAKING`, and (not muted or `LISTENING`).

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("state", [State.IDLE, State.THINKING, State.SPEAKING, State.FOLLOW_UP])
def test_the_key_listens_from_every_state(sm, state):
    reach(sm, state); assert sm.on(Event.PUSH) is State.LISTENING

def test_the_key_listens_while_muted_and_only_then_is_the_mic_open(sm):
    sm.on(Event.MUTE); assert not sm.mic_open
    assert sm.on(Event.PUSH) is State.LISTENING and sm.mic_open
    sm.on(Event.SPEECH_END); assert not sm.mic_open            # back to shut once the request is in

def test_a_typed_request_thinks_then_speaks(sm):
    assert [sm.on(e) for e in (Event.REQUEST, Event.REPLY_START, Event.REPLY_END)] == \
        [State.THINKING, State.SPEAKING, State.FOLLOW_UP]

def test_an_announcement_speaks_from_idle(sm):
    assert sm.on(Event.REPLY_START) is State.SPEAKING and not sm.mic_open

def test_speech_that_runs_out_mid_turn_goes_back_to_thinking(sm):
    reach(sm, State.SPEAKING); assert sm.on(Event.REPLY_PAUSE) is State.THINKING

def test_listening_gives_up_after_eight_seconds(sm, clock):
    sm.on(Event.WAKE); clock.advance(7.9); assert sm.on(Event.TICK) is State.LISTENING
    clock.advance(0.1); assert sm.on(Event.TICK) is State.IDLE

def test_listening_does_not_give_up_mid_sentence(sm, clock):
    sm.on(Event.WAKE); sm.on(Event.SPEECH_START); clock.advance(30); assert sm.on(Event.TICK) is State.LISTENING

def test_a_name_still_wakes_only_from_idle(sm):
    reach(sm, State.THINKING); assert sm.on(Event.WAKE) is State.THINKING

def test_waking_again_while_listening_restarts_the_eight_seconds(sm, clock):
    sm.on(Event.WAKE); sm.on(Event.SPEECH_START); clock.advance(5); sm.on(Event.WAKE)
    clock.advance(7.9); assert sm.on(Event.TICK) is State.LISTENING
    clock.advance(0.1); assert sm.on(Event.TICK) is State.IDLE
```

- [ ] **Step 2: Run** `uv run pytest tests/daemon/test_state.py -q` → the new ones fail.
- [ ] **Step 3: Implement** in `state.py`. **Step 4: Run** `uv run pytest tests/daemon -q` → all pass.
- [ ] **Step 5: Commit** `git commit -m "feat: the state machine knows the talk key, typed requests and a pause in speech"`

---

### Task 7: The core speaks and drives the state

**Files:**
- Modify: `jarvis/daemon/core.py`
- Create: `tests/conftest.py` (the fixtures `clock`, `vault`, `scribe_runs`, `make`, `jarvis`, `jarvis_fast_timeouts`, `jarvis_no_vault`, `bridge`, `bridge_of` and the helpers `FakeClock`, `FakeBridge`, `until`, `NOW`, `day_log`, moved unchanged out of `tests/daemon/conftest.py` and `tests/daemon/test_core.py` so `tests/voice` can use them)
- Test: `tests/daemon/test_core_voice.py`

**Interfaces:**
- Consumes: Task 6's events.
- Produces:

```python
class Speaker(Protocol):                 # in core.py; Task 9 implements it
    on_start: Callable[[], None]         # set by the core: the first sound of a run of speech is going out
    on_done: Callable[[], None]          # set by the core: speech ran out (also when there was nothing to say)
    def feed(self, delta: str) -> None   # reply text as it streams
    def say(self, text: str) -> None     # a complete reply
    def stop(self) -> None               # silence now; forget what was queued
    def hold(self, on: bool) -> None     # while on, start no new sound
    def cue(self) -> None                # the listening tone

Jarvis(..., speaker: Speaker | None = None)
def wake(self, key: bool = False) -> bool   # WAKE, or PUSH for the key; True if now LISTENING
def cue(self) -> None                    # the listening tone, if there is a speaker
def speech_started(self) -> None         # SPEECH_START
def heard(self, text: str) -> None       # SPEECH_END, then the request runs as a task; "" → give_up()
def give_up(self) -> None                # LISTENING → IDLE with no request and no reply
def level(self, rms: float) -> None      # publishes {"type": "level", "rms": 0.0–1.0}
def set_mic(self, word: str) -> None     # health.mic; default "off"
```

Rules the tests pin:
- A typed `mac` request sends `REQUEST`. A `phone` request never touches the voice state or the speaker.
- A text delta goes to `speaker.feed` when the turn's request is on `mac` (a turn nobody asked for counts as `mac` unless its owner is a `phone` request). Every `mac` reply goes to `speaker.say`: turn ends, instant answers, gate questions, limit and vault sentences, announcements.
- `on_start` → `REPLY_START`. `on_done` → `REPLY_PAUSE` if a `mac` request is still running or waiting, else `REPLY_END`. With no speaker, a `mac` reply sends `REPLY_END` itself.
- `cancel()` calls `speaker.stop()`. The cancelled turn's own "Cancelled." is not spoken a second time.
- `wake(key=True)` while speaking calls `speaker.stop()`. `speaker.hold(True)` whenever the state becomes `LISTENING`, `hold(False)` when it leaves.
- `tick()` sends `TICK`. Every change of `state` or `muted` publishes one `state` event; no change publishes none.

- [ ] **Step 1: Move the fixtures into `tests/conftest.py`.** Run `uv run pytest -q` → 647 + the earlier tasks' tests pass, none lost.

- [ ] **Step 2: Write the failing tests** (`FakeSpeaker` records `calls` as tuples; `states(jarvis)` collects the `voice` of each `state` event)

```python
async def test_a_streamed_reply_is_fed_then_finished(make, bridge_of):
    j = await make(speaker=(sp := FakeSpeaker())); b = bridge_of(j)
    t = asyncio.create_task(j.submit("how are you", "mac")); await b.got("how are you")
    b.emit({"kind": "delta", "text": "Fine. "}); b.emit(turn("Fine.")); await t
    assert sp.calls == [("feed", "Fine. "), ("say", "Fine.")]

async def test_phone_replies_are_not_spoken()             # submit(..., "phone") + turn → sp.calls == [], state stays IDLE
async def test_instant_answers_and_questions_are_spoken() # "what time is it" → ("say", say_time(NOW)); a gate question → ("say", question)
async def test_the_state_follows_one_spoken_exchange():
    # wake() → heard("capital of Australia") → sp.on_start() → turn → sp.on_done()
    # states == ["LISTENING", "THINKING", "SPEAKING", "FOLLOW_UP"]
async def test_speech_that_runs_out_mid_turn_goes_back_to_thinking()   # on_done() before the turn ends → "THINKING"
async def test_cancelled_is_said_once()                   # a turn in flight, then heard("never mind"):
                                                          # sp.calls has ("stop",) and exactly one ("say", "Cancelled.")
async def test_without_a_speaker_nothing_sticks()         # make(): typed request + turn → state IDLE
async def test_the_key_stops_speech_and_listens()         # SPEAKING; wake(key=True) → ("stop",), ("hold", True), LISTENING
async def test_jarvis_does_not_talk_over_a_listening_mic() # LISTENING, then an announcement turn: ("hold", True) came
                                                          # before its ("say", …); heard("…") → ("hold", False)
async def test_an_empty_hearing_gives_up_quietly(vault)   # wake(); heard("") → IDLE, no "heard" event, no day log
async def test_listening_times_out_through_tick(clock)    # wake(); clock.advance(8); await j.tick() → IDLE, one state event
async def test_the_tone_only_when_asked()                 # cue() → ("cue",); wake() alone → none; no speaker: cue() does nothing
async def test_level_and_mic_reach_subscribers()          # level(0.4) → {"type": "level", "rms": 0.4}; set_mic("on") → health.mic == "on"
async def test_a_typed_request_shows_thinking()           # submit typed → first state event "THINKING"
```

- [ ] **Step 3: Run** `uv run pytest tests/daemon/test_core_voice.py -q` → fail.
- [ ] **Step 4: Implement in `core.py`.** `heard` must not await the reply: it starts `submit(text, "mac")` as a task and keeps a reference to it.
- [ ] **Step 5: Run** `uv run pytest -q` → all pass (Plan 2's core tests unchanged).
- [ ] **Step 6: Commit** `git commit -m "feat: the core speaks mac replies and drives the voice state"`

---

### Task 8: The engines, the mic and the player

**Files:**
- Create: `jarvis/voice/engines.py`, `jarvis/voice/audio.py`
- Test: `tests/voice/test_engines.py`, `tests/voice/test_audio.py`

**Interfaces:**
- Produces:

```python
RATE_OUT = 24000

class ModelsMissing(Exception): ...               # raised by the real loaders when a model is not in the cache

class Engines:
    def __init__(self, load_stt=_load_parakeet, load_tts=_load_kokoro): ...
    async def load(self) -> str | None            # loads and warms both; None, or why not: "no models" or the error's class name
    async def transcribe(self, pcm: np.ndarray) -> str      # int16 16 kHz → text, "" for silence
    async def synth(self, text: str) -> np.ndarray          # float32 mono at RATE_OUT
    def close(self) -> None
def vad() -> Callable[[np.ndarray], float]        # Silero, for the Segmenter; runs on the caller's thread
def download() -> None                            # `jarvis models`: both repos into the Hugging Face cache

class Mic:
    def __init__(self, open_stream=_open_input, sleep=time.sleep): ...
    on_frame: Callable[[np.ndarray], None]        # set by Voice; both default to doing nothing
    on_word: Callable[[str], None]
    def start(self) -> None
    def stop(self) -> None
class Player:
    def __init__(self, open_stream=_open_output, reopen_delay: float = config.MIC_REOPEN_DELAY): ...
    on_start: Callable[[], None]                  # set by VoiceSpeaker; both default to doing nothing
    on_done: Callable[[], None]
    busy: bool
    def play(self, pcm: np.ndarray) -> None
    def stop(self) -> None
```

`Mic` and `Player` call back on their own threads; whoever sets the callback hops to the loop. `Mic` delivers `FRAME`-sample int16 frames, reports `on_word("on")` once real audio flows, `on_word("no permission")` after 2 s of all-zero samples (what macOS gives a process without the grant), `on_word("off")` while it has no stream; after a stream error or 2 s without a frame it reopens, waiting 1, 2, 4 … up to 30 s between tries. `Player` fires `on_start` at the first sample of a run and `on_done` `reopen_delay` after the last one once nothing is queued; `stop()` empties the queue, silences the output and fires `on_done` at once.

- [ ] **Step 1: Write the failing tests** (fake loaders, fake streams, a fake `sleep`; no hardware)

```python
async def test_every_engine_call_runs_on_the_one_worker_thread()   # load, 3× transcribe, 3× synth: one thread id, not the main one
async def test_load_warms_both_engines()                           # the fakes saw one transcribe and one synth before load() returned
async def test_missing_models_are_named_not_raised()               # loader raises ModelsMissing → load() == "no models"
async def test_a_failed_load_names_the_error()                     # loader raises RuntimeError → load() == "RuntimeError"

def test_mic_delivers_frames_and_says_on()
def test_mic_reopens_after_an_error_with_a_growing_wait()          # stream raises 3 times → sleeps [1, 2, 4], then frames again
def test_mic_reopens_when_frames_stop_coming()                     # a stream that goes quiet for 2 s is closed and opened again
def test_all_zero_audio_is_no_permission_then_on_when_it_returns()
def test_mic_stop_ends_its_thread_and_says_off()

def test_player_fires_start_once_per_run_and_done_after_the_delay()  # play ×2 back to back → one on_start; on_done reopen_delay after the end
def test_player_stop_drops_what_is_queued_and_is_done_at_once()
def test_player_starts_again_after_done()                          # a second run fires on_start again
```

- [ ] **Step 2: Run** → fail. **Step 3: Implement.** The real loaders follow `spikes/03-stt/engines.py` and `spikes/04-tts/stream_race.py` (`load_model(config.TTS_MODEL)`, `generate(text, voice=config.TTS_VOICE, lang_code=config.TTS_LANG)`); the worker is a `ThreadPoolExecutor(max_workers=1)`. `mlx`, `sounddevice` and `openwakeword` are imported inside the functions that use them.
- [ ] **Step 4: Run** `uv run pytest tests/voice -q` → pass. **Step 5: Commit** `git commit -m "feat: speech engines on one thread, a mic that comes back, a player that can be stopped"`

---

### Task 9: The speaker

**Files:**
- Create: `jarvis/voice/speaker.py`
- Test: `tests/voice/test_speaker.py`

**Interfaces:**
- Consumes: `Splitter`, `speakable` (Task 4); `Engines.synth`, `Player`, `RATE_OUT` (Task 8); the `Speaker` protocol (Task 7).
- Produces: `VoiceSpeaker(synth: Callable[[str], Awaitable[np.ndarray]], player, fallback: Callable[[str], Awaitable[None]] = say_daniel)`, which implements `Speaker`. It is built on the running loop, sets `player.on_start` and `player.on_done` to its own handlers, and those hop to that loop before touching its state or calling the core's `on_start` / `on_done`. `say_daniel` runs `say -v Daniel <text>` and can be killed by `stop()`.

- [ ] **Step 1: Write the failing tests** (fake `synth` returns `len(text)` samples and records its texts; fake player records `play` and `stop`)

```python
async def test_chunks_are_spoken_in_order_as_they_complete():
    sp.feed("Right. I'll che"); sp.feed("ck now. "); await idle(sp)
    assert synth.texts == ["Right.", "I'll check now."]

async def test_say_after_feed_speaks_only_the_tail():
    sp.feed("Fine. And y"); sp.say("Fine. And you?"); await idle(sp)
    assert synth.texts == ["Fine.", "And you?"]

async def test_text_before_a_tool_call_is_not_spoken_twice():
    sp.feed("Let me check. "); sp.feed("Done."); sp.say("Done."); await idle(sp)   # the turn's text is its last message only
    assert synth.texts == ["Let me check.", "Done."]

async def test_say_alone_speaks_it_all()                 # say("Mic off.") → ["Mic off."]
async def test_a_different_say_after_feed_speaks_both()  # feed("Deleting. "); say("Delete 14 files?") → both, in order
async def test_stop_forgets_the_rest()                   # feed 3 sentences, stop() after the first plays → player.stop called,
                                                         # nothing more played, a synthesis in flight is thrown away
async def test_hold_starts_nothing_until_released()      # hold(True); say("Hi.") → nothing played; hold(False) → played
async def test_synthesis_that_fails_falls_back_to_say()  # synth raises → fallback("Hi.") awaited
async def test_when_both_fail_done_still_fires()         # on_done called, no exception escapes
async def test_nothing_speakable_is_done_without_a_start() # say("```") → on_done called, on_start not
async def test_cue_plays_a_tone()                        # cue() → one play of 0.08 s of audio, no synth call
```

- [ ] **Step 2: Run** → fail. **Step 3: Implement.** One consumer task takes chunks from a queue, so order holds and a `stop()` can drop what is behind it. `say(text)` compares with the text fed since the last `say`, white space collapsed: if the fed text ends with `text`, only the splitter's tail is flushed; otherwise the tail is flushed and `text` is spoken whole. The tone is an 880 Hz, 80 ms sine at a quarter of full scale.
- [ ] **Step 4: Run** → pass. **Step 5: Commit** `git commit -m "feat: replies are spoken sentence by sentence, and can be stopped or held"`

---

### Task 10: The voice loop

**Files:**
- Create: `jarvis/voice/loop.py`
- Test: `tests/voice/test_loop.py`

**Interfaces:**
- Consumes: `wake.split`, `Segmenter`, `Utterance`, `Engines`, `Mic`, the core methods of Task 7, `instant.match`.
- Produces:

```python
class Voice:
    def __init__(self, jarvis, engines, mic, segmenter): ...
    async def start(self) -> None        # mic word "loading"; engines.load(); then the mic, or the reason as the mic word
    async def stop(self) -> None
    def on_frame(self, frame: np.ndarray) -> None        # on the mic thread
    async def on_utterance(self, utt: Utterance, by_key: bool = False) -> None
```

What an utterance means, decided after transcription, from the state at that moment (`r = wake.split(text)`):

| State | Heard | Jarvis does |
|---|---|---|
| any | nothing, or transcription failed | Nothing. If the state is `LISTENING`: `give_up()`. |
| `IDLE` | no name | Discards it. |
| `IDLE` | the name alone | `wake()`, `cue()`. |
| `IDLE` | name + request | `wake()`, then `heard(r)`. If the utterance was cut at the cap: `wake()` and keep `r` as the start of the next one; the kept start is dropped if the state leaves `LISTENING` with nothing more said. |
| `LISTENING` | anything | `heard(start + (r or text))`. The name alone again: `wake()`, so the 8 s start again. |
| `THINKING` | name + "cancel", "never mind" or "stop" | `heard(r)`. |
| `THINKING` | anything else | Discards it. |
| by key, any state | anything | `heard(text)` whole. |

In the follow-up window the first speech frame calls `speech_started()`, which makes the state `LISTENING`, so the row above covers it. While `jarvis.sm.mic_open` is false, frames are dropped and the segmenter is reset once. When the state machine is muted the mic stream is stopped; unmuting starts it. `Voice` sets `mic.on_frame` and `mic.on_word`; `health.mic` is `muted` while muted, else the mic's own word. Every third frame, `jarvis.level(rms)` with the frame's RMS over 32768, capped at 1. The segmenter is touched by the mic thread and (from Task 11) the loop, always under one lock. The log gets `transcribe %.2f s for %.1f s of speech` and nothing of the text.

- [ ] **Step 1: Write the failing tests** (the real `Jarvis` from `tests/conftest.py` with a `FakeSpeaker`; `FakeEngines` returns the next queued text; a fake `Mic`; `utt()` builds an `Utterance`)

```python
async def test_speech_without_the_name_leaves_no_trace(voice, jarvis, vault, caplog):   # Review Focus 2
    seen = collect(jarvis); engines.hears("I told Travis the door code is 4417")
    await voice.on_utterance(utt())
    assert seen == [] and "4417" not in caplog.text and not list(vault.raw.glob("*.md"))

async def test_a_failed_transcription_leaves_no_trace_and_no_stuck_state()   # engines raises → state IDLE, caplog has the
                                                                             # error's class name only
async def test_a_request_in_one_breath()                 # "Jervis, what time is it?" → the time is spoken; day log has it
async def test_the_name_alone_listens_and_the_next_utterance_is_the_request()   # "Jarvis." → LISTENING + ("cue",);
                                                                                # then "open Mail" → bridge got "open Mail"
async def test_the_follow_up_window_needs_no_name()      # state FOLLOW_UP; a speech frame → LISTENING; "yes" → submitted
async def test_noise_in_the_follow_up_window_goes_back_to_idle()   # Review Focus 4: a speech frame → LISTENING;
                                                         # transcription "" → IDLE, nothing submitted
async def test_a_kept_start_is_dropped_when_listening_ends()       # cut "Jarvis, write an email to", 8 s pass → IDLE;
                                                         # a later "Jarvis, what time is it" is sent alone
async def test_thinking_hears_only_cancel()              # turn in flight: "Jarvis, open Mail" → not sent;
                                                         # "Jarvis, never mind" → bridge.interrupted
async def test_a_cut_request_continues_into_the_next_utterance()   # utt(cut=True) "Jarvis, write an email to" then
                                                                   # "the accountant about Friday" → one request, joined
async def test_frames_while_speaking_are_dropped_and_the_cutter_reset()   # Review Focus 1: state SPEAKING; 40 speech
                                                         # frames → no utterance; back to FOLLOW_UP + silence → still none
async def test_muting_stops_the_mic_and_unmuting_starts_it()        # "Jarvis, stop listening" → mic.stopped; health.mic "muted"
async def test_engines_that_will_not_load_leave_typed_jarvis_working()   # load() → "no models": mic never started,
                                                         # health.mic == "no models", a typed request still answers
async def test_levels_are_published_while_the_mic_is_open()
async def test_the_log_has_timings_and_never_text(caplog)
```

- [ ] **Step 2: Run** → fail. **Step 3: Implement `Voice`.** **Step 4: Run** `uv run pytest -q` → all pass.
- [ ] **Step 5: Commit** `git commit -m "feat: wake by name: Jarvis hears a request, and forgets everything else"`

---

### Task 11: The talk key

**Files:**
- Create: `jarvis/voice/keys.py`
- Modify: `jarvis/voice/loop.py`
- Test: `tests/voice/test_loop.py` (add), `tests/voice/test_keys.py`

**Interfaces:**
- Consumes: `Gesture`, `Kind` (Task 5); `Segmenter.hold / release / tap / reset` (Task 3).
- Produces:

```python
def allowed() -> bool                                    # Input Monitoring is granted to this process
def listen(on_kind: Callable[[Kind], None], keycode: int = config.TALK_KEYCODE) -> Callable[[], None] | None
    """Starts a listen-only tap on its own thread; `on_kind` is called on that thread. Returns a stop function,
    or None when the tap cannot be made (no permission)."""
Voice.key(self, kind: Kind) -> None                      # on the loop
Voice.__init__(..., listen=keys.listen)                  # start() calls it; its callback hops to the loop, then key()
```

`Voice.key`:

| Kind | Does |
|---|---|
| `down` | `segmenter.hold()` at once (and starts the mic if muted), so no first word is lost. Engages (`jarvis.wake(key=True)`) after `KEY_GRACE_SECONDS`, or sooner if the key comes up first. |
| `chord` | Before engaging: `segmenter.reset()`, nothing else happened. After: `give_up()` and `segmenter.reset()`. |
| `tap` | Engages if not yet; `segmenter.tap()`; `jarvis.cue()`. The utterance then ends by silence, and is a request with no name needed (the state is `LISTENING`). |
| `hold_end` | Engages if not yet; `segmenter.release()` → `on_utterance(utt, by_key=True)`, or `give_up()` if nothing was kept. |

The tap watches `flagsChanged` and `keyDown` only. For `flagsChanged` it reads the key code and the flags; for `keyDown` it reads nothing and reports "another key". If macOS disables the tap for being slow, it is switched back on. `health.mic` is `on, no key` when `listen` returns None.

- [ ] **Step 1: Write the failing tests**

```python
async def test_hold_sends_what_was_said_with_no_name_and_no_silence_wait()   # down, frames, hold_end → "open Mail" submitted
async def test_tap_listens_and_a_pause_sends()                               # down, tap → LISTENING + ("cue",); speech, silence → submitted
async def test_typing_with_the_key_does_nothing():                           # Review Focus 5
    # SPEAKING; key("down"); key("chord") inside the grace → no ("stop",), no state event, segmenter reset
async def test_a_chord_after_the_grace_gives_up_quietly()                    # LISTENING → IDLE, nothing submitted
async def test_the_key_works_while_muted_and_the_mic_shuts_again()           # muted: down → mic.started; hold_end → request;
                                                                             # after the reply mic.stopped again
async def test_the_key_stops_speech()                                        # SPEAKING; down + grace → ("stop",), LISTENING
async def test_holding_with_nothing_said_gives_up()                          # hold_end, transcription "" → IDLE
async def test_without_a_listener_the_footer_says_so()                       # listen returns None → health.mic == "on, no key"
def test_no_permission_means_no_listener(monkeypatch)                        # allowed() False → listen(...) is None
```

- [ ] **Step 2: Run** → fail. **Step 3: Implement** `keys.py` (Quartz imported inside the functions; use the key code and flag bit P6 measured) and `Voice.key`. **Step 4: Run** `uv run pytest -q` → pass.
- [ ] **Step 5: Commit** `git commit -m "feat: hold or tap Right Option to talk, with typing left alone"`

---

### Task 12: Wiring, `jarvis models`, the doctor and the permissions

**Files:**
- Modify: `jarvis/cli.py`, `launchd/README.md`, `.claude/agents/jarvis.md`
- Test: `tests/test_cli.py` (add), `tests/brain/test_agents.py` (existing limits still pass)

**Interfaces:**
- Consumes: everything above.
- Produces: `jarvis models`; `voice_lines(mic: str) -> list[str]` in `cli.py`; a daemon that talks.

- [ ] **Step 1: Write the failing tests**

```python
def test_voice_lines_say_what_to_do():
    assert voice_lines("on") == []
    assert "Microphone" in voice_lines("no permission")[0]
    assert "Input Monitoring" in voice_lines("on, no key")[0]
    assert "jarvis models" in voice_lines("no models")[0]

def test_models_is_a_command(monkeypatch)                # main(["models"]) calls engines.download once
def test_the_daemon_never_downloads_at_start(monkeypatch)   # daemon() sets HF_HUB_OFFLINE=1 before _run
def test_cli_import_stays_light():                       # in a fresh interpreter: import jarvis.cli, jarvis.tui.app,
                                                         # jarvis.daemon.core → none of mlx, sounddevice, Quartz,
                                                         # openwakeword in sys.modules
async def test_a_voice_that_fails_to_start_does_not_stop_the_daemon(monkeypatch)   # Voice.start raises → API still answers,
                                                                                   # health.mic == "off", the error is logged
```

- [ ] **Step 2: Run** → fail.
- [ ] **Step 3: Implement.** `_run(vault, token, build_voice=_build_voice)`: `_build_voice` builds `Engines`, `Player`, `VoiceSpeaker`, `Mic`, `Segmenter(vad())` and returns the speaker and a function that makes the `Voice` once the `Jarvis(..., speaker=…)` exists. The existing daemon tests pass a `build_voice` that builds nothing, so no test opens a mic or a model. `voice.start()` runs as a background task so the API is up while the models load (4–14 s); `voice.stop()` runs before `jarvis.stop()`. `jarvis doctor` asks `GET /health` when jarvisd is up and prints `voice_lines(mic)`; when it is down it says the voice lines need jarvisd running (the permissions belong to that process, not to the terminal).
- [ ] **Step 4: `jarvis.md`**, under "How you talk", one line: `A request may be transcribed speech. Read past words that were plainly mis-heard ("report" for "repo"); if a wrong guess would change what you do, ask.` The part above the marker stays within 60 lines.
- [ ] **Step 5: `launchd/README.md`**: a "Permissions" section: which program macOS lists (from P6 and P7), where to allow Microphone and Input Monitoring, `launchctl kickstart -k gui/$(id -u)/com.febriel.jarvisd` afterwards, and that a Homebrew Python upgrade can reset both.
- [ ] **Step 6: Run** `uv run pytest -q` → all pass. **Step 7: Commit** `git commit -m "feat: jarvisd starts the voice; jarvis models and the doctor's voice lines"`

---

### Task 13: The HUD shows the voice

**Files:**
- Modify: `jarvis/tui/model.py`, `jarvis/tui/app.py`
- Test: `tests/tui/test_model.py`, `tests/tui/test_app.py` (add)

**Interfaces:**
- Consumes: the `level` event and `health.mic` (Task 7).
- Produces: `View.levels: tuple[float, ...]` (the last 28); the waveform; `ctrl+l`.

- [ ] **Step 1: Write the failing tests**

```python
def test_levels_keep_the_last_28():                      # 40 level events → len(view.levels) == 28, newest last
def test_levels_clear_when_the_mic_goes_off()            # a health event with mic "muted" → levels == ()

async def test_the_waveform_follows_the_levels(hud, pilot, fake):
    # levels 0.0, 0.5, 1.0 → the VOICE panel's second line ends "▁▅█"; with no levels it is 28 × "▁"
async def test_the_mic_word_shows_in_the_footer(hud, pilot, fake):
    # health.mic "on" → "MIC ● on"; "muted", "no permission", "no models", "loading" → "MIC ○ <word>"; "on, no key" → "MIC ● on, no key"
async def test_ctrl_l_turns_the_mic_off_and_on(hud, pilot, fake):
    # not muted: ctrl+l → fake.asked == ["stop listening"]; muted: → ["start listening"]
async def test_still_fits_80_by_24(hud)                  # the footer with "MIC ● on, no key" and "LIMITS ● 100%" is ≤ 80 columns
```

- [ ] **Step 2: Run** → fail. **Step 3: Implement.** Bars are `▁▂▃▄▅▆▇█` by level; the input's placeholder becomes `Type to Jarvis…   / skills   ^L mic   esc cancel`. **Step 4: Run** `uv run pytest -q` → pass.
- [ ] **Step 5: Commit** `git commit -m "feat: the HUD shows a live waveform and the mic's state"`

---

### Task 14: Tune the name match on Febriel's voice 👤

**Files:**
- Create: `spikes/09-voice/wake_tune.py`
- Modify: `jarvis/config.py`, `tests/voice/test_wake.py`, `docs/spikes/findings.md`

**Interfaces:**
- Consumes: `Segmenter`, `Engines`, `wake.sounds_like_name`.
- Produces: final `WAKE_SIMILARITY`, `WAKE_STRICT`, `WAKE_ALSO`.

- [ ] **Step 1: Write `wake_tune.py`.** It listens live. For each utterance it keeps, in memory only: whether the current rule woke, and any of the first three words that scored ≥ 0.6, with its score. No audio, no other words. It prints the tally at the end and writes nothing to disk.
- [ ] **Step 2: 👤 Positives.** Unload the login agent first (one mic owner). Febriel says "Jarvis" or "Hey Jarvis" plus a short request 30 times, 1–3 m from the Mac, facing it and turned away. Bar: 27 of 30 wake.
- [ ] **Step 3: 👤 Negatives.** 30 minutes of video, music and people talking at normal volume. Bar: at most 1 wake.
- [ ] **Step 4: Adjust.** From the near-miss words: lower `WAKE_SIMILARITY`, or add a word he is reliably heard as to `WAKE_ALSO`, only if Step 3's tally shows it never appeared in the negatives. Put each word added or newly rejected into `test_wake.py`'s lists. If the bar is still missed, record the numbers; the key is the fallback (spec §6.1).
- [ ] **Step 5: Record** the tallies and the final rule in the findings ("Plan 3 results"). Run `uv run pytest -q` → pass.
- [ ] **Step 6: Commit** `git commit -m "feat: the name match, tuned on Febriel's voice"`

---

### Task 15: End to end by voice, then the checkpoint 👤

**Files:**
- Modify: `docs/spikes/findings.md`, `docs/superpowers/specs/2026-11-10-jarvis-design.md`, `PROJECT.md`, this plan (amendments)

- [ ] **Step 1: Restart the login agent** (`launchctl kickstart -k gui/$(id -u)/com.febriel.jarvisd`), 👤 grant Microphone and Input Monitoring when asked, restart once more. `jarvis doctor` → `Ready.`; the HUD footer → `MIC ● on`.

- [ ] **Step 2: 👤 Run the rows, record each in the findings.** A row that fails gets a failing test first, then the fix, then the row again.

| # | Do | Pass when |
|---|---|---|
| 1 | "Jarvis, what time is it" ×10 | Spoken each time. Median end of speech → first sound, from the log, recorded. |
| 2 | A small request for Sonnet ("Jarvis, what's the capital of Australia") ×10 | Median end of speech → first word ≤ 2.5 s (§11). If over: set `END_SILENCE_SECONDS` to 0.6, repeat with 20 requests, keep 0.6 only if none was cut off mid-sentence. |
| 3 | "Jarvis" alone, wait for the tone, then a request | Tone within about 1 s; the request is answered. Nothing said for 8 s → back to `IDLE`. |
| 4 | Ask something that makes Jarvis ask back; answer without the name inside 6 s; then again after 6 s | First is taken; second needs the name. |
| 5 | "Jarvis, delete the file test.txt on my Desktop" (a scratch file) | The question is spoken and in the HUD; "yes" deletes it; "no" on a second run leaves it. |
| 6 | Hold Right Option, speak, release | Answered with no name and no silence wait. |
| 7 | Tap Right Option, speak, pause | Tone, then answered. |
| 8 | "Jarvis, stop listening"; say "Jarvis, what time is it"; hold the key and ask; `ctrl+l` in the HUD | Orange mic indicator off and `MIC ○ muted`; the name does nothing; the key works; `ctrl+l` brings it back. |
| 9 | Ask for a long answer ("read me today's log") at normal volume, five times | Jarvis never answers itself; nothing is taken in the follow-up window while the room is quiet. |
| 10 | During a long answer: Escape; next time: the key. During a slow request: "Jarvis, never mind" | Silence within 0.2 s each time; the key leaves it listening; the request is cancelled. |
| 11 | Five minutes of ordinary talk and a video, never saying the name | `jarvisd.log`, the day's log and the HUD hold none of it. |
| 12 | Connect and disconnect AirPods (or sleep and wake the Mac) mid-run | `MIC` leaves `on` and comes back within 30 s without a restart. |
| 13 | Type é, ñ and a Right Option shortcut in another app while Jarvis is idle and while it speaks | Nothing happens in Jarvis. |
| 14 | Leave it idle ten minutes, quiet room; then ten with a video on | CPU a few percent of one core (§11: 2 % and 4 % measured). |
| 15 | Type a request in the HUD; start a job for a worker by voice and wait | Both the typed reply and the worker's result are spoken. |
| 16 | Stop jarvisd with Wi-Fi off, start it | Voice comes up from the cache; instant answers work by voice. |

- [ ] **Step 3: Amend the spec** with what Febriel confirmed and what was measured, each dated: §6.1 (the key, the key in every state, cancel while speaking, the name rule, muted closes the mic, the tone, the 8 s and 15 s / 60 s limits, mac replies always spoken), §7 (`MIC` words, `ctrl+l`, the `level` event in §15's list), §11 (the measured spoken figure), §13 (which program gets the two grants).
- [ ] **Step 4: Update `PROJECT.md`** (status, measured figures, decisions, dead ends) and copy this plan and its results to Obsidian (`Astro/Claude Code/Jarvis Plan 3 Voice.md`, `Jarvis Plan 3 Results.md`), linked from `[[Jarvis Design]]`.
- [ ] **Step 5: One review pass over the whole branch**, with the Review Focus list and the privacy rule first. Findings go to Febriel before any fix.
- [ ] **Step 6: Commit** `git commit -m "docs: Plan 3 results, spec amendments and PROJECT.md status"`
