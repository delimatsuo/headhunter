\echo 'Configuring pgvector schemas and extensions'
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS search;
CREATE SCHEMA IF NOT EXISTS taxonomy;
CREATE SCHEMA IF NOT EXISTS msgs;
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS search.tenants (
    tenant_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS search.candidate_profiles (
    tenant_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    full_name TEXT,
    current_title TEXT,
    headline TEXT,
    location TEXT,
    country TEXT,
    industries TEXT[] DEFAULT ARRAY[]::TEXT[],
    skills TEXT[] DEFAULT ARRAY[]::TEXT[],
    years_experience NUMERIC(4,1),
    analysis_confidence NUMERIC(3,2) DEFAULT 0,
    profile JSONB DEFAULT '{}'::JSONB,
    search_document TSVECTOR,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    PRIMARY KEY (tenant_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS search.candidate_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL,
    embedding_text TEXT,
    metadata JSONB DEFAULT '{}'::JSONB,
    model_version TEXT NOT NULL,
    chunk_type TEXT NOT NULL DEFAULT 'profile',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (tenant_id, entity_id, chunk_type)
);

CREATE TABLE IF NOT EXISTS search.job_descriptions (
    tenant_id TEXT NOT NULL,
    jd_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(768),
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    PRIMARY KEY (tenant_id, jd_id)
);

CREATE INDEX IF NOT EXISTS candidate_profiles_tenant_updated_idx
    ON search.candidate_profiles (tenant_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS candidate_embeddings_tenant_idx
    ON search.candidate_embeddings (tenant_id, entity_id);

CREATE INDEX IF NOT EXISTS job_descriptions_tenant_idx
    ON search.job_descriptions (tenant_id, updated_at DESC);

DROP INDEX IF EXISTS search.candidate_embeddings_embedding_hnsw_idx;
CREATE INDEX IF NOT EXISTS candidate_embeddings_embedding_hnsw_idx
    ON search.candidate_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS taxonomy.eco_occupations (
    occupation_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    title_normalized TEXT NOT NULL,
    locale TEXT NOT NULL DEFAULT 'pt-BR',
    family TEXT,
    group_code TEXT,
    attributes JSONB DEFAULT '{}'::JSONB
);

CREATE TABLE IF NOT EXISTS msgs.outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    routing_key TEXT NOT NULL,
    payload JSONB NOT NULL,
    published BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    published_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ops.job_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    finished_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::JSONB
);

\echo 'Generating realistic seed data'
INSERT INTO search.tenants (tenant_id, name)
VALUES
    ('tenant-alpha', 'Alpha Search Partners'),
    ('tenant-beta', 'Beta Talent Group'),
    ('tenant-gamma', 'Gamma Staffing Co.'),
    ('tenant-delta', 'Delta Recruiters')
ON CONFLICT (tenant_id) DO UPDATE SET name = EXCLUDED.name;

WITH sample_titles AS (
    SELECT * FROM (VALUES
        ('Software Engineer', 'Engenheira de Software'),
        ('Data Scientist', 'Cientista de Dados'),
        ('Product Manager', 'Gerente de Produto'),
        ('DevOps Engineer', 'Engenheiro(a) DevOps'),
        ('UX Designer', 'Designer UX'),
        ('Sales Manager', 'Gerente de Vendas')
    ) AS t(en_title, pt_title)
),
ranked AS (
    SELECT gs AS idx,
           'tenant-' || choose_tenant AS tenant_id,
           'cand-' || gs AS candidate_id,
           initcap(fake.first_name || ' ' || fake.last_name) AS full_name,
           st.en_title AS title_en,
           st.pt_title AS title_pt,
           fake.city || ', ' || fake.country AS location,
           ARRAY['cloud', 'python', 'leadership', 'sql', 'coaching'][1:3] AS skills,
           ARRAY['technology', 'consulting', 'finance'][1:2] AS industries,
           round(1 + random() * 15, 1) AS years_experience,
           round(0.55 + random() * 0.35, 2) AS confidence,
           jsonb_build_object(
               'headline', st.en_title || ' com foco em ' || fake.specialty,
               'languages', ARRAY['pt-BR', 'en-US'],
               'summary', fake.summary
           ) AS profile
    FROM generate_series(1, 60) AS gs
    CROSS JOIN LATERAL (
        SELECT ARRAY['alpha','beta','gamma','delta'][((gs - 1) % 4) + 1] AS choose_tenant
    ) AS tenant_picker
    CROSS JOIN LATERAL (
        SELECT *
        FROM sample_titles
        ORDER BY random()
        LIMIT 1
    ) AS st
    CROSS JOIN LATERAL (
        SELECT
            initcap(md5(gs::text || 'fn')::text) AS first_name,
            initcap(md5((gs + 100)::text || 'ln')::text) AS last_name,
            initcap(md5((gs + 200)::text || 'city')::text) AS city,
            'BR' AS country,
            initcap(md5((gs + 500)::text || 'focus')::text) AS specialty,
            'Profissional com experiência comprovada em projetos de alta escala.' AS summary
    ) AS fake
)
INSERT INTO search.candidate_profiles (
    tenant_id,
    candidate_id,
    full_name,
    current_title,
    headline,
    location,
    industries,
    skills,
    years_experience,
    analysis_confidence,
    profile,
    search_document
)
SELECT
    tenant_id,
    candidate_id,
    full_name,
    title_en,
    profile->>'headline',
    location,
    industries,
    ARRAY['python', 'sql', 'cloud', 'leadership'][1:3],
    years_experience,
    confidence,
    profile,
    to_tsvector('simple', coalesce(full_name, '') || ' ' || coalesce(title_en, '') || ' ' || coalesce(location, ''))
FROM ranked
ON CONFLICT (tenant_id, candidate_id) DO UPDATE
SET full_name = EXCLUDED.full_name,
    current_title = EXCLUDED.current_title,
    headline = EXCLUDED.headline,
    location = EXCLUDED.location,
    industries = EXCLUDED.industries,
    skills = EXCLUDED.skills,
    years_experience = EXCLUDED.years_experience,
    analysis_confidence = EXCLUDED.analysis_confidence,
    profile = EXCLUDED.profile,
    search_document = EXCLUDED.search_document,
    updated_at = timezone('utc', now());

WITH vector_data AS (
    SELECT
        tenant_id,
        candidate_id,
        (SELECT array_agg(random() * 2 - 1)
         FROM generate_series(1, 768))::vector AS embedding,
        profile,
        current_timestamp AS ts
    FROM search.candidate_profiles
)
INSERT INTO search.candidate_embeddings (
    tenant_id,
    entity_id,
    embedding,
    embedding_text,
    metadata,
    model_version,
    chunk_type,
    created_at,
    updated_at
)
SELECT
    tenant_id,
    candidate_id,
    embedding,
    profile->>'summary',
    jsonb_build_object('source', 'seed', 'locale', 'pt-BR'),
    'mock-embeddings-v1',
    'profile',
    ts,
    ts
FROM vector_data
ON CONFLICT (tenant_id, entity_id, chunk_type) DO UPDATE
SET embedding = EXCLUDED.embedding,
    embedding_text = EXCLUDED.embedding_text,
    metadata = EXCLUDED.metadata,
    model_version = EXCLUDED.model_version,
    updated_at = EXCLUDED.updated_at;

WITH job_data AS (
    SELECT
        tenant_id,
        'jd-' || lpad(row_number() OVER (PARTITION BY tenant_id ORDER BY candidate_id)::text, 3, '0') AS jd_id,
        concat('Vaga ', row_number() OVER (PARTITION BY tenant_id ORDER BY candidate_id)) AS title,
        concat('Procuramos profissional com experiencia em ', profile->>'headline', ' na regiao de ', location, '.') AS content,
        jsonb_build_object('created_by', 'seed', 'source_candidate', candidate_id) AS metadata
    FROM search.candidate_profiles
    LIMIT 40
)
INSERT INTO search.job_descriptions (tenant_id, jd_id, title, content, metadata)
SELECT tenant_id, jd_id, title, content, metadata
FROM job_data
ON CONFLICT (tenant_id, jd_id) DO UPDATE
SET title = EXCLUDED.title,
    content = EXCLUDED.content,
    metadata = EXCLUDED.metadata,
    updated_at = timezone('utc', now());

INSERT INTO taxonomy.eco_occupations (
    occupation_id,
    title,
    title_normalized,
    locale,
    family,
    group_code,
    attributes
)
VALUES
    ('ECO-2131', 'Engenheira de Software', 'engenheira de software', 'pt-BR', 'Tecnologia', '2131', '{"seniority":"pleno","skills":["python","cloud"]}'::JSONB),
    ('ECO-2422', 'Cientista de Dados', 'cientista de dados', 'pt-BR', 'Tecnologia', '2422', '{"seniority":"senior","skills":["data science","ml"]}'::JSONB),
    ('ECO-1120', 'Gerente de Produto', 'gerente de produto', 'pt-BR', 'Gestao', '1120', '{"seniority":"pleno","skills":["produto","ux"]}'::JSONB),
    ('ECO-1425', 'Especialista DevOps', 'especialista devops', 'pt-BR', 'Tecnologia', '1425', '{"seniority":"senior","skills":["devops","sre"]}'::JSONB)
ON CONFLICT (occupation_id) DO UPDATE
SET title = EXCLUDED.title,
    title_normalized = EXCLUDED.title_normalized,
    locale = EXCLUDED.locale,
    family = EXCLUDED.family,
    group_code = EXCLUDED.group_code,
    attributes = EXCLUDED.attributes;

ANALYZE search.candidate_profiles;
ANALYZE search.candidate_embeddings;
