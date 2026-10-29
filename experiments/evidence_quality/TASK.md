# Task: Implement and Run J3 + J4 Jev Experiments — Noul and Score

## 1. Project context

We are building a small employee expense reimbursement auditing system to learn effective semantic decision modeling using Jev (TypeSafe AI).

Our guiding architecture is:

- **Invoice:** Establishes what product or service was purchased.
- **Employee explanation:** Establishes the claimed purpose.
- **Jev:** Interprets semantic evidence against reimbursement policies.
- **Python:** Performs deterministic calculations, policy enforcement, and workflow routing.
- **Human reviewer:** Resolves cases that cannot be handled confidently.

One reimbursement claim targets one specific invoice item or service.

We have already completed:

**J1 — Category validation**

- Compared Noul-first against Choice-first.
- Selected Choice-first for application V1.
- J1 uses the invoice item description without the employee's justification.
- It distinguishes eligible candidate categories, `OTHER`, `INSUFFICIENT_INFORMATION`, and `MIXED_ITEMS`.

**J2 — Purpose alignment**

- Implemented one Jev Choice question.
- Outcomes: `SUPPORTED`, `UNRELATED`, `UNCLEAR`, `INCONSISTENT`.
- Evaluated 32 cases, three trials each.
- Primary cases achieved 84/87 agreement with preregistered expected labels.
- Three disagreements came from the same ambiguous transport case:

  Invoice: Ola passenger cab journey.

  Explanation: "Went to an event with people from my office."

  Expected: `UNCLEAR`.

  Observed: `SUPPORTED` in all three trials.

  This was an unsupported inference of business purpose, not evidence that the event was actually business-related.

The exact existing J2 records and reports are the source of truth. Verify these summary details against the files before relying on them.

## 2. Objective

Investigate whether adding two narrowly defined Jev judgments improves semantic evidence assessment:

- **J3 — Noul:** Is the essential qualifying-purpose evidence explicitly established?
- **J4 — Score:** How sufficiently informative is the explanation for assessing its claimed purpose?

Compare four configurations:

1. J2 alone.
2. J2 + J3.
3. J2 + J4.
4. J2 + J3 + J4.

We want to determine whether the additional questions reduce unsupported `SUPPORTED` decisions without unnecessarily delaying legitimate reimbursement claims.

The objective is not to maximize the number of Jev questions. If either judgment duplicates J2 or the other new judgment, recommend removing it.

## 3. Preserve existing reimbursement policy

Reuse the exact fictional reimbursement policy definitions from the completed J2 experiment.

Do not silently modify them.

The categories remain:

- `WELLNESS`: ₹30,000 annual allowance. Fitness products, sports shoes, workout apparel, fitness trackers, AirPods/headphones for exercise, gym memberships, personal training, non-medical meditation and wellness services. The employee must identify a qualifying own-use wellness purpose.
- `SMARTPHONE`: ₹1,00,000 annual allowance. Smartphone handsets; ordinary employee own use is sufficient. No invented business-use requirement.
- `BROADBAND`: ₹3,000 monthly allowance. Home fixed broadband/fiber service; home connectivity is sufficient without work-from-home proof.
- `MOBILE_BILL`: ₹750 monthly allowance. Cellular service. Complimentary bundled Netflix does not disqualify the plan; separately charged entertainment is excluded.
- `BUSINESS_HOTEL`: No fixed cap. Client visits, company training, workshops, offsites and legitimate work-related accommodation qualify. A meaningful explanation is sufficient without external verification.
- `BUSINESS_TRANSPORT`: No fixed cap. Client visits, business travel, transporting clients, work-related events, and exceptional office travel for a specific business requirement qualify. Ordinary daily commuting does not.

Do not evaluate allowance limits or financial eligibility in these experiments.

Do not infer employee gender, purchase ownership or dishonesty from product labels.

## 4. J3 — Noul: Essential purpose evidence

Implement a Jev Noul proposition asking whether the employee's explanation actually establishes the qualifying purpose required by the applicable policy.

The proposition must be affirmative, narrow and policy-specific.

General formulation:

"Based on the invoice item, employee explanation, and applicable reimbursement policy, the explanation explicitly establishes a qualifying purpose for this purchase or service without relying on unstated facts."

Here, "explicitly establishes" means that the required purpose can reasonably be understood from the employee's words. It does not mean the explanation must be lengthy or contain formal policy terminology.

Examples:

**Wellness**

Nike Running Shoes — "For daily running."

Expected: Strong support.

AirPods — "Personal use."

Expected: Weak support because wellness purpose is missing.

**Business transport**

Uber — "Travelled to a client meeting."

Expected: Strong support.

Ola — "Went to an event with people from my office."

Expected: Weak or uncertain support because an event involving colleagues is not necessarily work-related.

Uber — "My usual commute from home to office."

Expected: Low support because the explanation establishes an excluded purpose.

**Business hotel**

Hotel accommodation — "Stayed for internal company training."

Expected: Strong support.

Hotel accommodation — "Stayed overnight in Bengaluru."

Expected: Weak support because business purpose is not established.

**Smartphone**

iPhone — "My new phone."

Expected: Strong support under our own-use policy.

Do not demand professional use where no such requirement exists.

**Important:** Noul does not verify whether the employee is truthful. It evaluates whether the provided explanation supports the proposition.

Record the returned Noul probability exactly. Do not treat it as a calibrated correctness probability.

## 5. J4 — Score: Explanation sufficiency

Implement one Jev Score judgment evaluating how sufficiently informative the employee's explanation is to assess its stated purpose under the applicable policy.

This must not be a score of:

- Reimbursement correctness.
- Fraud risk.
- Policy eligibility.
- J2 or J3 accuracy.
- Employee honesty.
- Explanation length or writing quality.

Use an anchored, ordered 0–2 sufficiency scale conceptually:

**0 — No usable purpose information**

The explanation does not meaningfully identify why the item or service was purchased.

Example: "Needed it."

**1 — Partial purpose information**

The explanation provides relevant context but leaves an essential detail unresolved.

Example: "Went to an event with people from my office."

**2 — Sufficient purpose information**

The explanation identifies the purpose clearly enough to assess it against the policy.

Examples:

- "For daily running."
- "Travelled to a client meeting."
- "My new phone."
- "Stayed overnight for internal company training."

An explanation can be sufficiently informative even when it describes an excluded purpose.

For example:

"My ordinary daily commute to the office."

This should score as sufficiently informative, because the purpose is clear, even though J2 should classify it as `UNRELATED`.

**This distinction is critical.**

J4 measures information sufficiency, not whether the stated purpose is permissible.

Before implementing Score, inspect the installed SDK's actual Score schema, expected output type, instruction conventions and scale support.

If Jev Score does not support an exact integer 0–2 output, use its documented numeric behavior and define appropriate anchored regions or interpretation rules. Preserve the raw returned score. Do not pretend unsupported precision or discrete outcomes.

Document the actual SDK representation.

## 6. Independent question design

Both J3 and J4 must evaluate the original evidence independently.

Provide only:

```json
{
  "invoice_item_description": "Ola passenger cab journey",
  "policy_category": "BUSINESS_TRANSPORT",
  "employee_justification": "Went to an event with people from my office."
}
```

Also provide the applicable fixed policy definition as question instructions.

Do not provide either question with:

- J2's result or distribution.
- The other new question's output.
- Expected evaluation labels.
- Budget balances.
- Claim amounts.
- Purchase history.
- Previous Jev conclusions.

Question independence here means independent formulations without prior model-answer contamination. It does not imply statistically independent predictions, since the judgments share the same original evidence and underlying model.

Reuse the existing pinned Jev model snapshot and authenticated SDK configuration.

If the SDK supports multiple question types in one request, verify the behavior and whether it preserves independent question instructions. You may use a single request for J3 and J4 if supported; otherwise use separate calls. Preserve their individual outputs either way.

## 7. Evaluation dataset

Reuse all 32 existing J2 cases and their frozen expected outcomes.

Do not modify historical expected labels or existing raw J2 records.

Preserve the distinction between:

- Primary J2 cases.
- J1 boundary diagnostic probes.

For the new J3 and J4 experiments, preregister additional expected observations before inference.

For J3, record an expected qualitative support region such as `HIGH`, `LOW`, or `AMBIGUOUS`, with a clear explanation of what that hypothesis means. These must not be represented as exact expected model probabilities.

For J4, preregister an expected sufficiency level (`0`, `1`, `2`) for the anchored conceptual rubric, with justification.

Do not use these expectations in the Jev request.

Pay attention to these contrasts:

- Explicit qualifying purpose versus vague purpose.
- Explicit excluded purpose versus vague purpose.
- Concise but sufficient explanation versus long but irrelevant explanation.
- Identified work-related event versus event merely involving colleagues.
- Clearly identified item-purpose contradiction versus missing purpose.
- Business hotel with qualifying work purpose versus personal accommodation.
- Ordinary commute versus exceptional business-related travel.

## 8. Add a genuinely new held-out set

Create approximately 20 new realistic cases not present in J2.

These should include new wording, different products/services and borderline semantic situations across the policies.

Do not simply paraphrase each existing example with one or two word substitutions.

Include examples such as:

- A company social outing versus a company training session.
- A networking dinner with colleagues without an established business requirement.
- An actual client-facing event.
- Travel for an internal technical workshop.
- A wellness product with a clearly non-wellness purpose.
- An explanation that describes an excluded purpose in substantial detail.
- A very short but qualifying explanation.
- An identifiable invoice item whose description conflicts with the explanation.
- A broadly described event where business purpose remains unresolved.

Before inference, freeze all new input cases and expected J2/J3/J4 annotations.

Use the new cases to test the selected routing rules.

Do not choose or change routing thresholds after viewing the held-out results.

If an initial analysis informs threshold selection, do that only on the reused development cases, then apply the frozen rule to the new held-out set.

Do not rerun and relabel the held-out set to improve apparent performance.

## 9. Execution

Verify the current working SDK configuration in the repository.

Use the pinned Jev model used in J2, with no latest aliases or silent model fallback.

Execute:

- J3 Noul.
- J4 Score.
- J2 Choice on the new held-out cases only, so the new cases have a complete baseline.

For historical J2 cases, reuse the saved actual J2 responses rather than rerunning J2 merely to recreate the baseline.

Run new J3/J4 questions three times per case, and J2 on held-out cases three times per case.

Retain each individual observation with its trial identifier.

Do not average multiple runs into a single fabricated model response.

Record:

- Complete input state.
- Exact question instructions.
- Model identity.
- Noul probabilities.
- Raw Score outputs.
- Choice distributions for newly evaluated J2 cases.
- Response confidence where supplied.
- Request count.
- Latency.
- Errors, including rate limits and timeouts.
- Usage and relevant response metadata.

No credential values or sensitive request headers should be persisted.

Never convert API errors into semantic decisions.

## 10. Offline routing analysis

After collecting actual model results, implement a deterministic Python experiment comparing:

**Configuration A — J2 only**

Use the original J2 outcome.

**Configuration B — J2 + J3**

Use Noul evidence support as an additional signal when considering whether `SUPPORTED` can continue.

**Configuration C — J2 + J4**

Use explanation sufficiency as an additional signal when considering whether `SUPPORTED` can continue.

**Configuration D — J2 + J3 + J4**

Use both supplemental signals.

A J3/J4 disagreement must not automatically cause a denial. It may require clarification or human review.

Respect these semantic distinctions:

- `UNRELATED`: Explicit excluded purpose. Never override it to supported merely because J3/J4 outputs are high.
- `INCONSISTENT`: Material item-purpose conflict. Do not override with a high explanation score.
- `UNCLEAR`: Missing or unresolved evidence. Ask for targeted clarification.
- `SUPPORTED`: Continue only when the selected evidence-routing rule permits.

An explicitly excluded purpose can legitimately receive a high J4 sufficiency score because it is clearly explained.

For development-case routing, compare a small, documented set of candidate thresholds/decision rules. Avoid exhaustive tuning on a tiny dataset.

Choose one provisional rule and freeze it before scoring the held-out set.

Do not call a model-output probability calibrated unless independent calibration evidence exists.

## 11. Evaluation metrics

Report both development and held-out results separately.

Calculate:

1. J2-only false `SUPPORTED` outcomes.
2. False `SUPPORTED` outcomes remaining after supplemental routing.
3. Legitimately supported cases unnecessarily held for clarification/review.
4. Clarification and review counts.
5. Cases where Noul added useful information.
6. Cases where Score added useful information beyond Noul.
7. Cases where both supplemental signals were redundant.
8. Repeated-trial outcome stability.
9. Latency and request cost.
10. Failure handling.

For held-out evaluation, report per-case outcomes as well as aggregate counts.

Do not claim causal improvement from unpaired observations or treat repeated trials as independent cases.

Distinguish:

- Catching a model misclassification.
- Correcting a business decision.
- Requesting more information.
- Verifying the employee's underlying claim.

The experiment can assess the first and third, but does not independently verify real-world employee behavior.

## 12. Deliverables

Add a focused experiment directory, reusing existing repository infrastructure.

Suggested structure:

```text
experiments/
  evidence_quality/
    experiment_j3_j4.py
    j3_j4_dev_cases.json
    j3_j4_heldout_cases.json
    test_experiment_j3_j4.py
    results/
      preregistered.json
      raw_results.json
      routing_comparison.json
    JEV_EVIDENCE_QUALITY_RESULTS.md
```

Adapt directory names to the existing repository layout rather than duplicating common functionality.

The final report must contain:

- Exact Noul proposition.
- Exact Score question and documented numeric scale.
- Frozen expected annotations.
- Actual results for every run.
- J2-only versus supplemental-routing comparison.
- False-support and unnecessary-hold cases.
- A separate held-out evaluation section.
- Detailed discussion of the ambiguous office-event case.
- Explanation of whether J3 and J4 provide distinct information.
- Reproducibility details.
- API/SDK failures.
- Limitations and a clear architecture recommendation.

Include the final questions and Python routing logic in the report or link to the corresponding source files.

## 13. Engineering and execution constraints

- Generate the Python code and **actually execute the experiments** using the working API credentials already configured in the Codex environment.
- Do not mock or fabricate Jev inference.
- Do not modify historical J1/J2 artifacts.
- Do not implement FastAPI, SQLite, OCR, invoice PDF processing, authentication, budgets or payment workflows.
- Keep code minimal, readable, testable and appropriately modular.
- Add deterministic offline tests for scoring, routing, preregistration, failure handling and input isolation.
- Preserve and redact raw responses safely.
- Use stable case IDs.
- Save intermediate results so an interrupted execution can resume without silently replacing earlier observations.
- Do not silently alter thresholds after examining held-out results.
- If API access fails, preserve actual error records and report incomplete coverage instead of inventing results.

## 14. Final recommendation required

After running everything, explicitly answer:

1. Does Noul add useful evidence beyond J2 Choice?
2. Does Score add useful evidence beyond J2 Choice?
3. Does Score add anything meaningfully different from Noul?
4. Which of the four configurations should our reimbursement system use in V1?
5. What limitations remain before integrating the semantic decisions into FastAPI?

Do not recommend retaining a question simply because it demonstrates another Jev primitive.

**The central goal is to learn when multiple narrow semantic judgments improve decisions and when they merely introduce redundant complexity.**