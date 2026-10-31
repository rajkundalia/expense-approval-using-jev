"""Isolated policy-condition Noul and clarification-resolution Score experiment."""
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

from typesafe_sdk import Choice, Noul, Score, ScoreAnswer, TypeSafeClient

if __package__:
    from . import sdk_support as core, j2_reference as j2, analysis
else:
    import sdk_support as core
    import j2_reference as j2
    import analysis

HERE = Path(__file__).resolve().parent
MODEL = core.MODEL_SNAPSHOT
PROPOSITIONS = {
    "exceptional_commute": "The supplied explanation explicitly establishes an exceptional business requirement that distinguishes this home-to-regular-office journey from ordinary commuting.",
    "charged_mobile_extra": "The invoice description explicitly identifies a separately charged entertainment or streaming component in addition to the cellular plan."
}
RUBRIC = [
    "Not resolved. The revision does not address the requested missing information or adds no relevant clarification. Merely repeating the original explanation or adding an unrelated detail is not resolution.",
    "Partially resolved. The revision adds relevant information but leaves a necessary part of the specific clarification unresolved. Answering only one of two requested details is partial.",
    "Resolved. The revision supplies the information needed to answer the exact clarification, including an explicit policy exclusion or a correction that contradicts an earlier explanation. This does not establish eligibility, truthfulness or claim approval. A short answer can be complete."
]
TRANSPORT_POLICY = (
    "Ordinary daily home-to-regular-office commuting is excluded. A specific exceptional journey to that office "
    "for a client meeting or another qualifying business requirement can be covered. Client meetings, mandatory "
    "internal training and work-related offsites can qualify. Colleague attendance alone does not establish "
    "business purpose. The employee explanation is sufficient evidence for this experiment without external proof."
)
MOBILE_POLICY = (
    "Cellular voice/data plans qualify, subject to a monthly limit handled later by Python. A complimentary "
    "streaming benefit does not independently disqualify the cellular plan. Separately charged entertainment "
    "or streaming extras are excluded. Assess only whether the invoice explicitly identifies this condition; "
    "do not calculate charges, split amounts, apply a cap or reject the underlying plan."
)


def sha_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs():
    fixtures = {name: json.loads((HERE / f"{name}_cases.json").read_text(encoding="utf-8")) for name in ("j3", "j4")}
    if len(fixtures["j3"]["cases"]) != 18 or len(fixtures["j4"]["cases"]) != 22:
        raise ValueError("This design expects 18 J3 and 22 J4 cases.")
    seen = set()
    for family, dataset in fixtures.items():
        for c in dataset["cases"]:
            if c["id"] in seen or c["split"] not in {"development", "heldout"}:
                raise ValueError("Duplicate case or invalid split.")
            seen.add(c["id"])
            if family == "j3":
                states = {"EXPLICITLY_PRESENT", "EXPLICITLY_ABSENT", "UNKNOWN", "NOT_APPLICABLE"}
                if c["expected_evidence_state"] not in states or c["applicable"] != (c["expected_evidence_state"] != "NOT_APPLICABLE"):
                    raise ValueError("Applicability and evidence annotation disagree.")
                if c["j2_meaningful"] != (c["expected_j2"] in j2.LABELS):
                    raise ValueError("J2 comparison must be explicitly meaningful or skipped.")
            elif c["expected_level"] not in (0, 1, 2) or c["expected_level"] not in c["acceptable_levels"]:
                raise ValueError("Invalid resolution-level hypothesis.")
    frozen = json.loads((HERE / "reference_data/j2_preregistered.json").read_text(encoding="utf-8"))
    return fixtures, frozen["specification"]


def noul_question(case):
    commuting = case["proposition"] == "exceptional_commute"
    return Noul(instructions={
        "proposition": PROPOSITIONS[case["proposition"]],
        "applicable_policy": TRANSPORT_POLICY if commuting else MOBILE_POLICY,
        "scope": (
            "Applicability to home-to-regular-office travel is established outside this question. "
            "A low proposition probability does not prove ordinary commuting; missing exceptional-purpose "
            "evidence and an explicit ordinary commute are different evidence states. Do not verify honesty, "
            "require formal wording or external documents, or use another model answer."
            if commuting else
            "Judge explicit invoice charging evidence, not employee purpose. Missing or unclear charging "
            "information is not explicit absence. Complimentary benefits do not satisfy the proposition. "
            "A low probability alone cannot distinguish unknown status from explicit absence. "
            "Do not calculate or approve an amount or use another model answer."
        )})


def revision_question(case, reference):
    return Score(instructions={
        "question": "How completely does the revised employee response address the exact clarification question?",
        "applicable_policy": reference["dataset"]["policies"][case["policy_category"]],
        "scope": "Compare the original evidence, exact question and revision. Measure resolution of requested information, "
                 "not general explanation quality, length, policy eligibility, employee honesty, or approval. "
                 "An explicit non-qualifying answer can fully resolve the question. A correction can be resolved "
                 "even if it contradicts the original; resolution does not verify the correction or remove "
                 "the need for purpose/consistency reassessment. Do not demand external proof or calculate money."
    }, criteria=RUBRIC)


def request_for(case, kind, reference):
    if kind == "noul":
        keys = ("invoice_item_description", "policy_category") if case["proposition"] == "charged_mobile_extra" else j2.STATE_FIELDS
        state = {k: case[k] for k in keys}
        return state, {"policy_condition": noul_question(case)}
    if kind == "choice":
        return j2.state_for({**case, "employee_justification": case["employee_justification"]}), {
            "purpose_alignment": Choice(**reference["questions_by_policy"][case["policy_category"]])}
    state = {k: case[k] for k in ("policy_category", "invoice_item_description", "original_employee_explanation", "clarification_question", "revised_employee_explanation")}
    return state, {"revision_resolution": revision_question(case, reference)}


def jobs(fixtures, split):
    for family, dataset in fixtures.items():
        for trial in range(1, 4):
            cases = [c for c in dataset["cases"] if c["split"] == split]
            shift = (trial-1)*3 % len(cases)
            for case in cases[shift:] + cases[:shift]:
                kinds = (["noul"] if case["applicable"] else []) + (["choice"] if case["j2_meaningful"] else []) if family == "j3" else ["score"]
                if trial % 2 == 0:
                    kinds.reverse()
                for kind in kinds:
                    yield family, case, trial, kind


def build_spec():
    if version("typesafe-sdk") != "0.7.5":
        raise ValueError("Install the pinned typesafe-sdk==0.7.5.")
    fixtures, reference = load_inputs()
    questions = {c["id"]: {kind: {name: q.model_dump(mode="json") for name, q in request_for(c, kind, reference)[1].items()}
                for kind in ((["noul"] if c["applicable"] else []) + (["choice"] if c["j2_meaningful"] else []) if family == "j3" else ["score"])}
                for family, ds in fixtures.items() for c in ds["cases"]}
    references = {str(p.relative_to(HERE)): sha_file(p) for p in (HERE / "reference_data").glob("*.json")}
    return {"fixtures": fixtures, "reference_policy": reference, "references": references, "questions": questions,
            "sdk_version": version("typesafe-sdk"), "model": MODEL, "base_url": core.BASE_URL, "trials": 3,
            "sdk_signatures": {name: str(inspect.signature(obj)) for name, obj in {"Noul": Noul, "Score": Score, "Choice": Choice, "system_one": TypeSafeClient.system_one}.items()},
            "score_schema": ScoreAnswer.model_json_schema(),
            "selection_protocol": "No numerical routing cutoffs are specified before inference. After development results, derive at most three sensitivity cutoffs from midpoints of distinct case-median outputs at approximately quartile positions, separately for each Noul proposition and Score. Freeze that sensitivity plan before collecting held-out results. Compare all frozen cutoffs without choosing or retuning a deployment threshold on held-out outcomes. If development values do not vary, report that limitation. No cutoff is a calibrated correctness guarantee.",
            "applicability_protocol": "Applicability is fixture-supplied structured context, not inferred by Python from free text or a low Noul. An eventual app needs an identified claimed line/journey and explicit trip relation or billing context, supplied/confirmed by the employee or a separately evaluated classifier. Mixed legs and known J1 mismatches are clarified before these questions.",
            "expected_request_count": sum(1 for s in ("development", "heldout") for _ in jobs(fixtures, s)),
            "retry_max": 0, "timeout_seconds": 30}


def read_saved(output):
    data = json.loads(output.read_text(encoding="utf-8"))
    frozen = json.loads((output.parent / "preregistered.json").read_text(encoding="utf-8"))
    if frozen != data["preregistration"] or j2.sha(frozen["specification"]) != data["specification_sha256"]:
        raise ValueError("Preregistration integrity check failed.")
    for name, digest in frozen["specification"]["references"].items():
        if sha_file(HERE / name) != digest:
            raise ValueError("Copied historical reference changed.")
    if data["sensitivity_plan"]:
        if json.loads((output.parent / "sensitivity_plan.json").read_text(encoding="utf-8")) != data["sensitivity_plan"]:
            raise ValueError("Frozen sensitivity plan mismatch.")
        expected = analysis.derive_sensitivity_plan(data)
        if any(data["sensitivity_plan"].get(key) != value for key, value in expected.items()):
            raise ValueError("Sensitivity cutoffs differ from the registered development-only derivation.")
        for o in data["observations"]:
            if o["split"] == "heldout" and o["call"]["started_at"] < data["sensitivity_plan"]["frozen_at"]:
                raise ValueError("Held-out inference predates sensitivity-plan freeze.")
    elif any(o["split"] == "heldout" for o in data["observations"]):
        raise ValueError("Held-out observations lack a prior frozen sensitivity plan.")
    return data


def prepare(output):
    spec = build_spec()
    if output.exists():
        data = read_saved(output)
        if data["specification_sha256"] != j2.sha(spec):
            raise ValueError("Design changed after freezing. Do not relabel or overwrite this run.")
        return data
    frozen_path = output.parent / "preregistered.json"
    if frozen_path.exists():
        raise ValueError("Orphaned preregistration exists; preserve it rather than overwrite.")
    frozen = {"created_at": j2.timestamp(), "specification": spec}
    core.save(frozen_path, frozen)
    data = {"status": "prepared", "preregistration": frozen, "specification_sha256": j2.sha(spec),
            "observations": [], "sensitivity_plan": None, "pending_request": None, "preflights": [], "execution_errors": []}
    core.save(output, data)
    return data


def parse_answer(response, kind):
    if response.model != MODEL:
        raise ValueError("Returned model differs from the exact pinned snapshot.")
    name = {"noul": "policy_condition", "choice": "purpose_alignment", "score": "revision_resolution"}[kind]
    if set(response.answers) != {name}:
        raise ValueError("Response must answer the one registered question.")
    if kind == "choice":
        return j2.validate_answer(response.choices[name])
    answer = response.nouls[name] if kind == "noul" else response.scores[name]
    values = [answer.noul] if kind == "noul" else [answer.score, answer.confidence, *answer.probabilities.values()]
    if any(not math.isfinite(v) for v in values):
        raise ValueError("Non-finite response value.")
    if kind == "noul":
        if not 0 <= answer.noul <= 1:
            raise ValueError("Noul probability outside [0,1].")
    elif not 0 <= answer.score <= 2 or set(answer.probabilities) != {0, 1, 2} or set(answer.legend) != {0, 1, 2} or any(not 0 <= v <= 1 for v in [answer.confidence, *answer.probabilities.values()]):
        raise ValueError("Invalid three-level Score answer.")
    return answer.model_dump(mode="json")


def collect(client, family, case, trial, kind, reference):
    state, questions = request_for(case, kind, reference)
    response, call = core.invoke("system_one", {"model": MODEL, "state": state,
        "questions": {name: q.model_dump(mode="json") for name, q in questions.items()}},
        lambda: client.system_one(state=state, questions=questions, model=MODEL))
    obs = {"family": family, "case_id": case["id"], "split": case["split"], "trial": trial,
           "kind": kind, "status": "error", "answer": None, "interpretation_error": None, "call": call}
    if response is not None:
        try:
            obs.update(answer=parse_answer(response, kind), status="ok")
        except Exception as error:
            obs["interpretation_error"] = core.error_record(error)
    return obs


def write_artifacts(data, output, report):
    summary = analysis.summarize(data, HERE / "reference_data")
    core.save(output.parent / "evaluation_summary.json", summary)
    analysis.write_report(core.redact(data), core.redact(summary), report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "results/raw_results.json")
    parser.add_argument("--report", type=Path, default=HERE / "JEV_POLICY_CONDITIONS_AND_REVISIONS_RESULTS.md")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare-only", "--dry-run", action="store_true", help="Freeze fixtures and inspect copied saved results; no API calls")
    modes.add_argument("--analysis-only", action="store_true", help="Analyze retained results only; no API calls")
    args = parser.parse_args()
    output = args.output.resolve()
    data = read_saved(output) if args.analysis_only else prepare(output)
    if args.prepare_only or args.analysis_only or data["status"] == "complete":
        write_artifacts(data, output, args.report)
        print(f"Status: {data['status']}. Report: {args.report.resolve()}")
        return 0
    spec = data["preregistration"]["specification"]
    fixtures = spec["fixtures"]
    completed = {(o["case_id"], o["trial"], o["kind"]) for o in data["observations"]}
    reason = None
    if data["pending_request"]:
        reason = "An interrupted request has unknown server outcome; it will not be silently repeated."
    elif not os.environ.get(core.KEY_ENV, "").strip():
        reason = f"{core.KEY_ENV} is missing in this process. No inference was fabricated."
    else:
        execution_stage = "setup"
        try:
            with TypeSafeClient(api_key=os.environ[core.KEY_ENV], model=MODEL, base_url=core.BASE_URL,
                                timeout=30, retry=core.RetryPolicy(max_retries=0), compression=False) as client:
                catalogue, record = core.model_preflight()
                data["preflights"].append(record)
                core.save(output, data)
                if catalogue is None:
                    raise RuntimeError("Model availability preflight failed; see saved error.")
                core.verify_catalogue(catalogue)
                data["status"] = "running"
                data.pop("blocking_reason", None)
                for split in ("development", "heldout"):
                    if split == "heldout" and data["sensitivity_plan"] is None:
                        plan = analysis.derive_sensitivity_plan(data)
                        data["sensitivity_plan"] = {**plan, "frozen_at": j2.timestamp()}
                        core.save(output.parent / "sensitivity_plan.json", data["sensitivity_plan"])
                        core.save(output, data)
                    for family, case, trial, kind in jobs(fixtures, split):
                        identity = (case["id"], trial, kind)
                        if identity in completed:
                            continue
                        data["pending_request"] = {"case_id": case["id"], "trial": trial, "kind": kind, "split": split, "started_at": j2.timestamp()}
                        execution_stage = "checkpoint_before_request"
                        core.save(output, data)
                        execution_stage = "model_request"
                        obs = collect(client, family, case, trial, kind, spec["reference_policy"])
                        data["observations"].append(obs)
                        data["pending_request"] = None
                        completed.add(identity)
                        execution_stage = "checkpoint_after_response"
                        core.save(output, data)
                        execution_stage = "between_requests"
                        print(f"{split} {case['id']} {kind} {trial}/3: {obs['status']}; {obs['call']['latency_ms']:.0f} ms", flush=True)
        except KeyboardInterrupt:
            reason = "Interrupted; unfinished request remains unknown, not a semantic outcome."
        except Exception as error:
            data["execution_errors"].append({"at": j2.timestamp(), "stage": execution_stage, "error": core.error_record(error)})
            if execution_stage == "checkpoint_before_request":
                # This failed before collect() was called: safe to resume the unsent request.
                data.setdefault("not_sent_requests", []).append(data["pending_request"])
                data["pending_request"] = None
            reason = "Execution stopped; inspect actual saved errors."
    if reason:
        data["blocking_reason"] = reason
    data["status"] = "complete" if len(completed) == spec["expected_request_count"] and all(o["status"] == "ok" for o in data["observations"]) else "incomplete"
    core.save(output, data)
    write_artifacts(data, output, args.report)
    if reason:
        print(reason)
    print(f"Status: {data['status']}. Report: {args.report.resolve()}")
    return 0 if data["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
