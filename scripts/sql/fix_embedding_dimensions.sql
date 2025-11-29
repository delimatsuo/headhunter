-- Fix embedding dimensions from 3072 to 768
-- This script assumes the table was created with incorrect dimensions
-- and needs to be corrected to match the VertexAI text-embedding-004 model (768 dimensions)

BEGIN;

-- Drop the existing embedding column with incorrect dimensions
ALTER TABLE search.candidate_embeddings
DROP COLUMN IF EXISTS embedding CASCADE;

-- Recreate with correct dimensions
ALTER TABLE search.candidate_embeddings
ADD COLUMN embedding vector(768) NOT NULL;

-- Recreate the HNSW index for fast similarity search
CREATE INDEX IF NOT EXISTS idx_candidate_embeddings_hnsw
  ON search.candidate_embeddings
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Recreate the IVFFlat index as backup
CREATE INDEX IF NOT EXISTS idx_candidate_embeddings_ivfflat
  ON search.candidate_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

COMMIT;

-- Verify the change
SELECT
  column_name,
  data_type,
  udt_name
FROM information_schema.columns
WHERE table_schema = 'search'
  AND table_name = 'candidate_embeddings'
  AND column_name = 'embedding';
