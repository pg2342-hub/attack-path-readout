"""The rule checks plus one LLM judge check, for runs that have an API key (the record workflow)."""
import json

from golive_gate import ClaudeJudge, judge_check

from checks import checks as rule_checks

checks = rule_checks.without()  # a copy we can add to

FIELDS = ("title", "summary", "why_it_matters", "fix_point_asset", "fix_steps", "verify_steps")

checks.add(judge_check(
    "actionable",
    "The owning team could act on this ticket without opening another document: it says which asset and "
    "product to change, the fix steps are concrete and in order (interim exposure cuts before patching), and "
    "it explains in plain words why the path matters to the business. The asset inventory has no version "
    "numbers, so one pointer to the vendor's fixed release for the named CVEs is expected and is not a fault; "
    "any other reliance on outside documents is.",
    judge=ClaudeJudge(),
    render_output=lambda out: json.dumps({k: out.get(k) for k in FIELDS}, indent=1),
))
