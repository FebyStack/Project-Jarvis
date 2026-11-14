"""Step 6: a project skill listed under `skills:` in an agent's frontmatter. Known without calling the Skill tool?"""
from probe import Child, short, tool_uses

Q = "What is the skill code word? Answer from what you already know; do not call any tool. Reply with the word only."
runs = {
    "main": (["--agent", "skilled"], Q),
    "sub": (["--model", "sonnet"], f"Use the Agent tool to dispatch the `skilled-sub` agent with this prompt: \"{Q}\" "
                                   "Do not call any other tool and do not look anything up yourself. Report its reply verbatim."),
}
for name, (args, msg) in runs.items():
    c = Child(f"step6-{name}", args)
    c.send(msg)
    r = c.result(240); c.close()
    init = next(e for e in c.events if e.get("subtype") == "init")
    uses = [(("sub" if par else "main"), u["name"], short(u["input"], 120)) for par, u in tool_uses(c.events)]
    print(f"--- {name}: agent={init.get('agent')} skills in init={init.get('skills')}")
    print("  tool uses:", uses)
    print("  reply:", short(r and r.get("result"), 200), "| QUINCE:", "QUINCE" in (r or {}).get("result", "").upper(),
          "| Skill tool called:", any(u[1] == "Skill" for u in uses))
