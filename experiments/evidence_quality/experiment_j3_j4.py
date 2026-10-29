"""J3 Noul + J4 Score experiment; run inference only when invoked without offline flags."""
from __future__ import annotations

import argparse
import hashlib
import inspect
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import sys
from typesafe_sdk import Score, ScoreAnswer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from experiments.category_validation import experiment as core
from experiments.purpose_alignment import experiment_j2 as j2
from experiments.evidence_quality import routing_analysis as analysis

SOURCE = ROOT / "experiments/purpose_alignment/results/j2_comparison.json"
FROZEN_SOURCE = SOURCE.with_name("j2_preregistered.json")
MODEL = core.MODEL_SNAPSHOT
RUBRIC = [
    "No usable purpose information. The explanation does not meaningfully identify why this item/service was purchased, such as 'Needed it'. Do not infer a reason from product identity alone.",
    "Partial purpose information. Relevant context is supplied but an essential purpose detail remains unresolved, such as an event with colleagues whose business purpose is not established.",
    "Sufficient purpose information. The explanation identifies its purpose clearly enough to assess it under the applicable policy, whether qualifying, excluded or materially inconsistent with the invoice. Concise explanations can suffice. Ordinary daily commuting is sufficiently clear even though excluded."
]
PROPOSITIONS = {
    "WELLNESS": "The explanation explicitly establishes the employee's own fitness or wellbeing purpose for the invoiced purchase, without assuming unstated use or disregarding an explicit contradiction in the purchased service.",
    "SMARTPHONE": "The explanation explicitly establishes purchase of this smartphone for the employee's own use, without contrary facts or an invented professional-use requirement.",
    "BROADBAND": "The explanation explicitly establishes home fixed-internet connectivity as the purpose of this service, without requiring professional use or proof of hours worked at home.",
    "MOBILE_BILL": "The explanation explicitly establishes cellular voice or mobile-data use for this service; a complimentary included streaming benefit does not negate it, while a separate entertainment subscription does not establish cellular use.",
    "BUSINESS_HOTEL": "The explanation explicitly establishes work-related travel requiring this temporary accommodation, such as client visits, internal training, workshops or offsites, without assuming business purpose from location or an overnight stay alone.",
    "BUSINESS_TRANSPORT": "The explanation explicitly establishes a specific work-related purpose for this journey, including exceptional travel for an identifiable business requirement; ordinary daily commuting and colleague attendance alone do not establish that purpose."
}
J3_TASK = (
    "Evaluate the affirmative proposition from the original evidence and applicable fixed policy. "
    "Explicitly established means reasonably understandable from the employee's words, not lengthy or formal terminology. "
    "Do not fill in missing purpose from the product, a colleague's attendance, or an event location. "
    "Bind the explanation to the identified purchase without redoing J1 category classification. "
    "This tests provided evidence, not employee truthfulness. Do not demand external proof, infer gender from sizing, "
    "calculate amounts, or use any other question's answer."
)
J4_TASK = (
    "How sufficiently informative is the employee explanation to assess its stated purpose under the applicable policy? "
    "Use the three ordered descriptions below. Measure purpose-information sufficiency, not policy eligibility, "
    "reimbursement correctness, fraud, honesty, writing quality, explanation length, or another judgment's accuracy. "
    "An explicitly excluded purpose or identifiable item-purpose contradiction can be sufficiently informative. "
    "A brief own-phone-use or home-connectivity explanation can suffice without a business-use requirement. "
    "Do not invent missing facts, require external documents, or use another question's answer."
)


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    original = json.loads(FROZEN_SOURCE.read_text(encoding="utf-8"))
    if source["status"] != "complete" or source["preregistration"] != original:
        raise ValueError("A complete, consistent historical J2 source is required.")
    if j2.sha(original["specification"]) != source["specification_sha256"]:
        raise ValueError("Historical J2 preregistration hash is invalid.")
    dev = json.loads((HERE / "j3_j4_dev_cases.json").read_text(encoding="utf-8"))
    heldout = json.loads((HERE / "j3_j4_heldout_cases.json").read_text(encoding="utf-8"))
    if dev["source_j2_sha256"] != file_sha(SOURCE) or dev["source_preregistration_sha256"] != file_sha(FROZEN_SOURCE):
        raise ValueError("Historical J2 source differs from the development annotations.")
    old_cases = original["specification"]["dataset"]["cases"]
    if len(dev["cases"]) != 32 or len(heldout["cases"]) != 20:
        raise ValueError("Expected 32 development and 20 held-out cases.")
    for before, after in zip(old_cases, dev["cases"]):
        if any(after.get(key) != value for key, value in before.items()):
            raise ValueError("Historical J2 case or expected outcome was altered.")
    seen = set()
    evidence_seen = set()
    for case in dev["cases"] + heldout["cases"]:
        evidence = tuple(j2.state_for(case).values())
        if case["id"] in seen or evidence in evidence_seen:
            raise ValueError("Duplicate case ID or original evidence.")
        seen.add(case["id"])
        evidence_seen.add(evidence)
        if case["expected_j3_region"] not in {"HIGH", "LOW", "AMBIGUOUS"} or case["expected_j4_level"] not in (0, 1, 2):
            raise ValueError("Invalid qualitative or sufficiency hypothesis.")
    return source, original, dev, heldout


def signal_questions(policy, category):
    context = {"applicable_policy_category": category, "applicable_policy": policy}
    return {
        "essential_purpose": core.Noul(instructions={**context, "task": J3_TASK, "proposition": PROPOSITIONS[category]}),
        "explanation_sufficiency": Score(instructions={**context, "question": J4_TASK}, criteria=RUBRIC)
    }


def sdk_evidence():
    if version("typesafe-sdk") != "0.7.5":
        raise ValueError("This preregistration requires typesafe-sdk==0.7.5.")
    return {"version": version("typesafe-sdk"), "python": sys.version.split()[0],
            "signatures": {name: str(inspect.signature(obj)) for name, obj in {
                "Score": Score, "Noul": core.Noul, "system_one": core.TypeSafeClient.system_one}.items()},
            "score_schema": Score.model_json_schema(),
            "score_answer_schema": ScoreAnswer.model_json_schema()}


def build_spec():
    source, original, dev, heldout = load_inputs()
    policies = original["specification"]["dataset"]["policies"]
    spec = {"model": MODEL, "gateway": core.BASE_URL, "sdk": sdk_evidence(), "trials": 3,
            "development": dev, "heldout": heldout, "policies": policies,
            "policy_limits_not_evaluated": original["specification"]["dataset"]["policy_limits_not_evaluated"],
            "historical_source_sha256": file_sha(SOURCE), "historical_preregistration_sha256": file_sha(FROZEN_SOURCE),
            "j2_questions": original["specification"]["questions_by_policy"],
            "signal_questions": {cat: {name: q.model_dump(mode="json") for name, q in signal_questions(policies[cat], cat).items()} for cat in policies},
            "candidates": analysis.CANDIDATES,
            "selection_protocol": analysis.SELECTION_PROTOCOL,
            "expectation_regions": {"j3": "LOW: p < 0.3; AMBIGUOUS: 0.3 <= p < 0.7; HIGH: p >= 0.7. Qualitative development hypotheses, not calibrated correctness or exact expected probabilities.",
                                    "j4": "Conceptual nearest-anchor regions: [0,0.5) -> 0, [0.5,1.5) -> 1, [1.5,2] -> 2. Raw fractional score is always retained; region assignment is Python analysis, not an SDK integer output."},
            "batching": "One request with independent Noul/Score instructions and original state. Held-out J2 is a separate request with the exact historical question. No prior answers enter any request.",
            "max_retries": 0, "timeout_seconds": 30}
    return spec, source["observations"]


def prepare(output):
    spec, historical = build_spec()
    frozen_path = output.parent / "preregistered.json"
    if output.exists():
        data = read_saved(output)
        if data["specification_sha256"] != j2.sha(spec):
            raise ValueError("Specification changed after freezing. Preserve this run; use a new output directory for a separately registered experiment.")
        return data
    if frozen_path.exists():
        raise ValueError("Preregistration already exists without raw results; do not overwrite it.")
    frozen = {"created_at": j2.timestamp(), "specification": spec}
    core.save(frozen_path, frozen)
    data = {"status": "prepared", "preregistration": frozen, "specification_sha256": j2.sha(spec),
            "historical_j2": historical, "observations": [], "selected_rule": None,
            "preflights": [], "execution_errors": [], "pending_request": None}
    core.save(output, data)
    return data


def read_saved(output):
    data = json.loads(output.read_text(encoding="utf-8"))
    frozen = json.loads((output.parent / "preregistered.json").read_text(encoding="utf-8"))
    if frozen != data["preregistration"] or j2.sha(frozen["specification"]) != data["specification_sha256"]:
        raise ValueError("Preregistration integrity check failed.")
    if file_sha(SOURCE) != frozen["specification"]["historical_source_sha256"] or file_sha(FROZEN_SOURCE) != frozen["specification"]["historical_preregistration_sha256"]:
        raise ValueError("Historical J2 input files changed.")
    if j2.sha(data["historical_j2"]) != j2.sha(json.loads(SOURCE.read_text(encoding="utf-8"))["observations"]):
        raise ValueError("Historical J2 baseline snapshot no longer matches its source.")
    if data["selected_rule"]:
        rule_path = output.parent / "routing_rule.json"
        if json.loads(rule_path.read_text(encoding="utf-8")) != data["selected_rule"]:
            raise ValueError("Frozen routing rule does not match raw results.")
        chosen = data["selected_rule"]
        expected = analysis.select_rule(data)
        if any(chosen[key] != value for key, value in expected.items()):
            raise ValueError("Frozen rule differs from the preregistered development-only selection.")
        if chosen["specification_sha256"] != data["specification_sha256"]:
            raise ValueError("Routing rule belongs to a different specification.")
        if any(o["split"] == "heldout" and o["call"]["started_at"] < chosen["frozen_at"] for o in data["observations"]):
            raise ValueError("Held-out request predates routing-rule freeze.")
    elif any(o["split"] == "heldout" for o in data["observations"]):
        raise ValueError("Held-out observations exist without a frozen routing rule.")
    return data


def validate_signal(name, answer):
    if name == "j3":
        value = answer.noul
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Noul probability outside [0,1].")
    else:
        if not math.isfinite(answer.score) or not 0 <= answer.score <= 2:
            raise ValueError("Score outside the registered 0-2 rubric.")
        if set(answer.probabilities) != {0, 1, 2} or set(answer.legend) != {0, 1, 2}:
            raise ValueError("Score must describe all three rubric levels.")
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in [answer.confidence, *answer.probabilities.values()]):
            raise ValueError("Score confidence/probabilities outside [0,1].")
    return {"status": "ok", "answer": answer.model_dump(mode="json"), "error": None}


def collect(client, spec, case, trial, split, kind):
    state = j2.state_for(case)
    category = case["policy_category"]
    if kind == "signals":
        questions = signal_questions(spec["policies"][category], category)
    else:
        questions = {"purpose_alignment": core.Choice(**spec["j2_questions"][category])}
    response, call = core.invoke("system_one", {"model": MODEL, "state": state,
        "questions": {name: q.model_dump(mode="json") for name, q in questions.items()}},
        lambda: client.system_one(state=state, questions=questions, model=MODEL))
    observation = {"case_id": case["id"], "trial": trial, "split": split, "kind": kind, "call": call, "outputs": {}}
    roles = ("j3", "j4") if kind == "signals" else ("j2",)
    for role in roles:
        try:
            if response is None:
                observation["outputs"][role] = {"status": "error", "answer": None, "error": call["error"]}
                continue
            if response.model != MODEL:
                raise ValueError("Response model is not the exact registered snapshot.")
            if role == "j2":
                answer = j2.validate_answer(response.choices["purpose_alignment"])
                result = {"status": "ok", "answer": answer, "error": None}
            else:
                answer = response.nouls["essential_purpose"] if role == "j3" else response.scores["explanation_sufficiency"]
                result = validate_signal(role, answer)
            observation["outputs"][role] = result
        except Exception as error:
            observation["outputs"][role] = {"status": "error", "answer": None, "error": core.error_record(error)}
    return observation


def write_artifacts(data, output, report):
    comparison = analysis.compare(data)
    core.save(output.parent / "routing_comparison.json", comparison)
    analysis.write_report(core.redact(data), core.redact(comparison), report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "results/raw_results.json")
    parser.add_argument("--report", type=Path, default=HERE / "JEV_EVIDENCE_QUALITY_RESULTS.md")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare-only", action="store_true", help="Freeze inputs/questions; no API calls")
    modes.add_argument("--report-only", action="store_true", help="Analyze saved records; no API calls")
    args = parser.parse_args()
    output = args.output.resolve()
    data = read_saved(output) if args.report_only else prepare(output)
    if args.prepare_only or args.report_only or data["status"] == "complete":
        write_artifacts(data, output, args.report)
        print(f"Status: {data['status']}. Report: {args.report.resolve()}")
        return 0
    spec = data["preregistration"]["specification"]
    completed = {(o["split"], o["case_id"], o["trial"], o["kind"]) for o in data["observations"]}
    reason = None
    if data["pending_request"]:
        reason = "An interrupted request has unknown server outcome. Preserved; it will not be silently resubmitted."
    elif not os.environ.get(core.KEY_ENV, "").strip():
        reason = f"{core.KEY_ENV} is missing in this process; no API requests made."
    else:
        try:
            with core.TypeSafeClient(api_key=os.environ[core.KEY_ENV], model=MODEL, base_url=core.BASE_URL,
                                     timeout=30, retry=core.RetryPolicy(max_retries=0), compression=False) as client:
                catalogue, preflight = core.model_preflight()
                data["preflights"].append(preflight)
                core.save(output, data)
                if catalogue is None:
                    raise RuntimeError("Catalogue preflight failed; see actual recorded error.")
                core.verify_catalogue(catalogue)
                data["status"] = "running"
                data.pop("blocking_reason", None)
                for split in ("development", "heldout"):
                    if split == "heldout" and data["selected_rule"] is None:
                        selection = analysis.select_rule(data)
                        frozen_rule = {**selection, "frozen_at": j2.timestamp(), "specification_sha256": data["specification_sha256"]}
                        core.save(output.parent / "routing_rule.json", frozen_rule)
                        data["selected_rule"] = frozen_rule
                        core.save(output, data)
                    cases = spec[split]["cases"]
                    for trial in range(1, 4):
                        offset = ((trial-1)*7) % len(cases)
                        for index, case in enumerate(cases[offset:] + cases[:offset]):
                            kinds = ("signals",) if split == "development" else (("j2", "signals") if (index+trial)%2 else ("signals", "j2"))
                            for kind in kinds:
                                identity = (split, case["id"], trial, kind)
                                if identity in completed:
                                    continue
                                data["pending_request"] = {"split": split, "case_id": case["id"], "trial": trial, "kind": kind, "started_at": j2.timestamp()}
                                core.save(output, data)
                                observation = collect(client, spec, case, trial, split, kind)
                                data["observations"].append(observation)
                                completed.add(identity)
                                data["pending_request"] = None
                                core.save(output, data)
                                states = {k: v["status"] for k, v in observation["outputs"].items()}
                                print(f"{split} {case['id']} trial {trial}/3 {kind}: {states}; {observation['call']['latency_ms']:.0f} ms", flush=True)
        except KeyboardInterrupt:
            reason = "Interrupted; any pending request is retained as unknown, not a semantic result."
        except Exception as error:
            data["execution_errors"].append({"at": j2.timestamp(), "error": core.error_record(error)})
            reason = "Execution failed; see saved error records. No results were fabricated."
    if reason:
        data["blocking_reason"] = reason
    data["status"] = "complete" if len(completed) == 216 and all(v["status"] == "ok" for o in data["observations"] for v in o["outputs"].values()) else "incomplete"
    data["updated_at"] = j2.timestamp()
    core.save(output, data)
    write_artifacts(data, output, args.report)
    if reason:
        print(reason)
    print(f"Status: {data['status']}. Report: {args.report.resolve()}")
    return 0 if data["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
