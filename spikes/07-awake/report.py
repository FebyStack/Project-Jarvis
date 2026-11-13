"""Spike 7 report: read tmp/awake.log and check it against Task 12's bars.

Usage: python3 report.py [--bar-minutes 6]
Bars: no gap over 6 min in the log; no system sleep in `pmset -g log`; display slept.
"""
import re, subprocess, sys
from datetime import datetime
from pathlib import Path

LOG = Path(__file__).parent / "tmp" / "awake.log"
bar = float(sys.argv[sys.argv.index("--bar-minutes") + 1]) if "--bar-minutes" in sys.argv else 6.0

rows = []
for line in LOG.read_text().splitlines():
    m = re.match(r"(\S+) power=(\S+) batt=(\S+) reach=(.*)", line)
    if m:
        rows.append((datetime.fromisoformat(m[1]), m[2], m[3], m[4]))
if len(rows) < 2:
    sys.exit("need at least two log lines")

start, end = rows[0][0], rows[-1][0]
gap, gap_at = max(((b[0] - a[0]).total_seconds(), a[0]) for a, b in zip(rows, rows[1:]))
checks = [c.split(":") for r in rows for c in r[3].split(",")]
print(f"window   {start} -> {end}  ({(end - start).total_seconds() / 3600:.2f} h, {len(rows)} lines)")
print(f"gap      largest {gap / 60:.1f} min after {gap_at}  -> {'PASS' if gap / 60 <= bar else 'FAIL'} (bar {bar} min)")
ac = [((b[0] - a[0]).total_seconds(), a[0]) for a, b in zip(rows, rows[1:]) if a[1] == b[1] == "AC"]
if ac:
    g, at = max(ac)
    print(f"gap AC   largest {g / 60:.1f} min after {at} while on AC  -> {'PASS' if g / 60 <= bar else 'FAIL'}")
for l in LOG.read_text().splitlines():
    if " STOP " in l:
        print(f"stopped  {l}")
for h in dict.fromkeys(c[0] for c in checks):
    n = [c for c in checks if c[0] == h]
    print(f"reach    {h}: {sum(c[1] == 'FAIL' for c in n)} of {len(n)} checks failed")

# pmset -g log lines: "2026-11-13 22:10:43 +0800 Wake   \tWake from ..."
events = []
for line in subprocess.run(["pmset", "-g", "log"], capture_output=True, text=True).stdout.splitlines():
    m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) [+-]\d{4} (\S[^\t]*?)\s*\t(.*)", line)
    if m:
        t = datetime.strptime(m[1], "%Y-%m-%d %H:%M:%S")
        if start <= t <= end:
            events.append((t, m[2], m[3].strip()))
sleeps = [e for e in events if e[1] == "Sleep"]
print(f"sleep    {len(sleeps)} system sleep(s) in pmset log -> {'PASS' if not sleeps else 'FAIL'}")
for t, _, msg in sleeps:
    print(f"           {t} {msg[:90]}")
off = [e for e in events if "Display is turned off" in e[2]]
print(f"display  turned off {len(off)} time(s) -> {'yes' if off else 'NO (check assertions holding it on)'}")

batt = [(t, int(p)) for t, src, p, _ in rows if src == "Battery" and p.isdigit()]
if len(batt) >= 2 and batt[-1][0] > batt[0][0]:
    hours = (batt[-1][0] - batt[0][0]).total_seconds() / 3600
    print(f"battery  {batt[0][1]}% -> {batt[-1][1]}% over {hours:.2f} h on battery = {(batt[0][1] - batt[-1][1]) / hours:.1f} %/h")
else:
    print("battery  not on battery for two or more samples")
