"""Spike 2: train a small custom wake-word head on openWakeWord embeddings.

Positives: Febriel's takes from record_session.py plus macOS `say` voices, augmented with his room noise.
Negatives: his normal talk, his room, `say` confusable phrases, openWakeWord validation features (10.7 h).
A 2.0 s clip is exactly 16 embedding frames; the phrase is placed to end near the clip's end,
which is when a streaming detector sees it. No audio is written except temp `say` files, deleted at once.

usage: train_wake.py PHRASE   (hey_jarvis | jarvis)
"""
import json, os, subprocess, sys, wave
import joblib
import numpy as np
from openwakeword.utils import AudioFeatures
from sklearn.neural_network import MLPClassifier

SR, CLIP = 16000, 32000
phrase = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
rec, data = os.path.join(here, "tmp", "rec"), os.path.join(here, "data")
rng = np.random.default_rng(7)

audio = np.frombuffer(wave.open(os.path.join(rec, "session.wav")).readframes(10**9), dtype=np.int16).astype(np.float32)
markers = json.load(open(os.path.join(rec, "markers.json")))
part = lambda name: [m for m in markers if m["part"] == name]
room = np.concatenate([audio[m["start"]:m["end"]] for m in part("room")])
talk = np.concatenate([audio[m["start"]:m["end"]] for m in part("talk")])


def trim(x, floor=None):
    """Cut a take down to the spoken phrase: 20 ms RMS frames above 3x the take's own background (its 10th
    percentile) or a fixed floor. Takes whose peak is under 2.5x their background are treated as missed."""
    f = 320
    rms = np.sqrt(np.mean(x[: len(x) // f * f].reshape(-1, f) ** 2, axis=1))
    base = float(np.percentile(rms, 10)) if floor is None else floor
    if floor is None and rms.max() < 2.5 * base:
        return None
    on = np.where(rms > max(3 * base, 150))[0]
    if len(on) == 0:
        return None
    s, e = max(0, on[0] * f - 1600), min(len(x), (on[-1] + 1) * f + 1600)
    return x[s:e] if (e - s) / SR < 1.9 else None




def say_clip(text, voice, rate):
    path = os.path.join(rec, "say.wav")
    subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", path, "--data-format=LEI16@16000", text], check=True)
    x = np.frombuffer(wave.open(path).readframes(10**7), dtype=np.int16).astype(np.float32)
    os.remove(path)
    return trim(x, 30.0)


def place(x, end_at=None):
    """Put x on a 2.0 s bed of room noise, ending near the end of the clip, with random gain and speed."""
    speed = rng.uniform(0.9, 1.1)
    x = np.interp(np.arange(0, len(x), speed), np.arange(len(x)), x)
    end = CLIP - int(rng.uniform(0.02, 0.15) * SR) if end_at is None else end_at
    x = x[-end:] * rng.uniform(0.4, 1.6)  # keep the end of the phrase if it is longer than the room left
    bed_start = rng.integers(0, len(room) - CLIP)
    out = room[bed_start: bed_start + CLIP] * rng.uniform(0.3, 1.0)
    out[end - len(x): end] += x
    return np.clip(out, -32768, 32767)


NOVELTY = {"Albert", "Bad", "Bahh", "Bells", "Boing", "Bubbles", "Cellos", "Good", "Jester", "Organ", "Superstar",
           "Trinoids", "Whisper", "Wobble", "Zarvox"}
voices = list(dict.fromkeys(l.split()[0] for l in subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout.splitlines()
                            if " en_" in l and l.split()[0] not in NOVELTY))
rates = (150, 190, 230)

# ── positives ──
other = "jarvis" if phrase == "hey_jarvis" else "hey_jarvis"
mine = [trim(audio[m["start"]:m["end"]]) for m in part(phrase)]
kept = [x for x in mine if x is not None]
rng.shuffle(kept)
n_test = max(2, len(kept) // 5)
test_takes, train_takes = kept[:n_test], kept[n_test:]
spoken = "Hey Jarvis" if phrase == "hey_jarvis" else "Jarvis"
synth = [c for v in voices for r in rates if (c := say_clip(spoken, v, r)) is not None]
pos = [place(x) for x in train_takes for _ in range(15)] + [place(x) for x in synth for _ in range(2)]
if phrase == "jarvis":  # "Hey Jarvis" also contains the bare wake word
    pos += [place(x) for m in part("hey_jarvis") if (x := trim(audio[m["start"]:m["end"]])) is not None for _ in range(5)]

# ── negatives ──
confusables = ["Travis", "service", "nervous", "garbage", "harvest", "hey there", "hey Siri", "hey Charles", "jars",
               "hey Jarvis" if phrase == "jarvis" else "Jarvis", "Marvin", "Davis", "Jervis", "hey, Chris", "car service"]
if phrase == "jarvis":
    confusables.remove("hey Jarvis")
neg_say = [c for t in confusables for v in voices[::3] for r in (170, 220) if (c := say_clip(t, v, r)) is not None]
neg = [place(x) for x in neg_say]
if phrase == "hey_jarvis":  # bare "Jarvis" should not wake the two-word model
    neg += [place(x) for m in part("jarvis") if (x := trim(audio[m["start"]:m["end"]])) is not None for _ in range(5)]
for src in (talk, room):
    for s in range(0, len(src) - CLIP, SR // 4):
        neg.append(np.clip(src[s: s + CLIP] * rng.uniform(0.6, 1.4), -32768, 32767))

feat = AudioFeatures()
emb = lambda clips: feat.embed_clips(np.stack(clips).astype(np.int16), batch_size=64)
Xp, Xn = emb(pos), emb(neg)
val = np.load(os.path.join(data, "validation_set_features.npy"), mmap_mode="r")
cut = int(len(val) * 0.7)
win = lambda a, step: np.stack([a[i: i + 16] for i in range(0, len(a) - 16, step)])
Xv_train, val_test = win(np.asarray(val[:cut]), 8), np.asarray(val[cut:])

X = np.concatenate([Xp, Xn, Xv_train]).reshape(-1, 16 * 96)
y = np.concatenate([np.ones(len(Xp)), np.zeros(len(Xn) + len(Xv_train))])
reps = max(1, int((len(Xn) + len(Xv_train)) / len(Xp) / 3))  # oversample positives
X, y = np.concatenate([X] + [X[y == 1]] * (reps - 1)), np.concatenate([y] + [np.ones(int((y == 1).sum()))] * (reps - 1))
clf = MLPClassifier(hidden_layer_sizes=(128, 32), early_stopping=True, max_iter=60, random_state=7).fit(X, y)

# ── held-out checks ──
test_clips = [place(x) for x in test_takes for _ in range(3)]
p_test = clf.predict_proba(emb(test_clips).reshape(-1, 16 * 96))[:, 1]
p_val = np.concatenate([clf.predict_proba(win(val_test[i: i + 10016], 1).reshape(-1, 16 * 96))[:, 1]
                        for i in range(0, len(val_test) - 16, 10000)])  # every 80 ms step, in batches
hours = len(val[cut:]) * 0.08 / 3600
report = {"phrase": phrase, "takes_recorded": len(mine), "takes_usable": len(kept), "train_takes": len(train_takes),
          "test_takes": len(test_takes), "synthetic_positives": len(synth), "voices": len(voices),
          "train_pos_clips": len(Xp), "train_neg_clips": len(Xn) + len(Xv_train)}
for thr in (0.5, 0.7, 0.9):
    hits = np.where(p_val >= thr)[0]
    events = int(np.sum(np.diff(hits) > 25) + (1 if len(hits) else 0))  # windows 2 s apart count once
    report[f"thr{thr}"] = {"held_out_recall": round(float(np.mean(p_test >= thr)), 3),
                           "false_wakes_per_hour_on_held_out_audio": round(events / hours, 2)}
report["held_out_hours"] = round(hours, 2)
joblib.dump(clf, os.path.join(data, f"wake_{phrase}.joblib"))
print(json.dumps(report, indent=1))
