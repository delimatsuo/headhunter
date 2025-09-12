# Handover & Recovery Runbook (Updated 2025‑09‑11)

This document is the single source of truth to restart work quickly. It reflects the current plan and what’s actually in the repo.

## Summary

- LLM Processing: Together AI single pass using Qwen 2.5 32B Instruct (env: `TOGETHER_MODEL_STAGE1`).
- Output: Structured JSON profile with explicit/inferred skills, confidence, evidence, `analysis_confidence`, and `quality_flags`.
- Storage: Firestore (`candidates/`, `enriched_profiles/`); embeddings in `candidate_embeddings` (standardized).
- Search: One pipeline — ANN recall (pgvector planned) + re‑rank with structured signals (skills/experience/analysis_confidence) → one ranked list.
- UI: React SPA (Firebase Hosting) calls callable Functions.
- Functions: CRUD/search/upload; enrichment in Python processors (remove/guard Gemini enrichment in Functions).

Authoritative PRD: `.taskmaster/docs/prd.txt`

## UX Quick Reference

- People Search → Candidate Page (deep view).
- Job Search → minimal list (50; expandable) → Candidate Page on click.
- Candidate Page → Skill Map (explicit + inferred with verification tags), Pre‑Interview Analysis (on‑demand), compact timeline, resume freshness, LinkedIn link.

List row content: name, current role @ company, years/level, composite score, freshness badge, LinkedIn link, optional low‑depth badge.

## No Mock Fallbacks

- Production/staging do not return mock data when dependencies are unavailable.
- If enrichment (Gemini) is disabled or fails, endpoints surface an explicit error; no synthetic enrichment is returned.
- Embedding provider does not silently fallback to deterministic vectors. For development only, set `EMBEDDING_PROVIDER=local` to opt in to deterministic vectors.

## Environment & Secrets

- `TOGETHER_API_KEY`: Together AI key (required)
- `TOGETHER_MODEL_STAGE1`: default `Qwen/Qwen2.5-32B-Instruct`
- Firebase Admin creds (local/dev) or ADC in GCP
- (Future) Secret Manager for production

## Data Locations & Buckets

- GCS Raw: `gs://<PROJECT>-raw-json/`, `gs://<PROJECT>-raw-csv/`
- Profiles (optional): `gs://<PROJECT>-profiles/`
- Use one consistent naming scheme for buckets.

## Orchestration

- Single‑pass enrichment runs via Python processors (local or Cloud Run worker).
- Pub/Sub + Cloud Run is optional for throughput scaling.

## Embeddings & Search

- Baseline embeddings: Vertex `text-embedding-004`.
- Canonical collection: `candidate_embeddings`.
- Planned: Cloud SQL + pgvector service for ANN; SPA calls this service.

### Recall Safeguards (thin profiles)
- ANN recall unioned with deterministic title/company matches; then composite re‑rank.
- Deterministic boost + higher demotion floor when deterministic matches exist.
- Optional small quota for a “Potential matches (low profile depth)” section.

## Smoke Test (50 Candidates)

```bash
export TOGETHER_API_KEY=... 
export TOGETHER_MODEL_STAGE1=Qwen/Qwen2.5-32B-Instruct
python3 scripts/intelligent_skill_processor.py  # capped to 50 in main()
```

Expected:
- High parse success; few JSON repairs until TDD repair is integrated.
- Records include `analysis_confidence` and `quality_flags`; low‑content profiles are ranked lower but searchable.

## Known Gaps / Fixes

1) UI callable wiring: ensure `headhunter-ui/src/config/firebase.ts` exports
   - `skillAwareSearch = httpsCallable(functions, 'skillAwareSearch')`
   - `getCandidateSkillAssessment = httpsCallable(functions, 'getCandidateSkillAssessment')`

2) JSON repair + schema validation (TDD): integrate into processors; target <1% repair/quarantine.

3) Functions cleanup:
   - Remove stray entrypoints (keep `functions/src/index.ts` only)
   - Guard/remove Gemini enrichment code paths
   - Standardize embeddings to `candidate_embeddings` and align `firestore.rules`

4) Vector search (pgvector): implement ANN service on Cloud Run; SPA integration.

5) Pre‑Interview Analysis: add callable generate/get; add Candidate Page panel; cache with TTL.

6) Functions cleanup (completed): Gemini enrichment removed/disabled in Cloud Functions. Enrichment is performed exclusively by Together AI Python processors. Functions storage trigger now skips enrichment; the `enrichProfile` callable returns a failed‑precondition error to guide callers.

## Validation Checklist

- [ ] Together AI connectivity OK; Stage 1 model set via env
- [ ] Firestore writes visible; profiles include skills/confidence/evidence
- [ ] Embeddings generated and stored in `candidate_embeddings`
- [ ] UI search + skill assessment callable work; results include rationales
- [ ] Pre‑Interview Analysis callable enabled; Candidate Page renders summary/strengths/flags; caching effective
- [ ] Functions tests/build pass; no Gemini enrichment paths used

## Task Master Usage

- Use TDD and log notes:
  - `task-master set-status --id=<id> --status=in-progress`
  - `task-master update-subtask --id=<id> --prompt="TDD: tests first, then impl; notes…"`
  - `task-master set-status --id=<id> --status=done` after tests+docs

## Helpful Files

- PRD: `.taskmaster/docs/prd.txt`
- Architecture: `ARCHITECTURE.md`, `docs/CLOUD_ARCHITECTURE.md`
- Visual map: `docs/architecture-visual.html`
- Processors: `scripts/intelligent_skill_processor.py`, `scripts/*together*`
- Functions: `functions/src/*.ts`
- UI: `headhunter-ui/src/*`
