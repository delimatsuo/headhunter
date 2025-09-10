# Handover & Recovery Runbook

Last updated: 2025-09-10

Purpose: If the session crashes, this is the single source of truth to restart work quickly with the correct architecture.

## Summary

- AI Provider: Together AI (chat completions; Llama 3.1 8B Instruct Turbo)
- Storage: Firestore (enhanced profiles), Cloud Storage (raw/enhanced JSON), Cloud SQL + pgvector (embeddings)
- APIs: Firebase Cloud Functions and/or Cloud Run
- UI: React (Firebase Hosting)

Authoritative PRD: `.taskmaster/docs/prd.txt` (Together AI + pgvector)

## Project Consolidation

Use ONE GCP/Firebase project for all resources. Recommended: `headhunter-ai-0088`.

What to do (manual, from your machine):
- Set default: `gcloud config set project headhunter-ai-0088`
- (Optional) Delete any unused projects after exporting data/backups:
  - List: `gcloud projects list`
  - Mark for deletion: `gcloud projects delete <OTHER_PROJECT_ID>`

Note: Deleting projects is irreversible and not automated here.

## Secrets & Environment

- Together AI: `TOGETHER_API_KEY` (set in shell or `.env` for Python processors)
- Firebase Admin credentials (local/dev): service account JSON or Application Default Credentials
- For CI/Cloud Run: use Secret Manager or deploy-time environment variables

## Data Locations

- NAS source (local): `/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project`
- Target GCS buckets (in chosen project):
  - `gs://headhunter-ai-0088-raw-csv/`
  - `gs://headhunter-ai-0088-raw-json/`
  - `gs://headhunter-ai-0088-profiles/`

Upload (run locally, where NAS is mounted):
```bash
# Set project
gcloud config set project headhunter-ai-0088

# Create buckets (if needed)
gsutil mb -p headhunter-ai-0088 -l us-central1 gs://headhunter-ai-0088-raw-csv/ || true
gsutil mb -p headhunter-ai-0088 -l us-central1 gs://headhunter-ai-0088-raw-json/ || true
gsutil mb -p headhunter-ai-0088 -l us-central1 gs://headhunter-ai-0088-profiles/ || true

# Sync CSV and JSON (adjust subfolders as needed)
gsutil -m rsync -r \
  "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/CSV" \
  gs://headhunter-ai-0088-raw-csv/

gsutil -m rsync -r \
  "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project" \
  gs://headhunter-ai-0088-raw-json/
```

## Orchestration Plan

Stage 1: Enrichment
- Pub/Sub topic `candidate-process-requests` with payloads pointing to raw JSON in GCS.
- Cloud Run service `candidate-enricher` (Python) pulls JSON, calls Together AI, writes to Firestore.
- Batch kick-off via Cloud Scheduler or one-time script.

Stage 2: Embeddings
- Either in the same worker or a separate `embedding-worker` (Pub/Sub triggered), generate embeddings (Vertex `text-embedding-004` baseline) and upsert vectors into Cloud SQL `pgvector`.

Stage 3: Search API
- Cloud Functions/Run endpoint receives JD or profile text → generates query embedding → ANN query in pgvector → returns ranked candidates with rationale.

## Vector Store

Provider: Cloud SQL (PostgreSQL + pgvector)

Setup (one-time):
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE candidate_vectors (
  candidate_id TEXT PRIMARY KEY,
  embedding VECTOR(768) NOT NULL,
  metadata JSONB,
  updated_at TIMESTAMP DEFAULT NOW()
);

-- IVFFLAT index (tune lists)
CREATE INDEX ON candidate_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

Query (cosine similarity):
```sql
-- Assume :q is a 768-dim vector
SELECT candidate_id,
       1 - (embedding <=> :q) AS score,
       metadata
FROM candidate_vectors
ORDER BY embedding <-> :q
LIMIT 50;
```

## Embedding Provider

- Baseline: Vertex `text-embedding-004` (already integrated in `functions/src/vector-search.ts`).
- Pluggable: Add provider env flag later (vertex|together|local) to switch embedding backends.
- Bake-off: Compare Vertex vs Together embeddings on a labeled subset (2k candidates × 30–50 JDs) using NDCG/MRR.

## Cost Guardrails (Together AI)

- Token budget per candidate: target ~5k tokens (trim noisy inputs; cap output length).
- Estimated range for 29k candidates (confirm with current pricing): $80–$180 total; keep below $300 soft cap.
- Batch reprocessing policy: nightly or event-driven on resume updates; enqueue via Pub/Sub.

## One-Time 50-Candidate Test

```bash
# Use intelligent batch processor for richer analysis
python3 scripts/intelligent_skill_processor.py  # internally caps to 50 in main()

# Verify Firestore writes, then run embedding generation endpoint
cd functions && npm run build && npm run deploy
# Use callable generateEmbeddingForCandidate or batch generator as needed
```

## Known Issues

- `functions/src/index.ts` references `enrichProfileWithGemini` but defines `enrichProfile`. Align or remove Gemini references (enrichment is in Python/Together).

## Contacts & Ownership

- AI Processing: Together processors in `scripts/`
- Cloud APIs: `functions/src/`
- Vector DB: Cloud SQL (pgvector)
- UI: `headhunter-ui/`

