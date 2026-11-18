# Employee expense reimbursement with Jev

Experiments exploring Jev for employee reimbursement auditing:

- **J1:** Category validation with Noul-first and Choice-first approaches.
- **J2:** Purpose alignment using Choice.
- **J3/J4:** Additional purpose-evidence and explanation-sufficiency checks using Noul and Score.

Code, datasets, saved results, setup instructions and findings are documented in
[experiments/README.md](experiments/README.md).

The end-to-end reimbursement application is not implemented yet.

## Milestone 1: reproducible Python setup

Only project scaffolding is implemented. No application modules, endpoints, claim
models, database schema, policy logic, Jev evaluations or UI have been added.

Use `uv` from the repository root (verified with uv 0.10.9):

```powershell
uv sync --locked
uv run python --version
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python -m unittest discover -s experiments -t . -v
```

`.python-version` selects Python 3.12.14, matching the retained experiments.
`requires-python` limits this initial setup to Python 3.12; other minor versions
have not been verified. Install that interpreter with `uv python install 3.12.14`
if unavailable. `uv sync` creates/manages `.venv`; `--locked` prevents accidental
lockfile updates. No build backend or package installation is needed yet
(`tool.uv.package = false`). Existing experiments remain importable from the root.

### Files and dependencies

| File | Responsibility |
| --- | --- |
| `pyproject.toml` | Python target, pinned SDK, development tools, Ruff and pytest configuration |
| `uv.lock` | Resolved dependency versions and distribution hashes for repeatable syncs |
| `.python-version` | Default interpreter selection, Python 3.12.14 |
| `.env.example` | Placeholder key and provisional future settings; no loading behavior |
| `.gitignore` | Ignore local secrets, environments, SQLite files/sidecars and generated caches; allow `.env.example` |
| `README.md` | Setup instructions and this inspection/verification record |

The only direct runtime dependency is the existing `typesafe-sdk==0.7.5`, needed
to run the retained offline SDK tests. Both existing experiment requirements files
are unchanged and specify the same pin. Installed SDK metadata declares Python
`>=3.10`; SDK construction and offline tests work on 3.12.14.

Development dependencies are pytest (`>=8,<10`, locked to 9.2.0) and Ruff
(`>=0.14,<0.15`, locked to 0.14.14). The first sync updated previously unlocked
transitive packages within the SDK's declared ranges: AnyIO 4.15.1 to 4.16.0,
Pydantic 2.14.1 to 2.14.2, and pydantic-core 2.50.1 to 2.50.2. These versions are
now locked; the SDK version and experiment dependency declarations did not change.
This reproduces the new setup, not the exact historical inference environment.

FastAPI and Uvicorn are deferred until a backend milestone. Pydantic is already
installed transitively by the SDK; declare it directly when application models
use it. SQLite uses Python's built-in `sqlite3`, so no package is required.
`python-dotenv` is deferred until environment-file loading is implemented.
The eventual UI uses plain HTML/CSS/JavaScript; no Node, React or Docker is needed.

### Environment and SDK conventions

`.env.example` documents `OPENROUTER_API_KEY`, `JEV_MIN_CONFIDENCE=0.70`, and
`JEV_MIN_PROBABILITY_MARGIN=0.30`. The threshold values are provisional future
defaults, not implemented settings. Copying the example to `.env` does not load
it into Python. Existing experiments read the process environment; their README
documents secure interactive key entry. Offline checks need no API key.

Reuse model snapshot `typesafe/jev-1.14-20261014`. Historical J1 and the scoped
policy experiment use `typesafe/jev-1.14` and check the canonical snapshot;
J2/J3/J4 request the exact snapshot. The integration explicitly supplies the key,
model and OpenRouter `base_url="https://openrouter.ai/api"` to `TypeSafeClient`;
the SDK appends `/v1/systemone`. Experiments disable automatic retries. No model
upgrade, live inference, credential loading or API configuration behavior was added.

### Repository inspection and authoritative design

The authoritative working specification is present at
[`JEV_EXPENSE_AUDIT_WORKING_SPEC.md`](JEV_EXPENSE_AUDIT_WORKING_SPEC.md).
The diagram directory is `flowchart/` (singular): three Mermaid `.txt` sources
and corresponding PNGs. The four experiment areas retain SDK helpers, fictional
fixtures, offline tests, raw results, preregistrations and reports. The archive
manifest tracks 19 immutable artifacts. Reuse these as learning evidence; the
future application should have its own small adapter rather than import runners.

Explicit recent finalized decisions and clearly dated later amendments take
precedence over other agreed specification requirements, provisional proposals,
diagrams and historical experiments, in that order. Milestone 2 Phase B
consolidates the approved decisions into specification sections 1–11 and aligns
all Mermaid sources. The historical specification text is preserved with a
supersession map; it is not a competing implementation contract.

### Finalized decision log (2026-11-03)

These resolutions were explicitly confirmed by the user during Milestone 1.
They document future behavior only; no business logic is implemented here.

1. **J4 Score is informational only.** Its score, distribution and confidence
   may be displayed, but it does not influence claim status, approval, rejection,
   clarification or escalation. There is no J4 routing threshold. Always reassess
   revisions using relevant Python validations and J1/J2 evaluations.
2. **J2 INCONSISTENT is confidence-aware.** Apply configurable minimum confidence
   (default `0.70`) and top-two probability margin (default `0.30`). If both pass,
   route to `HUMAN_REVIEW`. Otherwise route to `NEED_INFO`, with Benefits Team
   escalation to `HUMAN_REVIEW` after two unresolved semantic clarification
   attempts.
3. **Every revision undergoes Python validation again**, including financial and
   duplicate checks. Reevaluate J1 when Invoice Item Name or Reimbursement
   Category changes. Rerun J2 when appropriate, including after justification
   revisions. J4 never replaces or gates these validations and evaluations.

### Milestone 2 Phase B: five finalized decisions (2026-11-03)

This milestone reconciles documentation only. No application logic is implemented.
The following user-approved decisions resolve the five Phase A questions:

1. **Q1 — Mixed mobile bills:** keep the existing form and use J1's existing
   `MIXED_ITEMS` result where applicable to request one eligible cellular component
   and its actual charge. No itemization fields, new classifier, inferred split or
   narrow Noul gate. Complimentary streaming is not independently disqualifying;
   inability to identify the eligible component leads to Benefits Team referral.
   Detection is best-effort from unverified employee-entered information.
2. **Q2 — Editability:** `NEED_INFO` is editable; `HUMAN_REVIEW` permits corrections
   and technical retries. Only these two states can be cancelled.
   `POLICY_RESTRICTION` and `CANCELLED` are terminal and permit new submissions only
   under the usual rules. `PROCESSABLE` cannot be edited, cancelled or reversed.
   Old claims/history remain; a new claim has its own date/duplicate checks.
3. **Q3 — Evidence versions:** evaluate the latest applicable evidence. Reuse J1
   only for unchanged relevant inputs and a valid prior result. J3 receives raw
   evaluated-revision evidence/policy, never other Jev conclusions. J4 receives the
   outstanding question, corresponding earlier evidence, and employee response.
   Preserve every earlier evidence version; "original" does not always mean first
   submission.
4. **Q4 — Validation/persistence:** invalid new fields/amounts/dates return errors
   without creating claims; blocked new duplicates return conflicts without
   creating claims. Structurally valid allowance failures and semantic exclusions
   are saved as `POLICY_RESTRICTION`. Existing editable claims retain their ID and
   last valid evidence on failed corrections; audit attempted values and failures.
   No Jev or consumption/reservation when deterministic validation fails. Corrected
   dates are checked against the original submission date.
5. **Q5 — Category corrections:** allow at most two ordinary category-correction
   attempts after reliable J1 mismatch, then refer if still mismatched. Keep this
   counter separate from the one uncertain-J1 correction opportunity and two J2
   semantic responses. Ordinary corrections and technical retries consume no J2
   semantic attempts.

### Reconciled discrepancy inventory

| Phase A issue | Phase B resolution |
| --- | --- |
| C01: J4 routing and open threshold | Informational only; no threshold; failure records a diagnostic and does not control decisions |
| C02: uncertain INCONSISTENT | Same two configurable checks as SUPPORTED/UNRELATED; full four-label J2 table in specification §6 and Flowchart 1 |
| C03/C07/C16: revision validation, J1 reuse and vague returns | Every revision/retry uses Python PRE; valid unchanged J1 reuse only; named READY and FINAL handoffs |
| C04: allowance-only final check | Serialized atomic duplicate-and-allowance recheck with same-claim idempotency |
| C05/C06: J1 validity, labels and correction loops | Response-validity check precedes reliability; separate label instructions and distinct correction limits |
| C08: terminal/editable states | Explicit Q2 lifecycle table and cancellation restrictions |
| C09/C10: evaluation failures and J3 eligibility | J1/J2 critical failure is distinct from J3 UNAVAILABLE and J4 diagnostic failure; J3 requires successful applicable J1/J2 |
| C11: ambiguous original evidence | Q3 versioned current evidence and question-associated earlier evidence |
| C12: mobile detection | Q1 uses the tested V2 MIXED_ITEMS contract; no new detection mechanism |
| C13/C15: invalid submissions and history | Q4 persistence table; no saved claim for invalid initial dates or blocked new duplicates; failed corrections audited |
| C14: archive and misleading open questions | Current sections consolidate approved amendments; historical text retained with an explicit supersession map |

The actual V2 `MOBILE_BILL` and `MIXED_ITEMS` definitions in
`experiments/category_validation/v2_plan.json` already explicitly cover separately
charged mobile service plus Netflix, complimentary Netflix, and a specifically
claimed cellular line. The older V1 helper lacks `MIXED_ITEMS`; it is historical,
not the application's category contract. No experiment was changed. Historical
experiment routing recommendations remain evidence, not current V1 rules.

The five initial decisions and four independent-review findings now have explicit
resolutions. Manual invoice identity and mixed-item detection remain limited;
model thresholds remain provisional. These limitations do not authorize new
features. Implementation choices and any newly discovered ambiguity must be
reviewed in later milestones.

### Initial Phase B verification record (2026-11-03)

Only this README, the working specification, and the three existing
`flowchart/Flowchart_1.txt`, `Flowchart_2.txt`, `Flowchart_3.txt` sources are changed.
The specification embeds matching copies of those Mermaid sources. Review covers
all J1/J2 branches, separate counters, terminal states, failed corrections,
diagnostic independence, and the sole atomic path to processing. Verification:

- All three embedded blocks exactly match their standalone sources. Node/edge
  structure checks passed (39/55, 33/32 and 29/31 nodes/edges respectively).
- Graph checks confirmed that accepted revisions cannot bypass Python validation,
  new processing cannot bypass the final transaction/rechecks, diagnostic branches
  cannot reach decision routing, and unresolved J2 outcomes cannot process.
- The historical specification body, six detailed policy rows, and Milestone 1
  setup/verification text remain unchanged. All 19 archive hashes match.
- SHA-256 comparison against the inspection baseline found only the five
  authorized files changed; the other 69 tracked files, including experiments,
  configuration, dependencies and PNGs, are unchanged.
- `git diff --check` passed. Existing Mermaid CLI tooling was not found on PATH;
  manual syntax review and structural checks were used without installing tools.
  These checks are not a full Mermaid parser or visual rendering check.

### Flowcharts

The three `flowchart/Flowchart_*.txt` files are the editable Mermaid sources;
matching `.png` files are generated images. After changing a source, render it
with a Mermaid-compatible tool, check labels and arrows for readability, and
replace the corresponding PNG using the same filename. Keep the embedded diagrams
in the working specification aligned with the sources.

### Milestone 1 verification record (2026-11-03)

- Baseline `.venv/Scripts/python.exe -m unittest discover -s experiments -t . -v`:
  25 passed, one temporary-directory permission error in the sandbox.
- `uv sync --python .venv/Scripts/python.exe`: initial sandbox DNS failure accessing
  PyPI; authorized network retry succeeded and generated `uv.lock`.
- `uv sync --locked`: passed without changes; `uv run python --version`: 3.12.14.
- `uv run ruff check .` and `uv run ruff format --check .`: exit 0. There are
  currently no eligible Python files outside experiments, so these are empty-scope
  checks, not claims that historical code conforms. `extend-exclude` preserves
  experiments and recovered source snapshots; `force-exclude` also protects
  explicitly passed paths. Future application files inherit Ruff's selected rules.
- `uv run pytest -q`: 26 passed, 7 subtests passed.
- `uv run python -m unittest discover -s experiments -t . -v`: all 26 passed.
- SHA-256 verification: all 19 manifest artifacts match; all 68 pre-existing
  experiment, flowchart and specification files match the inspection snapshot.
- Git ignore checks cover `.env`, `.env.local`, `.venv`, SQLite files/sidecars,
  bytecode and tool caches; `.env.example` remains eligible for version control.

Sandbox verification used the following process-local paths before the successful
commands above; ordinary local shells normally do not need these overrides:

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD '.uv-cache'
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:TEMP = Join-Path $PWD '.tmp'
$env:TMP = $env:TEMP
```

The system `python` command pointed to an inaccessible Windows Store alias;
`uv run` uses the working interpreter. Git reported dubious repository ownership;
inspection used `git -c safe.directory=D:/ProjectsForBlogLearning/expense-approval-using-jev`
per command, without changing global Git settings. The specification and flowchart
directory were already untracked before this work. No commit or push was made.

Milestone 2 Phase B stops at documentation reconciliation for human review.
Application implementation has not started. Further work
requires explicit approval; the README's final application-wide cleanup is
deferred until the application milestones are complete.
