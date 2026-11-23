# Product

<!-- impeccable:product-schema 1 -->

## Platform

ios

(Nearest of impeccable's four values. The real target is macOS 26 on one Mac: AppKit through PyObjC, Apple HIG applies, there is no iOS build and no Simulator.)

## Users

Febriel, alone, at his M4 Mac. He is mid-task in another app (editing, coding, clinic content) and talks to Jarvis by voice. He looks at Jarvis in glances, from the corner of the screen, and must never lose keyboard focus to it.

## Product Purpose

Jarvis is a personal, local-only voice agent with Claude Code as its brain. It hands real work to named worker agents. The on-screen face exists so he can see who is working, answer an agent's yes/no question, and stop one agent, in whatever app he is in, without opening a terminal.

## Positioning

The agents are his own, named, and steerable by voice or click ("stop Nova", "yes to Nova"). Jarvis's presence is a red circle of silk lines modelled on the Obsidian graph that is also its memory.

## Operating Context

- One Mac, one user, lid open. Voice first; a terminal HUD (`jarvis hud`) stays for detail and typing.
- `jarvisd` is the only source of state; the face is a client of its local API and holds nothing but where the circle sits.
- The gate is the only thing that approves actions; a card's Yes / No / Always goes through the same `/answer` route as the terminal.
- No answer in 60 seconds is a no.

## Capabilities and Constraints

- Two surfaces only: the circle (Jarvis) and one bead ("card" in code) per working agent, at most five shown, the rest counted.
- Cards for workers only (not `triage`, not `scribe`); a `Jarvis` card only while Jarvis itself asks.
- Card content: name, role and model, job title, one line of what it is doing, elapsed time, Stop; with a question: the question and Yes / No / Always.
- Card life (Febriel, 2026-11-23): pops in full, shrinks to one compact line, expands on hover or when it asks; a card with a question never shrinks.
- Cards are native AppKit views with system Liquid Glass (Febriel, 2026-11-23); the circle stays a canvas.
- Never takes keyboard focus; clicks beside a card pass through; shows on every Space and over full-screen apps.
- Agent text is never markup or code.
- Budgets: idle at most 5 % of one core, working or talking at most 15 %, at most 200 MB, a card within 0.5 s of its agent starting.
- Subscription login only; the face calls no model.
- Direction: **Tether** (Febriel, 2026-11-23). Each agent is a glass bead hanging from the circle on a red silk thread, wherever the circle sits; not a stack in the top-right corner. Design: `docs/superpowers/specs/2026-11-23-jarvis-face-tether-design.md`.

## Brand Commitments

- The red silk circle, dense and aggressive while working and talking, confirmed from the mockup on 2026-11-17. Every change of state eases in over about two seconds.
- Red replaces gold everywhere: `#FF3B30` active, `#C2241B` text and lines, `#6B1512` idle and borders.
- Apple ecosystem style for UI and UX, and not generic (Febriel, 2026-11-23).
- Normal states carry no text on the circle; a word appears only when something is wrong.
- Agent names come from a fixed list of short names, no film characters.

## Evidence on Hand

- `docs/superpowers/specs/2026-11-17-jarvis-screen-hud-design.md` (approved 2026-11-17).
- `docs/superpowers/specs/2026-11-23-jarvis-face-tether-design.md` (amends it; direction chosen 2026-11-23, details not yet read by him).
- `docs/superpowers/specs/assets/2026-11-23-jarvis-face-directions.html` (the live mockup he chose Tether from).
- `docs/superpowers/plans/2026-11-17-jarvis-plan-4-on-screen.md` (rewritten for Tether 2026-11-23, not started).
- `docs/superpowers/specs/assets/2026-11-17-jarvis-face-mockup.html` (the confirmed circle; its cards are a sketch he never commented on).
- `NSGlassEffectView` and `NSGlassEffectContainerView` are reachable from PyObjC 13.0 on macOS 26.4.1 (checked 2026-11-23).

## Product Principles

1. A glance is enough: state is read from motion and position before any text.
2. Jarvis never interrupts the app in front; it waits at the edge.
3. A question is the only thing allowed to be loud.
4. Names are for people, ids are for code: every click lands on exactly one agent or on none.
5. The face can die without Jarvis losing its voice.

## Accessibility & Inclusion

Honour Reduce Motion, Reduce Transparency and Increase Contrast. Native cards are reachable by VoiceOver. State is never carried by colour alone.
