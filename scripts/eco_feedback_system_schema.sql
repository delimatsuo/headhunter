-- ECO Feedback Loop Schema
-- Supports recruiter feedback capture, review workflows, and impact analysis for ECO data quality.
-- References: scripts/eco_schema.sql

-- Enumerations for feedback classification and lifecycle
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'eco_feedback_type') THEN
    CREATE TYPE eco_feedback_type AS ENUM ('alias_correction', 'occupation_mapping', 'skill_template', 'search_result');
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'eco_feedback_status') THEN
    CREATE TYPE eco_feedback_status AS ENUM ('pending', 'reviewed', 'applied', 'rejected');
  END IF;
END $$;

-- Ensure updated_at trigger function exists for standalone deployments
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_proc
    WHERE proname = 'set_updated_at'
  ) THEN
    CREATE OR REPLACE FUNCTION set_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
      NEW.updated_at = NOW();
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
  END IF;
END $$;

-- Primary feedback table collected from recruiters and reviewers
CREATE TABLE IF NOT EXISTS eco_feedback (
  id SERIAL PRIMARY KEY,
  feedback_type eco_feedback_type NOT NULL,
  original_value TEXT NOT NULL,
  corrected_value TEXT,
  eco_id TEXT REFERENCES eco_occupation(eco_id) ON DELETE SET NULL,
  recruiter_id TEXT NOT NULL,
  confidence_rating INTEGER CHECK (confidence_rating BETWEEN 1 AND 5),
  feedback_notes TEXT,
  context_data JSONB,
  status eco_feedback_status NOT NULL DEFAULT 'pending',
  reviewed_by TEXT,
  applied_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE eco_feedback IS 'Feedback submissions from recruiters to improve ECO alias, occupation, and template accuracy.';
COMMENT ON COLUMN eco_feedback.context_data IS 'Structured metadata such as search queries, candidate profiles, or posting references.';

CREATE INDEX IF NOT EXISTS idx_eco_feedback_type_status
  ON eco_feedback(feedback_type, status);
CREATE INDEX IF NOT EXISTS idx_eco_feedback_recruiter
  ON eco_feedback(recruiter_id);
CREATE INDEX IF NOT EXISTS idx_eco_feedback_eco_id
  ON eco_feedback(eco_id)
  WHERE eco_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_eco_feedback_status
  ON eco_feedback(status);

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'tr_eco_feedback_updated_at'
  ) THEN
    CREATE TRIGGER tr_eco_feedback_updated_at
    BEFORE UPDATE ON eco_feedback
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
END $$;

-- Impact tracking for applied feedback changes
CREATE TABLE IF NOT EXISTS eco_feedback_impact (
  id SERIAL PRIMARY KEY,
  feedback_id INTEGER NOT NULL REFERENCES eco_feedback(id) ON DELETE CASCADE,
  metric_name TEXT NOT NULL,
  metric_before NUMERIC,
  metric_after NUMERIC,
  impact_score NUMERIC(6,3),
  evaluation_window DATERANGE,
  impact_notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE eco_feedback_impact IS 'Tracks quantitative impact of applied feedback on ECO system performance metrics.';

CREATE INDEX IF NOT EXISTS idx_eco_feedback_impact_metric
  ON eco_feedback_impact(metric_name);
CREATE INDEX IF NOT EXISTS idx_eco_feedback_impact_feedback
  ON eco_feedback_impact(feedback_id);

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'tr_eco_feedback_impact_updated_at'
  ) THEN
    CREATE TRIGGER tr_eco_feedback_impact_updated_at
    BEFORE UPDATE ON eco_feedback_impact
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
END $$;
