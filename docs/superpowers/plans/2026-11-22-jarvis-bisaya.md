# Jarvis Bisaya Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jarvis understands Febriel's Bisaya and his Bisaya-accented English. Step one is a hint to the brain. Step two is a test of Cebuano listeners on his voice. If one passes, step three adds a second listener that runs on every spoken request.

**Architecture:** Parakeet still decides the wake word, the fixed phrases, "cancel" and yes/no. Once an utterance has become a request, it also goes to the winning Cebuano listener, and the brain gets both transcripts: Parakeet's text plus a line `(Bisaya ear: "…")`. The test lives in `spikes/10-bisaya/` and touches no jarvisd code.

**Tech Stack:** Python 3.12, `uv`, parakeet-mlx, `transformers` + `torch` (MPS; already in the venv), `mlx-whisper` (spike only, through `uv run --with`), `claude -p` for the dry-run judge, pytest.

**Spec:** `docs/superpowers/specs/2026-11-20-jarvis-bisaya-design.md` (approved 2026-11-22). Read it first.

## Global Constraints
- Audio never leaves the Mac. No cloud speech service and no API keys. `claude -p` runs on the subscription login.
- **Ask Febriel before every download or install.** Give the repo or package name, the source, and the size (read from the repo's file list). Wait for his yes.
- Recordings live only in `spikes/10-bisaya/data/`, which is git-ignored, and are never committed. `docs/spikes/findings.md` gets counts, timings and short mishearing examples, never his full requests.
- Bars, from the spec:
  - Bisaya or mixed: the meaning is kept in **≥ 10 of 12**.
  - English: right at least as often as with Parakeet alone.
  - One-breath wakes: **3 of 3**.
  - Extra time: **≤ 1.5 s** for a 5 s utterance, warm, on the M4.
  - Resident memory of the second listener: **≤ ~1.5 GB**.
- Spoken yes/no answers, instant phrases, waking, and "cancel" while thinking use **Parakeet's text only**. A Bisaya word never counts as yes.
- Speech without the name never reaches the second listener.
- Replies stay in English.
- jarvisd loads models offline (`HF_HUB_OFFLINE=1`). Only `jarvis models` downloads.
- **Tasks 5–7 start only once Plan 3 is finished** (its Task 15 review pass is closed), and **only if Task 4 found a winner** that Febriel okayed.
- Code changes take effect after `launchctl kickstart -k gui/$(id -u)/com.febriel.jarvisd`. Ask Febriel first, because a kickstart interrupts anything that's running.
- Tests: `uv run pytest -q` (offline: `uv run --frozen --no-sync pytest -q`).
- Commits carry no Claude credit lines (no `Co-Authored-By: Claude`, no "Generated with").

## Review Focus
1. **The Bisaya listener raises or hangs mid-request.** The request still goes out with Parakeet's text alone, and no state gets stuck. Test in Task 7.
2. **A yes/no is waiting** and Parakeet hears "oh" while the Bisaya ear hears "oo". Nothing is approved. Test in Task 6.
3. **The model is missing or fails to load at start.** Voice and typed Jarvis work, health shows `"bisaya": "missing"`/`"error"`, and doctor says what to do. Test in Task 5.
4. **Speech without the name, while idle.** The second listener is never called. Test in Task 7.
5. **A request cut at the length limit arrives in two utterances.** The Bisaya text covers both pieces, in order. Test in Task 7.

---

### Task 1: The hint

**Files:**
- Modify: `.claude/agents/jarvis.md` (the "A request may be transcribed speech…" bullet under "How you talk")
- Test: `tests/brain/test_agents.py`

**Interfaces:** none.

- [x] **Step 1: Write the failing test** `test_jarvis_knows_febriel_speaks_bisaya`. It takes the body's own part (before `VENDORED_MARK`) and asserts that `"Bisaya (Cebuano) accent"` and `"Reply in English even when he speaks Bisaya"` are both in it. The existing `<= 60` line test must still pass.
- [x] **Step 2:** Run `uv run pytest tests/brain/test_agents.py -q`. Expected: the new test FAILS.
- [x] **Step 3:** Replace the bullet with the spec's Part 1 text, word for word. Keep it one bullet.
- [x] **Step 4:** Run `uv run pytest -q`. Expected: all PASS.
- [x] **Step 5:** Commit: `git add .claude/agents/jarvis.md tests/brain/test_agents.py && git commit -m "feat: Jarvis knows Febriel speaks Bisaya and Bisaya-accented English"`.
- [x] **Step 6 👤:** Ask Febriel whether to kickstart jarvisd now. Plan 3's session may be live-testing. *(2026-11-22: "Not now"; the hint goes live at the next kickstart.)*

### Task 2: The recorder 👤

**Files:**
- Create: `spikes/10-bisaya/record.py`

**Interfaces:**
- Produces:
  - `spikes/10-bisaya/data/<kind>-<NN>.wav`: 16 kHz mono int16, where `kind` is one of `bisaya`, `english`, `wake`.
  - `spikes/10-bisaya/data/meant.json`, shaped `{"<file>.wav": {"kind": str, "meant": str}}`.

- [x] **Step 1:** Write `record.py` on the same path as `spikes/09-voice/wake_tune.py` (`Mic`, `Segmenter(engines.vad())`). It loops over 12 `bisaya`, 8 `english` and 3 `wake` prompts:
  - Print the kind. For `wake`, add: *say "Jarvis, …" then a Bisaya request in one breath*.
  - Take the next utterance and write it with `soundfile`.
  - Ask Febriel to type what he said. Press Enter to keep it; type `r` to record again.
  - Write `meant.json` after every item, so a stop loses nothing.
  - Stop the mic while he types.
- [x] **Step 2:** Check that the folder is ignored: `git check-ignore spikes/10-bisaya/data/x.wav` must print the path.
- [x] **Step 3 👤:** Febriel runs `uv run python spikes/10-bisaya/record.py` and speaks the way he really talks to Jarvis. Expected: 23 WAV files, and 23 entries in `meant.json`. *(Done 2026-11-22. He asked for lines to read, so `record.py` shows each one and Enter keeps it. On his ask ("it should also support and understand me when saying bisaya-english"), 6 mixed lines were added: 29 in all.)*
- [x] **Step 4:** Commit only the script: `git add spikes/10-bisaya/record.py && git commit -m "spike: record Febriel's Bisaya and English requests"`.

### Task 3: The listeners 👤

**Files:**
- Create: `spikes/10-bisaya/listeners.py`, `spikes/10-bisaya/listen.py`

**Interfaces:**
- Produces:
  - `listeners.LOADERS: dict[str, Callable[[], Callable[[np.ndarray], str]]]`, where each loaded function takes 16 kHz int16 PCM and returns text. Keys: `parakeet`, `buzz`, `mms`, `turbo`, and `omni` if it survives Step 1. Task 5 copies the winner's loader.
  - `data/results-<name>.json`, shaped `{"load_s": float, "rss_mb": float, "files": {"<file>.wav": {"text": str, "seconds": float, "audio_s": float}}}`.

- [x] **Step 1: Check before downloading.**
  - BuzzASR/cebuano: read its model card for the license and the expected input.
  - Omnilingual ASR: look for `ceb_Latn` on its supported-language list, and check whether `omnilingual-asr` installs on macOS arm64. If either check fails, drop `omni` and note why.
- [x] **Step 2 👤 Downloads.** Ask Febriel to okay each one, with name, source and size:
  - `BuzzASR/cebuano`
  - `facebook/mms-1b-all`
  - `mlx-community/whisper-large-v3-turbo`
  - the `mlx-whisper` package (spike only: `uv run --with mlx-whisper`)
  - if it survived Step 1: the Omnilingual CTC 300M or 1B checkpoint and its package

  Download only what he okays. *(He okayed BuzzASR and MMS only. Turbo and Omnilingual are dropped. The models are stored on his external SSD, his choice. Later, on his "shrink BuzzASR", `mlx-whisper` and mlx-examples' `convert.py` were added.)*
- [x] **Step 3:** Write the loaders:
  - `parakeet`: the same call as `jarvis/voice/engines._load_parakeet`.
  - `buzz`: a `transformers` ASR pipeline on `mps`, fp16.
  - `mms`: `Wav2Vec2ForCTC` with `tokenizer.set_target_lang("ceb")` and `model.load_adapter("ceb")`.
  - `turbo`: `mlx_whisper.transcribe` with no language set. *(not okayed: dropped)*
  - `omni`: per its README. *(not okayed: dropped)*
  - *(added)* `buzz8`/`buzz4`, MLX 8/4-bit, and `buzz8w10`/`buzz4w10`/…, with an encoder window of at least 10 s.
- [x] **Step 4:** Write `listen.py --listener NAME`. It runs one listener per process, so the memory figures stay clean:
  - Load it, timing `load_s`.
  - Warm it once on 1 s of silence.
  - Transcribe every WAV in `data/`, timing each one.
  - Record `rss_mb` from `resource.getrusage(RUSAGE_SELF).ru_maxrss` (bytes on macOS).
  - Write `results-NAME.json`.
- [x] **Step 5:** Run `uv run python spikes/10-bisaya/listen.py --listener NAME` for each name (with `uv run --with mlx-whisper` for `turbo`). Expected: one results file per listener, with 23 entries each.
- [x] **Step 6:** Commit the two scripts only.

### Task 4: The judge and the verdict 👤

**Files:**
- Create: `spikes/10-bisaya/judge.py`
- Modify: `docs/spikes/findings.md` (new section "Bisaya listener"), `PROJECT.md`

**Interfaces:**
- Consumes: `data/meant.json` and `data/results-*.json` (Tasks 2–3), and `jarvis.brain.env.clean_env()`.
- Produces: the winner's name, or "none". If there is a winner, `config.BISAYA_MODEL`'s value and its loader for Task 5.

- [x] **Step 1:** Write `judge.py`. For each recording, and for each case (`parakeet` alone, then Parakeet plus each other listener), it runs a dry-run `claude -p` and appends the reply to `data/judged.md`, next to `meant`. The run:
  - uses `clean_env()`, `--model sonnet` *(the front door's model: Haiku, then Sonnet at low effort; see findings)*, `--tools ""`, `--strict-mcp-config`, and `--system-prompt` set to `jarvis.md`'s own part with the Part 3 sentence added;
  - sends a message built the way Task 6's `with_alt` builds it, followed by: *"Dry run: do nothing. In one line, say what you would do."*

  That is about 115 short subscription calls. Run them one at a time.
- [x] **Step 2:** Score them by hand, judging each line in `judged.md` against `meant`:
  - **Kept:** Claude would do what Febriel meant.
  - **Lost:** it would do something else, or not understand.
  - **Unsure:** it's unclear which.

  The unsure ones go to Febriel.
- [x] **Step 3: Measure.**
  - One-breath wakes: `wake.split(parakeet text) is not None` for the 3 `wake` files.
  - Extra time at 5 s: a least-squares line of `seconds` against `audio_s`, evaluated at 5.0.
  - Memory: `rss_mb`.
- [x] **Step 4:** Write the findings section: one table row per listener (Bisaya kept /12, English kept /8 vs Parakeet's, wakes /3, extra s at 5 s, MB, license), plus up to five short mishearing examples. The winner is the listener that meets every bar with the least extra time; a tie goes to the higher Bisaya score.
- [ ] **Step 5 (only if every listener misses the time bar):** *(Skipped: MMS met the time bar. Febriel chose to shrink BuzzASR instead; see findings.)* Search Hugging Face for small or medium Whisper models fine-tuned on Cebuano, at most three. Ask Febriel before each download. Run each through Task 3 Steps 3–5 and this task's Steps 1–4.
- [x] **Step 6 👤:** Show Febriel the table and get his okay on the winner. *(2026-11-22: BuzzASR MLX 8-bit, ≥ 10 s window; memory ~2.3 GB over the bar, accepted.)*
  - **No winner, or he says no:** record "Bisaya listener: dead end (date, why)" in `PROJECT.md`'s Dead ends, and mark Tasks 5–7 skipped. Go to Task 8.
- [x] **Step 7:** Commit `judge.py`, `findings.md` and `PROJECT.md`. *(`judge.py` committed. `findings.md` and `PROJECT.md` are left uncommitted: they also hold the Plan 3 session's uncommitted edits.)*

### What Task 4 found, for Tasks 5–7 (2026-11-22)
- **The winner:** BuzzASR/cebuano converted to MLX at 8-bit, in a local folder: `/Volumes/PortableSSD/Jarvis/mlx/buzzasr-cebuano-q8` (`weights.safetensors` + `config.json`). It is not a Hub repo, so `config.BISAYA_MODEL` is that path. `download()` cannot fetch it: it needs the BuzzASR snapshot (also on the SSD) and mlx-examples' `whisper/convert.py` (`-q --q-bits 8`, then rename `model.safetensors` → `weights.safetensors`). With the SSD unplugged, it's `"missing"`.
- **Loader:** `listeners._buzz_short(8, 10)`. It uses mlx-whisper's `decode` with `language="tl"`, greedy, and an encoder window of at least 10 s (the positional embedding is sliced to fit). It needs `mlx-whisper==0.4.3` as a main dependency, which is Febriel's okay in Task 5.
- **Threads:** it is MLX, so it runs on the existing `self._pool`, adding about 0.6 s there.

### Task 5: The third model in `Engines`

**Files:**
- Modify: `jarvis/config.py`, `jarvis/voice/engines.py`, `jarvis/daemon/core.py` (health), `jarvis/cli.py` (doctor), `pyproject.toml` (only if the winner needs a package that isn't already a main dependency, okayed by Febriel)
- Test: `tests/voice/test_engines.py`, `tests/test_cli.py`, `tests/daemon/` (the health test that already exists)

**Interfaces:**
- Produces:
  - `config.BISAYA_MODEL: str | None`, the winner's repo, where `None` means off.
  - `engines._load_bisaya() -> Callable[[np.ndarray], str]`, raising `ModelsMissing` when the repo isn't cached.
  - `Engines(load_stt=…, load_tts=…, load_bisaya=_load_bisaya)`.
  - `Engines.bisaya: Literal["on", "off", "missing", "error"]`.
  - `async Engines.transcribe_bisaya(pcm: np.ndarray) -> str | None`, which returns `None` unless `bisaya == "on"`.
  - `JarvisCore.set_bisaya(word: str) -> None`, and `"bisaya"` in the health body.
  - `cli.bisaya_lines(word: str) -> list[str]`.

- [ ] **Step 1: Write the failing tests:**
  - `test_a_missing_bisaya_model_leaves_voice_on`: a `load_bisaya` that raises `ModelsMissing` gives `load()` → `None`, `bisaya == "missing"`, and `transcribe_bisaya` → `None`, while `transcribe` still works.
  - `test_a_broken_bisaya_model_is_error`: a `load_bisaya` that raises `RuntimeError` gives `bisaya == "error"`.
  - `test_bisaya_off_when_unset`: with `BISAYA_MODEL = None`, the loader is never called and `bisaya == "off"`.
  - The existing thread test, extended: `transcribe_bisaya` runs on one fixed worker thread.
  - `test_doctor_bisaya_lines`: `"missing"` → `["the Bisaya listener is missing: run jarvis models"]`; `"error"` → one line that names `jarvisd.log`; `"on"` and `"off"` → `[]`.
  - The health body holds `"bisaya"`.
- [ ] **Step 2:** Run `uv run pytest tests/voice/test_engines.py tests/test_cli.py -q`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
  - `_load_bisaya`: the winner's loader from `spikes/10-bisaya/listeners.py`. Warm it in `Engines._load` on 1 s of silence.
  - A failure in the Bisaya loader never fails `load()`: log the error's type and set `bisaya`.
  - Threads: an MLX winner runs on the existing `self._pool`; a torch winner runs on a second single-thread pool.
  - `download()` also fetches `BISAYA_MODEL` when it's set.
  - Voice's `start()` calls `jarvis.set_bisaya(engines.bisaya)` after loading.
  - `doctor()` adds `bisaya_lines(health["bisaya"])`.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: all PASS.
- [ ] **Step 5:** Commit: `git commit -m "feat: jarvisd loads the Bisaya listener; voice works without it"`.

### Task 6: Two transcripts to the brain

**Files:**
- Modify: `jarvis/daemon/core.py` (`heard`, `submit`, plus a new module function `with_alt`)
- Test: `tests/daemon/` (the file that tests `submit` and `heard`)

**Interfaces:**
- Consumes: nothing from Task 5.
- Produces:
  - `with_alt(text: str, alt: str | None) -> str`: returns `text`, or `f'{text}\n(Bisaya ear: "{alt}")'` unless `alt` is empty, or equals `text` once both are lowercased and stripped of everything but letters, digits and single spaces.
  - `JarvisCore.heard(text: str, alt: Awaitable[str | None] | None = None) -> None`: drives `SPEECH_END` at once. Its task awaits `alt` (an exception, or a wait longer than `config.BISAYA_WAIT_SECONDS = 5.0`, → `None`, logging only the error's type), then calls `submit`.
  - `JarvisCore.submit(text: str, channel: Channel, alt: str | None = None) -> Reply`: `instant.match`, the ask answers, `_last_heard` and the `"heard"` event all use `text`. The `_Request` and its `Tracker` (so `raw/` too) get `with_alt(text, alt)`.

- [ ] **Step 1: Write the failing tests:**
  - `test_with_alt_adds_the_line` and `test_with_alt_skips_a_same_or_empty_alt`: `("Open Safari.", "open safari")` → `"Open Safari."`; an alt of `""` → the text unchanged.
  - `test_the_brain_gets_both_lines`: `submit("set a timer", "mac", alt="butangi ug timer")` puts `set a timer\n(Bisaya ear: "butangi ug timer")` in the bridge's sent text and in `raw/`.
  - `test_bisaya_never_answers_a_gate_question` (Review Focus 2): with a mac yes/no pending, `submit("oh", "mac", alt="oo")` does not resolve it as yes, while `submit("yes", "mac", alt="oo")` does.
  - `test_instant_phrases_ignore_the_alt`: `submit("what time is it", "mac", alt="unsa na oras")` gives the instant time reply, and the bridge gets nothing.
  - `test_a_failed_alt_still_sends`: `heard("open mail", alt=<a future that raises>)` → the brain gets `"open mail"`, and the state leaves LISTENING.
- [ ] **Step 2:** Run the daemon tests. Expected: the new ones FAIL.
- [ ] **Step 3:** Implement to the interfaces above.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: all PASS.
- [ ] **Step 5:** Commit: `git commit -m "feat: the brain gets the Bisaya transcript beside Parakeet's; answers and instant phrases never do"`.

### Task 7: Voice sends requests to the second listener 👤

**Files:**
- Modify: `jarvis/voice/loop.py` (`on_utterance`, `_act`, the kept-start state), `.claude/agents/jarvis.md` (the second-transcript sentence)
- Test: `tests/voice/test_loop.py`, `tests/brain/test_agents.py`

**Interfaces:**
- Consumes: `Engines.transcribe_bisaya` (Task 5) and `JarvisCore.heard(text, alt=…)` (Task 6).
- Produces: nothing new.

- [ ] **Step 1: Write the failing tests.** Give `FakeEngines` a queue for `transcribe_bisaya` and a call counter.
  - `test_a_request_carries_the_bisaya_text`: one breath, "Jarvis, ablihi ang mail" → `heard` gets the Bisaya text.
  - `test_the_follow_up_and_the_key_carry_it_too`: the LISTENING path and the `by_key` path.
  - `test_speech_without_the_name_never_reaches_the_bisaya_ear` (Review Focus 4): the counter stays at 0.
  - `test_cancel_and_answers_skip_the_bisaya_ear`: THINKING plus "cancel", and a bare ack in the follow-up window → counter 0.
  - `test_a_cut_request_joins_both_bisaya_pieces` (Review Focus 5): the two pieces come out as one Bisaya text, joined by a space, in order.
  - `test_a_failing_bisaya_ear_still_sends` (Review Focus 1): `transcribe_bisaya` raises → the request is sent with Parakeet's text alone.
  - In `test_agents.py`, extend the Task 1 test: the own part also holds `"(Bisaya ear: …)"`.
- [ ] **Step 2:** Run `uv run pytest tests/voice/test_loop.py tests/brain/test_agents.py -q`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
  - Wherever `_act` turns an utterance into a request (the `by_key` path, the LISTENING request, and the IDLE one-breath request), call `heard(text, alt=asyncio.ensure_future(engines.transcribe_bisaya(pcm)))`. `_act` needs the PCM, so pass it in.
  - The cancel path keeps calling `heard(r)` with no alt.
  - For a cut request, keep the first piece's future beside `_start`, drop it wherever `_start` is dropped, and join its result with the second piece's.
  - Add the spec's Part 3 sentence to the hint bullet in `jarvis.md`, word for word.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: all PASS.
- [ ] **Step 5:** Commit: `git commit -m "feat: every spoken request also goes to the Bisaya listener"`.
- [ ] **Step 6 👤 Live check.**
  - Run `jarvis models`; it downloads the winner, which Febriel already okayed in Task 3.
  - With his okay, kickstart jarvisd. `jarvis doctor` must not mention Bisaya.
  - Febriel says 5 requests in Bisaya, 3 in English, and 1 yes/no answer. Expected: each one is acted on as meant; English is no slower than the new limit; the yes/no answer works only in English.
  - Record the rows in `findings.md`, under "Bisaya listener, live".

### Task 8: The review pass and the records

**Files:**
- Modify: `PROJECT.md`, `docs/superpowers/specs/2026-11-20-jarvis-design.md` (amend §6, speech-to-text: the second listener), `/Users/febrielotud/Obsidian/Astro/Claude Code/Jarvis Bisaya Design.md` (re-copy), new `Jarvis Bisaya Plan.md` and `Jarvis Bisaya Results.md` beside it with `[[Jarvis Design]]` links

- [ ] **Step 1:** Run **one** review pass over everything this plan committed: a fresh reviewer on the most capable model. Its findings go to Febriel **before any fix**.
- [ ] **Step 2:** Fix what Febriel picks, using TDD, one commit per fix.
- [ ] **Step 3:** Update `PROJECT.md`: status, the second listener under Measured (or the dead end), and the Obsidian copies list. Amend the main spec. Copy everything to Obsidian.
- [ ] **Step 4:** Commit: `git commit -m "docs: Bisaya results, spec amendment and project memory"`.
