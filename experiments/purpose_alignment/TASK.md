# Task: Implement Jev J2 — Purpose Alignment Experiment

## 1. Context

We are building a small employee expense reimbursement audit system to understand Jev (TypeSafe AI) and semantic decision modeling.

The architecture separates responsibilities:

- **Jev:** Evaluates semantic questions that cannot be reliably answered using ordinary deterministic rules.
- **Python:** Performs deterministic validations, financial calculations, budget enforcement, and workflow routing.
- **Employee:** Submits an invoice item, chooses a reimbursement category, specifies a requested amount, and provides a meaningful justification.
- **Human reviewer:** Handles cases that cannot be resolved confidently or safely.

**One reimbursement claim targets one specific invoice item or service**, even when multiple claims reference the same invoice.

We have already implemented two category-validation experiments:

- V1 compared Noul-first with Choice-first.
- V2 tested 15 cases, three repetitions each, using corrected reimbursement policy definitions.
- Both approaches matched all 45 preregistered expected classifications.
- Choice-first required fewer model requests and had lower observed median latency.

For application V1, we have provisionally selected **Choice-first for category validation (J1)**.

**Your task is to implement the next experiment, J2: Purpose Alignment.**

Do not rebuild J1 or change its historical experiment results.

## 2. Objective

Determine whether a single Jev `Choice` question can reliably evaluate:

1. Whether the employee's stated reason for purchasing an item qualifies under the selected reimbursement policy.
2. Whether that reason is reasonably consistent with the actual product or service identified on the invoice.
3. Whether missing information can be distinguished from an explicitly ineligible purpose.
4. Whether a product-purpose inconsistency deserves an outcome different from an unrelated purpose.

This is an experiment about semantic question design, not a complete reimbursement workflow.

Do not use Noul or Score in this initial J2 experiment merely for demonstration. We will consider additional primitives only if the results identify a genuine need.

## 3. Fixed reimbursement policies

Preserve the following fictional company policies. Do not modify them to improve model results.

### WELLNESS

Annual allowance: ₹30,000.

Potentially eligible purchases include:

- Running and sports shoes.
- Gym or exercise clothing and equipment.
- Fitness trackers and Garmin fitness wearables.
- AirPods, headphones, and other workout audio accessories.
- Gym memberships and personal training.
- Non-medical meditation and mental-wellness subscriptions.
- Other identifiable products/services reasonably supporting personal fitness or wellbeing.

The purchase must be for the employee's own fitness or wellbeing.

The invoice establishes what was purchased. The employee's explanation establishes the claimed purpose.

AirPods and similar accessories are candidate Wellness products even if the invoice does not mention exercise. Purpose eligibility is determined separately.

General fashion, gaming, entertainment, and arbitrary relaxation subscriptions do not automatically qualify.

Examples:

- Running shoes for daily running: qualifying.
- AirPods for gym workouts: qualifying.
- AirPods for watching movies at home: non-qualifying.
- Casual sneakers claimed for marathon training: potentially inconsistent; assess conservatively.

Do not infer eligibility or ineligibility from gender-labelled product sizing.

### SMARTPHONE

Annual allowance: ₹1,00,000.

Covers smartphone handsets, not tablets, laptops, watches, accessories, or mobile service charges.

Purpose alignment for an identified smartphone purchase should not require an invented professional-use requirement. A straightforward explanation of purchasing a phone for the employee's own use is sufficient unless contrary facts are provided.

Do not evaluate whether the amount falls within the allowance during J2.

### BROADBAND

Monthly allowance: ₹3,000.

Covers home broadband/fiber internet service, not mobile hotspots, dongles, or cellular service.

A reasonable explanation identifying home internet connectivity is sufficient. Do not invent a requirement that the employee prove hours worked from home.

### MOBILE_BILL

Monthly allowance: ₹750.

Covers prepaid and postpaid cellular voice/data service.

A mobile plan including Netflix at no separately stated charge can qualify as a mobile plan. A separately charged entertainment subscription is excluded.

Do not calculate or split charges during J2.

### BUSINESS_HOTEL

No fixed reimbursement cap.

Qualifying purposes include:

- Client visits.
- Internal company training.
- Workshops.
- Business offsites.
- Other adequately explained work-related travel requiring temporary accommodation.

Employee explanation is sufficient for assessing the claimed business purpose. Do not demand external client verification, meeting invitations, employer approval documents, or proof beyond the explanation in this experiment.

Personal vacations are non-qualifying.

### BUSINESS_TRANSPORT

No fixed reimbursement cap.

Qualifying purposes include:

- Travel to client meetings.
- Business trips.
- Transporting clients.
- Internal business events requiring travel.
- Exceptional travel from home to the usual office for a specific client meeting or similarly identifiable business requirement.

Ordinary daily commuting from home to the employee's regular office is excluded.

A specific work-related purpose should be sufficient without inventing external verification requirements.

## 4. J2 inputs

Each J2 evaluation must receive only the relevant information:

```json
{
  "invoice_item_description": "Apple AirPods Pro 2 wireless earbuds",
  "policy_category": "WELLNESS",
  "employee_justification": "I use these during my gym workouts."
}
```

The applicable policy definition should be supplied as part of the Jev question instructions or otherwise consistently available.

Do not give J2:

- Budget balances.
- Employee purchase history.
- Claim amounts.
- Invoice totals.
- Previous Jev probabilities.
- J1 model classifications or confidence values.
- Expected test labels.
- Unrelated invoices or descriptions.

Assume that J1 has already identified the item as a valid candidate for the supplied policy category. J2 does not need to reclassify the item.

Do not pass an employee-selected category known to conflict with J1 into J2. Such a claim should have been routed to category correction first.

## 5. Design one Jev Choice question

Use exactly four outcomes:

### SUPPORTED

The explanation identifies a qualifying purpose under the supplied policy, and that purpose is reasonably consistent with the identified product or service.

Examples:

- Nike Running Shoes — "For daily running."
- Garmin fitness tracker — "To monitor my marathon training."
- AirPods — "For music during gym workouts."
- Marriott Hotel — "Stayed overnight for an internal company workshop."
- Uber — "Travelled to a client meeting."

Short explanations can be sufficient. Do not require essays.

### UNRELATED

The explanation explicitly describes a purpose that falls outside the policy.

Examples:

- Nike Running Shoes — "I bought these to wear to weddings."
- AirPods — "For watching movies at home."
- Marriott Hotel — "Family holiday."
- Uber — "My normal daily commute to the office."

Do not use UNRELATED simply because an explanation is short, vague, or missing details.

### UNCLEAR

The explanation does not establish a qualifying purpose, but it also does not explicitly describe an ineligible purpose or clear inconsistency.

Examples:

- AirPods — "Personal use."
- Marriott Hotel — "Stayed overnight in Bengaluru."
- Uber — "Had something important to attend."
- Running shoes — "Needed new footwear."

Use UNCLEAR for insufficient purpose information.

Do not assume missing facts are true.

### INCONSISTENT

The explanation describes a potentially qualifying purpose, but it is materially inconsistent with the item or service identified on the invoice.

Examples:

- Formal Leather Office Shoes — "For marathon training."
- Gaming console — "For treadmill workouts."

Treat inconsistency carefully:

- Do not accuse the employee of fraud.
- Do not assume that unconventional product usage is impossible.
- Do not treat a merely unusual product-purpose combination as a proven contradiction.
- A weak or debatable mismatch may deserve UNCLEAR instead.

The output indicates an evidence discrepancy requiring clarification or review, not verified dishonesty.

**Important:** The four labels must be defined as mutually distinguishable as reasonably possible. If their boundaries remain problematic, document the issue rather than silently redefining the policy.

## 6. Prepare a preregistered evaluation dataset

Before making any Jev calls, create and freeze approximately **30 realistic test cases**, with:

- Unique case ID.
- Invoice item description.
- Policy category.
- Employee justification.
- Expected J2 outcome.
- Brief reason for the expected outcome.
- Coverage tag.

Include a balanced variety of straightforward and difficult cases.

Required coverage:

**Wellness**
- Clearly supported running shoes.
- Clearly supported gym equipment.
- Supported fitness tracker.
- Supported AirPods workout use.
- AirPods used for entertainment.
- Vague AirPods justification.
- Converse Chuck Taylor sneakers for marathon training.
- Formal leather shoes for marathon training.
- Generic sneakers with a running justification.
- Wellness subscription with a meaningful explanation.
- Wellness subscription with an unclear explanation.
- Gender-labelled fitness apparel without discriminatory inferences.

**Smartphone, broadband, and mobile bill**
- Smartphone purchased for own use.
- Smartphone with an unusually brief but sufficient explanation.
- Home broadband for household connectivity.
- Mobile bill for cellular service.
- Mobile service with a complimentary streaming bundle.
- Explicitly personal entertainment use of separately charged mobile-bill add-ons should not be treated as qualifying cellular service.
- Avoid inventing professional-use requirements where policy does not require them.

**Business hotel**
- Client visit.
- Internal training.
- Company workshop or offsite.
- Family vacation.
- Vague overnight stay.

**Business transport**
- Client meeting.
- Business travel.
- Transporting a client.
- Ordinary commute.
- Exceptional trip to the regular office for a client meeting.
- Vague journey.
- A description where the work purpose is plausible but not established.

Include borderline cases deliberately, not just obvious examples.

Ensure the expected labels are recorded **before inference** and are not changed after seeing Jev's answers.

If a test case falls outside the policy category before purpose is evaluated, replace or separately mark it as a J1 precondition/consistency probe. Do not score it as an ordinary J2 case without explaining that exception.

In particular, examples such as gaming consoles or formal shoes may already fail J1. Preserve their value as diagnostic boundary tests while keeping the primary J2 evaluation logically consistent with the J1 → J2 workflow.

## 7. Run the experiment

Reuse the existing working TypeSafe SDK integration and authenticated API configuration.

Use:

- `typesafe-sdk==0.7.5`, unless the existing environment needs documented adjustments.
- The existing pinned Jev snapshot, `typesafe/jev-1.14-20261014`, through the already verified model configuration.
- The same gateway configuration already proven to work.
- No latest-model aliases or automatic model substitution.
- No simulated Jev responses.

Run each case three times and preserve all individual responses.

Record:

- Selected Choice label.
- Full Choice probability distribution.
- Reported confidence, when available.
- Input state and exact question formulation.
- Model identity.
- API status.
- Errors and timeouts.
- Request latency.
- Request/response metadata and usage when available.

Do not log secrets or authorization headers.

API failures must remain failures; never silently treat them as SUPPORTED, UNCLEAR, or any other semantic outcome.

## 8. Evaluation

Calculate:

1. Agreement with preregistered expected outcomes.
2. Per-label agreement and confusion matrix.
3. False SUPPORTED classifications, especially when the expected label is UNRELATED or INCONSISTENT.
4. Cases where UNCLEAR was incorrectly classified as UNRELATED.
5. Cases where UNRELATED was incorrectly classified as UNCLEAR.
6. Confusion between INCONSISTENT and UNCLEAR.
7. Repeatability across three runs.
8. Typical latency and number of requests per case.

Pay particular attention to whether Jev:

- Accepts an eligible-purpose explanation despite an item-purpose contradiction.
- Penalizes genuinely supported but concise justifications.
- Infers business purpose from hotel/transport invoices without an explanation.
- Treats vague claims as explicitly ineligible.
- Overreacts to unconventional but plausible item usage.

Do not report a 100% accuracy claim merely because a small development set matches expected outcomes. Describe results as observed agreement with preregistered labels, not calibrated accuracy.

## 9. Outputs

Create:

```text
experiments/
  purpose_alignment/
    experiment_j2.py
    j2_cases.json
    test_experiment_j2.py
    results/
      j2_preregistered.json
      j2_comparison.json
    JEV_PURPOSE_ALIGNMENT_RESULTS.md
```

Adapt paths to the existing repository structure if necessary. Do not create duplicate infrastructure unnecessarily.

The Markdown report must include:

1. Objective and scope.
2. Exact Jev Choice question and outcome definitions.
3. Policy assumptions.
4. Frozen test cases and expected labels.
5. Actual results for every case and trial.
6. Confusion matrix and critical misclassifications.
7. Analysis of difficult/borderline cases.
8. Repeatability and latency.
9. Limitations.
10. Recommendation about whether a single Choice question is sufficient.

Do not merely summarize successful cases. Critically examine errors and surprising results.

## 10. Constraints

- Do not implement FastAPI, SQLite, authentication, invoice OCR, PDF processing, budgets, payment, or the full reimbursement engine.
- Do not change J1's experimental results.
- Do not silently change existing policy rules.
- Do not add a second semantic judgment unless the experiment proves it is needed and its proposed role is documented separately.
- Do not use J1's model output as evidence for J2 purpose alignment.
- Do not add artificial verification requirements.
- Do not invent results.
- Do not rewrite ground-truth hypotheses after inference.
- Do not build an approval pipeline from this experiment.

**Final deliverable:** A reproducible J2 experiment and evidence-based recommendation on whether `SUPPORTED / UNRELATED / UNCLEAR / INCONSISTENT` can be handled reliably with one Jev Choice question.

The goal is to learn effective semantic decision decomposition, not to maximize the number of Jev calls or model primitives used.