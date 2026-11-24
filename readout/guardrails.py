"""Rules every ticket must pass before it is assigned to a team.

The model writes the ticket. These rules decide whether it can go out on its own:
a ticket that breaks one is routed to a person with the reason, never dropped.
"""
from __future__ import annotations

import re

CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.I)
# Anything that reads like attack tooling or a command line. Tickets describe fixes, not attacks.
EXPLOIT_RE = re.compile(
    r"(\bcurl\s|\bwget\s|powershell|cmd\.exe|/bin/(ba)?sh|\bbash\s+-c|\bnc\s+-|\bnetcat\b|"
    r"\bpayload\b|proof[- ]of[- ]concept|\bPoC\b|exploit code|msfconsole|metasploit|\$\{jndi:|"
    r"mimikatz|reverse shell|\.\./\.\./)", re.I)
REQUIRED = ("title", "summary", "why_it_matters", "fix_point_asset", "fix_steps", "verify_steps", "exec_line", "route")


def ticket_text(t: dict) -> str:
    parts = [str(t.get(k, "")) for k in ("title", "summary", "why_it_matters", "exec_line", "route_reason")]
    parts += [str(x) for x in t.get("fix_steps", []) + t.get("verify_steps", [])]
    return "\n".join(parts)


def check(ticket: dict, path: dict, assets: dict) -> list[str]:
    """Return the list of broken rules (empty when the ticket may be assigned as written)."""
    problems = []
    missing = [k for k in REQUIRED if not ticket.get(k)]
    if missing:
        problems.append("missing fields: " + ", ".join(missing))
    on_path = [s["asset"] for s in path["steps"]]
    fp = ticket.get("fix_point_asset")
    if fp not in on_path:
        problems.append(f"fix point {fp!r} is not a step on this path")
    elif fp not in assets:
        problems.append(f"fix point {fp!r} has no owner in the asset list")
    allowed = {s["cve"].upper() for s in path["steps"] if s.get("cve")}
    named = {m.upper() for m in CVE_RE.findall(ticket_text(ticket))}
    if named - allowed:
        problems.append("names a CVE that is not on this path: " + ", ".join(sorted(named - allowed)))
    hit = EXPLOIT_RE.search(ticket_text(ticket))
    if hit:
        problems.append(f"contains attack detail ({hit.group(0)!r}); tickets describe fixes only")
    if assets[path["target"]]["crown_jewel"] and ticket.get("route") != "human_review":
        problems.append("path ends at a crown-jewel asset, so a person must review it before assignment")
    return problems


def apply(ticket: dict, path: dict, assets: dict) -> dict:
    """Attach the rule results and the final routing. The model's text is kept as written."""
    problems = check(ticket, path, assets)
    out = dict(ticket)
    out["guardrail_problems"] = problems
    out["final_route"] = "human_review" if problems or ticket.get("route") == "human_review" else "assign"
    fp = ticket.get("fix_point_asset")
    out["owner_team"] = assets[fp]["owner_team"] if fp in assets else None
    return out
