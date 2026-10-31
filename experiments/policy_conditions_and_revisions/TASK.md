# Task: Implement the final Jev experiments for policy-specific Noul and revision-specific Score

Work in the existing repository:

https://github.com/rajkundalia/expense-approval-using-jev

## 1. Context

This repository already contains experiments:

- J1: Category classification using Choice versus Noul-first.
- J2: Purpose alignment using Choice.
- J3/J4: Evidence sufficiency using Noul and Score.

We are planning a small, local-only employee reimbursement application with a manually entered invoice, simple UI, claim revisions, Python routing, and employee-facing escalation to the Benefits Team.

**Do not implement the application or UI yet.**

This task is solely to validate two proposed new responsibilities for J3 and J4 and analyze the role of Jev's confidence and probability distributions.

Preserve the existing experiments, datasets, outputs, and reports. Do not overwrite them.

Inspect the repository first to reuse its SDK configuration, model version, response parsing, test conventions, and execution patterns. Avoid inventing SDK methods or assuming fields exist without checking the installed SDK and current code.

Use the same pinned model and SDK as the existing experiments unless there's a compelling, documented compatibility issue.

## 2. J3 — Noul for narrow policy conditions

The old J3 asked whether the explanation established the qualifying purpose in general. Preserve that experiment, but investigate two new, narrower propositions.

### J3-A: Exceptional business commuting

Fictional policy:

- Ordinary daily home-to-regular-office commuting is excluded.
- A specific exceptional journey to the regular office for a client meeting or another qualifying business requirement can be covered.
- Travelling to client meetings, mandatory internal training, or work-related offsites can qualify.
- A journey involving colleagues is not automatically business-related.

Noul should evaluate a proposition similar to:

"The supplied explanation explicitly establishes an exceptional business requirement that distinguishes this home-to-regular-office journey from ordinary commuting."

The question must not treat missing evidence as proof of ordinary commuting.

Test examples such as:

1. Ordinary daily commute to the regular office.
2. Exceptional trip to the regular office for a scheduled client meeting.
3. Unusual office visit for mandatory internal training.
4. "Went to the office" without explaining why.
5. "Went to an event with colleagues."
6. Trip to meet a client at the client's premises.
7. Employee says they travelled to the office because they preferred working there.
8. Journey involving both an ordinary commute and a separately described business destination.

Important: The exceptional-commute proposition is only applicable to claims involving home-to-regular-office travel. Do not treat low Noul probability on other business journeys as evidence that the journey is excluded.

For this experiment, define applicability as part of the fixture rather than assuming Python can reliably recognize it from unstructured text. Record how this applicability determination would eventually be made in the application.

### J3-B: Separately charged mobile-plan extras

Fictional policy:

- Cellular voice/data plans qualify up to ₹750 per month.
- A complimentary streaming subscription bundled into the plan does not independently make the underlying plan ineligible.
- Separately charged entertainment or streaming extras are not reimbursable.
- Python calculates eligible amounts; Jev only assesses the semantic policy condition.

Noul proposition:

"The invoice description explicitly identifies a separately charged entertainment or streaming component in addition to the cellular plan."

Test examples such as:

1. ₹699 cellular plan, no extras.
2. ₹699 cellular plan including complimentary Netflix.
3. ₹699 plan plus separately charged ₹199 Netflix add-on.
4. ₹749 mobile plan with unspecified entertainment benefits.
5. ₹699 plan with an entertainment component whose additional charge is unclear.
6. ₹799 plan with complimentary streaming.
7. ₹599 cellular plan plus ₹150 separately charged entertainment.
8. Entertainment-only subscription incorrectly submitted as Mobile Bill.

Distinguish:

- Explicitly present condition.
- Explicitly absent condition.
- Unknown or insufficient information.
- Not applicable.

Noul only returns a proposition probability; it does not inherently provide these four states. Therefore, do not claim that a low probability alone proves explicit absence.

Use the expected evidence state in the test fixture and evaluate how Noul probabilities behave across the states. Where ambiguity requires a separate assessment, document the limitation rather than silently converting the result to false.

## 3. Compare J3 against J2 Choice

The experiment must answer whether these narrow Noul questions provide information beyond our existing J2 purpose-alignment Choice.

For each applicable case:

- Run the relevant J3 Noul proposition.
- Run the existing J2 Choice formulation where its original input contract permits meaningful comparison.
- Do not feed J2's result into Noul or vice versa.
- Preserve the original evidence and the full response metadata.
- Compare cases where J2's selected label would permit an incorrect routing action and J3 might prevent it.
- Identify cases where Noul would introduce unnecessary clarification or review.

Do not invent or force a J2 result for cases incompatible with the existing J2 question. Label such comparisons not applicable and explain why.

## 4. J4 — Score for resolving clarifications

The existing J4 measured general explanation sufficiency.

Preserve that version. This experiment tests a different question:

**How completely does an employee's revised response address the specific information requested in a clarification?**

Inputs should contain:

- Applicable reimbursement policy.
- Original invoice item description.
- Original employee explanation.
- Exact clarification question.
- Revised employee explanation.

Use a 0–2 ordered rubric:

**0 — Not resolved:** The revision does not address the requested missing information or adds no relevant clarification.

**1 — Partially resolved:** The revision adds relevant information but leaves a necessary part of the requested clarification unresolved.

**2 — Resolved:** The revision supplies the information required to answer the clarification, whether the answer ultimately establishes eligibility or an explicit policy exclusion.

The key distinction is that Score measures **resolution of the question**, not whether the expense is eligible.

Examples:

**Business Transport**

Original: "Went to an event with colleagues."

Question: "What specific work-related activity required this journey?"

Revisions:

- "It was important." → Expected 0.
- "It was an office event." → Expected 1.
- "It was mandatory technical training organized by my company." → Expected 2.
- "It was a personal birthday gathering with colleagues." → Expected 2, although the stated purpose is excluded.

**Wellness**

Original: "Bought headphones for personal use."

Question: "How will these headphones be used for fitness or wellbeing?"

Revisions:

- "I like them." → Expected 0.
- "I use them regularly." → Expected 1 or an explicitly documented borderline expectation.
- "I use them during daily treadmill workouts." → Expected 2.
- "I purchased them exclusively for watching movies." → Expected 2 because the purpose is explicit, although it is not qualifying.

**Mobile Bill**

Original invoice description: "Mobile plan with entertainment benefits."

Question: "Is the entertainment benefit complimentary or separately charged?"

Revisions:

- "It is part of my plan." → Expected partial or ambiguous.
- "Netflix is included at no additional charge." → Expected 2.
- "Netflix costs an additional ₹199 on top of my cellular plan." → Expected 2.

Include additional cases where:

- The revision merely repeats the original justification.
- The answer introduces an unrelated detail.
- The clarification is fully answered with a clearly excluded purpose.
- The answer supplies one of two requested details.
- The revision contradicts the previous explanation.
- The revised explanation is concise but sufficient.

Do not penalize short answers simply for being short.

## 5. Evaluation design

Create a compact, reproducible, preregistered dataset before running model inference.

Target approximately:

- 16–20 J3 cases distributed across both propositions.
- 18–24 J4 clarification-revision cases.
- Three trials per case, consistent with the existing experiments.

If practical, separate development examples and held-out examples before inspecting results. Do not tune decision thresholds on the held-out set.

Make the fixture expectations explicit, including genuinely ambiguous or debatable cases. Do not retroactively rewrite expected outcomes to match the model.

For J3, evaluate whether affirmative-condition cases tend to receive higher probability than clearly negative or insufficient-information cases. Analyze uncertain cases separately.

For J4, evaluate the expected rubric level, absolute score error, and whether the distribution includes substantial probability on competing rubric levels.

Report per-case outputs rather than relying only on aggregate accuracy.

## 6. Confidence and probability distribution analysis

This is a mandatory part of the experiment.

For every Choice or Score response, preserve:

- Selected label or expected score.
- Full available probability distribution.
- Reported confidence.
- Model and SDK versions.
- Case ID and trial number.
- Latency and errors, if available.

For Noul, record the proposition probability and any other genuinely supported response metadata. Do not assume it has the same confidence schema as Choice or Score.

Investigate whether uncertainty measures correlate with errors or borderline expected outcomes.

For Choice, consider:

- Selected-label probability.
- Margin between the two highest-probability labels.
- Probability assigned to routing-relevant alternatives.
- Returned confidence.

For Score, consider:

- Expected score.
- Distribution over ordered rubric levels.
- Probability assigned to the expected level.
- Probability of scores below a proposed resolution threshold.
- Returned confidence.

Do not assume confidence is interchangeable with the probability of the winning label. Do not claim that the values represent verified real-world correctness probabilities.

Where useful, calculate descriptive calibration or error-detection statistics, but acknowledge the small sample size and repeated-trial dependence.

Also inspect our existing saved J1/J2 responses, if their confidence fields and distributions are available. Analyze whether the reported confidence or competing probabilities would have flagged the previously observed ambiguous office-event error.

**Do not introduce or finalize routing thresholds before inspecting the data.**

## 7. Python routing analysis

Create a small offline analysis that compares the existing J2-only routing with potential J3-enhanced routing and evaluates possible J4 revision-resolution gates.

This is analysis code, not the final reimbursement application.

Requirements:

- Define routing conditions in Python, not in Jev prompts.
- Distinguish `CONTINUE`, `NEED_INFO`, `HUMAN_REVIEW`, and explicit policy restriction outcomes.
- A positive Noul signal must not override a clearly excluded purpose.
- A low Noul probability must not independently prove a policy violation.
- A high Score must not approve a claim.
- An unresolved clarification after a revision may be escalated, but do not assume every low Score means dishonesty or exclusion.
- Any missing, malformed, or failed model response must fail safely.
- Keep numeric thresholds configurable for sensitivity analysis.

Report false continues, unnecessary holds, ambiguous outcomes, and any differences compared with J2-only routing.

If the dataset does not support a reliable routing threshold, say so.

## 8. Implementation constraints

- Use Python.
- Reuse the current SDK and model configuration.
- Keep the new experiment isolated under the existing `experiments/` structure.
- Avoid changing previous experiment artifacts.
- Use readable test fixtures in JSON or another existing repository convention.
- Add unit tests for parsing, evaluation calculations, and routing logic.
- Mock model calls in unit tests.
- Keep API keys in environment variables; never commit credentials.
- Avoid excessive frameworks or unnecessary abstractions.
- Do not add FastAPI, SQLite, browser UI, or production application code in this task.
- Provide a dry-run or analysis-only mode where possible, so existing saved results can be analyzed without new API calls.

## 9. Deliverables

Produce:

1. New experiment source code.
2. Preregistered J3 and J4 evaluation fixtures.
3. Unit tests.
4. Raw or minimally sanitized response data with complete relevant probability information.
5. Machine-readable evaluation summary.
6. Markdown report explaining results and important failures.
7. Reproducible execution instructions.

The report should answer:

- Did policy-specific Noul provide useful signals beyond J2?
- Which Noul proposition worked best, and where did it fail?
- Can Score reliably distinguish resolved from partially resolved and unresolved clarifications?
- Does Score appropriately assign high resolution to clearly excluded purposes?
- Did confidence and probability distributions identify ambiguous or incorrect decisions?
- Would any proposed gate cause legitimate claims to be held unnecessarily?
- Should J3/J4 be mandatory, conditional, diagnostic-only, or omitted from the application?
- What design limitations should be carried into the eventual FastAPI implementation?

## 10. Final instruction

Do not optimize the report toward proving that Noul and Score must be used.

We want an evidence-based design. If a proposed question provides no useful incremental information, say so.

At the end, provide a concise summary of findings, exact commands to reproduce the results, and a recommendation for integrating—or not integrating—these questions into the application.

If a working API key is not available, implement the datasets, scripts, tests, and analysis pipeline, but do not fabricate model outputs or pretend the inference runs succeeded.