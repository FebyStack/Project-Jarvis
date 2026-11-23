# Jarvis on screen — design

Date: 2026-11-17 · Owner: Febriel · Status: approved by Febriel 2026-11-17, as written (so the calls marked Claude's are accepted).

Extends `2026-11-10-jarvis-design.md` (the main design) and replaces parts of its §7. Where the two disagree, this one wins once approved. Anything marked **(Claude's call)** was not said by Febriel.

## 1. Intent

Jarvis gets a presence on the desktop instead of living in a terminal window.

- **Jarvis** is a red circle of fine, silk-like lines, like the graph ("brain") in Obsidian. Nothing else: no panels, no text.
- **Agents** are small cards that pop up in the top-right corner of the screen, one per working agent, at most five stacked. A card shows what its agent is doing, and Febriel can answer its question or stop it there. Each agent has a randomly chosen name.
- When an agent has a question, Jarvis tells him and notifies him.

Why, as Claude reads it (Febriel has not said): he wants to see and steer the agents at a glance, in whatever app he is in, without opening a terminal. **(Claude's reading)**

## 2. Goals

1. A floating red circle that shows Jarvis's state by how it moves.
2. A card per working agent in the top-right corner, up to five, with its name, its job, what it is doing now and for how long.
3. Answer an agent's yes/no question from its card. Stop one agent from its card.
4. A random name per agent, used everywhere that agent is mentioned, and usable by voice: "Jarvis, stop Nova", "yes to Nova". (Febriel's choice, 2026-11-17.)
5. A question is announced: Jarvis says it, the card stands out, the circle pulses.
6. The terminal HUD stays as an optional detail and typing view, in red.

## 3. Non-goals

- Typing to Jarvis on the circle or on a card. Open questions ("which repo?") are answered by voice or in the terminal HUD. (Febriel's choice.)
- Cards for `triage` and `scribe`. Workers only. (Febriel's choice.)
- Clicking the circle to do something. It can be dragged, nothing more. **(Claude's call)**
- A card's history, logs, or a click-through to the agent's full output. The task note in the vault has that.
- More than one screen: everything shows on the main display. **(Claude's call)**
- A phone version of the cards.

## 4. Anti-goals

- A card or the circle takes keyboard focus away from the app Febriel is typing in.
- Text an agent produced is treated as markup or code by the window that shows it.
- The window's page can reach the network or see the API token.
- The face crashing or hanging takes `jarvisd` down, or stops a question from being asked by voice.
- Stop on one card silently stops other agents too.

## 5. Constraints

- macOS 26.4, one Mac, one user. Python 3.12, same package and repo.
- The face is a client of `jarvisd`'s local API, like the terminal HUD. It holds no state of its own beyond where the circle sits.
- Subscription login only; the face calls no model.
- The gate stays the only thing that approves actions: a card's Yes / No / Always goes through the same `/answer` route as the terminal HUD's `y` / `n` / `a`.

## 6. Approaches

| | Approach | Trade-off |
|---|---|---|
| **A (picked)** | A small Mac app in Python (PyObjC): borderless, always-on-top windows whose content is a local page drawn in a web view. The circle is a canvas animation; the cards are plain HTML. | Stays in Python and in this package. The silk-line animation is easy to make look right and to tune. Costs a web-view process (roughly 100–200 MB) and two new PyObjC packages. |
| B | The same app, but everything drawn natively from Python (Core Graphics / Core Animation), no web view. | Lighter, but animating hundreds of curved lines from Python is slow to write and likely to stutter. |
| C | A separate Swift app. | Best performance and the most native feel, but a second language, Xcode builds and code signing in a project that is Python throughout. |
| D | Draw the circle in the terminal with text characters. | Cheapest, but cannot look like Obsidian's graph, and cannot float over other apps. Febriel turned it down. |

A is picked **(Claude's call; Febriel handed over the how)**. This is not the web dashboard the main design rejected: there is no browser, no server page and no URL; the web view is only the paint surface for two floating windows.

## 7. How it works

### 7.1 The process

A new command, `jarvis face`, started at login by its own agent (`com.febriel.jarvis-face`). It is separate from `jarvisd` because a Mac app needs the main thread, which `jarvisd` gives to its event loop, and because a crash in drawing must not stop Jarvis. It connects to `jarvisd`'s event stream with the token from `~/.jarvis/token`, reconnects when `jarvisd` restarts, and posts answers and stops back.

The page inside the windows never talks to the network and never sees the token. The Python side receives the events and pushes plain values into the page; the page can send back exactly three messages: an answer (`yes`, `no`, `always` with the question's id), a stop (with the agent's id), and "the circle was dragged to here". Every string from `jarvisd` is inserted as text.

Both windows float above other apps, on every Space and over full-screen apps, and never become the key window. Clicks outside a card or the circle pass through to whatever is underneath.

### 7.2 The circle

About 160 points across **(Claude's call)**, starts at the bottom-right, can be dragged anywhere, and remembers its place in `~/.jarvis/face.json`.

It is dense and busy, not a tidy graph (Febriel, 2026-11-17: "more complicated circle with too many line graphs that moves aggressively when walking and talking"; "walking" read as "working"). On the order of 150 points joined by several hundred fine curved lines, with several rings of jagged, waveform-like lines around and through it. The second mockup of 2026-11-17 (the one with Idle / Listening / Working / Talking buttons) is the reference; Febriel confirmed it the same day ("Yes, that's it").

| Jarvis is | The circle |
|---|---|
| Idle | Everything drifts slowly, dim red. |
| Listening | Lines swell and tighten with the mic level. |
| Working (thinking, or any agent running) | Aggressive: lines whip and jitter, the rings spin fast and spike. |
| Talking | Aggressive: the whole circle and its rings throb and spike with the loudness of Jarvis's own voice. |
| Waiting on Febriel (a question is open) | A bright ring pulses around it. |
| Muted | Still and dim. |
| Offline, limit reached, or `jarvisd` not running | Grey, with one word under it (`OFFLINE`, `LIMIT`, `NO DAEMON`). |

**Every change of state eases in over about two seconds; nothing jumps** (Febriel, 2026-11-17: the second mockup lurched at the moment it began listening, working or talking; "it should move just smoothly"). The motion is as wild as before once it gets there; it is the start that is gentle. The mockup file was corrected the same day: speeds bend by advancing each motion's phase a little per frame, and loudness fades in. Febriel confirmed the corrected motion on 2026-11-17 ("Yes, smooth now").

Normal states carry no text, as he asked. A word appears only when something is wrong, because grey alone does not say what. **(Claude's call)** The main design's rule that every state is shown as a word still holds in the terminal HUD.

Motion stops while the display is asleep or the Mac is locked.

### 7.3 The cards

One card per working agent: `coder`, `researcher`, and later `operator`, `reverser` and spawned sessions. Not `triage`, not `scribe`.

A card shows: the agent's name; its role and model; the job's title (from triage's verdict); one line of what it is doing now; how long it has run; a Stop button. When it has a question the card also shows the question and Yes / No / Always, gets a bright border and moves to the top.

When Jarvis itself needs a yes for something small (no worker involved), a card named `Jarvis` appears with the question and the same buttons, so there is always something to click. **(Claude's call)**

Life of a card: it slides in when the agent starts; when the agent finishes it shows `done` (or `stopped`, `failed`) for 8 seconds and fades. **(Claude's call)**

The stack holds five. Order: cards with a question first, then working agents newest first, then finished ones. Anything beyond five is counted on one line under the stack (`+2 more working`, `+1 more needs you`). A card with a question is never pushed out by one without.

### 7.4 Names

Each worker gets a name when it starts, picked at random from a list of about sixty short names kept in the code **(Claude's call: a fixed list, no film characters)**, never one that a running agent already has. The name stays for that agent's life and is used on its card, in the terminal HUD's AGENTS panel, in the task note in the vault, and when Jarvis speaks about it ("Nova has finished").

**The name is chosen by `jarvisd`, and Jarvis's brain is told it** (Febriel, 2026-11-17: names work by voice too). `jarvisd` picks the name when the front door dispatches the worker, before the worker starts, and hands it to the front door so its own replies say "Nova", not "the coder". How it is handed over (in the dispatch itself, or as a `[jarvisd]` notice) is for the plan's first task to probe. If the model cannot be told reliably, the fallback is that `jarvisd` adds the name to what is spoken and shown, and the model's own sentence stays nameless.

**By voice or typed, answered by code with no model**, like the other instant phrases, and matched only against the agents running now:

| Said | Jarvis does |
|---|---|
| "stop Nova" | Stops that agent, as its Stop button does. |
| "yes to Nova", "no to Nova", "yes always to Nova" | Answers that agent's open question. |

This also closes a gap in the main design: with two questions open, a bare "yes" is refused because Jarvis will not guess; now Jarvis says who is asking ("Nova and Orin each have a question") and he answers by name. A bare "yes" still works when one question is open. The name is matched loosely, since speech-to-text may mis-hear it, but only among the running agents' names, and the name list avoids names that sound alike. A name that matches no running agent is not an instant phrase; the sentence goes to the front door as an ordinary request.

### 7.5 Questions

When an agent's question opens: Jarvis says "Nova has a question", then the question (voice, from the voice plan); the card moves to the top with its border lit; the circle pulses; a short alert sound plays. **(The sound is Claude's call.)** The phone nudge arrives with the phone plan.

Answering on the card, by voice, or in the terminal HUD are equivalent; whichever comes first wins and the others clear. No answer in 60 seconds is still a no.

Work started from the phone **(Claude's call)**: its agents get cards like any other, and a question's card has its buttons, since he may be at the Mac. But the question is not spoken and makes no sound on the Mac, and it keeps the phone's 10-minute wait: the main design sends a question to the channel the request came from.

Only questions that need a yes (the gate's) light the card, the ring and the sound. When Jarvis asks an open question in its reply ("Which repo?"), that is just a reply: it is spoken, the follow-up window opens, and nothing else changes. **(Claude's call)**

### 7.6 Stop

Stop on a card stops that one agent. Its request is recorded as stopped by Febriel, the card shows `stopped`, and Jarvis says nothing (he clicked it; he knows). Stop on the `Jarvis` question card answers no.

Today "never mind" stops every running worker by restarting the `claude` process. Whether one background worker can be stopped alone is not yet known; the plan's first task probes it.

What counts as stopped **(Claude's call)**: from the click on, that agent does nothing more. So `jarvisd` first refuses every further tool call from that agent at the gate, at once and by code, and then ends it: a real kill of that one worker if the probe finds one, otherwise a `[jarvisd]` notice telling the front door to end it. The card says `stopped` as soon as the gate is shut. A stopped agent's result, if one still arrives, is not announced.

If the probe shows the gate cannot tell one worker's calls from another's, one-click Stop is not safe: Stop then says so on the card ("This stops all 3 running agents") and needs a second click. It never stops the others silently.

### 7.7 What `jarvisd` gains

- Each agent row carries the name, the job title, a state (`working`, `needs_you`, `done`, `stopped`, `failed`) and, while one is open, the question and its id. A question records which agent asked it (the hook already says).
- `POST /stop` with an agent id, behind the token like every route.
- The name phrases of §7.4 among the instant answers.
- The mic-level and voice-state events the voice plan adds are what moves the circle. One more is needed: the loudness of Jarvis's own speech while it talks, sent the same way as the mic level.

### 7.8 The terminal HUD

Kept, optional, opened with `jarvis hud`. Its gold becomes red, and its AGENTS panel shows the names. Nothing else about it changes here.

### 7.9 Colour

Red on near-black, three values: `#FF3B30` for what is active, `#C2241B` for text and lines, `#6B1512` for idle and borders **(exact values are Claude's call)**. Gold is retired everywhere.

The reference for the look, circle and cards, is `docs/superpowers/specs/assets/2026-11-17-jarvis-face-mockup.html` (open it in a browser). The circle in it is the one Febriel confirmed; the cards are Claude's sketch and he has not commented on them.

## 8. Performance

- The face uses a few percent of one core while idle, no more than about 15 % while working or talking, and under 200 MB of memory.
- A card appears within half a second of its agent starting.
- The circle animates at about 30 frames a second without stutter while agents work.

These figures count everything the face starts, the web view's helper processes included. The plan's first task measures them on a throwaway build before anything else is built. If they are missed **(Claude's call)**: first the idle circle slows to about 10 frames a second; then the memory limit loosens to 300 MB; approach A is dropped for B only if working or talking still costs more than a quarter of one core.

## 9. Order of work

After voice (Febriel's choice), so the circle reacts to listening and speaking from the start and questions are spoken.

| Plan | Delivers |
|---|---|
| 3 | Voice (written 2026-11-16) |
| **4** | **Jarvis on screen: the circle, the cards, names, stop, the red terminal HUD** |
| 5 | Phone route, Reminder nudge, keep-awake, battery rule |
| 6 | On-screen control, reverse engineering, spawned sessions |

## 10. Left to the builder

The plan is written against the voice plan's interfaces as they stand (`level`, `state`, the speaker), since voice is built first. The window and web-view details; the animation's maths; the name list; the alert sound; the card's exact layout and sizes; where the stack sits relative to macOS's own notification banners (both use the top-right corner); the event and field names; the probe for stopping one worker; tests.

## 11. Setup Febriel does

Nothing new is expected: a floating window needs no permission. Two installs are named before they run: `pyobjc-framework-Cocoa` and `pyobjc-framework-WebKit`.
