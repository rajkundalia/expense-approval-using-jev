"""Deterministic offline comparisons only; this module never makes model calls."""
from __future__ import annotations

from collections import Counter
import json
from statistics import median

CANDIDATES = [
    {"name": "balanced", "noul_min": 0.8, "score_min": 1.5},
    {"name": "lenient", "noul_min": 0.7, "score_min": 1.25},
    {"name": "cautious", "noul_min": 0.9, "score_min": 1.75}
]
SELECTION_PROTOCOL = (
    "After all development signal requests and before any held-out request, compare exactly the three registered "
    "candidate pairs using configuration D on primary development cases only. Minimize lexicographically: "
    "distinct false-CONTINUE cases, distinct unnecessary-hold cases, false-CONTINUE trials, unnecessary-hold trials, "
    "then registered candidate order (balanced first). No held-out predictions or hypotheses enter selection. "
    "Freeze the selected pair and comparison in routing_rule.json before held-out inference. If development "
    "primary paired coverage is incomplete, freeze the predeclared balanced fallback with an explicit limitation. "
    "Apply the same selected Noul/Score thresholds to B/C/D; do not tune them again."
)
CONFIGS = ("A", "B", "C", "D")
ROUTES = ("CONTINUE", "EXCLUDED_PURPOSE", "CLARIFY", "REVIEW", "API_FAILURE", "NOT_MEASURED")


def route(label, noul, score, config, rule, failed=False):
    """No expected labels enter routing. A disagreement never becomes an automatic denial."""
    if config not in CONFIGS:
        raise ValueError("Unknown configuration.")
    if label is None:
        return "API_FAILURE" if failed else "NOT_MEASURED"
    if label == "UNRELATED":
        return "EXCLUDED_PURPOSE"
    if label == "INCONSISTENT":
        return "REVIEW"
    if label == "UNCLEAR":
        return "CLARIFY"
    if label != "SUPPORTED":
        raise ValueError("Unknown J2 semantic label.")
    if (config in ("B", "D") and noul is None) or (config in ("C", "D") and score is None):
        return "API_FAILURE" if failed else "NOT_MEASURED"
    if config in ("B", "D") and noul < rule["noul_min"]:
        return "REVIEW" if noul < .3 else "CLARIFY"
    if config in ("C", "D") and score < rule["score_min"]:
        return "CLARIFY"
    return "CONTINUE"


def paired(data, split, group="primary", rule=None):
    spec = data["preregistration"]["specification"]
    rule = rule or (data.get("selected_rule") or {}).get("rule") or spec["candidates"][0]
    lookup = {(o["split"], o["case_id"], o["trial"], o["kind"]): o for o in data["observations"]}
    historical = {(o["case_id"], o["trial"]): o for o in data["historical_j2"]}
    rows = []
    for case in spec[split]["cases"]:
        if case["evaluation_group"] != group:
            continue
        for trial in range(1, 4):
            signal = lookup.get((split, case["id"], trial, "signals"))
            baseline = historical.get((case["id"], trial)) if split == "development" else lookup.get((split, case["id"], trial, "j2"))
            if split == "development":
                label = baseline["outcome"] if baseline and baseline["status"] == "ok" else None
                baseline_failed = baseline is not None and baseline["status"] != "ok"
            else:
                output = (baseline or {}).get("outputs", {}).get("j2", {})
                label = (output.get("answer") or {}).get("choice") if output.get("status") == "ok" else None
                baseline_failed = output.get("status") == "error"
            j3 = (signal or {}).get("outputs", {}).get("j3", {})
            j4 = (signal or {}).get("outputs", {}).get("j4", {})
            n = (j3.get("answer") or {}).get("noul") if j3.get("status") == "ok" else None
            s = (j4.get("answer") or {}).get("score") if j4.get("status") == "ok" else None
            row = {"case_id": case["id"], "trial": trial, "expected_j2": case["expected_outcome"],
                   "expected_j3": case["expected_j3_region"], "expected_j4": case["expected_j4_level"],
                   "j2": label, "j3": n, "j4": s, "routes": {}}
            for config in CONFIGS:
                failed = baseline_failed or (config in ("B", "D") and j3.get("status") == "error") or (config in ("C", "D") and j4.get("status") == "error")
                row["routes"][config] = route(label, n, s, config, rule, failed)
            rows.append(row)
    return rows


def summarize(rows, config):
    evaluable = [r for r in rows if r["routes"][config] not in ("API_FAILURE", "NOT_MEASURED")]
    false_continue = [r for r in evaluable if r["routes"][config] == "CONTINUE" and r["expected_j2"] != "SUPPORTED"]
    holds = [r for r in evaluable if r["routes"][config] in ("CLARIFY", "REVIEW") and r["expected_j2"] == "SUPPORTED"]
    counts = Counter(r["routes"][config] for r in rows)
    return {"planned_trials": len(rows), "evaluable_trials": len(evaluable),
            "j2_false_supported": sum(r["j2"] == "SUPPORTED" and r["expected_j2"] != "SUPPORTED" for r in rows) if any(r["j2"] for r in rows) else None,
            "false_continue_trials": len(false_continue) if evaluable else None,
            "false_continue_cases": sorted({r["case_id"] for r in false_continue}),
            "unnecessary_hold_trials": len(holds) if evaluable else None,
            "unnecessary_hold_cases": sorted({r["case_id"] for r in holds}),
            "incremental_unnecessary_holds": sum(r["routes"]["A"] == "CONTINUE" for r in holds) if evaluable else None,
            "wrong_excluded_purpose_routes": sum(r["routes"][config] == "EXCLUDED_PURPOSE" and r["expected_j2"] == "SUPPORTED" for r in evaluable) if evaluable else None,
            "route_counts": {name: counts[name] for name in ROUTES}}


def select_rule(data):
    """Reads only primary development pairs. Called before the held-out loop starts."""
    candidates = data["preregistration"]["specification"]["candidates"]
    comparisons = []
    complete = True
    for index, rule in enumerate(candidates):
        rows = paired(data, "development", "primary", rule)
        complete = complete and all(r["j2"] is not None and r["j3"] is not None and r["j4"] is not None for r in rows)
        summary = summarize(rows, "D")
        loss = [len(summary["false_continue_cases"]), len(summary["unnecessary_hold_cases"]),
                summary["false_continue_trials"] or 0, summary["unnecessary_hold_trials"] or 0, index]
        comparisons.append({"rule": rule, "D_development_primary": summary, "loss": loss,
                            "all_configurations": {c: summarize(rows, c) for c in CONFIGS}})
    chosen = min(comparisons, key=lambda c: c["loss"])["rule"] if complete else candidates[0]
    return {"rule": chosen, "basis": "development-primary-only selection" if complete else "predeclared balanced fallback: incomplete development signal coverage",
            "candidate_comparison": comparisons, "selection_input_scope": "development primary only; no held-out results or annotations consulted"}


def utility(rows):
    # Common complete pairs avoid claiming improvement merely because a supplemental call failed.
    common = [r for r in rows if all(r["routes"][c] not in ("API_FAILURE", "NOT_MEASURED") for c in CONFIGS)]
    details = []
    for r in common:
        if r["routes"]["A"] != "CONTINUE":
            continue
        b, c, d = (r["routes"][key] != "CONTINUE" for key in ("B", "C", "D"))
        false = r["expected_j2"] != "SUPPORTED"
        details.append({"case_id": r["case_id"], "trial": r["trial"],
                        "noul_catches_false_support": b and false,
                        "score_catches_false_support": c and false,
                        "score_adds_beyond_noul": d and not b and false,
                        "score_extra_legitimate_hold_beyond_noul": d and not b and not false,
                        "both_hold_same_false_support": b and c and false,
                        "both_allow_same_false_support": not b and not c and false,
                        "same_B_C_D_route": len({r["routes"][key] for key in ("B", "C", "D")}) == 1})
    keys = ("noul_catches_false_support", "score_catches_false_support", "score_adds_beyond_noul", "score_extra_legitimate_hold_beyond_noul", "both_hold_same_false_support", "both_allow_same_false_support", "same_B_C_D_route")
    return {"common_evaluable_trials": len(common),
            "common_configuration_summaries": {c: summarize(common, c) for c in CONFIGS},
            "counts": {key: sum(d[key] for d in details) for key in keys} if common else None,
            "cases": {key: sorted({d["case_id"] for d in details if d[key]}) for key in keys}, "details": details}


def compare(data):
    result = {"selected_rule": data.get("selected_rule"), "status": data["status"], "splits": {}}
    for split, groups in (("development", ("primary", "j1_boundary_probe")), ("heldout", ("primary",))):
        result["splits"][split] = {}
        for group in groups:
            rows = paired(data, split, group)
            n_rows = [r for r in rows if r["j3"] is not None]
            s_rows = [r for r in rows if r["j4"] is not None]
            contrasts = [r for r in rows if r["expected_j2"] == "UNRELATED" and r["j3"] is not None and r["j4"] is not None and r["j3"] < .3 and r["j4"] >= 1.5]
            checks = {"j3_region_measured": len(n_rows),
                      "j3_region_agreement": sum(j3_region(r["j3"]) == r["expected_j3"] for r in n_rows) if n_rows else None,
                      "j4_region_measured": len(s_rows),
                      "j4_region_agreement": sum(j4_region(r["j4"]) == r["expected_j4"] for r in s_rows) if s_rows else None,
                      "clear_excluded_purpose_low_noul_high_sufficiency_trials": len(contrasts) if n_rows and s_rows else None,
                      "clear_excluded_contrast_cases": sorted({r["case_id"] for r in contrasts})}
            result["splits"][split][group] = {"trial_pairs": rows, "summaries": {c: summarize(rows, c) for c in CONFIGS}, "utility": utility(rows), "hypothesis_checks": checks}
    return result


def j3_region(value):
    return "LOW" if value < .3 else "AMBIGUOUS" if value < .7 else "HIGH"


def j4_region(value):
    return 0 if value < .5 else 1 if value < 1.5 else 2


def write_report(data, comparison, path):
    spec = data["preregistration"]["specification"]
    lines = []
    def add(value=""):
        lines.append(value)
    def code(value):
        add("```json\n" + json.dumps(value, indent=2, ensure_ascii=False) + "\n```\n")
    def table(headers, rows):
        add("| " + " | ".join(headers) + " |")
        add("| " + " | ".join("---" for _ in headers) + " |")
        for row in rows:
            add("| " + " | ".join(str(x).replace("|", "\\|").replace("\n", " ") for x in row) + " |")
        add()
    add("# Jev J3 + J4 — Evidence quality experiment\n")
    add(f"Status: **{data['status']}**. This report analyzes retained records only. No unobserved predictions are filled in.\n")
    add("## Objective, source verification and scope\n")
    add("Compare A: J2 alone, B: J2+J3 Noul, C: J2+J4 Score, and D: J2+both. Extra judgments can request clarification/review, not verify a real claim or automatically deny it. No financial eligibility, budget enforcement, OCR, FastAPI, authentication or approval workflow is implemented.\n")
    historical = [o for o in data["historical_j2"] if o["evaluation_group"] == "primary" and o["status"] == "ok"]
    matches = sum(o["outcome"] == o["expected_outcome"] for o in historical)
    errors = [o for o in historical if o["outcome"] != o["expected_outcome"]]
    add(f"Historical J2 verified from saved actual records: **{matches}/{len(historical)} primary agreement**, with {len(errors)} disagreements: {[(o['case_id'], o['trial'], o['outcome']) for o in errors]}. Historical J2 Choice was not rerun; the saved 96 actual responses are retained as the development baseline.\n")
    add(f"Frozen at `{data['preregistration']['created_at']}`, specification SHA-256 `{data['specification_sha256']}`. Exact J2 policies are copied from its preregistration. Historical result SHA-256: `{spec['historical_source_sha256']}`; preregistration SHA-256: `{spec['historical_preregistration_sha256']}`.\n")
    add(f"SDK {spec['sdk']['version']}, Python {spec['sdk']['python']}, model `{spec['model']}`, gateway `{spec['gateway']}`. Three trials per case. 32 development cases (29 primary + 3 J1 probes), and 20 genuinely new held-out primary cases. Planned new inference requests: 96 development signal requests + 60 held-out signal requests + 60 held-out J2 requests = **216**. No historical results were changed.\n")
    add("## Actual SDK Score representation and question independence\n")
    add("The installed Score constructor takes an ordered sequence of descriptions. The three entries define levels 0, 1 and 2. ScoreAnswer exposes a numeric `score` (which can be fractional), confidence, probabilities and a legend keyed by integer level in Python; JSON keys are strings. Score is documented as a probability-weighted position, not an exact integer. Raw values are preserved without rounding, normalization or pretending discrete model output. The following region rules are offline interpretation only.\n")
    code(spec["expectation_regions"])
    add("J4 measures whether purpose can be assessed, not whether it qualifies. An explicit ordinary commute, entertainment purpose, or product-purpose contradiction can score near 2. J3 asks whether qualifying purpose is established for the actual purchase. Neither judgment receives another answer, expected annotation, budget or amount. Each sees only invoice_item_description, policy_category and employee_justification plus its applicable policy. Shared state/model means outputs are not statistically independent.\n")
    add("Official docs support mixing question types in one request. J3/J4 use one such request with separately specified instructions. Held-out J2 uses its original frozen question in a separate request; no J2 result enters the signal request. Live gateway support and actual error coverage are established by the user's run, not assumed from the offline constructor checks.\n")
    code(spec["sdk"]["signatures"])
    add("## Exact final propositions and Score question\n")
    code(spec["signal_questions"])
    add("Exact held-out J2 question objects are retained under `j2_questions` in preregistered.json and every raw J2 request; they match the historical frozen question objects byte-for-value after JSON decoding.\n")
    add("## Frozen expected annotations and original input states\n")
    for split in ("development", "heldout"):
        add(f"### {split}\n")
        table(["ID", "Group", "Policy", "Invoice description", "Explanation", "Expected J2", "Expected J3", "Expected J4", "J3/J4 rationale"],
              [[c["id"], c["evaluation_group"], c["policy_category"], c["invoice_item_description"], c["employee_justification"], c["expected_outcome"], c["expected_j3_region"], c["expected_j4_level"], c["j3_j4_expected_reason"]] for c in spec[split]["cases"]])
    add("All historical J2 input fields, group membership and hypotheses were copied unchanged. New J3 support regions are qualitative hypotheses, not exact expected probabilities or correctness guarantees. Held-out cases add staff social outings, networking dinners, a customer exhibition, international roaming, a gift, a video-service/equipment contradiction, exceptional outage travel and mixed audio use. Their labels were fixed before inference.\n")
    add("## Routing rules and development-only selection\n")
    code(spec["candidates"])
    add(spec["selection_protocol"] + "\n")
    add("Routing source: [routing_analysis.py](routing_analysis.py), function `route`. A never changes the original J2 semantic outcome. UNRELATED routes to EXCLUDED_PURPOSE, INCONSISTENT to REVIEW, UNCLEAR to CLARIFY. Only a J2 SUPPORTED result can CONTINUE. B requires Noul >= selected threshold; a value <0.3 goes to REVIEW, other sub-threshold values to CLARIFY. C requires raw Score >= selected threshold, otherwise CLARIFY. D applies both gates. Failures/uncollected signals are API_FAILURE/NOT_MEASURED for required gates, never a semantic label. A high Score or Noul never overrides UNRELATED or INCONSISTENT. These are experimental routing labels, not payment decisions.\n")
    if data.get("selected_rule"):
        code(data["selected_rule"])
    else:
        add("**No routing rule has been selected from signal measurements yet.** Development candidate selection occurs after signal collection; the balanced candidate is shown below only as the registered planning default. No held-out requests should occur before routing_rule.json is frozen.\n")
    add("## Development and held-out comparisons\n")
    for split, groups in comparison["splits"].items():
        for group, result in groups.items():
            add(f"### {split}: {group}\n")
            table(["Config", "Planned", "Evaluable", "J2 false SUPPORTED", "False CONTINUE", "False CONTINUE cases", "Unnecessary holds", "Hold cases", "Clarify", "Review", "API failure", "Not measured"],
                  [[config, m["planned_trials"], m["evaluable_trials"], m["j2_false_supported"], m["false_continue_trials"], m["false_continue_cases"], m["unnecessary_hold_trials"], m["unnecessary_hold_cases"], m["route_counts"]["CLARIFY"], m["route_counts"]["REVIEW"], m["route_counts"]["API_FAILURE"], m["route_counts"]["NOT_MEASURED"]] for config, m in result["summaries"].items()])
            add("Common fully evaluable trial pairs (all four configurations available) prevent calling missing supplemental outputs an improvement. Do not subtract error-driven missing outcomes from baseline errors.\n")
            add("Qualitative J3 and conceptual J4 hypothesis checks (agreement with regions, not calibrated correctness):\n")
            code(result["hypothesis_checks"])
            add("The excluded-purpose contrast tests whether low qualifying evidence and high information sufficiency coexist. Such a contrast shows distinct measured semantics, but does not by itself justify another routing gate.\n")
            code(result["utility"])
            table(["Case", "Trial", "Expected J2", "Actual J2", "Noul", "Raw Score", "A", "B", "C", "D"],
                  [[r["case_id"], r["trial"], r["expected_j2"], r["j2"], r["j3"], r["j4"], *[r["routes"][c] for c in CONFIGS]] for r in result["trial_pairs"]])
    add("False CONTINUE means routing a J2 SUPPORTED prediction onward while its preregistered J2 hypothesis is not SUPPORTED. Unnecessary holds mean CLARIFY/REVIEW on expected-SUPPORTED cases; incremental holds count only new holds beyond A. Repeated trials are counted but distinct affected case IDs are reported. Probe results never enter primary selection or headline held-out metrics. An API error is an observed failure, not semantic UNCLEAR.\n")
    add("## Ambiguous office-event case J2-30\n")
    focus = [r for r in comparison["splits"]["development"]["primary"]["trial_pairs"] if r["case_id"] == "J2-30"]
    add("Invoice: Ola passenger cab journey. Explanation: 'Went to an event with people from my office.' Frozen J2 hypothesis: UNCLEAR. Historical J2 actually returned SUPPORTED in all three trials. This is unsupported inference of business purpose relative to the hypothesis; it does not establish what the employee really did. J3 hypothesis is AMBIGUOUS; J4 conceptual level is 1 because colleague attendance leaves work purpose unresolved.\n")
    code(focus)
    add("Check whether a gate holds this case without holding concise legitimate phone, broadband or fitness explanations. Catching it means requesting evidence/clarification, not discovering fraud or verifying a business event. If both supplemental questions pass it, they have not repaired the known limitation. If both hold it, shared catches do not prove Score adds value beyond Noul.\n")
    add("## Individual responses, hypotheses and repeatability\n")
    lookup = {(o["split"], o["case_id"], o["trial"], o["kind"]): o for o in data["observations"]}
    for split in ("development", "heldout"):
        rows = []
        for c in spec[split]["cases"]:
            for trial in range(1, 4):
                o = lookup.get((split, c["id"], trial, "signals"))
                n = (o or {}).get("outputs", {}).get("j3", {})
                s = (o or {}).get("outputs", {}).get("j4", {})
                na, sa = n.get("answer") or {}, s.get("answer") or {}
                nv, sv = na.get("noul"), sa.get("score")
                rows.append([c["id"], trial, nv, j3_region(nv) if nv is not None else None,
                             sv, j4_region(sv) if sv is not None else None, sa.get("confidence"), sa.get("probabilities"),
                             n.get("status", "not_run"), s.get("status", "not_run"), (o or {}).get("call", {}).get("latency_ms")])
        add(f"### {split}: Noul and Score trials\n")
        table(["Case", "Trial", "Raw Noul", "J3 region", "Raw Score", "J4 region", "Score confidence", "Score distribution", "J3 status", "J4 status", "Request ms"], rows)
    repeat_rows = []
    for split, groups in comparison["splits"].items():
        for group, result in groups.items():
            ids = list(dict.fromkeys(r["case_id"] for r in result["trial_pairs"]))
            for case_id in ids:
                rs = [r for r in result["trial_pairs"] if r["case_id"] == case_id]
                for config in CONFIGS:
                    values = [r["routes"][config] for r in rs]
                    stable = len(set(values)) == 1 if all(v not in ("API_FAILURE", "NOT_MEASURED") for v in values) else None
                    repeat_rows.append([split, group, case_id, config, values, stable])
    table(["Split", "Group", "Case", "Config", "Trial routes", "All 3 routes agree"], repeat_rows)
    add("Raw Noul/Score values and every distribution above remain separate observations, never averaged into a fabricated response. Matching routes can hide probability changes. Historical and new J2 individual Choice distributions, confidence and request timings are below.\n")
    baseline_rows = []
    for o in data["historical_j2"]:
        a = o.get("answer") or {}
        baseline_rows.append(["development (historical)", o["case_id"], o["trial"], o.get("outcome"), a.get("confidence"), a.get("probabilities"), o["call"]["latency_ms"], o["status"]])
    for o in data["observations"]:
        if o["kind"] == "j2":
            a = o["outputs"]["j2"].get("answer") or {}
            baseline_rows.append(["heldout (new)", o["case_id"], o["trial"], a.get("choice"), a.get("confidence"), a.get("probabilities"), o["call"]["latency_ms"], o["outputs"]["j2"]["status"]])
    table(["Baseline", "Case", "Trial", "Choice", "Confidence", "Full distribution", "Request ms", "Status"], baseline_rows)
    add("## Requests, latency, usage and failures\n")
    costs = []
    for split in ("development", "heldout"):
        for kind in ("signals", "j2"):
            observations = [o for o in data["observations"] if o["split"] == split and o["kind"] == kind]
            values = [o["call"]["latency_ms"] for o in observations]
            raw_usage = []
            for o in observations:
                try:
                    raw_usage.append(json.loads(o["call"]["http"]["body_text"]).get("usage", {}))
                except (TypeError, ValueError, KeyError):
                    pass
            recorded_costs = [u["cost"] for u in raw_usage if isinstance(u.get("cost"), (int, float))]
            costs.append([split, kind, len(observations), median(values) if values else None,
                          sum(u.get("input_tokens", 0) for u in raw_usage), sum(recorded_costs) if recorded_costs else None, len(recorded_costs)])
    table(["Split", "Request kind", "Attempts", "Median ms", "Recorded input tokens", "Recorded cost sum", "Requests with cost"], costs)
    add("J3/J4 share a request: per-question price and latency cannot be isolated from this run. B, C and D are offline ablations of shared signal responses, not separately benchmarked deployments. Do not claim measured Noul-only versus Score-only latency/cost. Historical development baseline latency is from a different run, so adding its time to new signals is not a paired causal timing experiment. Reported usage.cost is copied from HTTP bodies without inventing missing costs or assuming currency.\n")
    code({"blocking_reason": data.get("blocking_reason"), "pending_request": data.get("pending_request"),
          "execution_errors": data["execution_errors"],
          "preflights": [{"status": p["status"], "error": p.get("error"), "latency_ms": p["latency_ms"]} for p in data["preflights"]],
          "failed_outputs": [{"split": o["split"], "case_id": o["case_id"], "trial": o["trial"], "kind": o["kind"], "call_error": o["call"].get("error"), "output_errors": {k: v.get("error") for k, v in o["outputs"].items() if v["status"] != "ok"}} for o in data["observations"] if any(v["status"] != "ok" for v in o["outputs"].values())]})
    add("Full original input states, question objects, response model, HTTP bodies and safe response headers, IDs, provider, usage, confidence, statuses and errors remain in raw_results.json. Pending requests are checkpointed before sending and never silently reissued after an interruption. API failures stay failures. No authorization headers or credential values are saved.\n")
    table(["Split", "Case", "Trial", "Kind", "Started UTC", "HTTP", "Returned model", "Response ID", "Typed usage"],
          [[o["split"], o["case_id"], o["trial"], o["kind"], o["call"]["started_at"],
            (o["call"].get("http") or {}).get("status", (o["call"].get("error") or {}).get("status")),
            (o["call"].get("response") or {}).get("model"),
            (o["call"].get("http") or {}).get("headers", {}).get("x-generation-id"),
            (o["call"].get("response") or {}).get("usage")] for o in data["observations"]])
    add("## Architecture recommendation: five questions\n")
    held = comparison["splits"]["heldout"]["primary"]
    if data["status"] != "complete" or held["utility"]["common_evaluable_trials"] != 60:
        add("1. **Does Noul add beyond J2?** Not yet established on complete new evidence.\n2. **Does Score add beyond J2?** Not yet established.\n3. **Is Score distinct from Noul?** Conceptually yes (information sufficiency can be high for an excluded purpose); empirical incremental value remains unmeasured/incomplete.\n4. **Which configuration for V1?** Retain J2-only as the existing provisional baseline until this experiment supplies a complete comparison; no new primitive is justified by demonstration alone.\n5. **Before integration?** Complete the preregistered held-out evaluation, inspect false continues and unnecessary holds, and validate with independently labelled real examples. No FastAPI integration is built here.\n")
    else:
        u = held["utility"]
        common = u["common_configuration_summaries"]
        add(f"1. **Noul beyond J2:** held-out catches relative to frozen hypotheses: {u['counts']['noul_catches_false_support']} trial(s), cases {u['cases']['noul_catches_false_support']}; incremental legitimate holds: {common['B']['incremental_unnecessary_holds']}. A catch is a request to hold/review, not verification or semantic relabelling.\n")
        add(f"2. **Score beyond J2:** held-out catches: {u['counts']['score_catches_false_support']} trial(s), cases {u['cases']['score_catches_false_support']}; incremental legitimate holds: {common['C']['incremental_unnecessary_holds']}.\n")
        add(f"3. **Score beyond Noul:** D catches beyond B: {u['counts']['score_adds_beyond_noul']}, cases {u['cases']['score_adds_beyond_noul']}; extra legitimate holds: {u['counts']['score_extra_legitimate_hold_beyond_noul']}. Shared holds: {u['counts']['both_hold_same_false_support']}; both miss the same false support: {u['counts']['both_allow_same_false_support']}. A zero incremental catch provides no evidence to retain Score on top of Noul.\n")
        ranks = {"A": 0, "B": 1, "C": 1, "D": 2}
        # A conservative evidence screen, not another tuned held-out routing rule.
        acceptable = [c for c in CONFIGS if common[c]["false_continue_trials"] < common['A']["false_continue_trials"] and common[c]["unnecessary_hold_trials"] == common['A']["unnecessary_hold_trials"]]
        best = min(acceptable, key=lambda c: (common[c]["false_continue_trials"], ranks[c], c)) if acceptable else "A"
        add(f"4. **Provisional V1 choice: {best}.** This recommendation uses an explicitly conservative screen: fewer held-out false continues with no increase in legitimate holds, preferring fewer judgments. If no supplemental configuration meets it, retain A and document unresolved false support rather than assume added complexity helps. This is post-evaluation architecture assessment, not threshold tuning or proof of production accuracy.\n")
        add("5. **Before FastAPI integration:** obtain independent labels and broader policy-edge cases, set operational review/error tolerance, validate confidence calibration separately if needed, and inspect provider failure and clarification handling. No workflow or external truth verification was tested.\n")
    add("## Limitations and reproducibility\n")
    add("The development baseline and its known error were already observed before designing these supplemental questions; development improvements are exploratory and may overfit. The 20 new scenarios are manually authored by the same experimenter and frozen before inference, not an external blind benchmark. Policy interpretation of social events and mixed uses can be debatable; frozen hypotheses remain unchanged. Three repeats are correlated measurements, not 156 independent purchases. Model/cache effects and shared evidence correlate judgments. Pairing trial IDs for historical J2 and newly collected signals is a bookkeeping comparison of the same state, not simultaneous sampling or a causal intervention. Routing can catch a prediction relative to a hypothesis or ask for information; it does not correct financial eligibility or verify underlying employee behavior. No probability is claimed calibrated.\n")
    add("Run `experiment_j3_j4.py` to collect; `--prepare-only` freezes with no model calls; `--report-only` regenerates artifacts with no calls. A completed run is never repeated automatically. Original J1/J2 policies, expectations and raw files are read-only inputs. New held-out labels/rules are not adjusted after inference. A future changed hypothesis requires a new separately identified experiment, not relabelling this set.\n")
    add("References: [official Score behavior](https://docs.typesafe.ai/primitives/score), [mixed question types](https://docs.typesafe.ai/api/system-one), [SDK question schema](https://docs.typesafe.ai/sdk/python/api/types/questions). Runtime schema/signature evidence is preserved in preregistered.json.\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
