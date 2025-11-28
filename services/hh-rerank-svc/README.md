# hh-rerank-svc

`hh-rerank-svc` provides Together AI powered reranking for Headhunter search flows. The service consumes candidate lists plus job context and returns tenant-scoped ordering tuned for the ≤350 ms p95 SLA defined in the rerank PRD.

## Features
- `POST /v1/search/rerank` — reranks candidates with Gemini 2.5 Flash (primary) or Qwen 2.5 32B via Together AI (fallback).
- Tenant-aware Redis caching (`hh:rerank:{tenant}:{jd_hash}:{docset_hash}`) with graceful cache bypass controls.
- Circuit breaker, retry, and timeout safeguards around LLM providers to guarantee graceful degradation.
- Built-in health endpoint surfaces Redis, Gemini, and Together AI status for Cloud Run probes.
- Structured logging, Firebase auth, and tenant validation provided by `@hh/common`.

## Quick Start

```bash
cd services
npm install --workspaces
npm run build --workspace @hh/hh-rerank-svc
npm run dev --workspace @hh/hh-rerank-svc
```

Copy `.env.example` to `.env` (or export variables) and supply valid `TOGETHER_API_KEY` and Google Cloud credentials before starting locally.

## Configuration
Key environment variables (see `.env.example` for the full list):

### Gemini (Primary)
- `GEMINI_ENABLE` — toggle Gemini integration (default: `true`).
- `GEMINI_PROJECT_ID`, `GEMINI_LOCATION` — Google Cloud project details.
- `GEMINI_MODEL` — model version (default: `gemini-2.5-flash`).
- `GEMINI_TIMEOUT_MS` — timeout for Gemini requests (default: `8000`).

### Together AI (Fallback)
- `TOGETHER_API_KEY` / `TOGETHER_MODEL` / `TOGETHER_TIMEOUT_MS` — Together AI auth and latency targets.

### Runtime
- `RERANK_SLA_TARGET_MS` — overall service SLA target (default: `10000` to accommodate Gemini).
- `RERANK_MAX_CANDIDATES`, `RERANK_DEFAULT_LIMIT` — caps to keep prompts light.
- `RERANK_CACHE_TTL_SECONDS`, `RERANK_REDIS_PREFIX` — Redis cache behaviour.
- `RERANK_ENABLE_FALLBACK` — toggle graceful degradation to passthrough ranking.
- `REDIS_*` — standard cache connectivity toggles.

## API Overview
A minimal rerank request:

```json
{
  "jobDescription": "Lead backend engineer responsible for...",
  "jdHash": "4c8a3316f5df4b40",
  "candidates": [
    { "candidateId": "cand-123", "summary": "10y Python...", "initialScore": 0.78 },
    { "candidateId": "cand-456", "summary": "8y Go...", "features": { "vectorScore": 0.71 } }
  ],
  "limit": 10,
  "includeReasons": true
}
```

Responses follow the schema in `src/schemas.ts`, returning ranked candidates, cache metadata, Together AI timing, and a `usedFallback` flag when passthrough ordering is served.

## Caching & Degradation
- Cache keys combine tenant + JD hash + candidate docset hash, enabling safe reuse across repeated queries.
- Requests can opt-out of caching with `disableCache=true`.
- Together AI failures (timeouts, circuit breaker, HTTP 5xx) trigger passthrough ordering when `RERANK_ENABLE_FALLBACK=true`, preserving baseline relevance while logging degradation.

## Performance Notes
- Prompt construction and Together calls are capped to honour the ≤350 ms p95 SLA.
- Circuit breaker thresholds (`TOGETHER_CB_FAILURES`, `TOGETHER_CB_COOLDOWN_MS`) prevent repeated slow vendor calls.
- Slow invocations emit structured warnings with latency breakdowns.

## Testing & Tooling
Run unit tests with `npm test --workspace @hh/hh-rerank-svc`. Type-check via `npm run typecheck --workspace @hh/hh-rerank-svc`. Lint with `npm run lint --workspace @hh/hh-rerank-svc`.

## Deployment
The Dockerfile mirrors other Cloud Run services.

```bash
cd services
gcloud builds submit --config cloudbuild.yaml --substitutions _SERVICE=hh-rerank-svc
```

Provide production Together AI credentials via Secret Manager and point Redis hosts at the regional cache cluster. Follow the staged rollout playbook in `docs/RUNBOOK.md`.

## Troubleshooting
- `/health` returns HTTP 503 when Redis or Together AI is degraded.
- Set `LOG_LEVEL=debug` for verbose logging.
- Use `RERANK_CACHE_DISABLE=true` when testing uncached behaviour locally.
- Verify Together connectivity with `curl -H "Authorization: Bearer $TOGETHER_API_KEY" https://api.together.xyz/v1/models`.

