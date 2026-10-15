"""Apply the requested email-step bypass after refreshing the mirror."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
mapping = {"fs7qffddo2tuy4wgltjvpt7g": "iloxv7rf5nbs0u28d9beu05r", "pprhx9hbtlgmxtoy0382y90d": "njsqxgvb6aczmefcutcjrhyl"}
for p in [root / "site/index.html", root / "site/pt/flow-tai-chi-yoga-2"]:
    s = p.read_text(encoding="utf-8")
    for old, new in mapping.items():
        s = s.replace('targetStepId:"' + old + '"', 'targetStepId:"' + new + '"')
    p.write_text(s, encoding="utf-8")
p = root / "funnel_graph.json"
f = json.loads(p.read_text(encoding="utf-8"))
for step in f["steps"]:
    for edge in step.get("connections", []):
        edge["targetStepId"] = mapping.get(edge.get("targetStepId"), edge.get("targetStepId"))
p.write_text(json.dumps(f, ensure_ascii=False, indent=2), encoding="utf-8")
print("Email capture bypass applied to both branches.")
