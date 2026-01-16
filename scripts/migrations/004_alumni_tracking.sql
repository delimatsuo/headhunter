-- Migration: Add alumni tracking and company affiliation fields
-- Enables efficient querying of candidates by their company history
-- Created: 2026-01-14

-- Add company affiliation tracking columns to candidates table
ALTER TABLE sourcing.candidates
    ADD COLUMN IF NOT EXISTS company_affiliations JSONB,
    -- Structure: {"current": [...], "past": [...]}
    -- Each entry: {"company": "Nubank", "title": "Senior Engineer", "is_target_company": true}

    ADD COLUMN IF NOT EXISTS is_target_company_alumni BOOLEAN DEFAULT FALSE,
    -- TRUE if candidate previously worked at any target company

    ADD COLUMN IF NOT EXISTS is_target_company_current BOOLEAN DEFAULT FALSE,
    -- TRUE if candidate currently works at a target company

    ADD COLUMN IF NOT EXISTS target_companies_worked TEXT[],
    -- Array of target company names this person worked at (past + current)

    ADD COLUMN IF NOT EXISTS affiliation_updated_at TIMESTAMP;
    -- When affiliations were last computed

-- Create indexes for efficient alumni queries
CREATE INDEX IF NOT EXISTS idx_candidates_target_alumni
    ON sourcing.candidates(is_target_company_alumni)
    WHERE is_target_company_alumni = TRUE;

CREATE INDEX IF NOT EXISTS idx_candidates_target_current
    ON sourcing.candidates(is_target_company_current)
    WHERE is_target_company_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_candidates_target_companies
    ON sourcing.candidates USING GIN(target_companies_worked);

CREATE INDEX IF NOT EXISTS idx_candidates_affiliations
    ON sourcing.candidates USING GIN(company_affiliations);

-- Add index on experience table for company name searches
CREATE INDEX IF NOT EXISTS idx_experience_company_lower
    ON sourcing.experience(LOWER(company_name));

CREATE INDEX IF NOT EXISTS idx_experience_company_current
    ON sourcing.experience(company_name, is_current);

-- Function to check if a company name matches any target company
-- Uses fuzzy matching with common variations
CREATE OR REPLACE FUNCTION sourcing.is_target_company(company_name TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    target_patterns TEXT[] := ARRAY[
        -- Unicorns
        'nubank', 'quintoandar', 'c6 bank', 'c6bank', 'ifood', 'creditas',
        'loft', 'cloudwalk', 'ebanx', 'nuvemshop', 'loggi', 'madeiramadeira',
        'dock', 'unico', 'olist', 'qi tech', 'qitech',

        -- Big Tech Brazil
        'google', 'meta', 'facebook', 'microsoft', 'amazon', 'mercado libre',
        'mercadolibre', 'salesforce', 'sap', 'oracle', 'ibm', 'spotify',

        -- Funded Scaleups
        'picpay', 'stone', 'pagseguro', 'celcoin', 'omie', 'rd station',
        'vtex', 'gympass', 'wellhub', 'hotmart', 'totvs', 'contabilizei',
        'clara', 'hash', 'caju', 'gupy', 'warren', 'kovi', 'buser', 'meliuz',

        -- Series A/B
        'pipefy', 'involves', 'runrun', 'pipo', 'memed', 'freto', 'logcomex',
        'solides', 'feedz', 'neoway', 'bigdatacorp', 'cortex', 'parfin',
        'aarin', 'z1', 'cora', 'blu', 'qulture', 'neon', 'inter', 'banco inter',
        'original', 'recargapay', 'asaas', 'transfeera', 'magalu', 'magazine luiza',
        'americanas', 'via', 'casas bahia', 'zenklub', 'psicologia viva', 'dr consulta',

        -- Emerging
        'vaas', 'capim', 'canopy', 'agrolend', 'trace finance', 'dotz', 'nomad',
        'frete.com', 'tembici', 'alice', 'facily', 'ze delivery', 'daki', 'shopper', 'liv up'
    ];
    pattern TEXT;
    company_lower TEXT;
BEGIN
    IF company_name IS NULL THEN
        RETURN FALSE;
    END IF;

    company_lower := LOWER(company_name);

    FOREACH pattern IN ARRAY target_patterns LOOP
        IF company_lower LIKE '%' || pattern || '%' THEN
            RETURN TRUE;
        END IF;
    END LOOP;

    RETURN FALSE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to compute and update candidate affiliations
CREATE OR REPLACE FUNCTION sourcing.update_candidate_affiliations(p_candidate_id INTEGER)
RETURNS VOID AS $$
DECLARE
    v_affiliations JSONB;
    v_current_entries JSONB := '[]'::JSONB;
    v_past_entries JSONB := '[]'::JSONB;
    v_is_target_alumni BOOLEAN := FALSE;
    v_is_target_current BOOLEAN := FALSE;
    v_target_companies TEXT[] := ARRAY[]::TEXT[];
    v_exp RECORD;
BEGIN
    -- Build affiliations from experience records
    FOR v_exp IN
        SELECT company_name, title, is_current, start_date, end_date
        FROM sourcing.experience
        WHERE candidate_id = p_candidate_id
        ORDER BY is_current DESC, end_date DESC NULLS FIRST
    LOOP
        DECLARE
            v_entry JSONB;
            v_is_target BOOLEAN;
        BEGIN
            v_is_target := sourcing.is_target_company(v_exp.company_name);

            v_entry := jsonb_build_object(
                'company', v_exp.company_name,
                'title', v_exp.title,
                'start_date', v_exp.start_date,
                'end_date', v_exp.end_date,
                'is_target_company', v_is_target
            );

            IF v_exp.is_current THEN
                v_current_entries := v_current_entries || v_entry;
                IF v_is_target THEN
                    v_is_target_current := TRUE;
                    IF NOT v_exp.company_name = ANY(v_target_companies) THEN
                        v_target_companies := array_append(v_target_companies, v_exp.company_name);
                    END IF;
                END IF;
            ELSE
                v_past_entries := v_past_entries || v_entry;
                IF v_is_target THEN
                    v_is_target_alumni := TRUE;
                    IF NOT v_exp.company_name = ANY(v_target_companies) THEN
                        v_target_companies := array_append(v_target_companies, v_exp.company_name);
                    END IF;
                END IF;
            END IF;
        END;
    END LOOP;

    v_affiliations := jsonb_build_object(
        'current', v_current_entries,
        'past', v_past_entries
    );

    -- Update candidate record
    UPDATE sourcing.candidates
    SET
        company_affiliations = v_affiliations,
        is_target_company_alumni = v_is_target_alumni,
        is_target_company_current = v_is_target_current,
        target_companies_worked = v_target_companies,
        affiliation_updated_at = NOW()
    WHERE id = p_candidate_id;
END;
$$ LANGUAGE plpgsql;

-- Function to update all candidate affiliations (batch)
CREATE OR REPLACE FUNCTION sourcing.update_all_affiliations()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER := 0;
    v_candidate_id INTEGER;
BEGIN
    FOR v_candidate_id IN
        SELECT DISTINCT c.id
        FROM sourcing.candidates c
        JOIN sourcing.experience e ON c.id = e.candidate_id
    LOOP
        PERFORM sourcing.update_candidate_affiliations(v_candidate_id);
        v_count := v_count + 1;

        -- Log progress every 500 candidates
        IF v_count % 500 = 0 THEN
            RAISE NOTICE 'Processed % candidates', v_count;
        END IF;
    END LOOP;

    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update affiliations when experience is modified
CREATE OR REPLACE FUNCTION sourcing.trigger_update_affiliations()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM sourcing.update_candidate_affiliations(OLD.candidate_id);
        RETURN OLD;
    ELSE
        PERFORM sourcing.update_candidate_affiliations(NEW.candidate_id);
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS experience_affiliation_trigger ON sourcing.experience;
CREATE TRIGGER experience_affiliation_trigger
    AFTER INSERT OR UPDATE OR DELETE ON sourcing.experience
    FOR EACH ROW
    EXECUTE FUNCTION sourcing.trigger_update_affiliations();

-- Add comments
COMMENT ON COLUMN sourcing.candidates.company_affiliations IS 'JSON object with current and past company affiliations';
COMMENT ON COLUMN sourcing.candidates.is_target_company_alumni IS 'TRUE if previously worked at a target company';
COMMENT ON COLUMN sourcing.candidates.is_target_company_current IS 'TRUE if currently works at a target company';
COMMENT ON COLUMN sourcing.candidates.target_companies_worked IS 'Array of target company names this person worked at';
COMMENT ON FUNCTION sourcing.is_target_company(TEXT) IS 'Check if company name matches any target company (fuzzy)';
COMMENT ON FUNCTION sourcing.update_candidate_affiliations(INTEGER) IS 'Recompute affiliations for a single candidate';
COMMENT ON FUNCTION sourcing.update_all_affiliations() IS 'Batch update all candidate affiliations';
