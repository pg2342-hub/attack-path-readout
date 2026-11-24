"""Build eval/cases.json from data/paths.json and the answer key."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
paths = json.loads((ROOT / "data" / "paths.json").read_text())["paths"]
key = json.loads((ROOT / "eval" / "answer_key.json").read_text())["cases"]
cases = [{"id": p["id"], "title": p["title"],
          "group": "crown_jewel" if key[p["id"]]["route"] == "human_review" else "standard",
          "input": {"path_id": p["id"]}, "expected": key[p["id"]]} for p in paths]
(ROOT / "eval" / "cases.json").write_text(json.dumps({"cases": cases}, indent=1) + "\n")
print(len(cases), "cases")
