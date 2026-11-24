"""Pilot metrics at a readout day: what is validated, fixed, still open, and how fast it moved."""
from __future__ import annotations

from statistics import median

from . import data
from .severity import severity


def status_at(path: dict, day: int) -> str:
    t = path["timeline"]
    if t["validated"] > day:
        return "not_yet_validated"
    closed = [d for d, r in t["retests"] if r == "closed" and d <= day]
    if closed:
        return "closed"
    if t.get("fixed") and t["fixed"] <= day:
        reopened = [d for d, r in t["retests"] if r == "open" and d <= day]
        return "fix_failed_retest" if reopened and not closed else "fixed_awaiting_retest"
    return "open"


def closed_day(path: dict) -> int | None:
    c = [d for d, r in path["timeline"]["retests"] if r == "closed"]
    return min(c) if c else None


def readout(day: int, tickets: dict[str, dict] | None = None) -> dict:
    a, k = data.assets(), data.kev()
    rows = []
    for p in data.paths():
        st = status_at(p, day)
        if st == "not_yet_validated":
            continue
        cd = closed_day(p)
        t = (tickets or {}).get(p["id"], {})
        rows.append({
            "id": p["id"], "title": p["title"], "phase": p["phase"], "target": p["target"],
            "target_name": a[p["target"]]["name"], "crown_jewel": a[p["target"]]["crown_jewel"],
            "severity": severity(p, a, k), "status": st,
            "owner_team": t.get("owner_team") or a[p["steps"][0]["asset"]]["owner_team"],
            "validated": p["timeline"]["validated"], "acknowledged": p["timeline"]["acknowledged"],
            "days_to_close": (cd - p["timeline"]["validated"]) if cd and cd <= day else None,
            "days_open": day - p["timeline"]["validated"] if st != "closed" else None,
            "acked_within_2_days": p["timeline"]["acknowledged"] - p["timeline"]["validated"] <= 2,
            "hold_note": p.get("hold_note") if st != "closed" else None,
        })
    closed = [r for r in rows if r["status"] == "closed"]
    open_ = [r for r in rows if r["status"] != "closed"]
    ttc = [r["days_to_close"] for r in closed]
    return {
        "day": day,
        "validated": len(rows),
        "closed": len(closed),
        "open": len(open_),
        "open_critical": sum(1 for r in open_ if r["severity"] == "critical"),
        "open_to_crown_jewels": sum(1 for r in open_ if r["crown_jewel"]),
        "median_days_to_close": median(ttc) if ttc else None,
        "max_days_to_close": max(ttc) if ttc else None,
        "acked_within_2_days": sum(1 for r in rows if r["acked_within_2_days"]),
        "teams_with_tickets": len({r["owner_team"] for r in rows}),
        "rows": rows,
    }
