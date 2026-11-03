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

### Repository inspection and documented discrepancies

The authoritative working specification is present at
[`JEV_EXPENSE_AUDIT_WORKING_SPEC.md`](JEV_EXPENSE_AUDIT_WORKING_SPEC.md).
The diagram directory is `flowchart/` (singular): three Mermaid `.txt` sources
and corresponding PNGs. The four experiment areas retain SDK helpers, fictional
fixtures, offline tests, raw results, preregistrations and reports. The archive
manifest tracks 19 immutable artifacts. Reuse these as learning evidence; the
future application should have its own small adapter rather than import runners.

The finalized decision log below takes precedence over older contradictory
specification sections and Mermaid diagrams. The discrepancies remain documented
for traceability; this milestone changes neither the specification nor the diagrams.

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

### Older wording and diagram discrepancies

- Specification section 6 still says J4 can guide further clarification and calls
  a numeric cutoff open. Section 11 item 1 and finalized steps 24/37 instead make
  J4 informational only. Flowchart 2's "Use J4 to inform next clarification" has
  the same conflict with the finalized advisory-only wording.
- Specification section 6 calls low-confidence `INCONSISTENT` routing open, while
  section 11 item 3 and step 38 finalize confidence/margin-aware routing.
  Flowcharts 1 and 2 send `INCONSISTENT` directly to review without that check.
- Flowchart 2's semantic clarification branch omits Python revalidation before
  reevaluating J2, which specification section 6 requires for revisions.
- Flowchart 1's final check mentions only allowance; section 5 also requires a
  duplicate recheck. Flowchart 3 explicitly includes both. Preserve this difference
  rather than implementing the narrower check from Flowchart 1.
- The historical experiments README describes a J1/J2-only provisional default
  and optional extra judgments; the current specification includes advisory J3
  and clarification J4. Experimental routing thresholds and old policy wording
  remain historical evidence, not current application rules.
- Finalized step 39 explicitly requests ordinary item correction for separately
  charged mobile entertainment. The external diagrams do not explicitly show
  this branch. The specification's archived text is labeled historical, but also
  contains later finalized amendments; it cannot be dismissed wholesale.

Other diagrams simplify lifecycle rules such as cancellation, technical retries,
the J1 correction limit and J3's successful-J1/J2 precondition. Consult the full
specification together with the finalized decision log before implementation.
The first three discrepancies above have authoritative resolutions in that log;
their older source text remains untouched for this milestone.

### Verification record (2026-11-03)

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

Recommended next milestone: approve a small typed settings/validation scope and
its tests, using the finalized decision log above. Any diagram or specification
cleanup remains a separate approved documentation task. No Milestone 2 work has
started; further implementation requires explicit approval.
