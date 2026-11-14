---
name: system
description: Small Mac jobs Jarvis does itself — open an app, set the volume, set a timer. Use for these instead of calling triage.
---
# Small Mac jobs

Each one is a single Bash command, written exactly as below so it runs without a question. Say what you did in one short sentence.

## Open an app
`open -a "/System/Applications/NAME.app"` for Apple's own apps (Notes, Calendar, Music…), or `open -a "/Applications/NAME.app"` for the others (Safari, Chrome…). If you are not sure where it is, `ls /Applications /System/Applications` and pick the match. Any other form of `open` asks Febriel first.

## Volume
`osascript -e 'set volume output volume N'`, with N a whole number from 0 to 100. Mute: `osascript -e 'set volume output muted true'`; unmute with `false`.

## Timer
`sleep N && osascript -e 'display notification "WHAT" with title "Jarvis timer"'`

with N in seconds and WHAT a few words on what the timer is for, without quotation marks or backslashes. Run it with the Bash tool's `run_in_background: true` so you stay free, and say when it will go off.

## Anything else on screen
Clicking, typing into other apps, moving or resizing windows: not yet. Tell Febriel on-screen control comes in a later version.
