"""Severity is decided by rules, not by the model, so the same path always gets the same rating."""
from __future__ import annotations

from . import data


def severity(path: dict, assets: dict | None = None, kev: dict | None = None) -> str:
    assets = assets or data.assets()
    kev = kev or data.kev()
    target = assets[path["target"]]
    entry = assets[path["steps"][0]["asset"]]
    ransomware = any(kev[c]["knownRansomwareCampaignUse"] == "Known" for c in data.path_cves(path))
    if target["crown_jewel"]:
        return "critical"
    if entry["zone"] == "internet" and ransomware:
        return "high"
    return "medium"
