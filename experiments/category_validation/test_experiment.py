"""Deterministic policy checks only. No simulated Jev answers or network calls."""

import unittest

from experiments.category_validation.experiment import CASES, CATEGORIES, choice_question, gate, noul_question, redact, sdk_evidence


class ExperimentTests(unittest.TestCase):
    def test_thresholds_and_boundaries(self):
        for p, expected in [(0, "negative"), (.2, "negative"), (.2001, "uncertain"),
                            (.5, "uncertain"), (.7999, "uncertain"), (.8, "match"), (1, "match")]:
            with self.subTest(probability=p):
                self.assertEqual(gate(p), expected)
        for p in (-.1, 1.1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                gate(p)

    def test_shared_definitions_and_sdk_construction(self):
        self.assertEqual(len(CATEGORIES), 8)
        self.assertEqual(choice_question().criteria, CATEGORIES)
        self.assertEqual(noul_question().instructions["category_definitions"], CATEGORIES)
        self.assertEqual(sdk_evidence()["sdk_version"], "0.7.5")

    def test_cases_keep_ambiguous_descriptions(self):
        self.assertEqual([c["description"] for c in CASES],
                         ["iPhone", "iPad", "Garmin", "AirPods", "Premium Lifestyle Subscription"])
        self.assertTrue(all(set(c) == {"description", "selected_category", "hypothesis"} for c in CASES))

    def test_redaction_of_real_key_if_present(self):
        import os
        key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if key:
            self.assertEqual(redact({"body": [key]}), {"body": ["[REDACTED]"]})
        else:
            self.assertEqual(redact({"body": ["ordinary data"]}), {"body": ["ordinary data"]})


if __name__ == "__main__":
    unittest.main()
