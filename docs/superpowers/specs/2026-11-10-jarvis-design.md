# Jarvis — design

Date: 2026-11-10 · Owner: Febriel · Status: approved by Febriel 2026-11-10, as written.

Amended 2026-11-13: hold-to-talk (§6.1, Febriel's request); second reference folded in at Febriel's request (§1, §2, §3, §6, §6.1–6.3, §7, §9, §14). The second-reference amendments were written by Claude and approved by Febriel on 2026-11-13.

Amended 2026-11-14 at the Plan 1 checkpoint (Task 13), from the spike findings in `docs/spikes/findings.md`: §5, §6, §6.1, §6.2, §6.4, §6.5, §6.6, §9, §10, §11, §12, §13, §14, §15. Decisions Febriel made the same day are marked as his: wake by transcription, no parroting, settled clarifications, Back Tap, the Reminder nudge, on-screen control only while unlocked. Spike 7 (staying awake overnight and on battery) is still to run.

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

- Mac: Apple M4 laptop, macOS 26.4. Claude Code 2.1.322 (it updates itself). The command-line `claude` needs its own login: the desktop app's sign-in does not carry over to processes `jarvisd` starts. Febriel signed the CLI in on 2026-11-13 (claude.ai, Max plan). *(amended 2026-11-14, Spike 1)*
- Present: node, python3, ffmpeg, Homebrew, `uv`. Installed during Plan 1: Tailscale 1.104.5 (Mac App Store) on the Mac and the iPhone (tailnet `tail80d4ef.ts.net`, the Mac named `jarvis-mac` inside it), agent-desktop 1.3.0, and the speech stack in the `spike` dependency group (Parakeet, Silero voice detection, `mlx-audio` with Kokoro). *(amended 2026-11-14)*
- Wi-Fi required. English only. Personal and local: one user, one Mac, one iPhone.
- Vault: `/Users/febrielotud/Obsidian/Jarvis` with `raw/`, `wiki/`, `outputs/`, `Home.md`. Separate from the Astro vault. Already created.
- Code: `/Users/febrielotud/Developer/Project Jarvis`.

## 6. How it works

```
 Mac mic ─ speech detect ─ speech-to-text ────┐
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

- **Wake by transcription (amended 2026-11-14, Spikes 2–3; Febriel's choice):** no wake-word model. A voice-activity detector (Silero) cuts the mic stream into utterances, Parakeet transcribes each one on the Mac, and Jarvis wakes if one of the first three words is close to "Jarvis" (fuzzy match; Parakeet usually hears his "Jarvis" as "Jervis"). Both "Jarvis" and "Hey Jarvis" wake it, and "Jarvis, set a timer for ten minutes" works in one breath: the words after the name are the request. Measured on Febriel's voice: about 88 % of utterances woke it (misses heard as "Jovis", "Pervis", "Agries"), 0 false wakes in 29 minutes of video, music and other people talking, 2–4 % of one core. Plan 3 tunes the match (about 0.7 similarity takes "Jovis" and still rejects "Travis") against a recorded set. openWakeWord is dropped: its pretrained "hey jarvis" caught 3 of 10 of Febriel's tries, and a quick model trained on his voice failed for lack of data.
- **"Jarvis" vs "Hey Jarvis": settled 2026-11-14.** Both work with wake by transcription, so bare "Jarvis", which Febriel asked for, is in v1.
- **End of speech:** detected by silence (voice activity detection), about 0.8 s. Measured: end of speech to transcript about 1 s, of which 0.8 s is the silence wait. *(amended 2026-11-14)*
- **Speech-to-text:** Parakeet (`mlx-community/parakeet-tdt-0.6b-v2`, English, through `parakeet-mlx`). Measured on Febriel's speech (Spike 3): 0.17 s median per request, 1 meaning-changing error in 8 ("captions repo" heard as "captions report"), nothing on silence. `faster-whisper` `small.en` int8 took 1.02 s, made 3 errors in 8 and turned silence into "You", so Parakeet is the engine; whisper.cpp was not needed. *(amended 2026-11-14)*
- **Text-to-speech:** Kokoro through `mlx-audio` (`mlx-community/Kokoro-82M-bf16`, British English, with `misaki[en]`), voice **`bm_daniel`**, picked by Febriel by ear, spoken sentence by sentence as text streams in. Measured (Spike 4): first audio 0.19 s, no gaps between sentences. `kokoro-onnx` missed the 0.5 s first-audio bar. The first synthesis after loading takes 4–6 s, so `jarvisd` loads the model and speaks a throwaway sentence at start-up, never on the first reply. Fallback: macOS built-in `say -v Daniel`. *(amended 2026-11-14)*
- **Follow-up window:** for about 6 s after Jarvis finishes speaking, Febriel can reply without the wake word. This is what makes confirmations and clarifying questions usable by voice.
- **Mic gating:** the microphone is ignored while Jarvis is speaking, so it cannot hear and obey itself.
- **Mute:** "Jarvis, stop listening" and a key in the HUD turn the mic off; the HUD shows mic state at all times.
- **Hold-to-talk (added 2026-11-13, Febriel's request):** holding a key also starts listening, as a fallback when the wake word does not hear him. Speech ends when the key is released (no 0.8 s silence wait), then Jarvis answers as usual. It works with the HUD closed and in any app. A terminal cannot tell when a key is released, so the hold is read by a system-wide key listener in `jarvisd`, which needs the macOS Input Monitoring permission (Febriel grants it). The key is chosen in Plan 3; it must be one that does not type text (a modifier such as Right Option, not Space). Hold-to-talk works even while muted for the wake word.
- **Tap-to-talk (added 2026-11-13, from the second reference; Claude's call):** a short tap of the same key, under 0.3 s, starts listening exactly as the wake word does, and a pause sends. Holding it is hold-to-talk. One key, two gestures.
- **Cancel (added 2026-11-13, from the second reference):** Escape in the HUD, or saying "cancel" or "never mind", drops what Jarvis is hearing, stops it speaking, and abandons the current small exchange. It does not stop background workers or spawned sessions; those are stopped from the queue. The state machine gains a `CANCEL` event that returns `LISTENING`, `THINKING`, `SPEAKING`, and the follow-up window to `IDLE`.
- Spoken replies are short. Long output goes to the HUD and the vault, and Jarvis says where it put it.
- **No parroting (amended 2026-11-14, Febriel):** Jarvis never repeats back what Febriel just said ("You said: …"). It answers or acts.
- **Speech without the wake name (amended 2026-11-14):** waking by transcription means everything said near the Mac is transcribed, including other people. The text never leaves the Mac, and an utterance without the wake name is discarded at once: never logged, never shown, never written to the vault.
- **Plan 3, as built and confirmed (amended 2026-11-22):**
  - **The name rule.** Only the first three words count. A word wakes Jarvis when either of these holds:
    - it scores at least 0.70 against "jarvis", starts with "j" and has at least 5 letters;
    - it scores at least 0.80 and has at least 6 letters.

    "javi" and "javier" also wake it: that is how Febriel is heard (Task 14). "travis" stays rejected.
  - **The talk key is Right Option** (key code 61).
    - A tap under 0.3 s starts listening with the tone.
    - A hold records from the moment the key goes down, and Jarvis engages after a **0.8 s grace** (Febriel's chords for é, ñ and ⌥← come 87–603 ms after the key). Right Option used for typing therefore stops nothing and shows nothing.
    - The key works in every state. In `SPEAKING` it cuts the speech short and listens.
  - **Cancel while speaking.** Escape, the key, or "Jarvis, never mind" silence Jarvis within 0.2 s.
  - **Muted closes the mic stream.** The orange indicator goes off. Only the key opens the mic while muted, and only for that hold.
  - **The tone** plays on a bare "Jarvis" and on a tap.
  - **Timeouts and caps.**
    - Nothing said for 8 s after the tone returns to `IDLE`.
    - One utterance is cut at 15 s, and the cut start is kept for the rest of the request.
    - A hold is capped at 60 s.
  - **Mac replies are always spoken**, typed or said. Phone replies are not.
  - **The follow-up window (Febriel, 2026-11-17)** opens only after a reply that asks something (ends in "?") or while a yes/no question waits. A plain answer goes straight back to `IDLE`, because other people talking in the room were otherwise taken as follow-ups. A bare reaction in the window ("Okay.", "Huh?", "Thanks") ends the exchange instead of going to Claude.
  - **Holding line (Febriel, 2026-11-22).** If a mac request is still thinking 1.5 s after it was sent and nothing has been said, jarvisd says "Looking that up.", "On it." or "One moment." The wording follows what the front door is doing. The line changes no state, never plays while the talk key is down, and never plays after a stop.

### 6.2 The brain

`jarvisd` keeps one long-lived Claude Code process warm, started as `claude -p --agent jarvis --model sonnet --input-format stream-json --output-format stream-json --verbose`, so there is no start-up cost per utterance. It is never started with `--bare`, because bare mode does not use the subscription login.

Measured and required (amended 2026-11-14, Spike 1): the process runs on the subscription (`apiKeySource: none`), remembers across messages, runs `triage` on `claude-opus-5-5` and workers on the per-call tier, and reaches the first text token in 0.79 s median when warm. It must start with a **scrubbed environment** (no `CLAUDE_*` or `ANTHROPIC_*` variables: a Claude session's environment carries `CLAUDE_CODE_SIMPLE=1`, which is what `--bare` sets, and inheriting it broke the login) and with **only Jarvis's own configuration**: `--setting-sources project --settings <Jarvis's settings> --strict-mcp-config --mcp-config <Jarvis's MCP list>`. Otherwise Febriel's personal allow rules (for example `Bash(cp *)`) and plugins load into Jarvis and get around the gate.

**Routing**

| Step | Model | What it does |
|---|---|---|
| Instant (code in `jarvisd`) | none | Answers a fixed list of phrases itself, before anything reaches Claude Code. *(added 2026-11-13)* |
| Front door (`jarvis`) | Sonnet | Talks to Febriel. Does small and convenient tasks itself: open an app, find a file, answer a question, run one command, set a timer. |
| Triage (`triage`) | `claude-opus-5-5`, pinned | Called for everything the front door judges not small. Returns a verdict: which worker, which model tier, what could go wrong, and what must be asked first. Does no work itself. |
| Workers | Haiku, Sonnet, Opus, or Fable, as triage says | Do the job. |

Reading of Febriel's answer **(Claude's call)**: Sonnet decides what counts as small, so Opus is never spent on "what time is it". Everything else goes through Opus 5.5 triage, as originally asked.

*(amended 2026-11-14, Plan 2 end-to-end run; Claude's call, Febriel to confirm)* Making or changing a file is never small, even when one command would do it: in the run, Sonnet wrote a requested poem to a file itself and skipped triage. In practice triage also runs in the background, so the front door's first reply is "triage is checking it" and the outcome arrives in later replies (shown in the HUD; a request through `POST /ask` gets only the first reply).

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
| "stop Nova" *(amended 2026-11-23, Plan 4)* | Stops that one agent and says "Stopped Nova." |
| "yes to Nova", "no to Nova", "yes always to Nova" *(amended 2026-11-23, Plan 4)* | Answers that agent's open question. |

*(amended 2026-11-23, Plan 4)* A heard word matches a running agent's name only if it is that name or a close mis-hearing: the same first letter (b and v count as one, p and f as one), a length within one letter, and not a dictionary word. A word that matches no running name is not an instant phrase.

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
- *(amended 2026-11-14, Plan 2 probes)* `skills:` in an agent's frontmatter does not load on the `--agent` main thread, so the humanizer and grill-me bodies are pasted into `jarvis.md` below a `<!-- vendored skills -->` line. Subagents keep `skills:`, which works. All three skills are vendored at pinned commits (`.claude/skills/VENDORED.md`), because `--setting-sources project` keeps Febriel's user-level plugins out of Jarvis.
- Jarvis's own small skills live in the project's `.claude/skills/`, one per job, loaded only when needed: `vault` (how to read and write memory), `sessions` (spawn and check background sessions), `system` (apps, volume, windows, timers).
- Honey stays as it is for Febriel's ordinary Claude Code sessions; it is not loaded inside Jarvis. **(Claude's call)**
- **Skills from Febriel's own repeat work (added 2026-11-13, from the second reference).** Once, during Plan 2, the last 30 days of Febriel's Claude Code sessions and the vault are read for tasks he keeps repeating, and a shortlist is brought to him. He picks; only the picked ones become skills. Nothing is created automatically, and none of them run on a schedule.
- *(amended 2026-11-14, Febriel's choice)* The shortlist turned up little worth a new skill. Instead Jarvis gets the skills already installed in his Claude desktop app (81 on 2026-11-14), with these limits:
  - Skill files only: no plugin hooks, permission rules or connectors, so the gate stays the only thing that approves what Jarvis does.
  - A skill that declares its own hooks, or holds a !`command` line that runs as it loads, is never linked, for the same reason.
  - Only the skills that can run without the desktop app's own tools or connectors.
  - superpowers comes in; honey stays out.
  - They are linked afresh at every `jarvisd` start and passed to Claude Code with `--add-dir`, so his edits carry over.
  - A small reply's first token was unchanged (0.95–1.13 s).

**Staying conversational (Claude's call).** The front door never waits on a worker. Workers run in the background (background subagents, or a spawned session for long jobs), and the front door stays free to talk, take new requests, and relay questions. There is one front door and one conversation, shared by the Mac and the phone; requests are taken in arrival order. Conversation context carries across exchanges and is reset after 30 minutes of silence, when a fresh Claude Code session starts and the memory index is injected again.

**Spawning sessions.** A job triage expects to run long is started as its own background Claude Code session in the right project folder, so it survives Jarvis restarting and can be opened and steered on its own. Jarvis tracks it in the HUD queue and announces when it finishes. Mechanism (settled 2026-11-14, Spike 1): a detached `claude -p` started in its own process group, continued later with `--resume <session-id>`. It outlives its parent and needs no folder trust. `claude --bg` refuses any folder not yet trusted in interactive `claude`, so it is not used.

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
- **Distilling.** `scribe` updates `wiki/` after each task, and sweeps the day's log once Jarvis has been idle for a while. It does not run after every small exchange, to spare the subscription limits. *(amended 2026-11-14, Plan 2)* Each `scribe` run is its own one-shot `claude -p --agent scribe --model haiku` process under Jarvis's settings file, started detached by `jarvisd` once a task's note is written, or by the idle sweep after 20 minutes of quiet when the day's log has grown. Distilling never uses the front door's conversation or holds it up. It may decide there is nothing to keep and change nothing.
- No audio is stored. Transcripts are stored as text.
- No database. Files only.

### 6.4 iPhone remote

- **Private network:** Tailscale on the Mac and the iPhone. `jarvisd` listens only on `127.0.0.1`; `tailscale serve` publishes it to Febriel's own devices over HTTPS. Tailscale Funnel (public exposure) is never used. Measured (amended 2026-11-14, Spike 6): under 4 s from the end of his request to the spoken answer on mobile data; 401 without the token; not reachable with Tailscale off, and public DNS does not know the name. Tailscale on the iPhone must stay connected (turn on its VPN On Demand), or the Shortcut reports that the server cannot be found. The very first request after HTTPS is enabled waits about 30 s for the certificate.
- **Second lock:** every request carries a secret token generated on the Mac. Febriel pastes it into the Shortcut once. A request without it is refused even from inside the private network.
- **Shortcut "Jarvis":** triggered by **Back Tap** (double-tap the back of the iPhone) or its tile/home-screen icon. **(Amended 2026-11-14:** "Hey Siri, Jarvis" did not start it in testing; Febriel chose Back Tap.) It dictates the request, sends the text, and speaks the answer. If Jarvis needs a yes or has a clarifying question, the reply says so and the Shortcut listens again, in a loop, until the exchange is done. The reply carries `"loop": "yes"` while Jarvis wants an answer and leaves `loop` out when the exchange is done; the Shortcut stops when `loop` has no value (Shortcuts cannot reliably compare true/false values). The Shortcut is generated as a signed file without the token (`shortcuts/`), Febriel pastes the token, and it reaches the iPhone by AirDrop. *(amended 2026-11-14)*
- **Long jobs:** the Shortcut gets "started, I'll message you" straight away. When the job finishes or needs approval, Jarvis notifies the phone. the notification is **an iCloud Reminder with an alert** that Jarvis adds on the Mac; it syncs to the iPhone and notifies there, with no extra account or app. **(Amended 2026-11-14, Febriel's choice:** the earlier iMessage to his own Apple ID was tested and does not notify the iPhone, because a message to yourself counts as sent by you.)
- **Fallback, no build needed:** Claude Code's own Remote Control in the Claude iOS app can still open and steer any spawned session for a full view.
- Speech-to-text on the phone is Apple's dictation, not Jarvis's local model. The phone hears typed-quality text back and reads it aloud.

Febriel must do these parts personally: create the Tailscale account, install and sign in on both devices, and paste the token into the Shortcut. All done 2026-11-14, with Back Tap set up.

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

A request for a yes is spoken on the Mac or sent to the phone, whichever channel the request came from, and shown in the HUD queue as `NEEDS YOU`. On the phone the yes is given through the Shortcut; the Reminder is only a nudge and nothing done to it is read as an answer. No answer within 60 s on the Mac (10 min on the phone) counts as no. Implemented with a `PreToolUse` hook that runs the gate on every tool call, and a `PermissionRequest` hook that hands a yes/no to `jarvisd`. *(amended 2026-11-14, Spike 1: `PermissionRequest` alone fires only when Claude Code itself would ask, so it would miss calls Claude Code already allows. Tested: the hook holds the call until it is answered, deny blocks it, allow runs it, and the hook travels to spawned sessions through `--settings`.)*

*(amended 2026-11-14, Plan 2 probes)* In `-p` mode a `PreToolUse` answer of `ask` is a silent no and `PermissionRequest` never fires, so `jarvisd` holds the call inside `PreToolUse` until Febriel answers and then allows or denies it; the `PermissionRequest` hook stays registered as a net. If `jarvisd` cannot be reached, the hook answers no.

Jarvis's own `.claude/` folder, its settings, and the gate's rule files are outside the free-write areas, so Jarvis cannot loosen its own gate without a yes. *(amended 2026-11-14, Plan 2)* The whole project folder `~/Developer/Project Jarvis` (the gate's code and the Python that runs it) and `~/.jarvis` (token, trusted list, log) are protected, although `~/Developer` is otherwise free-write: a write there asks every time and can never be remembered with "yes, always". A web fetch of `localhost`, a loopback, private or link-local address, or a `.local` or `.ts.net` name asks the same way, so Jarvis cannot reach its own API to answer its own question. Shell builtins that set variables or run the next word (`export`, `printf`, `read`, `mapfile`, and zsh's `noglob`, `print`, `vared` and similar) ask and are never remembered either.

*(amended 2026-11-14, Claude's call, from the Plan 2 security pass; Febriel to confirm)* A write into any `.git`, `.claude`, `.obsidian` or `.vscode` folder, or to a `.envrc` file, wherever it is (free-write areas included, letter case ignored, symlinks followed), asks every time and can never be remembered with "yes, always": files there run code later without Jarvis running anything.

**When code cannot tell what an action does — strict, with remembered approvals (Claude's call; Febriel to confirm).** The gate uses fixed rules only; no model sits inside it.

- *Shell:* a list of known read-only commands runs freely; known state-changing commands are judged by the paths they touch; anything unrecognised asks.
- *On screen:* judged from the target's role and label in the accessibility snapshot. Moving around, opening, scrolling, and typing into fields are free. Activating a control whose label matches a fixed word list (send, submit, post, publish, pay, buy, delete, remove, confirm, sign) asks, and so does pressing Return in an app that is not on the trusted list. A click on a control with no readable label asks every time and cannot be remembered with "yes, always", except on passive targets where a click only places focus, scrolls or selects (agent-desktop roles `textfield`, `scrollarea`, `scrollbar`, `list`, `outline`, `cell`), which stay free. *(amended 2026-11-13, from Spike 5)* On-screen control works only while the Mac is unlocked (§6.6).
- *Connector tools:* read tools are free; tools that write or send ask.
- *Remembered approvals:* when Febriel answers "yes, always", that exact pattern (command shape, or app plus control) joins a trusted list and stops asking. The list is a plain file Febriel can read and edit.

*(amended 2026-11-15, the Plan 2 review pass; Febriel approved "fix all")* For shell commands, "yes, always" now remembers only a short allowlist (`ln`, `chmod`, `defaults`, `say` and the listed git, brew, npm, pip and uv subcommands). Every other command asks each time. Even a remembered command must not reach a protected path or a local address. Shell text the gate cannot read exactly (`$'…'`, `${…}`, zsh's `>!` and `=name`, control characters) asks and is never remembered. A bare "yes" or "no" answers only when one question is open on that channel; with several, the HUD answers each by id. The "without asking" column covers opening an app by its full path, the volume and a notification, in the exact forms the `system` skill uses. Shell and login start-up files (`.zshrc` and the like, `.gitconfig`, `.ssh`, `LaunchAgents`) and the folders holding the programs Jarvis runs (`~/.local/bin`, `/opt/homebrew`, `/usr/local`) are protected like Jarvis's own folder.

The cost of strict: early on, remote on-screen work will ask often, and gets quieter as the trusted list grows. The alternative is to let a model judge the unclear cases, which is smoother but puts a model inside the gate.

**Grilling.** For any request that goes to triage, if triage finds it unclear or consequential, Jarvis asks questions one at a time until the job is pinned down, then repeats the plan in one sentence and waits for "go". **Once a task is clarified, those clarifications are not repeated (amended 2026-11-14, Febriel):** later replies about the same task do not restate settled answers or re-ask settled questions, unless the task has changed. Small tasks are never grilled. Reading of "it should grill-me for it" **(Claude's call)**: this is the mattpocock grill-me behaviour applied before big tasks, in addition to the confirmation gate.

**Read content is data.** Text from web pages, emails, documents, and screens is never treated as an instruction. The gate applies no matter what any agent has been told, because it sits below the model.

### 6.6 Staying awake

- While `jarvisd` runs it holds a `caffeinate -i` assertion, which stops idle sleep on power and on battery and still lets the display turn off. It needs no admin rights and changes no system setting. Overnight and battery runs are still to measure (Spike 7). Found so far: while any Claude session is working, the Claude app keeps the display on, so the display sleeps only while Jarvis is idle. *(amended 2026-11-14)*
- Closing the lid sleeps the Mac and Jarvis goes offline until it is opened. Accepted.
- **Battery (Claude's call):** stay awake on battery down to 20%, then warn on the phone and let the Mac sleep.
- **On-screen control needs the Mac unlocked (amended 2026-11-14, Spike 5; Febriel's decision).** The screen lock is set to "immediately", so when the display sleeps the Mac also locks, and agent-desktop cannot see app windows while it is locked (tested: nothing could be clicked, typed or dragged). Febriel keeps the lock as it is. When the Mac is locked, Jarvis says that on-screen work needs it unlocked and holds or refuses those steps; files, the terminal and everything else keep working. Jarvis never changes the lock setting.

## 7. The face

*(amended 2026-11-23, Plan 4)* The face is now the on-screen design in `2026-11-17-jarvis-screen-hud-design.md`, amended by `2026-11-23-jarvis-face-tether-design.md`: a red circle with a bead per agent. The terminal app below stays as `jarvis hud`, optional, and **red replaces gold** (`#FF3B30` active, `#C2241B` text and lines, `#6B1512` idle and borders).

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
- **QUEUE:** jobs and spawned sessions; `NEEDS YOU` rows can be answered with `y` / `n` (and `a` for "yes, always") while the input line is empty and not being typed in. Enter on a spawned session opens it in a new terminal window to watch or steer *(added 2026-11-13)*.
- **MEMORY:** vault reads (`r`), new notes (`+`), updates (`~`).
- **Footer:** awake and power, phone link, mic, subscription limits. `LIMITS` shows the share of the weekly allowance used when Claude Code reports it, and otherwise `ok`, `near`, or `reached` *(amended 2026-11-13; whether the figure is available is checked in Plan 2)*.
- **Keys** *(added 2026-11-13)*: Escape cancels (§6.1); `/` lists Jarvis's skills and runs the chosen one.
- States are always shown as words as well as colour. It must be usable at 80×24. Typing a request is possible as a fallback to voice.
- States to design: starting up, offline (no Wi-Fi), mic muted, limit reached, phone not linked, vault missing or not writable (Jarvis refuses tasks, since it cannot keep the memory rule), first run (a checklist of the permissions and installs still missing). *(amended 2026-11-14, Plan 2)* With the vault missing or not writable, Jarvis refuses **every** request, not only tasks: even a small exchange must be logged, and it cannot be.

The panels differ from the reference HUD because routines and inbox/calendar are out of scope. **(Claude's call)**

*(amended 2026-11-22, Plan 3)*
- **`MIC` words:** `loading`, `on`, `on, no key` (no Input Monitoring grant), `off`, `no permission` (2 s of silent samples), `muted`, or a model-load error such as `no models`.
- **`ctrl+l`** in the HUD toggles mute.
- The VOICE waveform is fed by a `level` event (0–1, about ten per second while the mic is open).
- The front door runs on Sonnet at low effort, and triage on Sonnet at medium effort (§11).

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
    tui/        Textual HUD, gold theme (red since 2026-11-23)
    face/       the on-screen circle and beads: model, controller, place, tether, mark, page/, beads, threads, app (added 2026-11-23, Plan 4)
  .claude/
    agents/     jarvis, triage, coder, operator, reverser, researcher, scribe
    skills/     vault, sessions, system
    jarvis-settings.json   hooks, passed with --settings (no settings.json)
  launchd/      login agents that start jarvisd and, since 2026-11-23, com.febriel.jarvis-face
  shortcuts/    build steps for the iOS Shortcut
  tests/
```

Febriel's usual hybrid web layout (frontend/backend/ai/database) is not used: there is no web front end and no database. **(Claude's call)**

*(amended 2026-11-14, Plan 2)* Jarvis's hooks and settings live in `.claude/jarvis-settings.json`, passed to every `claude` that `jarvisd` starts with `--settings`. There is no `.claude/settings.json`: a project settings file would load into every Claude Code session opened in this repo, putting Febriel's own development sessions behind Jarvis's gate (and refusing everything while `jarvisd` is down). Every path, port and timing is defined once, in `jarvis/config.py`. The command line is `jarvis daemon | hud | ask | doctor | shortlist` (`jarvis/cli.py`). `operator`, `reverser` and the `sessions` skill arrive with Plan 5.

State lives in three places only: the in-memory state machine in `jarvisd`, Claude Code's own session transcripts, and the vault. `jarvisd` pushes events to clients over a local WebSocket; clients send requests over HTTP.

## 9. Trade-offs behind the big decisions

- **Avoid sleep rather than wake from it.** Remote wake over the internet does not exist for a Mac. Cost: battery drain when unplugged, and no lid-closed use.
- **Tailscale + Shortcut rather than the official app alone.** Gives a one-gesture start (Back Tap; "Hey Siri, Jarvis" did not work in testing) and spoken answers. Cost: an account to create, a network service to keep private, and a token to guard. The official app remains as a free fallback.
- **One daemon with thin clients rather than a terminal app that does everything.** Needed so Jarvis works with no terminal open. Cost: a background process that needs microphone permission, which macOS grants awkwardly to background processes (risk 2 below).
- **A fixed phrase list rather than a router model.** Instant and free for the few things it covers, and nothing outside the Claude subscription. Cost: it only catches exact phrases; everything else still takes a Sonnet turn.
- **Sonnet front door rather than Opus on every utterance.** Seconds faster on small tasks and far lighter on limits. Cost: Sonnet may occasionally keep a task it should have escalated.
- **Local speech rather than Claude Code's built-in dictation.** Private, works with a wake word, and can speak back. Cost: models to download and tune.
- **Raw notes written by code rather than by the model.** Guarantees the memory rule. Cost: raw notes are plain logs; the readable knowledge depends on the scribe pass.
- **CLI process rather than the Agent SDK packages.** The CLI is documented to use the subscription login; the SDK packages are documented around API keys.

## 10. Risks, and the spikes that settle them first

1. **Subscription login in non-interactive mode.** Works today without `--bare`, but the docs say bare mode "will become the default for `-p` in a future release", which would require an API key. Spike: confirm the long-lived stream-json process, subagents, hooks, and the permission bridge all work on the subscription. Keep an explicit non-bare setting and have a fallback of driving an interactive session. **Settled 2026-11-14: all pass (Spike 1); the risk of a future default change remains.**
2. **Microphone permission for a background process.** If the login agent cannot get mic access, `jarvisd` is started from a Terminal login item instead. **Settled 2026-11-14: a `launchd` user agent opened the mic without a prompt (Spike 2).**
3. **Wake word on Apple Silicon** and its false-trigger rate in Febriel's room, with speakers playing. **Settled 2026-11-14 by wake by transcription: about 88 % on his voice, 0 false wakes in 29 minutes (Spikes 2–3).**
4. **Voice quality and latency.** Target: first spoken word within about 2.5 s of Febriel finishing a small request. **Measured 2026-11-14: 1.95 s on the sum of the parts; about 2.2–2.8 s once the first sentence has to finish arriving (Spike 4). Borderline; see §11.**
5. **agent-desktop:** `drag` exists but its syntax is undocumented; behaviour with the display asleep is unknown. **Settled 2026-11-14: drag works with slow timing (`--duration 1000 --drop-delay 1000`); nothing works while the Mac is locked (Spike 5).**
6. **Phone round trip:** Shortcut → Tailscale → Mac → spoken answer, including the confirm loop, on mobile data. **Settled 2026-11-14: under 4 s, loop hands-free (Spike 6).**
7. **Overnight keep-awake** on power and on battery, with Wi-Fi staying connected. **Open: the first night was inconclusive (other apps held the Mac awake); a clean night and a 2-hour battery run are still to do (Spike 7).**
8. **Unlocked and remote** is a real exposure. The gate in §6.5 is the main protection; a spoken command from a video or another person in the room is caught only for risky actions.

## 11. Performance targets

- Wake: the wake and the request arrive together about 1 s after Febriel stops speaking (0.8 s silence + about 0.2 s transcription). *(amended 2026-11-14; replaces "wake word to LISTENING under 0.3 s", which assumed a wake-word model)*
- End of speech to first spoken word, small task: about 2.5 s. Measured: 1.95 s on the sum of the parts, about 2.2–2.8 s with the first-sentence wait. Plan 3 has the `jarvis` agent open with a very short first sentence and measures the real end-to-end time. *(amended 2026-11-14)*
- *(Plan 2, 2026-11-14)* Through `jarvisd`, a small typed request's first token arrived 0.97–1.50 s after it was sent (1.12 s on a fresh process), against 0.79 s in Spike 1. That eats into the margin above; Plan 3 measures the spoken figure.
- Anything expected to take over 5 s gets a short spoken acknowledgement first.
- Idle CPU with the mic open: a few percent of one core. Measured: 2 % in a quiet room, about 4 % with video playing. *(amended 2026-11-14)*
- *(Plan 3, measured on the running daemon)*
  - End of speech to first sound: about 1.37 s for an instant answer, and a median of **2.42 s** to the first word for a small Sonnet request (2026-11-17, ten each). The 2.5 s target is met, and `END_SILENCE_SECONDS` stays 0.8.
  - The spoken acknowledgement above is now jarvisd's holding line at 1.5 s (§6.1). A lookup's first token went from 17 s to 13 s when triage moved from Opus to Sonnet at medium effort.
  - Haiku took 1.4–2.0 s to its first token against Sonnet's 0.75–0.9 s, so the front door stays on Sonnet at low effort (2026-11-22).
  - Idle CPU measured 6.4 % in a quiet room and 5.9 % with a video (2026-11-22). That is a few percent, but above Plan 1's figures; the voice detector is the only active code.

## 12. Privacy

- Mac audio is processed on the Mac and discarded. Request text goes to Anthropic through Claude Code, like any session.
- Phone speech is transcribed by Apple's dictation.
- Speech near the Mac that does not contain the wake name, Febriel's or anyone else's, is transcribed locally and discarded at once (§6.1). *(amended 2026-11-14)*
- Session text is kept in the vault indefinitely unless Febriel deletes it.
- A local log file records timings and errors for debugging; no analytics leave the machine.

## 13. Setup Febriel does personally

- Grant Microphone, Accessibility, and Input Monitoring (for hold-to-talk) permissions when macOS asks. *(2026-11-14: Microphone, Accessibility and Screen Recording were granted to the Claude app during the spikes; `jarvisd` will need its own grants. Input Monitoring is still to do.)*
  *(amended 2026-11-22, Plan 3)* Microphone and Input Monitoring are granted to **Homebrew Python** (`/opt/homebrew/Cellar/python@3.12/…/Python.app`), the interpreter the login agent runs `.venv/bin/jarvis` on. Both show as "Python" in System Settings. A Python upgrade that moves that path will likely need them granted again.
- Create the Tailscale account; install and sign in on Mac and iPhone. *(Done 2026-11-14.)*
- Build the Shortcut from the steps in `shortcuts/` and paste in the token; set up Back Tap. *(Done 2026-11-14.)*
- Allow Claude to control Reminders when macOS asks (for the phone nudge). *(Done 2026-11-14.)*
- Set lock-screen timing in System Settings. *(Kept at "immediately", 2026-11-14; see §6.6.)*
- Open `/Users/febrielotud/Obsidian/Jarvis` in Obsidian once ("Open folder as vault").

Installs the build will do, each named before it runs: Tailscale, agent-desktop, the speech libraries and models, and the humanizer, ponytail, and grill-me skills. *(Tailscale, agent-desktop and the speech stack were installed during Plan 1.)*

## 14. Later, not v1

Interrupting Jarvis mid-sentence by voice, talking to Jarvis from inside Obsidian (a plugin as a second front door), the vault drawn as a star map on the idle HUD, voice-print lock, proactive alerts, "what's on my screen", clipboard and file hand-off with the phone, a HUD page on the phone, routines, and a weekly tidy of `wiki/`.

## 15. Left to the builder

Library versions, the exact agent prompts, the event names, the HTTP routes, test layout, and the order of work after the spikes. Build order should put the spikes in §10 first, since each can change the design.

*(amended 2026-11-14, Plan 2)* The HTTP routes and event names are now fixed. Routes, in `jarvis/remote/api.py`, on `127.0.0.1:8787`, every one behind the bearer token and a `Host` check: `POST /ask` (`{"text", "channel"?}` → `{"say", "loop"?: "yes"}`, Spike 6's contract), `POST /answer`, `POST /cancel`, `POST /hook`, `GET /health`, and the WebSocket `GET /events`. Events, in `jarvis/daemon/core.py`: `snapshot` first, then `state`, `heard`, `reply_delta`, `reply`, `agents`, `queue`, `memory`, `limits` and `health`, plus `level` *(added 2026-11-22, Plan 3: mic level for the waveform)*.

*(amended 2026-11-23, Plan 4)* Added to the API:
- Route `POST /stop` with `{"agent": id}`: stops one agent (the gate first, then a `stop_task` control request).
- The `agents` event and snapshot rows carry `id`, `name`, `call`, `model`, `doing`, `since`, `background`, `title`, `state`, `question`, `ask_id`, `ask_until`, `channel`.
- The `level` event carries `source`: `"mic"` or `"voice"`.
- The face is hidden or shown with Ctrl-Option-J: the snapshot carries `face_hidden`, and a `face` event `{"type": "face", "hidden": bool}` follows each change.
