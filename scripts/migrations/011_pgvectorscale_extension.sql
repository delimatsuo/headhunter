-- Migration: 011_pgvectorscale_extension.sql
-- Install pgvectorscale for StreamingDiskANN indices
-- Requires pgvector extension to be installed first

-- Check if pgvector is installed
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    RAISE EXCEPTION 'pgvector extension must be installed before pgvectorscale';
  END IF;
END $$;

-- Install pgvectorscale (provides StreamingDiskANN index type)
CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE;

-- Verify installation
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vectorscale') THEN
    RAISE EXCEPTION 'Failed to install vectorscale extension';
  END IF;
  RAISE NOTICE 'pgvectorscale extension installed successfully';
END $$;
