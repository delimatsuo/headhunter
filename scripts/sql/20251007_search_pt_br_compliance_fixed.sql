-- Migration: ensure candidate_profiles supports compliance fields and Portuguese FTS
-- PRD References: lines 6-15 (Portuguese FTS, compliance fields)
-- Run against Cloud SQL instance sql-hh-core (us-central1)
-- Fixed version: PostgreSQL doesn't support column references in DEFAULT expressions

BEGIN;

-- Add compliance columns
ALTER TABLE search.candidate_profiles
    ADD COLUMN IF NOT EXISTS legal_basis TEXT;

ALTER TABLE search.candidate_profiles
    ADD COLUMN IF NOT EXISTS consent_record TEXT;

ALTER TABLE search.candidate_profiles
    ADD COLUMN IF NOT EXISTS transfer_mechanism TEXT;

-- Update existing rows to use Portuguese FTS
-- (search_document column already exists from previous schema)
UPDATE search.candidate_profiles
SET search_document = to_tsvector('portuguese', COALESCE(full_name, '') || ' ' || COALESCE(headline, ''))
WHERE search_document IS NULL OR search_document = to_tsvector('english', '');

-- Create or replace the FTS index with Portuguese configuration
DROP INDEX IF EXISTS search.candidate_profiles_fts_idx;
CREATE INDEX candidate_profiles_fts_idx
    ON search.candidate_profiles USING GIN (search_document);

-- Create a trigger to maintain Portuguese FTS on updates
CREATE OR REPLACE FUNCTION search.update_candidate_search_document()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_document := to_tsvector('portuguese', COALESCE(NEW.full_name, '') || ' ' || COALESCE(NEW.headline, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS candidate_profiles_search_document_trigger ON search.candidate_profiles;
CREATE TRIGGER candidate_profiles_search_document_trigger
    BEFORE INSERT OR UPDATE OF full_name, headline
    ON search.candidate_profiles
    FOR EACH ROW
    EXECUTE FUNCTION search.update_candidate_search_document();

COMMIT;
