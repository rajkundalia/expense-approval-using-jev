# Final scoped J3 and J4 experiment

This is a new, isolated experiment. The previously checked-in code, fixtures,
preregistrations, raw responses and reports are not altered. Shared SDK and J2 code
was **copied first**, then reused locally. No runtime import points to another
experiment's implementation. `COPY_PROVENANCE.json` records the source files and
hashes of all files tracked when this work began.

The copied `j2_reference.py` differs only in importing the new local SDK helper.
`sdk_support.py` is a copy of the existing SDK integration. Its older runner functions
are unused; run the new `experiment.py`, not these support files.

## Questions and boundaries

- **J3-A, Noul:** Does the explanation explicitly establish an exceptional business
  requirement distinguishing this home-to-regular-office journey from ordinary commuting?
  It is not applicable to an ordinary client-premises business journey. Missing
  evidence is not proof of an excluded commute.
- **J3-B, Noul:** Does the invoice explicitly identify a separately charged entertainment
  or streaming component in addition to the cellular plan? Low probability does not
  prove absence, and a separate extra does not disqualify the underlying cellular line.
- **J4, Score:** How completely does the revision answer the exact clarification?
  Ordered anchors are 0 not resolved, 1 partial, 2 resolved. The actual SDK result can
  be fractional. A fully answered clarification can reveal an excluded purpose or
  contradict the original explanation; high resolution is not approval or verification.

J2 comparisons use a copy of the exact frozen original Choice formulation, only where
the one-item and candidate-category preconditions hold. No model output is passed to
another question. All request states and exact instructions are preserved.

There is no application, UI, allowance enforcement, monetary calculation or payment
workflow. Eventual Benefits Team escalation is represented only by offline routing
labels. Applicability is explicit fixture context, not a reliable free-text recognizer.

## Dataset and execution

The fixtures were written before new inference:

- `j3_cases.json`: 18 fixtures, nine per proposition; explicit present, explicit absent,
  unknown and not applicable states. Three fixtures skip Noul; two also skip J2 because
  the claim scope/category is incompatible. The client-premises journey receives a
  valid J2 comparison without an exceptional-commute Noul.
- `j4_cases.json`: 22 revision cases. Two borderline hypotheses have acceptable
  alternatives declared in advance; the primary expected anchor is still retained.
- Three trials per applicable question: **45 Noul + 48 Choice + 66 Score = 159 requests**.
- Development and held-out splits are fixed. No numeric routing cutoff is introduced
  before development results exist. After the development phase, at most three
  exploratory cutoffs per signal are derived from case-median observations and frozen
  in `sensitivity_plan.json` before held-out collection. No winning deployment threshold
  is selected or retuned on the held-out set.

The mobile cases identify one claimed cellular line while allowing invoice context
about separate charges. A new component flag is not automatically a correction of
J2: J2 may correctly support the cellular purpose already. Unknown charging details,
missed separate flags and false purpose continuations are evaluated separately.

## Run from the repository root

Use the existing virtual environment and the PowerShell session containing
`OPENROUTER_API_KEY`:

```powershell
.\.venv\Scripts\python.exe -m experiments.policy_conditions_and_revisions.experiment
```

The pinned environment is `typesafe-sdk==0.7.5`, OpenRouter base URL
`https://openrouter.ai/api`, and exact model snapshot
`typesafe/jev-1.14-20261014`. SDK retries and automatic model fallback are disabled.
The installed Score signature/schema is inspected and captured in preregistration.

If dependencies need reinstalling:

```powershell
.\.venv\Scripts\python.exe -m pip install -r experiments/policy_conditions_and_revisions/requirements.txt
```

The script checkpoints after every individual request and preserves errors/timeouts
without assigning semantic labels. Completed attempts, including failures, are skipped
on resume rather than silently replaced. An interrupted pending request with unknown
server outcome blocks automatic resubmission. A completed run only regenerates its
analysis/report. Policy, hypotheses and questions cannot change within a frozen run.

Checkpoint writes use unique temporary files and bounded local rename retries to
tolerate transient Windows file locks. These retries never repeat an API request.
If a pre-request checkpoint fails persistently, it is recorded as unsent and can resume;
a request interrupted during inference remains unknown and is not automatically resent.
The 2026-10-31 Windows rename failure after 95 saved observations was backed up under
`results/recovery_20261031T084638Z/`. The unsent pending marker was cleared with an
audit entry; all saved responses and the original error were preserved.

## Offline commands

These make no inference calls:

```powershell
.\.venv\Scripts\python.exe -m unittest experiments.policy_conditions_and_revisions.test_experiment -v
.\.venv\Scripts\python.exe -m experiments.policy_conditions_and_revisions.experiment --dry-run
.\.venv\Scripts\python.exe -m experiments.policy_conditions_and_revisions.experiment --analysis-only
```

Unit tests explicitly mock model calls in memory. Mock responses/timeouts are never
written to the actual results directory as inference evidence. No API key is needed
for these commands or for inspecting the copied historical response data.

## Files and outputs

```text
policy_conditions_and_revisions/
  TASK.md
  README.md
  requirements.txt
  COPY_PROVENANCE.json
  experiment.py
  analysis.py
  sdk_support.py                  # Local copy, no old-code dependency
  j2_reference.py                 # Local copy, adapted import only
  j3_cases.json
  j4_cases.json
  test_experiment.py
  reference_data/                 # Byte-identical copies of historical J1/J2 data
  results/
    preregistered.json
    raw_results.json
    sensitivity_plan.json         # Created only after development inference
    evaluation_summary.json
  JEV_POLICY_CONDITIONS_AND_REVISIONS_RESULTS.md
```

The report includes all per-case outputs, probability distributions, confidence,
selected-label margins, competing routing alternatives, expected-level probabilities,
absolute score error, repeatability, latency, usage, API errors and sensitivity tables.
For Score, cumulative mass refers to rubric levels below a cutoff, not an invented
probability distribution of the expected score itself. Confidence is never treated as
the winning-label probability or calibrated real-world certainty.

The copied historical office-event error is already analyzable: the three incorrect
SUPPORTED predictions had confidence 0.43/0.35/0.35, selected probability
0.57/0.51/0.51, and competing UNCLEAR probability 0.43/0.49/0.49. This is actual saved
evidence, not new inference or an established routing threshold. Sources are analyzed
separately because their policies, questions and fixtures differ.

Before a live run, the report explicitly states that new Noul/Score findings and gate
recommendations are unmeasured. The study must not be optimized to justify retaining
either primitive. Small, repeated fictional cases do not establish production accuracy.

## Verify the earlier checked-in files are unchanged

From the repository root:

```powershell
@'
import hashlib, json
from pathlib import Path
p = Path('experiments/policy_conditions_and_revisions/COPY_PROVENANCE.json')
manifest = json.loads(p.read_text(encoding='utf-8'))
for name, expected in manifest['tracked_files'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
print('All previously tracked files are unchanged.')
'@ | .\.venv\Scripts\python.exe -
```

Historical instructions and absolute paths inside copied references are provenance,
not current execution paths. Do not run an old experiment merely to reproduce a
baseline that is already saved here. No commit, push or new model run is performed
by preparing this folder.
