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

## Gate: open review findings

- **Fixed 2026-11-13 (was an allow-verdict bypass):** a `cd` behind a shell keyword was missed by the folder check, so `{ cd ~/Documents; } && rm a.txt` returned `allow`. Leading keywords are now skipped before the `cd` test. Regression test: `test_cd_after_a_keyword_still_poisons_relative_paths`. No findings open.
