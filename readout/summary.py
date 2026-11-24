"""The weekly readout for the customer's security leadership, written by Claude from the metrics only.

A rule checks that every number in the summary is one the metrics contain, so the summary cannot
invent a count. If it fails, the readout falls back to a plain summary built from the same numbers.
"""
from __future__ import annotations

import json
import re
import time

from .agents import MODEL, PRICE

SYSTEM = """You write the weekly security readout for the chief information security officer of a large
electric utility during a four-week pilot of an attack-path validation platform.
You get the metrics for this readout as JSON. Write 3 to 5 sentences of plain prose, at most 110 words:
what was found, what was closed, what is still open and why, and the one decision or help you need from
leadership this week. Use only numbers that appear in the JSON, written as digits. No CVE IDs, no asset IDs,
no bullet points, no em dashes."""

NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\b")


def facts(m: dict) -> dict:
    open_rows = [r for r in m["rows"] if r["status"] != "closed"]
    return {
        "readout_day": m["day"], "paths_validated": m["validated"], "paths_closed": m["closed"],
        "paths_open": m["open"], "open_paths_reaching_crown_jewels": m["open_to_crown_jewels"],
        "median_days_from_validation_to_confirmed_close": m["median_days_to_close"],
        "slowest_close_days": m["max_days_to_close"],
        "tickets_acknowledged_within_2_days": m["acked_within_2_days"],
        "teams_with_tickets": m["teams_with_tickets"],
        "open_paths": [{"title": r["title"], "owner_team": r["owner_team"], "days_open": r["days_open"],
                        "status": r["status"], "hold_note": r["hold_note"]} for r in open_rows],
    }


def allowed_numbers(f: dict) -> set[str]:
    nums = set()

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            nums.add(str(int(x)) if float(x).is_integer() else str(x))
        elif isinstance(x, str):
            nums.update(NUM_RE.findall(x))
    walk(f)
    return nums


def check(text: str, f: dict) -> list[str]:
    problems = []
    bad = sorted(set(NUM_RE.findall(text)) - allowed_numbers(f) - {"2"}, key=float)
    if bad:
        problems.append("numbers not in the metrics: " + ", ".join(bad))
    if re.search(r"CVE-\d{4}", text, re.I):
        problems.append("names a CVE")
    if len(text.split()) > 130:
        problems.append("longer than 130 words")
    return problems


def plain(f: dict) -> str:
    s = (f"By day {f['readout_day']}, {f['paths_validated']} attack paths were validated and "
         f"{f['paths_closed']} were fixed and confirmed closed by a retest.")
    if f["paths_open"]:
        s += f" {f['paths_open']} remain open, {f['open_paths_reaching_crown_jewels']} of them reaching crown-jewel systems."
    return s


def claude_summary(m: dict, client=None) -> dict:
    import anthropic

    client = client or anthropic.Anthropic()
    f = facts(m)
    start = time.perf_counter()
    resp = client.beta.messages.create(
        model=MODEL, max_tokens=4000, system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(f, indent=1)}],
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
    )
    latency = time.perf_counter() - start
    p_in, p_out = PRICE.get(MODEL, (4.0, 20.0))
    meta = {"model": getattr(resp, "model", MODEL), "latency_s": round(latency, 2),
            "cost_usd": round((resp.usage.input_tokens * p_in + resp.usage.output_tokens * p_out) / 1e6, 5)}
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    problems = check(text, f) if resp.stop_reason != "refusal" else ["model declined"]
    return {"text": text if not problems else plain(f), "model_text": text, "problems": problems,
            "used": "claude" if not problems else "plain fallback", "_meta": meta}
