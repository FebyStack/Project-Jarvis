"""Spike 1 step 6b: detached claude -p that outlives its parent, then --resume by session id."""
import json, os, subprocess, sys, time
from clean import clean_env
here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, "tmp", "detached.json")
if sys.argv[1] == "start":
    subprocess.Popen(["claude", "-p", "--model", "haiku", "--setting-sources", "project", "--output-format", "json",
                      "Remember the word ALIVE-DETACHED. Reply with exactly that word."],
                     stdin=subprocess.DEVNULL, stdout=open(out, "w"), stderr=subprocess.STDOUT, cwd=here, env=clean_env(),
                     start_new_session=True)
    print("parent exiting at once, pid", os.getpid())
else:
    first = json.load(open(out))
    print("detached result:", first.get("result"), "| session", first.get("session_id"))
    r = subprocess.run(["claude", "-p", "--model", "haiku", "--setting-sources", "project", "--resume", first["session_id"],
                        "--output-format", "json", "What exact word did you reply with before? One word."],
                       capture_output=True, text=True, cwd=here, env=clean_env(), timeout=120)
    second = json.loads(r.stdout)
    print("resumed result:", second.get("result"), "| session", second.get("session_id"))
