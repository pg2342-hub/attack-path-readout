"""Ticket writers. Each takes one validated attack path and returns a draft fix ticket.

claude_ticket   the real agent: one Claude call per path, structured output
template_ticket a rules-only baseline: copies the KEV required action into a fixed template
naive_ticket    a negative control: sends every ticket to the team that owns the target and assigns it
"""
from __future__ import annotations

import json
import os
import time

from . import data

MODEL = os.environ.get("READOUT_MODEL", "claude-opus-5-5")
PRICE = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0)}  # USD per million tokens in/out

SYSTEM = """You write remediation tickets for a security team at a large electric utility.
You get one attack path that an autonomous validation tool has already confirmed, the assets on it,
and the public CISA KEV and FIRST EPSS records for its CVEs.

Write one ticket for the team that can close the path with the least work. Rules:
- fix_point_asset is the asset_id of the step to fix. Prefer the first step on the path: fixing the
  entry point breaks everything after it. Only pick a later step if the first step has no fix.
- fix_steps: 2 to 5 short actions for that asset's owner, in the order they should happen: any
  interim step that cuts exposure today (restrict access, take it off the internet) comes before the
  patch or upgrade, and checks for compromise and credential resets come after. Base them on the KEV
  required action (quote its specific demands, such as killing sessions or checking for compromise) or,
  for a misconfiguration, on the configuration change that removes it. Name the product and asset.
  Your inputs do not include vendor advisories, version numbers or the vendor's mitigation steps, so
  never invent them. Point once, in one step, to "the vendor's advisory for <CVE IDs>" for the fixed
  release and its mitigation and integrity-check steps. Every other step must stand on its own: say
  what to do (for example block the management interface from the internet, end active sessions, reset
  the credentials named on the path), not "per vendor instructions" or "as CISA requires".
- why_it_matters: two or three plain sentences about what an attacker could reach and what that would
  mean for the utility. Do not lead with KEV or EPSS; at most one short clause on how widely it is exploited.
- summary and fix_steps must agree on which asset each fact belongs to (for example where a credential
  was found and where it was reused).
- verify_steps: 1 to 3 checks the owner can run to show the fix holds, ending with a request to rerun
  the validation of this path.
- Describe fixes only. Never include commands, exploit strings, payloads or how the attack works step by step.
- Only mention CVE IDs that appear in the path.
- route: "human_review" if the path ends at an asset marked crown_jewel, otherwise "assign".
- exec_line: one sentence of about 20 words (never more than 25), plain English for an executive, no CVE IDs.
Write plainly. No em dashes."""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "fix_point_asset": {"type": "string"},
        "fix_steps": {"type": "array", "items": {"type": "string"}},
        "verify_steps": {"type": "array", "items": {"type": "string"}},
        "exec_line": {"type": "string"},
        "route": {"type": "string", "enum": ["assign", "human_review"]},
        "route_reason": {"type": "string"},
    },
    "required": ["title", "summary", "why_it_matters", "fix_point_asset", "fix_steps",
                 "verify_steps", "exec_line", "route", "route_reason"],
    "additionalProperties": False,
}


def claude_ticket(path: dict, client=None) -> dict:
    """One Claude call. Returns the ticket plus a _meta block with tokens, cost and latency."""
    import anthropic

    client = client or anthropic.Anthropic()
    ctx = data.context(path)
    start = time.perf_counter()
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": "Validated attack path and context:\n" + json.dumps(ctx, indent=1)}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    latency = time.perf_counter() - start
    p_in, p_out = PRICE.get(MODEL, (4.0, 20.0))
    meta = {"model": getattr(resp, "model", MODEL), "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens, "latency_s": round(latency, 2),
            "cost_usd": round((resp.usage.input_tokens * p_in + resp.usage.output_tokens * p_out) / 1e6, 5),
            "stop_reason": resp.stop_reason}
    if resp.stop_reason == "refusal":
        return {"_meta": meta, "route": "human_review", "route_reason": "model declined to write this ticket"}
    text = next(b.text for b in resp.content if b.type == "text")
    ticket = json.loads(text)
    ticket["_meta"] = meta
    return ticket


def template_ticket(path: dict) -> dict:
    a, k = data.assets(), data.kev()
    first = path["steps"][0]
    asset = a[first["asset"]]
    if first.get("cve"):
        action = k[first["cve"]]["requiredAction"]
        fix = [f"{asset['product']} on {asset['asset_id']}: {action}"]
    else:
        fix = [f"Remove this misconfiguration on {asset['asset_id']}: {first['misconfig']}"]
    crown = a[path["target"]]["crown_jewel"]
    return {
        "title": f"Fix {asset['asset_id']} to close {path['id']}",
        "summary": path["title"],
        "why_it_matters": f"Path ends at {path['target']}.",
        "fix_point_asset": asset["asset_id"],
        "fix_steps": fix,
        "verify_steps": [f"Rerun validation of {path['id']}."],
        "exec_line": f"{path['title']} is open.",
        "route": "human_review" if crown else "assign",
        "route_reason": "crown-jewel target" if crown else "standard",
    }


def naive_ticket(path: dict) -> dict:
    t = template_ticket(path)
    t["fix_point_asset"] = path["target"] if any(s["asset"] == path["target"] for s in path["steps"]) else t["fix_point_asset"]
    t["route"] = "assign"
    t["route_reason"] = "auto-assigned"
    return t
