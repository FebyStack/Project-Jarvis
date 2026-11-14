---
name: system
description: Small Mac jobs Jarvis does itself — open an app, set the volume, set a timer. Use for these instead of calling triage.
---
# Small Mac jobs

Each one is a single Bash command. Say what you did in one short sentence.

## Open an app
`open -a "App Name"`, for example `open -a "Safari"`. If the name is unclear, `ls /Applications` and pick the match.

## Volume
`osascript -e 'set volume output volume N'`, with N from 0 to 100. Mute: `osascript -e 'set volume output muted true'`; unmute with `false`.

## Timer
Run it in the background so you stay free:

`sleep N && osascript -e 'display notification "WHAT" with title "Jarvis timer"'`

with N in seconds and WHAT a few words on what the timer is for. Use the Bash tool with `run_in_background: true`. Say when it will go off.

## Anything else on screen
Clicking, typing into other apps, moving or resizing windows: not yet. Tell Febriel on-screen control comes in a later version.
