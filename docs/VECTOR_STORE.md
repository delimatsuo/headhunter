# Vector Store Design (Cloud SQL + pgvector)

## Why pgvector

- 29k candidates fit comfortably; low-latency ANN search with IVFFLAT/HNSW
- Simple per-candidate updates (resume changes) with transactional writes
- Cost-effective and predictable vs heavy managed vector services

## Schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE candidate_vectors (
  candidate_id TEXT PRIMARY KEY,
  embedding VECTOR(768) NOT NULL,
  metadata JSONB,
  updated_at TIMESTAMP DEFAULT NOW()
);

-- ANN index (tune lists based on dataset)
CREATE INDEX candidate_vectors_embedding_idx
ON candidate_vectors USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

Metadata should include fast filter fields for pre-filtering before ANN, e.g.:
- years_experience, current_level, company_tier, overall_score, primary_skills

## Query Example

```sql
-- :q is a 768-dim normalized vector (cosine)
SELECT candidate_id,
       1 - (embedding <=> :q) AS score,
       metadata
FROM candidate_vectors
WHERE (metadata->>'current_level') IS NOT NULL  -- example filter
ORDER BY embedding <-> :q
LIMIT 50;
```

## Write Path

1. Enhanced profile arrives in Firestore
2. Embedding is generated (Vertex or other provider)
3. Upsert into `candidate_vectors` with the new vector + metadata

```sql
INSERT INTO candidate_vectors (candidate_id, embedding, metadata, updated_at)
VALUES (:id, :vec, :meta, NOW())
ON CONFLICT (candidate_id) DO UPDATE
  SET embedding = EXCLUDED.embedding,
      metadata  = EXCLUDED.metadata,
      updated_at = NOW();
```

## Operational Notes

- Keep vectors normalized for cosine similarity
- Batch writes for throughput; use connection pooling for Cloud Run/Functions
- Periodically `VACUUM (ANALYZE)` and reindex with tuned `lists`
- Consider HNSW index for even lower latency if available in your version

