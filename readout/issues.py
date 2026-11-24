"""Open each assignable ticket as a GitHub issue, labelled by owning team; human-review tickets get a review label.

Runs in the record workflow with the workflow's GITHUB_TOKEN. Issues stand in for the customer's ticket queue.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

API = "https://api.github.com"


def _call(method: str, url: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None, headers={
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json",
        "User-Agent": "attack-path-readout"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")


def body(t: dict) -> str:
    lines = [t.get("summary", ""), "", f"**Why it matters.** {t.get('why_it_matters', '')}", "",
             f"**Fix point:** `{t.get('fix_point_asset')}` (owner: {t.get('owner_team')})", "", "**Fix steps**"]
    lines += [f"{i}. {s}" for i, s in enumerate(t.get("fix_steps", []), 1)]
    lines += ["", "**Verify**"] + [f"- {s}" for s in t.get("verify_steps", [])]
    if t.get("guardrail_problems"):
        lines += ["", "**Held for review:** " + "; ".join(t["guardrail_problems"])]
    lines += ["", "_Drafted by the attack-path-readout agent from a synthetic validation run. Not a real finding._"]
    return "\n".join(lines)


def ensure_label(repo: str, name: str) -> None:
    try:
        _call("POST", f"{API}/repos/{repo}/labels", {"name": name, "color": "ededed"})
    except urllib.error.HTTPError as e:
        if e.code != 422:  # 422 = already exists
            raise


def open_issues(tickets: dict[str, dict], repo: str) -> dict[str, str]:
    existing = {i["title"]: i["html_url"] for i in _call("GET", f"{API}/repos/{repo}/issues?state=all&per_page=100")}
    urls = {}
    for pid, t in sorted(tickets.items()):
        title = f"[{pid}] {t.get('title', '')}"
        if title in existing:
            urls[pid] = existing[title]
            continue
        labels = ["needs-review" if t["final_route"] == "human_review" else "assigned",
                  "team: " + (t.get("owner_team") or "unknown")]
        for name in labels:
            ensure_label(repo, name)
        urls[pid] = _call("POST", f"{API}/repos/{repo}/issues",
                          {"title": title, "body": body(t), "labels": labels})["html_url"]
    return urls


if __name__ == "__main__":
    import sys
    from pathlib import Path
    run_dir, repo = Path(sys.argv[1]), sys.argv[2]
    tickets = json.loads((run_dir / "tickets.json").read_text())
    urls = open_issues(tickets, repo)
    (run_dir / "issues.json").write_text(json.dumps(urls, indent=1) + "\n")
    print(f"{len(urls)} issues")
