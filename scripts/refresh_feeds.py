"""Rebuild data/kev_subset.json and data/epss.json from the public feeds.

    python3 scripts/refresh_feeds.py                     # download both feeds
    python3 scripts/refresh_feeds.py --kev-file kev.json # use a KEV catalog already on disk

KEV comes from CISA's GitHub mirror of the Known Exploited Vulnerabilities catalog.
EPSS comes from FIRST's public API. Only the CVEs named in data/paths.json are kept.
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEV_URL = "https://raw.githubusercontent.com/cisagov/kev-data/main/known_exploited_vulnerabilities.json"
EPSS_URL = "https://api.first.org/data/v1/epss?cve="
KEEP = ("cveID", "vendorProject", "product", "vulnerabilityName", "dateAdded",
        "requiredAction", "knownRansomwareCampaignUse", "shortDescription")


def path_cves() -> list[str]:
    paths = json.loads((ROOT / "data" / "paths.json").read_text())["paths"]
    return sorted({s["cve"] for p in paths for s in p["steps"] if s.get("cve")})


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "attack-path-readout"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kev-file")
    ap.add_argument("--epss-file", help="a saved FIRST EPSS API response")
    args = ap.parse_args()
    cves = path_cves()
    kev = json.loads(Path(args.kev_file).read_text()) if args.kev_file else fetch(KEV_URL)
    by_id = {v["cveID"]: v for v in kev["vulnerabilities"]}
    missing = [c for c in cves if c not in by_id]
    if missing:
        raise SystemExit(f"not in the KEV catalog: {missing}")
    out = {"source": "CISA Known Exploited Vulnerabilities catalog", "url": KEV_URL,
           "catalogVersion": kev["catalogVersion"], "dateReleased": kev["dateReleased"],
           "vulnerabilities": [{k: by_id[c][k] for k in KEEP} for c in cves]}
    (ROOT / "data" / "kev_subset.json").write_text(json.dumps(out, indent=1) + "\n")
    epss = json.loads(Path(args.epss_file).read_text()) if args.epss_file else fetch(EPSS_URL + ",".join(cves))
    scores = {d["cve"]: {"epss": float(d["epss"]), "percentile": float(d["percentile"]), "date": d["date"]}
              for d in epss["data"]}
    (ROOT / "data" / "epss.json").write_text(json.dumps(
        {"source": "FIRST EPSS API", "url": EPSS_URL, "scores": scores}, indent=1, sort_keys=True) + "\n")
    print(f"kept {len(cves)} CVEs from KEV {kev['catalogVersion']}")


if __name__ == "__main__":
    main()
