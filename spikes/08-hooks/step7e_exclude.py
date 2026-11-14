"""Step 7 side check: does settings `claudeMdExcludes` keep ~/.claude/CLAUDE.md out of the child?"""
import json, os
import probe
from probe import Child, TMP, short

s = json.load(open(os.path.join(probe.here, "probe-settings.json"))) | {"autoMemoryEnabled": False,
     "claudeMdExcludes": [os.path.expanduser("~/.claude/CLAUDE.md")]}
alt = os.path.join(TMP, "settings-exclude.json"); json.dump(s, open(alt, "w"))
probe.BASE[probe.BASE.index("--settings") + 1] = alt
c = Child("step7e", ["--model", "haiku"])
c.send("Without calling any tool: quote, exactly, the first markdown heading of each CLAUDE.md file in your context, with the file path if shown. If none, say NONE.")
r = c.result(120); c.close()
print("reply:", short(r and r.get("result"), 500))
