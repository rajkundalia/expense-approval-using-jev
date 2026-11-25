# Employee expense reimbursement with Jev

Experiments exploring Jev for employee reimbursement auditing:

- **J1:** Category validation with Noul-first and Choice-first approaches.
- **J2:** Purpose alignment using Choice.
- **J3/J4:** Additional purpose-evidence and explanation-sufficiency checks using Noul and Score.

Code, datasets, saved results, setup instructions and findings are documented in
[experiments/README.md](experiments/README.md).

The end-to-end reimbursement application is not implemented yet.

## Milestone 1: reproducible Python setup

Milestone 1 established project scaffolding. Milestone 3 now includes typed
configuration, structural claim/money validation, and contextual invoice-date
eligibility (see below). Milestone 4 adds the SQLite connection/schema foundation,
identity normalization, raw evidence capture, initial storage/history reads, and
guarded ordinary-correction/cancellation persistence. These are internal persistence
capabilities; complete admission, financial-policy enforcement, Jev evaluation and
decision orchestration, endpoints and UI remain deferred.

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
| `.env.example` | Placeholder key and supported configuration values; no automatic `.env` loading |
| `.gitignore` | Ignore local secrets, environments, SQLite files/sidecars and generated caches; allow `.env.example` |
| `README.md` | Setup instructions and this inspection/verification record |

Direct runtime dependencies are `typesafe-sdk==0.7.5`, Pydantic for typed settings,
and Windows-only `tzdata` for IANA timezone support. Both existing experiment
requirements files are unchanged and retain the SDK pin. SDK metadata declares Python
`>=3.10`; SDK construction and offline tests work on 3.12.14.

Development dependencies are pytest (`>=8,<10`, locked to 9.2.0) and Ruff
(`>=0.14,<0.15`, locked to 0.14.14). The first sync updated previously unlocked
transitive packages within the SDK's declared ranges: AnyIO 4.15.1 to 4.16.0,
Pydantic 2.14.1 to 2.14.2, and pydantic-core 2.50.1 to 2.50.2. These versions are
now locked; the SDK version and experiment dependency declarations did not change.
This reproduces the new setup, not the exact historical inference environment.

FastAPI and Uvicorn are deferred until a backend milestone. Pydantic is declared
directly and remains locked to 2.14.2; Windows timezone data is locked to 2026.6.
SQLite uses Python's built-in `sqlite3`, so no package is required.
`python-dotenv` is deferred until environment-file loading is implemented.
The eventual UI uses plain HTML/CSS/JavaScript; no Node, React or Docker is needed.

### Environment and SDK conventions

`.env.example` documents `OPENROUTER_API_KEY`, `JEV_MIN_CONFIDENCE=0.70`, and
`JEV_MIN_PROBABILITY_MARGIN=0.30`. The thresholds are implemented configuration
defaults, still provisional and not calibrated. Copying the example to `.env`
does not load it into Python. Existing experiments continue reading the process
environment; their README documents interactive key entry. Offline checks need
no API key.

Reuse model snapshot `typesafe/jev-1.14-20261014`. Historical J1 and the scoped
policy experiment use `typesafe/jev-1.14` and check the canonical snapshot;
J2/J3/J4 request the exact snapshot. The integration explicitly supplies the key,
model and OpenRouter `base_url="https://openrouter.ai/api"` to `TypeSafeClient`;
the SDK appends `/v1/systemone`. Experiments disable automatic retries. No model
upgrade or live inference was added; typed application settings are described below.

### Typed configuration (Milestone 3, Slice 2)

`expense_approval/settings.py` separates a small Pydantic `Settings` model from
explicit loading. `load_settings({})` uses defaults; supplying a mapping uses only
the three supported variables. To read process values, the caller opts in:

```python
import os

from expense_approval.settings import load_settings

settings = load_settings(os.environ)
```

Importing the module does not load application environment values or create a
settings instance. No `.env` file is read. Missing thresholds use defaults;
explicit blank, malformed, non-finite or out-of-range values raise Pydantic
validation errors. Both thresholds independently accept finite values in `[0, 1]`.
The optional API key uses `SecretStr` and is omitted from model representations;
normal serialization masks it. No credentials are checked externally. Loading
does not mutate its input or process environment. Tests use synthetic mappings
and keys, with no network or real `.env` dependency.

Slice 2 verification: locked offline Ruff lint/format checks passed; pytest
collected and passed 57 tests (31 configuration tests and 26 historical tests),
plus 7 historical subtests. No dependencies changed.

### Structural claim and money validation (Milestone 3, Slice 3)

`expense_approval/claim_input.py` provides `ClaimInput` and the six-category
`ReimbursementCategory` enum. Use `ClaimInput.model_validate(payload)` for the
employee-entered fields. Required text must be nonblank and is preserved without
trimming or case changes; unknown fields are rejected. Invoice line numbers must
be positive integers and default to `1` only when omitted. Dates accept Python
`date` values or valid `YYYY-MM-DD` text, rejecting datetimes and timestamps.

Both amount fields use the reusable `parse_money` function in
`expense_approval/validation.py` through a Pydantic before-validator. It accepts
decimal text, `Decimal` and integers, rejecting floats and booleans before
coercion. Values must be finite, positive and exactly representable in paise:
`12.340` and `12.0000` pass; `12.345` and `12.001` fail. The parser inspects
fractional digits without rounding, quantizing or depending on Decimal arithmetic
precision, and retains redundant zeros. Requested reimbursement may be below or
equal to the item amount; it is never silently adjusted.

Validation leaves the caller's payload unchanged, including after failure. The
typed model is not a raw audit snapshot; Milestone 4 persistence captures the
original employee-entered evidence separately before parsing. A valid model
establishes only structural validity: three-month eligibility, future-date
restrictions and original-submission-based correction checks use the separate
contextual date validator implemented in Slice 4. Duplicate/allowance checks and
semantic eligibility are not performed here.

Slice 3 verification: locked offline Ruff lint/format checks passed; pytest
collected and passed 176 tests (119 new structural/money cases, 31 configuration
cases and 26 historical tests), plus 7 historical subtests. No dependencies changed.

### Business clock and invoice-date eligibility (Milestone 3, Slice 4)

`expense_approval/clock.py` provides `utc_now()` as an aware production time
source and `business_date(now=utc_now)`. The latter reads its callable once,
converts the instant to `Asia/Kolkata`, and returns the date. Naive datetimes
raise `ValueError`; host timezone and environment settings are not consulted.
Injecting a fixed aware datetime source makes midnight behavior reproducible.

`validate_invoice_date(invoice_date, original_submission_date)` in `validation.py`
accepts already parsed dates and returns `None` on success. The inclusive window
starts three calendar months before the reference date, preserving the day where
possible and clamping to the target month's last day: May 31 maps to February 28
(February 29 in a leap year). This is not a 90-day calculation. `ValueError`
messages distinguish too-old invoices (including the earliest allowed date) from
invoices after the original submission date.

For an initial submission, capture `business_date()` once and pass that trusted
date explicitly. For corrections, pass the retained original submission date;
the correction's date never moves either bound. The validator reads no clock.
`ClaimInput` retains its structural-only date contract. Milestone 4 initial storage
and ordinary-correction persistence call this validator; complete admission and
revision orchestration remain deferred.

Slice 4 verification: locked offline Ruff lint/format checks passed; pytest
collected and passed 195 tests, plus 7 historical subtests. The 19 new cases cover
11 clock cases and 8 calendar-window/correction cases. All 176 prior tests pass,
all 19 archive hashes match, and `git diff HEAD --check` passes. No dependencies,
historical experiments, specification or diagrams changed.

### Milestone 3 final verification (Slice 5, 2026-11-19)

This historical record describes the scope and review status before Milestone 4.

The foundation now includes explicit typed settings, the six-category claim
contract, exact money validation, the injectable India business clock and
original-submission-based invoice eligibility. The usage notes above describe
each component; callers connect them directly without an orchestration service:

```python
from expense_approval.claim_input import ClaimInput
from expense_approval.clock import business_date
from expense_approval.validation import validate_invoice_date

# payload is the employee-entered mapping; capture the trusted date once.
original_submission_date = business_date()
claim = ClaimInput.model_validate(payload)
validate_invoice_date(claim.invoice_date, original_submission_date)
# Later corrections use the retained original_submission_date with the same validator.
```

Three integration cases now verify complete payload parsing and preservation,
explicit clock/date validation, later corrections using the original reference,
and structurally valid claims rejected as too old or after submission. Final checks:

```powershell
uv sync --locked
uv run --offline --locked python --version
uv run --offline --locked ruff check .
uv run --offline --locked ruff format --check .
uv run --offline --locked pytest --collect-only -q
uv run --offline --locked pytest -q
uv run --offline --locked python -m unittest discover -s experiments -t . -v
git diff --check
```

All commands passed: Python 3.12.14; Ruff lint/format clean; 198 pytest cases
collected and passed (172 application cases, 26 historical tests), plus 7 historical
subtests; separate unittest discovery passed all 26 experiment tests. All 19
protected archive hashes match. SDK 0.7.5, dependency declarations and lockfile are
unchanged, as are production modules, historical artifacts, specification and diagrams.

Settings thresholds remain provisional; loading remains explicit with no automatic
`.env` loading. Typed inputs do not replace raw audit evidence or verify invoices.
Endpoints/startup, persistence, duplicate handling, allowances/policy enforcement,
Jev integration, lifecycle/audit workflows, UI, authentication and deployment remain
unimplemented. Slice 5 is ready for independent review; formal milestone closure
and further implementation require approval.

### SQLite connection/schema foundation (Milestone 4, Slice 1)

`expense_approval/database.py` provides three explicit functions:
`initialize_database(path)`, `connect_database(path)` and
`write_transaction(connection)`. The connection context enables foreign keys
and always closes the connection. The transaction context uses `BEGIN IMMEDIATE`,
commits on success and rolls back on exceptions, including commit-time foreign-key
failures. It rejects nested transactions. Importing the module creates no database;
opening a connection may create an empty file, but only initialization adds tables.

`schema.sql` defines four STRICT tables: `claims` for current state/identity,
`claim_revisions` for accepted evidence and failed attempts, `evaluations` for
evidence-bound evaluation records, and `claim_events` for audit history. Deferred
foreign keys let a transaction insert the claim before its accepted revision and
require valid references at commit. Composite references prevent cross-claim links
and require event revision/evaluation IDs to match the supplied evidence version;
revision-only failed-attempt events remain supported.

The partial unique identity index includes undecided (`NULL`), `NEED_INFO`,
`HUMAN_REVIEW` and `PROCESSABLE` claims; restricted/cancelled rows release the key.
Undecided claims must have evidence version 1, zero counters, no question and no
decision reason. NULL is not a sixth employee-facing status. Revision/event history
is immutable; completed evaluations cannot be updated, deleted or replaced.
Evaluation claim/evidence associations are fixed from insertion; unfinished rows
can still receive response/error, completion-time and write-disposition updates.
Explicit replacement guards also protect history when recursive triggers are off.

Initialization uses `PRAGMA user_version = 1`. Repeated initialization leaves that
version intact; unknown versions and nonempty unversioned databases are rejected.
DDL and version assignment share one transaction; complete statements are executed
individually to avoid `executescript()` committing a pending transaction. There is
no migration or schema-repair mechanism. Money and line-number projections use text
without a signed 64-bit limit; date/money validation and encoding remain Python
responsibilities. Raw JSON storage is separate from the evidence encoder below.

Slice 1 verification: locked offline Ruff lint/format checks passed; pytest
collected and passed 298 tests, plus 7 historical subtests. The 100 new database
cases span 31 test functions, including 21 audit-reference regression cases, using
temporary files and direct SQL fixtures.
Separate unittest discovery passed all 26 historical tests; all 19 protected
archive hashes match. Two-connection tests verify writer exclusion and duplicate
identity protection. These checks do not establish complete admission, lifecycle,
retry or allowance correctness. No dependencies, prior modules/tests, historical
artifacts, specification or diagrams changed. No application database was created.

### Identity normalization and raw evidence (Milestone 4, Slice 2)

`expense_approval/identity.py` exposes `normalize_identity_text(value: str) -> str`.
Its exact operation is `" ".join(value.split()).casefold()`: collapse Unicode
whitespace, trim surrounding whitespace, and perform Unicode case folding.
Punctuation and other distinctions remain; there is no fuzzy matching or merchant
alias resolution. Non-string inputs raise `TypeError`; blank input may normalize
to `""`. Structural validation remains the caller's responsibility. Original text
is unchanged; normalization does not acquire or query duplicate ownership.

`expense_approval/evidence.py` exposes `encode_raw_evidence(value: object) -> str`.
It returns strict JSON with the envelope `{"format":"raw-evidence","version":1,
"value":...}`. Each value has an explicit type tag. Exact built-in `None`, boolean,
string, integer, float, list and dictionary values, plus exact `Decimal` and plain
`date` values, are supported. Dictionary `entries` preserve insertion order; list
`items` preserve list order. Field absence stays distinct from explicit values;
no defaults are inserted, and employee keys cannot collide with encoding metadata.

Integers use exact decimal text, including exceptionally large values, without
changing interpreter-global settings. Decimal sign, digits and exponent are
preserved, including trailing zeros, signed zero and special values. Finite floats
use exact hexadecimal text; infinities have explicit markers, and NaNs retain sign
and payload bits. Dates have a separate ISO-date tag. Capture performs no claim
validation, text normalization, rounding or quantization, and does not mutate input.

Unsupported objects/subclasses (including `datetime`), non-string dictionary keys
and cycles produce `type: "incomplete"` descriptors with a reason and Python type.
These explicitly identify incomplete capture; they do not reconstruct the omitted
object or key. Supported surrounding values remain captured. Shared noncyclic
containers are encoded each time. Arbitrary object `str()`, `repr()` and custom
serialization methods are not invoked.

Capture raw input before structural parsing applies defaults or transformations;
do not reconstruct it from `ClaimInput`. Invalid evidence can still be captured:
for example, a list supplied as an amount remains a list. Encoding does not certify
validity or accept a revision. Callers supply stable input while encoding; returned
JSON is detached from later mutations. Unexpected errors, including excessive
nesting, propagate without partial JSON. Original HTTP bytes, object identity,
arbitrary-object reconstruction and a decoder are outside this format's scope.

Slice 2 verification: locked offline Ruff lint/format checks passed; pytest
collected and passed 364 tests, plus 7 historical subtests. New coverage comprises
21 identity cases and 45 evidence cases, including one temporary SQLite round trip
using direct SQL for accepted and failed-attempt snapshots. Separate unittest
discovery passed all 26 historical tests; all 19 protected archive hashes match.
The four approved source/test files are unchanged during final documentation.
No dependencies, schema, database helpers, specification, diagrams or historical
artifacts changed. At Slice 2 completion, claim-admission, duplicate-query,
revision/lifecycle and evaluation-persistence workflows remained deferred; neither
helper writes to SQLite. Slices 3–4 below add storage and guarded claim changes.

### Internal initial storage and history reads (Milestone 4, Slice 3)

`expense_approval/claim_store.py` exposes `insert_initial_claim(connection,
raw_input=..., submitted_at=...)` as an internal persistence primitive. Supply a
connection from `connect_database()` inside a caller-owned `write_transaction()`.
The function rejects calls without an active transaction. It uses a local savepoint
to insert a claim, accepted evidence version and matching `INITIAL_CLAIM_STORED`
audit event atomically. A failed insert removes that operation's partial records
even when the caller catches the error. It never commits or rolls back the caller's
entire transaction; the returned UUID is provisional until the caller commits.

The single supplied aware submission instant provides both the UTC timestamp and
original India business date, without another clock read. Raw evidence is captured
before `ClaimInput` parsing; existing structural and invoice-date checks run before
SQL writes. Employee ID, merchant name and invoice number are normalized separately
from the original snapshot. Monetary projections retain exact Decimal text, and
line numbers use canonical positive-integer text without a signed 64-bit limit.
The claim, revision and event have separate UUID4 identifiers. Initial evidence and
state versions are 1; status/reason/question are unset and all counters remain zero.
The SQLite partial unique index enforces duplicate ownership during insertion;
there is no preliminary duplicate-query API or allowance reservation. Validation
and database errors propagate without being converted into reimbursement statuses.

`get_claim(connection, claim_id)` returns `sqlite3.Row` current state together with
`current_revision_id`, `current_raw_evidence_json`, `current_invoice_date`,
`current_reimbursement_category`, `current_invoice_item_amount` and
`current_requested_reimbursement`. It joins the accepted revision on both the same
claim ID and `claims.current_evidence_version`, rather than choosing the latest
historical row. Missing claims return `None`.

`list_claim_revisions()` returns all accepted and failed-attempt records, preserving
dispositions and ordering by `submitted_at, revision_id`. `list_claim_events()`
returns complete event history ordered by `occurred_at, event_id`. Both return
lists of `sqlite3.Row` and return `[]` for missing history. All three reads use
cursor-local row factories, preserve stored JSON as text, close their cursors and
leave connection-wide settings and caller transaction ownership unchanged. They
perform no writes or explicit transaction control. A caller needing a shared
snapshot across multiple reads must supply the transaction scope.

Slice 3 verification: locked offline Ruff lint/format checks passed; focused
claim-store tests passed all 41 cases (32 insertion and 9 read cases). Full pytest
collected and passed 405 tests, plus 7 historical subtests. Separate unittest
discovery passed all 26 historical tests; all 19 protected archive hashes match.
Both approved code/test files are unchanged during final documentation. No schema,
database helpers, dependencies, specification, diagrams or historical artifacts
changed. At Slice 3 completion, complete admission orchestration, financial-policy/
allowance checks, corrections, cancellation, evaluation persistence and lifecycle
workflows remained deferred. Slice 4 below adds ordinary-correction and cancellation
persistence. The future admission workflow must complete policy checks before
calling Jev.

### Guarded corrections and cancellation (Milestone 4, Slice 4)

`expense_approval/claim_changes.py` provides internal evidence-change and
cancellation persistence through `correct_claim()` and `cancel_claim()`. These
operations preserve history and enforce current-state and invoice-line ownership
guards; persisted evidence is not complete financial or semantic admission.

Supply a connection from `connect_database()` inside a caller-owned
`write_transaction()` (`BEGIN IMMEDIATE`). Both functions require an active
transaction and accept `claim_id`, a canonical UUID4 string `operation_id`,
`expected_status`, positive integer `expected_evidence_version` and
`expected_state_version`, and a trusted aware `occurred_at` datetime. Timestamps
are stored in UTC; booleans are not version integers. The helpers never commit or
roll back the outer transaction. Every returned outcome, including a rejection,
is provisional until the caller commits. Outer rollback removes the operation's
changes, audits and receipt.

`correct_claim()` additionally requires `action_kind="ORDINARY_CORRECTION"` and
`raw_input`, a complete replacement dictionary of employee evidence. Supply all
required `ClaimInput` fields, including unchanged fields: there is no patch or
merge. Omitting optional `invoice_line_number` applies its default `1`, rather
than retaining the previous line. Keep input stable during capture and validation.
Raw input is encoded before parsing applies defaults; structural and exact-money
checks reuse `ClaimInput`. Invoice dates are validated against the stored
`original_submission_date`, never the correction date. Accepted corrections store
an `ACCEPTED` revision and a `CLAIM_CORRECTION_ACCEPTED` event, update normalized
employee/merchant/invoice/line projections, and increment both evidence and state
versions once. An unchanged-value correction with a new operation ID also creates
the next accepted version; replay does not.

Ordinary corrections preserve the original submission timestamp/date, existing
status, reason, outstanding-question pointer and all four counters. Retained
decision/question context can concern earlier evidence: it is not a fresh decision
about the new revision, nor acceptance of an answer to that question. The accepted
event records earlier versions and retained context. Earlier evidence, question
events and evaluations retain their original associations. Subsequent decision
reevaluation and question/counter coordination remain deferred. Trusted internal
callers must identify ordinary corrections explicitly; they must not submit a
semantic response or a separately counted correction response through this API.
The helper does not infer response intent from employee text.

`cancel_claim()` permits only matching `NEED_INFO` or `HUMAN_REVIEW` claims. It
accepts optional `cancellation_reason` as plain text or `None`, sets status to
`CANCELLED` with reason `CANCELLED_BY_EMPLOYEE`, increments only state version,
and clears `outstanding_question_event_id`. It creates no revision and preserves
accepted evidence/version, identity projections, original submission context and
all counters. Its `CLAIM_CANCELLED` event references the current evidence version
and records the previous status, reason and question reference plus the optional
explanation. Clearing the current pointer never deletes historical question events.

After replay lookup, both operations compare expected status, evidence version and
state version exactly. A mismatch takes precedence over editability and correction
validation. Only `NEED_INFO` and `HUMAN_REVIEW` are editable/cancellable;
`POLICY_RESTRICTION`, `CANCELLED`, `PROCESSABLE` and undecided `NULL` are not.

| Outcome | Persistence and effect |
| --- | --- |
| `INVALID` correction | Unversioned failed revision and rejection event with structural/date errors; keep accepted evidence and claim state |
| `DUPLICATE_CONFLICT` correction | Roll back candidate revision/identity changes, then store an unversioned failed revision and rejection event identifying the other blocking claim |
| `STALE` correction | Unversioned failed revision and rejection event identifying mismatched guards; preserve current claim |
| `STALE` cancellation | Rejection event only; no revision or claim change |
| `NOT_EDITABLE` with matching guards | Rejection event only for either action; correction input remains captured in event details; no revision or claim change |

All rejection events use `CLAIM_CHANGE_REJECTED`. No rejection advances evidence
or state versions or changes counters. Failed revisions have NULL evidence versions,
and their events leave `evidence_version` NULL to keep composite foreign keys
coherent. These failures do not produce financial-policy restrictions. Missing
claims raise `LookupError`; invalid internal arguments and unexpected failures
raise errors rather than claiming a recorded business outcome.

The existing partial unique index enforces normalized invoice-line ownership on
the same guarded UPDATE. A same-claim key does not self-conflict; distinct lines
remain independent. Revision acceptance releases the old key and acquires the new
key atomically within the serialized write transaction. Only a verified identity
uniqueness failure with another blocking owner becomes `DUPLICATE_CONFLICT`;
other integrity errors propagate. Cancellation releases ownership through the
index's status predicate. Another writer cannot acquire the released key before
commit, and rollback restores the original ownership. Acquiring a key does not
reserve allowance.

Local savepoints join mutation and audit persistence. Duplicate handling rolls back
the candidate mutation before writing its failed-attempt audit. A failed revision,
claim update or event insertion leaves no partial operation, while ordinary
operation failures preserve earlier caller work. Lock contention propagates for
the caller to retry in a fresh transaction. SQLite-wide transaction aborts and
outer commit failures can roll back the whole caller transaction; original errors
are preserved rather than masked by savepoint cleanup.

Generate an operation UUID4 once per logical request and reuse it for retries. It
is used directly as the globally unique event ID. Versioned receipts in event JSON
support both accepted and rejected operations. An identical request replays its
original `ChangeResult` before current guards, with `replayed=True`, no additional
audit and no version increment, even after later claim changes. The result carries
operation/claim/event IDs, optional revision ID, outcome/reason, recorded resulting
status/versions and detached `details_json`; replay returns those original values,
not a fresh current-state snapshot.

Reusing an operation ID for another claim, action, guards, encoded correction
input or cancellation explanation raises `OperationIdConflict`; unrelated event-ID
collisions do too. Retry timestamp is excluded from equality, but must still be
aware. Correction equality is exact encoded equality, including field presence,
dictionary order and Decimal representation. Malformed or incompatible recognized
receipts raise `MalformedOperationReceipt`, never a successful replay.

When either correction capture includes incomplete descriptors, matching descriptors
cannot prove identical requests. With otherwise matching request metadata, replay
raises `UnverifiableReplayConflict` (an `OperationIdConflict`) even for the same
unsupported object. The first accepted/rejected outcome and its audit stay intact;
no duplicate record is appended. Reliable replay requires fully captured inputs;
no additional serialization framework is used.

These operations do not implement financial allowance enforcement, Jev evaluation
or orchestration, semantic clarification-response admission, correction/response
counter updates, initial evaluation recovery, final processing, endpoints or UI.
Future admission must complete applicable financial and semantic coordination
before evaluation/processing. Tests seed `PROCESSABLE` rows directly to verify
preservation of existing state and derived consumed amounts; those fixtures do not
demonstrate implemented allowance calculation or processing decisions.

Slice 4 final verification (Step 5): locked offline checks passed with Python
3.12.14 and clean Ruff lint/format checks. The focused `test_claim_changes.py`
suite passed 245 cases; full pytest passed 650 tests plus 7 historical subtests.
Separate historical unittest discovery passed all 26 tests. All 19 protected
archive SHA-256 hashes match, and staged/unstaged Git whitespace checks pass.
Foreign-key and SQLite integrity assertions pass in the persistence tests.
Coverage includes deterministic cross-connection ordering, accepted/rejected
replays, before/after-write failures, caller savepoints, outer commit failure and
transaction aborts, immutable history and nonempty evaluation associations.

Step 5 changes only this README. The independently reviewed Slice 4 source and
tests remain unchanged, as do schema, dependencies, specification, flowcharts and
historical experiments. Existing staged work remains intact. Slice 4 is ready for
independent documentation/final-verification review; no commit, push or later
slice is included.

### Milestone 4 Phase B verification and status (Slice 5)

Slice 5 Step 1 verified committed HEAD
`d493fd94e4e551f615159ae7241bd98ef559aa8e` using locked offline Python 3.12.14.
Ruff lint and format checks passed; claim-change tests passed 245 cases; database,
store, identity and evidence tests passed 207 cases. Full pytest passed 650 tests
plus 7 historical subtests, and separate historical unittest discovery passed
26 tests. All 19 protected archive hashes matched; existing SQLite foreign-key
and integrity assertions and Git whitespace checks passed. All 94 tracked files
and the Git index were unchanged, with no errors or warnings reported.

Step 1 verification has been independently reviewed and approved. Step 2 reconciles
only this README; no additional integration tests were required by the approved
Slice 5 plan. The persistence capabilities and workflow exclusions are documented
in Slices 1–4 above; evaluation schema/association protection does not implement
evaluation-persistence workflows or decision orchestration. At that review checkpoint,
Slice 5 documentation and formal Milestone 4 closure were pending independent review;
no later step was authorized. Milestone 4 was subsequently formally closed with
commit `aafc9535b58be492f81b77abaa9f84d159c7111b`.

### Fixed allowance policies and invoice periods (Milestone 5, Slice 1)

`expense_approval/allowance_policy.py` provides deterministic, side-effect-free
`get_allowance_policy(category)` and `get_allowance_period(category, invoice_date)`.
`AllowancePolicy` and `AllowancePeriod` are frozen value objects; the fixed policy
mapping is read-only. Caps are exact INR `Decimal` constants:

| Existing `ReimbursementCategory` | Cap (INR) | Calendar period |
| --- | --- | --- |
| `WELLNESS` | 30000 | Annual |
| `SMARTPHONE` | 100000 | Annual |
| `BROADBAND` | 3000 | Monthly |
| `MOBILE_BILL` | 750 | Monthly |
| `BUSINESS_HOTEL` | `None` (uncapped) | None |
| `BUSINESS_TRANSPORT` | `None` (uncapped) | None |

Annual period keys contain `kind=ANNUAL`, the invoice year and `month=None`;
monthly keys contain `kind=MONTHLY`, the invoice year and month. They represent
the whole calendar year/month, inclusive, using only the supplied invoice date.
Employee and category remain separate scopes. Uncapped policies have no cap or
period kind, and period lookup returns `None`; this does not imply reimbursement
approval. Period selection does not establish invoice-date eligibility.

Both functions require an existing `ReimbursementCategory` enum member, rejecting
plain category strings. Period lookup accepts `date` objects and their subclasses,
but rejects `datetime`, date text and other types. Unsupported types raise
`TypeError`; category validation precedes date validation, including for uncapped
categories. Lookup reads no clock and performs no database operations.

Slice 1 implementation and Step 3 integration verification have been independently
reviewed and approved. Locked offline verification passed with Python 3.12.14:
916 pytest tests plus 7 historical subtests; separate historical unittest discovery
passed 26 tests. Ruff lint/format passed, existing SQLite foreign-key/integrity
assertions passed in the persistence tests, and all 19 protected archive hashes
matched. These results verify the current implementation, not deferred workflows.

At Slice 1 completion, money conversion and financial assessment arithmetic,
remaining-allowance calculations, SQLite consumption queries, composed claim
allowance assessments, admission and final processing, financial allowance
enforcement and consumption recording, Jev orchestration, API endpoints and UI
remained deferred.

### Exact financial assessment (Milestone 5, Slice 2)

`expense_approval/allowance_policy.py` now also provides
`MoneyInput` (`str | Decimal | int`), `AllowanceOutcome`, frozen `AllowanceAssessment`
and `assess_allowance(category, invoice_date, requested, consumed)`. All four
arguments are required. Assessment reuses Slice 1's fixed policies and invoice periods and
accepts caller-supplied consumption; it performs no database operations or state
changes.

Requested amounts must be finite, positive and exactly representable in paise.
For capped policies, consumption must be explicit, finite, nonnegative and exactly
representable in paise.
Exact integer-paise arithmetic computes remaining allowance as cap minus consumption,
before the candidate request. The full request is compared with that balance:
equal or lower returns `WITHIN_ALLOWANCE`; higher returns `EXCEEDS_ALLOWANCE`.
Requests are never silently reduced, negative balances are never clamped, and no
rounding is performed. Parsed input values and Decimal representations are preserved;
derived remaining balances have exactly two decimal places, including negative
balances and canonical positive zero. Arithmetic does not depend on ambient Decimal
precision or impose a fixed-width integer limit.

Uncapped categories require `consumed=None` and return `UNCAPPED`, with cap, period,
consumed and remaining fields all `None`. The result also carries the category and
validated requested amount. A financial assessment is not reimbursement approval
or authorization to process a claim.

SQLite consumption queries and employee/category/period consumption attribution,
claim admission and lifecycle orchestration, financial allowance enforcement,
allowance reservations or consumption writes, Jev evaluations and decision routing,
final processing, API endpoints and UI remain deferred. Callers are responsible
for supplying consumption for the intended employee, category and invoice period.

Slice 2 implementation and Step 3 integration verification have been independently
reviewed and approved. Locked offline checks passed with Python 3.12.14: 439 focused
tests; 1,089 full pytest tests plus 7 historical subtests; and 26 separate historical
unittest tests. Ruff lint/format passed, existing SQLite foreign-key/integrity
assertions passed in the persistence tests, and all 19 protected archive hashes
matched. These results establish the approved Slice 2 integration baseline.

### Milestone 5 allowance integration and final verification

Slices 1-4 implement Deterministic Allowance Foundations and are committed at
`46993e220722acd893cdfa8c04a27448aa3737f6`. The fixed category caps and invoice
periods are documented in Slice 1 above; exact financial calculations and the
`WITHIN_ALLOWANCE`, `EXCEEDS_ALLOWANCE` and `UNCAPPED` outcomes are documented in
Slice 2. This Slice 5 Step 2 documentation and verification checkpoint awaits
independent review; Milestone 5 is not formally closed. The preceding Slice 2
deferral statement and the final Milestone 4 stopping-boundary paragraph record
historical checkpoints, rather than the current availability of Slices 3-4.

**SQLite consumption reader (Slice 3).**
`expense_approval/allowance_store.py` provides
`read_consumed_allowance(connection, *, employee_id, category, period) -> Decimal`
for capped categories. It normalizes employee identity and selects only
`PROCESSABLE` claims, joining accepted revisions on both claim ID and the current
evidence version. The current revision supplies category, invoice date and
requested reimbursement. Inclusive invoice-calendar year/month bounds select the
period; submission and correction timestamps do not determine consumption.
Non-current accepted history and rejected attempts do not contribute. Selected
money is validated and summed exactly as Python integer paise, returning two-place
INR or `0.00` for no matches. Malformed selected money raises `ValueError` without
a partial total. Schema-valid references, canonical ISO dates and standard text
decoding are assumed; the reader is not a database corruption scanner.

**Candidate assessment (Slice 4).**
`expense_approval/candidate_allowance.py` provides
`assess_candidate_allowance(connection, *, candidate: ClaimInput) -> AllowanceAssessment`.
Supply a normally validated `ClaimInput`; validation-bypassing construction or
updates are outside this contract. The function derives the candidate's policy
and invoice period, reads capped consumption for its employee/category/period,
and delegates to `assess_allowance`, returning the existing assessment object.
Both uncapped categories bypass SQLite and supply `consumed=None`; a correctly
typed but closed SQLite connection is therefore acceptable for those categories.
Contextual invoice-date eligibility and selection of current candidate evidence
remain caller responsibilities. There is no candidate claim ID or exclusion:
every matching `PROCESSABLE` claim contributes, even one represented by the
candidate. This function is not an idempotent processing shortcut.

**Transactions and limitations.** The reader and composition are read-only and
preserve caller ownership of the connection, transaction and savepoints. They
start no transactions or savepoints, change no connection settings, and perform
no commits or rollbacks. Capped consumption observes one SELECT snapshot or the
caller's existing transaction snapshot, including its own visible writes. A WAL
writer can commit while an established reader snapshot remains active;
rollback-journal readers can block writer commit. Consumption can become stale,
and an assessment never approves a claim, reserves allowance or authorizes
spending. Future final processing must serialize and recheck consumption and the
applicable state/evidence guards. Extreme monetary values remain resource-bound.

Financial enforcement/admission, allowance reservations or consumption writes,
claim lifecycle orchestration, Jev judgments and semantic decisions, final
processing and its idempotency workflow, API endpoints and UI remain deferred.
No schema extensions/migrations or configurable/employee-specific policies are
implemented by Milestone 5. The separate approved Milestone 5 Phase A document
was unavailable locally; it has not been reconstructed.

**Locked offline verification.** Run from the repository root using the existing
Python 3.12.14 environment. These process-local cache/temp overrides are the
established sandbox settings; `.tmp` already exists in this workspace.

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD '.uv-cache'
$env:TEMP = Join-Path $PWD '.tmp'
$env:TMP = $env:TEMP
uv run --offline --locked python --version
uv run --offline --locked ruff check .
uv run --offline --locked ruff format --check .
uv run --offline --locked pytest tests/test_allowance_policy.py tests/test_allowance_store.py tests/test_candidate_allowance.py -q
uv run --offline --locked pytest -q
uv run --offline --locked python -m unittest discover -s experiments -t . -v
```

The reader/composition tests include SQLite foreign-key and integrity assertions;
the full pytest suite also runs the historical tests and their subtests. Verify
the 19 protected archive hashes separately using the manifest procedure in
[experiments/README.md](experiments/README.md#offline-verification). Inspect the
complete README diff, run `git diff --check` and `git diff --cached --check`, and
compare the other tracked files and Git index against the pre-edit SHA-256
baseline. Use the established per-command `safe.directory` override if needed.

Step 2 verification on 2026-11-22 passed with Python 3.12.14: Ruff lint/format;
588 focused Milestone 5 tests; 1,238 full pytest tests plus 7 historical subtests;
and 26 separate historical unittest tests. Existing SQLite foreign-key/integrity
assertions passed, and all 19 protected archive hashes matched. Git whitespace
checks passed. All 99 tracked files other than README and the Git index remained
byte-identical to the pre-edit baseline. This step adds only this README section;
no source, tests, schema, dependencies or historical artifacts changed. No staging,
commit or push occurred. Documentation review and formal milestone closure remain
pending independent approval.

### Milestone 6 — Evidence-Bound Evaluation Persistence

Slices 1–4 are implemented, independently reviewed and committed through
`dfe426112974099ccf493152bfab47e3a6df0442`. Earlier deferrals and planning/review
checkpoints remain historical records; this section describes the current
evaluation-persistence contract. This Slice 5 README update awaits independent
review and is not a committed Slice 5 or formal Milestone 6 closure.

**Interfaces and creation.** `expense_approval/evaluation_store.py` provides
`create_evaluation()`, `complete_evaluation()`, `get_evaluation()` and
`list_claim_evaluations()`. Creation binds an attempt to the claim's current
accepted evidence version, expected status (including NULL) and expected state
version. Opaque creation metadata and input JSON are preserved and immutable
through these public APIs. New rows are unfinished: `completed_at`,
`response_json`, `error_json` and `write_disposition` are all NULL. New J1/J2
attempts against `POLICY_RESTRICTION`, `CANCELLED` or `PROCESSABLE` are rejected.
J3/J4 diagnostic storage does not establish inference eligibility or prerequisites.

**Completion.** Supply exactly one result channel: a strict JSON-object response
or a supported technical-failure code. JSON validation rejects duplicate keys and
nonstandard numeric constants, requires UTF-8 encodability and SQLite
compatibility, and preserves accepted text exactly. The five failure codes are
`TIMEOUT`, `CONNECTION_ERROR`, `PROVIDER_ERROR`, `INVALID_RESPONSE` and
`REMOTE_OUTCOME_UNKNOWN`. Generated `error_json` contains only the approved code,
for example `{"code":"TIMEOUT"}`; arbitrary provider messages or exceptions are
not accepted through this channel. Aware start/completion timestamps normalize to
UTC with fixed microsecond precision. Completion cannot precede the stored start.
One atomic update completes an unfinished row; completed records cannot be
updated, deleted or replaced.

| First completion condition | Stored disposition |
| --- | --- |
| Current anchor, J1/J2 | NULL |
| Current anchor, J3/J4 | `DIAGNOSTIC` |
| Changed evidence/status/state version | `STALE` |

Staleness takes precedence over diagnostic identity, including after corrections
or cancellation; the response or sanitized failure is still retained. NULL means
this capture applied no claim outcome, not that the evaluation can never
subsequently be referenced. These APIs never assign `APPLIED`; valid historical
`APPLIED` records remain readable and replayable. Future claim application must
be separately guarded and audited without updating completed evaluation rows.

**Exact replay.** The globally unique `evaluation_id` is the persistence
idempotency key. `evaluation_run_id` is correlation metadata, not a uniqueness
key. Creation replay compares all immutable metadata, normalized start timestamp
and exact input JSON text. Completion replay compares the result channel, exact
response text or approved failure code, and normalized completion timestamp.
After argument and stored-record validation, exact replay returns the existing row
before current-state checks, even after completion or later claim changes. It
performs no write and never recomputes the stored disposition. Conflicting reuse
raises `EvaluationConflict`; stale new creation raises `EvaluationStateConflict`;
malformed existing lifecycle records raise `MalformedEvaluationRecord`. Missing
claim/evaluation write targets raise `LookupError`.

Retain the original request, IDs, metadata, JSON and timestamps for reliable
retry after lost acknowledgments. Evaluation replay includes normalized
timestamps in its identity, unlike the earlier claim-change replay contract,
which excludes its retry timestamp. Formatting changes to JSON conflict even
when the parsed values would be equivalent.

**Transactions and reads.** Supply a connection from `connect_database()` inside
caller-owned `write_transaction()` (`BEGIN IMMEDIATE`) for evaluation writes.
Active-transaction validation alone cannot prove the begin mode or foreign-key
enforcement. Local savepoints isolate ordinary failures and preserve earlier
caller work; the APIs do not begin, commit or roll back the outer transaction.
Returned writes remain provisional until outer commit. SQLite transaction aborts
and deferred commit failures can invalidate provisional writes; original failures
propagate without cleanup against a transaction SQLite has already ended.

Reads return stored historical rows without reinterpretation or repair.
`get_evaluation()` returns `sqlite3.Row` or `None`;
`list_claim_evaluations()` returns a list or `[]`, ordered by
`started_at, evaluation_id`. `unfinished_only=True` filters
`completed_at IS NULL`. Reads use cursor-local row factories, close only owned
cursors, and preserve connection settings and caller transaction ownership.

**Provenance and exclusions.** Input and response snapshots are opaque JSON.
Validation guarantees syntax and SQLite compatibility, not semantic fidelity or
correspondence to accepted evidence or actual model requests. Trusted callers
must avoid storing secrets. Database persistence idempotency is not exactly-once
remote model execution; no automatic retry/recovery workers exist.

Milestone 6 does not implement Jev SDK/model calls, semantic interpretation or
routing, financial enforcement, claim-result application, final processing, API
or UI. Evaluation operations do not change claims, revisions, events, counters,
question pointers or consumed allowance.

**Reported verification baseline.** Before this README-only step, locked offline
verification passed with Python 3.12.14: 238 evaluation-store pytest tests;
1,476 full pytest tests plus 7 historical subtests; 26 historical unittest tests;
Ruff lint/format; SQLite foreign-key/integrity assertions; and all 19 protected
archive SHA-256 hashes. For this documentation audit, use the established
process-local cache/temp settings above, run Ruff checks, substitute
`pytest tests/test_evaluation_store.py -q` for the focused allowance-suite command,
and run full pytest, historical unittest, archive and Git preservation checks.
No source, tests, schema or dependencies are changed by this README addition.

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

Milestone 4 Phase B Slice 5 Step 2 is limited to README reconciliation against the
committed persistence implementation and approved Step 1 verification. Work stops
here for independent review; staging, commits, pushes and Step 3 are not authorized.
Application-wide README cleanup remains deferred until the application milestones
are complete.
