# Plan 1 spike findings

One section per spike: what was run, the numbers, pass or fail against the plan's bar, and what it means for the design.

## Spike 1 — Claude Code as the brain, on the subscription (Task 6)

Run 2026-11-10 (blocked: CLI not logged in) and 2026-11-13 (after Febriel signed the CLI in). Claude Code 2.1.322, Max subscription. Scripts: `spikes/01-brain/`. Every child `claude` was started with a scrubbed environment (`clean.py`: HOME, USER, LOGNAME, SHELL, TERM, LANG, TMPDIR and a fixed PATH; no `CLAUDE_*` / `ANTHROPIC_*`), as `jarvisd` will.

| Step | Bar | Measured | Verdict |
|---|---|---|---|
| 1 Long-lived stream-json on the subscription | Both answered in one process; second remembers the first; init shows subscription, no API key | One PID, one `session_id`; second reply "PLUM" (remembered); `apiKeySource: "none"`; `ANTHROPIC_API_KEY` unset | **Pass** |
| 2 Agents on the expected models | Each agent on its expected model | `jarvis` → `claude-sonnet-5-5`; `triage` (`model: claude-opus-5-5`) → `claude-opus-5-5`; `quick` (default haiku) dispatched with per-call `model: "sonnet"` → `claude-sonnet-5-5` | **Pass** |
| 3 Permission bridge | Held until the script answers; deny prevents; allow runs | `PermissionRequest` hook: held 5.0 s, deny → no file, allow → file created. `--permission-prompt-tool` (stdio MCP server): held 5.0 s, same deny/allow behaviour. Test file deleted. | **Pass (both)** |
| 4 Hook in a second session via `--settings` | Same hook fires | Session in `/tmp` with `--settings spike-settings.json`: hook fired (`cwd: /private/tmp`), held 5.0 s, denied | **Pass** |
| 5 Front door free while a worker runs | Front door answers before the worker finishes | Background `slow` subagent (60 s) dispatched at 8.9 s; new message at 25.8 s answered at 31.3 s (5.5 s); worker finished at 89.6 s and the process announced it unprompted | **Pass** — one process serves both channels |
| 6 Spawned sessions that survive the parent | Record which works | `claude --bg`: refused — "Workspace not trusted" (needs the trust prompt accepted once per folder in interactive `claude`). Detached `claude -p` (`start_new_session=True`, parent exits at once): completed, then `claude -p --resume <id>` answered from memory under the same session id | Detached `-p` + `--resume` **works**; `--bg` **untested** (👤 trust) ; Code-tab visibility **unverified** (👤) |
| 7 First text token, ten runs | Record | Warm process, `--include-partial-messages`: median **0.79 s** (runs 2–10: 0.72–0.90 s); run 1 incl. process start 1.63 s; whole short reply 1.0–1.5 s | Recorded |

### Payloads (for Plan 2's bridge)
- `PermissionRequest` hook stdin: `session_id`, `prompt_id`, `transcript_path`, `cwd`, `permission_mode`, `effort`, `hook_event_name`, `tool_name`, `tool_input` (Bash: `command`, `description`), `permission_suggestions` (e.g. `addDirectories`, `setMode acceptEdits`). Reply on stdout: `{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}` or `{"behavior": "deny", "message": "..."}`. Timeout set per hook (`"timeout": 30` used; default 600 s).
- `--permission-prompt-tool` arguments: `tool_name`, `input`, `tool_use_id`; reply text `{"behavior": "allow", "updatedInput": {...}}` or `{"behavior": "deny", "message": "..."}`.
- Background work events in the stream: `system/background_tasks_changed`, `task_started`, `task_progress`, `task_notification`, `task_updated` (status `completed`). The HUD queue can be fed from these.

### What it means for the design
- **Engine choice holds.** The CLI runs on the subscription in non-interactive stream-json mode, with agents, pinned Opus 5.5 triage, per-call worker tiers, hooks and background workers. No API key anywhere.
- **Bridge: use the `PermissionRequest` hook** passed with `--settings`. It needs no MCP server and travels to spawned sessions. Keep `--permission-prompt-tool` as the fallback.
- **Caveat for the gate:** `PermissionRequest` fires only when Claude Code itself would ask. Commands Claude Code already allows never reach it. Plan 2 should run the gate from a `PreToolUse` hook (sees every tool call) and use `PermissionRequest` only for the yes/no hand-off, or make sure no allow rules are loaded. (Not measured here; design note.)
- **Load only Jarvis's settings.** Febriel's user `settings.local.json` holds allow rules (e.g. `Bash(cp *)`) and his plugins/MCP servers (chatcut, rea, n8n) load into every session. `jarvisd` must start `claude` with `--setting-sources project` (no `user`), `--settings <jarvis settings>`, and `--strict-mcp-config --mcp-config <jarvis MCP list>`.
- **Clean environment.** A Claude session's environment carries `CLAUDE_CODE_SIMPLE=1` (what `--bare` sets), `CLAUDE_CODE_*` host-auth variables and an `ANTHROPIC_BASE_URL` proxy. Inherited, they broke auth in the first run. `jarvisd` must scrub them.
- **One process, both channels.** Step 5 shows the front door stays free while workers run, so Mac and phone can share one process (as the spec says).
- **Session spawning (spec §6.2, "left to the builder"):** detached `claude -p` + `--resume <session_id>` works now and needs no trust prompt. `claude --bg` needs each project folder trusted once in interactive `claude`.
- **Latency budget:** 0.79 s to first token leaves about 1.7 s of the 2.5 s target (§11) for end-of-speech, speech-to-text and the first spoken audio. Measured with a bare Sonnet prompt; the real `jarvis` agent prompt and memory index will add some.
- 👤 Open: accept the trust prompt (run `claude` once in `~/Developer/Project Jarvis/spikes/01-brain`) so `--bg` can be tried; check whether `--bg` and detached sessions show in the Claude app's Code tab.

## Spike 2 — microphone and wake word (Task 7)

Run 2026-11-13. openWakeWord 0.6.0 (`hey_jarvis_v0.1`, ONNX), onnxruntime 1.32.0, sounddevice 0.5.6, all in the `spike` dependency group. MacBook Air microphone, 16 kHz mono, 80 ms frames, threshold 0.5. Script: `spikes/02-wake/wake.py`. No audio stored; the one synthetic WAV was deleted after use.

| Check | Bar | Measured | Verdict |
|---|---|---|---|
| Pipeline, offline | — | macOS `say` "Hey Jarvis" (Daniel, Samantha, Alex) through the model: max score 0.995–0.999 | Works |
| Live mic, speakers → mic | — | 3 of 3 detected (0.62–0.91) | Works |
| 👤 Febriel, "Hey Jarvis" ×10 from ~2 m | 9 of 10 | **3 of 10** (0.64, 0.74, 0.77); one near miss at 0.36; the rest scored ≈0. An earlier 5-minute run caught none. | **Fail** |
| Inference cost | — | 4–8 ms per 80 ms frame (p99 9.6 ms) | — |
| CPU while listening | "a few percent of one core" (§11) | 6.3–9.2 % of one core | Borderline |
| Mic permission | — | Already granted to the Claude app (no prompt); the launchd case is still untested | — |

### What it means
- The model and the audio path work; the pretrained "hey jarvis" model does not recognise Febriel's voice reliably at 2 m on the laptop mic. Lowering the threshold will not fix it: most attempts scored near 0, not just under 0.5.
- **Decision for Febriel** (see options in the report): train a custom model, wake by transcribing short speech locally, or use a third-party engine. Hold-to-talk (added to the spec today) is the guaranteed fallback either way.
- **Step 4, mic from a launchd agent: Pass.** A temporary user agent (`launchctl bootstrap gui/<uid>` from a plist in the spike's temp folder, then `bootout`) ran `wake.py` for 20 s and got real audio (RMS 2386–2728), with no permission prompt. `jarvisd` can run as a login agent; no Terminal login item is needed. Python is Homebrew's `python3.12`.
- **Step 5, CPU while listening:** 6.3–9.8 % of one core with openWakeWord. Recorded; the transcription wake approach is measured in Spike 3.
- **Step 3 (30-minute false-trigger run)** moves to Spike 3, because Febriel chose wake-by-transcription (2026-11-13) after the training attempt below.

### Custom training attempt (Febriel chose "train on my voice")
- Recorded with `record_session.py` (Mac-guided, chime per take): 30 × "Hey Jarvis", 30 × "Jarvis" (moving 1–3 m, turned toward and away), 2 min normal talk, 1 min "quiet" room (which had speech/TV in it: RMS p90 1277 vs talk p90 1069). Audio kept in `spikes/02-wake/tmp/rec/` (git-ignored) until the spike ends.
- Usable takes (peak ≥ 2.5× the take's own background): 13/30 "Hey Jarvis", 20/30 "Jarvis". The rest are barely above the room at the mic.
- Lite trainer (`train_wake.py`): small MLP over openWakeWord's 16×96 embedding window. Positives: his takes + macOS voices (12 English voices × 3 rates), augmented with room noise, gain and speed. Negatives: his talk and room, `say` confusables, 70 % of openWakeWord's 10.7 h validation features. Held out: 20 % of his takes and 3.2 h of the validation audio.

| Model | Held-out recall @0.5 / 0.7 / 0.9 | False wakes per hour @0.5 / 0.7 / 0.9 | Verdict |
|---|---|---|---|
| custom "Hey Jarvis" | 0.33 / 0.33 / 0.33 | 66 / 54 / 36 | **Fail** |
| custom "Jarvis" | 0.33 / 0.17 / 0.08 | 65 / 39 / 17 | **Fail** |

- Diagnostic, pretrained `hey_jarvis` on his recorded takes: clear takes (peak ≥ 5× background) 7/17 over 0.5 (scores up to 1.00); faint takes 0/12. So the pretrained model catches about half his clear takes and none of the far ones.
- What it means: about 30 usable positives and 12 synthetic voices are far too little data; openWakeWord's own recipe uses thousands of synthetic speakers (Piper) and 2,000 h of negatives. Distance on the laptop mic also matters: at 2–3 m or turned away his speech is barely above the room.

## Spike 3 — speech-to-text, end of speech, and wake by transcription (Task 8)

Run 2026-11-13/14. Engines attached with `uv run --with parakeet-mlx --with faster-whisper` (no change to `pyproject.toml`). Models: Parakeet `mlx-community/parakeet-tdt-0.6b-v2` (English, 2.47 GB, MLX) and faster-whisper `small.en` (486 MB, `compute_type="int8"`, CPU). End of speech: Silero VAD (shipped with openWakeWord), 30 ms frames, 0.8 s of silence. Scripts: `spikes/03-stt/`. Recordings kept in `spikes/03-stt/tmp/` (git-ignored) until the spike ends.

### Steps 2–3: ten spoken requests, both engines
Febriel read ten typical requests, each starting with "Jarvis", about 1–2 m from the MacBook Air mic, TV off. The test harness captured 8 of the 10. The first three chimes timed out before he began, requests 1 and 2 ran together into one utterance, and the list ran out before requests 9–10. Results are lined up by what he said:

| Request (as said) | Parakeet | faster-whisper small.en int8 |
|---|---|---|
| what time is it / open the captions repo in VS Code | "Jervis, what time is it? Please. Open the captions **report** in Viscode." | "Jarvis, what time is it, please? Open the **caption triple** in VSCODE." |
| set a timer for twelve minutes | correct | correct |
| how much free space is on my disk | correct | "much free spaces on my disc" (meaning kept) |
| find the PDF about taxes I downloaded yesterday | correct | correct |
| turn the volume down to thirty percent | correct | correct ("30%") |
| run the tests in Project Jarvis and tell me what fails | "…tell me what that fails" (meaning kept) | "…tell me what that **feels**" |
| what's on my calendar tomorrow morning | correct | "Jarvis **was** on my calendar tomorrow morning" |

| Bar | Parakeet | faster-whisper |
|---|---|---|
| Median transcription < 0.7 s (utterances ≤ 5 s; these were 2.3–5.4 s) | **0.17 s** (max 0.41 s) | 1.02 s (max 1.22 s); 2.7 s median and one 26.9 s runaway on the Spike 2 recording |
| ≤ 1 meaning-changing error in 10 | **1 of 8** ("captions repo" → "captions report") | 3 of 8 |
| Silence produces no text | `""` (and the VAD never passes silence on) | "You" on 2 s of silence |
| Verdict | **Pass — winner** | Fail (speed, errors) |

- End of speech → transcript, measured live with Parakeet: median **0.97 s**, of which 0.8 s is the silence wait.
- Whisper.cpp was not needed (Parakeet passed).

### Wake by transcription (Febriel's choice after Spike 2)
How it works: the VAD cuts utterances; Parakeet transcribes each; it wakes if one of the first three words is within 0.75 similarity of "jarvis" (`difflib`), so "Jervis" and "Jarvis's" count and "Travis", "service" and "hey there" do not. The rest of the utterance is the request, so "Jarvis, set a timer…" works in one breath.
- Parakeet consistently hears his "Jarvis" as **"Jervis"**, which is why exact-word matching would fail and the fuzzy match is needed.
- Live (ten requests): woke on 3 of 3 utterances whose start was recorded intact. In four more, the start was cut by the test harness itself (the script dropped audio recorded while the chime played, and Febriel had started speaking on the chime), so these say nothing about waking.
- On the Spike 2 recording: the "clear" takes included sentences Febriel did not say ("More money", "I'm going to take a look at it"): **there was background speech (a TV or another person) during that session**, which confounds the Spike 2 wake-word numbers. His "talk normally" part was him reading Claude's message aloud, which contains "Jarvis", so its one "false wake" was a real "Jarvis" (and the custom-training negatives were contaminated with the wake word).
- Wake latency is no longer "wake word → listening in 0.3 s": the wake and the request arrive together about 1 s after he stops speaking (0.8 s silence + ~0.2 s transcription). For "Jarvis" said alone, Jarvis starts listening ~1 s later.

### Live wake and false-trigger run (35 min, `wake_live.py`, 2026-11-14)
Phases: 2 min quiet → Febriel says "Jarvis"/"Hey Jarvis" plus requests at his own pace (TV off, 1–2 m) → ~29 min of video and music at normal volume with other people talking (partly not in English). Every utterance the VAD passed was transcribed by Parakeet; no audio was stored.

| Measure | Bar | Measured | Verdict |
|---|---|---|---|
| Wakes on Febriel's "Jarvis" | 9 of 10 | 23 wakes; 3 likely misses heard as "Hey Jovis", "Pervis", "Agries, check my emails" → **≈ 88 % of utterances** (23/26). Febriel counted 17 attempts; the transcripts hold about 28 "Jarvis" mentions, some several to an utterance, so the per-utterance figure is used. | **Borderline** (just under 9/10) |
| False wakes with video/music/people talking | ≤ 1 in 30 min | **0** in 155 utterances over ~29 min | **Pass** |
| CPU, quiet room | "a few percent of one core" (§11) | 2.0 % | Pass |
| CPU, video playing | same | median 3.7 % per minute (1.6–5.5 %; one 12.8 % minute while the Mac was busy elsewhere); 4.0 % over the whole run | Pass |
| Transcription per utterance | — | median 0.20 s, 90th percentile 0.53 s; 196 utterances, 816 s of speech in 35 min | — |

Compared with Spike 2: the pretrained `hey_jarvis` model caught 3 of 10 live; wake by transcription caught about 88 % with no false wakes, at a similar CPU cost (2–4 % against 6–10 %).

### What the wake rule means for the spec (for the Task 13 amendment)
- **Wake phrase.** Spec §6.1 says v1 ships on "Hey Jarvis". What was tested is "Jarvis" anywhere in the first three words (fuzzy, ≥ 0.75 similarity), so **both "Jarvis" and "Hey Jarvis" wake it**, and bare "Jarvis" (Febriel's original ask) is no longer a later item.
- **Engine.** No wake-word model: Silero VAD → Parakeet → name match. openWakeWord is dropped.
- **Timing.** §11's "wake word to LISTENING under 0.3 s" no longer applies. The wake and the request arrive together about **1 s after he stops speaking** (0.8 s silence + ~0.2 s transcription). "Jarvis" said alone starts a listening turn about 1 s later, and the follow-up window still lets him reply without the name.
- **Misses.** Parakeet hears his "Jarvis" mostly as "Jervis" and sometimes as "Jovis", "Pervis" or "Agries". Plan 3 should tune the match (for example accept ≥ 0.7, which takes "Jovis" but still rejects "Travis" at 0.67) against a recorded set, and keep hold-to-talk as the fallback.
- **Privacy.** This way Jarvis transcribes everything said near the Mac, including other people. The text never leaves the Mac, but the spec should say that utterances without the wake word are discarded at once, never logged or written to the vault.
- **Fit with the 2.5 s target.** End of speech → text is about 1 s (0.8 s of it is the silence wait), so the 2.5 s budget to the first spoken word leaves about 1.5 s for the brain's first token (0.79 s, Spike 1) and the first audio.

### Cleanup
All spike audio is deleted: the Spike 2 session recording, the ten Spike 3 request recordings, and the transcript logs (they held other people's speech). The two failed custom wake models (`wake_*.joblib`, derived from his voice) are deleted. Kept, git-ignored: openWakeWord's public validation features (`spikes/02-wake/data/`, 185 MB), deletable any time.

## Spike 4 — spoken replies (Task 9), Steps 1–2

- Installed into the `spike` group: `mlx-audio` 0.6.5 and `misaki[en]` 0.9.4 (Kokoro's text-to-phoneme step; mlx-audio no longer pulls it in). `misaki[en]` drags in `torch` and `spacy`, and the first run downloads `en_core_web_sm` (12 MB) outside the lockfile. Model: `mlx-community/Kokoro-82M-bf16`, `lang_code="b"`. `.venv` is now 1.3 GB. `kokoro-onnx` not installed yet (needed for Step 3's race).
- Same three lines in the four Kokoro British male presets (`bm_george`, `bm_lewis`, `bm_daniel`, `bm_fable`) and `say -v Daniel`, script `spikes/04-tts/voices.py`, audio in its `tmp/`.
- **Febriel picked `bm_daniel` by ear (2026-11-13).** Spec §TTS's "exact voice preset is unverified" is now settled.

### Step 3 — streaming race, `mlx-audio` vs `kokoro-onnx`

Run 2026-11-13, 23:31–23:36. Voice `bm_daniel` on both. Script: `spikes/04-tts/stream_race.py <mlx|onnx> 5`, run with `.venv/bin/python`.

- **`mlx-audio` 0.6.5**: `mlx-community/Kokoro-82M-bf16`, `lang_code="b"`, `misaki[en]` 0.9.4 for phonemes.
- **`kokoro-onnx` 0.6.1**: `uv add --group spike kokoro-onnx` added `kokoro-onnx` 0.6.1 and `phonemizer` 3.6.0. Its other dependencies (`onnxruntime` 1.32.0, `espeakng-loader` 0.2.4, `numpy`) were already installed. `.venv` grew by 0.35 MB (1,378,532 → 1,378,880 KB). Model files come from the project's official release `model-files-v1.0` (github.com/thewh1teagle/kokoro-onnx), stored in `spikes/04-tts/data/` (git-ignored):
  - `kokoro-v1.0.onnx`: 325.5 MB, sha256 `7d5df8ec…3636a6c5`. This is the fp32 file the README uses. The fp16 (177 MB) and int8 (92 MB) files were not tried.
  - `voices-v1.0.bin`: 28.2 MB, sha256 `bca610b8…7f1fbf7d`.
  - `bm_daniel` is in `get_voices()`. Language `en-gb`, default ONNX Runtime CPU provider. CoreML is available but was not tried.
- **Package clash:** `phonemizer` 3.6.0 and misaki's `phonemizer-fork` 3.3.2 both install the `phonemizer` module, so installing `kokoro-onnx` overwrote the fork. `mlx-audio` still synthesizes `bm_daniel` correctly after that.
- **Method:** the paragraph is 7 sentences of Jarvis-style reply (an evening email/build summary that ends in a question). The model is loaded and warmed with one sentence first. The sentences are then synthesized back to back from t = 0, as if they arrive faster than the engine can speak them. Playback is simulated from the audio lengths, not played through the speakers: each sentence starts once it is ready and the previous one has finished. A "gap" is how long playback would stall. Five passes per engine.
- **Load:** run 1 overlapped Spike 3's 2.5 GB model download (load average 3.4–4.3). Run 2 started after that download ended and was meant to be the quieter re-run. Other work started meanwhile, so it was busier (load average 6.4 → 12.8). Run 1 is the primary result; run 2 shows the engines under heavy load.

| Engine | Run | First audio, median (range), s | Worst gap, median (range), s | Paragraph synth / speech length, s | Cold start: load + first synth, s |
|---|---|---|---|---|---|
| `mlx-audio` | 1 (load ~4) | **0.189** (0.182–0.217) | **0** (0–0) | 2.2–2.5 / 26.6 | 1.0 + 5.9 |
| `mlx-audio` | 2 (load 6–13) | 0.393 (0.315–1.591) | 0 (0–0) | 5.0–7.9 / 26.6 | 1.9 + 13.9 |
| `kokoro-onnx` | 1 (load ~4) | 0.647 (0.557–0.774) | 0 (0–0) | 7.1–10.8 / 22.8 | 0.5 + 1.4 |
| `kokoro-onnx` | 2 (load 6–13) | 0.812 (0.526–1.570) | 0 (0–**2.33**) | 10.1–22.8 / 22.8 | 0.5 + 1.2 |

| Bar | `mlx-audio` | `kokoro-onnx` |
|---|---|---|
| First audio ≤ 0.5 s after the first sentence arrives | **Pass**: every run-1 pass ≤ 0.22 s. Run 2 passed on median (0.39 s), with one outlier at 1.6 s. | **Fail**: 0 of 5 run-1 passes and 0 of 5 run-2 passes under 0.5 s; best was 0.526 s. |
| No gap > 0.3 s between sentences | **Pass**: no stall in any of 10 passes. | Pass when the machine is moderately loaded. **Fails under heavy load**: two stalls of 2.05 s and 2.33 s in run 2, pass 5. |

**Winner: `mlx-audio`.** It is the only engine that meets both bars. In run 1 it reaches first audio about 3.4× faster than `kokoro-onnx` and synthesizes the whole paragraph 3–4× faster (real-time factor about 0.09 against 0.3–0.5). The dependency tie-break does not apply because `kokoro-onnx` misses the first-audio bar. For the record, `kokoro-onnx` is much lighter: `onnxruntime`, `numpy`, `espeakng-loader` (a bundled espeak-ng library, about 10 MB wheel) and `phonemizer`, plus 354 MB of model files. `mlx-audio` needs `mlx` and `misaki[en]`, which pulls in `torch` and `spacy` and downloads `en_core_web_sm` outside the lockfile.

### Listen later
- `tmp/stream_mlx.wav` is run 2's last pass as it would play: no inserted stalls.
- `tmp/stream_onnx.wav` is run 2's pass 5, the heavy-load pass. It includes the 2.05 s and 2.33 s stalls as silence, so you can hear what a stall sounds like.
- The same paragraph comes out 26.6 s long from `mlx-audio` and 22.8 s from `kokoro-onnx`. The pacing or pauses differ, so it is worth a listen to compare.

### What it means for Plan 3
- Use `mlx-audio` + `misaki[en]` with `bm_daniel`, `lang_code="b"`. Do not add `kokoro-onnx` to the main dependencies: it swaps out misaki's `phonemizer-fork`.
- **Warm up at daemon start.** The first synthesis after loading costs 5.9 s (13.9 s under load), mostly misaki and spaCy setup and the first MLX graph build. `jarvisd` should load the model and synthesize a throwaway sentence at startup, never on the first reply.
- Stream sentence by sentence: first audio is about 0.2 s when the machine is calm. No gaps appeared even under load average 13, so a one-sentence lookahead is enough.
- The first sentence here is short ("Good evening, Febriel."). Long sentences took `mlx-audio` 0.28–0.48 s each in run 1, so a long first sentence would still clear 0.5 s, with less margin.
- Not tested: `kokoro-onnx` on the CoreML provider or with the int8/fp16 models. That only matters if the `torch`/`spacy` weight becomes a problem later.
- Step 4 (the end-to-end latency sum) waits for Spike 3's transcription number. Use **0.19 s** as the TTS term.


Chosen engine and voice: **`mlx-audio` 0.6.5, `mlx-community/Kokoro-82M-bf16`, voice `bm_daniel`, `lang_code="b"`** (with `misaki[en]` 0.9.4).

### `kokoro-onnx` removed (2026-11-13)

- `uv remove --group spike kokoro-onnx`; `git diff pyproject.toml uv.lock` is now empty. `spikes/04-tts/data/` (348 MB of v1.0 model files) deleted. `stream_race.py`'s docstring says the `onnx` half needs both back.
- **Watch out:** `uv remove --group spike` re-synced `.venv` *without* the `spike` group. It uninstalled 106 of 112 packages (mlx, torch, spacy, misaki, openwakeword…). `uv sync --group spike` restored every one at its previous version. The exception was `en_core_web_sm` 3.8.0, which sits outside the lockfile; misaki re-downloaded it on first use. Any `uv add`/`uv remove` for a group that is not the default needs `uv sync --group spike` afterwards, or `spike` should become a default group. **Done 2026-11-13:** `[tool.uv] default-groups = ["dev", "spike"]` in `pyproject.toml`.
- Versions check against a snapshot taken before the removal: nothing changed version. Only `kokoro-onnx` 0.6.1 and `phonemizer` 3.6.0 are gone. `import phonemizer` reports 3.3.2, the `phonemizer-fork` version, reinstalled clean by the sync. `mlx-audio` synthesizes a `bm_daniel` sentence (2.38 s of audio).
- **Quieter re-check of first audio:** one `mlx` race, 5 passes, 23:45, 1-minute load average 4.9 → 4.0 (no model work by other spikes running). First audio **0.177 s** median (0.174–0.236), no gaps, cold start 1.0 + 4.0 s. This confirms Step 3's 0.19 s.

### Step 4 — end of speech to first spoken word (final 2026-11-14, with Spike 3's live number)

| Term | Value | Source |
|---|---|---|
| End-of-speech silence (voice activity detection) | 0.80 s | Spec §6.1, "about 0.8 s" |
| Transcription (Parakeet) | 0.17 s | Spike 3, live median over Febriel's spoken requests (max 0.41 s). Spike 3 measured end of speech → transcript at 0.97 s in one piece, which matches the two rows above. The provisional figure from recorded audio was 0.28 s (sum 2.06 s) |
| First text token | 0.79 s | Spike 1 Step 7, warm process, bare Sonnet prompt |
| First audio of the first sentence | 0.19 s | Spike 4 Step 3 (re-check 0.18 s) |
| **Sum** | **1.95 s** | Bar §11: about 2.5 s → **passes, with 0.55 s to spare** |

#### What the sum leaves out (best estimates)
1. **The first sentence has to finish arriving before it can be synthesized.** The 0.79 s is time to the first token, not to the first full sentence. Spike 1 measured a *whole* short reply at 1.0–1.5 s, so the first sentence lands 0.2–0.7 s after the first token. A short opener ("Right.", "Good evening, Febriel.") is at the low end. **+0.2–0.7 s → 2.15–2.65 s.** This is the biggest gap.
2. **The real `jarvis` prompt and memory index.** Spike 1 used a bare prompt, and `docs/spikes/findings.md` has no number for a heavy one. Rough guess: +0.1–0.5 s to first token on a warm, cached session, more on the first turn after a context change. **Unmeasured.**
3. **Live transcription vs recorded.** Settled: the live number (0.17 s) came in under the recorded one (0.28 s).
4. **Machine load.** Under load average 6–13, first audio rose to 0.39 s median with one 1.6 s outlier (Step 3, run 2). Spike 1's token times were taken on a quieter machine. A busy Mac (a CapCut export, say) could add 0.2 s or more across the TTS and transcription terms.
5. **Cold paths, excluded by design.** The first TTS synthesis after load costs 4–6 s (14 s under load), and the first Claude turn including process start was 1.63 s against 0.79 s. `jarvisd` must keep both warm (load the model, synthesize a throwaway sentence, and keep the `claude` process running), or the first reply of the day misses the bar badly.
6. **Replies that call a tool before speaking** (look something up, then answer) are not "small requests" and are outside this bar; their first word waits for the tool.
7. **Audio output start** (Core Audio buffer, device wake from idle) is unmeasured; usually tens of milliseconds, more if the output device was asleep.

**Realistic estimate: about 2.2–2.8 s** for a small request: the 1.95 s sum, plus 0.2–0.7 s for the first sentence and up to about 0.2 s for prompt weight. That is around the 2.5 s bar, not safely under it.

#### Levers for Plan 3
- Tell the `jarvis` agent to open with a very short first sentence. That turns item 1 into about +0.2 s.
- Start synthesis at the first clause break (a comma or dash) when the first sentence is long. `mlx-audio` handles short fragments in about 0.18 s.
- Shorten the end-of-speech silence from 0.8 s to 0.6 s if Spike 3's false-cutoff rate allows. That saves 0.2 s.

Verdict: **pass on the bare sum (1.95 s); borderline once the first-sentence wait is counted (about 2.2–2.8 s).** Plan 3 should build in the short-first-sentence lever from the start and measure the real end-to-end time with the `jarvis` agent prompt.

## Spike 5 — on-screen control (Task 10)

Run 2026-11-13. agent-desktop **1.3.0** (npm `agent-desktop`, repository `github.com/vercel-labs/agent-desktop`, published by `vercel-release-bot`), installed with `npm install -g agent-desktop@1.3.0` into `/opt/homebrew` (no sudo). npm skipped the package's `postinstall` (npm allow-scripts policy). The macOS arm64 binary and helper ship in the package and their SHA-256 sums match the bundled `.sha256` files, so nothing was downloaded. Scripts: `spikes/05-screen/step2.sh`, `step4.sh`. Logs and snapshots: `spikes/05-screen/tmp/logs/`.

Accessibility was `denied` at 23:28 and `granted` at 23:30, with no action from this worker; Febriel granted it while the spike was running. The grant covers the app that runs this Claude Code session (process chain: `Claude.app` → `disclaimer` → `~/Library/Application Support/Claude/claude-code/2.1.321/…/claude.app` → zsh). Which of those two bundles appears in the Accessibility list is **unverified**. Screen Recording is still `denied`.

| Step | Bar | Measured | Verdict |
|---|---|---|---|
| 1 Install | vercel-labs package, no sudo | 1.3.0, `/opt/homebrew/bin/agent-desktop`, checksums match | **Pass** |
| 2 TextEdit: snapshot, click, type a line | Actions succeed | Snapshot ok. **Click** on the text area: headless → `POLICY_DENIED` (a text view has no press action); `--headed` → ok (one earlier run: `ACTION_FAILED … occluded by group`, not repeated). **Type** headless → ok, and `get --property value` read the line back. Close button clicked headless → window closed with no save prompt (file-backed scratch doc) | **Pass** (click needs `--headed` on text views) |
| 2 Finder: drag a scratch file between two scratch folders | File moves | `--headed drag` with default timing (no `--duration`, `--drop-delay 800`): `ok` (`delivered_unverified`) but **file did not move**. With `--duration 1000 --drop-delay 1000 --timeout-ms 10000`: file moved, twice (once by hand, once from `step2.sh`) | **Pass** with slow timing; `ok` alone proves nothing |
| 3 Snapshot gives role and label for a button | Enough for `classify_screen` | Yes: `role` + `name` (+ `description`). Mapping below | **Pass**, two gaps noted |
| 4 Display asleep | Actions succeed; screenshot usable | Run 2026-11-14 from the Claude session (its Accessibility grant). Display off 10:48:00 and session **locked** (`CGSSessionScreenIsLocked=Yes`; lock is "immediately"). At 10:49: `open -a TextEdit` and `open <folder>` ran, but agent-desktop found **no TextEdit window and no Finder window**, so nothing was typed or dragged. Screen Recording still `denied` (granted by Febriel but needs a Claude restart), so no screenshots | **Fail while locked** — see "Step 4 result" below |

### Exact syntax (1.3.0)
- Every command prints one JSON envelope: `{"ok": true, "data": …}` or `{"ok": false, "error": {"code", "message", "disposition": {"delivery", "retry"}}}`. Retry only when `retry` is `safe`.
- `agent-desktop permissions` — read-only check (`accessibility`, `screen_recording`, `automation`, each `{state}`). `--guide` opens System Settings (Febriel's step); `--request` shows system prompts. `agent-desktop status` adds platform and supported surfaces.
- `agent-desktop snapshot --app TextEdit --window-id w-26492 -i --compact` — refs look like `@s3oh1yjv7l7e6y:e2`; a bare `@e2` is rejected. Refs go stale when the UI changes (`STALE_REF`).
- `agent-desktop click @s…:eN` — headless `AXPress`. `agent-desktop --headed click @s…:eN` — physical click; it focuses the window and moves the real pointer. **`--headed` is a global flag and goes before the command.**
- `agent-desktop type @s…:eN "text"` (or `--stdin`) — headless insert; verifies the element value.
- `agent-desktop get @s…:eN --property value|text|role|states|bounds`.
- `agent-desktop --headed drag --from @s…:eA --to @s…:eB --duration 1000 --drop-delay 1000 --timeout-ms 10000`. Coordinates instead: `--from-xy X,Y --to-xy X,Y` (negative values as `--from-xy=-100,50`). Drag is **always physical** and refuses without `--headed`. `--wait-for-scope from|to` exists for cross-window drags.
- `agent-desktop screenshot --window-id w-… out.png` / `--screen 0 out.png` / `--app X` — needs Screen Recording.
- `agent-desktop press cmd+c [--app X]` — always physical keyboard; quit combos need `--force`. `agent-desktop close-app X [--force]`. `agent-desktop list-windows --app X` → `data: [{id, title, app_name, pid, bounds, is_focused, accessible, …}]`.
- Also present: `find --role --name --first`, `wait --window|--text|--element|--event`, `select @ref "Option"`, `set-value`, `scroll`, `mouse-click --xy` (headed), `batch` (JSON list of commands), `mcp` (serves every command as an MCP tool over stdio), `session`, `trace`.

### Snapshot format and `classify_screen` (Step 3)
Each node: `role`, `name`, `description`, `value`, `states`, `available_actions`, `native_id`, `ref_id`, `children`. Real button nodes from this Mac (`tmp/logs/finder-snapshot-20261113-233336.json`, `textedit-snapshot-…`):

```json
{"role":"button","name":"Eject","description":"eject","available_actions":["Click","SetFocus"],"ref_id":"@s2v0ctobsz2mtz:e17"}
{"role":"button","name":"Close","available_actions":["Click"],"ref_id":"@s217v14vfhj2yk:e5"}
{"role":"button","available_actions":["Click"],"ref_id":"@s2v0ctobsz2mtz:e47"}
{"role":"image","name":"jarvis-drag.txt","description":"jarvis-drag.txt","available_actions":["Click","RightClick"]}
```

Roles are lowercase words (`button`, `textfield`, `radiobutton`, `menubutton`, `treeitem`, `cell`, `image`, `list`, `scrollarea`, `slider`). Mapping for Plan 2:
- `classify_screen(role=node["role"], label=…)`. Use **`label = name + " " + description`** (both when present), not `name` alone: an icon-only control can carry its words only in `description`.
- **Gap 1 — unlabelled controls.** Finder has clickable `button`s with no `name` and no `description` (e47 above). `classify_screen` allows an empty label (`tests/brain/test_gate_screen.py` has `("", "allow")`), so a click on an unnamed control is never asked about. Recommend: a click on a node with no name and no description asks. **Closed 2026-11-13:** `classify_screen` now asks on an empty label and never remembers it, except on passive roles (`textfield`, `scrollarea`, `scrollbar`, `list`, `outline`, `cell`); spec §6.5 amended, Febriel to confirm.
- **Gap 2 — which node.** agent-desktop takes only a ref. The gate must judge the node that ref points to: look it up in the snapshot Jarvis just took, or read it live with `get @ref --property text` / `--property role` right before acting.
- Command → gate action: `click`, `double-click`, `triple-click`, `right-click`, `toggle`, `check`, `uncheck` → `click`; `select @ref "Option"` → `click` with label = the option text (a menu item named "Delete" is chosen this way); `type`, `set-value` → `type` (text with a newline asks); `press` → `press` (agent-desktop's combo strings, `return`, `cmd+w`, already match the gate's key parsing); `scroll`, `scroll-to`, `expand`, `collapse` → `scroll`; `launch`, `focus-window` → `open`; `drag` → `drag`. No element to judge, so they should ask: `mouse-click`/`drag` with `--xy`, `close-app`, `clipboard-set`, `notification-action`. `batch` and `mcp` must not be exposed, or every step must go through the gate.

### Other things found
- **Screen Recording also gives window titles.** Without it, `list-windows` returns the app name as every window's title, and `wait --window <title>` never matches. `step2.sh` finds its windows by id (TextEdit) or by contents (Finder) for this reason.
- **Stage Manager is on** (`com.apple.WindowManager GloballyEnabled = 1`). `list-windows` reports only the active stage's windows, so the list changes when the foreground app changes. Jarvis must bring the target app forward (`open`, `launch --activate`, `focus-window`) before it snapshots. One `step2.sh` run lost the Finder window this way; the script now re-runs `open` if the window does not appear.
- **Finder keeps windows of deleted folders.** It moves them to the parent folder instead of closing them, so scripts must close their own windows before they delete scratch folders. One Finder window left from debugging may still sit in a background stage, showing `spikes/05-screen/tmp`; it can be closed by hand.
- Physical input (`--headed` click, drag) moves the real pointer and takes focus: it disturbs Febriel if he is at the Mac. Headless covers `type`, buttons with a press action, and windows' Close buttons.

### Step 4 result (2026-11-14)
- **On-screen control does not work while the session is locked.** With the display asleep and the Mac locked, the apps opened but their windows were invisible to agent-desktop (`list-windows` found no new accessible window for 20 s), so no click, type or drag could happen. Log: `spikes/05-screen/tmp/logs/step4-20261114-104724.log` (git-ignored).
- The "display asleep but unlocked" case could not be tested: with the lock set to "immediately", the display never sleeps without locking. Testing it needs the lock delay changed, which is a security setting and Febriel's decision.
- Screenshots: not measured. Febriel granted Screen Recording to Claude, but it reads `denied` until Claude restarts.
- **Meaning for the design (spec §6.6, §2 goal 4):** remote on-screen control works only while the Mac is unlocked. Files, terminal and everything else Jarvis does still work while locked. **Decided by Febriel 2026-11-14: on-screen control works only while the Mac is unlocked.** When it is locked, Jarvis says so and holds or refuses on-screen steps; everything else carries on. The lock setting stays "immediately". (The alternative, a longer lock delay for "unlocked with display off", was declined.)

### Step 4 (as prepared by the worker)
`step4.sh [delay, default 120]` holds `caffeinate -i` (system awake, display free to sleep), logs the screen-lock setting and permissions, waits 5 s, runs `pmset displaysleepnow`, waits the delay, logs display and lock state (`pmset -g log` "Display is turned on/off"; `ioreg` `CGSSessionScreenIsLocked`), runs `step2.sh` with screenshots of the TextEdit window and screen 0 into `spikes/05-screen/tmp/`, then logs the state again. The headed Finder drag runs last because physical pointer events may wake the display. With lock "immediately", the run tests **display asleep and session locked**; `PROJECT.md` already expects GUI control to need an unlocked session. The lock delay is a security setting: Jarvis does not change it, and whether to change it is Febriel's decision.

### What Febriel has to do, in order
1. **Grant Terminal.** Step 4 is started from Terminal, so Terminal is the app macOS checks. In Terminal, run `agent-desktop permissions --guide` and add **Terminal** to **Accessibility** and to **Screen Recording** (Screen Recording is only for the screenshots and window titles; without it, Step 4 still runs but the screenshot part fails). Confirm with `agent-desktop permissions` (both `granted`).
2. **Run Step 4.** Unlock the Mac (open TextEdit documents are safe: the script only closes its own scratch window), then in Terminal:
   ```bash
   bash "$HOME/Developer/Project Jarvis/spikes/05-screen/step4.sh" 120
   ```
   Let go of mouse and keyboard; the display sleeps after 5 s (and locks, given the current setting). Wait about 3 minutes, wake the Mac, and hand over `spikes/05-screen/tmp/logs/step4-*.log` and the two `step4-*.png` files.
3. **Decide after the result** (only if Step 4 fails while locked): keep remote on-screen control limited to when the display is awake and unlocked, or change the lock delay yourself. Jarvis does neither for you.
4. Optional: tell the conductor which app now has Accessibility for the Claude session (`Claude` or the `claude` helper under `~/Library/Application Support/Claude/claude-code/<version>/`). If it is the versioned helper, the grant may not survive a Claude Code update.

## Spike 6 — phone round trip (Task 11): local part

Run 2026-11-13 without Tailscale, which is not installed yet. Script: `spikes/06-phone/server.py` (standard library only). Python 3.14.7 (Homebrew).

### What ran
- `server.py [--ask-first]` binds `127.0.0.1:8787` and checks the port first: a second start exits with `port 8787 is taken; not starting`, exit 1. `allow_reuse_address` is off as well.
- On first start it created the token in `~/.jarvis/token` with `secrets.token_urlsafe(32)`. File mode is `-rw-------`, folder mode is `drwx------`. The token never appeared in chat, command output or the server log. The log records method, path and status only, and a grep of the log for the token found 0 matches.
- The `Authorization` header is checked with `hmac.compare_digest` against `Bearer <token>`.
- `--ask-first` makes the first request answer `needs_reply: true` ("…Shall I go ahead?"). Every later request answers `false`.

| Check (curl on the Mac, token read from the file inside the command) | Expected | Got |
|---|---|---|
| Right token, 1st request (`--ask-first`) | 200, `needs_reply: true` | 200 `{"say": "You said: what time is it. Shall I go ahead?", "needs_reply": true}` |
| Right token, 2nd request | 200, `needs_reply: false` | 200 `{"say": "You said: yes", "needs_reply": false}` |
| Wrong token | 401 | 401 |
| No `Authorization` header | 401 | 401 |
| Token without `Bearer ` | 401 | 401 |
| Bad JSON / JSON without `text` | handled | 400 `expected JSON {"text": "..."}` |
| Wrong path `/other` | — | 404 |
| `GET /ask` | — | 501 (stdlib default) |
| `lsof -nP -iTCP:8787 -sTCP:LISTEN` | 127.0.0.1 only | `TCP 127.0.0.1:8787 (LISTEN)`, IPv4 only |
| Request to the Mac's Wi-Fi address on port 8787 | refused | curl exit 7 (connection refused) |
| Server stopped afterwards | no listener | `lsof` finds none |

### Verified
The server contract for Steps 2 and 5, the token handling and a loopback-only bind. Steps 3–7 need Tailscale and Febriel.

### Checked against current docs (2026-11-13)
- **Tailscale Serve** ([kb/1242](https://tailscale.com/kb/1242/tailscale-serve)): `tailscale serve --bg --https=443 http://127.0.0.1:8787` serves the port to the tailnet only, and "only `http://127.0.0.1` is supported for proxies". Status: `tailscale serve status`. Clear everything: `tailscale serve reset`. Public exposure is the separate `tailscale funnel` command, which is never used here.
- **HTTPS needs two switches in the admin console** ([kb/1153](https://tailscale.com/kb/1153/enabling-https)): *DNS* page → MagicDNS on → HTTPS Certificates → **Enable HTTPS**. **Privacy:** the Mac's machine name and the tailnet name go into the public Certificate Transparency log. If the Mac's name contains Febriel's name, rename the machine in the admin console *before* enabling HTTPS.
- **Shortcuts has no "repeat while"** ([Apple, Repeat actions](https://support.apple.com/guide/shortcuts/use-repeat-actions-apdc11deb2c1/ios)). The only loops are **Repeat** (N times) and **Repeat with Each**. `shortcuts/README.md` uses Repeat ×10 with an **If** → **Stop This Shortcut** when `needs_reply` is false. Siri runs a shortcut when you say its name ([Apple](https://support.apple.com/en-gb/HT208309)), so the shortcut must be named "Jarvis".

### Prepared commands (not run)
Run these from the repo root. On the Mac the `tailscale` CLI comes from the app (Settings → *Install CLI*), or use `/Applications/Tailscale.app/Contents/MacOS/Tailscale`.

**Step 3: publish to the tailnet and prove it is private**

```bash
lsof -i :8787
```

```bash
python3 spikes/06-phone/server.py --ask-first
```

In a second tab:

```bash
tailscale serve --bg --https=443 http://127.0.0.1:8787
```

```bash
tailscale serve status
```

```bash
tailscale funnel status
```

The last one must show nothing funnelled. Set `HOST` to the `ts.net` name that `serve status` printed, then:

```bash
curl -s -w ' -> %{http_code}\n' -H "Authorization: Bearer $(cat ~/.jarvis/token)" -d '{"text":"hello"}' "https://$HOST/ask"
```

```bash
curl -s -w ' -> %{http_code}\n' -d '{"text":"hello"}' "https://$HOST/ask"
```

Expect 200, then 401. Then check it is not reachable without Tailscale. Public DNS must not resolve the name, and with Tailscale down the request must fail:

```bash
dig +short "$HOST" @1.1.1.1
```

```bash
tailscale down; curl -sS -m 5 -o /dev/null -w '%{http_code}\n' "https://$HOST/ask"; echo "curl exit $?"; tailscale up
```

Expect an empty `dig` result and a curl failure (no 200 or 401). Also look at the Mac's own LAN address: port 8787 is already refused there (above).

**Step 6: iMessage to Febriel's own Apple ID.** Replace `APPLE_ID_EMAIL_OR_PHONE` with his address. The first run may raise a macOS Automation prompt (Terminal → Messages); record whether it does.

```bash
osascript -e 'tell application "Messages" to send "Jarvis spike 6: test notification" to participant "APPLE_ID_EMAIL_OR_PHONE" of (1st account whose service type = iMessage)'
```

Risk to watch: a message sent to your own Apple ID usually lands as *sent by you* and may not notify on the iPhone. If no notification arrives, record it as a failure of the "iMessage to self" call (spec §6.4) and bring it to the conductor. Do not swap channels inside the spike.

**Step 7: stop**

```bash
tailscale serve reset
```

```bash
tailscale serve status
```

Then press Ctrl-C on the server and run `lsof -i :8787`, which should show no listener.

### Results with Tailscale (2026-11-14)
Febriel created the Tailscale account (sign-in with GitHub), installed Tailscale 1.104.5 from the Mac App Store and on the iPhone, renamed the Mac to `jarvis-mac` inside Tailscale (the OS name contains his name), and enabled HTTPS. Tailnet: `tail80d4ef.ts.net`. Server run from this session (`server.py`, `127.0.0.1:8787`).

| Step | Bar | Measured | Verdict |
|---|---|---|---|
| 3 `tailscale serve --bg --https=443 http://127.0.0.1:8787` | Reachable on the tailnet only | `serve status`: `https://jarvis-mac.tail80d4ef.ts.net (tailnet only)`; Funnel off. With token: 200 in 1.08 s (the very first request waited ~30 s for the certificate). No token / wrong token: 401. Public DNS (1.1.1.1): no answer. Mac's LAN address :8787: refused. With `tailscale down`: name does not resolve (curl exit 6); after `up`: 200 | **Pass** |
| 4 Shortcut | Built; token pasted by Febriel | Febriel could not find the Jarvis tile after building by hand, so Claude generated the shortcut as a signed file (`spikes/06-phone/make_shortcut.py` → `shortcuts/Jarvis.shortcut`, placeholder instead of the token). Import dropped the If step's comparison value, so the loop rule changed: the server sends `"loop": "yes"` only when it wants an answer, and the If tests "does not have any value" (set by clicking). Febriel pasted the token on the Mac (a first paste missed the field; the server's 401 log showed the placeholder) and AirDropped the shortcut to the iPhone (iCloud did not sync it) | Done |
| 5 Mobile data, Wi-Fi off | < 4 s to spoken answer; reply loop hands-free; 401 without token | Febriel: **under 4 s**. Reply loop: two requests 8 s apart (16:50:26 and 16:50:34), the second taken hands-free. 401 without the token verified over the tailnet from the Mac. First try failed with "A server with the specified hostname could not be found": Tailscale on the iPhone was off (offline 1 h); fixed by connecting it (VPN On Demand recommended) | **Pass** |
| 5 "Hey Siri, Jarvis" | Starts the shortcut | **Did not start it.** Febriel chose **Back Tap** (double-tap the back of the iPhone) instead; it works (runs at 16:55:49 and 16:56:03) | **Fail → Back Tap** |
| 6 iMessage from the Mac to Febriel's own Apple ID (`osascript` → Messages) | Arrives on the iPhone as a notification | First run blocked on the macOS Automation prompt (Claude → Messages; `AppleEvent timed out`, -1712) until Febriel allowed it. The message then **appeared in Messages on the Mac but no notification on the iPhone**: a message to your own Apple ID counts as sent by you | **Fail** — iMessage-to-self cannot nudge the phone |
| 7 Stop | Nothing left exposed | `tailscale serve reset` → "No serve config"; Funnel never on; server stopped, nothing listens on 8787; server log deleted. Kept: `~/.jarvis/token` (mode 600), used by the shortcut | Done |

Other findings:
- **Febriel's reply rules (spec amended 2026-11-14):** Jarvis never repeats back what he said, and once a task is clarified it does not repeat those clarifications unless the task changes. The spike server's "You said: …" echo was removed for the same reason.
- **Decided 2026-11-14 — Febriel chose the iCloud Reminder (option 1); spec §6.4 amended.** **Tested the same day: pass.** `osascript` → Reminders added "Jarvis test nudge" with an alert at 17:07:03 (first run raised the Automation prompt Claude → Reminders, allowed); Febriel saw the alert on the iPhone. The test reminder was then deleted. Original question: how Jarvis nudges the phone (spec §6.4 said iMessage to self, "to be confirmed"; it fails). Options, none tested yet: (1) **an iCloud Reminder with an alert** that Jarvis adds on the Mac; it syncs to the iPhone and notifies there, with no new account or app (Claude's recommendation; test in Plan 4); (2) **an email to himself**, which notifies if Mail/Gmail notifications are on (noisier); (3) **ntfy**, an open-source push app with its server on the tailnet (one more app; iOS push goes through ntfy.sh's relay, which sees only a wake-up, not the text). Until decided, long phone jobs answer "started" and Febriel checks back with Back Tap.
- The tailnet name and `jarvis-mac` are in the public Certificate Transparency log (expected; no personal name).
- A 401 on the server now logs only the header's shape (present, `Bearer ` prefix, placeholder, length), never its value; that is how the missed paste was found without anyone seeing the token.

### Waiting on Febriel, in order
1. Create a Tailscale account (he does this; Jarvis creates no accounts).
2. Install Tailscale on the Mac and sign in. Install the CLI from the app's settings.
3. Install Tailscale on the iPhone and sign in to the same tailnet.
4. In the admin console: rename the Mac if its name is personal, then turn on MagicDNS and **Enable HTTPS** (DNS page).
5. Run Step 3's commands above (or let a worker run them once Tailscale is up). Bar: 200 with the token and 401 without over `https://…ts.net`; not reachable with Tailscale down.
6. Build the Shortcut from `shortcuts/README.md` and paste the token in himself.
7. Wi-Fi off, mobile data on: run it by icon and by "Hey Siri, Jarvis", with the server on `--ask-first`. Bar: under 4 s from request to spoken answer; the reply loop works hands-free; 401 without the token.
8. Run the Step 6 `osascript` line with his Apple ID. Confirm on the iPhone whether a notification arrived, and say whether macOS asked for Automation permission.
9. Step 7: `tailscale serve reset`, stop the server.

## Spike 7 — staying awake (Task 12): dry run

Run 2026-11-13. Scripts: `spikes/07-awake/awake_log.py` and `report.py` (standard library only, Python 3.14.7). The first overnight run (2026-11-13 23:38 → 2026-11-14 09:13) is **inconclusive** (see below); the battery run has not started.

### What the scripts do
- `awake_log.py HOST [HOST ...] [--interval S]` (default 300 s) appends one line per tick to `spikes/07-awake/tmp/awake.log` (git-ignored): ISO timestamp, power source and battery percent from `pmset -g batt`, and `ping -c 1 -t 5` to each host. Example: `2026-11-13T23:32:00 power=Battery batt=66 reach=1.1.1.1:ok:58.934ms,192.0.2.1:FAIL`.
- `report.py [--bar-minutes 6]` reads the log and prints:
  - the largest gap between lines against the 6-minute bar;
  - reachability failures per host;
  - system `Sleep` entries in `pmset -g log` inside the log's window (bar: none);
  - how often "Display is turned off" appears (Step 3: the display must have slept);
  - battery drop per hour over the samples on battery power.

### Dry runs
| Run | Result |
|---|---|
| 2 min, `--interval 15`, host 1.1.1.1, under `caffeinate -i` | 8 lines; `pmset -g assertions` showed `PreventUserIdleSystemSleep` from `caffeinate` on behalf of the logger. One ping failed and was logged as `FAIL`. With `--bar-minutes 0.3` the report flagged the 0.33-min gap as FAIL, so the gap check works. 0 system sleeps. Battery 68→66 % (too short a window to mean anything per hour). |
| 45 s, `--interval 10`, hosts 1.1.1.1 + 192.0.2.1 (unroutable) | Per-host counts: 0/3 and 3/3 failed. Gap PASS against 6 min. |

The display did not turn off in either dry run (they were too short), so the display line reads `NO` as expected. Both logs were deleted afterwards so the real runs start clean.

### Notes for the real runs
- A failing ping waits up to 5 s, so each down host stretches a tick by 5 s. At 300 s with two hosts down, the gap is about 5.2 min, still inside the 6-min bar.
- Hosts: pass `1.1.1.1` (the Mac's Wi-Fi is up) **and** the iPhone's tailnet address `100.x.y.z` (from `tailscale status`). iOS may suspend Tailscale on a locked phone, so iPhone failures while 1.1.1.1 stays ok point at the phone, not the Mac. The decisive check is the Shortcut answering in the morning without waking the Mac.
- `pmset -g log` showed other apps can hold `NoDisplaySleepAssertion` (the Claude app did briefly at 23:05). If the report says the display never turned off, check `pmset -g assertions` for the app holding it.
- `caffeinate -i` stops idle system sleep only. Closing the lid still sleeps the Mac (spec §6.6, accepted).

### Commands (run from the repo root; not started)
Overnight, plugged in, lid open (Step 1):

```bash
caffeinate -i python3 spikes/07-awake/awake_log.py 1.1.1.1 IPHONE_TAILNET_IP
```

Two hours on battery, lid open (Step 2). Same command; stop it with Ctrl-C after 2 h:

```bash
caffeinate -i python3 spikes/07-awake/awake_log.py 1.1.1.1 IPHONE_TAILNET_IP
```

After each run (Step 3), then move or delete `spikes/07-awake/tmp/awake.log` before the next run so the windows don't mix:

```bash
python3 spikes/07-awake/report.py
```

### Change 2026-11-13: overnight run tonight, without the tailnet check
Febriel said "Yes, tonight": run Step 1 now, before Tailscale exists.
- **Deviation:** reachability is checked against `1.1.1.1` (a plain internet host), not a tailnet address. Tailnet reachability is re-checked in a later run once Tailscale is installed.
- **The bar applies to the stretch on AC.** The Mac was on battery (64–67 %) when this was set up, and every log line carries `power=AC` or `power=Battery`. `report.py` now also prints `gap AC`, the largest gap between two consecutive lines that were both on AC.
- **Safety rule (added to `awake_log.py`):** if it is on battery and below 20 %, it writes a `STOP on battery at N% …` line and exits. `caffeinate` then ends and the Mac can sleep instead of draining flat. `report.py` prints that line if it is there. Tested with a faked 15 % reading: the logger wrote the STOP line and exited 0.
- **Started 2026-11-13 23:38:41 (+0800) by the conductor session** with the command below, after Febriel plugged in (first line: `power=AC batt=62 reach=1.1.1.1:ok`). The worker session's own attempt was refused by its permission check (auto mode: "unauthorized persistence"). `caffeinate` holds `PreventUserIdleSystemSleep` for the logger. Result: see "First overnight run" below.

**Start (plugged in, lid open).** Changed 2026-11-14: it no longer deletes an earlier log (it renames it) and refuses to start while a run is alive.

```bash
cd ~/Developer/"Project Jarvis" && mkdir -p spikes/07-awake/tmp && if pgrep -f spikes/07-awake/awake_log.py >/dev/null; then echo "already running; stop it first"; else s=$(date +%Y%m%d-%H%M%S); for f in awake.log run.out; do [ -f spikes/07-awake/tmp/$f ] && mv spikes/07-awake/tmp/$f spikes/07-awake/tmp/$s-$f; done; date '+%Y-%m-%dT%H:%M:%S%z' > spikes/07-awake/tmp/run.start; nohup caffeinate -i python3 spikes/07-awake/awake_log.py 1.1.1.1 > spikes/07-awake/tmp/run.out 2>&1 & fi
```

Check that it is alive. Expect one `caffeinate -i python3 …` line and a first log line with `power=AC`. Terminal.app can then be closed, because `nohup` keeps the run going.

```bash
pgrep -fl awake_log.py; cat ~/Developer/"Project Jarvis"/spikes/07-awake/tmp/awake.log
```

**Morning: stop it, then report.** Stopping the logger also ends `caffeinate`.

```bash
pkill -f spikes/07-awake/awake_log.py
```

```bash
cd ~/Developer/"Project Jarvis" && python3 spikes/07-awake/report.py
```

Read `gap AC` against the 6-min bar (plain `gap` also counts any battery stretch before he plugged in), along with `sleep` (must be 0) and `display` (must show it turned off at least once).

### First overnight run: 2026-11-13 23:38 → 2026-11-14 09:13 — inconclusive

| Check | Bar | What the night shows | Verdict |
|---|---|---|---|
| System sleep | none in `pmset -g log` | No `Sleep`, `Wake` or `DarkWake` entry between 23:38 and 09:13 | Met, but **not attributable to `caffeinate`** (below) |
| Gap in the logger's lines | none over 6 min | **Log lost.** The start command was run again from Terminal at 09:11:03, and it began with `rm -f …/awake.log` and overwrote `run.out`. Only indirect evidence is left: the original logger (PID 25662, started 23:38:41) was still alive and ticked at 09:13:55, which is 115 ticks of 300.1 s after its first line, so it was never suspended | **Not shown** |
| Display slept (Step 3) | yes | Off 00:12–00:25 and 00:56–00:57 only; on from 00:57 to 09:13 | **Fail** for this night |
| On AC | whole run | On battery at 23:43 (61 %), 100 % and on AC by 09:11; the time he plugged in is not recorded (the log is gone) | Unknown |

Why it proves nothing about `caffeinate -i`:
- The Claude app held a `NoDisplaySleepAssertion` named "Capturing" from 01:40 to 09:12 (25,445 creations; another 23 from `chrome-headless-shell`). Other Claude sessions were working overnight. With the display held on, `powerd` holds its own "Prevent sleep while display is on" system assertion (8 h 15 min at 09:13).
- `coreaudiod` also held `PreventUserIdleSystemSleep` for the built-in speaker and an audio tap for most of the night (9 h 45 min and 10 h 57 min at 09:13).
- So the Mac would have stayed awake without `caffeinate`. Keyboard and mouse activity stopped after 01:xx and resumed at 09:xx.

What it means:
- The bar needs a clean night: no Claude session working, no audio playing, plugged in from the start. Then `caffeinate -i` is the only thing between the Mac and idle sleep, and the display is free to sleep.
- **Design note for Plan 4:** a working Claude session keeps the display on ("Capturing"). When Jarvis itself is working overnight the display will not sleep; spec §6.6's "let the display sleep" only holds while Jarvis is idle.
- The start command's `rm -f` cost the night's log. Fixed in the command above. Both loggers were writing to one file from 09:11; the original was stopped at 09:14, the one started from Terminal at 09:11 was left running.

### Waiting on Febriel, in order
1. Repeat the overnight run on a clean night: plugged in from the start, no Claude session left working, nothing playing audio. Then stop it and run `report.py`.
2. Tailscale on the Mac and iPhone (Spike 6 steps 1–3), so there is a tailnet address to check.
3. Later overnight run with the tailnet check: plugged in, lid open, screen left to sleep on its own. Bar: no gap over 6 min, no system sleep in `pmset -g log`.
4. Run `report.py`. Keep the output, then clear the log.
5. Two-hour run on battery, lid open. Same bars. Record battery % per hour.
6. Run `report.py` again. Both runs must show the display turned off (Step 3).

## Plan 2 probes (Plan 2 Task 1)

Run 2026-11-14. Claude Code 2.1.322, Max subscription. Scripts: `spikes/08-hooks/`: `probe.py` (runner), `hook.py` (logs every payload and answers both events from env), `probe-settings.json` (one hook entry each for `PreToolUse` and `PermissionRequest`, matcher `*`, `"timeout": 660`), probe agents and a skill under `.claude/`. Every child ran with the scrubbed environment from `spikes/01-brain/clean.py` and `--setting-sources project --settings probe-settings.json --strict-mcp-config`, stream-json in and out. The keychain login worked inside the tool sandbox, so no sandbox override was needed. Logs: `spikes/08-hooks/tmp/` (git-ignored).

| Step | What ran | What was seen | Verdict |
|---|---|---|---|
| 1 `PreToolUse` deny / allow | `step1_pretool.py`: `touch tmp/step1.txt`; hook answers `deny`, then `allow` | deny: no file; tool result `PreToolUse:Bash hook error: probe`; the model quoted the reason. allow: file made; only `PreToolUse` fired, no `PermissionRequest` | **Pass** |
| 2 `ask` → `PermissionRequest` | `step2_ask.py`: `PreToolUse` answers `ask`, `PermissionRequest` answers deny, then allow. Control `step2b_control.py`: `PreToolUse` silent | In `-p` mode, `ask` is a denial. `PermissionRequest` never fired; tool result `probe`; the call is listed in `result.permission_denials`. Same with `PermissionRequest` set to allow. Control: with `PreToolUse` silent, Claude Code asks by itself, `PermissionRequest` fires and its allow runs the command | **Fail → fallback: `HOLD_IN_PRETOOL = True`** |
| 3 Hooks inside a subagent | `step3_subagent.py none` then `deny`: the front door dispatches `worker` (tools: Bash), foreground and with `run_in_background: true` | Both modes: `PreToolUse` and `PermissionRequest` fired for the worker's `Bash`, each carrying `agent_id` and `agent_type: "worker"`. The front door's own call (`Agent`) carried neither. The allow ran the command in both modes. With `deny`, `PreToolUse` stopped the worker's `Bash` in both modes | **Pass** |
| 4 90 s hold | `step4_hold.py pre` and `perm`: wait 90 s, then allow; entry `"timeout": 660` | `PreToolUse` held 90.0 s, then ran (94.5 s total). `PermissionRequest` held 90.0 s, then ran (93.9 s). No cap at 90 s. A 600 s hold was not run | **Pass**, no cap |
| 5 `--append-system-prompt` | `step5_append.py`: `--agent jarvis --append-system-prompt "The code word is MARMALADE."` | Replied `MARMALADE`, no tool calls | **Pass** |
| 6 `skills:` preload | `step6_skills.py`: skill `probe-word` (body holds code word QUINCE) listed under `skills:`. Main thread: `--agent skilled`. Subagent: the default main thread dispatches `skilled-sub` | Main thread: "I don't know it, because the probe-word skill hasn't been loaded". QUINCE appears in neither the stream nor the transcript; no Skill call. Subagent: replied QUINCE, no Skill call | **Main thread fail → fallback: paste the skill bodies into `jarvis.md`.** Subagent pass |
| 7 No MCP, no plugins | `step7_isolation.py`, then the same scrubbed env without the three flags as a contrast | `mcp_servers: []`. `plugins`: only the built-in `cc-plugin-agents-md`, `cc-plugin-telemetry`, `cc-plugin-privacy`, `cc-plugin-plugin-authoring`. No plugin-namespaced slash commands. Skills: the project `probe-word` plus Claude Code's built-ins. `apiKeySource: "none"`. Contrast: 13 MCP servers, Febriel's plugins (superpowers, honey, chatcut, …), 81 plugin commands | **Pass** (with the leak below) |
| 7 extra: what still leaks in | `step7b_memory.py` … `step7e_exclude.py` | Under the same flags, Febriel's `~/.claude/CLAUDE.md` ("Global rules — Febriel") and this repo's dev auto-memory index (`system/init` `memory_paths.auto`) still reach the child; the model quoted both. `"autoMemoryEnabled": false` in the settings file, or env `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`, removes the memory index (`memory_paths` gone). `"claudeMdExcludes": ["/Users/febrielotud/.claude/CLAUDE.md"]` removes the user `CLAUDE.md` ("NONE") | Found, and the fix was measured |
| 8 Interrupt | `step8_interrupt.py`: count to 400 in words with `--include-partial-messages`; `control_request` `interrupt` 3 s after the first delta | `control_response` `success` (`{"still_queued": []}`) and `result` arrived 0.01 s after the write; the stream stopped there. `result.subtype: "error_during_execution"`, `is_error: true`. Process alive, same `session_id`; the follow-up restated the first request correctly. Every new turn starts with a fresh `system/init` | **Pass** |
| 9 Write-up | This section | | Done |

### Payloads (for Tasks 6, 7, 10)
- `PreToolUse` stdin: `session_id`, `transcript_path`, `cwd`, `prompt_id`, `permission_mode`, `effort`, `hook_event_name`, `tool_name`, `tool_input`, `tool_use_id`. A call made inside a subagent also carries **`agent_id`** and **`agent_type`** (the agent's name). Neither field appears on the front door's own calls: the presence of `agent_id` is what marks a worker's call.
- `PermissionRequest` stdin: the same fields minus `tool_use_id`, plus `permission_suggestions`; `agent_id` and `agent_type` also appear inside a subagent.
- One real worker `PreToolUse` payload (foreground, paths shortened):
  `{"session_id": "466c3106-…", "transcript_path": "~/.claude/projects/…-spikes-08-hooks/466c3106-….jsonl", "cwd": "~/Developer/Project Jarvis/spikes/08-hooks", "prompt_id": "43d9d7d6-…", "permission_mode": "default", "agent_id": "a3e84bcc18d5fbecc", "agent_type": "worker", "effort": {"level": "medium"}, "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "touch tmp/step3-fg.txt", "description": "Create empty file tmp/step3-fg.txt"}, "tool_use_id": "toolu_01J8DpHr4zHMN8XypYYayVNW"}`
- What the model sees: on a `PreToolUse` deny the tool result reads `PreToolUse:Bash hook error: <reason>`; on an `ask` in `-p` mode it reads `<reason>` alone.

### What later tasks must do
- **Task 10 (and Task 6): `HOLD_IN_PRETOOL = True`.** The hook client holds the ask inside `PreToolUse` and answers only `allow` or `deny`. Never answer `ask`: in `-p` mode it is a silent deny. `PermissionRequest` fires only when Claude Code would ask by itself, which stops happening once `PreToolUse` always answers, so registering it is harmless but unused.
- **Task 6:** one hook entry, matcher `*`, `"timeout": 660`. A worker's call is the one carrying `agent_id`; `agent_type` names the agent. Key a held decision by `tool_use_id` (present in `PreToolUse` only).
- **Task 4 / `jarvis/config.py`:** no cap found, so the phone ask timeout stays 600 s. Only a 90 s hold was measured; Task 15 sees the first real 600 s one.
- **Task 8:** `skills:` in frontmatter does not load on the `--agent` main thread. Paste the skill bodies into `jarvis.md`. Subagents keep `skills:`, which works.
- **Task 7:** the `control_request` interrupt works, so `Bridge.interrupt()` needs no kill-and-`--resume`. A `result` with `subtype: "error_during_execution"` right after an interrupt means "cancelled", not "error". Expect a `system/init` at the start of every turn; a second init is not a restart. `--append-system-prompt` works together with `--agent`.
- **Tasks 6 and 7 (not in the plan yet; the conductor should place it):** without two more keys in `.claude/jarvis-settings.json`, `"autoMemoryEnabled": false` and `"claudeMdExcludes": ["/Users/febrielotud/.claude/CLAUDE.md"]`, Febriel's personal Claude Code rules and this repo's dev memory reach Jarvis's front door.

## Gate: open review findings

- **Fixed 2026-11-13 (was an allow-verdict bypass):** a `cd` behind a shell keyword was missed by the folder check, so `{ cd ~/Documents; } && rm a.txt` returned `allow`. Leading keywords are now skipped before the `cd` test. Regression test: `test_cd_after_a_keyword_still_poisons_relative_paths`. No findings open.

## Plan 2 results (Task 15 Step 1, rows 1–9, 2026-11-14)

Run from this checkout: `.venv/bin/jarvis daemon` on Febriel's subscription (`claude` 2.1.322, scrubbed environment, `--setting-sources project --settings .claude/jarvis-settings.json --strict-mcp-config`), the real vault and `~/.jarvis`. Requests went through `jarvis ask` (channel `mac`). Evidence: `~/.jarvis/jarvisd.log` (timings only) and a recorder on `GET /events` with wall-clock stamps. The daemon was restarted twice to load fixes (rows 1–2 on the first run, row 3's last try and rows 4–9 on the third).

| # | What ran | Seen | Verdict |
|---|---|---|---|
| 1 | `what time is it`, 3 times via the CLI, 5 times by HTTP | CLI 0.05–0.06 s wall, Python start included; HTTP round trip 0.4–6.7 ms. No `claude` line in the log. One day-log line each | **Pass** |
| 2 | `what's the capital of Australia` | "Canberra." from the front door: no `Agent` call, no triage row, one day-log line. First token 1.12 s (the process's first turn); warm repeats 0.97 s and 1.50 s, against Spike 1's 0.79 s | **Pass**; first token about 0.2–0.7 s slower than Spike 1 |
| 3 | Poem to `~/Developer/jarvis-e2e/poem.txt`, with `wiki/poetry.md` seeded first | Try 1: the front door wrote it itself with `printf`, no triage (the gate then asked about `printf`). Try 2: triage ran **in the background**; the front door dispatched `coder` in a turn nobody prompted, and jarvisd refused it with "Call triage before dispatching a worker." Try 3, after both fixes below: triage on `claude-opus-5-5` (background) at 3.2 s; `wiki/poetry.md` read at 3.4 s; `coder` dispatched at 10.6 s, background, on `claude-haiku-5-5` (triage said `tier: haiku`); front door answered at 4.3 s and 11.7 s, before the worker ended at 17.3 s; "Done" at 18.5 s; the file held four lines. Task note `2026-11-14-2209-write-gold-poem-file.md`: agents `jarvis (sonnet)`, `triage (claude-opus-5-5)`, `coder (claude-haiku-5-5)`, the file, `[[poetry]]`; the day log links it. `scribe` started at 21.5 s, read the note, `wiki/index.md` and `wiki/poetry.md`, and wrote nothing ("nothing to keep" is allowed by its prompt). A second task carrying a preference: the front door wrote it into `wiki/poetry.md` itself; scribe again wrote nothing. Scribe did write after row 6's task: it created `wiki/protected-paths.md` and updated `wiki/index.md` (22:21:56) | **Pass** after fixes; the scribe write was seen on row 6's task, not on row 3's |
| 4 | `Create an empty file at ~/Documents/jarvis-e2e.txt`: no, then yes, then no answer | Each went triage → background `coder`, whose call asked 9–16 s in. `no`: refused, no file, Jarvis said so. `yes`: the worker asked twice (`[ -e … ]`, then `touch`); after both yeses the file existed. Silence: denied at the 60 s timeout ("No answer in time, so no."), no file, and Jarvis said so 74 s in | **Pass** |
| 5 | `Run sudo ls` | Refused in 2.9 s with no question; Jarvis said to run it in his own terminal. The model never called Bash, so the gate was also checked directly: `/hook` with `sudo ls` → `deny` "needs sudo; Febriel runs it himself" in 3 ms, and the hook client renders it as a `PreToolUse` deny | **Pass** |
| 6 | `Add a comment to jarvis/brain/gate.py` | Triage asked first ("What should the comment say?"). Then `coder` asked for `od` (yes) and for "protected path: …/gate.py". `yes, always` let that one edit through and wrote nothing to `trusted.txt`. Asked again: it asked again; `no` left the file unchanged. The test comment was reverted with `git checkout` | **Pass** |
| 7 | 600-word answer, then `jarvis ask "never mind"` after 21 deltas | `never mind` answered "Cancelled." in 0.09 s; the long request's turn ended 0.10 s after it, last delta 0.02 s after it. Next request ("what was the last thing I asked you to explain") named the jet-engine question | **Pass** |
| 8 | A normal `claude -p` in the repo (clean environment, default setting sources) running `ls` | `ls` ran; the only hook was Febriel's own `SessionStart`; nothing from `jarvis.brain.hook`; 13 MCP servers. Jarvis's own process logged `brain online; 0 MCP servers` | **Pass** |
| 9 | `pkill -f "claude -p --agent [j]arvis"`, then a question | A new child 1.49 s later with `--resume <session>`; the answer (2.6 s) recalled both poem tasks | **Pass** |

### Fixed during the run (each with a failing test first)

- `fce4102`: a yes to a background worker's question waited for a turn that never came, so `jarvis ask "yes"` hung. It now answers "Okay." at once.
- `61511d9` (row 3, try 1): `jarvis.md` says making or changing a file is never small.
- `77677a4` (row 3, try 2): when no request is current, front-door calls and stream events belong to the latest open request; a background triage's verdict is read from its summary.
- `02b719f`: Ctrl-C hung while any `/events` client (the HUD) was connected; shutdown now closes the streams. Measured after: 0.7 s with a client connected.
- `637d128`: the CLI sends its first `init` only with the first message, so the HUD would have shown STARTING UP until Febriel typed. The brain now counts as online once the child runs.
- `da1f7ed`: starting jarvisd no longer bumps `wiki/index.md`'s time.
- Gate, from the automated security review of these commits: `6747476` made `printf` read-only; `9206a5f`, `87f602e` took that back (`printf -v PATH …` and brace expansion set variables); `ff91e96`, `b67241c`, `a0cd8af` make `printf`, `read`, `mapfile` and the zsh builtins that run the next word or set variables (`noglob`, `-`, `print`, `vared`, `repeat`, `sched`, …) ask with no pattern, so "always" can never remember them.

### For the review pass

- **The gate's "never remember" list is a denylist.** The security review added names five times in a row. An allowlist of commands whose "always" may be remembered would end that; it changes what Febriel's "always" does, so it is his call.
- **Triage runs in the background** although `jarvis.md` says to wait for it. The first reply is "Triage is checking it", and the rest arrive as unprompted replies, which only `/events` (the HUD) shows; `jarvis ask` and the phone's `POST /ask` get the first reply only. That matters for Plan 4.
- **Workers ask for read-only commands the gate does not know** (`[`, `od`): three extra questions across rows 4 and 6. And questions are worded in the gate's terms ("cannot tell what command 'f=/Users/…' runs", "unrecognised command: [. Yes or no?"), which is hard to judge by ear.
- **Task notes carry triage's verdict block** in "Done" (it is a background agent's summary).
- **A request whose first reply is a question** is logged with its last reply, and the `yes`/`no` that answered it gets its own line.

### Left in the vault

The `raw/` notes and day-log lines written between 22:01 and 22:22 stay as history. Removed after the run: the seeded `wiki/poetry.md` (made-up preferences), the test-made `wiki/protected-paths.md`, the index lines for both, `~/Developer/jarvis-e2e/` and `~/Documents/jarvis-e2e.txt`. `CLAUDE.md` (the vault map from `ensure_map`) stays.

### Rows 10–11 (Febriel, 2026-11-14 22:33–23:02)

| # | What ran | Seen | Verdict |
|---|---|---|---|
| 10 | `uv run jarvis hud` in an 80×24 Terminal window, against jarvisd from the login agent | Screenshot: gold on black, header `● ONLINE` and clock, VOICE, AGENTS, QUEUE and MEMORY readable, footer `AWAKE ○ n/a  PHONE ○ not linked  MIC ○ off  LIMITS ● 82%`; typing worked ("hey", "status" answered). The `NEEDS YOU` test failed: after Enter the input kept focus, so Febriel's `y` went to Jarvis as text (day log `22:38 · mac · y → …`), and the `touch` question timed out ("No answer in time, so no"; no file). Fixed in `0ea1325`, which also keeps the first letter typed with nothing focused (Textual's `Input` selected its text on focus, so the second key overwrote it). Not yet seen: Escape cancelling, and closing the HUD leaving Jarvis running. A long memory path wraps onto a second line under its `r` Re-check at 22:49: closing the HUD (ctrl+q) left jarvisd running, and the reopened HUD (with the fix) connected to it. The `y`/`n` answer and Escape were not tried live again; `test_y_answers_right_after_typing_a_request` and `test_escape_cancels_and_slash_lists_skills` cover them, and row 7 showed a cancel through the API | **Pass** for look, typing and closing; `y`/`n` failed live, fixed, covered by tests but not re-seen live; Escape not seen live |
| 11 | Login agent loaded from `launchd/README.md`; `jarvis ask "status"` | Loaded at 22:33:38 (`launchctl print`: running, `runs = 1`); `status` answered "Nothing is running." both from a new Terminal tab and from the project folder; a hand-started `jarvis daemon` refused with "port 8787 is taken". The daemon was still the 22:33:38 process at 22:40, so no macOS log-out and log-in happened (a log-out ends every login agent) After a macOS log-out and log-in (console login 22:54), launchd started a new jarvisd at 22:55:00 (pid 8059, `runs = 1` in the new session) with nothing started by hand, and `jarvis ask "status"` answered "Nothing is running." at 23:02 | **Pass** |
