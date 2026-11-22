# Jarvis understands Bisaya — design

Date: 2026-11-20 · Status: approved by Febriel 2026-11-22

## Why
Febriel speaks Bisaya (Cebuano), and English with a Bisaya accent. He wants Jarvis to understand him either way (his words: "understand bisaya and its accent").

What gets in the way today is the speech-to-text, not the model that answers. Claude reads Bisaya fine. Parakeet (`parakeet-tdt-0.6b-v2`) only knows English, so it writes Bisaya words down as English look-alikes, and his accent costs some English words too (the name was heard as "javi", "javier" and "travis" in Task 14).

## Goals
- When Febriel says a request in Bisaya, or in a Bisaya–English mix, Jarvis does the right thing.
- His accented English is understood at least as well as it is today.
- Everything stays local: audio never leaves the Mac, and there are no API keys.

## Non-goals (v1)
- **Spoken Bisaya replies.** Kokoro can't speak Bisaya, and the only local Bisaya voice ([MMS](https://huggingface.co/facebook/mms-tts-ceb)) would be a different, rougher voice. Jarvis answers in English. This can be looked at later.
- **Bisaya for the fixed phrases** (instant answers, "cancel", "never mind", time/date, mute) and **Bisaya in the wake word**. These still run on Parakeet's English text.
- **Phone dictation.** iOS turns the speech into text before Jarvis gets it. Only the written hint helps there.
- **Training Parakeet on his voice.** It needs hours of transcribed recordings, the same reason the custom wake model failed.

## Anti-goals (a failure even if it works)
- **A Bisaya word must never count as "yes" to the gate.** Spoken yes/no answers, and later "yes to Nova", stay as the exact English words Parakeet hears (`instant._ANSWERS`). A misheard "oo" must never approve a risky action.
- **Speech without the name never reaches the second listener.** The rule "speech without the name leaves no trace" holds, and the CPU cost stays low.
- English requests and waking on "Jarvis" must not get worse.
- No cloud speech service and no paid keys.

## Constraints
- M4 with 16 GB of memory, shared with the `claude` processes. Model memory counts.
- MLX models run on one thread (`Engines`). A second MLX model on that thread adds its time to every request.
- Today, from the end of speech to the first spoken word takes about 2.2–2.8 s, against a 2.5 s target. Febriel relaxed that target for spoken requests on 2026-11-20 (see the bars in Part 2).
- jarvisd loads models offline (`HF_HUB_OFFLINE=1`). Downloads happen only through `jarvis models`, and each new model download needs Febriel's okay first (name, source, size).
- Plan 3 owns `jarvis/voice/` until it is finished. The test lives in `spikes/10-bisaya/`, so it can run now. Wiring into jarvisd waits for Plan 3.

## Approaches considered
1. **The hint only.** Keep Parakeet, and tell Claude that Febriel has a Bisaya accent and that Bisaya words show up as English look-alikes. Takes hours. It helps the accent and the odd Bisaya word, but whole Bisaya sentences still arrive as nonsense.
2. **A second listener for the request, plus the hint. (Febriel's pick, 2026-11-20.)** Parakeet keeps the wake word, fixed phrases and yes/no. Speech that becomes a request also goes to a model that knows Cebuano, and Claude gets both transcripts. It runs on every request: Febriel chose "always" over running it only when Parakeet is unsure, and accepts slower replies. Costs: another model's memory, and more time per request. A test on his voice comes first.
3. **One model that speaks both, for everything.** Dropped. Listening for the wake word runs on everything the mic hears, so a big model there costs a lot of CPU, and it would throw away the wake tuning from Task 14.
4. **Training Parakeet on his voice.** Dropped, for lack of data (see Non-goals).

## Design

### Part 1 — the hint (ships first, alone)
In `.claude/agents/jarvis.md`, under "How you talk", replace the line "A request may be transcribed speech…" with:

> - A spoken request is transcribed on the Mac. Febriel speaks English with a Bisaya (Cebuano) accent, and sometimes Bisaya or a mix of the two; the English transcriber writes Bisaya words as English look-alikes. Read past plain mis-hearings ("report" for "repo"). If a wrong guess would change what you do, ask. Reply in English even when he speaks Bisaya.

Part 3 adds one sentence about the second transcript. This part changes no code.

### Part 2 — the test (`spikes/10-bisaya/`)
**Recordings.** A small script records Febriel through the same 16 kHz mono path `wake_tune.py` uses, then saves each utterance as a WAV file with the words he says he spoke, typed by him. The set:
- 12 requests in Bisaya or mixed, said the way he would really talk to Jarvis
- 8 requests in English
- 3 one-breath "Jarvis, <Bisaya request>" utterances, to check that Parakeet still finds the name when Bisaya follows it

**Candidate listeners.** Each is checked for license and Cebuano support before any download:
- [BuzzASR/cebuano](https://huggingface.co/BuzzASR/cebuano): Whisper large-v3 fine-tuned on Cebuano. Run through `mlx-whisper` (converted, 4- or 8-bit if quality holds), or through `transformers` on MPS.
- Meta [Omnilingual ASR](https://arxiv.org/abs/2511.09690) CTC 300M or 1B, if `ceb_Latn` is on its supported list and it installs on macOS arm64. If either is false, it's dropped.
- Meta `mms-1b-all` with its Cebuano adapter (CTC; Whisper's 30 s padding doesn't apply, so it is likely faster).
- Stock `whisper-large-v3-turbo` (`mlx-whisper`), with no language set. This is the baseline that shows whether a fine-tune is needed at all.
- Parakeet, the English baseline.
- *(My call.)* If the large models miss the time bar, a short search for small or medium Whisper models fine-tuned on Cebuano. That way a dead end means none of them work, not just that the list was short.

**What's measured.** For each recording and each listener: the transcript, seconds per utterance (warm), and peak memory. Then the real test: the hint (with the second-transcript sentence) plus both transcripts go to Claude, and each result is judged on whether Claude understood what Febriel meant, against his typed text. *(My call.)* This is a dry run: a `claude -p` run with the `jarvis` agent prompt and no tools, asked to say in one line what it would do. It is not `jarvis ask`, which would act for real, speak, and write to `raw/`. The builder judges each line against Febriel's typed text, and only the ones the builder is unsure of go to Febriel.

**Recordings** *(my call)*: they stay on the Mac in `spikes/10-bisaya/data/`, which is already git-ignored, along with `*.wav`. They are never committed, and they're kept so the test can be re-run when a new model comes out. Because the repo is public, `findings.md` holds counts, timings and a few short mishearing examples, never his full requests.

**Bars** (my proposals; Febriel can change them):
- Bisaya or mixed: Claude gets the meaning in at least 10 of 12.
- English: Claude gets it right at least as often as with Parakeet alone.
- One-breath wake: all 3 still wake.
- Extra time: Febriel accepts slower replies so that the second listener runs on every request (2026-11-20: "Always, accept slower"). *(My call.)* The limit is at most **1.5 s** extra per request for a 5 s utterance, warm, on the M4. Beyond that, replies take about 4 s and start to feel broken.
- Memory: the second listener's resident size is at most about 1.5 GB.

**If it's over the time limit**, try the faster candidates (MMS, the smaller fine-tunes). If none of them meet the bars, only Part 1 ships.

**Results** go in `docs/spikes/findings.md` under "Bisaya listener". If no candidate meets the bars, only Part 1 ships, and the result is listed as a dead end in `PROJECT.md`.

### Part 3 — wiring into jarvisd (after Plan 3, and only if Part 2 passes)
- `config.BISAYA_MODEL` names the winner. `jarvis models` downloads it, and `jarvis doctor` shows whether it loaded.
- `Engines` loads and warms a third model, `transcribe_bisaya(pcm)`. If it's missing or fails to load, voice still works without it: the error is logged, and doctor shows "Bisaya off".
- `Voice` sends every utterance that becomes a request (the paths that call `jarvis.heard`) to the second listener, always, with no confidence gate. This happens after the Parakeet pass that decided it was a request. Waking, fixed phrases, "cancel" while thinking, and yes/no answers use Parakeet's text alone.
- `heard` and `submit` carry the second transcript separately. `instant.match` and the ask answers see only Parakeet's text. The brain gets Parakeet's text followed by a line `(Bisaya ear: "<text>")`, unless the two are the same once case and punctuation are ignored.
- The hint gains one sentence: "When a line `(Bisaya ear: …)` follows, it is the same speech heard by a Cebuano transcriber; use whichever makes sense, or both."
- `raw/` keeps what was sent to the brain, both lines included.

## Left to the builder
- How the test script is laid out, and whether it reuses `spikes/09-voice/_common.py`.
- How the second transcript is joined when a request was cut at the length limit and arrives in pieces (the `_start` path).
- Whether the second model runs on the MLX thread or on its own thread (if it's PyTorch/MPS), as long as the time bar holds.
- Test layout for Part 3, following the existing `tests/voice` patterns.

## Order
1. Part 1, as soon as this is approved.
2. Part 2, which can run now beside Plan 3. It needs Febriel for the recordings and an okay for each model download.
3. Part 3, after Plan 3 is done. My pick is before Plan 4, since it's small and the voice code will still be fresh. Febriel decides the order.
