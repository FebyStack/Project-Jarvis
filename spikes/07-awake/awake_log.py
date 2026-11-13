"""Spike 7 logger: append power, battery and a reachability check to tmp/awake.log.

Usage: caffeinate -i python3 awake_log.py HOST [HOST ...] [--interval SECONDS]   (default 300)
Safety: on battery below 20 % it logs why and exits, so caffeinate ends and the Mac can sleep.
"""
import re, subprocess, sys, time
from datetime import datetime
from pathlib import Path

LOG = Path(__file__).parent / "tmp" / "awake.log"


def battery():
    out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
    src = re.search(r"drawing from '(\w+)", out)
    pct = re.search(r"(\d+)%", out)
    return (src.group(1) if src else "?"), (pct.group(1) if pct else "?")


def reach(host):
    r = subprocess.run(["ping", "-c", "1", "-t", "5", host], capture_output=True, text=True)
    ms = re.search(r"time=([\d.]+) ms", r.stdout)
    return f"{host}:ok:{ms.group(1)}ms" if r.returncode == 0 and ms else f"{host}:FAIL"


if __name__ == "__main__":
    args = sys.argv[1:]
    interval = 300
    if "--interval" in args:
        i = args.index("--interval")
        interval = int(args.pop(i + 1)); args.pop(i)
    hosts = args
    LOG.parent.mkdir(exist_ok=True)
    while True:
        src, pct = battery()
        line = f"{datetime.now().isoformat(timespec='seconds')} power={src} batt={pct} reach={','.join(reach(h) for h in hosts)}"
        with LOG.open("a") as f:
            f.write(line + "\n")
        print(line, flush=True)
        if src == "Battery" and pct.isdigit() and int(pct) < 20:
            with LOG.open("a") as f:
                f.write(f"{datetime.now().isoformat(timespec='seconds')} STOP on battery at {pct}% (below 20%); exiting so the Mac can sleep\n")
            sys.exit(0)
        time.sleep(interval)
