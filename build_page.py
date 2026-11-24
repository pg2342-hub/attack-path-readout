"""Build docs/index.html (the GitHub Pages demo) from the recorded run and the gate reports.

    python3 docs/build_page.py              # uses runs/live and reports/
    python3 docs/build_page.py --preview    # uses the rules-only template tickets, for layout work only
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from readout import agents, data, guardrails, metrics, summary  # noqa: E402

preview = "--preview" in sys.argv
a = data.assets()
if preview:
    tickets = {p["id"]: guardrails.apply(agents.template_ticket(p), p, a) for p in data.paths()}
    sums = {}
else:
    tickets = json.loads((ROOT / "runs" / "live" / "run1" / "tickets.json").read_text())
    sums = json.loads((ROOT / "runs" / "live" / "summaries.json").read_text())
issues_file = ROOT / "runs" / "live" / "run1" / "issues.json"
issues = json.loads(issues_file.read_text()) if issues_file.exists() and not preview else {}

views = {}
for ro in data.pilot()["pilot"]["readouts"]:
    m = metrics.readout(ro["day"], tickets)
    s = sums.get(ro["id"]) or {"text": summary.plain(summary.facts(m)), "used": "plain fallback"}
    views[ro["id"]] = {"label": ro["label"], "day": ro["day"], "metrics": m,
                       "summary": s["text"], "summary_by": s["used"]}


def gate(name):
    f = ROOT / "reports" / name / "results.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text())
    rows = []
    for c in d["cases"]:
        for r in c["runs"]:
            crit = {ch["id"] for ch in d["checks"] if ch.get("critical")}
            rows.append({"case": c["id"], "run": r["run"], "passed": r["passed"],
                         "critical": bool(set(r["failed_checks"]) & crit), "failed": r["failed_checks"],
                         "cost": r.get("cost_usd", 0), "judge": r.get("judge_cost_usd", 0),
                         "latency": r.get("latency_s", 0)})
    return {"decision": d["decision"], "runs": d["runs"], "cells": rows,
            "checks": [{"id": c["id"], "text": c.get("text", ""), "critical": c.get("critical", False)} for c in d["checks"]]}


meta = [t.get("_meta", {}) for t in tickets.values() if t.get("_meta")]
paths_out = []
for p in data.paths():
    paths_out.append({"id": p["id"], "title": p["title"], "phase": p["phase"], "target": p["target"],
                      "steps": [{**s, "name": a[s["asset"]]["name"], "product": a[s["asset"]]["product"],
                                 "crown": a[s["asset"]]["crown_jewel"]} for s in p["steps"]],
                      "evidence": p["evidence"], "timeline": p["timeline"], "retest_notes": p.get("retest_notes", {}),
                      "hold_note": p.get("hold_note"), "ticket": {k: v for k, v in tickets[p["id"]].items() if k != "_meta"},
                      "issue": issues.get(p["id"])})
payload = {
    "preview": preview, "views": views, "paths": paths_out,
    "gates": {"live": gate("live"), "template": gate("template"), "naive": gate("naive")},
    "kev": data.kev_meta(),
    "cost": {"tickets": len(meta), "usd": round(sum(x["cost_usd"] for x in meta), 4),
             "mean_latency_s": round(sum(x["latency_s"] for x in meta) / len(meta), 1) if meta else None,
             "model": meta[0]["model"] if meta else None},
}
template = (ROOT / "docs" / "template.html").read_text()
out = template.replace("/*DATA*/null", json.dumps(payload))
(ROOT / "docs" / "index.html").write_text(out)
print("wrote docs/index.html", len(out), "bytes", "(preview)" if preview else "")
