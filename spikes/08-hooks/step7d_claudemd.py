"""Step 7 side check: does ~/.claude/CLAUDE.md (user memory) reach the child under --setting-sources project?"""
from probe import Child, short

c = Child("step7d", ["--model", "haiku"], {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"})
c.send("Without calling any tool: quote, exactly, the first markdown heading of each CLAUDE.md file in your context, with the file path if shown. If none, say NONE.")
r = c.result(120); c.close()
print("reply:", short(r and r.get("result"), 500))
