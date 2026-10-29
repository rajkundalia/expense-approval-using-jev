"""Run the preregistered V2 cases through the existing Jev SDK integration."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from statistics import median
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from experiments.category_validation import experiment as core

ROOT = Path(__file__).resolve().parent
PLAN = ROOT / "v2_plan.json"
DEFAULT_OUTPUT = ROOT / "results" / "v2" / "comparison.json"
DEFAULT_REPORT = ROOT / "JEV_CATEGORY_EXPERIMENT_V2_RESULTS.md"
SPECIAL = {"OTHER", "INSUFFICIENT_INFORMATION", "MIXED_ITEMS"}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def load_plan(path=PLAN):
    plan = json.loads(path.read_text(encoding="utf-8"))
    assert len(plan["cases"]) == 15 and plan["trials_per_case"] == 3
    assert len({c["id"] for c in plan["cases"]}) == 15
    assert len(plan["category_definitions"]) == 9
    for case in plan["cases"]:
        assert case["selected_category"] in plan["category_definitions"]
        assert case["expected_category"] in plan["category_definitions"]
        assert set(case) == {"id", "description", "selected_category", "expected_category", "coverage", "expected_reason"}
    return plan


def score(expected, selected, result):
    """Count observable category decisions; no purpose or payment decision is inferred."""
    if result["status"] != "ok":
        return None
    label = result["category"]
    accepted = label == selected
    # Count wrong OTHER/MIXED_ITEMS suggestions too; clarification is separate.
    suggestion = label != "INSUFFICIENT_INFORMATION" and label != selected
    return {
        "hypothesis_agreement": label == expected,
        "false_category_acceptance": accepted and selected != expected,
        "incorrect_category_suggestion": suggestion and label != expected,
        "unnecessary_clarification": label == "INSUFFICIENT_INFORMATION" and expected != label,
        "wrong_alternative_outcome": label != selected and label != expected,
        "missed_correct_selection": selected == expected and not accepted,
        "noul_gate_false_acceptance": result.get("gate") == "match" and selected != expected,
    }


def stats(data, approach):
    observations = [o for o in data["observations"] if o["approach"] == approach]
    successes = [o for o in observations if o["result"]["status"] == "ok"]
    sums = Counter()
    for observation in successes:
        sums.update({k: int(v) for k, v in observation["scores"].items()})
    calls = [j["record"] for j in data["call_journal"] if j["approach"] == approach]
    http_calls = [c for c in calls if c.get("http") is not None or (c.get("error") or {}).get("status") is not None]
    latencies = [o["result"]["latency_ms"] for o in observations]
    return {
        "planned_observations": 45, "finished_observations": len(observations),
        "successful_observations": len(successes),
        "failed_observations": len(observations) - len(successes),
        "request_attempts": len(calls), "http_responses": len(http_calls),
        "call_errors": sum(c["status"] == "error" for c in calls),
        "suggestion_opportunities": sum(
            o["result"]["category"] != "INSUFFICIENT_INFORMATION" and
            o["result"]["category"] != o["selected_category"] for o in successes),
        "false_acceptance_opportunities": sum(o["expected_category"] != o["selected_category"] for o in successes),
        "clarification_opportunities": sum(o["expected_category"] != "INSUFFICIENT_INFORMATION" for o in successes),
        "median_latency_ms": median(latencies) if latencies else None,
        "total_latency_ms": round(sum(latencies), 3) if latencies else None,
        "counts": dict(sums) if successes else None,
    }


def repeatability(data, case_id, approach):
    observations = sorted((o for o in data["observations"] if o["case_id"] == case_id and
                           o["approach"] == approach), key=lambda o: o["trial"])
    successful = [o for o in observations if o["result"]["status"] == "ok"]
    labels = [o["result"]["category"] for o in successful]
    return {"finished": len(observations), "successful": len(successful), "labels": labels,
            "all_three_labels_agree": len(labels) == 3 and len(set(labels)) == 1,
            "noul_probabilities": [o["result"].get("noul_probability") for o in successful] if approach == "A" else None,
            "gates": [o["result"].get("gate") for o in successful] if approach == "A" else None}


def write_report(data, path):
    plan = data["preregistration"]["plan"]
    lines = ["# Jev category-validation experiment V2 results", "",
             f"Run status: **{data['status']}**. This report is generated only from retained records.", "",
             "## Frozen design and policy", "",
             f"Preregistered at `{data['preregistration']['created_at']}` before inference; specification SHA-256: `{data['specification_sha256']}`.",
             f"Requested `{core.MODEL}` through `{core.BASE_URL}` using `typesafe-sdk=={core.SDK_VERSION}`; expected canonical snapshot `{core.MODEL_SNAPSHOT}`.",
             "The immutable preregistration snapshot is stored beside the raw comparison JSON as `preregistered.json`. Expected labels are development hypotheses fixed before inference, not verified ground truth.", "",
             "Policy follows the user's explicit V2 rules: AirPods/headphones are candidate Wellness by product identity; missing purpose is never insufficient information. Explicit cross-category purchases are MIXED_ITEMS. Included Netflix at no separate charge remains MOBILE_BILL; a separately charged Netflix service is distinct. A specific claimed line overrides other invoice lines. No eligible amount, reimbursement, or purpose alignment is calculated.", "",
             "V2 uses uppercase identifiers for all six categories, plus OTHER, INSUFFICIENT_INFORMATION and MIXED_ITEMS. V1 raw results and its historical definitions remain unchanged.", "",
             "A asks Noul whether the described claimed purchase matches the selected category. p <= 0.2 is negative, p >= 0.8 is match, and the interval is uncertain. A negative or uncertain result triggers independent Choice; errors are failures, not uncertainty. B always asks independent Choice, then Python compares its label with the selection. Both Choice prompts are identical and see no selection, previous answer, hypothesis or justification.", "",
             "Three rounds cover all 15 cases: 45 observations per approach. A/B order alternates by case and round, with no concurrent calls and SDK retries disabled. Every individual call is checkpointed in a journal before the next call.", "",
             "## Expected outcomes saved before inference", "",
             "| ID | Description | Selected | Expected | Reason |", "| --- | --- | --- | --- | --- |"]
    for c in plan["cases"]:
        lines.append(f"| {c['id']} | {c['description']} | {c['selected_category']} | {c['expected_category']} | {c['expected_reason']} |")
    lines += ["", "## Comparison", "",
              "False category acceptance means a successful final label equals the employee selection although the frozen expected label differs. A's positive Noul-gate false acceptances are also counted separately. A fallback that returns the selected category counts as final category acceptance; it remains a proposal from that stage, not a reimbursement approval.", "",
              "Incorrect category suggestion means a successful non-clarification label different from the selection and different from the expected label, including wrong OTHER or MIXED_ITEMS suggestions. INSUFFICIENT_INFORMATION on an identifiable purchase is separately unnecessary clarification. Wrong alternative outcome includes all wrong labels different from the selection, including clarification. A gate marked uncertain triggers a model call, not human clarification. API failures are never counted as clarification or correct decisions. Error categories may overlap.", "",
              "Counts use successful-observation denominators, not all planned trials; missing observations are not zero-error evidence.", "",
              "| Metric | A: Noul-first | B: Choice-first |", "| --- | --- | --- |"]
    summary = {a: stats(data, a) for a in ("A", "B")}
    for field in ("planned_observations", "finished_observations", "successful_observations", "failed_observations", "request_attempts", "http_responses", "call_errors", "false_acceptance_opportunities", "suggestion_opportunities", "clarification_opportunities", "median_latency_ms", "total_latency_ms"):
        lines.append(f"| {field} | {summary['A'][field]} | {summary['B'][field]} |")
    for field in ("hypothesis_agreement", "false_category_acceptance", "noul_gate_false_acceptance", "incorrect_category_suggestion", "unnecessary_clarification", "wrong_alternative_outcome", "missed_correct_selection"):
        values = [(summary[a]["counts"] or {}).get(field, "not measured") for a in ("A", "B")]
        lines.append(f"| {field} | {values[0]} | {values[1]} |")
    lines += ["", "Request attempts are SDK invocations, including connection failures; HTTP responses count those with a returned status. The public catalogue preflight is separate. Latency is end-to-end per approach, including A's conditional second call and local checkpoint writes, not pure model inference time. Call latency in the ledger excludes the subsequent checkpoint write.", "",
              "## Individual trial decisions", "", "| Case | Trial | Approach | Expected | Observed | Noul p | Gate | Calls | Latency ms | Status |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for o in data["observations"]:
        r = o["result"]
        lines.append(f"| {o['case_id']} | {o['trial']} | {o['approach']} | {o['expected_category']} | {r.get('category')} | {r.get('noul_probability')} | {r.get('gate')} | {len(r['calls'])} | {r['latency_ms']} | {r['status']} |")
    if not data["observations"]:
        lines += ["", "No measured decisions are available. None of the planned cases is represented as having a measured zero error or successful classification."]
    lines += ["", "## Repeatability", "", "| Case | Approach | Successful trials | Labels in trial order | All 3 labels agree | Noul probabilities | Gates |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for c in plan["cases"]:
        for a in ("A", "B"):
            r = repeatability(data, c["id"], a)
            lines.append(f"| {c['id']} | {a} | {r['successful']}/3 | {r['labels']} | {r['all_three_labels_agree'] if r['successful'] == 3 else 'not measured completely'} | {r['noul_probabilities']} | {r['gates']} |")
    lines += ["", "Repeated labels alone do not imply identical confidence or distributions. Individual Choice records below retain all values so differing distributions remain visible.", "", "## Individual response ledger: full distributions, confidence, metadata and errors", ""]
    for j in data["call_journal"]:
        call = j["record"]
        raw = call.get("http")
        raw_body = None
        if raw:
            try:
                raw_body = json.loads(raw["body_text"])
            except (ValueError, KeyError):
                raw_body = raw.get("body_text")
        entry = {"case_id": j["case_id"], "trial": j["trial"], "approach": j["approach"],
                 "started_at": call["started_at"], "request": call["request"]["state"],
                 "question_names": list(call["request"]["questions"]),
                 "latency_ms": call["latency_ms"], "status": call["status"],
                 "http_status": raw["status"] if raw else None, "response": call.get("response"),
                 "raw_body": raw_body, "error": call.get("error")}
        lines += ["```json", json.dumps(entry, indent=2, ensure_ascii=False), "```", ""]
    lines += ["## API and execution errors", "", "```json", json.dumps({"blocking_reason": data.get("blocking_reason"), "execution_errors": data["execution_errors"],
              "preflight": [{"status": p["status"], "error": p.get("error"), "latency_ms": p["latency_ms"], "http_status": (p.get("http") or {}).get("status")} for p in data["preflights"]]}, indent=2), "```", "",
              "Call-level errors are retained in the individual ledger; interpretation errors are retained in the raw observation results. HTTP failures retain SDK error bodies/metadata. Noul exposes no independent confidence or explicit distribution; neither is invented.", "",
              "## Recommendation and limitations", ""]
    if all(summary[a]["finished_observations"] == 45 and summary[a]["successful_observations"] == 45 for a in ("A", "B")):
        a, b = summary["A"], summary["B"]
        primary = ("false_category_acceptance", "incorrect_category_suggestion", "unnecessary_clarification")
        av, bv = tuple(a["counts"][k] for k in primary), tuple(b["counts"][k] for k in primary)
        if av == bv:
            lines.append("The two structures have equal observed counts on the three primary errors. Prefer independent Choice-first as the provisional category-validation design if its case-level outcomes below are acceptable: it provides a category distribution for every purchase and uses one call per observation. Noul-first adds a probability and a conditional request; retain it only if those gates provide operational value established on a larger validation set.")
        elif all(x <= y for x, y in zip(bv, av)):
            lines.append("Choice-first has no higher count on any of the three primary errors in this run. Prefer it provisionally for this category-only task, subject to reviewing individual failures and a larger independently labelled evaluation.")
        elif all(x <= y for x, y in zip(av, bv)):
            lines.append("Noul-first has no higher count on any of the three primary errors in this run. It is the provisional candidate on these cases, but its additional requests and gate behavior need validation on a larger independently labelled set.")
        else:
            lines.append("The structures trade off the three primary errors; this run does not establish a single best choice. Choose operational error priorities before selecting a structure, without changing policy or relabelling these cases.")
    else:
        lines.append("A measured recommendation is not yet supported: the full three-trial evaluation is incomplete. Choice-first is architecturally simpler and exposes distributions on every case, but that is a design observation, not a measured performance conclusion. Do not use V1's different Wellness definitions to fill missing V2 outcomes.")
    lines += ["", "This is a small, hand-authored development set with three sequential repetitions per case, not an independent accuracy benchmark or a calibration study. Shared case definitions and fixed thresholds can bias conclusions. Repeated responses may share provider or cache effects; independent sampling and backend determinism are not established. Order is alternated, but network and connection warmup remain confounders. No threshold, expected label, or reimbursement policy is tuned from predictions. No purpose-alignment, budget, eligibility amount or reimbursement calculation occurs.", "",
              "## Exact fixed question objects", "", "Noul and Choice objects were frozen in preregistration before calls. No expected label, selection in Choice, or employee justification appears in these questions.", "", "```json", json.dumps(data["preregistration"]["questions"], indent=2, ensure_ascii=False), "```", "",
              f"Raw records: `{data['output_path']}`. All request/response records, response headers, statuses, metadata, distributions, confidence values, errors and latencies remain there. Original V1 artifacts were not overwritten.", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--prepare-only", action="store_true", help="Freeze expected outcomes and write an unmeasured report; no API calls")
    parser.add_argument("--report-only", action="store_true", help="Regenerate the report from saved responses; no API calls")
    args = parser.parse_args()
    plan = load_plan()
    spec = {"plan": plan, "model": core.MODEL, "snapshot": core.MODEL_SNAPSHOT,
            "thresholds": {"negative_max": core.NEGATIVE_MAX, "positive_min": core.POSITIVE_MIN},
            "questions": {"matches_selected": core.noul_question(plan["category_definitions"]).model_dump(mode="json"),
                          "category": core.choice_question(plan["category_definitions"]).model_dump(mode="json")}}
    output = args.output.resolve()
    if output.exists():
        data = json.loads(output.read_text(encoding="utf-8"))
        if data["specification_sha256"] != digest(spec) and not args.report_only:
            raise ValueError("Frozen specification changed. Use a new --output directory; never overwrite labelled results.")
    else:
        if args.report_only:
            parser.error("No saved output exists to report.")
        evidence = core.sdk_evidence()
        prereg = {**spec, "created_at": now()}
        frozen_path = output.parent / "preregistered.json"
        if frozen_path.exists():
            raise ValueError("Preregistration already exists without comparison; use a new output directory.")
        core.save(frozen_path, prereg)
        data = {"preregistration": prereg, "specification_sha256": digest(spec), "sdk_evidence": evidence,
                "output_path": str(output), "status": "prepared", "observations": [],
                "call_journal": [], "preflights": [], "execution_errors": []}
        core.save(output, data)
    if args.report_only or args.prepare_only or data["status"] == "complete":
        write_report(data, args.report)
        print(f"Status: {data['status']}; frozen plan: {output.parent / 'preregistered.json'}; report: {args.report.resolve()}")
        return 0
    completed = {(o["case_id"], o["trial"], o["approach"]) for o in data["observations"]}
    journalled = {(o["case_id"], o["trial"], o["approach"]) for o in data["call_journal"]}
    reason = None
    if journalled - completed:
        reason = "Interrupted approach has journalled calls without a completed observation. Preserved; use a new --output directory for an explicitly new run."
    elif not os.environ.get(core.KEY_ENV, "").strip():
        reason = f"{core.KEY_ENV} is missing in this process; no new API calls were made."
    else:
        try:
            with core.TypeSafeClient(api_key=os.environ[core.KEY_ENV], model=core.MODEL,
                                     base_url=core.BASE_URL, timeout=30,
                                     retry=core.RetryPolicy(max_retries=0), compression=False) as client:
                catalogue, record = core.model_preflight()
                data["preflights"].append(record)
                core.save(output, data)
                if catalogue is None:
                    raise RuntimeError("OpenRouter model preflight failed; see its recorded error.")
                core.verify_catalogue(catalogue)
                data["status"] = "running"
                data.pop("blocking_reason", None)
                core.save(output, data)
                for trial in range(1, 4):
                    for index, case in enumerate(plan["cases"]):
                        for approach in (("A", "B") if (index + trial) % 2 else ("B", "A")):
                            key = (case["id"], trial, approach)
                            if key in completed:
                                continue
                            identity = {"case_id": case["id"], "trial": trial, "approach": approach}
                            def checkpoint(record):
                                data["call_journal"].append({**identity, "record": record})
                                core.save(output, data)
                            function = core.approach_a if approach == "A" else core.approach_b
                            result = function(client, case, plan["category_definitions"], checkpoint)
                            observation = {**identity, "selected_category": case["selected_category"],
                                           "expected_category": case["expected_category"], "result": result,
                                           "scores": score(case["expected_category"], case["selected_category"], result)}
                            data["observations"].append(observation)
                            completed.add(key)
                            core.save(output, data)
                            print(f"Trial {trial}/3 {case['id']} {approach}: {result.get('category')} ({result['status']}); {len(result['calls'])} call(s), {result['latency_ms']:.0f} ms", flush=True)
        except Exception as error:
            data["execution_errors"].append({"at": now(), "error": core.error_record(error)})
            reason = "Execution failed; inspect saved errors. No outputs were fabricated."
    if reason:
        data["blocking_reason"] = reason
    data["status"] = "complete" if len(data["observations"]) == 90 and all(o["result"]["status"] == "ok" for o in data["observations"]) else "incomplete"
    data["updated_at"] = now()
    core.save(output, data)
    write_report(data, args.report)
    for approach in ("A", "B"):
        print(approach, json.dumps(stats(data, approach)))
    print(f"Report: {args.report.resolve()}")
    if reason:
        print(reason)
    return 0 if data["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
