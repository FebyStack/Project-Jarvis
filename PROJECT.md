# Project Jarvis

Personal, local-only voice agent for Febriel's Mac (M4, macOS 26.4). Siri-style, gold ASCII terminal UI, Claude Code as the brain, remote from iPhone. English only. Subscription auth only — never API keys.

Status (2026-11-10): design approved, Plan 1 written and awaiting Febriel's review. Nothing built or installed; not yet a git repo.

Run/test (once Plan 1 Task 1 is done): `uv run pytest -q`.

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

## Research findings
- **Sleep:** a fully asleep Mac cannot be woken from the internet (Wake-on-LAN is LAN-only; `womp` is 0 here). Workable design = prevent system sleep while on AC, let the display sleep. Lid closed sleeps unless external display + power, or a sudo `pmset` override (user runs it). Battery = drain.
- **Remote:** Claude Code Remote Control (`claude remote-control`, Claude iOS app → Code tab). Needs claude.ai login, outbound HTTPS only, no open ports. Phone can start sessions. Docs: code.claude.com/docs/en/mobile
- **Voice:** built-in `/voice` is push-to-talk dictation only (hold Space), audio transcribed by Anthropic, needs a local mic, no spoken replies, no wake word. "Hey Jarvis" + spoken replies needs a local daemon (wake word + local STT + TTS).
- **agent-desktop:** Rust CLI, drives the OS accessibility tree, v1.1.0 (2026-11-03). Drag support reported limited — verify against the repo before promising drag. Needs Accessibility permission (user grants). GUI control needs an unlocked login session.
- **ponytail:** DietrichGebert/ponytail (`/plugin marketplace add DietrichGebert/ponytail`). Same goal as Honey (write less code) — stacking both is redundant.
- **humanizer:** blader/humanizer (`/plugin marketplace add blader/humanizer`). humanize-kit and stop-slop are already installed and overlap.
- **REA:** already installed (skill `reverse-engineer-anything` + `rea` MCP, connected).

## Environment
- Claude Code 2.1.312. Present: node, python3, ffmpeg, brew. Missing: tmux, tailscale, sox, whisper, agent-desktop.
- Docker not needed so far.
- Project dir is empty and not a git repo.

## Decisions
- **Memory vault (confirmed 2026-11-10):** separate vault at `/Users/febrielotud/Obsidian/Jarvis` (`raw/`, `wiki/`, `outputs/`, `Home.md`), not a folder inside Astro. Layout follows the Instagram reference, confirmed by Febriel. Finished blueprints still go to Astro's `Claude Code/` per the global rule unless Febriel says otherwise.
- **Febriel's answers (2026-11-10):** lid-open only, must not idle-sleep · custom phone route (not just the official app) · wake word "Jarvis" · it asks before risky actions and grills before big tasks · small/convenient tasks handled by Sonnet only, no Opus · Mac left unlocked with display off for remote GUI control · no routines (brief/plan/metrics/wrap) · ponytail for coding, humanizer for normal output.
- **Design doc:** `docs/superpowers/specs/2026-11-10-jarvis-design.md` — approved by Febriel 2026-11-10 as written (so "Hey Jarvis" for v1 and the strict, no-model gate with remembered approvals are settled).
- **Plans:** five, written one at a time because spikes can change later interfaces. Plan 1 = `docs/superpowers/plans/2026-11-10-jarvis-plan-1-foundation-and-spikes.md` (repo, vault writer, gate rules, state machine, then seven spikes). Plans 2–5 (typed Jarvis + HUD, voice, phone + keep-awake, on-screen/RE/sessions) are unwritten until Plan 1's checkpoint.
- **Obsidian copies:** `Astro/Claude Code/Jarvis Design.md` and `Jarvis Plan 1 Foundation and Spikes.md`. Re-copy if the sources change.
- **Verified for the design:** `claude -p` uses the subscription login only when NOT `--bare` (docs say bare may become the `-p` default — risk). Subagent `model` accepts `haiku|sonnet|opus|fable` or a full ID; per-call model override takes aliases only. openWakeWord ships "hey jarvis", not bare "jarvis" (pretrained models are non-commercial licence). agent-desktop installs via `npm i -g agent-desktop` or brew; has a `drag` command with undocumented syntax; needs Accessibility. STT pick: parakeet-mlx; TTS pick: Kokoro via mlx-audio (British voice unverified). grill-me = mattpocock/skills.
- **Dead end:** waking a sleeping Mac remotely. Use `caffeinate -i` instead.
