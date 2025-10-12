# Onboarding Prompt for New AI Coding Agent

## Required Reading (before any code changes)
1. `docs/HANDOVER.md` – latest operational status, benchmarks, open risks.
2. `AGENTS.md` – mandatory protocols (TaskMaster workflow, PRD alignment, TDD).
3. `.taskmaster/docs/prd.txt` – authoritative requirements (search flow, p95 ≤ 1.2 s, rerank ≤ 350 ms).
4. `ARCHITECTURE.md`, `docs/TDD_PROTOCOL.md`, `docs/PRODUCTION_DEPLOYMENT_GUIDE.md` – architecture, TDD process, deploy steps.

## Current Context (2025-10-08 18:55 UTC)
- Phase 2 enrichment complete; Gemini embeddings generated and archived (`data/enriched/archive/20251006T202644/`).
- `hh-search-svc` implements Redis-backed embedding cache, pgvector hybrid recall, optional Together rerank, and local performance tracker.
- Benchmark tooling added:
  - `services/hh-search-svc/src/scripts/run-hybrid-benchmark.ts`
  - `services/hh-search-svc/src/scripts/report-metrics.ts`
- Latest production benchmark (cache bust JD “Principal product engineer fintech”, 40 iterations, concurrency 5): `p95 total ≈ 230 ms`, `p95 embedding ≈ 57 ms`, rerank 0 ms (rerank apparently bypassed), cache-hit 0%.
- `ENABLE_RERANK` not explicitly set in Cloud Run env; service relies on default `true`. Redeploy attempts failed due to outdated artifact tags; active revision: `hh-search-svc-production-00041-jxf`.
- API Gateway `/health` does **not** expose metrics; call Cloud Run URL (`https://hh-search-svc-production-akcoqbr7sa-uc.a.run.app`) for metrics snapshot.

## Open Investigations / Next Steps
1. **Rerank Diagnostics**
   - Review `hh-search-svc` logs for `Rerank request failed` warnings.
   - Confirm `hh-rerank-svc` health/credentials; inspect `services/hh-rerank-svc/src/config.ts` and related secrets.
   - Ensure search service is sending job descriptions and candidate counts above rerank thresholds.
2. **Rebuild & Redeploy Search Service**
   - Build fresh image: `./scripts/build-and-push-services.sh --project-id headhunter-ai-0088 --environment production --services hh-search-svc`.
   - Update Cloud Run with new image and explicit `ENABLE_RERANK=true` (after validating image availability).
3. **Performance Verification**
   - Run benchmark script (cache bust) against Cloud Run endpoint using production API key.
   - Capture metrics snapshot (`report-metrics.ts`) and store results in `docs/HANDOVER.md` or TaskMaster notes.
4. **Documentation & TaskMaster**
   - Update `docs/HANDOVER.md` with new findings.
   - Log progress under Task 67.6 (`task-master update-subtask ...`) before marking done.

## Key Commands
```bash
# Benchmark (Cloud Run URL on production)
SEARCH_API_KEY=$(gcloud secrets versions access latest --secret=api-gateway-key --project=headhunter-ai-0088)
npx ts-node services/hh-search-svc/src/scripts/run-hybrid-benchmark.ts \
  --url https://hh-search-svc-production-akcoqbr7sa-uc.a.run.app \
  --tenantId tenant-alpha \
  --jobDescription 'Principal product engineer fintech' \
  --limit 6 --iterations 40 --concurrency 5 --bustCache true

# Metrics snapshot
SEARCH_API_KEY=$(gcloud secrets versions access latest --secret=api-gateway-key --project=headhunter-ai-0088)
npx ts-node services/hh-search-svc/src/scripts/report-metrics.ts \
  https://hh-search-svc-production-akcoqbr7sa-uc.a.run.app

# Cloud Run env inspection
gcloud run services describe hh-search-svc-production \
  --region=us-central1 --project=headhunter-ai-0088 \
  --format='value(spec.template.spec.containers[0].env)'
```

## Expectations for Incoming Agent
- Follow TaskMaster pre-work (`task-master next` → `task-master show <id>`).
- Cite PRD line numbers when asserting scope.
- Adhere strictly to TDD (write/confirm failing test, implement, rerun suite).
- Update `docs/HANDOVER.md` and TaskMaster notes before completing a task.
- Coordinate with existing benchmark tooling; do not run API Gateway health checks for metrics (use Cloud Run URL).
