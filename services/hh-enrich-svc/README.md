# hh-enrich-svc

The enrichment service orchestrates asynchronous profile enrichment jobs, bridging recruiter-facing APIs with the Python processing pipeline and the embedding service. It handles authentication, deduplication, queueing, worker execution, telemetry, and downstream updates to Firestore and pgvector-backed embeddings.

## Architecture

1. **API Layer** – Exposes REST endpoints under `/v1/enrich` for job submission and status checks. Requests are authenticated using the shared `@hh/common` middleware and tenant metadata is propagated to workers.
2. **Job Store** – Persists job state in Redis, enforcing deduplication, TTL management, job metrics, and queue depth tracking.
3. **Worker** – Polls the Redis queue, executes the Python enrichment script (`scripts/run_enrich_job.py`), persists results, and communicates with the embedding service.
4. **Python Processor** – Resides in `cloud_run_worker` and performs candidate enrichment using Together AI before updating Firestore.
5. **Embedding Client** – Upserts embeddings via `hh-embed-svc` with retries, circuit breaking, and structured telemetry.

```
Client ──► hh-enrich-svc (API) ──► Redis (queue/state)
                                     │
                                     ├─► Worker ──► Python processor ──► Firestore
                                     │
                                     └─► Embedding client ──► hh-embed-svc ──► pgvector
```

## Endpoints

- `POST /v1/enrich/profile` – Enqueue a candidate enrichment job. Supports idempotency, `force` overrides, and optional synchronous waits by passing `"async": false`.
- `GET /v1/enrich/status/:jobId` – Retrieve job state and results.
- `GET /health` – Lightweight health probe that validates Redis connectivity.

### Request Headers

- `Authorization` – Gateway-issued bearer token.
- `X-Tenant-ID` – Required tenant identifier used for partitioning queues, metrics, and downstream documents.

## Job Lifecycle

1. **Submission** – The service validates the payload, computes an idempotency key, creates a job record, and enqueues it if it was not deduplicated.
2. **Processing** – A worker transitions the job to `processing`, invokes the Python enrichment script with retries, and records phase timing metrics.
3. **Embedding** – The worker invokes the embedding client. Circuit breakers and retries prevent cascading failures from the embedding service.
4. **Completion** – Job results include processing times, phase durations, attempt counts, embedding outcome, optional `embeddingSkippedReason`, and model metadata. Failures capture categorized error codes and messages.

## Error Handling & Resilience

- **Python processor** – Exponential backoff, attempt tracking, and a circuit breaker (`ENRICH_JOB_*` variables) prevent thundering herds when the processor is unavailable.
- **Embedding client** – Retries with jitter plus an independent circuit breaker (`ENRICH_EMBED_*` variables). When the breaker opens the worker completes the job with `embeddingUpserted=false`.
- **Redis outages** – Health metrics publish redis availability changes to logs (`metric=health.redis`).
- **Telemetry** – Structured log entries (`metric=*`) expose queue depth, latency percentiles, tenant usage, and failure categories for monitoring.

## Local Development

```bash
# Install dependencies
cd services
npm install --workspaces

# Start the service locally
npm run dev --workspace @hh/hh-enrich-svc

# Tail worker logs
npm run dev --workspace @hh/hh-enrich-svc | jq '."enrich-worker"?'
```

Environment variables are defined in `.env.local` and surfaced inside `docker-compose.local.yml`. Key settings:

- Redis host/port (`REDIS_HOST`, `REDIS_PORT`)
- Python runner (`ENRICH_PYTHON_BIN`, `ENRICH_PYTHON_SCRIPT`)
- Queue controls (`ENRICH_QUEUE_KEY`, `ENRICH_JOB_TTL_SECONDS`, `ENRICH_JOB_RETRY_LIMIT`, etc.)
- Embedding client resilience (`ENRICH_EMBED_*` variables)
- Metrics exporter toggle (`ENRICH_METRICS_EXPORT_ENABLED`)

## Testing & Tooling

- **Unit + integration suites** – Located under `tests/unit` and `tests/integration`. Run with Jest once Node dependencies are installed: `npx jest tests/unit/enrich-service.test.ts`.
- **End-to-end smoke** – `scripts/test-enrich-e2e.sh` orchestrates docker-compose services, submits a job, waits for completion, and inspects Firestore emulator state.
- **Performance benchmarking** – `node scripts/benchmark-enrich-service.js --jobs 50 --concurrency 10` exercises the full pipeline and prints latency percentiles.

## Monitoring & Alerting

Custom metrics emitted through structured logs feed `config/monitoring/enrich-service-dashboard.json`, covering:

- Latency percentiles (p50/p95/p99)
- Throughput vs failure rate
- Queue depth trends
- Embedding success ratio and circuit state
- Tenant-level job volume
- Recent worker errors (log panel)

These metrics can be ingested into Cloud Logging-based metrics or exported to Prometheus using the existing logging pipeline.

### Metrics Exporter

When `ENRICH_METRICS_EXPORT_ENABLED=true`, the service enables a lightweight Cloud Monitoring exporter that publishes custom metrics under `custom.googleapis.com/hh_enrich/*`. The exporter powers the bundled dashboard and maps enrichment events as follows:

- `job_latency_ms` – gauge updated on each completion with labels `percentile={p50|p95|p99}`.
- `job_completed_count` / `job_failed_count` – counters annotated with `tenant` labels.
- `queue_depth` – gauge reflecting the latest Redis queue length.
- `tenant_job_count` – counter incremented for new submissions per tenant.
- `embed_success_ratio` – success indicator (1/0) per attempt, aggregated to a ratio in dashboards. Skipped embeddings also increment `embed_skipped_count` with a `reason` label.
- `embed_circuit_state` – gauge (0 closed, 0.5 half-open, 1 open) mirroring the embedding circuit breaker.

The exporter uses the Firestore project id from the shared config and respects standard Cloud credentials (service account key or metadata server). Disable it for local development (default) to avoid API calls.

## Troubleshooting

| Symptom | Checks |
| --- | --- |
| Jobs stuck in `queued` | Inspect Redis queue depth, confirm worker process is running (`docker compose logs hh-enrich-svc`). |
| Frequent `python_circuit_open` errors | Inspect Python worker logs, verify `cloud_run_worker` dependencies, and consider increasing backoff. |
| Embedding failures | Confirm `hh-embed-svc` health, review circuit breaker logs, and ensure Together AI credentials are configured for the worker. |
| Missing Firestore updates | Validate emulator connectivity, ensure `FIRESTORE_EMULATOR_HOST` is set, and review Python processor output logs. |

## Scripts & Automation

- `scripts/test-enrich-e2e.sh` – Comprehensive smoke test with health checks.
- `scripts/benchmark-enrich-service.js` – Load testing harness for latency analysis.
- `scripts/test-services-health.sh` – Extended to include enrichment endpoints and dependencies (see script for details).

For additional operational guidance reference `docs/TDD_PROTOCOL.md` and `docs/HANDOVER.md` for security and credential rotation policies.
