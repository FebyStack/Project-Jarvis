# Project Jarvis

Personal, local-only voice agent for Febriel's Mac (M4, macOS 26.4). Siri-style, gold ASCII terminal UI, Claude Code as the brain, remote from iPhone. English only. Subscription auth only — never API keys.

Status (2026-11-14): Plan 1 nearly done. Part A (vault writer, ask-first gate, voice state machine; 194 tests) and Spikes 1–6 are done; the Task 13 checkpoint amended the spec from the findings (`docs/spikes/findings.md`). **Open:** Spike 7 (a clean overnight run with the Mac plugged in and the Claude app quit, then 2 h on battery). Next: Plan 2, written in the planning session. Executor ledger (git-ignored, old commit hashes): `.superpowers/sdd/2026-11-10-jarvis-plan-1-foundation-and-spikes/progress.md`.

Run/test: `uv run pytest -q`. `spike` is a default uv group (`pyproject.toml`), so plain `uv sync` keeps the spike packages.

## Stated requirements
- Voice in/out on Mac; talk from iPhone while sessions run on the Mac.
- Full machine access: disk, terminal, GUI (click/type/drag).
- Can create Claude Code sessions.
- Router: Opus 5.5 judges complexity, hands off to Haiku / Sonnet / Opus / Fable agents.
- Obsidian notes mandatory every session; Obsidian is also the memory.
- Skills: blader/humanizer (outputs), ponytail (coding), vercel-labs/agent-desktop (GUI), REA (reverse engineering).
- Reference: instagram.com/p/DfFPLqaoO03 (ibraviz.ai), all 8 slides read 2026-11-10. Exact prompts are DM-gated; the design is:
  - Loop: speak → route (Claude Code picks the skill) → execute (one SKILL.md) → remember (saved to vault). "Small skills beat one giant prompt."
  - Brain: `claude` run in `~/jarvis` with `skills/{inbox,plan,metrics,trends,vault}/SKILL.md`, each loaded only when asked.
  - Memory: one vault, three folders — `raw/` (everything captured), `wiki/` (what it learned), `outputs/` (what it shipped). No database, just linked files.
  - Voice: hold Space; speech-to-text and text-to-speech both local, answers out loud, audio never leaves the machine. Push-to-talk, no wake word.
  - Face: HUD with header `J.A.R.V.I.S. ● ONLINE`, panels VITALS (inbox need-you, calls today, tasks open), TODAY (timed schedule), VOICE (waveform), COMMAND DECK (brief / plan / metrics / close day). Fed by Gmail, Calendar, Obsidian, Slack.
  - Day: 7:00 morning brief (inbox + calendar read aloud), 9:00 plan today (top 3 priorities into vault), 14:00 metrics pull, 19:00 close the day (reflection logged, tomorrow queued).
  - Not in the post (Febriel's additions): iPhone remote, keep-awake, GUI control, model-tier routing, REA, session spawning.
- Second reference: instagram.com/p/DfKquhHHK3B (chase.h.ai "Claude Agentic OS"), all 9 slides read 2026-11-13. Setup is DM-gated; the design is:
  - Stack: Opus 5.5 in Claude Code (or GPT-6 Astra in Codex, one switch) as the brain; Jev as router; faster-whisper + kokoro-onnx for local voice; Obsidian memory (`raw/`, `wiki/`, `outputs/`, plus a `CLAUDE.md` map); custom skills.
  - Router tiers: 1 = rules + saved data, no AI, instant; 2 = small fast model (Haiku); 3 = real work, opens a Claude Code terminal or runs a skill in the background.
  - Voice panel: "Tap to talk, then pause to send. Escape cancels." Text box beside it. "Speech stays local. Transcripts go to the selected provider."
  - Dashboard (web app): weekly-usage meter, top-3 directives, skills quick access (21 skills, run in background), schedule, vault drawn as a star map, status strip (core state, vault connected, terminals connected).
  - Skills come from the owner's own repeat work ("ask Claude which repeat tasks from your last 30 days qualify"), each with a trigger (daily 6:30, on publish, Fridays).
  - Two front doors (web app, Obsidian plugin) → one bridge → router → vault.

## Research findings
- **Sleep:** a fully asleep Mac cannot be woken from the internet (Wake-on-LAN is LAN-only; `womp` is 0 here). Workable design = prevent system sleep while on AC, let the display sleep. Lid closed sleeps unless external display + power, or a sudo `pmset` override (user runs it). Battery = drain.
- **Remote:** Claude Code Remote Control (`claude remote-control`, Claude iOS app → Code tab). Needs claude.ai login, outbound HTTPS only, no open ports. Phone can start sessions. Docs: code.claude.com/docs/en/mobile
- **Voice:** built-in `/voice` is push-to-talk dictation only (hold Space), audio transcribed by Anthropic, needs a local mic, no spoken replies, no wake word. "Hey Jarvis" + spoken replies needs a local daemon (wake word + local STT + TTS).
- **agent-desktop:** 1.3.0 installed (`npm i -g agent-desktop`). Type works headless; clicks on text views need `--headed`; drag works only with slow timing (`--duration 1000 --drop-delay 1000`); nothing works while the Mac is locked. Exact syntax in findings, Spike 5.
- **ponytail:** DietrichGebert/ponytail (`/plugin marketplace add DietrichGebert/ponytail`). Same goal as Honey (write less code) — stacking both is redundant.
- **humanizer:** blader/humanizer (`/plugin marketplace add blader/humanizer`). humanize-kit and stop-slop are already installed and overlap.
- **REA:** already installed (skill `reverse-engineer-anything` + `rea` MCP, connected).

## Environment
- Claude Code 2.1.322; the CLI has its own claude.ai login (Max), separate from the desktop app's. Installed: `uv` 0.12.5, Tailscale 1.104.5 (Mac App Store; tailnet `tail80d4ef.ts.net`, Mac = `jarvis-mac`, iPhone = `iphone-12-pro-max`), agent-desktop 1.3.0, speech stack in the default `spike` uv group (Parakeet, `mlx-audio` + Kokoro, openWakeWord's Silero VAD). Phone token: `~/.jarvis/token` (mode 600).
- Docker not needed so far.
- Git repo on `main` since Plan 1 Task 1. Remote `origin` = github.com/FebyStack/Project-Jarvis (public; `main` first pushed 2026-11-13). Commits carry no Claude credit; history was rewritten 2026-11-13 to strip the old trailers (backup at `refs/backup/pre-strip-claude`, never push it). `uv` 0.12.5 was already installed.
- The desktop app's child environment sets `CLAUDE_CODE_SIMPLE=1` (what `--bare` sets) and an `ANTHROPIC_BASE_URL` proxy; `jarvisd` must start `claude` with a scrubbed environment.

## Decisions
- **Memory vault (confirmed 2026-11-10):** separate vault at `/Users/febrielotud/Obsidian/Jarvis` (`raw/`, `wiki/`, `outputs/`, `Home.md`), not a folder inside Astro. Layout follows the Instagram reference, confirmed by Febriel. Finished blueprints still go to Astro's `Claude Code/` per the global rule unless Febriel says otherwise.
- **Febriel's answers (2026-11-10):** lid-open only, must not idle-sleep · custom phone route (not just the official app) · wake word "Jarvis" · it asks before risky actions and grills before big tasks · small/convenient tasks handled by Sonnet only, no Opus · ~~Mac left unlocked with display off for remote GUI control~~ (superseded 2026-11-14, below) · no routines (brief/plan/metrics/wrap) · ponytail for coding, humanizer for normal output.
- **Febriel's decisions (2026-11-14):** wake by transcription (both "Jarvis" and "Hey Jarvis") · Jarvis never repeats back what he said, and doesn't repeat settled clarifications unless the task changed · Back Tap starts the phone Shortcut ("Hey Siri, Jarvis" failed) · phone nudge = iCloud Reminder with an alert (iMessage to self doesn't notify) · on-screen control only while the Mac is unlocked; lock stays "immediately".
- **Design doc:** `docs/superpowers/specs/2026-11-10-jarvis-design.md` — approved by Febriel 2026-11-10 as written (so "Hey Jarvis" for v1 and the strict, no-model gate with remembered approvals are settled).
- **Plans:** five, written one at a time because spikes can change later interfaces. Plan 1 = `docs/superpowers/plans/2026-11-10-jarvis-plan-1-foundation-and-spikes.md` (repo, vault writer, gate rules, state machine, then seven spikes). Plans 2–5 (typed Jarvis + HUD, voice, phone + keep-awake, on-screen/RE/sessions) are unwritten until Plan 1's checkpoint.
- **Obsidian copies:** `Astro/Claude Code/Jarvis Design.md` and `Jarvis Plan 1 Foundation and Spikes.md`. Re-copy if the sources change.
- **Measured in Plan 1 (2026-11-13/14; details in `docs/spikes/findings.md`):**
  - Brain: long-lived `claude -p` stream-json on the subscription works; agents run on their models (triage on `claude-opus-5-5`, per-call tier override); first token 0.79 s warm. Start it with a scrubbed env and `--setting-sources project --settings … --strict-mcp-config` (Febriel's user allow rules and plugins otherwise leak in). Gate from a `PreToolUse` hook; `PermissionRequest` hook for the yes/no hand-off (it fires only when Claude Code would ask). Spawn = detached `claude -p` + `--resume <id>`; `claude --bg` needs folder trust.
  - Voice: wake by transcription (Silero VAD → Parakeet → fuzzy "Jarvis" in the first 3 words): ~88 % on his voice, 0 false wakes in 29 min, 2–4 % CPU. Parakeet 0.17 s per request, 1 meaning error in 8. TTS `mlx-audio` + Kokoro `bm_daniel`: first audio 0.19 s; warm up at start (first synth 4–6 s). End of speech → first word 1.95 s summed, ~2.2–2.8 s realistic vs the 2.5 s bar. Mic opens from a launchd agent.
  - Phone: Tailscale serve (tailnet only) + token; under 4 s on mobile data; reply loop via `"loop": "yes"`; Back Tap; Reminder alert reaches the iPhone. Keep Tailscale on the iPhone connected (VPN On Demand).
  - Screen: agent-desktop fails while locked. Stage Manager is on: bring the app forward before a snapshot.
  - Awake: open. The Claude app holds the Mac awake while any session works (setting "Keep computer awake while Claude works" is on).
- **Hold-to-talk (Febriel, 2026-11-13):** hold a key to talk to Jarvis as a fallback when the wake word misses him. Spec §6.1 amended. Needs a system-wide key listener (Input Monitoring permission); key chosen in Plan 3.
- **Second reference folded in (2026-11-13, Febriel asked; amendments written by Claude and approved by him the same day):** adopted — instant no-model answers for a fixed phrase list (spec §6.2; narrows his "small tasks go to Sonnet" answer for those phrases only), tap-to-talk + Escape/"cancel" (§6.1), `CLAUDE.md` vault map (§6.3), skill shortlist from his last 30 days (§6.2), usage share in the HUD footer, Enter opens a spawned session, `/` skill list (§7); faster-whisper and kokoro-onnx added as measured candidates in Plan 1 Tasks 8–9. Rejected — Jev (TypeSafe AI's decision model, a separate provider; breaks subscription-only), Codex/GPT brain switch (same reason), web dashboard (terminal-only requirement), scheduled skills (routines stay out). Later — Obsidian plugin front door, star-map idle HUD. Plan 1 has a "Carried into later plans" table saying which plan builds each.
- **Dead ends:** waking a sleeping Mac remotely (use `caffeinate -i`) · openWakeWord's pretrained "hey jarvis" (3 of 10 for Febriel) · a quick custom wake model on his voice (too little data; the full openWakeWord recipe needs Piper + 17 GB) · faster-whisper small.en int8 (1.02 s, more errors, "You" on silence) · kokoro-onnx (misses 0.5 s first audio; clashes with misaki's phonemizer-fork) · "Hey Siri, Jarvis" · iMessage to own Apple ID as a nudge · on-screen control while locked · Shortcuts If comparing text after import (value dropped; use "does not have any value").

last Claude session: 2026-11-14 17:40
