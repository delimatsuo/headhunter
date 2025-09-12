Vector ANN Search Service (Cloud Run) – Specification

Purpose
- Provide fast ANN (approximate nearest neighbor) search over candidate embeddings stored in Cloud SQL + pgvector, and return results re‑ranked with structured signals.

Data
- Table: candidate_vectors(candidate_id TEXT PRIMARY KEY, embedding VECTOR(768), metadata JSONB, updated_at TIMESTAMP)
- Index: CREATE INDEX ON candidate_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

API (HTTP JSON)
- POST /search
  Request:
  { "query_text": "Senior backend engineer, Python + AWS, SOA", "limit": 50, "filters": { "min_years_experience": 5, "current_level": "senior", "company_tier": "enterprise" }, "org_id": "optional" }
  Response:
  { "candidates": [ { "candidate_id": "123", "similarity_score": 0.87, "metadata": {"years_experience": 9, "current_level": "senior", "company_tier": "enterprise"}, "match_reasons": ["semantic match", "python, aws"] } ], "search_time_ms": 42 }

- POST /skill-aware-search (preferred)
  Request adds required_skills, preferred_skills, experience_level, minimum_overall_confidence, limit, ranking_weights. Response aligns with Functions skill-aware endpoint and includes profile/rationale for UI.

Flow
1) Generate query embedding (same provider as Functions: Vertex text-embedding-004)
2) ANN query in pgvector (cosine distance), apply coarse filters in SQL
3) Fetch candidate structured data (Firestore or cache) for re‑ranking
4) Compute composite ranking (skill match + confidence + vector similarity + experience), applying analysis_confidence demotion
5) Return unified ranked results with profile snippet and rationale

Security
- Service account with Cloud SQL IAM Database Auth
- Optionally require Firebase token or service‑to‑service auth for internal calls

Notes
- Keep Function fallback for dev/small data
- Share scoring code between this service and Functions where possible to ensure identical results
