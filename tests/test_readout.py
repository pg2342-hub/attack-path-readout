import json
import unittest

from readout import agents, data, guardrails, metrics, summary
from readout.severity import severity


def good_ticket(path, **kw):
    t = agents.template_ticket(path)
    t["fix_steps"] = t["fix_steps"] + ["Record the change in the change log."]
    t.update(kw)
    return t


class DataTests(unittest.TestCase):
    def test_every_step_asset_exists(self):
        a = data.assets()
        for p in data.paths():
            self.assertIn(p["target"], a)
            for s in p["steps"]:
                self.assertIn(s["asset"], a, p["id"])

    def test_every_cve_is_in_kev_and_epss(self):
        k, e = data.kev(), data.epss()
        for p in data.paths():
            for c in data.path_cves(p):
                self.assertIn(c, k)
                self.assertIn(c, e)

    def test_every_step_has_a_cve_or_a_misconfiguration(self):
        for p in data.paths():
            for s in p["steps"]:
                self.assertTrue(s.get("cve") or s.get("misconfig"), p["id"])

    def test_context_hides_the_answer_key_and_timeline(self):
        ctx = json.dumps(data.context(data.paths()[0]))
        self.assertNotIn("timeline", ctx)
        self.assertNotIn("fix_terms", ctx)


class GuardrailTests(unittest.TestCase):
    def setUp(self):
        self.a = data.assets()
        self.p = {p["id"]: p for p in data.paths()}

    def test_clean_ticket_passes(self):
        t = good_ticket(self.p["P05"])
        self.assertEqual(guardrails.check(t, self.p["P05"], self.a), [])
        self.assertEqual(guardrails.apply(t, self.p["P05"], self.a)["final_route"], "assign")

    def test_crown_jewel_path_is_held_even_if_the_agent_assigns_it(self):
        t = good_ticket(self.p["P01"], route="assign")
        out = guardrails.apply(t, self.p["P01"], self.a)
        self.assertEqual(out["final_route"], "human_review")
        self.assertTrue(any("crown-jewel" in x for x in out["guardrail_problems"]))

    def test_cve_not_on_path_is_caught(self):
        t = good_ticket(self.p["P05"], summary="Also related to CVE-2021-44228.")
        self.assertTrue(any("CVE-2021-44228" in x for x in guardrails.check(t, self.p["P05"], self.a)))

    def test_attack_detail_is_caught(self):
        t = good_ticket(self.p["P09"], fix_steps=["Send ${jndi:ldap://x} to confirm", "Patch"])
        self.assertTrue(any("attack detail" in x for x in guardrails.check(t, self.p["P09"], self.a)))

    def test_fix_point_off_path_is_caught(self):
        t = good_ticket(self.p["P05"], fix_point_asset="dc-01")
        self.assertTrue(guardrails.check(t, self.p["P05"], self.a))

    def test_owner_comes_from_the_asset_list(self):
        out = guardrails.apply(good_ticket(self.p["P12"]), self.p["P12"], self.a)
        self.assertEqual(out["owner_team"], "OT Engineering")


class SeverityAndMetricsTests(unittest.TestCase):
    def test_crown_jewel_targets_are_critical(self):
        a = data.assets()
        for p in data.paths():
            if a[p["target"]]["crown_jewel"]:
                self.assertEqual(severity(p), "critical")

    def test_week1_only_counts_paths_validated_by_day_7(self):
        m = metrics.readout(7)
        self.assertEqual(m["validated"], 9)
        self.assertTrue(all(r["phase"] == "external" for r in m["rows"]))

    def test_week4_counts(self):
        m = metrics.readout(28)
        self.assertEqual((m["validated"], m["closed"], m["open"]), (12, 10, 2))
        self.assertEqual(m["open_to_crown_jewels"], 2)

    def test_failed_retest_keeps_the_path_open(self):
        p4 = next(p for p in data.paths() if p["id"] == "P04")
        self.assertEqual(metrics.status_at(p4, 12), "fix_failed_retest")
        self.assertEqual(metrics.status_at(p4, 28), "closed")


class SummaryTests(unittest.TestCase):
    def test_invented_number_is_caught(self):
        f = summary.facts(metrics.readout(28))
        self.assertTrue(summary.check("We closed 13 paths.", f))
        self.assertEqual(summary.check("We closed 10 of 12 paths.", f), [])
        self.assertEqual(summary.check("Median 6.0 days.", f), [])  # 6.0 is the metric 6

    def test_plain_fallback_uses_real_numbers(self):
        f = summary.facts(metrics.readout(28))
        self.assertEqual(summary.check(summary.plain(f), f), [])


class FakeClient:
    """Stands in for anthropic.Anthropic() so the Claude code path runs without a key."""

    def __init__(self, text, stop="end_turn"):
        self.text, self.stop = text, stop
        self.beta = self
        self.messages = self

    def create(self, **kw):
        self.kw = kw
        usage = type("U", (), {"input_tokens": 1000, "output_tokens": 300})()
        block = type("B", (), {"type": "text", "text": self.text})()
        return type("R", (), {"usage": usage, "content": [block], "stop_reason": self.stop, "model": "claude-opus-5-5"})()


class ClaudeAgentTests(unittest.TestCase):
    def test_parses_structured_output_and_records_cost(self):
        p = data.paths()[4]
        fake = FakeClient(json.dumps(good_ticket(p)))
        t = agents.claude_ticket(p, client=fake)
        self.assertEqual(t["fix_point_asset"], "mft-01")
        self.assertAlmostEqual(t["_meta"]["cost_usd"], 0.01)
        self.assertEqual(fake.kw["output_config"]["format"]["type"], "json_schema")

    def test_refusal_routes_to_a_person(self):
        t = agents.claude_ticket(data.paths()[0], client=FakeClient("", stop="refusal"))
        self.assertEqual(t["route"], "human_review")


if __name__ == "__main__":
    unittest.main()
