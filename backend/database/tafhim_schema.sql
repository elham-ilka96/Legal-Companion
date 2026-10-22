-- Tafhim PostgreSQL schema (initial production-oriented baseline)
-- Assumption: PostgreSQL 15+; UUID primary keys; UTF-8; app-level authentication.
-- Important product rule: full OCR text/source-document text is NOT persisted in Tafhim's database.
-- Store original files in private object storage / Paperless-ngx. Persist simple summaries,
-- structured extracted fields, source references (document/page), approvals, and relationship metadata.
-- This is a fresh-database script; review enum/check values against the final product terminology.

BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- 1. Users and preferences
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_subject        VARCHAR(255) UNIQUE, -- ID from an external auth provider, if used
    email               VARCHAR(320),
    phone               VARCHAR(32),
    display_name        VARCHAR(160),
    account_status      VARCHAR(20) NOT NULL DEFAULT 'active'
                        CHECK (account_status IN ('active','suspended','pending_deletion','deleted')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ,
    CONSTRAINT users_auth_method_present CHECK (auth_subject IS NOT NULL OR email IS NOT NULL OR phone IS NOT NULL),
    CONSTRAINT users_id_user_unique UNIQUE (id)
);
CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email)) WHERE email IS NOT NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX uq_users_phone ON users (phone) WHERE phone IS NOT NULL AND deleted_at IS NULL;

CREATE TABLE user_settings (
    user_id                 UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    locale                  VARCHAR(20) NOT NULL DEFAULT 'fa-IR',
    timezone                VARCHAR(64) NOT NULL DEFAULT 'Asia/Tehran',
    calendar_preference     VARCHAR(16) NOT NULL DEFAULT 'jalali'
                            CHECK (calendar_preference IN ('jalali','gregorian')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 2. Stories and cases
-- Summaries here are current cached versions. Full version history is in version tables below.
-- ---------------------------------------------------------------------------
CREATE TABLE legal_stories (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    title               VARCHAR(240) NOT NULL,
    user_context        TEXT, -- written by the user; not a source-document transcript
    current_summary     TEXT,
    summary_revision    INTEGER NOT NULL DEFAULT 0 CHECK (summary_revision >= 0),
    story_status        VARCHAR(24) NOT NULL DEFAULT 'active'
                        CHECK (story_status IN ('active','archived','completed','needs_review')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at         TIMESTAMPTZ,
    deleted_at          TIMESTAMPTZ,
    UNIQUE (id, user_id)
);
CREATE INDEX ix_legal_stories_user_status ON legal_stories(user_id, story_status) WHERE deleted_at IS NULL;

CREATE TABLE cases (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    case_number_raw             VARCHAR(160),
    case_number_normalized      VARCHAR(160),
    archive_number_raw          VARCHAR(160),
    court_name                  VARCHAR(240),
    branch_name                 VARCHAR(160),
    jurisdiction                VARCHAR(80),
    case_type                   VARCHAR(80),
    case_subject                VARCHAR(300),
    current_stage               VARCHAR(120),
    current_status              VARCHAR(80) NOT NULL DEFAULT 'unknown'
                                CHECK (current_status IN ('unknown','active','pending','appeal','enforcement','closed','suspended','needs_review')),
    current_summary             TEXT,
    summary_revision            INTEGER NOT NULL DEFAULT 0 CHECK (summary_revision >= 0),
    current_state_revision      INTEGER NOT NULL DEFAULT 0 CHECK (current_state_revision >= 0),
    first_seen_at               TIMESTAMPTZ,
    last_activity_at            TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at                  TIMESTAMPTZ,
    UNIQUE (id, user_id)
);
-- Product assumption agreed so far: normalized case number is the primary deterministic document-to-case key.
-- If production evidence shows case numbers need jurisdiction/court scoping, expand this unique key accordingly.
CREATE UNIQUE INDEX uq_cases_user_case_number ON cases(user_id, case_number_normalized)
    WHERE case_number_normalized IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX ix_cases_user_status ON cases(user_id, current_status) WHERE deleted_at IS NULL;
CREATE INDEX ix_cases_user_activity ON cases(user_id, last_activity_at DESC) WHERE deleted_at IS NULL;

-- One active/confirmed story membership per case at a time. Old links are retained with valid_to set.
CREATE TABLE legal_story_case_links (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    legal_story_id      UUID NOT NULL,
    case_id             UUID NOT NULL,
    relationship_type   VARCHAR(40) NOT NULL DEFAULT 'part_of_story',
    match_method        VARCHAR(40) NOT NULL CHECK (match_method IN ('user_selected','user_confirmed_ai_suggestion','admin_corrected','imported')),
    match_candidate_id  UUID,
    confirmed_by        UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    confirmed_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_from          TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to            TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (legal_story_id, user_id) REFERENCES legal_stories(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (case_id, user_id) REFERENCES cases(id, user_id) ON DELETE RESTRICT,
    UNIQUE (id, user_id),
    CHECK (valid_to IS NULL OR valid_to >= valid_from)
);
CREATE UNIQUE INDEX uq_case_one_active_story ON legal_story_case_links(case_id) WHERE valid_to IS NULL;
CREATE INDEX ix_story_case_links_story ON legal_story_case_links(legal_story_id, valid_to);
CREATE INDEX ix_story_case_links_user ON legal_story_case_links(user_id, valid_to);

-- Candidate suggestions are separate from confirmed links; the AI must not silently make an ambiguous link definitive.
CREATE TABLE case_story_match_candidates (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    case_id                 UUID NOT NULL,
    legal_story_id          UUID NOT NULL,
    algorithm_version       VARCHAR(80) NOT NULL,
    score                   NUMERIC(6,5), -- rank score, not necessarily a calibrated probability
    score_breakdown         JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_manifest       JSONB NOT NULL DEFAULT '{}'::jsonb, -- IDs / signal metadata; no OCR transcript
    rationale               TEXT,
    status                  VARCHAR(24) NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','accepted','rejected','dismissed','expired')),
    reviewed_by             UUID REFERENCES users(id) ON DELETE RESTRICT,
    reviewed_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at              TIMESTAMPTZ,
    FOREIGN KEY (case_id, user_id) REFERENCES cases(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (legal_story_id, user_id) REFERENCES legal_stories(id, user_id) ON DELETE RESTRICT,
    UNIQUE (id, user_id),
    UNIQUE (id, case_id, user_id),
    CHECK (score IS NULL OR (score >= 0 AND score <= 1))
);
CREATE UNIQUE INDEX uq_pending_case_story_candidate ON case_story_match_candidates(case_id, legal_story_id)
    WHERE status = 'pending';
CREATE INDEX ix_match_candidates_inbox ON case_story_match_candidates(user_id, status, created_at DESC);

-- ---------------------------------------------------------------------------
-- 3. Documents and document-to-case links
-- No ocr_text/source_text column is intentionally defined.
-- ---------------------------------------------------------------------------
CREATE TABLE documents (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    storage_provider            VARCHAR(40) NOT NULL, -- e.g. private_object_storage, paperless_ngx
    external_document_id        VARCHAR(255),
    storage_key                 TEXT, -- private key/path, never a public URL
    original_filename           VARCHAR(255) NOT NULL,
    mime_type                   VARCHAR(120) NOT NULL,
    file_size_bytes             BIGINT CHECK (file_size_bytes IS NULL OR file_size_bytes >= 0),
    page_count                  INTEGER CHECK (page_count IS NULL OR page_count >= 0),
    sha256_hash                 CHAR(64),
    document_type               VARCHAR(100),
    document_type_status        VARCHAR(20) NOT NULL DEFAULT 'pending'
                                CHECK (document_type_status IN ('pending','suggested','confirmed','rejected','unknown')),
    document_date               DATE,
    document_date_raw           VARCHAR(100), -- preserve extracted date representation; no transcript
    document_date_calendar      VARCHAR(16) CHECK (document_date_calendar IS NULL OR document_date_calendar IN ('jalali','gregorian','unknown')),
    document_number_raw         VARCHAR(160),
    case_number_raw             VARCHAR(160),
    case_number_normalized      VARCHAR(160),
    current_summary             TEXT,
    summary_revision            INTEGER NOT NULL DEFAULT 0 CHECK (summary_revision >= 0),
    processing_status           VARCHAR(24) NOT NULL DEFAULT 'uploaded'
                                CHECK (processing_status IN ('uploaded','queued','processing','processed','needs_review','failed','deleted')),
    review_status               VARCHAR(24) NOT NULL DEFAULT 'pending'
                                CHECK (review_status IN ('pending','in_review','confirmed','partially_confirmed','rejected','not_required')),
    quality_status              VARCHAR(24) NOT NULL DEFAULT 'not_assessed'
                                CHECK (quality_status IN ('not_assessed','good','poor','unreadable','incomplete','needs_review')),
    upload_source               VARCHAR(40) NOT NULL DEFAULT 'user_upload',
    uploaded_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at                TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at                  TIMESTAMPTZ,
    UNIQUE (id, user_id)
);
CREATE INDEX ix_documents_user_uploaded ON documents(user_id, uploaded_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX ix_documents_user_status ON documents(user_id, processing_status, review_status) WHERE deleted_at IS NULL;
CREATE INDEX ix_documents_user_hash ON documents(user_id, sha256_hash) WHERE sha256_hash IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX ix_documents_user_case_number ON documents(user_id, case_number_normalized) WHERE case_number_normalized IS NOT NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX uq_documents_external_id ON documents(user_id, storage_provider, external_document_id)
    WHERE external_document_id IS NOT NULL AND deleted_at IS NULL;

CREATE TABLE document_case_links (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    document_id         UUID NOT NULL,
    case_id             UUID NOT NULL,
    link_role           VARCHAR(30) NOT NULL DEFAULT 'primary'
                        CHECK (link_role IN ('primary','supporting','referenced_only')),
    link_method         VARCHAR(40) NOT NULL
                        CHECK (link_method IN ('exact_case_number','user_selected','user_confirmed_ai','manual_admin','imported')),
    status              VARCHAR(20) NOT NULL DEFAULT 'confirmed'
                        CHECK (status IN ('proposed','confirmed','rejected','ended')),
    confidence          NUMERIC(6,5),
    confirmed_by        UUID REFERENCES users(id) ON DELETE RESTRICT,
    confirmed_at        TIMESTAMPTZ,
    valid_from          TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to            TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (case_id, user_id) REFERENCES cases(id, user_id) ON DELETE RESTRICT,
    UNIQUE (id, user_id),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CHECK (status <> 'confirmed' OR link_method = 'exact_case_number' OR (confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL))
);
CREATE UNIQUE INDEX uq_document_primary_case_current ON document_case_links(document_id)
    WHERE link_role = 'primary' AND status = 'confirmed' AND valid_to IS NULL;
CREATE INDEX ix_document_case_links_case ON document_case_links(case_id, status, valid_to);

-- Explicit case-number references stated by a document are not the same as assigning the document to that case.
CREATE TABLE document_case_references (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    source_document_id          UUID NOT NULL,
    source_case_id              UUID,
    referenced_case_number_raw  VARCHAR(160),
    referenced_case_number_norm VARCHAR(160),
    referenced_case_id          UUID,
    reference_type              VARCHAR(40) NOT NULL DEFAULT 'mentions'
                                CHECK (reference_type IN ('appeal_of','related_to','enforcement_of','counter_case','mentions','unknown')),
    confidence                  NUMERIC(6,5),
    verification_status         VARCHAR(20) NOT NULL DEFAULT 'suggested'
                                CHECK (verification_status IN ('suggested','confirmed','rejected','unresolved')),
    source_page                 INTEGER CHECK (source_page IS NULL OR source_page > 0),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (source_document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_case_id, user_id) REFERENCES cases(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (referenced_case_id, user_id) REFERENCES cases(id, user_id) ON DELETE RESTRICT,
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CHECK (referenced_case_id IS NOT NULL OR referenced_case_number_norm IS NOT NULL OR referenced_case_number_raw IS NOT NULL)
);
CREATE INDEX ix_case_refs_lookup ON document_case_references(user_id, referenced_case_number_norm);

-- ---------------------------------------------------------------------------
-- 4. Persons and participants
-- ---------------------------------------------------------------------------
CREATE TABLE persons (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    display_name        VARCHAR(240) NOT NULL,
    normalized_name     VARCHAR(240),
    person_status       VARCHAR(20) NOT NULL DEFAULT 'active'
                        CHECK (person_status IN ('active','merged','archived','needs_review')),
    merged_into_person_id UUID,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ,
    FOREIGN KEY (merged_into_person_id, user_id) REFERENCES persons(id, user_id) ON DELETE RESTRICT,
    UNIQUE (id, user_id),
    CHECK (merged_into_person_id IS NULL OR merged_into_person_id <> id)
);
CREATE INDEX ix_persons_user_name ON persons(user_id, normalized_name) WHERE deleted_at IS NULL;

CREATE TABLE person_aliases (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    person_id           UUID NOT NULL,
    alias_raw           VARCHAR(240) NOT NULL,
    alias_normalized    VARCHAR(240) NOT NULL,
    source_document_id  UUID,
    verification_status VARCHAR(20) NOT NULL DEFAULT 'suggested'
                        CHECK (verification_status IN ('suggested','confirmed','rejected')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (person_id, user_id) REFERENCES persons(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    UNIQUE (id, user_id)
);
CREATE INDEX ix_person_aliases_normalized ON person_aliases(user_id, alias_normalized);

CREATE TABLE case_participants (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    case_id             UUID NOT NULL,
    person_id           UUID NOT NULL,
    role                VARCHAR(80) NOT NULL,
    role_raw            VARCHAR(120),
    source_document_id  UUID,
    verification_status VARCHAR(20) NOT NULL DEFAULT 'suggested'
                        CHECK (verification_status IN ('suggested','confirmed','rejected')),
    valid_from          DATE,
    valid_to            DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (case_id, user_id) REFERENCES cases(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (person_id, user_id) REFERENCES persons(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    UNIQUE (id, user_id),
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);
CREATE INDEX ix_case_participants_case ON case_participants(case_id, verification_status);
CREATE INDEX ix_case_participants_person ON case_participants(person_id, verification_status);

CREATE TABLE document_person_mentions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    document_id         UUID NOT NULL,
    person_id           UUID,
    mentioned_name_raw  VARCHAR(240) NOT NULL,
    normalized_name     VARCHAR(240),
    role_in_document    VARCHAR(100),
    source_page         INTEGER CHECK (source_page IS NULL OR source_page > 0),
    confidence          NUMERIC(6,5),
    verification_status VARCHAR(20) NOT NULL DEFAULT 'suggested'
                        CHECK (verification_status IN ('suggested','confirmed','rejected','unmatched')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (person_id, user_id) REFERENCES persons(id, user_id) ON DELETE RESTRICT,
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);
CREATE INDEX ix_doc_person_mentions_document ON document_person_mentions(document_id);
CREATE INDEX ix_doc_person_mentions_name ON document_person_mentions(user_id, normalized_name);

-- ---------------------------------------------------------------------------
-- 5. Structured extracted facts (values only; no source-document transcript)
-- ---------------------------------------------------------------------------
CREATE TABLE document_extracted_facts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    document_id             UUID NOT NULL,
    processing_run_id       UUID, -- FK added after processing_runs is created
    field_key               VARCHAR(120) NOT NULL,
    occurrence_index        INTEGER NOT NULL DEFAULT 0 CHECK (occurrence_index >= 0),
    value_type              VARCHAR(24) NOT NULL DEFAULT 'string'
                            CHECK (value_type IN ('string','date','number','boolean','person','case_number','money','json')),
    value_raw               VARCHAR(1000), -- extracted field value, not the whole page/text
    value_normalized        VARCHAR(1000),
    value_json              JSONB,
    source_page             INTEGER CHECK (source_page IS NULL OR source_page > 0),
    confidence              NUMERIC(6,5),
    verification_status     VARCHAR(20) NOT NULL DEFAULT 'suggested'
                            CHECK (verification_status IN ('suggested','confirmed','rejected','superseded')),
    is_current              BOOLEAN NOT NULL DEFAULT TRUE,
    reviewed_by             UUID REFERENCES users(id) ON DELETE RESTRICT,
    reviewed_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    UNIQUE (id, user_id)
);
CREATE UNIQUE INDEX uq_current_document_fact ON document_extracted_facts(document_id, field_key, occurrence_index)
    WHERE is_current = TRUE;
CREATE INDEX ix_document_facts_field ON document_extracted_facts(user_id, field_key, value_normalized);

-- ---------------------------------------------------------------------------
-- 6. Events, evidence links and conflicting date observations
-- ---------------------------------------------------------------------------
CREATE TABLE case_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    case_id             UUID NOT NULL,
    event_type          VARCHAR(100) NOT NULL,
    title               VARCHAR(300) NOT NULL,
    description         TEXT, -- concise explanatory description, not copied full source text
    event_date          DATE,
    event_date_raw      VARCHAR(100),
    date_precision      VARCHAR(16) NOT NULL DEFAULT 'unknown'
                        CHECK (date_precision IN ('day','month','year','unknown')),
    event_status        VARCHAR(20) NOT NULL DEFAULT 'suggested'
                        CHECK (event_status IN ('suggested','confirmed','rejected','needs_review')),
    creation_method     VARCHAR(40) NOT NULL DEFAULT 'ai_extraction'
                        CHECK (creation_method IN ('ai_extraction','system_rule','user_created','user_corrected','imported')),
    source_processing_run_id UUID,
    created_by          UUID REFERENCES users(id) ON DELETE RESTRICT,
    confirmed_by        UUID REFERENCES users(id) ON DELETE RESTRICT,
    confirmed_at        TIMESTAMPTZ,
    occurred_at_unknown BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (case_id, user_id) REFERENCES cases(id, user_id) ON DELETE RESTRICT,
    UNIQUE (id, user_id)
);
CREATE INDEX ix_events_case_date ON case_events(case_id, event_date, created_at);
CREATE INDEX ix_events_user_status ON case_events(user_id, event_status, created_at DESC);

CREATE TABLE event_document_links (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    event_id            UUID NOT NULL,
    document_id         UUID NOT NULL,
    evidence_role       VARCHAR(24) NOT NULL DEFAULT 'supports'
                        CHECK (evidence_role IN ('supports','contradicts','mentions','context')),
    source_page         INTEGER CHECK (source_page IS NULL OR source_page > 0),
    confidence          NUMERIC(6,5),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (event_id, user_id) REFERENCES case_events(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    UNIQUE (event_id, document_id, evidence_role),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);
CREATE INDEX ix_event_document_links_document ON event_document_links(document_id);

CREATE TABLE event_date_observations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    event_id            UUID NOT NULL,
    document_id         UUID NOT NULL,
    observed_date       DATE,
    observed_date_raw   VARCHAR(100),
    calendar_system     VARCHAR(16) CHECK (calendar_system IS NULL OR calendar_system IN ('jalali','gregorian','unknown')),
    source_page         INTEGER CHECK (source_page IS NULL OR source_page > 0),
    confidence          NUMERIC(6,5),
    selection_status    VARCHAR(20) NOT NULL DEFAULT 'candidate'
                        CHECK (selection_status IN ('candidate','selected','rejected','conflicting')),
    selection_reason    VARCHAR(300),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (event_id, user_id) REFERENCES case_events(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    CHECK (observed_date IS NOT NULL OR observed_date_raw IS NOT NULL),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);
CREATE UNIQUE INDEX uq_one_selected_event_date ON event_date_observations(event_id) WHERE selection_status = 'selected';
CREATE INDEX ix_event_date_observations_event ON event_date_observations(event_id, created_at);

-- ---------------------------------------------------------------------------
-- 7. Case-to-story matching features, state history, and summary versioning
-- ---------------------------------------------------------------------------
CREATE TABLE case_match_features (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    case_id             UUID NOT NULL,
    feature_type        VARCHAR(60) NOT NULL
                        CHECK (feature_type IN ('topic','person','asset','incident','claim','case_reference','location','date','amount','other')),
    normalized_value    VARCHAR(600) NOT NULL,
    display_value       VARCHAR(600),
    source_document_id  UUID,
    source_event_id     UUID,
    confidence          NUMERIC(6,5),
    verification_status VARCHAR(20) NOT NULL DEFAULT 'suggested'
                        CHECK (verification_status IN ('suggested','confirmed','rejected')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (case_id, user_id) REFERENCES cases(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_event_id, user_id) REFERENCES case_events(id, user_id) ON DELETE RESTRICT,
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);
CREATE INDEX ix_case_match_features_lookup ON case_match_features(user_id, feature_type, normalized_value);
CREATE INDEX ix_case_match_features_case ON case_match_features(case_id, verification_status);

CREATE TABLE case_state_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    case_id             UUID NOT NULL,
    revision            INTEGER NOT NULL CHECK (revision > 0),
    state_payload       JSONB NOT NULL DEFAULT '{}'::jsonb, -- structured snapshot; no OCR transcript
    stage_snapshot      VARCHAR(120),
    status_snapshot     VARCHAR(80) NOT NULL,
    source_manifest     JSONB NOT NULL DEFAULT '{}'::jsonb, -- event/document IDs and revisions
    change_reason       VARCHAR(300),
    created_by_run_id   UUID,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (case_id, user_id) REFERENCES cases(id, user_id) ON DELETE RESTRICT,
    UNIQUE (case_id, revision),
    UNIQUE (id, user_id)
);
CREATE INDEX ix_case_state_versions_latest ON case_state_versions(case_id, revision DESC);

CREATE TABLE ai_processing_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    target_document_id  UUID,
    target_case_id      UUID,
    target_story_id     UUID,
    task_type           VARCHAR(48) NOT NULL
                        CHECK (task_type IN ('quality_assessment','document_extraction','document_summary','case_summary','story_summary','case_story_matching','event_extraction','other')),
    provider            VARCHAR(80),
    model_name          VARCHAR(120),
    prompt_version      VARCHAR(80),
    schema_version      VARCHAR(80),
    input_fingerprint   CHAR(64),
    input_manifest      JSONB NOT NULL DEFAULT '{}'::jsonb, -- IDs/versions/flags; never source OCR text
    status              VARCHAR(20) NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued','running','succeeded','failed','cancelled','skipped')),
    input_tokens        BIGINT CHECK (input_tokens IS NULL OR input_tokens >= 0),
    output_tokens       BIGINT CHECK (output_tokens IS NULL OR output_tokens >= 0),
    cost_amount         NUMERIC(14,8) CHECK (cost_amount IS NULL OR cost_amount >= 0),
    cost_currency       CHAR(3) DEFAULT 'USD',
    error_code          VARCHAR(100),
    safe_error_message  VARCHAR(1000), -- do not put source text/PII in error details
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (target_document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (target_case_id, user_id) REFERENCES cases(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (target_story_id, user_id) REFERENCES legal_stories(id, user_id) ON DELETE RESTRICT,
    CHECK (num_nonnulls(target_document_id, target_case_id, target_story_id) = 1),
    CHECK (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at),
    UNIQUE (id, user_id)
);
CREATE INDEX ix_ai_runs_user_recent ON ai_processing_runs(user_id, created_at DESC);
CREATE INDEX ix_ai_runs_status ON ai_processing_runs(status, created_at) WHERE status IN ('queued','running','failed');
CREATE INDEX ix_ai_runs_fingerprint ON ai_processing_runs(user_id, input_fingerprint) WHERE input_fingerprint IS NOT NULL;

ALTER TABLE document_extracted_facts ADD CONSTRAINT fk_document_facts_processing_run
    FOREIGN KEY (processing_run_id, user_id) REFERENCES ai_processing_runs(id, user_id) ON DELETE RESTRICT;
ALTER TABLE case_events ADD CONSTRAINT fk_case_events_processing_run
    FOREIGN KEY (source_processing_run_id, user_id) REFERENCES ai_processing_runs(id, user_id) ON DELETE RESTRICT;
ALTER TABLE case_state_versions ADD CONSTRAINT fk_case_state_created_by_run
    FOREIGN KEY (created_by_run_id, user_id) REFERENCES ai_processing_runs(id, user_id) ON DELETE RESTRICT;

-- Summary versions preserve history and explain which inputs/model revision created each summary.
CREATE TABLE document_summary_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    document_id         UUID NOT NULL,
    revision            INTEGER NOT NULL CHECK (revision > 0),
    summary_text        TEXT NOT NULL,
    input_fingerprint   CHAR(64),
    input_manifest      JSONB NOT NULL DEFAULT '{}'::jsonb,
    generation_run_id   UUID,
    approval_status     VARCHAR(20) NOT NULL DEFAULT 'generated'
                        CHECK (approval_status IN ('generated','reviewed','corrected','rejected')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    UNIQUE (document_id, revision)
);
CREATE INDEX ix_document_summary_versions_latest ON document_summary_versions(document_id, revision DESC);

CREATE TABLE case_summary_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    case_id             UUID NOT NULL,
    revision            INTEGER NOT NULL CHECK (revision > 0),
    summary_text        TEXT NOT NULL,
    input_fingerprint   CHAR(64),
    input_manifest      JSONB NOT NULL DEFAULT '{}'::jsonb,
    generation_run_id   UUID,
    approval_status     VARCHAR(20) NOT NULL DEFAULT 'generated'
                        CHECK (approval_status IN ('generated','reviewed','corrected','rejected')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (case_id, user_id) REFERENCES cases(id, user_id) ON DELETE RESTRICT,
    UNIQUE (case_id, revision)
);
CREATE INDEX ix_case_summary_versions_latest ON case_summary_versions(case_id, revision DESC);

CREATE TABLE story_summary_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    legal_story_id      UUID NOT NULL,
    revision            INTEGER NOT NULL CHECK (revision > 0),
    summary_text        TEXT NOT NULL,
    input_fingerprint   CHAR(64),
    input_manifest      JSONB NOT NULL DEFAULT '{}'::jsonb,
    generation_run_id   UUID,
    approval_status     VARCHAR(20) NOT NULL DEFAULT 'generated'
                        CHECK (approval_status IN ('generated','reviewed','corrected','rejected')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (legal_story_id, user_id) REFERENCES legal_stories(id, user_id) ON DELETE RESTRICT,
    UNIQUE (legal_story_id, revision)
);
CREATE INDEX ix_story_summary_versions_latest ON story_summary_versions(legal_story_id, revision DESC);

ALTER TABLE document_summary_versions ADD CONSTRAINT fk_document_summary_generation_run
    FOREIGN KEY (generation_run_id, user_id) REFERENCES ai_processing_runs(id, user_id) ON DELETE RESTRICT;
ALTER TABLE case_summary_versions ADD CONSTRAINT fk_case_summary_generation_run
    FOREIGN KEY (generation_run_id, user_id) REFERENCES ai_processing_runs(id, user_id) ON DELETE RESTRICT;
ALTER TABLE story_summary_versions ADD CONSTRAINT fk_story_summary_generation_run
    FOREIGN KEY (generation_run_id, user_id) REFERENCES ai_processing_runs(id, user_id) ON DELETE RESTRICT;

-- Add FK from a confirmed link to a candidate only after both tables exist.
ALTER TABLE legal_story_case_links ADD CONSTRAINT fk_story_case_link_candidate
    FOREIGN KEY (match_candidate_id, case_id, user_id) REFERENCES case_story_match_candidates(id, case_id, user_id) ON DELETE RESTRICT;

-- ---------------------------------------------------------------------------
-- 8. Review history and duplicate detection
-- ---------------------------------------------------------------------------
CREATE TABLE user_review_decisions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    target_type         VARCHAR(24) NOT NULL
                        CHECK (target_type IN ('document','case','story','event','person','document_case_link','story_case_candidate','extracted_fact')),
    document_id         UUID,
    case_id             UUID,
    legal_story_id      UUID,
    event_id            UUID,
    person_id           UUID,
    extracted_fact_id   UUID,
    document_case_link_id UUID,
    case_story_match_candidate_id UUID,
    field_key           VARCHAR(120),
    decision            VARCHAR(24) NOT NULL CHECK (decision IN ('accepted','corrected','rejected','deferred','merged','unmerged')),
    previous_value      JSONB,
    accepted_value      JSONB,
    reason              VARCHAR(500),
    related_processing_run_id UUID,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (case_id, user_id) REFERENCES cases(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (legal_story_id, user_id) REFERENCES legal_stories(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (event_id, user_id) REFERENCES case_events(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (person_id, user_id) REFERENCES persons(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (extracted_fact_id, user_id) REFERENCES document_extracted_facts(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (document_case_link_id, user_id) REFERENCES document_case_links(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (case_story_match_candidate_id, user_id) REFERENCES case_story_match_candidates(id, user_id) ON DELETE RESTRICT,
    CHECK (num_nonnulls(document_id, case_id, legal_story_id, event_id, person_id, extracted_fact_id, document_case_link_id, case_story_match_candidate_id) = 1),
    CHECK ((target_type = 'document' AND document_id IS NOT NULL) OR
           (target_type = 'case' AND case_id IS NOT NULL) OR
           (target_type = 'story' AND legal_story_id IS NOT NULL) OR
           (target_type = 'event' AND event_id IS NOT NULL) OR
           (target_type = 'person' AND person_id IS NOT NULL) OR
           (target_type = 'document_case_link' AND document_case_link_id IS NOT NULL) OR
           (target_type = 'story_case_candidate' AND case_story_match_candidate_id IS NOT NULL) OR
           (target_type = 'extracted_fact' AND extracted_fact_id IS NOT NULL)),
    FOREIGN KEY (related_processing_run_id, user_id) REFERENCES ai_processing_runs(id, user_id) ON DELETE RESTRICT
);
CREATE INDEX ix_review_decisions_user_recent ON user_review_decisions(user_id, created_at DESC);

CREATE TABLE duplicate_document_candidates (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    document_id             UUID NOT NULL,
    candidate_document_id   UUID NOT NULL,
    detection_method        VARCHAR(32) NOT NULL
                            CHECK (detection_method IN ('sha256_exact','case_type_date','text_similarity','metadata_similarity','manual')),
    similarity_score        NUMERIC(6,5),
    evidence_manifest       JSONB NOT NULL DEFAULT '{}'::jsonb,
    status                  VARCHAR(24) NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','confirmed_duplicate','not_duplicate','ignored')),
    reviewed_by             UUID REFERENCES users(id) ON DELETE RESTRICT,
    reviewed_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (candidate_document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    CHECK (document_id <> candidate_document_id),
    CHECK (document_id < candidate_document_id), -- normalize order before inserting
    CHECK (similarity_score IS NULL OR (similarity_score >= 0 AND similarity_score <= 1)),
    UNIQUE (user_id, document_id, candidate_document_id, detection_method)
);
CREATE INDEX ix_duplicate_candidates_review ON duplicate_document_candidates(user_id, status, created_at DESC);

-- ---------------------------------------------------------------------------
-- 9. Notifications, delivery attempts, reminders, and reliable async outbox
-- notifications = in-app inbox record; deliveries = email/SMS/push dispatch.
-- ---------------------------------------------------------------------------
CREATE TABLE notification_preferences (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_type   VARCHAR(80) NOT NULL, -- e.g. document_processed, review_required, reminder_due
    channel             VARCHAR(16) NOT NULL CHECK (channel IN ('in_app','email','sms','push')),
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    quiet_hours_start   TIME,
    quiet_hours_end     TIME,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, notification_type, channel),
    CHECK ((quiet_hours_start IS NULL AND quiet_hours_end IS NULL) OR
           (quiet_hours_start IS NOT NULL AND quiet_hours_end IS NOT NULL))
);
CREATE INDEX ix_notification_preferences_user ON notification_preferences(user_id);

CREATE TABLE reminders (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    title                   VARCHAR(240) NOT NULL,
    description             VARCHAR(1000), -- user-authored short note; not a legal conclusion
    due_at                  TIMESTAMPTZ NOT NULL,
    timezone                VARCHAR(64) NOT NULL DEFAULT 'Asia/Tehran',
    related_legal_story_id  UUID,
    related_case_id         UUID,
    related_document_id     UUID,
    related_event_id        UUID,
    reminder_status         VARCHAR(20) NOT NULL DEFAULT 'scheduled'
                            CHECK (reminder_status IN ('scheduled','sent','completed','cancelled','snoozed','failed')),
    created_from            VARCHAR(24) NOT NULL DEFAULT 'user'
                            CHECK (created_from IN ('user','confirmed_document_date','confirmed_event','system')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at            TIMESTAMPTZ,
    cancelled_at             TIMESTAMPTZ,
    FOREIGN KEY (related_legal_story_id, user_id) REFERENCES legal_stories(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (related_case_id, user_id) REFERENCES cases(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (related_document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (related_event_id, user_id) REFERENCES case_events(id, user_id) ON DELETE RESTRICT,
    CHECK (num_nonnulls(related_legal_story_id, related_case_id, related_document_id, related_event_id) >= 1),
    UNIQUE (id, user_id)
);
CREATE INDEX ix_reminders_due ON reminders(reminder_status, due_at) WHERE reminder_status IN ('scheduled','snoozed');
CREATE INDEX ix_reminders_user_due ON reminders(user_id, due_at DESC);

CREATE TABLE notifications (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    notification_type       VARCHAR(80) NOT NULL,
    title                   VARCHAR(240) NOT NULL,
    body                    VARCHAR(2000) NOT NULL,
    severity                VARCHAR(16) NOT NULL DEFAULT 'info'
                            CHECK (severity IN ('info','success','warning','urgent')),
    status                  VARCHAR(16) NOT NULL DEFAULT 'unread'
                            CHECK (status IN ('unread','read','archived','expired')),
    related_legal_story_id  UUID,
    related_case_id         UUID,
    related_document_id     UUID,
    related_event_id        UUID,
    reminder_id             UUID,
    action_label            VARCHAR(100),
    action_route            VARCHAR(500), -- internal route identifier only; do not use arbitrary untrusted URLs
    payload                 JSONB NOT NULL DEFAULT '{}'::jsonb, -- non-sensitive IDs / UI metadata only
    deduplication_key       VARCHAR(240),
    scheduled_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at                 TIMESTAMPTZ,
    archived_at             TIMESTAMPTZ,
    expires_at              TIMESTAMPTZ,
    FOREIGN KEY (related_legal_story_id, user_id) REFERENCES legal_stories(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (related_case_id, user_id) REFERENCES cases(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (related_document_id, user_id) REFERENCES documents(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (related_event_id, user_id) REFERENCES case_events(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (reminder_id, user_id) REFERENCES reminders(id, user_id) ON DELETE RESTRICT,
    UNIQUE (id, user_id)
);
CREATE UNIQUE INDEX uq_notification_dedupe ON notifications(user_id, deduplication_key)
    WHERE deduplication_key IS NOT NULL;
CREATE INDEX ix_notifications_inbox ON notifications(user_id, status, created_at DESC);
CREATE INDEX ix_notifications_scheduled ON notifications(scheduled_at) WHERE scheduled_at IS NOT NULL AND status = 'unread';

CREATE TABLE notification_deliveries (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    notification_id         UUID NOT NULL,
    channel                 VARCHAR(12) NOT NULL CHECK (channel IN ('email','sms','push')),
    destination_masked      VARCHAR(200), -- masked display/debug value; never log full phone/token unnecessarily
    provider                VARCHAR(80),
    provider_message_id     VARCHAR(255),
    delivery_status         VARCHAR(20) NOT NULL DEFAULT 'queued'
                            CHECK (delivery_status IN ('queued','sending','sent','delivered','failed','cancelled','skipped')),
    attempt_count           INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    next_attempt_at         TIMESTAMPTZ,
    sent_at                 TIMESTAMPTZ,
    delivered_at            TIMESTAMPTZ,
    last_error_code         VARCHAR(100),
    last_error_safe_message VARCHAR(500),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (notification_id, user_id) REFERENCES notifications(id, user_id) ON DELETE RESTRICT,
    UNIQUE (notification_id, channel)
);
CREATE INDEX ix_notification_deliveries_retry ON notification_deliveries(delivery_status, next_attempt_at)
    WHERE delivery_status IN ('queued','failed');

CREATE TABLE notification_delivery_attempts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_id             UUID NOT NULL REFERENCES notification_deliveries(id) ON DELETE CASCADE,
    attempt_number           INTEGER NOT NULL CHECK (attempt_number > 0),
    attempt_status           VARCHAR(20) NOT NULL CHECK (attempt_status IN ('started','succeeded','failed','timeout')),
    provider_response_code  VARCHAR(100),
    safe_error_message      VARCHAR(500),
    attempted_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at            TIMESTAMPTZ,
    UNIQUE (delivery_id, attempt_number)
);
CREATE INDEX ix_delivery_attempts_recent ON notification_delivery_attempts(delivery_id, attempted_at DESC);

-- Optional for push channel; store device token encrypted by the application, not in plaintext.
CREATE TABLE user_push_devices (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform            VARCHAR(16) NOT NULL CHECK (platform IN ('web','ios','android')),
    token_encrypted     BYTEA NOT NULL,
    token_fingerprint   CHAR(64) NOT NULL,
    device_label        VARCHAR(120),
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    last_seen_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at          TIMESTAMPTZ,
    UNIQUE (token_fingerprint)
);
CREATE INDEX ix_push_devices_user_active ON user_push_devices(user_id, active) WHERE active = TRUE;

-- Transactional outbox: insert along with a business change; worker delivers/handles it idempotently.
CREATE TABLE notification_outbox (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE RESTRICT,
    event_type          VARCHAR(100) NOT NULL,
    aggregate_type      VARCHAR(40) NOT NULL,
    aggregate_id        UUID NOT NULL,
    payload             JSONB NOT NULL DEFAULT '{}'::jsonb, -- IDs/flags, not raw OCR or sensitive document text
    deduplication_key   VARCHAR(240),
    status              VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','processing','processed','failed','dead_letter')),
    attempts            INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    available_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_at           TIMESTAMPTZ,
    processed_at        TIMESTAMPTZ,
    last_error_code     VARCHAR(100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (deduplication_key IS NULL OR length(deduplication_key) > 0)
);
CREATE UNIQUE INDEX uq_notification_outbox_dedupe ON notification_outbox(user_id, deduplication_key) WHERE deduplication_key IS NOT NULL;
CREATE INDEX ix_notification_outbox_worker ON notification_outbox(status, available_at, created_at)
    WHERE status IN ('pending','failed');

-- ---------------------------------------------------------------------------
-- 10. Audit log
-- ---------------------------------------------------------------------------
CREATE TABLE audit_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE RESTRICT,
    actor_type          VARCHAR(20) NOT NULL DEFAULT 'user'
                        CHECK (actor_type IN ('user','system','admin','worker')),
    action              VARCHAR(100) NOT NULL,
    entity_type         VARCHAR(60) NOT NULL,
    entity_id           UUID,
    request_id          VARCHAR(120),
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb, -- non-sensitive operational metadata only
    ip_address_hash     CHAR(64), -- optional pseudonymized IP fingerprint, not raw IP by default
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_user_recent ON audit_logs(user_id, created_at DESC);
CREATE INDEX ix_audit_entity ON audit_logs(entity_type, entity_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 11. updated_at helper triggers
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_user_settings_updated_at BEFORE UPDATE ON user_settings FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_legal_stories_updated_at BEFORE UPDATE ON legal_stories FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_cases_updated_at BEFORE UPDATE ON cases FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_documents_updated_at BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_document_case_references_updated_at BEFORE UPDATE ON document_case_references FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_persons_updated_at BEFORE UPDATE ON persons FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_case_participants_updated_at BEFORE UPDATE ON case_participants FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_case_events_updated_at BEFORE UPDATE ON case_events FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_notification_preferences_updated_at BEFORE UPDATE ON notification_preferences FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_reminders_updated_at BEFORE UPDATE ON reminders FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_notification_deliveries_updated_at BEFORE UPDATE ON notification_deliveries FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;

-- Implementation notes:
-- 1) Apply all ownership checks in backend and consider PostgreSQL Row-Level Security as defense-in-depth.
-- 2) Use private object storage for originals. Keep OCR transient and clear temp files after processing.
-- 3) Do not call LLM/OCR from database triggers; enqueue jobs/outbox records and process asynchronously.
-- 4) For each new confirmed document->case link: create/update document summary, facts, events, case state/summary;
--    if the case has a confirmed story link, enqueue story summary regeneration.
-- 5) Candidate story matching must not create a confirmed link until user confirmation.
-- 6) Legal reminders/notifications should reflect dates explicitly found or confirmed by the user; don't infer legal deadlines as certain without verified rules.
