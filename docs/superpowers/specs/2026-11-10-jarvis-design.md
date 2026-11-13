# Jarvis — design

Date: 2026-11-10 · Owner: Febriel · Status: approved by Febriel 2026-11-10, as written.

Amended 2026-11-13: hold-to-talk (§6.1, Febriel's request); second reference folded in at Febriel's request (§1, §2, §3, §6, §6.1–6.3, §7, §9, §14). The second-reference amendments were written by Claude and approved by Febriel on 2026-11-13.

Anything marked **(Claude's call)** was proposed by Claude and accepted with the approval, including "Hey Jarvis" for v1 and the strict gate.

## 1. Intent

A personal voice agent for one person on one Mac. Febriel says "Jarvis", speaks a request, and Jarvis does the work on the Mac and answers out loud. The same Jarvis is reachable from Febriel's iPhone when away from the desk, and the work still happens on the Mac. Claude Code is the engine. An Obsidian vault is the memory. The face is a gold terminal HUD.

Why: one voice layer over everything on the machine, with no tabs and no typing, that remembers what it was told and can be reached from anywhere.

Reference: the ibraviz.ai "Build your own JARVIS" carousel (instagram.com/p/DfFPLqaoO03). Jarvis keeps its loop (speak → route → execute → remember), its one-skill-per-job idea, its three-folder vault, and its HUD. Jarvis adds what that build lacks: a wake word, iPhone remote, keep-awake, on-screen control, model-tier routing, reverse engineering, and spawning sessions.

Second reference (added 2026-11-13): the Chase AI "Claude Agentic OS" carousel (instagram.com/p/DfKquhHHK3B). From it Jarvis takes: a no-model tier for fixed phrases, tap-to-talk with Escape to cancel, its two speech libraries as candidates to measure, a map file at the vault root, skills chosen from Febriel's own repeat work, a usage meter, and opening a running session in a terminal. Not taken: the Jev router model and the Codex / GPT brain switch (both need another provider), the web dashboard (Febriel asked for terminal only), and scheduled skills (routines stay out).

## 2. Goals

1. **Wake word voice on the Mac.** Say the wake word, speak, hear a spoken answer. Speech recognition and speech output both run on the Mac; no audio leaves it and none is stored.
2. **iPhone remote over a private route.** Talk to Jarvis from the phone from anywhere; the session runs on the Mac.
3. **The Mac stays reachable** whenever the lid is open, including when it would normally idle-sleep.
4. **Full machine reach:** files, terminal, and on-screen control (click, type, drag).
5. **Model routing.** A handful of fixed phrases are answered by code with no model. Sonnet handles small and convenient tasks itself. Anything bigger goes to Opus 5.5, which judges it and picks a worker on Haiku, Sonnet, Opus, or Fable.
6. **It asks.** Risky actions need a yes. Unclear or large requests get questioned before work starts.
7. **Mandatory memory.** Every session reads the vault before acting and writes to it after. This is enforced by code, not left to the model's discretion.
8. **Spawns Claude Code sessions** for long jobs and reports back.
9. **Gold terminal HUD** as the only interface on the Mac.

## 3. Non-goals (v1)

- Scheduled routines: no morning brief, daily plan, metrics pull, or nightly wrap. Febriel said no.
- Inbox, calendar, Slack panels in the HUD. (Jarvis can still be asked about them ad hoc if a connector is available; nothing is built for it.)
- Working with the lid closed, or waking the Mac from real sleep. A sleeping Mac cannot be woken from the internet; the design avoids sleep instead.
- A custom iOS app. The phone side is an iOS Shortcut.
- Languages other than English. Multiple users. Offline use. Smart-home control.
- Interrupting Jarvis mid-sentence by voice, voice-print lock, proactive alerts, screen awareness. Listed in §14 as later.
- A second brain (Codex / GPT) or a third-party router model such as Jev. Each needs another provider's account or pay-per-use credit, which the subscription-only rule excludes.
- A web dashboard. The terminal HUD is the only face on the Mac.

## 4. Anti-goals

These make Jarvis a failure even if it works:

- It does something destructive or outward-facing without a yes.
- It can be reached from the public internet.
- It uses an Anthropic API key or any pay-per-use credit. Subscription login only.
- It acts on instructions it read in a web page, email, or file as if Febriel had said them.
- It skips the vault read or the vault write.
- It types passwords, card numbers, or other credentials anywhere.

## 5. Constraints

- Mac: Apple M4 laptop, macOS 26.4. Claude Code 2.1.312, logged in with a claude.ai subscription.
- Present: node, python3, ffmpeg, Homebrew. Missing today: Tailscale, agent-desktop, and all speech components.
- Wi-Fi required. English only. Personal and local: one user, one Mac, one iPhone.
- Vault: `/Users/febrielotud/Obsidian/Jarvis` with `raw/`, `wiki/`, `outputs/`, `Home.md`. Separate from the Astro vault. Already created.
- Code: `/Users/febrielotud/Developer/Project Jarvis`.

## 6. How it works

```
 Mac microphone ─ wake word ─ speech-to-text ─┐
                                              ├─► jarvisd ─┬─ fixed phrase: answered by code, no model
 iPhone Shortcut ─ private network ─ HTTP ────┘      │     └─► Claude Code (front door, Sonnet)
                                                     │              ├─ small task: does it itself
        gold HUD ◄── events ─────────────────────────┤              └─ bigger: Opus 5.5 triage
        spoken reply ◄── text-to-speech ─────────────┤                       └─ worker agent
        Obsidian vault ◄── read before, write after ─┘                          (Haiku/Sonnet/Opus/Fable)
```

One background process, `jarvisd`, owns everything: the microphone loop, the Claude Code process, the vault, the phone endpoint, and the keep-awake. The HUD and the phone are both clients of it. This is so Jarvis keeps running when the terminal window is closed and Febriel is away.

### 6.1 Voice on the Mac

States: `IDLE → LISTENING → THINKING → SPEAKING → (follow-up window) → IDLE`.

- **Wake word:** openWakeWord running locally. It ships a ready-made "hey jarvis" model. Its pretrained models are licensed for non-commercial use, which fits a personal tool.
- **Open point — "Jarvis" vs "Hey Jarvis".** Febriel asked for "Jarvis". Only "Hey Jarvis" exists ready-made. Bare "Jarvis" needs a custom-trained model and, being one short word, will false-trigger more. **(Claude's call)** ship v1 on "Hey Jarvis" and train bare "Jarvis" as a follow-up. Febriel to confirm.
- **End of speech:** detected by silence (voice activity detection), about 0.8 s.
- **Speech-to-text:** Parakeet on Apple's MLX runtime (`parakeet-mlx`). Benchmarks on an M4 put it at roughly half a second for a short utterance and it returns blanks on silence rather than inventing words. **(Claude's call)**. `faster-whisper` (the second reference's choice) is measured beside it in Spike 3 and the better one on Febriel's own speech wins; whisper.cpp is the last resort. *(amended 2026-11-13)*
- **Text-to-speech:** Kokoro, spoken sentence by sentence as text streams in, in a British male voice. Two ways of running it are measured in Spike 4, `mlx-audio` and `kokoro-onnx` (the second reference's choice), and the faster to first sound wins. The exact voice preset is unverified and is a spike item. Fallback: macOS built-in `say -v Daniel`. *(amended 2026-11-13)*
- **Follow-up window:** for about 6 s after Jarvis finishes speaking, Febriel can reply without the wake word. This is what makes confirmations and clarifying questions usable by voice.
- **Mic gating:** the microphone is ignored while Jarvis is speaking, so it cannot hear and obey itself.
- **Mute:** "Jarvis, stop listening" and a key in the HUD turn the mic off; the HUD shows mic state at all times.
- **Hold-to-talk (added 2026-11-13, Febriel's request):** holding a key also starts listening, as a fallback when the wake word does not hear him. Speech ends when the key is released (no 0.8 s silence wait), then Jarvis answers as usual. It works with the HUD closed and in any app. A terminal cannot tell when a key is released, so the hold is read by a system-wide key listener in `jarvisd`, which needs the macOS Input Monitoring permission (Febriel grants it). The key is chosen in Plan 3; it must be one that does not type text (a modifier such as Right Option, not Space). Hold-to-talk works even while muted for the wake word.
- **Tap-to-talk (added 2026-11-13, from the second reference; Claude's call):** a short tap of the same key, under 0.3 s, starts listening exactly as the wake word does, and a pause sends. Holding it is hold-to-talk. One key, two gestures.
- **Cancel (added 2026-11-13, from the second reference):** Escape in the HUD, or saying "cancel" or "never mind", drops what Jarvis is hearing, stops it speaking, and abandons the current small exchange. It does not stop background workers or spawned sessions; those are stopped from the queue. The state machine gains a `CANCEL` event that returns `LISTENING`, `THINKING`, `SPEAKING`, and the follow-up window to `IDLE`.
- Spoken replies are short. Long output goes to the HUD and the vault, and Jarvis says where it put it.

### 6.2 The brain

`jarvisd` keeps one long-lived Claude Code process warm, started as `claude -p --agent jarvis --model sonnet --input-format stream-json --output-format stream-json --verbose`, so there is no start-up cost per utterance. It is never started with `--bare`, because bare mode does not use the subscription login.

**Routing**

| Step | Model | What it does |
|---|---|---|
| Instant (code in `jarvisd`) | none | Answers a fixed list of phrases itself, before anything reaches Claude Code. *(added 2026-11-13)* |
| Front door (`jarvis`) | Sonnet | Talks to Febriel. Does small and convenient tasks itself: open an app, find a file, answer a question, run one command, set a timer. |
| Triage (`triage`) | `claude-opus-5-5`, pinned | Called for everything the front door judges not small. Returns a verdict: which worker, which model tier, what could go wrong, and what must be asked first. Does no work itself. |
| Workers | Haiku, Sonnet, Opus, or Fable, as triage says | Do the job. |

Reading of Febriel's answer **(Claude's call)**: Sonnet decides what counts as small, so Opus is never spent on "what time is it". Everything else goes through Opus 5.5 triage, as originally asked.

**Instant answers (added 2026-11-13, from the second reference's "tier 1: rules, no AI"; Claude's call).** Febriel's answer was that small tasks go to Sonnet; this takes only the phrases below away from Sonnet, because code answers them at once and they cost nothing against the limits. The whole utterance must match after lower-casing, dropping punctuation, and dropping a leading "hey jarvis", "jarvis", or "please". A phrase with any extra words goes to Sonnet as before. No model is involved in the matching. Every instant answer is still written to the day's log.

| Said | Jarvis does |
|---|---|
| "what time is it", "what's the time" | Says the time. |
| "what's the date", "what day is it" | Says the date. |
| "stop listening", "mute" | Mic off for the wake word. |
| "start listening", "unmute" (by hold-to-talk or typed, since the mic is off) | Mic on. |
| "cancel", "never mind", "stop" | Cancel, as in §6.1. |
| "repeat that", "say that again" | Speaks its last reply again. |
| "status", "what are you working on" | Reads out the queue: what is running, waiting, and needing a yes. |
| "yes", "no", "yes always" while a yes is pending | Answers the gate (§6.5). |

The list is fixed in code for v1. Jev, the router model the reference uses for this sorting, is not used: it is a separate provider's model, and here the sorting is done by this list, then Sonnet, then Opus 5.5.

The front door dispatches workers itself, passing the tier triage chose as the per-call model. Workers are roles, not tiers:

| Agent | Default tier | Tools and skills |
|---|---|---|
| `coder` | Sonnet; Opus or Fable when triage says | Files, shell, git. **ponytail** preloaded. |
| `operator` | Sonnet | On-screen control through **agent-desktop**. |
| `reverser` | Opus | **REA** (the `rea` MCP server and the `reverse-engineer-anything` skill). |
| `researcher` | Haiku for lookups, Sonnet for synthesis | Web search and fetch, read-only files. |
| `scribe` | Haiku | Distils session notes into `wiki/`. Vault write access only. |

Guide for triage: Haiku for lookups and mechanical edits; Sonnet for ordinary multi-step work; Opus for hard reasoning, tricky debugging, reverse engineering; Fable for the hardest, longest jobs. Triage states its reason in one line, which the HUD shows.

**Skills**

- **humanizer** (blader/humanizer) is preloaded in the front door, so everything Jarvis says or writes to Febriel reads naturally. It is applied as writing rules in the same pass, not as a second rewrite, to keep replies fast.
- **ponytail** (DietrichGebert/ponytail) is preloaded in `coder` only.
- **grill-me** (mattpocock/skills) is preloaded in the front door for §6.5.
- Jarvis's own small skills live in the project's `.claude/skills/`, one per job, loaded only when needed: `vault` (how to read and write memory), `sessions` (spawn and check background sessions), `system` (apps, volume, windows, timers).
- Honey stays as it is for Febriel's ordinary Claude Code sessions; it is not loaded inside Jarvis. **(Claude's call)**
- **Skills from Febriel's own repeat work (added 2026-11-13, from the second reference).** Once, during Plan 2, the last 30 days of Febriel's Claude Code sessions and the vault are read for tasks he keeps repeating, and a shortlist is brought to him. He picks; only the picked ones become skills. Nothing is created automatically, and none of them run on a schedule.

**Staying conversational (Claude's call).** The front door never waits on a worker. Workers run in the background (background subagents, or a spawned session for long jobs), and the front door stays free to talk, take new requests, and relay questions. There is one front door and one conversation, shared by the Mac and the phone; requests are taken in arrival order. Conversation context carries across exchanges and is reset after 30 minutes of silence, when a fresh Claude Code session starts and the memory index is injected again.

**Spawning sessions.** A job triage expects to run long is started as its own background Claude Code session in the right project folder, so it survives Jarvis restarting and can be opened and steered on its own. Jarvis tracks it in the HUD queue and announces when it finishes. The exact mechanism (`claude --bg` versus a detached `claude -p` with `--resume`) is left to the builder after a spike.

Spawned sessions run under the same gate as Jarvis itself **(Claude's call)**: `jarvisd` launches them with Jarvis's settings file passed explicitly, so the rules and the permission hook travel with the session and nothing is installed at user level — Febriel's ordinary Claude Code sessions are untouched. If `jarvisd` is not running when a spawned session needs a yes, the answer is no and the job pauses until Jarvis is back (fail closed). A yes that Febriel gives personally in the Claude app's Remote Control counts.

**Limits.** When the subscription limit is hit, Jarvis says so, keeps the queue, and resumes when the limit resets. It never falls back to an API key.

### 6.3 Memory

The vault follows the reference layout:

- `raw/` — one note per session, written by `jarvisd` itself from the event stream: time, where the request came from (Mac or phone), what was asked, what was done, which agents and models ran, what was confirmed or refused, files touched. Named `YYYY-MM-DD-HHMM-short-title.md`.
- `wiki/` — durable knowledge: preferences, people, projects, decisions, how-tos. One topic per note, linked with `[[wiki-links]]`. `wiki/index.md` lists them.
- `outputs/` — things Jarvis produced for Febriel: reports, plans, drafts.
- `CLAUDE.md` at the vault root *(added 2026-11-13, from the second reference)* — the map: what each folder is for, how notes are named and linked, and the read-before, write-after rule. Any Claude session opened in the vault, Jarvis's or Febriel's own, starts with the same map. `wiki/index.md` stays the list of what is known; `CLAUDE.md` says how the vault works. Written in Plan 2.

Terms: an **exchange** is one request and its answer, from wake word back to idle. A **task** is an exchange that went to triage.

"Mandatory" is enforced, not requested **(the split between small exchanges and tasks is Claude's call)**:

- **Read before acting.** `wiki/index.md` is injected whenever a conversation starts, so Jarvis always has the memory map. For a task, the relevant notes must be opened before any worker starts; `jarvisd` refuses to dispatch otherwise. Small exchanges are not held up for a note read, so they stay inside the speed target. Every note read is logged and shown in the HUD.
- **Write after acting.** Every exchange is logged by code, whatever the model does. Small exchanges are appended as a line to the day's log, `raw/YYYY-MM-DD.md`. Each task gets its own `raw/` note, linked from the day's log.
- **Distilling.** `scribe` updates `wiki/` after each task, and sweeps the day's log once Jarvis has been idle for a while. It does not run after every small exchange, to spare the subscription limits.
- No audio is stored. Transcripts are stored as text.
- No database. Files only.

### 6.4 iPhone remote

- **Private network:** Tailscale on the Mac and the iPhone. `jarvisd` listens only on `127.0.0.1`; `tailscale serve` publishes it to Febriel's own devices over HTTPS. Tailscale Funnel (public exposure) is never used.
- **Second lock:** every request carries a secret token generated on the Mac. Febriel pastes it into the Shortcut once. A request without it is refused even from inside the private network.
- **Shortcut "Jarvis":** triggered by "Hey Siri, Jarvis" or a home-screen icon. It dictates the request, sends the text, and speaks the answer. If Jarvis needs a yes or has a clarifying question, the reply says so and the Shortcut listens again, in a loop, until the exchange is done.
- **Long jobs:** the Shortcut gets "started, I'll message you" straight away. When the job finishes or needs approval, Jarvis notifies the phone. **(Claude's call)** the notification is an iMessage from the Mac to Febriel's own Apple ID, because it needs no extra account or app. To be confirmed.
- **Fallback, no build needed:** Claude Code's own Remote Control in the Claude iOS app can still open and steer any spawned session for a full view.
- Speech-to-text on the phone is Apple's dictation, not Jarvis's local model. The phone hears typed-quality text back and reads it aloud.

Febriel must do these parts personally: create the Tailscale account, install and sign in on both devices, and paste the token into the Shortcut.

### 6.5 Asking

Two separate behaviours.

**Confirmation gate (enforced by the permission system, not by the model).**

| Without asking | Needs a yes | Never |
|---|---|---|
| Read anything | Delete or overwrite outside the free-write areas | Type passwords, card or ID numbers |
| Write inside `~/Developer` and the Jarvis vault | Send any email or message, post anything | Buy things or move money |
| Open apps, search the web | `git push`, installing software | Change system security settings |
| Read-only shell commands | Any other shell command that changes state outside the free-write areas | Anything needing `sudo` — Jarvis explains the command and Febriel runs it |
| | On-screen clicks that submit, send, pay, or delete | |

A request for a yes is spoken on the Mac or sent to the phone, whichever channel the request came from, and shown in the HUD queue as `NEEDS YOU`. On the phone the yes is given through the Shortcut; the iMessage is only a nudge and replies to it are not read. No answer within 60 s on the Mac (10 min on the phone) counts as no. Implemented with Claude Code permission rules plus a permission hook that hands the question to `jarvisd`.

Jarvis's own `.claude/` folder, its settings, and the gate's rule files are outside the free-write areas, so Jarvis cannot loosen its own gate without a yes.

**When code cannot tell what an action does — strict, with remembered approvals (Claude's call; Febriel to confirm).** The gate uses fixed rules only; no model sits inside it.

- *Shell:* a list of known read-only commands runs freely; known state-changing commands are judged by the paths they touch; anything unrecognised asks.
- *On screen:* judged from the target's role and label in the accessibility snapshot. Moving around, opening, scrolling, and typing into fields are free. Activating a control whose label matches a fixed word list (send, submit, post, publish, pay, buy, delete, remove, confirm, sign) asks, and so does pressing Return in an app that is not on the trusted list.
- *Connector tools:* read tools are free; tools that write or send ask.
- *Remembered approvals:* when Febriel answers "yes, always", that exact pattern (command shape, or app plus control) joins a trusted list and stops asking. The list is a plain file Febriel can read and edit.

The cost of strict: early on, remote on-screen work will ask often, and gets quieter as the trusted list grows. The alternative is to let a model judge the unclear cases, which is smoother but puts a model inside the gate.

**Grilling.** For any request that goes to triage, if triage finds it unclear or consequential, Jarvis asks questions one at a time until the job is pinned down, then repeats the plan in one sentence and waits for "go". Small tasks are never grilled. Reading of "it should grill-me for it" **(Claude's call)**: this is the mattpocock grill-me behaviour applied before big tasks, in addition to the confirmation gate.

**Read content is data.** Text from web pages, emails, documents, and screens is never treated as an instruction. The gate applies no matter what any agent has been told, because it sits below the model.

### 6.6 Staying awake

- While `jarvisd` runs it holds a `caffeinate -i` assertion, which stops idle sleep on power and on battery and still lets the display turn off. It needs no admin rights and changes no system setting.
- Closing the lid sleeps the Mac and Jarvis goes offline until it is opened. Accepted.
- **Battery (Claude's call):** stay awake on battery down to 20%, then warn on the phone and let the Mac sleep.
- **Unlocked with display off** is Febriel's choice so on-screen control works remotely. That means anyone who touches the Mac is in. Febriel sets the lock-screen timing in System Settings personally; Jarvis does not change security settings.
- Whether accessibility-tree actions and screenshots behave with the display asleep is a spike item.

## 7. The face

A full-screen terminal app, gold on black (`#D4AF37` text, brighter `#FFD700` for the active element, dim gold for idle), monospace, box-drawing characters. It attaches to `jarvisd`; closing it does not stop Jarvis.

```
╔════════════════════════════════════════════════════════════════════════════╗
║ J . A . R . V . I . S .                                   ● ONLINE   20:14 ║
╠══════════════════════════════╦═════════════════════════════════════════════╣
║ VOICE             LISTENING  ║ AGENTS                                      ║
║ ▁▂▃▅▇▅▃▂▁▂▃▅▇█▇▅▃▂▁▂▃▅▃▂▁    ║ jarvis   sonnet    talking to you           ║
║ "open the captions repo"     ║ triage   opus 5.5  idle                     ║
║                              ║ coder    opus      fixing export bug  04:12 ║
╠══════════════════════════════╬═════════════════════════════════════════════╣
║ QUEUE                        ║ MEMORY                                      ║
║ ▶ fix export bug    running  ║ + raw/2026-11-10-2014-export-bug.md         ║
║ ◦ tidy downloads    waiting  ║ ~ wiki/projects/captions.md                 ║
║ ? delete 14 files  NEEDS YOU ║ r wiki/preferences.md                       ║
╠══════════════════════════════╩═════════════════════════════════════════════╣
║ AWAKE ● plugged in    PHONE ● linked    MIC ● on    LIMITS ● ok            ║
╚════════════════════════════════════════════════════════════════════════════╝
```

- **VOICE:** state word, live waveform, last heard line.
- **AGENTS:** who is running, on which model, doing what, for how long.
- **QUEUE:** jobs and spawned sessions; `NEEDS YOU` rows can be answered with `y` / `n`. Enter on a spawned session opens it in a new terminal window to watch or steer *(added 2026-11-13)*.
- **MEMORY:** vault reads (`r`), new notes (`+`), updates (`~`).
- **Footer:** awake and power, phone link, mic, subscription limits. `LIMITS` shows the share of the weekly allowance used when Claude Code reports it, and otherwise `ok`, `near`, or `reached` *(amended 2026-11-13; whether the figure is available is checked in Plan 2)*.
- **Keys** *(added 2026-11-13)*: Escape cancels (§6.1); `/` lists Jarvis's skills and runs the chosen one.
- States are always shown as words as well as colour. It must be usable at 80×24. Typing a request is possible as a fallback to voice.
- States to design: starting up, offline (no Wi-Fi), mic muted, limit reached, phone not linked, vault missing or not writable (Jarvis refuses tasks, since it cannot keep the memory rule), first run (a checklist of the permissions and installs still missing).

The panels differ from the reference HUD because routines and inbox/calendar are out of scope. **(Claude's call)**

## 8. Structure

Python, one package, because the wake word, speech-to-text, and text-to-speech libraries are all Python. Terminal UI in Textual. **(Claude's call)**

```
Project Jarvis/
  PROJECT.md
  docs/superpowers/specs/         this document
  jarvis/
    daemon/     process lifecycle, state machine, event bus, keep-awake
    voice/      mic capture, wake word, end-of-speech, speech-to-text, text-to-speech
    brain/      Claude Code process bridge, session spawning, permission bridge
    memory/     raw-note writer, wiki index, vault paths
    remote/     local HTTP + WebSocket API, token check
    tui/        Textual HUD, gold theme
  .claude/
    agents/     jarvis, triage, coder, operator, reverser, researcher, scribe
    skills/     vault, sessions, system
    settings.json   permission rules and hooks
  launchd/      login agent that starts jarvisd
  shortcuts/    build steps for the iOS Shortcut
  tests/
```

Febriel's usual hybrid web layout (frontend/backend/ai/database) is not used: there is no web front end and no database. **(Claude's call)**

State lives in three places only: the in-memory state machine in `jarvisd`, Claude Code's own session transcripts, and the vault. `jarvisd` pushes events to clients over a local WebSocket; clients send requests over HTTP.

## 9. Trade-offs behind the big decisions

- **Avoid sleep rather than wake from it.** Remote wake over the internet does not exist for a Mac. Cost: battery drain when unplugged, and no lid-closed use.
- **Tailscale + Shortcut rather than the official app alone.** Gives "Hey Siri, Jarvis" hands-free and spoken answers. Cost: an account to create, a network service to keep private, and a token to guard. The official app remains as a free fallback.
- **One daemon with thin clients rather than a terminal app that does everything.** Needed so Jarvis works with no terminal open. Cost: a background process that needs microphone permission, which macOS grants awkwardly to background processes (risk 2 below).
- **A fixed phrase list rather than a router model.** Instant and free for the few things it covers, and nothing outside the Claude subscription. Cost: it only catches exact phrases; everything else still takes a Sonnet turn.
- **Sonnet front door rather than Opus on every utterance.** Seconds faster on small tasks and far lighter on limits. Cost: Sonnet may occasionally keep a task it should have escalated.
- **Local speech rather than Claude Code's built-in dictation.** Private, works with a wake word, and can speak back. Cost: models to download and tune.
- **Raw notes written by code rather than by the model.** Guarantees the memory rule. Cost: raw notes are plain logs; the readable knowledge depends on the scribe pass.
- **CLI process rather than the Agent SDK packages.** The CLI is documented to use the subscription login; the SDK packages are documented around API keys.

## 10. Risks, and the spikes that settle them first

1. **Subscription login in non-interactive mode.** Works today without `--bare`, but the docs say bare mode "will become the default for `-p` in a future release", which would require an API key. Spike: confirm the long-lived stream-json process, subagents, hooks, and the permission bridge all work on the subscription. Keep an explicit non-bare setting and have a fallback of driving an interactive session.
2. **Microphone permission for a background process.** If the login agent cannot get mic access, `jarvisd` is started from a Terminal login item instead.
3. **Wake word on Apple Silicon** and its false-trigger rate in Febriel's room, with speakers playing.
4. **Voice quality and latency.** Target: first spoken word within about 2.5 s of Febriel finishing a small request.
5. **agent-desktop:** `drag` exists but its syntax is undocumented; behaviour with the display asleep is unknown.
6. **Phone round trip:** Shortcut → Tailscale → Mac → spoken answer, including the confirm loop, on mobile data.
7. **Overnight keep-awake** on power and on battery, with Wi-Fi staying connected.
8. **Unlocked and remote** is a real exposure. The gate in §6.5 is the main protection; a spoken command from a video or another person in the room is caught only for risky actions.

## 11. Performance targets

- Wake word to `LISTENING`: under 0.3 s.
- End of speech to first spoken word, small task: about 2.5 s.
- Anything expected to take over 5 s gets a short spoken acknowledgement first.
- Idle CPU with the mic open: a few percent of one core.

## 12. Privacy

- Mac audio is processed on the Mac and discarded. Request text goes to Anthropic through Claude Code, like any session.
- Phone speech is transcribed by Apple's dictation.
- Session text is kept in the vault indefinitely unless Febriel deletes it.
- A local log file records timings and errors for debugging; no analytics leave the machine.

## 13. Setup Febriel does personally

- Grant Microphone, Accessibility, and Input Monitoring (for hold-to-talk) permissions when macOS asks.
- Create the Tailscale account; install and sign in on Mac and iPhone.
- Build the Shortcut from the steps in `shortcuts/` and paste in the token.
- Set lock-screen timing in System Settings.
- Open `/Users/febrielotud/Obsidian/Jarvis` in Obsidian once ("Open folder as vault").

Installs the build will do, each named before it runs: Tailscale, agent-desktop, the speech libraries and models, and the humanizer, ponytail, and grill-me skills.

## 14. Later, not v1

Bare "Jarvis" wake word (if not in v1), interrupting Jarvis mid-sentence by voice, talking to Jarvis from inside Obsidian (a plugin as a second front door), the vault drawn as a star map on the idle HUD, voice-print lock, proactive alerts, "what's on my screen", clipboard and file hand-off with the phone, a HUD page on the phone, routines, and a weekly tidy of `wiki/`.

## 15. Left to the builder

Library versions, the exact agent prompts, the event names, the HTTP routes, the session-spawning mechanism (after spike 1), test layout, and the order of work after the spikes. Build order should put the spikes in §10 first, since each can change the design.
