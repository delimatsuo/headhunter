-- Migration 013: Create tables for bias tracking (Phase 14)
-- These tables support BIAS-03 (selection event logging) and BIAS-04 (bias metrics computation)

-- Selection events table for tracking candidate interactions
CREATE TABLE IF NOT EXISTS selection_events (
    event_id VARCHAR(64) PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    candidate_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('shown', 'clicked', 'shortlisted', 'contacted', 'interviewed', 'hired')),
    search_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    user_id_hash VARCHAR(64) NOT NULL,

    -- Inferred dimensions for bias analysis (no actual demographics collected)
    company_tier VARCHAR(50) CHECK (company_tier IN ('faang', 'enterprise', 'startup', 'other')),
    experience_band VARCHAR(20) CHECK (experience_band IN ('0-3', '3-7', '7-15', '15+')),
    specialty VARCHAR(50) CHECK (specialty IN ('backend', 'frontend', 'fullstack', 'devops', 'data', 'ml', 'mobile', 'other')),

    -- Search context
    rank INTEGER,
    score NUMERIC(5, 4),

    -- Indexes
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_selection_events_tenant_timestamp
    ON selection_events (tenant_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_selection_events_search_id
    ON selection_events (search_id);
CREATE INDEX IF NOT EXISTS idx_selection_events_event_type
    ON selection_events (event_type);
CREATE INDEX IF NOT EXISTS idx_selection_events_dimensions
    ON selection_events (tenant_id, company_tier, experience_band, specialty);

-- Bias metrics table for storing computed results
CREATE TABLE IF NOT EXISTS bias_metrics (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,
    computed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    metrics_json JSONB NOT NULL,

    -- For querying latest metrics
    CONSTRAINT unique_tenant_computed UNIQUE (tenant_id, computed_at)
);

CREATE INDEX IF NOT EXISTS idx_bias_metrics_tenant_computed
    ON bias_metrics (tenant_id, computed_at DESC);

-- Comment for documentation
COMMENT ON TABLE selection_events IS 'Tracks candidate selection events for bias analysis (BIAS-03)';
COMMENT ON TABLE bias_metrics IS 'Stores computed bias metrics from Fairlearn worker (BIAS-04)';
