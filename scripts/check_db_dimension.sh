#!/bin/bash

# Check actual database dimension
gcloud sql connect sql-hh-core \
  --user=postgres \
  --database=headhunter \
  --project=headhunter-ai-0088 \
  --quiet << 'EOF'
SELECT
    attname as column_name,
    atttypmod,
    atttypmod - 4 as dimension,
    format_type(atttypid, atttypmod) as full_type
FROM pg_attribute
WHERE attrelid = 'search.candidate_embeddings'::regclass
  AND attname = 'embedding';

SELECT COUNT(*) as total_embeddings
FROM search.candidate_embeddings;
EOF
