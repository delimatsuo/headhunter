#!/bin/bash
#
# Execute database dimension migration via Cloud Run Job
# This ensures proper authentication and permissions
#

set -e

PROJECT_ID="headhunter-ai-0088"
REGION="us-central1"
SQL_INSTANCE="sql-hh-core"
DATABASE="headhunter"
USER="embed_writer"

echo "=================================================="
echo "DATABASE DIMENSION MIGRATION"
echo "=================================================="
echo ""
echo "Project: $PROJECT_ID"
echo "Instance: $SQL_INSTANCE"
echo "Database: $DATABASE"
echo "User: $USER"
echo ""

# Get the password from Secret Manager
PASSWORD=$(gcloud secrets versions access latest --secret=db-primary-password --project="$PROJECT_ID")

# SQL migration script
SQL_SCRIPT=$(cat << 'EOF'
BEGIN;

-- Check current dimension
DO $$
DECLARE
    current_dim INTEGER;
BEGIN
    SELECT atttypmod - 4 INTO current_dim
    FROM pg_attribute
    WHERE attrelid = 'search.candidate_embeddings'::regclass
    AND attname = 'embedding';

    RAISE NOTICE 'Current embedding dimension: %', current_dim;
END $$;

-- Drop and recreate with correct dimension
ALTER TABLE search.candidate_embeddings DROP COLUMN IF EXISTS embedding CASCADE;
ALTER TABLE search.candidate_embeddings ADD COLUMN embedding vector(768) NOT NULL;

-- Recreate indexes for performance
CREATE INDEX IF NOT EXISTS idx_candidate_embeddings_hnsw
  ON search.candidate_embeddings
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_candidate_embeddings_ivfflat
  ON search.candidate_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- Verify new dimension
DO $$
DECLARE
    new_dim INTEGER;
BEGIN
    SELECT atttypmod - 4 INTO new_dim
    FROM pg_attribute
    WHERE attrelid = 'search.candidate_embeddings'::regclass
    AND attname = 'embedding';

    RAISE NOTICE 'New embedding dimension: %', new_dim;

    IF new_dim != 768 THEN
        RAISE EXCEPTION 'Migration failed: dimension is %, expected 768', new_dim;
    END IF;
END $$;

COMMIT;
EOF
)

# Save SQL to temp file
echo "$SQL_SCRIPT" > /tmp/migration.sql

echo "📝 Migration SQL prepared"
echo ""
echo "Executing migration..."
echo ""

# Execute via gcloud sql connect
PGPASSWORD="$PASSWORD" psql \
  "host=/tmp/cloudsql/${PROJECT_ID}:${REGION}:${SQL_INSTANCE} dbname=${DATABASE} user=${USER}" \
  -f /tmp/migration.sql

echo ""
echo "✅ Migration completed successfully!"
echo "✅ Embedding column now configured for 768 dimensions"
echo "✅ VertexAI text-embedding-004 compatible"
