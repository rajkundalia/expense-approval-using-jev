# Jev reimbursement experiments

Keep this folder. It records what we asked Jev, what policy and expected labels were
fixed beforehand, the actual responses, and why we provisionally chose a design.
These are small learning experiments and future regression examples, not a production
reimbursement engine or proof of general model accuracy.

## Start here

| Experiment | Question | Saved evidence | Provisional conclusion |
| --- | --- | --- | --- |
| [J1 V1](category_validation/JEV_CATEGORY_EXPERIMENT_RESULTS.md) | Noul-first versus independent Choice for item category | Five cases; early experimental definitions | Historical baseline; its Wellness exclusion of audio accessories was superseded by the user-confirmed V2 policy |
| [J1 V2](category_validation/JEV_CATEGORY_EXPERIMENT_V2_RESULTS.md) | Category validation under corrected policy | 15 cases × 3 trials × both approaches; 45/45 hypothesis agreement each, 69 versus 45 requests; median approach latency 1,161 versus 611 ms | Prefer Choice-first for category validation; keep justification out of J1 |
| [J2](purpose_alignment/JEV_PURPOSE_ALIGNMENT_RESULTS.md) | One purpose-alignment Choice: SUPPORTED / UNRELATED / UNCLEAR / INCONSISTENT | 32 cases × 3 trials; 84/87 primary agreement; nine separately scored J1 boundary-probe trials | One Choice is the provisional baseline, with an important unresolved inference-of-business-purpose failure |
| [J3 + J4](evidence_quality/JEV_EVIDENCE_QUALITY_RESULTS.md) | Noul purpose evidence and Score information sufficiency beyond J2 | 32 reused development cases, 20 new held-out cases, 216 new requests; routing thresholds selected only on development | Supplemental gates caught the known development error; neither demonstrated additional catches on the held-out set, where J2 itself had no false SUPPORTED outcomes |

Numbers are observations from the retained development/held-out records, not
calibrated accuracy claims. Trials are repeated evaluations of the same cases, not
independent invoices. Read the reports for distributions, errors and limitations.

### The main lesson

The invoice establishes item identity; the employee's explanation supplies claimed
purpose. Keep category classification separate from purpose assessment. Keep arithmetic,
allowance/budget enforcement and state transitions in deterministic Python.

For the current provisional application baseline:

- **J1:** Choice-first, using only the claimed item/service and fixed category definitions.
- **J2:** One Choice using the item, category and explanation plus the applicable policy.
- **J3/J4:** Keep the experimental code and evidence; do not enable extra judgments
  by default merely because they demonstrate Noul and Score.

The distinction between J3 and J4 is meaningful: a clearly excluded daily commute can
have low qualifying-purpose evidence and high information sufficiency. However,
distinct semantics do not automatically establish useful incremental routing value.

The known regression is **J2-30**: an Ola journey described as “Went to an event with
people from my office.” J2 returned SUPPORTED in all three historical trials despite
the frozen UNCLEAR hypothesis. Colleague attendance does not establish a business
purpose. Both supplemental gates held it in development, but the held-out set did not
contain any false SUPPORTED baseline outcomes to test additional catches. This leaves
a limitation to investigate rather than a reason to claim J2 is reliable everywhere.

## Folder layout

```text
experiments/
  README.md
  requirements.txt
  ARCHIVE_MANIFEST.json
  category_validation/
    experiment.py                 # V1 runner and shared SDK/logging helpers
    experiment_v2.py              # V2 category comparison
    test_experiment.py
    test_experiment_v2.py
    v2_plan.json
    sdk-verification.json
    JEV_CATEGORY_EXPERIMENT_RESULTS.md
    JEV_CATEGORY_EXPERIMENT_V2_RESULTS.md
    results/                      # V1 and V2 records, including frozen V2 plan
  purpose_alignment/
    TASK.md                       # Original user-provided J2 brief
    experiment_j2.py
    j2_cases.json
    test_experiment_j2.py
    JEV_PURPOSE_ALIGNMENT_RESULTS.md
    results/                      # Frozen J2 design and 96 individual observations
  evidence_quality/
    TASK.md                       # Original user-provided J3/J4 brief
    experiment_j3_j4.py
    routing_analysis.py            # Offline comparison; no model calls
    j3_j4_dev_cases.json
    j3_j4_heldout_cases.json
    test_experiment_j3_j4.py
    JEV_EVIDENCE_QUALITY_RESULTS.md
    results/                      # Preregistration, raw responses, frozen rule, comparison
```

The shared SDK helper remains in the original category experiment to avoid duplicating
infrastructure. It is research code; a future application can introduce its own small
adapter with a deliberate interface rather than importing experiment runners wholesale.

## Dependencies and credentials

Use Python 3.10 or newer. The retained runs used Python 3.12.14 and
`typesafe-sdk==0.7.5`. The SDK pin is preserved; transitive dependencies are not fully
locked, so a fresh installation is not guaranteed bit-for-bit environment reproduction.

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r experiments/requirements.txt
```

The gateway is OpenRouter, with base URL `https://openrouter.ai/api`. The SDK appends
`/v1/systemone`. J2/J3/J4 explicitly request `typesafe/jev-1.14-20261014`; J1 uses the
versioned ID `typesafe/jev-1.14` and checks its canonical snapshot. There is no latest
alias, automatic model substitution or hidden SDK retrying.

Existing completed results can be inspected and tested without a key. For an
intentional new live experiment, supply `OPENROUTER_API_KEY` in your PowerShell
session. Run this one line, then enter only your key at the prompt:

```powershell
$env:OPENROUTER_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'OpenRouter API key' -AsSecureString)).Password
```

The code does not load `.env` files. Do not put keys in datasets, commands, reports
or source files. To clear the session value:

```powershell
Remove-Item Env:OPENROUTER_API_KEY -ErrorAction SilentlyContinue
```

## Offline verification

Run all 18 tests from the repository root; no model requests are made:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s experiments -t . -v
```

They cover SDK construction, category thresholds, policy boundaries, expected-case
coverage, purpose input isolation, confusion counts, deterministic routing, failure
handling, preregistration integrity, and development/held-out separation.

To verify the 19 immutable artifacts preserved during consolidation, without executing
an experiment:

```powershell
@'
import hashlib, json
from pathlib import Path
manifest = json.loads(Path('experiments/ARCHIVE_MANIFEST.json').read_text(encoding='utf-8-sig'))
for artifact in manifest['artifacts']:
    path = Path(artifact['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact['sha256'], str(path)
print('All archived artifact hashes match.')
'@ | .\.venv\Scripts\python.exe -
```

## Running and analyzing experiments

Prefer reading the retained reports. No model reruns are needed to remember or audit
the conclusions. These relocated commands work from the repository root:

```powershell
.\.venv\Scripts\python.exe -m experiments.category_validation.experiment_v2 --help
.\.venv\Scripts\python.exe -m experiments.purpose_alignment.experiment_j2 --help
.\.venv\Scripts\python.exe -m experiments.evidence_quality.experiment_j3_j4 --help
```

V2/J2/J3+J4 do not automatically repeat a completed run. Their report-only modes
perform offline analysis. To keep the archived Markdown untouched, write a separate
review report, for example:

```powershell
.\.venv\Scripts\python.exe -m experiments.evidence_quality.experiment_j3_j4 --report-only --report experiments/evidence_quality/review_report.md
```

The older V1 runner can overwrite its output: use an explicit new `--output` path
for any intentional rerun. Do not run it over the archived `results/comparison.json`.
New datasets, prompts, thresholds or policy hypotheses require a separately identified
experiment; never relabel old results after inspecting predictions.

The J3/J4 collector reuses the historical J2 responses. It selects a routing rule
using only primary development pairs before collecting held-out results. Its saved
balanced rule has Noul minimum 0.8 and Score minimum 1.5. These are experimental
thresholds, not calibrated correctness probabilities. Noul/Score share a request,
so this experiment cannot separately measure their latency or price in isolation.

## What to check in

Keep the source, tests, fictional test inputs, policy definitions, frozen designs,
raw responses, selected rules, reports, original task briefs and manifest. The briefs
are historical requirements; their original execution instructions do not trigger
model calls by being checked in. The `.gitignore` now permits
the nested experiment results so these evidence files are not accidentally omitted.
The local `.venv`, bytecode caches, `.env` files and temporary JSON writes stay ignored.

The consolidation changed source imports and output defaults for the new layout;
it did **not** regenerate historical predictions, rewrite labels, or modify the 19
hashed JSON/report artifacts. Old absolute paths or original file locations inside
saved responses/reports are historical provenance. Use this README and manifest for
their current locations. The manifest records old-to-new paths and SHA-256 checksums.

This is a source folder ready to include in version control. No Git repository was
initialized and no commit or push was performed as part of consolidation.

## Moving to an end-to-end implementation

These experiments provide a useful starting point, not an implementation plan or
production acceptance test. Preserve them while building application code separately.

The future plan should specify the claim/line-item data model, fixed policy contract,
J1-to-J2 boundaries, deterministic financial checks, clarification/reviewer workflow,
failure handling and persisted audit/version records. Real-world labelled validation
and the known ambiguous-purpose regression still matter before trusting automatic
continuation. Broader application scope will be decided from the next user-provided
implementation prompt; this consolidation does not choose a framework or start the app.
