-- Current ownership/state. NULL status means no first decision has been recorded.
CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY NOT NULL,
    status TEXT CHECK (status IN (
        'NEED_INFO', 'HUMAN_REVIEW', 'POLICY_RESTRICTION', 'CANCELLED', 'PROCESSABLE'
    )),
    reason_code TEXT,
    submitted_at TEXT NOT NULL,
    original_submission_date TEXT NOT NULL,
    current_evidence_version INTEGER NOT NULL CHECK (current_evidence_version > 0),
    state_version INTEGER NOT NULL CHECK (state_version > 0),
    normalized_employee_id TEXT NOT NULL CHECK (length(normalized_employee_id) > 0),
    normalized_merchant_name TEXT NOT NULL CHECK (length(normalized_merchant_name) > 0),
    normalized_invoice_number TEXT NOT NULL CHECK (length(normalized_invoice_number) > 0),
    invoice_line_number TEXT NOT NULL CHECK (
        length(invoice_line_number) > 0
        AND substr(invoice_line_number, 1, 1) BETWEEN '1' AND '9'
        AND invoice_line_number NOT GLOB '*[^0-9]*'
    ),
    uncertain_item_corrections INTEGER NOT NULL DEFAULT 0
        CHECK (uncertain_item_corrections BETWEEN 0 AND 1),
    reliable_item_corrections INTEGER NOT NULL DEFAULT 0
        CHECK (reliable_item_corrections BETWEEN 0 AND 1),
    category_corrections INTEGER NOT NULL DEFAULT 0
        CHECK (category_corrections BETWEEN 0 AND 2),
    semantic_responses INTEGER NOT NULL DEFAULT 0
        CHECK (semantic_responses BETWEEN 0 AND 2),
    outstanding_question_event_id TEXT,
    CHECK (status IS NOT NULL OR (
        current_evidence_version = 1
        AND uncertain_item_corrections = 0
        AND reliable_item_corrections = 0
        AND category_corrections = 0
        AND semantic_responses = 0
        AND outstanding_question_event_id IS NULL
        AND reason_code IS NULL
    )),
    FOREIGN KEY (claim_id, current_evidence_version)
        REFERENCES claim_revisions(claim_id, evidence_version)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (claim_id, outstanding_question_event_id)
        REFERENCES claim_events(claim_id, event_id)
        DEFERRABLE INITIALLY DEFERRED
) STRICT;

-- Only accepted evidence receives a version; rejected attempts remain auditable.
CREATE TABLE claim_revisions (
    revision_id TEXT PRIMARY KEY NOT NULL,
    claim_id TEXT NOT NULL REFERENCES claims(claim_id),
    evidence_version INTEGER,
    submitted_at TEXT NOT NULL,
    action_kind TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK (disposition IN (
        'ACCEPTED', 'INVALID', 'DUPLICATE_CONFLICT', 'ALLOWANCE_FAILURE', 'STALE'
    )),
    raw_evidence_json TEXT NOT NULL CHECK (json_valid(raw_evidence_json)),
    invoice_date TEXT,
    reimbursement_category TEXT CHECK (reimbursement_category IN (
        'WELLNESS', 'SMARTPHONE', 'BROADBAND', 'MOBILE_BILL',
        'BUSINESS_HOTEL', 'BUSINESS_TRANSPORT'
    )),
    invoice_item_amount TEXT,
    requested_reimbursement TEXT,
    validation_details_json TEXT NOT NULL CHECK (json_valid(validation_details_json)),
    UNIQUE (claim_id, evidence_version),
    UNIQUE (claim_id, revision_id),
    UNIQUE (claim_id, revision_id, evidence_version),
    CHECK (
        (disposition = 'ACCEPTED' AND evidence_version IS NOT NULL
            AND evidence_version > 0 AND invoice_date IS NOT NULL
            AND reimbursement_category IS NOT NULL AND invoice_item_amount IS NOT NULL
            AND requested_reimbursement IS NOT NULL)
        OR (disposition <> 'ACCEPTED' AND evidence_version IS NULL)
    )
) STRICT;

-- Payloads anticipate evaluation history, without implementing calls or routing.
CREATE TABLE evaluations (
    evaluation_id TEXT PRIMARY KEY NOT NULL,
    claim_id TEXT NOT NULL REFERENCES claims(claim_id),
    evidence_version INTEGER NOT NULL CHECK (evidence_version > 0),
    evaluation_run_id TEXT NOT NULL,
    question_kind TEXT NOT NULL CHECK (question_kind IN ('J1', 'J2', 'J3', 'J4')),
    question_revision TEXT NOT NULL,
    model_version TEXT NOT NULL,
    expected_status TEXT CHECK (expected_status IN (
        'NEED_INFO', 'HUMAN_REVIEW', 'POLICY_RESTRICTION', 'CANCELLED', 'PROCESSABLE'
    )),
    expected_state_version INTEGER NOT NULL CHECK (expected_state_version > 0),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    input_snapshot_json TEXT NOT NULL CHECK (json_valid(input_snapshot_json)),
    response_json TEXT CHECK (response_json IS NULL OR json_valid(response_json)),
    error_json TEXT CHECK (error_json IS NULL OR json_valid(error_json)),
    write_disposition TEXT CHECK (write_disposition IN ('APPLIED', 'STALE', 'DIAGNOSTIC')),
    UNIQUE (claim_id, evaluation_id),
    UNIQUE (claim_id, evaluation_id, evidence_version),
    FOREIGN KEY (claim_id, evidence_version)
        REFERENCES claim_revisions(claim_id, evidence_version)
) STRICT;

CREATE TABLE claim_events (
    event_id TEXT PRIMARY KEY NOT NULL,
    claim_id TEXT NOT NULL REFERENCES claims(claim_id),
    occurred_at TEXT NOT NULL,
    event_kind TEXT NOT NULL,
    evidence_version INTEGER,
    revision_id TEXT,
    evaluation_id TEXT,
    from_status TEXT CHECK (from_status IN (
        'NEED_INFO', 'HUMAN_REVIEW', 'POLICY_RESTRICTION', 'CANCELLED', 'PROCESSABLE'
    )),
    to_status TEXT CHECK (to_status IN (
        'NEED_INFO', 'HUMAN_REVIEW', 'POLICY_RESTRICTION', 'CANCELLED', 'PROCESSABLE'
    )),
    details_json TEXT NOT NULL CHECK (json_valid(details_json)),
    UNIQUE (claim_id, event_id),
    FOREIGN KEY (claim_id, evidence_version)
        REFERENCES claim_revisions(claim_id, evidence_version),
    FOREIGN KEY (claim_id, revision_id)
        REFERENCES claim_revisions(claim_id, revision_id),
    FOREIGN KEY (claim_id, evaluation_id)
        REFERENCES evaluations(claim_id, evaluation_id),
    -- These additional references apply only when both optional identifiers exist.
    -- Keep the pair references above: NULL evidence must still identify a real row.
    FOREIGN KEY (claim_id, revision_id, evidence_version)
        REFERENCES claim_revisions(claim_id, revision_id, evidence_version),
    FOREIGN KEY (claim_id, evaluation_id, evidence_version)
        REFERENCES evaluations(claim_id, evaluation_id, evidence_version)
) STRICT;

CREATE UNIQUE INDEX claims_blocking_identity ON claims (
    normalized_employee_id, normalized_merchant_name,
    normalized_invoice_number, invoice_line_number
)
WHERE status IS NULL OR status IN ('NEED_INFO', 'HUMAN_REVIEW', 'PROCESSABLE');

CREATE INDEX revisions_category_date
    ON claim_revisions(reimbursement_category, invoice_date);
CREATE INDEX evaluations_claim_history ON evaluations(claim_id, started_at, evaluation_id);
CREATE INDEX events_claim_history ON claim_events(claim_id, occurred_at, event_id);

CREATE TRIGGER revisions_no_update BEFORE UPDATE ON claim_revisions
BEGIN
    SELECT RAISE(ABORT, 'Revision history is immutable.');
END;

CREATE TRIGGER revisions_no_delete BEFORE DELETE ON claim_revisions
BEGIN
    SELECT RAISE(ABORT, 'Revision history is immutable.');
END;

-- REPLACE can bypass delete triggers unless recursive_triggers is enabled.
CREATE TRIGGER revisions_no_replace BEFORE INSERT ON claim_revisions
WHEN EXISTS (
    SELECT 1 FROM claim_revisions
    WHERE revision_id = NEW.revision_id
       OR (claim_id = NEW.claim_id AND evidence_version = NEW.evidence_version)
)
BEGIN
    SELECT RAISE(ABORT, 'Revision history is immutable.');
END;

CREATE TRIGGER events_no_update BEFORE UPDATE ON claim_events
BEGIN
    SELECT RAISE(ABORT, 'Event history is immutable.');
END;

CREATE TRIGGER events_no_delete BEFORE DELETE ON claim_events
BEGIN
    SELECT RAISE(ABORT, 'Event history is immutable.');
END;

CREATE TRIGGER events_no_replace BEFORE INSERT ON claim_events
WHEN EXISTS (SELECT 1 FROM claim_events WHERE event_id = NEW.event_id)
BEGIN
    SELECT RAISE(ABORT, 'Event history is immutable.');
END;

-- Bind each attempt to its original claim/evidence, while allowing completion.
-- Completed results also resist direct changes and replacement.
CREATE TRIGGER completed_evaluations_no_update BEFORE UPDATE ON evaluations
WHEN NEW.claim_id IS NOT OLD.claim_id
    OR NEW.evidence_version IS NOT OLD.evidence_version
    OR OLD.completed_at IS NOT NULL OR EXISTS (
    SELECT 1 FROM evaluations
    WHERE evaluation_id = NEW.evaluation_id AND completed_at IS NOT NULL
)
BEGIN
    SELECT RAISE(ABORT, 'Evaluation associations and completed records are immutable.');
END;

CREATE TRIGGER completed_evaluations_no_delete BEFORE DELETE ON evaluations
WHEN OLD.completed_at IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'Completed evaluations are immutable.');
END;

CREATE TRIGGER completed_evaluations_no_replace BEFORE INSERT ON evaluations
WHEN EXISTS (
    SELECT 1 FROM evaluations
    WHERE evaluation_id = NEW.evaluation_id AND (
        completed_at IS NOT NULL OR claim_id IS NOT NEW.claim_id
        OR evidence_version IS NOT NEW.evidence_version
    )
)
BEGIN
    SELECT RAISE(ABORT, 'Evaluation associations and completed records are immutable.');
END;
