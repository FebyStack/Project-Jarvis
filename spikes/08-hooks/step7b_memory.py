"""Step 7 side check: does the repo's Claude Code auto-memory (memory_paths.auto) reach the isolated child?"""
from probe import Child, short

c = Child("step7b", ["--model", "haiku"])
c.send("Without calling any tool: does your context contain a memory index (MEMORY.md) or notes about running plans in a separate Opus session, or about Claude credit in commits? Quote any titles you see, or say NONE.")
r = c.result(120); c.close()
print("reply:", short(r and r.get("result"), 400))
