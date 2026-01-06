-- Migration: Add country column to candidate_profiles
-- This enables country-level filtering for search results

-- Add country column if it doesn't exist
ALTER TABLE search.candidate_profiles
ADD COLUMN IF NOT EXISTS country TEXT;

-- Create index for country filtering
CREATE INDEX IF NOT EXISTS idx_candidate_profiles_country
ON search.candidate_profiles (country)
WHERE country IS NOT NULL;

-- Update comment
COMMENT ON COLUMN search.candidate_profiles.country IS
'ISO country name (e.g., "Brazil", "United States") for filtering. Extracted from address field.';
