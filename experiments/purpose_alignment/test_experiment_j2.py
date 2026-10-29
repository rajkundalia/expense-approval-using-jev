"""Offline J2 checks: no network calls, simulated SDK responses or model outputs."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE_PATH = Path(__file__).with_name("experiment_j2.py")
SPEC = importlib.util.spec_from_file_location("experiment_j2", MODULE_PATH)
j2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(j2)


class PurposeAlignmentTests(unittest.TestCase):
    def test_dataset_coverage_and_separate_j1_probes(self):
        dataset = j2.load_dataset()
        self.assertEqual(len(dataset["cases"]), 32)
        primary = [c for c in dataset["cases"] if c["evaluation_group"] == "primary"]
        self.assertEqual(len(primary), 29)
        self.assertEqual({c["expected_outcome"] for c in primary}, set(j2.LABELS))
        self.assertEqual({c["id"] for c in dataset["cases"] if c["evaluation_group"] != "primary"},
                         {"J2-07", "J2-08", "J2-18"})
        self.assertEqual(len({c["coverage_tag"] for c in dataset["cases"]}), 32)

    def test_input_whitelist_prevents_label_and_budget_leakage(self):
        case = copy.deepcopy(j2.load_dataset()["cases"][0])
        case.update(budget_balance=1000, claim_amount=500, j1_classification="WELLNESS", previous_probability=.9)
        state = j2.state_for(case)
        self.assertEqual(set(state), set(j2.STATE_FIELDS))
        self.assertEqual(state["employee_justification"], case["employee_justification"])
        self.assertNotIn("expected_outcome", state)

    def test_real_choice_constructor_four_labels_only_applicable_policy(self):
        dataset = j2.load_dataset()
        for category in dataset["policies"]:
            question = j2.question_for(dataset, category)
            self.assertIsInstance(question, j2.core.Choice)
            self.assertEqual(set(question.criteria), set(j2.LABELS))
            self.assertEqual(question.instructions["applicable_policy"], dataset["policies"][category])
            self.assertNotIn("policy_limits_not_evaluated", question.model_dump_json())
            self.assertNotIn("expected_outcome", question.model_dump_json())
        self.assertEqual(j2.MODEL, "typesafe/jev-1.14-20261014")

    def test_confusion_orientation_and_no_failure_labels(self):
        # A pure label-counting truth table, not a fabricated inference response.
        matrix = j2.confusion_counts([
            ("UNRELATED", "SUPPORTED"), ("UNCLEAR", "UNRELATED"),
            ("UNRELATED", "UNCLEAR"), ("INCONSISTENT", "UNCLEAR"),
            ("UNCLEAR", "INCONSISTENT"), ("SUPPORTED", "SUPPORTED")])
        self.assertEqual(matrix["UNRELATED"]["SUPPORTED"], 1)
        self.assertEqual(matrix["SUPPORTED"]["UNRELATED"], 0)
        self.assertEqual(matrix["INCONSISTENT"]["UNCLEAR"], 1)
        with self.assertRaises(ValueError):
            j2.confusion_counts([("SUPPORTED", "error")])

    def test_prepare_is_offline_idempotent_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "j2_comparison.json"
            data = j2.prepare(output)
            frozen_path = output.parent / "j2_preregistered.json"
            frozen_bytes = frozen_path.read_bytes()
            self.assertEqual(data["status"], "prepared")
            self.assertFalse(data["observations"])
            self.assertFalse(data["preflights"])
            self.assertEqual(j2.prepare(output), data)
            self.assertEqual(frozen_path.read_bytes(), frozen_bytes)
            self.assertEqual(j2.metrics(data, "primary")["planned"], 87)
            self.assertIsNone(j2.metrics(data, "primary")["false_supported"])
            self.assertIsNone(j2.repeatability(data, "J2-01")["all_three_labels_agree"])
            report = Path(folder) / "report.md"
            j2.write_report(data, report)
            text = report.read_text(encoding="utf-8")
            self.assertIn("No semantic outcomes have been measured", text)
            self.assertIn("No evidence-based sufficiency recommendation", text)
            frozen = json.loads(frozen_bytes)
            frozen["specification"]["dataset"]["cases"][0]["expected_outcome"] = "UNRELATED"
            frozen_path.write_text(json.dumps(frozen), encoding="utf-8")
            with self.assertRaises(ValueError):
                j2.prepare(output)


if __name__ == "__main__":
    unittest.main()
