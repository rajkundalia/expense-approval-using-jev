"""Offline tests. Mocked model calls stay in memory and are never saved as real results."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from experiments.policy_conditions_and_revisions import experiment as exp, analysis as a
from typesafe_sdk import ScoreAnswer, SystemOneResponse


class FinalExperimentTests(unittest.TestCase):
    def test_checkpoint_retries_only_local_replace(self):
        with tempfile.TemporaryDirectory(dir=exp.HERE) as folder:
            output=Path(folder)/"checkpoint.json"
            original_replace=Path.replace
            attempts=[]
            def transient_lock(path,target):
                attempts.append(str(path))
                if len(attempts)<3:
                    raise PermissionError("mocked temporary Windows file lock")
                return original_replace(path,target)
            with patch.object(Path,"replace",transient_lock),patch.object(exp.core,"sleep") as pause:
                exp.core.save(output,{"saved":True})
                self.assertEqual(pause.call_count,2)
            self.assertEqual(len(attempts),3)
            self.assertEqual(json.loads(output.read_text()),{"saved":True})

    def test_fixture_preconditions_splits_and_request_counts(self):
        fixtures, _ = exp.load_inputs()
        requests = [job for split in ("development", "heldout") for job in exp.jobs(fixtures, split)]
        self.assertEqual(len(requests), 159)
        self.assertEqual(sum(j[3] == "noul" for j in requests), 45)
        self.assertEqual(sum(j[3] == "choice" for j in requests), 48)
        self.assertEqual(sum(j[3] == "score" for j in requests), 66)
        self.assertFalse(any(c["id"] in {"PC-A08", "PC-B08"} for _, c, _, _ in requests))
        self.assertEqual({kind for _, c, _, kind in requests if c["id"] == "PC-A06"}, {"choice"})

    def test_request_isolation_and_actual_question_schemas(self):
        fixtures, reference = exp.load_inputs()
        for family, case, trial, kind in [j for split in ("development", "heldout") for j in exp.jobs(fixtures, split)]:
            state, qs = exp.request_for(case, kind, reference)
            self.assertEqual(len(qs), 1)
            self.assertFalse(set(state) & {"expected_level", "expected_evidence_state", "expected_j2", "applicable", "j2_result"})
            if kind == "score":
                self.assertEqual(len(next(iter(qs.values())).criteria), 3)
                self.assertEqual(set(state), {"policy_category", "invoice_item_description", "original_employee_explanation", "clarification_question", "revised_employee_explanation"})
            elif kind == "noul" and case["proposition"] == "charged_mobile_extra":
                self.assertNotIn("employee_justification", state)
            elif kind == "choice":
                self.assertEqual(next(iter(qs.values())).model_dump(mode="json"), reference["questions_by_policy"][case["policy_category"]])

    def test_fractional_score_parsing_does_not_round_or_fabricate(self):
        score = ScoreAnswer(score=1.37, confidence=.4, legend={0:"not",1:"partial",2:"resolved"}, probabilities={0:.1,1:.43,2:.47})
        response = SystemOneResponse(model=exp.MODEL, usage={"input_tokens":1,"output_tokens":1}, answers={"revision_resolution":score})
        answer = exp.parse_answer(response,"score")
        self.assertEqual(answer["score"],1.37)
        self.assertAlmostEqual(a.score_metrics(answer,2)["absolute_error"],.63)
        self.assertAlmostEqual(a.score_metrics(answer,2)["expected_level_probability"],.47)
        malformed = Mock(model=exp.MODEL, answers={})
        with self.assertRaises(ValueError):
            exp.parse_answer(malformed,"score")

    def test_mock_timeout_stays_failure_with_no_semantic_answer(self):
        fixtures, reference = exp.load_inputs()
        client = Mock()
        client.system_one.side_effect = TimeoutError("mocked unit-test timeout")
        case = fixtures["j3"]["cases"][0]
        obs = exp.collect(client,"j3",case,1,"noul",reference)
        self.assertEqual(obs["status"],"error")
        self.assertIsNone(obs["answer"])
        self.assertEqual(obs["call"]["error"]["type"],"TimeoutError")
        client.system_one.assert_called_once()

    def test_route_does_not_use_low_as_exclusion_or_ignore_scope(self):
        c={"j2_meaningful":True,"applicable":True,"proposition":"exceptional_commute"}
        self.assertEqual(a.j3_route(c,"SUPPORTED",.01,.7),"NEED_INFO")
        self.assertEqual(a.j3_route(c,"UNRELATED",.99,.7),"POLICY_RESTRICTION")
        self.assertEqual(a.j3_route({**c,"applicable":False},"SUPPORTED",None,None),"CONTINUE")
        self.assertEqual(a.j3_route(c,"SUPPORTED",None,.7,failed=True),"HUMAN_REVIEW")
        self.assertIsNone(a.j3_route(c,"SUPPORTED",None,.7))
        mobile={**c,"proposition":"charged_mobile_extra"}
        self.assertEqual(a.j3_route(mobile,"SUPPORTED",.9,.7),"RESTRICT_SEPARATE_COMPONENT")
        self.assertEqual(a.j3_route(mobile,"SUPPORTED",.01,.7,"conservative"),"NEED_INFO")
        self.assertEqual(a.revision_route(1.8,1.5),"CONTINUE")
        self.assertEqual(a.revision_route(.2,1.5),"HUMAN_REVIEW")

    def test_confidence_margin_and_auc_are_distinct(self):
        answer={"choice":"SUPPORTED","confidence":.35,"probabilities":{"SUPPORTED":.51,"UNCLEAR":.49,"UNRELATED":0,"INCONSISTENT":0}}
        metrics=a.choice_metrics(answer,"UNCLEAR")
        self.assertAlmostEqual(metrics["top_two_margin"],.02)
        self.assertNotEqual(metrics["confidence"],metrics["selected_probability"])
        self.assertEqual(a.auc([1,0],[True,False]),1)
        self.assertIsNone(a.auc([1,2],[False,False]))
        self.assertEqual(a.data_cutoffs([.2,.2])["cutoffs"],[])

    def test_preregistration_offline_resume_and_no_heldout_tuning(self):
        with tempfile.TemporaryDirectory(dir=exp.HERE) as folder:
            output=Path(folder).resolve()/"raw_results.json"
            self.assertIn(exp.HERE.resolve(),output.parents)
            data=exp.prepare(output)
            self.assertEqual(data,exp.prepare(output))
            self.assertFalse(data["observations"])
            self.assertIsNone(data["sensitivity_plan"])
            changed=copy.deepcopy(data)
            # Mocked analysis observations, only in memory: held-out values must not enter cutoff derivation.
            for case_id,value in [('RR-01',.1),('RR-02',.8),('RR-03',1.9)]:
                for trial in (1,2,3):
                    changed['observations'].append({'case_id':case_id,'trial':trial,'kind':'score','split':'development','status':'ok','answer':{'score':value}})
            derived=a.derive_sensitivity_plan(changed)
            self.assertEqual(len(derived['candidates']['score']['cutoffs']),2)
            heldout_changed=copy.deepcopy(changed)
            for trial in (1,2,3):
                heldout_changed['observations'].append({'case_id':'RR-04','trial':trial,'kind':'score','split':'heldout','status':'ok','answer':{'score':2.0}})
            self.assertEqual(derived,a.derive_sensitivity_plan(heldout_changed))
            changed=copy.deepcopy(data)
            for family in changed["preregistration"]["specification"]["fixtures"].values():
                for c in family["cases"]:
                    if c["split"]=='heldout': c['reason']='Held-out mutation must not affect development-only cutoffs.'
            self.assertEqual(a.derive_sensitivity_plan(data),a.derive_sensitivity_plan(changed))
            self.assertTrue(all(not c['cutoffs'] for c in a.derive_sensitivity_plan(data)['candidates'].values()))
            exp.write_artifacts(data,output,Path(folder)/'report.md')
            report=(Path(folder)/'report.md').read_text(encoding='utf-8')
            self.assertIn('No numerical routing cutoffs have been introduced',report)
            self.assertIn('0.43',report)
            frozen=json.loads((Path(folder)/'preregistered.json').read_text())
            frozen['specification']['model']='jev-latest'
            (Path(folder)/'preregistered.json').write_text(json.dumps(frozen),encoding='utf-8')
            with self.assertRaises(ValueError): exp.read_saved(output)


if __name__=='__main__':
    unittest.main()
