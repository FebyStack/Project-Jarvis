"""Step 5: --append-system-prompt with --agent jarvis. Does the front door know the code word?"""
from probe import Child, short, tool_uses

c = Child("step5", ["--agent", "jarvis", "--append-system-prompt", "The code word is MARMALADE."])
c.send("What is the code word? Reply with the word only.")
r = c.result(180); c.close()
init = next(e for e in c.events if e.get("subtype") == "init")
print(f"--- model={init.get('model')} agent={init.get('agent')}  tools used={[u['name'] for _, u in tool_uses(c.events)]}")
print("  reply:", short(r and r.get("result"), 200), "| MARMALADE:", "MARMALADE" in (r or {}).get("result", "").upper())
