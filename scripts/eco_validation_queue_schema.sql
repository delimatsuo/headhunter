-- ECO Quality Assurance Validation Queue Schema
-- Extends the ECO data model with structures to support manual validation flows,
-- reviewer assignments, and queue performance monitoring.
-- References: scripts/eco_schema.sql

-- Enumerations for validation queue
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'eco_validation_item_type') THEN
    CREATE TYPE eco_validation_item_type AS ENUM ('occupation', 'alias', 'template');
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'eco_validation_status') THEN
    CREATE TYPE eco_validation_status AS ENUM ('pending', 'in_review', 'resolved', 'rejected');
  END IF;
END $$;

-- Ensure updated_at trigger function exists
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

-- Main validation queue table
CREATE TABLE IF NOT EXISTS eco_validation_queue (
  id SERIAL PRIMARY KEY,
  item_type eco_validation_item_type NOT NULL,
  item_id TEXT NOT NULL,
  eco_id TEXT REFERENCES eco_occupation(eco_id) ON DELETE SET NULL,
  reason TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
  status eco_validation_status NOT NULL DEFAULT 'pending',
  assigned_reviewer TEXT,
  review_notes TEXT,
  resolution_details JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ,
  UNIQUE (item_type, item_id)
);

COMMENT ON TABLE eco_validation_queue IS 'Queue of ECO items pending manual validation or quality assurance review.';
COMMENT ON COLUMN eco_validation_queue.item_type IS 'Type of ECO entity requiring validation (occupation, alias, template).';
COMMENT ON COLUMN eco_validation_queue.reason IS 'Why the item was queued for validation (confidence threshold, conflict, etc.).';
COMMENT ON COLUMN eco_validation_queue.priority IS 'Reviewer priority from 1 (lowest) to 5 (highest).';

CREATE INDEX IF NOT EXISTS idx_eco_validation_queue_status_priority
  ON eco_validation_queue(status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_eco_validation_queue_reviewer
  ON eco_validation_queue(assigned_reviewer)
  WHERE assigned_reviewer IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_eco_validation_queue_created_at
  ON eco_validation_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_eco_validation_queue_eco_id
  ON eco_validation_queue(eco_id)
  WHERE eco_id IS NOT NULL;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'tr_eco_validation_queue_updated_at'
  ) THEN
    CREATE TRIGGER tr_eco_validation_queue_updated_at
    BEFORE UPDATE ON eco_validation_queue
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
END $$;

-- Metrics table to track validation throughput and quality
CREATE TABLE IF NOT EXISTS eco_validation_metrics (
  id SERIAL PRIMARY KEY,
  metric_date DATE NOT NULL,
  pending_count INTEGER NOT NULL DEFAULT 0,
  in_review_count INTEGER NOT NULL DEFAULT 0,
  resolved_count INTEGER NOT NULL DEFAULT 0,
  rejected_count INTEGER NOT NULL DEFAULT 0,
  avg_resolution_time INTERVAL,
  median_resolution_time INTERVAL,
  sla_breaches INTEGER NOT NULL DEFAULT 0,
  quality_score NUMERIC(5,4),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (metric_date)
);

COMMENT ON TABLE eco_validation_metrics IS 'Aggregated performance metrics for ECO validation queues.';

CREATE INDEX IF NOT EXISTS idx_eco_validation_metrics_date
  ON eco_validation_metrics(metric_date DESC);

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'tr_eco_validation_metrics_updated_at'
  ) THEN
    CREATE TRIGGER tr_eco_validation_metrics_updated_at
    BEFORE UPDATE ON eco_validation_metrics
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
END $$;
