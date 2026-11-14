"""Step 7: --setting-sources project --strict-mcp-config, no --mcp-config. What does system/init list? (Contrast: no flags.)"""
import os, subprocess, json
from probe import Child, TMP, here, short
from clean import clean_env

c = Child("step7", ["--model", "haiku"])
c.send("Say OK.")
c.result(120); c.close()
init = next(e for e in c.events if e.get("subtype") == "init")
print("--- init keys:", sorted(init))
for k in ("mcp_servers", "plugins", "slash_commands", "skills", "agents", "apiKeySource"):
    print(f"  {k}: {short(init.get(k), 600)}")
print("  plugin-namespaced commands:", [s for s in init.get("slash_commands", []) if ":" in s])

# contrast: same scrubbed env, none of the three flags
p = subprocess.run(["claude", "-p", "--model", "haiku", "--output-format", "stream-json", "--verbose", "Say OK."],
                   capture_output=True, text=True, cwd=here, env=clean_env(), timeout=180)
open(os.path.join(TMP, "step7-contrast.jsonl"), "w").write(p.stdout)
ci = next(json.loads(l) for l in p.stdout.splitlines() if '"init"' in l)
print("--- contrast (no flags): mcp_servers:", short([m.get("name") for m in ci.get("mcp_servers", [])], 400))
print("  plugins:", short([x.get("name") if isinstance(x, dict) else x for x in ci.get("plugins", [])], 400))
print("  plugin-namespaced commands:", len([s for s in ci.get("slash_commands", []) if ":" in s]))
