---
name: sleeper
description: Probe worker that runs slowly. Runs `sleep 4` over and over.
model: haiku
tools: Bash
---
Run `sleep 4` with the Bash tool, one call at a time, 15 times in a row. Never run two at once and never combine them. If a call is refused, try the next one anyway. Then reply DONE.
