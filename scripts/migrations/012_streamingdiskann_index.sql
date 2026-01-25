-- Migration: 012_streamingdiskann_index.sql
-- Create StreamingDiskANN index for candidate embeddings
-- Runs alongside existing HNSW index for A/B testing

-- Create StreamingDiskANN index (if vectorscale is available)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vectorscale') THEN
    -- Drop existing diskann index if it exists (for re-runs)
    DROP INDEX IF EXISTS search.candidate_embeddings_embedding_diskann_idx;

    -- Create StreamingDiskANN index with tuned parameters
    -- num_neighbors: Graph degree (higher = better recall, more memory)
    -- search_list_size: Search depth (tunable at query time)
    -- max_alpha: Pruning aggressiveness
    -- num_bits_per_dimension: SBQ compression (2 = high quality)
    EXECUTE 'CREATE INDEX candidate_embeddings_embedding_diskann_idx
      ON search.candidate_embeddings
      USING diskann (embedding)
      WITH (
        num_neighbors = 50,
        search_list_size = 100,
        max_alpha = 1.2,
        num_bits_per_dimension = 2
      )';

    RAISE NOTICE 'StreamingDiskANN index created successfully';
  ELSE
    RAISE NOTICE 'vectorscale extension not available, skipping diskann index';
  END IF;
END $$;

-- Verify index creation
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'search'
  AND tablename = 'candidate_embeddings'
  AND indexdef LIKE '%diskann%';
