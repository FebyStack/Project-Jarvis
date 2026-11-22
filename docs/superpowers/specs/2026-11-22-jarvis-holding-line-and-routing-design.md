# Jarvis: a spoken holding line, and faster model routing (short design)

Date: 2026-11-22. Size: a small change to jarvisd, the front door and triage. Builds on Plan 3 (voice).

## Why

After a request that takes a while, Jarvis is silent: the Tokyo weather request on 2026-11-22 gave 17 s of nothing before the answer. Febriel can't tell whether he was heard. He also wants basic requests answered fast, with a fast model and little thinking, and more thinking only when the work needs a new agent.

## Goals

- When a request is still working about 1.5 s after it was sent and nothing has been said yet, Jarvis says a short line that fits what it is doing, once per request.
- Basic requests are answered fast, at low effort (Sonnet: Haiku proved slower to start). Work that needs a worker still goes through triage to a tiered worker.

## Non-goals

- Fast mode. As far as we know it is billed as extra usage, outside the subscription (Febriel's billing rule).
- Switching the front door's model per request (one long-lived process holds the conversation).
- Any API key or credit-based usage, and `--bare`.

## Anti-goals

- A holding line before instant answers or quick replies.
- Talking over the reply, or a line after the reply has started.
- The holding line changing the voice state, opening the follow-up window, or leaving any trace of speech said without the name.

## Constraints

- Subscription login only.
- Plan 4's interfaces stay. `Speaker` only gains a method; `state` and `level` events are unchanged.
- Unit tests never open a mic, speaker, key listener or model.

## Approaches

| Decision | Options | Picked |
|---|---|---|
| Who says the holding line | jarvisd, on a timer, worded by the tool in use; or the model, by prompt (slower, and it skipped it on 2026-11-22) | jarvisd (Febriel) |
| Front-door model | Haiku at low effort; or Sonnet at low effort (safer judgement on permission questions and mis-hearings) | Haiku first; then **Sonnet, low effort** (Febriel, after the live check: Haiku took 1.4–2.0 s to its first token against Sonnet's 0.75–0.9 s) |
| Triage model | Haiku (fixed form, fastest); Sonnet at medium effort; Opus as now (slowest) | Sonnet, medium effort, kept quick (Febriel) |

## Design

1. **Holding line (jarvisd).**
   - `config.HOLD_SECONDS = 1.5`.
   - When a `mac` request has been sent and `HOLD_SECONDS` later it is still the current request, no reply token has come, and the state is still `THINKING`, the core asks the speaker for a holding line, once per request.
   - The wording follows the last tool the front door asked for in that request, as seen by the hook:
     - `WebSearch`, `WebFetch`, or the `researcher` worker → "Looking that up."
     - `triage` or any other agent → "On it."
     - anything else, or no tool yet → "One moment."
2. **`VoiceSpeaker.hint(text)`.**
   - Synthesizes each phrase once and keeps it, then plays it through the player the way `cue()` plays the tone.
   - No `on_start` or `on_done`, so no state change.
   - Skipped if reply speech has already begun.
3. **Front door.**
   - Runs as `--model sonnet --effort low` (amended after the live check), from `config.FRONT_MODEL` and `config.FRONT_EFFORT`.
   - `.claude/agents/jarvis.md` says `model: sonnet`.
   - The HUD's front-door row reads the same constant.
   - The prompt's "if something will take more than about 5 seconds, say so first" line is replaced by: jarvisd already says a holding line, so don't open with one.
4. **Triage.** `.claude/agents/triage.md` says `model: sonnet` and `effort: medium`. Its prompt already says to look at files only briefly.

## Left to the builder

- How the timer is scheduled: `call_later` at send, or the tick.
- The exact test shapes.

## Done looks like

- Tests are green.
- Live check:
  - "What's the capital of Peru" gets no holding line and a quick answer.
  - "Look up this week's weather in Tokyo" gets "Looking that up." within about 2 s, then the result.
  - jarvisd.log's first-token times are noted before and after.
