"""Agents for golive-gate. Each takes a case input ({"path_id": ...}) and returns the ticket as written."""
import json
from collections import defaultdict
from pathlib import Path

from golive_gate import Response

from readout import agents, data

ROOT = Path(__file__).resolve().parents[1]
_paths = {p["id"]: p for p in data.paths()}
_calls = defaultdict(int)


def recorded(case_input):
    """Replays the recorded live Claude run: call n for a path reads runs/live/run<n>/tickets.json."""
    pid = case_input["path_id"]
    _calls[pid] += 1
    t = json.loads((ROOT / "runs" / "live" / f"run{_calls[pid]}" / "tickets.json").read_text())[pid]
    return Response(t, float(t.get("_meta", {}).get("cost_usd", 0.0)))


def template(case_input):
    return agents.template_ticket(_paths[case_input["path_id"]])


def naive(case_input):
    return agents.naive_ticket(_paths[case_input["path_id"]])
