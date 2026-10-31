"""Offline descriptive analysis; cutoffs are derived after development observations."""
from collections import Counter
import json
from statistics import mean, median


def auc(scores, events):
    positives = [s for s, e in zip(scores, events) if e]
    negatives = [s for s, e in zip(scores, events) if not e]
    if not positives or not negatives:
        return None
    return mean(1 if p > n else .5 if p == n else 0 for p in positives for n in negatives)


def choice_metrics(answer, expected=None):
    p = answer["probabilities"]
    ordered = sorted(p.values(), reverse=True)
    label = answer["choice"]
    return {"choice": label, "selected_probability": p[label], "top_two_margin": ordered[0]-ordered[1],
            "confidence": answer.get("confidence"), "routing_alternatives": {k: p.get(k) for k in ("UNCLEAR", "UNRELATED", "INCONSISTENT")},
            "error": label != expected if expected is not None else None,
            "brier": sum((v-int(k == expected))**2 for k, v in p.items()) if expected in p else None}


def score_metrics(answer, expected):
    p = {int(k): v for k, v in answer["probabilities"].items()}
    value = answer["score"]
    return {"score": value, "nearest_anchor": min(range(3), key=lambda k: abs(value-k)),
            "absolute_error": abs(value-expected), "expected_level_probability": p[expected],
            "competing_probability_mass": 1-p[expected], "confidence": answer.get("confidence"),
            "probabilities": p, "expected_level": expected}


def data_cutoffs(values):
    unique = sorted(set(values))
    mids = [(a+b)/2 for a, b in zip(unique, unique[1:])]
    if not mids:
        return {"cutoffs": [], "case_values": values, "limitation": "No varying successful case-median outputs; no sensitivity cutoff derived."}
    positions = {round((len(mids)-1)*q) for q in (.25, .5, .75)}
    return {"cutoffs": [mids[i] for i in sorted(positions)], "case_values": values,
            "limitation": "Exploratory development-derived cutoffs only; no calibrated or selected deployment threshold."}


def lookup(data):
    return {(o["case_id"], o["trial"], o["kind"]): o for o in data["observations"]}


def derive_sensitivity_plan(data):
    spec = data["preregistration"]["specification"]
    found = lookup(data)
    values = {"exceptional_commute": [], "charged_mobile_extra": [], "score": []}
    incomplete = []
    for family, dataset in spec["fixtures"].items():
        for c in dataset["cases"]:
            if c["split"] != "development" or (family == "j3" and not c["applicable"]):
                continue
            kind, field = ("noul", "noul") if family == "j3" else ("score", "score")
            obs = [found.get((c["id"], t, kind)) for t in (1, 2, 3)]
            if not all(o and o["status"] == "ok" for o in obs):
                incomplete.append(c["id"])
                continue
            values[c["proposition"] if family == "j3" else "score"].append(median(o["answer"][field] for o in obs))
    return {"source_scope": "Successful three-trial development case medians only; no held-out values or labels used.",
            "candidates": {k: data_cutoffs(v) for k, v in values.items()}, "incomplete_development_cases": incomplete,
            "selection": "Sensitivity comparison only. No winning or production threshold is selected on held-out results."}


def base_route(label):
    return {"SUPPORTED": "CONTINUE", "UNCLEAR": "NEED_INFO", "INCONSISTENT": "HUMAN_REVIEW", "UNRELATED": "POLICY_RESTRICTION"}.get(label)


def j3_route(context, label, probability, cutoff, mode="positive_only", failed=False):
    if not context["j2_meaningful"]:
        return "NEED_INFO"  # Fixture-established one-item/category precondition, not a Noul inference.
    baseline = base_route(label)
    if baseline is None:
        return "HUMAN_REVIEW" if failed else None
    if baseline != "CONTINUE" or not context["applicable"]:
        return baseline
    if probability is None:
        return "HUMAN_REVIEW" if failed else None
    if context["proposition"] == "exceptional_commute":
        return "CONTINUE" if probability >= cutoff else "NEED_INFO"
    if probability >= cutoff:
        return "RESTRICT_SEPARATE_COMPONENT"  # Does not reject underlying cellular service.
    return "NEED_INFO" if mode == "conservative" else "CONTINUE"


def revision_route(value, cutoff, failed=False):
    if value is None:
        return "HUMAN_REVIEW" if failed else None
    return "CONTINUE" if value >= cutoff else "HUMAN_REVIEW"


def historical_analysis(folder):
    sources = {}
    for filename in ("j1_v1.json", "j1_v2.json", "j2_results.json"):
        raw = json.loads((folder / filename).read_text(encoding="utf-8"))
        rows = []
        if filename == "j2_results.json":
            for o in raw["observations"]:
                if o["status"] == "ok":
                    rows.append({"case_id": o["case_id"], "trial": o["trial"], "group": o["evaluation_group"],
                                 **choice_metrics(o["answer"], o["expected_outcome"]), "distribution": o["answer"]["probabilities"]})
        elif filename == "j1_v2.json":
            for o in raw["observations"]:
                for call in o["result"].get("calls", []):
                    a = (call.get("response") or {}).get("answers", {}).get("category")
                    if a:
                        rows.append({"case_id": o["case_id"], "trial": o["trial"], "approach": o["approach"],
                                     **choice_metrics(a, o["expected_category"]), "distribution": a["probabilities"]})
        else:
            for c in raw["rows"]:
                for approach in ("A", "B"):
                    for call in c[approach].get("calls", []):
                        a = (call.get("response") or {}).get("answers", {}).get("category")
                        if a:
                            rows.append({"case_id": c.get("id", c["description"]), "trial": c.get("trial"), "approach": approach,
                                         **choice_metrics(a, c["hypothesis"]), "distribution": a["probabilities"]})
        events = [r["error"] for r in rows]
        sources[filename] = {"choice_response_count": len(rows), "errors": sum(events),
                            "mean_brier": mean(r["brier"] for r in rows) if rows else None,
                            "low_confidence_error_detection_auc": auc([-r["confidence"] for r in rows], events) if rows else None,
                            "low_margin_error_detection_auc": auc([-r["top_two_margin"] for r in rows], events) if rows else None,
                            "rows": rows}
    sources["office_event_error"] = [r for r in sources["j2_results.json"]["rows"] if r["case_id"] == "J2-30"]
    return sources


def gate_comparisons(data):
    spec = data["preregistration"]["specification"]
    plan = data.get("sensitivity_plan")
    if not plan:
        return {"status": "No routing cutoffs before development observations; not measured.", "j3": [], "j4": []}
    found = lookup(data)
    output = {"status": "Frozen development-derived sensitivity analysis; no deployment cutoff selected.", "j3": [], "j4": []}
    for c in spec["fixtures"]["j3"]["cases"]:
        cuts = plan["candidates"][c["proposition"]]["cutoffs"] if c["applicable"] else [None]
        modes = ("positive_only", "conservative") if c["proposition"] == "charged_mobile_extra" and c["applicable"] else ("positive_only",)
        for t in (1, 2, 3):
            n, b = found.get((c["id"], t, "noul")), found.get((c["id"], t, "choice"))
            p = n["answer"]["noul"] if n and n["status"] == "ok" else None
            label = b["answer"]["choice"] if b and b["status"] == "ok" else None
            failed = any(o and o["status"] != "ok" for o in (n, b))
            for cut in cuts:
                for mode in modes:
                    route = j3_route(c, label, p, cut, mode, failed)
                    expected = c["expected_evidence_state"]
                    output["j3"].append({"case_id": c["id"], "split": c["split"], "trial": t, "proposition": c["proposition"],
                        "cutoff": cut, "mode": mode, "j2": label, "noul": p, "baseline_route": base_route(label), "route": route,
                        "quality": "failed" if failed else "measured" if (b or not c["j2_meaningful"]) and (n or not c["applicable"]) else "not_run",
                        "purpose_false_continue": route == "CONTINUE" and c["j2_meaningful"] and c["expected_j2"] != "SUPPORTED",
                        "unnecessary_hold": not failed and route in ("NEED_INFO", "HUMAN_REVIEW") and c["expected_j2"] == "SUPPORTED" and expected in ("EXPLICITLY_PRESENT", "EXPLICITLY_ABSENT", "NOT_APPLICABLE"),
                        "missed_separate_component_flag": c["proposition"] == "charged_mobile_extra" and expected == "EXPLICITLY_PRESENT" and route == "CONTINUE",
                        "unknown_component_continue": c["proposition"] == "charged_mobile_extra" and expected == "UNKNOWN" and route == "CONTINUE",
                        "incorrect_component_restriction": c["proposition"] == "charged_mobile_extra" and expected == "EXPLICITLY_ABSENT" and route == "RESTRICT_SEPARATE_COMPONENT"})
    for c in spec["fixtures"]["j4"]["cases"]:
        for t in (1, 2, 3):
            o = found.get((c["id"], t, "score"))
            a = o["answer"] if o and o["status"] == "ok" else None
            for cut in plan["candidates"]["score"]["cutoffs"]:
                r = revision_route(a["score"] if a else None, cut, bool(o and o["status"] != "ok"))
                output["j4"].append({"case_id": c["id"], "split": c["split"], "trial": t, "cutoff": cut, "route": r,
                    "quality": "measured" if a else "failed" if o else "not_run", "claim_approved": False,
                    "continue_means": "Clarification is resolved enough to reassess purpose/consistency, not approval.",
                    "false_resolution_continue": r == "CONTINUE" and c["expected_level"] < 2,
                    "unnecessary_hold": r == "HUMAN_REVIEW" and bool(a) and c["expected_level"] == 2,
                    "rubric_mass_below_cutoff": sum(v for k, v in a["probabilities"].items() if int(k) < cut) if a else None})
    return output


def summarize(data, reference_folder):
    spec = data["preregistration"]["specification"]
    found = lookup(data)
    result = {"status": data["status"], "j3": [], "j4": [], "historical": historical_analysis(reference_folder),
              "sensitivity": gate_comparisons(data), "request_attempts": len(data["observations"]),
              "api_errors": sum(o["call"]["status"] != "ok" for o in data["observations"]),
              "output_errors": sum(o["status"] != "ok" for o in data["observations"])}
    for family, ds in spec["fixtures"].items():
        for c in ds["cases"]:
            for t in (1, 2, 3):
                if family == "j3":
                    n, b = found.get((c["id"], t, "noul")), found.get((c["id"], t, "choice"))
                    a = b["answer"] if b and b["status"] == "ok" else None
                    result["j3"].append({"case_id": c["id"], "split": c["split"], "trial": t, "proposition": c["proposition"],
                        "expected_evidence_state": c["expected_evidence_state"], "applicable": c["applicable"],
                        "noul_status": n["status"] if n else "not_applicable" if not c["applicable"] else "not_run",
                        "noul": n["answer"]["noul"] if n and n["status"] == "ok" else None,
                        "choice_status": b["status"] if b else "not_applicable" if not c["j2_meaningful"] else "not_run",
                        "choice": choice_metrics(a, c["expected_j2"]) if a else None,
                        "distribution": a["probabilities"] if a else None})
                else:
                    o = found.get((c["id"], t, "score"))
                    m = score_metrics(o["answer"], c["expected_level"]) if o and o["status"] == "ok" else None
                    result["j4"].append({"case_id": c["id"], "split": c["split"], "trial": t, "expected_level": c["expected_level"],
                        "acceptable_levels": c["acceptable_levels"], "status": o["status"] if o else "not_run", "metrics": m,
                        "borderline_acceptable": m["nearest_anchor"] in c["acceptable_levels"] if m else None,
                        "revised_purpose_expectation": c["revised_purpose_expectation"]})
    groups = []
    for split in ("development", "heldout"):
        for proposition in ("exceptional_commute", "charged_mobile_extra"):
            rs = [r for r in result["j3"] if r["split"] == split and r["proposition"] == proposition and r["noul"] is not None]
            medians = {}
            for r in rs:
                medians.setdefault((r["case_id"], r["expected_evidence_state"]), []).append(r["noul"])
            pairs = [(median(v), state) for (_, state), v in medians.items()]
            groups.append({"split": split, "proposition": proposition, "measured_trials": len(rs),
                "state_case_medians": {state: [v for v, s in pairs if s == state] for state in ("EXPLICITLY_PRESENT", "EXPLICITLY_ABSENT", "UNKNOWN")},
                "present_vs_nonpresent_case_auc": auc([v for v, _ in pairs], [s == "EXPLICITLY_PRESENT" for _, s in pairs])})
    result["noul_separation"] = groups
    result["score_summary"] = {}
    result["choice_uncertainty"] = {}
    for split in ("development", "heldout"):
        rs = [r for r in result["j4"] if r["split"] == split and r["metrics"]]
        result["score_summary"][split] = {"measured": len(rs),
            "mean_absolute_error": mean(r["metrics"]["absolute_error"] for r in rs) if rs else None,
            "nearest_anchor_agreement": sum(r["metrics"]["nearest_anchor"] == r["expected_level"] for r in rs) if rs else None,
            "predeclared_borderline_agreement": sum(r["borderline_acceptable"] for r in rs) if rs else None,
            "low_confidence_anchor_error_auc": auc([-r["metrics"]["confidence"] for r in rs], [r["metrics"]["nearest_anchor"] != r["expected_level"] for r in rs]) if rs else None}
        choices = [r["choice"] for r in result["j3"] if r["split"] == split and r["choice"]]
        result["choice_uncertainty"][split] = {"measured": len(choices),
            "errors": sum(c["error"] for c in choices) if choices else None,
            "baseline_false_supported": sum(r["choice"]["choice"] == "SUPPORTED" and r["choice"]["error"] for r in result["j3"] if r["split"] == split and r["choice"]) if choices else None,
            "mean_confidence_on_errors": mean(c["confidence"] for c in choices if c["error"]) if any(c["error"] for c in choices) else None,
            "mean_confidence_on_agreements": mean(c["confidence"] for c in choices if not c["error"]) if any(not c["error"] for c in choices) else None,
            "low_confidence_error_auc": auc([-c["confidence"] for c in choices], [c["error"] for c in choices]) if choices else None,
            "low_margin_error_auc": auc([-c["top_two_margin"] for c in choices], [c["error"] for c in choices]) if choices else None}
    return result


def write_report(data, summary, path):
    spec = data["preregistration"]["specification"]
    lines = []
    def add(s=""):
        lines.append(s)
    def code(v):
        add("```json\n"+json.dumps(v, indent=2, ensure_ascii=False)+"\n```\n")
    def table(headers, rows):
        add("| "+" | ".join(headers)+" |")
        add("| "+" | ".join("---" for _ in headers)+" |")
        for row in rows:
            add("| "+" | ".join(str(v).replace("|", "\\|").replace("\n", " ") for v in row)+" |")
        add()
    add("# Policy-specific Noul and revision-specific Score experiments\n")
    add(f"Status: **{data['status']}**; {summary['request_attempts']}/{spec['expected_request_count']} planned inference requests attempted. No missing observations are invented.\n")
    add("## Scope, isolation and reproducibility\n")
    add("This new directory contains copied SDK/J2 helpers and copied historical data. No checked-in predecessor is imported or modified. COPY_PROVENANCE.json records original tracked-file and copied-source hashes. No application, UI, financial calculations or employee-truth verification is implemented.\n")
    add(f"Frozen at `{data['preregistration']['created_at']}`; specification SHA-256 `{data['specification_sha256']}`. SDK {spec['sdk_version']}, exact model `{spec['model']}`, gateway `{spec['base_url']}`; timeout 30 seconds, retries disabled.\n")
    add("18 J3 fixtures and 22 J4 fixtures each have three planned trials. Three J3 fixtures deliberately skip Noul as inapplicable; two also skip J2 because the one-item/category precondition fails. Client-premises travel still receives a valid J2 comparison without an exceptional-commute Noul. There are 45 Noul + 48 Choice + 66 Score planned requests: 159 total. Requests are independent and see no previous answer or expected annotation.\n")
    add(spec["applicability_protocol"]+"\n")
    add("## Exact questions and actual SDK representation\n")
    add("Noul supplies only a proposition probability; low values do not inherently distinguish explicitly absent, unknown and not applicable. Those are evaluation annotations, not parsed outputs. J3-A is scoped to fixture-confirmed home-to-regular-office travel. J3-B sees only the invoice description and category, while J3-A and valid J2 see the three original evidence fields.\n")
    add("Score accepts an ordered list of three descriptions and returns a fractional expected position in [0,2], a distribution over levels, a legend and confidence. It does not promise an integer. The nearest anchor is an offline descriptive interpretation (ties to the lower anchor), not a model output or routing threshold. Raw values and full distributions are retained.\n")
    code(spec["sdk_signatures"])
    # Deduplicate identical question objects while retaining exact per-case objects in preregistration/raw requests.
    unique = {}
    for case_id, kinds in spec["questions"].items():
        for kind, objects in kinds.items():
            key = json.dumps(objects, sort_keys=True)
            unique.setdefault(key, {"kind": kind, "case_ids": [], "questions": objects})["case_ids"].append(case_id)
    for record in unique.values():
        code(record)
    add("## Preregistered fixtures\n")
    for family, ds in spec["fixtures"].items():
        add(f"### {family.upper()}\n")
        code(ds)
    add("The mobile fixtures identify the claimed cellular line separately from invoice context. J2 can correctly return SUPPORTED for that purpose while a separate entertainment component exists. Flagging that component is not catching a J2 purpose misclassification, denying the whole plan, or computing eligible money. Price above INR 750 is deliberately not assessed by Jev.\n")
    add("## Actual per-case trial outputs\n")
    table(["Case", "Split", "Trial", "Expected evidence state", "Noul status", "Raw Noul", "J2 status", "Choice metrics", "Full Choice distribution"],
          [[r["case_id"], r["split"], r["trial"], r["expected_evidence_state"], r["noul_status"], r["noul"], r["choice_status"], r["choice"], r["distribution"]] for r in summary["j3"]])
    table(["Case", "Split", "Trial", "Expected level", "Status", "Score metrics and distribution", "Predeclared borderline agreement"],
          [[r["case_id"], r["split"], r["trial"], r["expected_level"], r["status"], r["metrics"], r["borderline_acceptable"]] for r in summary["j4"]])
    add("## Probability separation and resolution error\n")
    code(summary["noul_separation"])
    code(summary["score_summary"])
    code(summary["choice_uncertainty"])
    add("Noul AUC is a descriptive pairwise rank statistic on case medians, explicitly separating unknown from absent in the tables. It is not a calibration or verified correctness measure. Score absolute error is measured against the fixed primary anchor; acceptable alternative anchors were declared before inference, not added after. Competing-level mass is reported numerically without inventing a substantial-uncertainty boundary.\n")
    add("## Threshold sensitivity: development then held-out\n")
    add(spec["selection_protocol"]+"\n")
    code(data["sensitivity_plan"])
    if not data["sensitivity_plan"]:
        add("**No numerical routing cutoffs have been introduced.** New development model outputs have not yet supplied a sensitivity plan. Gates and held-out comparisons are unmeasured.\n")
    add("Routing is offline Python in analysis.py. Only fixture-supplied applicability/preconditions and actual outputs enter route functions; expected evidence states are used only to evaluate them. J2 UNRELATED remains an explicit POLICY_RESTRICTION and INCONSISTENT remains HUMAN_REVIEW even with a positive Noul. Low commute Noul requests information, never proves an ordinary commute. For mobile: positive-only flags high detected separate components but may continue on unresolved charging evidence; conservative mode holds everything not confidently flagged, potentially over-holding explicit complimentary/no-extra cases. Neither mode recovers the four evidence states from a scalar.\n")
    add("High revision Score continues only to purpose/consistency reassessment; it never approves a claim. Low Score after a revision escalates to HUMAN_REVIEW (the eventual Benefits Team path), not denial or an accusation of dishonesty.\n")
    sensitivity = summary["sensitivity"]
    for family in ("j3", "j4"):
        rows = sensitivity[family]
        groups = {}
        for r in rows:
            key = (r["split"], r.get("proposition", "revision_resolution"), r["cutoff"], r.get("mode", "escalate_after_revision"))
            groups.setdefault(key, []).append(r)
        headers = ["Split", "Proposition", "Cutoff", "Mode", "Measured trials", "False continues", "Unnecessary holds", "Other safety counts", "Routes"]
        rendered = []
        for key, rs in groups.items():
            measured = [r for r in rs if r["quality"] == "measured"]
            false_key = "purpose_false_continue" if family == "j3" else "false_resolution_continue"
            other = {k: sum(r.get(k, False) for r in measured) for k in ("missed_separate_component_flag", "unknown_component_continue", "incorrect_component_restriction")}
            rendered.append([*key, len(measured), sum(r[false_key] for r in measured) if measured else None,
                             sum(r["unnecessary_hold"] for r in measured) if measured else None, other, dict(Counter(r["route"] for r in rs))])
        table(headers, rendered)
    add("Full per-case/per-trial gate outputs, cumulative rubric mass below each cutoff, and baseline J2 routes are in evaluation_summary.json. 'False continue' here means a routing disagreement with a fixture, not a verified wrong payment. Unknown mobile-component continues and missed extra flags are separately counted; they are not mislabeled as false J2 purpose support. API failures are excluded from semantic error rates, shown as failures, and cannot count as a successful catch.\n")
    add("## Confidence and competing probabilities in historical J1/J2\n")
    historical = summary["historical"]
    code(historical["office_event_error"])
    for name, record in historical.items():
        if isinstance(record, dict):
            code({"source": name, **{k: v for k, v in record.items() if k != "rows"}})
    add("The historical office-event errors had confidence 0.43, 0.35 and 0.35, selected-label probability 0.57, 0.51 and 0.51, and UNCLEAR probability 0.43, 0.49 and 0.49. Confidence is not the winning probability. Close competition and modest confidence could flag this case descriptively; that observation alone does not establish a deployable confidence cutoff or prove incremental benefit from a new judgment. Historical sources and policies differ and are not pooled. All historical per-response measures remain in evaluation_summary.json. AUC is not estimable when a source has no errors or no correct decisions. Brier values are descriptive on fictional expected labels, not externally validated calibration.\n")
    add("## Repetition, timing, metadata and failures\n")
    repetitions = []
    for family, ds in spec["fixtures"].items():
        for c in ds["cases"]:
            for kind in ((["noul"] if c["applicable"] else []) + (["choice"] if c["j2_meaningful"] else []) if family == "j3" else ["score"]):
                obs = [o for o in data["observations"] if o["case_id"] == c["id"] and o["kind"] == kind]
                good = [o for o in sorted(obs, key=lambda o: o["trial"]) if o["status"] == "ok"]
                field = {"noul": "noul", "score": "score", "choice": "choice"}[kind]
                values = [o["answer"][field] for o in good]
                repetitions.append([c["id"], kind, len(good), values, len(set(values)) == 1 if len(good) == 3 else None,
                                    median(o["call"]["latency_ms"] for o in obs) if obs else None])
    table(["Case", "Kind", "Successful /3", "Individual outputs", "Exactly equal all 3", "Median request ms"], repetitions)
    ledger = []
    for o in data["observations"]:
        c = o["call"]
        raw = c.get("http") or {}
        body = {}
        if raw.get("body_text"):
            try:
                body = json.loads(raw["body_text"])
            except ValueError:
                pass
        ledger.append([o["case_id"], o["trial"], o["kind"], o["status"], raw.get("status", (c.get("error") or {}).get("status")),
                       c["latency_ms"], (c.get("response") or {}).get("model"), body.get("id"), body.get("usage"),
                       c.get("error") or o.get("interpretation_error")])
    table(["Case", "Trial", "Kind", "Status", "HTTP", "Latency ms", "Returned model", "ID", "Usage/cost", "Error"], ledger)
    code({"api_errors": summary["api_errors"], "output_errors": summary["output_errors"], "execution_errors": data["execution_errors"],
          "blocking_reason": data.get("blocking_reason"), "pending_request": data["pending_request"],
          "preflights": [{"status": p["status"], "error": p.get("error"), "latency_ms": p["latency_ms"]} for p in data["preflights"]]})
    add("Raw request states, exact questions, complete typed answers and original HTTP bodies, model identity, safe response headers, usage, confidence, errors and latency remain in results/raw_results.json. Noul has no invented confidence/distribution. Source snapshots and all individual observations are retained; medians are descriptive statistics, not fabricated averaged model responses.\n")
    add("## Findings and architecture recommendation\n")
    if data["status"] != "complete":
        add("New inference is not complete, so no evidence-based claim about which proposition works best or Score reliability is available. Keep both new roles experimental/diagnostic until the registered run is inspected. The copied historical confidence evidence is actual evidence, not a substitute for these new runs. No numerical deployment threshold or mandatory new question is recommended.\n")
    else:
        ranked = [g for g in summary["noul_separation"] if g["split"] == "heldout" and g["present_vs_nonpresent_case_auc"] is not None]
        if ranked:
            best = max(g["present_vs_nonpresent_case_auc"] for g in ranked)
            add(f"Best observed held-out affirmative/nonaffirmative case-rank separation: {[(g['proposition'], g['present_vs_nonpresent_case_auc']) for g in ranked if g['present_vs_nonpresent_case_auc'] == best]}. This descriptive ranking alone does not establish better routing or distinction between unknown and explicitly absent.\n")
        add(f"J2 comparison errors by split: {[(k, v['errors'], v['measured']) for k, v in summary['choice_uncertainty'].items()]}. If the held-out baseline has no false SUPPORTED outputs, fewer such errors cannot be demonstrated on that set. A separately charged component flag may still add invoice-condition information without correcting a purpose label.\n")
        add("Review the separate development/held-out tables and every error. Noul's best-supported scope is the proposition for which affirmative versus explicitly absent case-median separation is observed without unacceptable holds. It cannot, by itself, classify unknown versus absent; any mobile-extra automation still needs explicit billing context/clarification. Compare J2's purpose errors separately from component flags so a correct purpose answer is not called wrong.\n")
        for split in ("development", "heldout"):
            rs = [r for r in summary["j4"] if r["split"] == split and r["metrics"]]
            excluded = [r for r in rs if r["revised_purpose_expectation"] == "UNRELATED"]
            add(f"- {split}: Score MAE {summary['score_summary'][split]['mean_absolute_error']}; resolved-anchor results for explicit exclusions: {[(r['case_id'], r['trial'], r['metrics']['score']) for r in excluded]}. These answers may be resolved while still excluded.\n")
        add("Do not finalize a gate solely from a small held-out sensitivity table. The study supports at most conditional use for the scoped condition or specific clarification being assessed. Retain purpose/consistency reassessment after any high resolution score and human escalation for unresolved revisions. If no frozen candidate avoids false continues and unnecessary holds, this dataset does not support a reliable operating threshold. Do not retain either primitive merely to demonstrate it.\n")
    add("## Limitations and future implementation boundaries\n")
    add("This is a compact fictional, author-labelled dataset. Several development anchors are task examples; held-out variants are not externally blind validation. Repeated trials share underlying evidence and provider/cache effects. Borderline expectations were declared before inference; disagreement does not justify rewriting them. Applicability is supplied by fixtures, not solved by this experiment. The app must eventually identify/confirm the claimed journey/line and scope, clarify ambiguous billing, and distinguish an employee revision from verified invoice evidence. Contradictions in revisions may be fully responsive while still requiring review. Financial arithmetic, caps, excluded-charge subtraction, claim approval, UI, revision persistence and Benefits Team messaging remain outside scope. No verified dishonesty, financial correctness or calibrated real-world certainty is inferred.\n")
    add("The confidence analysis is descriptive, including retrospective inspection of an already-known office-event error. Do not call it independent calibration or a causal error-prevention experiment. Routing uses only new model outputs and allowed applicability context; expectation fields never enter model requests. Sensitivity candidates are derived after development observations and frozen before held-out collection. No held-out optimization or selected deployment cutoff is performed.\n")
    add("Run instructions are in README.md. Original task: TASK.md. SDK evidence is in preregistered.json. References: [Score behavior](https://docs.typesafe.ai/primitives/score), [question types](https://docs.typesafe.ai/sdk/python/api/types/questions).\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
