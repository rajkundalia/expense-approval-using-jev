"""Offline policy/scoring checks, with no fabricated or mocked Jev responses."""
import unittest

from experiments.category_validation import experiment as core
from experiments.category_validation.experiment_v2 import load_plan, score


class V2Tests(unittest.TestCase):
    def test_preregistered_coverage(self):
        plan = load_plan()
        cases = {c["id"]: c for c in plan["cases"]}
        self.assertEqual(cases["C04"]["expected_category"], "WELLNESS")
        self.assertEqual(cases["C05"]["expected_category"], "WELLNESS")
        self.assertEqual(cases["C12"]["expected_category"], "MOBILE_BILL")
        self.assertEqual(cases["C13"]["expected_category"], "MIXED_ITEMS")
        self.assertEqual(cases["C14"]["expected_category"], "MIXED_ITEMS")
        self.assertEqual(cases["C15"]["expected_category"], "MOBILE_BILL")
        self.assertEqual(plan["trials_per_case"], 3)

    def test_real_sdk_questions_use_v2_definitions(self):
        categories = load_plan()["category_definitions"]
        self.assertEqual(core.choice_question(categories).criteria, categories)
        self.assertEqual(core.noul_question(categories).instructions["category_definitions"], categories)
        self.assertNotIn("expected_category", core.choice_question(categories).model_dump_json())

    def test_scoring_predicates_without_model(self):
        # These are deterministic scoring truth tables, not simulated SDK results.
        def decision(label, gate=None):
            return {"status": "ok", "category": label, "gate": gate}
        false_accept = score("OTHER", "SMARTPHONE", decision("SMARTPHONE", "match"))
        self.assertTrue(false_accept["false_category_acceptance"])
        self.assertTrue(false_accept["noul_gate_false_acceptance"])
        self.assertFalse(false_accept["incorrect_category_suggestion"])
        wrong_suggestion = score("MOBILE_BILL", "BROADBAND", decision("OTHER"))
        self.assertTrue(wrong_suggestion["incorrect_category_suggestion"])
        clarify = score("MIXED_ITEMS", "SMARTPHONE", decision("INSUFFICIENT_INFORMATION"))
        self.assertTrue(clarify["unnecessary_clarification"])
        self.assertFalse(clarify["incorrect_category_suggestion"])
        correct_missing = score("INSUFFICIENT_INFORMATION", "WELLNESS", decision("INSUFFICIENT_INFORMATION"))
        self.assertFalse(correct_missing["unnecessary_clarification"])
        self.assertIsNone(score("WELLNESS", "WELLNESS", {"status": "error"}))


if __name__ == "__main__":
    unittest.main()
