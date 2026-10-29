"""Deterministic offline tests; no simulated inference or network calls."""
import copy
import inspect
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from experiments.evidence_quality import experiment_j3_j4 as eq
from experiments.evidence_quality import routing_analysis as ra


class EvidenceQualityTests(unittest.TestCase):
    def test_historical_source_truth_and_case_isolation(self):
        source, frozen, dev, heldout = eq.load_inputs()
        self.assertEqual(len(source["observations"]), 96)
        primary = [o for o in source["observations"] if o["evaluation_group"] == "primary"]
        self.assertEqual(sum(o["outcome"] == o["expected_outcome"] for o in primary), 84)
        self.assertEqual({o["case_id"] for o in primary if o["outcome"] != o["expected_outcome"]}, {"J2-30"})
        original = frozen["specification"]["dataset"]["cases"]
        for old, new in zip(original, dev["cases"]):
            self.assertEqual(old, {key: new[key] for key in old})
        for c in dev["cases"] + heldout["cases"]:
            self.assertEqual(set(eq.j2.state_for(c)), set(eq.j2.STATE_FIELDS))
        self.assertEqual(len(heldout["cases"]), 20)
        self.assertTrue({c["id"] for c in dev["cases"]}.isdisjoint({c["id"] for c in heldout["cases"]}))

    def test_actual_sdk_mixed_question_construction_and_fractional_schema(self):
        spec, _ = eq.build_spec()
        for cat, policy in spec["policies"].items():
            questions = eq.signal_questions(policy, cat)
            self.assertEqual({q.type for q in questions.values()}, {"noul", "score"})
            self.assertEqual(len(questions["explanation_sufficiency"].criteria), 3)
            self.assertEqual(questions["essential_purpose"].instructions["applicable_policy"], policy)
            for q in questions.values():
                payload = q.model_dump_json()
                for forbidden in ("expected_j3", "expected_j4", "expected_outcome", "budget_balance", "j2_result"):
                    self.assertNotIn(forbidden, payload)
            inspect.signature(eq.core.TypeSafeClient.system_one).bind(None, state={"employee_justification": "test evidence"}, questions=questions, model=eq.MODEL)
        fields = eq.ScoreAnswer.model_fields
        self.assertEqual(fields["score"].annotation, float)
        self.assertTrue({"legend", "probabilities", "confidence"}.issubset(fields))

    def test_routing_truth_table_and_invariant_nonoverrides(self):
        rule = ra.CANDIDATES[0]
        for config in ra.CONFIGS:
            self.assertEqual(ra.route("UNRELATED", 1, 2, config, rule), "EXCLUDED_PURPOSE")
            self.assertEqual(ra.route("INCONSISTENT", 1, 2, config, rule), "REVIEW")
            self.assertEqual(ra.route("UNCLEAR", 1, 2, config, rule), "CLARIFY")
        self.assertEqual(ra.route("SUPPORTED", .8, 1.5, "D", rule), "CONTINUE")
        self.assertEqual(ra.route("SUPPORTED", .799, 2, "B", rule), "CLARIFY")
        self.assertEqual(ra.route("SUPPORTED", .1, 2, "D", rule), "REVIEW")
        self.assertEqual(ra.route("SUPPORTED", 1, 1.499, "C", rule), "CLARIFY")
        # Sufficient excluded purposes stay excluded even with high sufficiency.
        self.assertEqual(ra.route("UNRELATED", .01, 1.99, "C", rule), "EXCLUDED_PURPOSE")

    def test_failures_are_not_semantic_decisions(self):
        rule = ra.CANDIDATES[0]
        self.assertEqual(ra.route(None, None, None, "A", rule, failed=True), "API_FAILURE")
        self.assertEqual(ra.route("SUPPORTED", None, 2, "D", rule, failed=True), "API_FAILURE")
        self.assertEqual(ra.route("SUPPORTED", None, 2, "D", rule), "NOT_MEASURED")
        self.assertEqual(ra.route("SUPPORTED", None, None, "A", rule, failed=True), "CONTINUE")
        self.assertEqual(ra.j3_region(.3), "AMBIGUOUS")
        self.assertEqual(ra.j3_region(.7), "HIGH")
        self.assertEqual(ra.j4_region(.5), 1)
        self.assertEqual(ra.j4_region(1.5), 2)

    def test_pure_counting_common_pairs_and_distinct_cases(self):
        # Offline decision-table rows; these are not fabricated SDK responses.
        row = {"case_id": "counting-example", "trial": 1, "expected_j2": "UNCLEAR", "j2": "SUPPORTED",
               "routes": {"A": "CONTINUE", "B": "CLARIFY", "C": "CONTINUE", "D": "CLARIFY"}}
        pair = {**row, "trial": 2}
        rows = [row, pair]
        self.assertEqual(ra.summarize(rows, "A")["false_continue_trials"], 2)
        self.assertEqual(ra.summarize(rows, "A")["false_continue_cases"], ["counting-example"])
        self.assertEqual(ra.utility(rows)["counts"]["noul_catches_false_support"], 2)
        failed = {**row, "routes": {**row["routes"], "D": "API_FAILURE"}}
        self.assertEqual(ra.utility([failed])["common_evaluable_trials"], 0)

    def test_preregistration_resume_and_no_heldout_selection_leak(self):
        with tempfile.TemporaryDirectory(dir=eq.HERE) as folder:
            output = Path(folder).resolve() / "raw_results.json"
            self.assertIn(eq.HERE.resolve(), output.parents)
            data = eq.prepare(output)
            before = (output.parent / "preregistered.json").read_bytes()
            self.assertEqual(eq.prepare(output), data)
            self.assertEqual((output.parent / "preregistered.json").read_bytes(), before)
            self.assertFalse(data["observations"])
            original_selection = ra.select_rule(data)
            changed = copy.deepcopy(data)
            for case in changed["preregistration"]["specification"]["heldout"]["cases"]:
                case["expected_outcome"] = "UNRELATED"
            self.assertEqual(ra.select_rule(changed), original_selection)
            self.assertEqual(original_selection["rule"], ra.CANDIDATES[0])
            self.assertIn("fallback", original_selection["basis"])
            # Generate the entire unmeasured report without a client/key.
            eq.write_artifacts(data, output, output.parent / "report.md")
            self.assertIn("Not yet established", (output.parent / "report.md").read_text(encoding="utf-8"))
            edited = json.loads((output.parent / "preregistered.json").read_text())
            edited["specification"]["model"] = "jev-latest"
            (output.parent / "preregistered.json").write_text(json.dumps(edited), encoding="utf-8")
            with self.assertRaises(ValueError):
                eq.read_saved(output)


if __name__ == "__main__":
    unittest.main()
