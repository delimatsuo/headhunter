-- Complete Database Fix for Embedding Service
-- Fixes dimension mismatch, index naming, and schema issues
--
-- This SQL should be run as postgres superuser
-- Target: headhunter database on sql-hh-core instance

BEGIN;

-- 1. Fix tenants table schema
ALTER TABLE search.tenants ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE search.tenants ALTER COLUMN name DROP NOT NULL;
ALTER TABLE search.tenants ALTER COLUMN name SET DEFAULT 'Unknown';

-- 2. Drop and recreate embedding column with correct dimensions
ALTER TABLE search.candidate_embeddings DROP COLUMN IF EXISTS embedding CASCADE;
ALTER TABLE search.candidate_embeddings ADD COLUMN embedding vector(768);

-- 3. Recreate unique constraint (was dropped by CASCADE)
ALTER TABLE search.candidate_embeddings
  ADD CONSTRAINT candidate_embeddings_tenant_entity_chunk_unique
  UNIQUE (tenant_id, entity_id, chunk_type);

-- 4. Recreate indexes with correct names that the service expects
CREATE INDEX IF NOT EXISTS candidate_embeddings_embedding_hnsw_idx
  ON search.candidate_embeddings
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS candidate_embeddings_embedding_ivfflat_idx
  ON search.candidate_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- 5. Verify the fix
DO $$
DECLARE
    dim_check INTEGER;
    index_count INTEGER;
BEGIN
    -- Check dimension
    SELECT atttypmod - 4 INTO dim_check
    FROM pg_attribute
    WHERE attrelid = 'search.candidate_embeddings'::regclass
    AND attname = 'embedding';

    IF dim_check != 768 THEN
        RAISE EXCEPTION 'Dimension verification failed: got %, expected 768', dim_check;
    END IF;

    -- Check indexes exist
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE schemaname = 'search'
    AND tablename = 'candidate_embeddings'
    AND indexname IN ('candidate_embeddings_embedding_hnsw_idx', 'candidate_embeddings_embedding_ivfflat_idx');

    IF index_count != 2 THEN
        RAISE EXCEPTION 'Index verification failed: found % indexes, expected 2', index_count;
    END IF;

    RAISE NOTICE '✅ All verifications passed';
    RAISE NOTICE '  - Embedding dimension: 768';
    RAISE NOTICE '  - HNSW index: exists';
    RAISE NOTICE '  - IVFFlat index: exists';
    RAISE NOTICE '  - Unique constraint: exists';
END $$;

COMMIT;
