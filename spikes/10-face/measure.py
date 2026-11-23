"""P1: CPU and memory of the probe and the WebKit helpers it started, over N seconds.

Run: uv run python spikes/10-face/measure.py <probe-pid> <webkit-pids-before-file> <seconds>
CPU % is CPU time used over wall time (100 = one core). Memory is the peak of the summed phys_footprint (from `footprint`),
falling back to RSS.
"""

import re
import subprocess
import sys
import time


def procs(probe, before):
    out = subprocess.run(["ps", "-axo", "pid=,comm="], capture_output=True, text=True).stdout
    pids = [probe]
    for line in out.splitlines():
        pid, comm = line.split(None, 1)
        if "WebKit" in comm and int(pid) not in before:
            pids.append(int(pid))
    return pids


def cpu_seconds(pids):
    out = subprocess.run(["ps", "-o", "pid=,time=", "-p", ",".join(map(str, pids))], capture_output=True, text=True).stdout
    total = {}
    for line in out.splitlines():
        pid, t = line.split()
        parts = [float(p) for p in t.replace("-", ":").split(":")]
        s = 0.0
        for p in parts:
            s = s * 60 + p
        total[int(pid)] = s
    return total


def footprint(pids):
    mb = 0.0
    for pid in pids:
        out = subprocess.run(["footprint", str(pid)], capture_output=True, text=True).stdout
        m = re.search(r"Footprint:\s*([\d.]+)\s*(KB|MB|GB)", out)
        if m:
            mb += float(m.group(1)) * {"KB": 1 / 1024, "MB": 1, "GB": 1024}[m.group(2)]
        else:
            rss = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
            mb += int(rss or 0) / 1024
    return mb


probe, before, secs = int(sys.argv[1]), {int(x) for x in open(sys.argv[2]).read().split()}, float(sys.argv[3])
pids = procs(probe, before)
c0, t0, peak = cpu_seconds(pids), time.time(), 0.0
while time.time() - t0 < secs:
    peak = max(peak, footprint(pids))
    time.sleep(min(10, secs - (time.time() - t0)) if secs - (time.time() - t0) > 0 else 0)
c1, wall = cpu_seconds(pids), time.time() - t0
per = {p: 100 * (c1.get(p, 0) - c0.get(p, 0)) / wall for p in pids}
names = dict(l.split(None, 1) for l in subprocess.run(["ps", "-o", "pid=,comm=", "-p", ",".join(map(str, pids))],
                                                     capture_output=True, text=True).stdout.splitlines())
for p, v in per.items():
    print(f"  {p} {names.get(str(p), '?').rsplit('/', 1)[-1]:<40} {v:5.1f} %")
print(f"total CPU {sum(per.values()):.1f} % of one core over {wall:.0f} s; peak memory {peak:.0f} MB")
