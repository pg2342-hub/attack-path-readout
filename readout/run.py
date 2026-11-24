"""Write tickets for every validated path, apply the guardrails, and save the run.

    python3 -m readout.run --agent template --out runs/template
    python3 -m readout.run --agent claude --runs 3 --out runs/live      # needs ANTHROPIC_API_KEY
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import agents, data, guardrails, metrics


def write_tickets(agent: str) -> dict[str, dict]:
    a = data.assets()
    fn = {"claude": agents.claude_ticket, "template": agents.template_ticket, "naive": agents.naive_ticket}[agent]
    out = {}
    for p in data.paths():
        t = fn(p)
        meta = t.pop("_meta", None)
        t = guardrails.apply(t, p, a)
        if meta:
            t["_meta"] = meta
        out[p["id"]] = t
        print(f"{p['id']}  {t['final_route']:<12} {t.get('owner_team')}  {len(t['guardrail_problems'])} problems")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", choices=["claude", "template", "naive"], default="template")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summaries", action="store_true", help="also write the weekly summaries with Claude")
    args = ap.parse_args()
    out = Path(args.out)
    for r in range(1, args.runs + 1):
        d = out / f"run{r}"
        d.mkdir(parents=True, exist_ok=True)
        tickets = write_tickets(args.agent)
        (d / "tickets.json").write_text(json.dumps(tickets, indent=1) + "\n")
    if args.summaries:
        from . import summary
        tickets = json.loads((out / "run1" / "tickets.json").read_text())
        s = {}
        for ro in data.pilot()["pilot"]["readouts"]:
            s[ro["id"]] = summary.claude_summary(metrics.readout(ro["day"], tickets))
            print(ro["id"], s[ro["id"]]["used"], s[ro["id"]]["problems"])
        (out / "summaries.json").write_text(json.dumps(s, indent=1) + "\n")


if __name__ == "__main__":
    main()
