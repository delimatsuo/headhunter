-- Cloud SQL schema definition for hh-msgs-svc
CREATE SCHEMA IF NOT EXISTS msgs;

CREATE TABLE IF NOT EXISTS msgs.skill_adjacency (
    tenant_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    related_skill_id TEXT NOT NULL,
    related_skill_label TEXT NOT NULL,
    pmi_score NUMERIC NOT NULL,
    support INTEGER NOT NULL,
    recency_days INTEGER NOT NULL DEFAULT 0,
    sources TEXT[] NOT NULL DEFAULT ARRAY['job_postings'],
    joint_count INTEGER NOT NULL DEFAULT 0,
    base_count INTEGER NOT NULL DEFAULT 0,
    related_count INTEGER NOT NULL DEFAULT 0,
    total_documents INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, skill_id, related_skill_id)
);

CREATE INDEX IF NOT EXISTS idx_msgs_skill_adjacency_tenant_skill
    ON msgs.skill_adjacency (tenant_id, skill_id)
    INCLUDE (pmi_score, support, recency_days);

CREATE TABLE IF NOT EXISTS msgs.role_template (
    tenant_id TEXT NOT NULL,
    eco_id TEXT NOT NULL,
    locale TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    required_skills JSONB NOT NULL,
    preferred_skills JSONB NOT NULL,
    yoe_min INTEGER,
    yoe_max INTEGER,
    version TEXT NOT NULL,
    prevalence_by_region JSONB,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, eco_id, locale)
);

CREATE INDEX IF NOT EXISTS idx_msgs_role_template_tenant_eco
    ON msgs.role_template (tenant_id, eco_id, locale);

CREATE TABLE IF NOT EXISTS msgs.skill_demand (
    tenant_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    country TEXT NOT NULL,
    region TEXT NOT NULL,
    industry TEXT,
    week_start DATE NOT NULL,
    postings_count INTEGER NOT NULL,
    demand_index NUMERIC NOT NULL,
    ema NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    version TEXT NOT NULL DEFAULT '2024.1',
    PRIMARY KEY (tenant_id, skill_id, region, industry, week_start)
);

CREATE INDEX IF NOT EXISTS idx_msgs_skill_demand_latest
    ON msgs.skill_demand (tenant_id, skill_id, region, industry, week_start DESC)
    INCLUDE (postings_count, demand_index);

COMMENT ON TABLE msgs.skill_adjacency IS 'Skill co-occurrence PMI metrics per tenant.';
COMMENT ON TABLE msgs.role_template IS 'Role templates generated from market data per tenant.';
COMMENT ON TABLE msgs.skill_demand IS 'Historical demand metrics for skills, used for EMA calculations.';
