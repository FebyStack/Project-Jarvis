---
name: Jarvis face (Tether)
description: A red silk circle on the Mac screen, with one Liquid Glass bead per working agent hanging from it on a red thread.
colors:
  red-active: "#FF3B30"
  red-ring: "#C2241B"
  red-deep: "#6B1512"
  red-dot: "#FF6A5F"
  word-grey: "#8F8784"
typography:
  bead:
    fontFamily: "system (SF Pro)"
    fontSize: "13px"
    fontWeight: 400
  bead-name:
    fontFamily: "system (SF Pro)"
    fontSize: "13px"
    fontWeight: 600
  bead-digits:
    fontFamily: "system, rounded design, monospaced digits"
    fontSize: "13px"
    fontWeight: 400
  circle-word:
    fontFamily: "-apple-system, Helvetica Neue, sans-serif"
    fontSize: "11px"
    lineHeight: 1.2
rounded:
  bead: "18px"
  chip: "13px"
  bar: "1px"
spacing:
  circle: "160px"
  bead-open-width: "300px"
  bead-line-height: "36px"
  bead-gap: "10px"
  bead-pad: "12px"
components:
  circle:
    backgroundColor: "transparent"
    size: "160px"
  bead-line:
    height: "36px"
    rounded: "{rounded.bead}"
  bead-open:
    width: "300px"
    rounded: "{rounded.bead}"
  bead-asking:
    width: "300px"
    rounded: "{rounded.bead}"
  button-yes:
    backgroundColor: "{colors.red-active}"
    height: "28px"
  button-stop:
    size: "22px"
  chip:
    rounded: "{rounded.chip}"
    height: "26px"
---

# Design System: Jarvis face (Tether)

This file records the face as built on 2026-11-23. Where the plan and the code differ, the code is described. Product facts are in `PRODUCT.md`; this file is visual only.

## Overview

**Creative North Star: "Lanterns on silk"**

The face is a red circle of silk lines at the edge of the screen, and each working agent hangs from it as a small glass bead on a red thread. Febriel reads state from motion and position first, text second. The circle is the only drawn art. Everything a person reads or clicks is a native macOS control in system type and system colour.

Febriel chose direction Tether on 2026-11-23. The circle is the confirmed one from the 2026-11-17 mockup. Red replaces gold everywhere.

**Key Characteristics:**
- Dense, aggressive circle when working or talking; faint and slow when idle; still when muted or off.
- Beads are system Liquid Glass. No hex colour is used on a bead.
- A question is the only loud thing: red tint, red edge, a pulsing ring on the circle.
- Normal states carry no text on the circle. A word shows only when something is wrong (mode `off`).
- The face never takes keyboard focus and shows on every Space and over full-screen apps.

## Colors

Three reds, one grey, one dot colour. Light and dark mode are handled by the system on beads; the circle is the same in both.

### Primary
- **Active Red** (`#FF3B30`): the circle's lines, its dots' base, the threads, and (as `systemRedColor`) the bead's mark, asking edge, countdown line and Yes button.
- **Ring Red** (`#C2241B`): text and line red; the inner stroke of the question ring on the circle.
- **Deep Red** (`#6B1512`): idle and borders; the outer, wide stroke of the question ring; the glow behind the circle's word.

### Neutral
- **Word Grey** (`#8F8784`): the circle's lines and dots when Jarvis is off (mode `off`), and its one word.
- **Dot Red** (`#FF6A5F`): the 150 node dots of the circle, a lighter step of Active Red.
- Bead text: `labelColor` (name, question, titles) and `secondaryLabelColor` (role, doing, time, countdown). Ended beads are dimmed to 62 % opacity.

### Named Rules
**The System Red Rule.** On a bead, red is `systemRedColor` and text is `labelColor` or `secondaryLabelColor`. Never a hex value. Beads recolour when the appearance changes (light, dark, Increase Contrast).

**The One Loud Thing Rule.** Only a question gets a red tint (about 20 %), a 1.5 pt red edge, a filled Yes, a faster thread and a pulsing ring. Nothing else may be loud.

## Typography

**Bead font:** the system font (SF Pro) at 13 pt.
**Digits:** the system font, rounded design, monospaced digits, 13 pt (timer and countdown).
**Circle word:** `-apple-system`, Helvetica Neue, sans-serif, 11 px, line 1.2, grey `#8F8784`.

**Character:** plain Apple system type, no custom face.

### Hierarchy
- **Name and question** (semibold 600, 13 pt): the agent's name; the question text (up to 4 lines).
- **Body** (regular, 13 pt): role and model, the job title (up to 2 lines, `labelColor`), what it is doing (up to 2 lines, secondary), the line in the one-line state (cut with an ellipsis at 160 pt).
- **Digits** (rounded, monospaced, 13 pt, secondary): elapsed time; the countdown `No in N s`.
- **Word** (11 px): the circle's single word, only in mode `off`, centred, 12 px in from each side, 30 px above the bottom, cut with an ellipsis.

### Named Rules
**The Characters Only Rule.** Agent text is set only as a string on a native label. It is never markup, HTML or attributed text.

## Layout

The circle is a 160 pt square borderless panel, draggable, remembered by the face and nowhere else. Beads are their own small panels, children of the circle's panel, so they follow a drag. One transparent click-through panel under them carries the threads. Clicks beside a bead, in the gap, and in the circle's square corners go to whatever is underneath.

**Plume rule (tether design section 6).** Order from nearest the circle: asking first (oldest question first), then working (newest first), then ended. The first bead sits beside the circle with its lower edge 22 pt below the circle's centre; each next one sits 10 pt (`CARD_GAP`) further along. A bead that overlaps the circle's height keeps outside a ring 88 pt from the centre (`TETHER_CLEAR`). One wholly past the circle starts 28 pt inside the centre line and each further one steps 46 pt outward (`TETHER_STEP`), so each thread drops clear of the beads below it. The plume grows away from the nearest screen edges: circle in the right half puts beads on its left, left half on its right, lower half grows up, upper half grows down. When the beads do not fit with that step, a second column is used (Febriel, 2026-11-23). Beads stay on screen; as a last resort one may overlap another rather than be unreachable. After a drag the plume re-forms and flips if a midline was crossed.

- At most five beads (`CARD_MAX`); the rest are a chip: `+N more working`, the last row, with no thread.
- Bead sizes: one line is 36 pt high (`CARD_LINE_HEIGHT`), as wide as its text, up to 300 pt; open is 300 pt wide (`CARD_OPEN_WIDTH`). Inner padding 12 pt, text indented 38 pt from the circle-side edge (mark 24 pt plus margin), 8 pt between items on a line.
- Mirrored: the mark sits on the side nearest the circle and text runs away from it. Circle on the right half: text right-aligned.
- Open when: it asks; the pointer is over it; or its agent started less than 4 s ago (`CARD_POP_SECONDS`). A bead with a question never shrinks. Ended beads linger 8 s (`CARD_LINGER_SECONDS`).
- Mac only, one display, one user. No mobile layout.

## Elevation & Depth

Depth is the glass. Each bead is `NSGlassEffectView` with a soft system shadow; the circle and threads are flat, drawn light on transparent. The threads sit in a panel below the beads. When Reduce Transparency is on, the system turns the glass solid and it stays readable (checked live with Febriel, 2026-11-23, light and dark).

### Named Rules
**The Native Glass Rule.** Beads use the system glass and its shadow. No custom blur, no drawn hover light (dropped 2026-11-23: the glass offers none and a drawn one would run Python on every pointer move).

## Shapes

- Bead: 18 pt corner radius. Chip: 13 pt.
- Asking bead: 1.5 pt red edge following the 18 pt corner.
- Mark: 24 pt, three 1 pt closed red rose curves. Petals 3 to 7, depth 0.30 to 0.50, offsets and turn direction all from a CRC32 of the name, so Nova always looks the same. Drawn at radius 10.5 pt in the 24 pt box.
- Countdown line: 2 pt high, 1 pt corners, red, shortens toward the circle.
- Thread: round caps, quadratic curve from the circle's rim to the bead's mark.
- Circle: 150 nodes in a disc of radius 250 (of 640 units), joined by curves where nodes are close; four wavy rings at 1.06, 0.82, 0.55 and 1.16 of the radius, 2.4 line width; node radius 3 to 5.

## Components

### The circle
Canvas in a web view. States by mode, with energy `E` and frame rate:

| Mode | Energy | Frame rate |
|---|---|---|
| idle | 0.12 | 10 fps, by timer |
| listen | 0.45 | 30 fps |
| work | 1.0 | 30 fps |
| talk | 0.85 | 30 fps, size follows voice level (up to 7 %) |
| muted | 0 | one still frame, dim |
| off | 0 | one still frame, grey, with a word |

Energy eases in over about two seconds on every state change (`FACE_EASE_SECONDS` 2.0). Question ring: a wide `#6B1512` stroke and a thin `#C2241B` stroke pulsing around the circle, on a clock of its own, so it pulses on a still circle too (this is the only animation under mute). Line width 2, drawn in 12 opacity steps, one stroke per step.

### Bead
Four states, all native: one line (mark, name, doing, time); open (mark, name, role and model, time, Stop, job title, doing); asking (open plus red tint, red edge, question, buttons, countdown); ended (one line, dimmed 62 %, mark becomes a grey `checkmark.circle` for done or `stop.circle` for stopped and failed, title, the state word). Every control acts on the first click without making the app active.

### Buttons
- **Yes:** filled system red, large push bezel, 28 pt high.
- **No, Always:** plain glass push buttons, 28 pt high, 6 pt apart; order mirrors with the plume.
- **Stop:** 22 pt round button with `stop.fill`, shown while the agent is live.
- **Focus:** none drawn; the panel is never key. Each has a VoiceOver label: `Stop Nova`, `Yes to Nova`.

### Mark
24 pt, three rose curves. Working: they turn at 6, 9 and 12 s per turn. Asking: 18, 21 and 24 s per turn, and the mark breathes (scale 1 to 1.12 over 1.2 s, eased, reversing).

### Countdown
A question on the Mac counts as no after 60 s; the line and `No in N s` run down over that wait (1 s steps, linear). A phone question shows the same over 10 minutes. `jarvisd` sends the end; the face does not guess.

### Thread
Red `#FF3B30`, round cap.

| Agent is | Width | Opacity | Dots |
|---|---|---|---|
| Working | 1 pt | 0.6 | 1, a full run about every 2.5 s |
| Asking | 1.8 pt | 1.0 | 2, twice as fast |
| Done | 1 pt | 0.2 | none |
| Stopped, failed | cut | cut | none |

Sway: the curve moves 4 pt either side over 3.2 s plus 0.4 s per bead, eased and reversing. Dots are 4 pt round. A cut thread retracts into the circle in 0.25 s and the bead stays, dimmed, tied to nothing.

### Chip
`+N more working`, secondary text, glass, 13 pt corners, 26 pt high.

### Hide and show
Ctrl-Option-J hides and shows the whole face (circle, beads, threads); the page is paused while hidden. A question that opens while hidden brings it back. `jarvisd` owns the state.

## Motion

- **Group move:** 0.45 s (`FACE_MOVE_SECONDS`), curve `cubic-bezier(0.25, 1.25, 0.4, 1)` with a slight overshoot. One animation group moves the bead window, its thread and its mark together. Checked live (P8, Febriel, 2026-11-23).
- **Bud:** a new bead starts at the circle's centre and travels to its place; a thread draws out with the same curve. It leaves the same way.
- **Open, shrink, re-order:** the same 0.45 s curve.
- **No Python per frame** for beads or threads: AppKit animates windows, Core Animation animates layers. Only the circle's canvas runs script.
- **Pause:** motion stops while the display sleeps, the Mac is locked, or the face is hidden. The app holds a user-initiated activity so App Nap does not freeze it.
- **Reduce Motion** (system setting, follows changes): the circle draws one still frame per change; beads appear and move without the threads' draw, sway or dots; marks hold still; the breathing stops.

## Accessibility

- Honours Reduce Motion, Reduce Transparency (system glass goes solid) and Increase Contrast (threads go fully opaque; system colours adapt).
- Native controls are reachable by VoiceOver; Stop and the answers carry labels naming the agent. Ended marks carry the state as their description.
- State is not carried by colour alone: asking also changes shape (open, question text, buttons), motion (breathing mark, faster dots) and edge weight; stopped is a cut thread plus a square.
- Never takes keyboard focus. The one chord, Ctrl-Option-J, is a global hide and show.
- The face is a glance surface; it is not the only way to answer (voice and the terminal HUD stay).

## Do's and Don'ts

### Do:
- **Do** use `systemRedColor`, `labelColor` and `secondaryLabelColor` on beads.
- **Do** keep one bead per agent, with each name's own mark.
- **Do** move group changes in 0.45 s on the (0.25, 1.25, 0.4, 1) curve.
- **Do** keep the circle's frame rates: 30 fps listen, work, talk; 10 fps idle by timer; one still frame when muted or off.
- **Do** set agent text as plain strings.
- **Do** test beads in light, dark, Reduce Transparency and Increase Contrast.

### Don't:
- **Don't** put gold anywhere; red replaces it.
- **Don't** put a hex colour on a bead, or draw a hover light on it.
- **Don't** put text on the circle in a normal state.
- **Don't** let a bead with a question shrink.
- **Don't** stack beads in a corner; they hang from the circle wherever it sits.
- **Don't** use a film character's name or a stock raster image; neither is part of this look.

## Performance (as measured)

Measured on the built face, 2026-11-23: idle 7.2 to 7.6 % of one core; working and talking with five beads 22 to 23 %; memory 159 to 177 MB. Febriel kept 30 fps and set the budgets to working and talking at most 25 %, idle at most 8 %, memory at most 200 MB. These replace the lower figures in `PRODUCT.md`.

## Provenance

- **Chosen by Febriel on 2026-11-23:** direction Tether, from `docs/superpowers/specs/assets/2026-11-23-jarvis-face-directions.html`. The circle comes from `docs/superpowers/specs/assets/2026-11-17-jarvis-face-mockup.html` (confirmed 2026-11-17).
- **Specs:** `docs/superpowers/specs/2026-11-17-jarvis-screen-hud-design.md`, amended by `docs/superpowers/specs/2026-11-23-jarvis-face-tether-design.md`. Product record: `PRODUCT.md` (direction seed `7ad2e9bf`).
- **Built code:** `jarvis/face/page/` (circle), `jarvis/face/beads.py`, `threads.py`, `tether.py`, `mark.py`, `app.py`, and `jarvis/config.py` for the numbers.
- **Verified live with Febriel, 2026-11-23:** `docs/spikes/findings.md`, "Plan 4 probes": glass right in light, dark and Reduce Transparency (P3); click-through, first-click, every Space and full-screen (P2); the 0.45 s group move (P8); budgets.
- **Images:** the face ships no raster images. The circle is drawn on a canvas, the marks and threads are vector layers, and the other glyphs are SF Symbols.
- **Hover:** a drawn hover light was dropped in the Plan 4 fix wave (2026-11-23).
