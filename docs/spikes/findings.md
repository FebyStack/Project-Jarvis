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

- **After the race:** `kokoro-onnx` is still in the `spike` group in the working tree (uncommitted) and its `phonemizer` sits over misaki's `phonemizer-fork`. It lost, so it is to be removed (`uv remove --group spike kokoro-onnx`, delete `spikes/04-tts/data/`) once Spike 3 is not using `.venv`.

## Spike 5 — on-screen control (Task 10)

Run 2026-11-13. agent-desktop **1.3.0** (npm `agent-desktop`, repository `github.com/vercel-labs/agent-desktop`, published by `vercel-release-bot`), installed with `npm install -g agent-desktop@1.3.0` into `/opt/homebrew` (no sudo). npm skipped the package's `postinstall` (npm allow-scripts policy). The macOS arm64 binary and helper ship in the package and their SHA-256 sums match the bundled `.sha256` files, so nothing was downloaded. Scripts: `spikes/05-screen/step2.sh`, `step4.sh`. Logs and snapshots: `spikes/05-screen/tmp/logs/`.

Accessibility was `denied` at 23:28 and `granted` at 23:30, with no action from this worker; Febriel granted it while the spike was running. The grant covers the app that runs this Claude Code session (process chain: `Claude.app` → `disclaimer` → `~/Library/Application Support/Claude/claude-code/2.1.321/…/claude.app` → zsh). Which of those two bundles appears in the Accessibility list is **unverified**. Screen Recording is still `denied`.

| Step | Bar | Measured | Verdict |
|---|---|---|---|
| 1 Install | vercel-labs package, no sudo | 1.3.0, `/opt/homebrew/bin/agent-desktop`, checksums match | **Pass** |
| 2 TextEdit: snapshot, click, type a line | Actions succeed | Snapshot ok. **Click** on the text area: headless → `POLICY_DENIED` (a text view has no press action); `--headed` → ok (one earlier run: `ACTION_FAILED … occluded by group`, not repeated). **Type** headless → ok, and `get --property value` read the line back. Close button clicked headless → window closed with no save prompt (file-backed scratch doc) | **Pass** (click needs `--headed` on text views) |
| 2 Finder: drag a scratch file between two scratch folders | File moves | `--headed drag` with default timing (no `--duration`, `--drop-delay 800`): `ok` (`delivered_unverified`) but **file did not move**. With `--duration 1000 --drop-delay 1000 --timeout-ms 10000`: file moved, twice (once by hand, once from `step2.sh`) | **Pass** with slow timing; `ok` alone proves nothing |
| 3 Snapshot gives role and label for a button | Enough for `classify_screen` | Yes: `role` + `name` (+ `description`). Mapping below | **Pass**, two gaps noted |
| 4 Display asleep | Actions succeed; screenshot usable | Not run (👤). Screen lock is set to **immediately** (`sysadminctl -screenLock status` → `screenLock delay is immediate`), so `pmset displaysleepnow` also **locks** the session | **Waiting** — expected to test the locked case |

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
- **Gap 1 — unlabelled controls.** Finder has clickable `button`s with no `name` and no `description` (e47 above). `classify_screen` allows an empty label (`tests/brain/test_gate_screen.py` has `("", "allow")`), so a click on an unnamed control is never asked about. Recommend: a click on a node with no name and no description asks.
- **Gap 2 — which node.** agent-desktop takes only a ref. The gate must judge the node that ref points to: look it up in the snapshot Jarvis just took, or read it live with `get @ref --property text` / `--property role` right before acting.
- Command → gate action: `click`, `double-click`, `triple-click`, `right-click`, `toggle`, `check`, `uncheck` → `click`; `select @ref "Option"` → `click` with label = the option text (a menu item named "Delete" is chosen this way); `type`, `set-value` → `type` (text with a newline asks); `press` → `press` (agent-desktop's combo strings, `return`, `cmd+w`, already match the gate's key parsing); `scroll`, `scroll-to`, `expand`, `collapse` → `scroll`; `launch`, `focus-window` → `open`; `drag` → `drag`. No element to judge, so they should ask: `mouse-click`/`drag` with `--xy`, `close-app`, `clipboard-set`, `notification-action`. `batch` and `mcp` must not be exposed, or every step must go through the gate.

### Other things found
- **Screen Recording also gives window titles.** Without it, `list-windows` returns the app name as every window's title, and `wait --window <title>` never matches. `step2.sh` finds its windows by id (TextEdit) or by contents (Finder) for this reason.
- **Stage Manager is on** (`com.apple.WindowManager GloballyEnabled = 1`). `list-windows` reports only the active stage's windows, so the list changes when the foreground app changes. Jarvis must bring the target app forward (`open`, `launch --activate`, `focus-window`) before it snapshots. One `step2.sh` run lost the Finder window this way; the script now re-runs `open` if the window does not appear.
- **Finder keeps windows of deleted folders.** It moves them to the parent folder instead of closing them, so scripts must close their own windows before they delete scratch folders. One Finder window left from debugging may still sit in a background stage, showing `spikes/05-screen/tmp`; it can be closed by hand.
- Physical input (`--headed` click, drag) moves the real pointer and takes focus: it disturbs Febriel if he is at the Mac. Headless covers `type`, buttons with a press action, and windows' Close buttons.

### Step 4 (👤, not run)
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

Run 2026-11-13. Scripts: `spikes/07-awake/awake_log.py` and `report.py` (standard library only, Python 3.14.7). The overnight run started 2026-11-13 23:38 (see the change note below); the battery run has not started.

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
- **Started 2026-11-13 23:38:41 (+0800) by the conductor session** with the command below, after Febriel plugged in (first line: `power=AC batt=62 reach=1.1.1.1:ok`). The worker session's own attempt was refused by its permission check (auto mode: "unauthorized persistence"). `caffeinate` holds `PreventUserIdleSystemSleep` for the logger. Result: pending the morning report.

**Start (as run; plugged in, lid open):**

```bash
cd ~/Developer/"Project Jarvis" && mkdir -p spikes/07-awake/tmp && rm -f spikes/07-awake/tmp/awake.log && date '+%Y-%m-%dT%H:%M:%S%z' > spikes/07-awake/tmp/run.start; nohup caffeinate -i python3 spikes/07-awake/awake_log.py 1.1.1.1 > spikes/07-awake/tmp/run.out 2>&1 &
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

### Waiting on Febriel, in order
1. In the morning: stop the run and run `report.py` (commands above).
2. Tailscale on the Mac and iPhone (Spike 6 steps 1–3), so there is a tailnet address to check.
3. Later overnight run with the tailnet check: plugged in, lid open, screen left to sleep on its own. Bar: no gap over 6 min, no system sleep in `pmset -g log`.
4. Run `report.py`. Keep the output, then clear the log.
5. Two-hour run on battery, lid open. Same bars. Record battery % per hour.
6. Run `report.py` again. Both runs must show the display turned off (Step 3).

## Gate: open review findings

- **Fixed 2026-11-13 (was an allow-verdict bypass):** a `cd` behind a shell keyword was missed by the folder check, so `{ cd ~/Documents; } && rm a.txt` returned `allow`. Leading keywords are now skipped before the `cd` test. Regression test: `test_cd_after_a_keyword_still_poisons_relative_paths`. No findings open.
