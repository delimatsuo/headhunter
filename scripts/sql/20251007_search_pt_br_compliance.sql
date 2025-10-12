-- Migration: ensure candidate_profiles supports compliance fields and Portuguese FTS
-- PRD References: lines 6-15 (Portuguese FTS, compliance fields)
-- Run against Cloud SQL instance sql-hh-core (us-central1)

BEGIN;

ALTER TABLE search.candidate_profiles
    ADD COLUMN IF NOT EXISTS legal_basis TEXT;

ALTER TABLE search.candidate_profiles
    ADD COLUMN IF NOT EXISTS consent_record TEXT;

ALTER TABLE search.candidate_profiles
    ADD COLUMN IF NOT EXISTS transfer_mechanism TEXT;

ALTER TABLE search.candidate_profiles
    ADD COLUMN IF NOT EXISTS search_document TSVECTOR;

ALTER TABLE search.candidate_profiles
    ALTER COLUMN search_document
    SET DEFAULT to_tsvector('portuguese', COALESCE(full_name, '') || ' ' || COALESCE(headline, ''));

UPDATE search.candidate_profiles
SET search_document = to_tsvector('portuguese', COALESCE(full_name, '') || ' ' || COALESCE(headline, ''))
WHERE search_document IS NULL;

CREATE INDEX IF NOT EXISTS candidate_profiles_fts_idx
    ON search.candidate_profiles USING GIN (search_document);

COMMIT;
