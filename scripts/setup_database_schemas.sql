-- Headhunter database schema setup
-- Applies required schemas and tables for the headhunter-ai-0088 environment

\connect headhunter

-- Schema creation
CREATE SCHEMA IF NOT EXISTS search AUTHORIZATION :app_user;
CREATE SCHEMA IF NOT EXISTS taxonomy AUTHORIZATION :app_user;
CREATE SCHEMA IF NOT EXISTS msgs AUTHORIZATION :app_user;
CREATE SCHEMA IF NOT EXISTS ops AUTHORIZATION :app_user;

-- Ensure pgvector extension exists
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

-- SEARCH SCHEMA OBJECTS
SET search_path TO search, public;

CREATE TABLE IF NOT EXISTS search.candidate_profiles (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    profile_source TEXT NOT NULL,
    full_name TEXT,
    headline TEXT,
    location TEXT,
    skills TEXT[],
    experience JSONB,
    education JSONB,
    metadata JSONB,
    legal_basis TEXT,
    consent_record TEXT,
    transfer_mechanism TEXT,
    search_document TSVECTOR NOT NULL DEFAULT to_tsvector('portuguese', COALESCE(full_name, '') || ' ' || COALESCE(headline, '')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS search.candidate_embeddings (
    profile_id UUID PRIMARY KEY REFERENCES search.candidate_profiles(id) ON DELETE CASCADE,
    tenant_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL,
    embedding_norm DOUBLE PRECISION,
    last_indexed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for vector similarity as specified
CREATE INDEX IF NOT EXISTS candidate_embeddings_hnsw
    ON search.candidate_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS candidate_profiles_fts_idx
    ON search.candidate_profiles USING GIN (search_document);

CREATE TABLE IF NOT EXISTS search.search_logs (
    id BIGSERIAL,
    tenant_id TEXT NOT NULL,
    search_id UUID NOT NULL,
    request_payload JSONB NOT NULL,
    response_payload JSONB,
    latency_ms INTEGER,
    source_service TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE IF NOT EXISTS search.search_logs_y2024m01
    PARTITION OF search.search_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE IF NOT EXISTS search.search_logs_y2025m01
    PARTITION OF search.search_logs
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE IF NOT EXISTS search.search_logs_y2025m10
    PARTITION OF search.search_logs
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');

-- Create trigger function for Portuguese FTS
CREATE OR REPLACE FUNCTION search.update_candidate_search_document()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_document := to_tsvector('portuguese', COALESCE(NEW.full_name, '') || ' ' || COALESCE(NEW.headline, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for Portuguese FTS on candidate_profiles
DROP TRIGGER IF EXISTS candidate_profiles_search_document_trigger ON search.candidate_profiles;
CREATE TRIGGER candidate_profiles_search_document_trigger
    BEFORE INSERT OR UPDATE OF full_name, headline
    ON search.candidate_profiles
    FOR EACH ROW
    EXECUTE FUNCTION search.update_candidate_search_document();

-- TAXONOMY SCHEMA OBJECTS
SET search_path TO taxonomy, public;

CREATE TABLE IF NOT EXISTS taxonomy.eco_occupation (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    parent_id TEXT,
    synonyms TEXT[],
    normalized_title TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS taxonomy.eco_relationship (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source_occupation_id TEXT NOT NULL REFERENCES taxonomy.eco_occupation(id) ON DELETE CASCADE,
    target_occupation_id TEXT NOT NULL REFERENCES taxonomy.eco_occupation(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    weight NUMERIC(5,4) DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS eco_rel_by_source
    ON taxonomy.eco_relationship (source_occupation_id, relationship_type);

-- MSGS SCHEMA OBJECTS
SET search_path TO msgs, public;

CREATE TABLE IF NOT EXISTS msgs.skill_demand (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    occupation_id TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    demand_score NUMERIC(6,3) NOT NULL,
    trend JSONB,
    observed_at DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS skill_demand_by_occ
    ON msgs.skill_demand (occupation_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS msgs.role_template (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    required_skills TEXT[] NOT NULL,
    optional_skills TEXT[],
    default_prompt TEXT,
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- OPS SCHEMA OBJECTS
SET search_path TO ops, public;

CREATE TABLE IF NOT EXISTS ops.refresh_jobs (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failure_reason TEXT,
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS ops.pipeline_metrics (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    service_name TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value NUMERIC(16,4) NOT NULL,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS pipeline_metrics_by_service
    ON ops.pipeline_metrics (service_name, metric_name, recorded_at DESC);

-- Permissions (placeholders for substitution in provisioning script)
GRANT USAGE ON SCHEMA search TO :app_user;
GRANT USAGE ON SCHEMA taxonomy TO :app_user;
GRANT USAGE ON SCHEMA msgs TO :app_user;
GRANT USAGE ON SCHEMA ops TO :app_user;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA search TO :app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA taxonomy TO :app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA msgs TO :app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ops TO :app_user;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA search TO :app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA taxonomy TO :app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA msgs TO :app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ops TO :app_user;

GRANT CONNECT ON DATABASE headhunter TO :app_user;
GRANT CONNECT ON DATABASE headhunter TO :analytics_user;
GRANT USAGE ON SCHEMA search TO :analytics_user;
GRANT SELECT ON ALL TABLES IN SCHEMA search TO :analytics_user;

RESET search_path;
