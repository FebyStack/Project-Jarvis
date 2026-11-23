# Jarvis on screen: Tether — design amendment

Date: 2026-11-23 · Owner: Febriel · Status: direction chosen by Febriel 2026-11-23 ("Tether", from the live mockup); the details below marked **(Claude's call)** are not yet read by him.

Amends `2026-11-17-jarvis-screen-hud-design.md` (the on-screen design). Where the two disagree, this one wins. Everything it does not mention stands: the circle and its states, names, questions, stop, what `jarvisd` gains, the terminal HUD, the order of work.

The look and the motion: `docs/superpowers/specs/assets/2026-11-23-jarvis-face-directions.html`, direction **Tether** (also published at https://claude.ai/artifact/UWndyYPhURoc24tkGoxQMw). It is a browser mockup; the real beads are native, so glass and motion will differ a little.

## 1. What changed, and who said so

| On-screen design said | Now | Source |
|---|---|---|
| Cards stack in the top-right corner (§1, §7.3) | Agents hang around the circle, wherever it sits | Febriel picked Tether knowing this was its risk |
| A card is always full size (§7.3) | It pops open for 4 s, shrinks to one line, opens on hover or when it asks; a question never shrinks | Febriel, 2026-11-23 |
| Cards are HTML in a web view (§6 approach A) | Cards are native AppKit views through PyObjC; only the circle stays a canvas in a web view | Febriel, 2026-11-23 |
| Red on near-black, three reds (§7.9) | The three reds stay for the circle, the threads and the terminal HUD. Beads are system Liquid Glass with system colours; red only on the mark, on a question and on Yes | Febriel, 2026-11-23 |
| Two windows: circle and stack (§7.1) | The circle, one click-through layer for the threads, one small panel per bead | Claude's call |
| The stack's place against macOS banners (§10) | Gone; nothing sits in the banner corner unless he drags the circle there | follows |

## 2. Intent

Agents are tied to Jarvis. Each one buds out of the circle on a silk thread and hangs beside it as a glass bead. He reads who is working from the threads before he reads a word. Stop cuts the thread.

It comes from two places: visionOS ornaments, which hang off their parent in glass, and the Obsidian graph the circle already is. The category default it refuses is the notification banner in the corner.

## 3. Direction contract

- **THESIS.** An agent is a node on Jarvis's graph. Its tie to Jarvis is drawn, and the tie carries its state. No banner stack.
- **OWN-WORLD.** Liquid Glass capsules, 18-point corners, hanging from a dense red silk circle by hairline red threads. One text size. Red on glass only where something asks or can be pressed.
- **STORY.** He glances: threads pulsing means work is going on; one thread burning bright means someone needs him; he clicks Yes or says it; the thread calms.
- **FIRST VIEW.** The circle, 160 points, bottom-right by default. Beads rise from it in a plume, the nearest one beside it, the rest stepping up and outward. The asking bead is nearest, open, tinted red, with Yes filled red.
- **FORM.** Seventh of seven grounded candidates (visionOS ornaments); seed `7ad2e9bf`. Signature interaction: the thread. Motion grammar: beads bud out of the circle and sink back into it; nothing slides in from a screen edge.
- **FINISH.** Unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

Raised by what it was weighed against **(Claude's calls)**:

- *One size, rank by weight* (from a timetable set at one type size): every label on a bead is 13 points. Name and question are semibold, the rest regular.
- *State in a fixed cell* (same source): the mark always sits at the bead's end nearest the circle and always shows state.
- *A character per agent* (from a character catalogue): each name has its own mark.
- *Colour only where it acts* (from a consumer app canon): red on glass is the mark, a question, Yes.
- *Readable with the words removed* (from a data field): thread motion alone tells working, asking, ended.

## 4. The bead

One per working agent, by the rules of §7.3 of the on-screen design (workers only; a `Jarvis` bead only while Jarvis itself asks; five at most, the rest counted).

| State | Shows |
|---|---|
| One line | mark · name · what it is doing (cut with an ellipsis at 160 points) · elapsed time |
| Open | mark · name · role and model · elapsed time · Stop; under them the job's title and what it is doing |
| Asking | open, tinted red with a red edge; adds the question, Yes / No / Always, and the countdown |
| Ended | one line, dimmed: mark turns into a grey tick (`done`) or square (`stopped`, `failed`), the job's title, the word |

- **Open when:** it asks; or the pointer is over it; or its agent started less than 4 seconds ago.
- **Size:** one line is 36 points high and as wide as its text, up to 300. Open is 300 wide.
- **Mirrored:** the mark sits on the side nearest the circle, the text runs away from it. With the circle on the right half of the screen that means right-aligned text, as in the mockup; on the left half everything flips.
- **Material:** system Liquid Glass (`NSGlassEffectView`), 18-point corners, following light and dark mode by itself. Asking: the glass's tint is system red at about 20 %, plus a 1.5-point red edge.
- **Type:** the system font at 13 points. The timer and the countdown use the rounded design with fixed-width digits.
- **Text colours:** `labelColor` and `secondaryLabelColor`. Never a hex value on a bead.
- **Buttons:** Yes is filled system red; No and Always are plain glass capsules, 28 points high. Stop is a 22-point round button with a square. Every one acts on the first click without making the app active.
- **Hover (Claude's call):** the pointer opens a bead; there is no hover light. Dropped on 2026-11-23 in the Plan 4 fix wave: AppKit's glass offers none, and a drawn one would run Python on every pointer move.

### The mark

Each name has its own mark: three thin red closed curves (rose curves) whose petal count, depth and offsets come from the name, so `Nova` always looks the same. Working: the three turn at different speeds. Asking: they turn slowly and the mark breathes. Ended: a grey ring with a tick or a square. It is 24 points.

The curves are worked out in Python from the name (pure, tested); the turning is a layer animation, not Python per frame.

### The countdown

A question on the Mac counts as no after 60 seconds (unchanged). The bead shows it: a 2-point red line that shortens toward the circle, and `No in 42 s` beside it. A question from phone work keeps its 10-minute wait and shows the same line over 10 minutes. `jarvisd` sends when the wait ends; the face does not guess.

## 5. The thread

A hairline red curve from the bead's mark to the circle's rim (68 points from the centre at 160), in the circle's own red (`#FF3B30`).

| Agent is | Thread |
|---|---|
| Working | 1 point, 60 % opaque, swaying slowly; one bright dot travels from the bead to the circle about every 2.5 s |
| Asking | 1.8 points, fully opaque; two dots, twice as fast |
| Done | fades to 20 %, no dot, for the 8 seconds the bead lingers |
| Stopped or failed | **cut**: it retracts into the circle in a quarter of a second. The bead stays 8 seconds, dimmed, tied to nothing |

Stopped differs from the mockup, which keeps a faint thread **(Claude's call)**: from the click on, that agent does nothing more (§7.6), and a cut thread says so.

Threads sit in their own layer that ignores the mouse entirely.

## 6. The plume: where beads sit

Pure arithmetic, no window involved, so it is unit-tested.

- Order is the on-screen design's: asking first (oldest question first), then working (newest first), then ended. **First means nearest the circle.**
- The first bead sits beside the circle, its lower edge 22 points below the circle's centre. Each next one sits 10 points further along.
- A bead whose height overlaps the circle keeps clear of a ring 88 points from the centre. One wholly past the circle starts 28 points inside the circle's centre line and each further one steps 46 points outward, so every thread drops clear of the beads below it.
- **The plume grows away from the nearest screen edges.** Circle in the right half: beads to its left. In the left half: to its right. In the lower half: upward. In the upper half: downward. Beads never leave the screen.
- The `+2 more working` chip is the last row of the plume and has no thread.
- He drags the circle and everything follows; on release the plume re-forms, flipping if he crossed a midline.

## 7. Motion

- A bead **buds**: it starts at the circle's centre, invisible, and travels to its place in 0.45 s with a slight overshoot. It leaves the same way, back into the circle.
- Opening, shrinking and re-ordering use the same 0.45 s curve; the thread follows the bead.
- No Python runs per frame: windows move with AppKit's own animation, threads and marks with layer animations. A timer-driven spring is the fallback if the probe finds that jerky.
- **Reduce Motion:** beads appear and move with a cross-fade, threads do not sway, no dots travel, marks hold still. **Reduce Transparency** and **Increase Contrast:** the system glass and system colours handle them; the threads go fully opaque.
- Motion stops while the display sleeps or the Mac is locked (unchanged).

## 8. How it is built

`jarvis face` stays one process, a client of `jarvisd` (unchanged). What it shows:

| Piece | What it is |
|---|---|
| The circle | A 160-point borderless panel holding a web view that draws the canvas. Unchanged from the on-screen design, minus the cards page. |
| The threads | One transparent panel covering the circle and the plume. It ignores the mouse. One shape layer per thread. |
| A bead | Its own small non-activating panel, exactly the bead's size, holding the glass view and native labels and buttons. A child of the circle's panel, so it follows a drag. |

One panel per bead **(Claude's call)** because it makes click-through true by construction: there is no transparent area over his work that could swallow a click. A single big panel that toggles mouse handling is the alternative the probe may prefer.

**An agent's text can no longer run as code on a bead.** A native label shows characters; there is no markup to interpret. The plan still pins it: bead code never builds text from HTML or attributed strings.

The circle's page loses two of its three messages. It can send only "the circle was dragged to here". Answers, stops and hover come from native buttons, straight to the controller, with the same checks as before: a click for an agent or question that is no longer on a bead does nothing.

Still true: never the key window, no Dock icon, every Space and over full-screen apps, the face's death never stops a question being asked by voice.

## 9. States worth naming

| Situation | The face |
|---|---|
| No agents | The circle alone. No empty plume, no label. |
| First run | Nothing to teach: the circle appears; the first job buds a bead. |
| `jarvisd` gone, offline, limit | Every bead and thread vanishes at once; the circle goes grey with its word (unchanged). |
| A sixth agent | Counted on the chip; a bead with a question is never the hidden one (unchanged). |
| Very long text | One line: cut with an ellipsis. Open: wraps inside 300 points, the question up to 4 lines. |
| Circle dragged to a corner | The plume flips so every bead stays on screen. |

## 10. What `jarvisd` gains beyond the on-screen design

One field: each agent row carries `ask_until`, the time its open question becomes a no (`None` when it has none). The countdown is drawn from it.

## 11. Performance

The budgets of §8 stand. Expect it lighter than planned, since one web view is gone. The probe measures the real thing: the circle, five glass beads, five animated threads.

## 12. Setup Febriel does

Nothing. One install is named before it runs: `pyobjc-framework-WebKit`. `pyobjc-framework-Cocoa` is already installed (it came with Quartz in Plan 3) and becomes a declared dependency. Checked on this Mac on 2026-11-23: `NSGlassEffectView` is reachable from PyObjC 13.0 on macOS 26.4.1.

## 13. Left to the builder

The probes of Plan 4 Task 1. Exact spring curve. The alert sound (unchanged). Tests.

## 14. Not decided

- Whether a single big panel replaces one panel per bead (the probe says).
- Whether the system glass looks right in a panel that is never key; the fallback is `NSVisualEffectView`.
