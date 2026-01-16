-- Migration: Create sourcing schema for Ella Sourcing SaaS product
-- LinkedIn candidate database with AI enrichment for Brazilian software engineers
-- Created: 2026-01-13

-- Create sourcing schema
CREATE SCHEMA IF NOT EXISTS sourcing;

-- Main candidates table
CREATE TABLE IF NOT EXISTS sourcing.candidates (
    id SERIAL PRIMARY KEY,
    linkedin_url VARCHAR(500) UNIQUE NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    headline VARCHAR(500),
    location VARCHAR(200),
    country VARCHAR(100) DEFAULT 'Brazil',
    summary TEXT,
    profile_image_url VARCHAR(500),
    connections INTEGER,
    followers INTEGER,

    -- AI Enrichment fields (from Together AI)
    intelligent_analysis JSONB,
    career_trajectory JSONB,
    skill_assessment JSONB,
    company_pedigree JSONB,
    recruiter_insights JSONB,

    -- Metadata
    scraped_at TIMESTAMP DEFAULT NOW(),
    enriched_at TIMESTAMP,
    last_updated TIMESTAMP DEFAULT NOW(),
    source VARCHAR(50) DEFAULT 'apify_linkedin',

    -- LGPD Compliance
    consent_status VARCHAR(20) DEFAULT 'pending',
    opt_out_requested_at TIMESTAMP,
    deleted_at TIMESTAMP
);

-- Experience history
CREATE TABLE IF NOT EXISTS sourcing.experience (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER REFERENCES sourcing.candidates(id) ON DELETE CASCADE,
    company_name VARCHAR(300),
    company_linkedin_url VARCHAR(500),
    title VARCHAR(300),
    location VARCHAR(200),
    start_date DATE,
    end_date DATE,
    is_current BOOLEAN DEFAULT FALSE,
    description TEXT,

    -- Company intelligence (enriched)
    company_size VARCHAR(50),
    company_industry VARCHAR(200),
    company_tech_stack JSONB,

    created_at TIMESTAMP DEFAULT NOW()
);

-- Skills lookup table
CREATE TABLE IF NOT EXISTS sourcing.skills (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) UNIQUE NOT NULL,
    category VARCHAR(100), -- 'programming', 'framework', 'cloud', 'soft_skill'
    normalized_name VARCHAR(200)
);

-- Candidate-Skills junction table
CREATE TABLE IF NOT EXISTS sourcing.candidate_skills (
    candidate_id INTEGER REFERENCES sourcing.candidates(id) ON DELETE CASCADE,
    skill_id INTEGER REFERENCES sourcing.skills(id) ON DELETE CASCADE,
    endorsement_count INTEGER DEFAULT 0,
    confidence_score FLOAT, -- From AI enrichment (0.0-1.0)
    is_inferred BOOLEAN DEFAULT FALSE, -- True if inferred from company/role
    PRIMARY KEY (candidate_id, skill_id)
);

-- Embeddings for semantic search (768-dim Gemini embeddings)
CREATE TABLE IF NOT EXISTS sourcing.embeddings (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER REFERENCES sourcing.candidates(id) ON DELETE CASCADE UNIQUE,
    embedding vector(768),
    model_version VARCHAR(100) DEFAULT 'gemini-embedding-001',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_sourcing_candidates_location ON sourcing.candidates(location);
CREATE INDEX IF NOT EXISTS idx_sourcing_candidates_country ON sourcing.candidates(country);
CREATE INDEX IF NOT EXISTS idx_sourcing_candidates_scraped_at ON sourcing.candidates(scraped_at);
CREATE INDEX IF NOT EXISTS idx_sourcing_candidates_enriched_at ON sourcing.candidates(enriched_at);
CREATE INDEX IF NOT EXISTS idx_sourcing_candidates_deleted_at ON sourcing.candidates(deleted_at) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_sourcing_experience_candidate ON sourcing.experience(candidate_id);
CREATE INDEX IF NOT EXISTS idx_sourcing_experience_company ON sourcing.experience(company_name);
CREATE INDEX IF NOT EXISTS idx_sourcing_experience_current ON sourcing.experience(is_current) WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_sourcing_skills_category ON sourcing.skills(category);
CREATE INDEX IF NOT EXISTS idx_sourcing_skills_normalized ON sourcing.skills(normalized_name);

-- IVFFlat index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_sourcing_embeddings_vector ON sourcing.embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Add comments for documentation
COMMENT ON SCHEMA sourcing IS 'Ella Sourcing SaaS - LinkedIn candidate database for Brazilian software engineers';
COMMENT ON TABLE sourcing.candidates IS 'Main candidate profiles scraped from LinkedIn and enriched with Together AI';
COMMENT ON TABLE sourcing.experience IS 'Work experience history for each candidate';
COMMENT ON TABLE sourcing.skills IS 'Normalized skill taxonomy';
COMMENT ON TABLE sourcing.candidate_skills IS 'Many-to-many relationship between candidates and skills';
COMMENT ON TABLE sourcing.embeddings IS '768-dim Gemini embeddings for semantic search';
COMMENT ON COLUMN sourcing.candidates.consent_status IS 'LGPD compliance: pending, consented, opted_out';
COMMENT ON COLUMN sourcing.candidate_skills.is_inferred IS 'True if skill was inferred from company/role context by AI';
