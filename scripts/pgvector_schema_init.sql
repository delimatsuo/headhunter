-- Non-destructive init schema generated from pgvector_schema.sql
-- Cloud SQL pgvector schema for candidate embeddings
-- PRD Reference: Lines 141, 143 - Embedding worker with pgvector and idempotent upserts

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create UUID extension for primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main embeddings table for semantic search
CREATE TABLE candidate_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id VARCHAR(255) NOT NULL,
    embedding vector(768),
    model_version VARCHAR(50) NOT NULL DEFAULT 'vertex-ai-textembedding-gecko',
    chunk_type VARCHAR(50) DEFAULT 'full_profile',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    UNIQUE(candidate_id, model_version, chunk_type)
);

-- Metadata table for tracking embedding generation
CREATE TABLE embedding_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id VARCHAR(255) NOT NULL UNIQUE,
    total_embeddings INTEGER DEFAULT 0,
    last_processed TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processing_status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    source_updated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- IVFFlat index for approximate nearest neighbor search
CREATE INDEX idx_candidate_embeddings_ivfflat 
ON candidate_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Standard B-tree indexes for filtering
CREATE INDEX idx_candidate_embeddings_candidate_id ON candidate_embeddings(candidate_id);
CREATE INDEX idx_candidate_embeddings_model_version ON candidate_embeddings(model_version);
CREATE INDEX idx_candidate_embeddings_chunk_type ON candidate_embeddings(chunk_type);
CREATE INDEX idx_candidate_embeddings_created_at ON candidate_embeddings(created_at);

CREATE INDEX idx_embedding_metadata_candidate_id ON embedding_metadata(candidate_id);
CREATE INDEX idx_embedding_metadata_status ON embedding_metadata(processing_status);
CREATE INDEX idx_embedding_metadata_last_processed ON embedding_metadata(last_processed);

-- Update trigger to automatically set updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_candidate_embeddings_updated_at 
    BEFORE UPDATE ON candidate_embeddings 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_embedding_metadata_updated_at 
    BEFORE UPDATE ON embedding_metadata 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function for similarity search with metadata filtering
CREATE OR REPLACE FUNCTION similarity_search(
    query_embedding vector(768),
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 10,
    model_filter VARCHAR(50) DEFAULT NULL,
    chunk_filter VARCHAR(50) DEFAULT 'full_profile'
) 
RETURNS TABLE(
    candidate_id VARCHAR(255),
    similarity FLOAT,
    metadata JSONB,
    model_version VARCHAR(50),
    chunk_type VARCHAR(50)
) 
LANGUAGE sql STABLE
AS $$
    SELECT 
        ce.candidate_id,
        1 - (ce.embedding <=> query_embedding) AS similarity,
        ce.metadata,
        ce.model_version,
        ce.chunk_type
    FROM candidate_embeddings ce
    WHERE 
        (model_filter IS NULL OR ce.model_version = model_filter)
        AND (chunk_filter IS NULL OR ce.chunk_type = chunk_filter)
        AND (1 - (ce.embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY ce.embedding <=> query_embedding
    LIMIT max_results;
$$;

-- Function for batch upsert (idempotent inserts as per PRD)
CREATE OR REPLACE FUNCTION upsert_candidate_embedding(
    p_candidate_id VARCHAR(255),
    p_embedding vector(768),
    p_model_version VARCHAR(50),
    p_chunk_type VARCHAR(50) DEFAULT 'full_profile',
    p_metadata JSONB DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    result_id UUID;
BEGIN
    INSERT INTO candidate_embeddings (
        candidate_id, embedding, model_version, chunk_type, metadata
    ) 
    VALUES (
        p_candidate_id, p_embedding, p_model_version, p_chunk_type, p_metadata
    )
    ON CONFLICT (candidate_id, model_version, chunk_type)
    DO UPDATE SET
        embedding = EXCLUDED.embedding,
        metadata = EXCLUDED.metadata,
        updated_at = CURRENT_TIMESTAMP
    RETURNING id INTO result_id;
    
    -- Update metadata table
    INSERT INTO embedding_metadata (candidate_id, processing_status)
    VALUES (p_candidate_id, 'completed')
    ON CONFLICT (candidate_id)
    DO UPDATE SET
        processing_status = 'completed',
        last_processed = CURRENT_TIMESTAMP,
        error_message = NULL,
        updated_at = CURRENT_TIMESTAMP;
    
    RETURN result_id;
END;
$$;

-- Views
CREATE OR REPLACE VIEW embedding_stats AS
SELECT 
    model_version,
    chunk_type,
    COUNT(*) as total_embeddings,
    AVG(COALESCE(array_length(string_to_array(embedding::text, ','), 1), 0)) as avg_dimensions,
    MIN(created_at) as first_created,
    MAX(updated_at) as last_updated
FROM candidate_embeddings
GROUP BY model_version, chunk_type;

CREATE OR REPLACE VIEW processing_stats AS
SELECT 
    processing_status,
    COUNT(*) as candidate_count,
    AVG(total_embeddings) as avg_embeddings_per_candidate,
    MIN(last_processed) as oldest_processed,
    MAX(last_processed) as latest_processed
FROM embedding_metadata
GROUP BY processing_status;

COMMENT ON TABLE candidate_embeddings IS 'Vector embeddings for candidate semantic search - PRD lines 141, 143';
COMMENT ON TABLE embedding_metadata IS 'Metadata for tracking embedding generation and processing status';
COMMENT ON FUNCTION similarity_search IS 'Semantic search function using cosine similarity';
COMMENT ON FUNCTION upsert_candidate_embedding IS 'Idempotent embedding upsert function per PRD requirements';

