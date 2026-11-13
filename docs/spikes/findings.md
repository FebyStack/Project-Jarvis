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
- Steps 3–5 (30-minute false-trigger run, launchd mic access, idle CPU) are on hold until the wake approach is chosen; launchd mic access matters whichever approach wins.

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

## Gate: open review findings

- **Fixed 2026-11-13 (was an allow-verdict bypass):** a `cd` behind a shell keyword was missed by the folder check, so `{ cd ~/Documents; } && rm a.txt` returned `allow`. Leading keywords are now skipped before the `cd` test. Regression test: `test_cd_after_a_keyword_still_poisons_relative_paths`. No findings open.
