-- Reference only. Codex MUST implement through the repository's SQLAlchemy + Alembic conventions.
-- PostgreSQL-oriented.

CREATE TABLE lottery_dlt_draws (
    issue VARCHAR(16) PRIMARY KEY,
    draw_date DATE,
    front_numbers SMALLINT[] NOT NULL,
    back_numbers SMALLINT[] NOT NULL,
    front_mask BIGINT NOT NULL,
    back_mask BIGINT NOT NULL,
    source VARCHAR(255),
    source_checksum VARCHAR(128),
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    schema_version VARCHAR(32) NOT NULL DEFAULT '1'
);

CREATE TABLE lottery_dlt_runs (
    id UUID PRIMARY KEY,
    target_issue VARCHAR(16) NOT NULL,
    history_cutoff_issue VARCHAR(16) NOT NULL,
    mode VARCHAR(32) NOT NULL, -- model/random/package/scarcity
    model_version VARCHAR(64),
    config JSONB NOT NULL,
    random_seed BIGINT,
    status VARCHAR(16) NOT NULL DEFAULT 'draft', -- draft/frozen/settled
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_lottery_dlt_runs_target ON lottery_dlt_runs(target_issue);

CREATE TABLE lottery_dlt_tickets (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES lottery_dlt_runs(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    front_numbers SMALLINT[] NOT NULL,
    back_numbers SMALLINT[] NOT NULL,
    front_mask BIGINT NOT NULL,
    back_mask BIGINT NOT NULL,
    expression_type VARCHAR(32) NOT NULL DEFAULT 'single',
    addon BOOLEAN NOT NULL DEFAULT FALSE,
    multiplier SMALLINT NOT NULL DEFAULT 1,
    expanded_bets INTEGER NOT NULL DEFAULT 1,
    cost_yuan NUMERIC(12,2) NOT NULL,
    score_breakdown JSONB,
    structure_features JSONB,
    UNIQUE(run_id, ordinal)
);

CREATE TABLE lottery_dlt_collision_profiles (
    ticket_id UUID PRIMARY KEY REFERENCES lottery_dlt_tickets(id) ON DELETE CASCADE,
    history_start_issue VARCHAR(16),
    history_end_issue VARCHAR(16) NOT NULL,
    history_draw_count INTEGER NOT NULL,
    n_total_hits INTEGER[] NOT NULL, -- index 0..7
    n_front_back JSONB NOT NULL, -- 6x3 matrix, [front_hits][back_hits]
    max_total_hits SMALLINT NOT NULL,
    scarcity_key INTEGER[] NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE lottery_dlt_run_aggregates (
    run_id UUID PRIMARY KEY REFERENCES lottery_dlt_runs(id) ON DELETE CASCADE,
    candidate_count INTEGER NOT NULL,
    m_total_hits BIGINT[] NOT NULL,
    u_total_hits INTEGER[] NOT NULL,
    m_front_back JSONB NOT NULL,
    u_front_back JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE lottery_dlt_freezes (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES lottery_dlt_runs(id) ON DELETE RESTRICT,
    version INTEGER NOT NULL,
    frozen_payload JSONB NOT NULL,
    sha256 CHAR(64) NOT NULL,
    frozen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(run_id, version)
);

CREATE TABLE lottery_dlt_settlements (
    run_id UUID PRIMARY KEY REFERENCES lottery_dlt_runs(id) ON DELETE RESTRICT,
    actual_issue VARCHAR(16) NOT NULL REFERENCES lottery_dlt_draws(issue),
    result JSONB NOT NULL,
    settled_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
