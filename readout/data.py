"""Load the sample estate, the validated attack paths and the public KEV and EPSS feeds."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def assets() -> dict[str, dict]:
    with open(DATA / "assets.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["crown_jewel"] = r["crown_jewel"] == "yes"
    return {r["asset_id"]: r for r in rows}


def pilot() -> dict:
    return json.loads((DATA / "paths.json").read_text())


def paths() -> list[dict]:
    return pilot()["paths"]


def kev() -> dict[str, dict]:
    return {v["cveID"]: v for v in json.loads((DATA / "kev_subset.json").read_text())["vulnerabilities"]}


def kev_meta() -> dict:
    d = json.loads((DATA / "kev_subset.json").read_text())
    return {"catalogVersion": d["catalogVersion"], "dateReleased": d["dateReleased"]}


def epss() -> dict[str, dict]:
    return json.loads((DATA / "epss.json").read_text())["scores"]


def path_cves(path: dict) -> list[str]:
    return [s["cve"] for s in path["steps"] if s.get("cve")]


def context(path: dict) -> dict:
    """Everything the agent may see about one path: the path, the assets on it, KEV and EPSS for its CVEs."""
    a, k, e = assets(), kev(), epss()
    ids = []
    for s in path["steps"]:
        if s["asset"] not in ids:
            ids.append(s["asset"])
    if path["target"] not in ids:
        ids.append(path["target"])
    return {
        "path": {key: path[key] for key in ("id", "title", "target", "steps", "evidence")},
        "assets": [a[i] for i in ids],
        "kev": [k[c] for c in path_cves(path)],
        "epss": {c: e[c] for c in path_cves(path)},
    }
