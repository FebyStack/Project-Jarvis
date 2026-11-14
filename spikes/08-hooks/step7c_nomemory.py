"""Step 7 side check: two ways to keep auto-memory out — settings `autoMemoryEnabled: false`, env CLAUDE_CODE_DISABLE_AUTO_MEMORY=1."""
import json, os
import probe
from probe import Child, TMP, short

Q = "Without calling any tool: does your context contain a memory index (MEMORY.md)? Quote any titles you see, or say NONE."
s = json.load(open(os.path.join(probe.here, "probe-settings.json"))) | {"autoMemoryEnabled": False}
alt = os.path.join(TMP, "settings-nomemory.json"); json.dump(s, open(alt, "w"))
for name, env, swap in (("settings", {}, alt), ("env", {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}, None)):
    base = probe.BASE[:]
    if swap:
        probe.BASE[probe.BASE.index("--settings") + 1] = swap
    c = Child(f"step7c-{name}", ["--model", "haiku"], env)
    probe.BASE[:] = base
    c.send(Q)
    r = c.result(120); c.close()
    init = next(e for e in c.events if e.get("subtype") == "init")
    print(f"--- {name}: memory_paths={init.get('memory_paths')}  reply: {short(r and r.get('result'), 200)}")
