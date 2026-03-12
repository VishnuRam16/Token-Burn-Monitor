-- ============================================================
-- raw_spend_logs: high-write append-only table for LLM usage
-- ============================================================

CREATE TABLE IF NOT EXISTS raw_spend_logs (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id      UUID            NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    -- caller context
    user_id         TEXT            NOT NULL,
    feature_name    TEXT,

    -- model info
    model           TEXT            NOT NULL,
    provider        TEXT,

    -- token counts
    prompt_tokens       INTEGER     NOT NULL DEFAULT 0,
    completion_tokens   INTEGER     NOT NULL DEFAULT 0,
    total_tokens        INTEGER     NOT NULL DEFAULT 0,

    -- cost
    cost_usd        NUMERIC(12,8)   NOT NULL DEFAULT 0,

    -- latency
    latency_ms      INTEGER,

    -- flexible sidecar for anything else
    metadata        JSONB           NOT NULL DEFAULT '{}'::jsonb
);

-- ── Indexes optimized for the query patterns we care about ──

-- Watchdog / dbt: aggregate by user + day
CREATE INDEX IF NOT EXISTS idx_spend_user_created
    ON raw_spend_logs (user_id, created_at DESC);

-- dbt: partition-friendly scans by date
CREATE INDEX IF NOT EXISTS idx_spend_created
    ON raw_spend_logs (created_at DESC);

-- Dedup guard (idempotent re-inserts)
CREATE UNIQUE INDEX IF NOT EXISTS idx_spend_request_id
    ON raw_spend_logs (request_id);

-- JSONB metadata queries (GIN for @> containment)
CREATE INDEX IF NOT EXISTS idx_spend_metadata
    ON raw_spend_logs USING gin (metadata);
