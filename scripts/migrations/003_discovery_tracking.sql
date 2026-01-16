-- Migration: Add discovery tracking for efficient profile acquisition
-- Separates cheap discovery from expensive extraction
-- Created: 2026-01-14

-- Track discovered LinkedIn URLs before extraction
CREATE TABLE IF NOT EXISTS sourcing.discovered_urls (
    id SERIAL PRIMARY KEY,
    linkedin_url VARCHAR(500) UNIQUE NOT NULL,

    -- Discovery metadata
    discovered_at TIMESTAMP DEFAULT NOW(),
    discovery_source VARCHAR(100),  -- 'apify_search', 'company_page', 'referral'
    discovery_query VARCHAR(500),   -- Search query used
    discovery_location VARCHAR(200), -- Location filter used

    -- Basic info from discovery (before full extraction)
    name VARCHAR(200),
    headline VARCHAR(500),
    location VARCHAR(200),

    -- Processing status
    status VARCHAR(20) DEFAULT 'discovered',  -- discovered, extracted, failed, skipped
    extracted_at TIMESTAMP,
    extraction_error TEXT,

    -- Quality signals (for prioritization)
    priority_score INTEGER DEFAULT 50,  -- 0-100, higher = extract first
    has_tech_keywords BOOLEAN DEFAULT FALSE,
    estimated_seniority VARCHAR(20),  -- junior, mid, senior, lead, executive

    -- Dedup tracking
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of INTEGER REFERENCES sourcing.candidates(id)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_discovered_status ON sourcing.discovered_urls(status);
CREATE INDEX IF NOT EXISTS idx_discovered_priority ON sourcing.discovered_urls(priority_score DESC)
    WHERE status = 'discovered';
CREATE INDEX IF NOT EXISTS idx_discovered_location ON sourcing.discovered_urls(discovery_location);
CREATE INDEX IF NOT EXISTS idx_discovered_url_lower ON sourcing.discovered_urls(LOWER(linkedin_url));

-- Track discovery campaigns/batches
CREATE TABLE IF NOT EXISTS sourcing.discovery_campaigns (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,

    -- Campaign parameters
    search_queries JSONB,  -- Array of queries used
    locations JSONB,       -- Array of locations targeted
    max_profiles INTEGER,

    -- Results
    profiles_discovered INTEGER DEFAULT 0,
    profiles_new INTEGER DEFAULT 0,  -- Not duplicates
    profiles_extracted INTEGER DEFAULT 0,

    -- Cost tracking
    estimated_cost DECIMAL(10,2),
    actual_cost DECIMAL(10,2),

    -- Timestamps
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'running'  -- running, completed, failed, paused
);

-- Link discovered URLs to campaigns
ALTER TABLE sourcing.discovered_urls
    ADD COLUMN IF NOT EXISTS campaign_id INTEGER REFERENCES sourcing.discovery_campaigns(id);

-- Function to check if URL already exists (as candidate or discovered)
CREATE OR REPLACE FUNCTION sourcing.url_exists(url TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM sourcing.candidates WHERE LOWER(linkedin_url) = LOWER(url)
        UNION
        SELECT 1 FROM sourcing.discovered_urls WHERE LOWER(linkedin_url) = LOWER(url)
    );
END;
$$ LANGUAGE plpgsql;

-- Function to normalize LinkedIn URL
CREATE OR REPLACE FUNCTION sourcing.normalize_linkedin_url(url TEXT)
RETURNS TEXT AS $$
BEGIN
    -- Remove trailing slash, convert to lowercase, ensure https://www.linkedin.com format
    url := LOWER(TRIM(url));
    url := REGEXP_REPLACE(url, '/+$', '');  -- Remove trailing slashes
    url := REGEXP_REPLACE(url, '^https?://(www\.)?', 'https://www.');  -- Normalize protocol
    RETURN url;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE sourcing.discovered_urls IS 'Tracks LinkedIn URLs discovered but not yet extracted - enables cheap broad discovery';
COMMENT ON TABLE sourcing.discovery_campaigns IS 'Tracks discovery campaigns for cost control and coverage analysis';
