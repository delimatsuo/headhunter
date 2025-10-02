-- Clustering schema extension for Brazilian job title analysis.

BEGIN;

CREATE TABLE IF NOT EXISTS clustering.title_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_title TEXT NOT NULL,
    canonical_title TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL,
    chunk_type TEXT NOT NULL DEFAULT 'job_title',
    source TEXT,
    frequency INTEGER NOT NULL DEFAULT 1,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_title_embeddings_unique
    ON clustering.title_embeddings (normalized_title, chunk_type);

CREATE INDEX IF NOT EXISTS idx_title_embeddings_frequency
    ON clustering.title_embeddings (frequency DESC);


CREATE TABLE IF NOT EXISTS clustering.title_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_title TEXT NOT NULL,
    cluster_id INTEGER NOT NULL,
    cluster_method TEXT NOT NULL,
    quality_score NUMERIC,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_title_clusters_title
        FOREIGN KEY (normalized_title)
        REFERENCES clustering.title_embeddings (normalized_title)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_title_clusters_cluster
    ON clustering.title_clusters (cluster_id, cluster_method);


CREATE TABLE IF NOT EXISTS clustering.career_progressions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_level TEXT NOT NULL,
    to_level TEXT NOT NULL,
    confidence NUMERIC NOT NULL,
    evidence_count INTEGER NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_career_progressions_levels
    ON clustering.career_progressions (from_level, to_level);


CREATE TABLE IF NOT EXISTS clustering.clustering_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_method TEXT NOT NULL,
    parameters JSONB NOT NULL,
    silhouette_score NUMERIC,
    davies_bouldin_index NUMERIC,
    calinski_harabasz_index NUMERIC,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE OR REPLACE FUNCTION clustering.touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_title_embeddings_updated
    BEFORE UPDATE ON clustering.title_embeddings
    FOR EACH ROW EXECUTE FUNCTION clustering.touch_updated_at();

CREATE TRIGGER trg_title_clusters_updated
    BEFORE UPDATE ON clustering.title_clusters
    FOR EACH ROW EXECUTE FUNCTION clustering.touch_updated_at();


CREATE OR REPLACE VIEW clustering.vw_cluster_summary AS
SELECT
    tc.cluster_id,
    tc.cluster_method,
    COUNT(*) AS title_count,
    SUM(te.frequency) AS total_frequency,
    AVG(tc.quality_score) AS avg_quality_score
FROM clustering.title_clusters tc
JOIN clustering.title_embeddings te ON te.normalized_title = tc.normalized_title
GROUP BY tc.cluster_id, tc.cluster_method;


CREATE OR REPLACE VIEW clustering.vw_progression_summary AS
SELECT
    from_level,
    to_level,
    confidence,
    evidence_count,
    metadata
FROM clustering.career_progressions;


CREATE OR REPLACE FUNCTION clustering.cluster_quality_flag(threshold NUMERIC)
RETURNS TABLE(cluster_id INTEGER, cluster_method TEXT, quality_score NUMERIC) AS $$
BEGIN
    RETURN QUERY
    SELECT cluster_id, cluster_method, quality_score
    FROM clustering.title_clusters
    WHERE quality_score IS NOT NULL AND quality_score < threshold;
END;
$$ LANGUAGE plpgsql;

COMMIT;
