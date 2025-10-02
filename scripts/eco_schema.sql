-- ECO (Ella Canonical Occupations) Schema
-- PRD: ECO Foundation Phase - Canonical occupation taxonomy for BR/pt-BR
-- This schema co-exists with existing pgvector tables in the same database.
-- References: scripts/pgvector_schema_init.sql
--
-- Transaction management note:
--   We intentionally DO NOT include BEGIN/COMMIT here. The deployment script
--   `scripts/validate_and_deploy_eco_schema.py` manages the transaction to
--   avoid nested transactions between SQL and driver-level controls.


-- Canonical occupations
CREATE TABLE IF NOT EXISTS eco_occupation (
  id SERIAL PRIMARY KEY,
  eco_id TEXT NOT NULL UNIQUE,                         -- e.g., 'ECO.BR.SE.FRONTEND'
  locale TEXT NOT NULL DEFAULT 'pt-BR',               -- BCP-47 locale
  country TEXT NOT NULL DEFAULT 'BR',                 -- ISO-3166 alpha-2
  display_name TEXT NOT NULL,                         -- e.g., 'Desenvolvedor(a) Front-end'
  normalized_title TEXT NOT NULL,                     -- lowercased, diacritics removed
  description TEXT,
  evidence_count INTEGER NOT NULL DEFAULT 0,          -- #postings supporting this occupation
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE eco_occupation IS 'PRD ECO §2.1 Canonical occupations for Brazil (pt-BR).';
CREATE INDEX IF NOT EXISTS idx_eco_occupation_locale ON eco_occupation(locale, country);
CREATE INDEX IF NOT EXISTS idx_eco_occupation_norm ON eco_occupation(normalized_title);
-- Trigram index optional: only create if extension exists
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
    CREATE INDEX IF NOT EXISTS idx_eco_occupation_norm_trgm ON eco_occupation USING GIN (normalized_title gin_trgm_ops);
  END IF;
END $$;

-- Aliases and synonyms for occupations
CREATE TABLE IF NOT EXISTS eco_alias (
  id SERIAL PRIMARY KEY,
  eco_id TEXT NOT NULL REFERENCES eco_occupation(eco_id) ON DELETE CASCADE,
  alias TEXT NOT NULL,                                 -- original alias from source
  normalized_alias TEXT NOT NULL,                      -- normalized form
  confidence NUMERIC(5,4) NOT NULL DEFAULT 0.7500,     -- 0..1 confidence
  source TEXT,                                         -- e.g., 'VAGAS', 'INFOJOBS', 'MANUAL'
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (eco_id, normalized_alias)
);

COMMENT ON TABLE eco_alias IS 'PRD ECO §2.2 Aliases/synonyms mapped to canonical occupations.';
CREATE INDEX IF NOT EXISTS idx_eco_alias_norm ON eco_alias(normalized_alias);
CREATE INDEX IF NOT EXISTS idx_eco_alias_eco_id ON eco_alias(eco_id);
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
    CREATE INDEX IF NOT EXISTS idx_eco_alias_norm_trgm ON eco_alias USING GIN (normalized_alias gin_trgm_ops);
  END IF;
END $$;

-- Optional crosswalks to public taxonomies (CBO, ESCO, O*NET)
CREATE TABLE IF NOT EXISTS occupation_crosswalk (
  id SERIAL PRIMARY KEY,
  eco_id TEXT NOT NULL REFERENCES eco_occupation(eco_id) ON DELETE CASCADE,
  system TEXT NOT NULL,                                -- 'CBO' | 'ESCO' | 'ONET'
  code TEXT NOT NULL,
  label TEXT,
  UNIQUE (eco_id, system, code)
);

COMMENT ON TABLE occupation_crosswalk IS 'PRD ECO §3 Crosswalks to CBO/ESCO/O*NET.';
CREATE INDEX IF NOT EXISTS idx_crosswalk_eco_id ON occupation_crosswalk(eco_id);

-- Skill templates extracted from postings (Phase 1 store, Phase 2 infer)
CREATE TABLE IF NOT EXISTS eco_template (
  id SERIAL PRIMARY KEY,
  eco_id TEXT NOT NULL REFERENCES eco_occupation(eco_id) ON DELETE CASCADE,
  required_skills JSONB DEFAULT '[]'::jsonb,           -- ["React", "TypeScript", ...]
  preferred_skills JSONB DEFAULT '[]'::jsonb,
  min_years_experience INTEGER,
  max_years_experience INTEGER,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE eco_template IS 'PRD ECO §4 Occupation templates (skills, YoE).';
CREATE INDEX IF NOT EXISTS idx_template_eco_id ON eco_template(eco_id);

-- Timestamp trigger to keep updated_at fresh
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'tr_eco_occupation_updated_at'
  ) THEN
    CREATE TRIGGER tr_eco_occupation_updated_at
    BEFORE UPDATE ON eco_occupation
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'tr_eco_alias_updated_at'
  ) THEN
    CREATE TRIGGER tr_eco_alias_updated_at
    BEFORE UPDATE ON eco_alias
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'tr_eco_template_updated_at'
  ) THEN
    CREATE TRIGGER tr_eco_template_updated_at
    BEFORE UPDATE ON eco_template
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
END $$;

-- Seed examples (Brazilian tech roles)
INSERT INTO eco_occupation (eco_id, locale, country, display_name, normalized_title, description, evidence_count)
VALUES
  ('ECO.BR.SE.FRONTEND', 'pt-BR', 'BR', 'Desenvolvedor(a) Front-end', 'desenvolvedor frontend', 'Desenvolvimento de interfaces web com foco em frontend (React, Vue, etc.)', 0),
  ('ECO.BR.SE.DATAENG', 'pt-BR', 'BR', 'Engenheiro(a) de Dados', 'engenheiro de dados', 'Pipelines de dados, ETL, orquestração e plataformas de dados', 0)
ON CONFLICT (eco_id) DO NOTHING;
