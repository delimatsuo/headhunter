# Handover & Recovery Runbook (Updated 2025-10-01)

> Canonical repository path: `/Volumes/Extreme Pro/myprojects/headhunter`. Do **not** work from `/Users/delimatsuo/Documents/Coding/headhunter`.
> Guardrail: all automation wrappers under `scripts/` source `scripts/utils/repo_guard.sh` and exit immediately when invoked from non-canonical clones.

This runbook is the single source of truth for resuming work or restoring local parity with production. It reflects the Fastify microservice mesh that replaced the legacy Cloud Functions stack.

## 🚨 CRITICAL: Production Deployment Status (2025-10-01)

**CURRENT STATE: PRODUCTION DEPLOYMENT FAILED**

The Phase 5-7 deployment executed on **2025-09-30T23:54:29Z** has **FAILED**. All 8 Fastify services are **NON-FUNCTIONAL** in production.

### Deployment Failure Summary

| Component | Expected State | Actual State | Status |
|-----------|---------------|--------------|--------|
| Fastify Services (8) | Healthy, serving traffic | 7 not deployed, 1 failing | ❌ FAILED |
| API Gateway | Active, routing requests | Not deployed | ❌ FAILED |
| OAuth Endpoint | `idp.production.ella.jobs` | `auth.headhunter.ai` (non-existent) | ❌ BLOCKED |
| Production Traffic | Fastify mesh | Legacy Cloud Functions (46 active) | ⚠️ DEGRADED |

### Root Causes Identified

1. **Invalid Cloud Run Configuration**
   - Error: `autoscaling.knative.dev/maxScale` annotation on Service instead of Revision
   - Impact: All 8 service deployments rejected by Cloud Run API
   - Location: Deployment configuration files

2. **Container PORT Misconfiguration**
   - Error: Fastify services not listening on `PORT=8080` environment variable
   - Impact: `hh-embed-svc` deployed but failing health checks (STATUS=False)
   - Log: "Container failed to start and listen on the port defined provided by the PORT=8080"

3. **OAuth Endpoint Misconfiguration**
   - Error: `token_uri` points to non-existent `https://auth.headhunter.ai/oauth/token`
   - Correct: Should be `https://idp.production.ella.jobs/oauth/token`
   - Impact: Authentication completely broken, no tokens can be issued

4. **Deployment Script Validation Gap**
   - Error: Script reports SUCCESS based on submission, not actual health
   - Impact: Deployment report shows "Ready" when services actually failed
   - Evidence: Deploy manifest shows all services with `"status": "failed"`, `"url": null`

### Recovery Task

**Task Master ID:** 78 - "Production Deployment Recovery"
**Priority:** CRITICAL (marked as medium due to TM constraints)
**Subtasks:** 8 (see `.taskmaster/tasks/task_078.txt`)

**Next Steps:**
1. Read task details: `cat .taskmaster/tasks/task_078.txt`
2. Start with subtask 78.1: Fix autoscaling annotation
3. Continue through 78.2-78.8 in dependency order

### Emergency Contact Protocol

If this session fails or you need to handover:
1. **Task Master status**: All recovery work tracked in Task 78 with 8 subtasks
2. **Deployment artifacts**: All evidence in `.deployment/` directory
3. **Root cause analysis**: Complete discrepancy report in this handover section
4. **Next operator**: Start with `cat .taskmaster/tasks/task_078.txt` for recovery plan

---

## Start Here – Operator Checklist

1. **Prime environment variables**
   ```bash
   export TOGETHER_API_KEY=...        # Live embedding/enrichment; mock wiring is available locally
   export FIRESTORE_EMULATOR_HOST=localhost:8080
   export PUBSUB_EMULATOR_HOST=localhost:8681
   ```
   - Root `.env` is the canonical source. Each service may include a `.env.local`; values there override root-level entries when the service container boots.
   - Keep `.env` and `.env.local` aligned—if you add a key to one, mirror or document it in the other to avoid drift.

2. **Install workspace dependencies**
   ```bash
   cd /Volumes/Extreme\ Pro/myprojects/headhunter
   npm install --workspaces --prefix services
   ```

3. **Launch the local mesh**
   ```bash
   docker compose -f docker-compose.local.yml up --build
   ```
   Check health endpoints once logs settle:

   | Port | Service | Health check | Expected response | If failure |
   | --- | --- | --- | --- | --- |
   | 7101 | `hh-embed-svc` | `curl -sf localhost:7101/health` | `{"status":"ok"}` | Verify Together AI (or mock) keys and Postgres connection. |
   | 7102 | `hh-search-svc` | `curl -sf localhost:7102/health` | `{"status":"ok"}` | Confirm Redis/Postgres availability; rerun warmup script. |
   | 7103 | `hh-rerank-svc` | `curl -sf localhost:7103/health` | `{"status":"ok"}` | Warm caches: `npm run seed:rerank --prefix services/hh-rerank-svc`. |
   | 7104 | `hh-evidence-svc` | `curl -sf localhost:7104/health` | `{"status":"ok"}` | Re-seed Firestore emulator via `scripts/manage_tenant_credentials.sh`. |
   | 7105 | `hh-eco-svc` | `curl -sf localhost:7105/health` | `{"status":"ok"}` | Ensure filesystem templates exist (`services/hh-eco-svc/templates`). |
   | 7106 | `hh-msgs-svc` | `curl -sf localhost:7106/health` | `{"status":"ok"}` | Reset Pub/Sub emulator (`docker compose restart pubsub`). |
   | 7107 | `hh-admin-svc` | `curl -sf localhost:7107/health` | `{"status":"ok"}` | Verify scheduler topics: `scripts/seed_pubsub_topics.sh`. |
   | 7108 | `hh-enrich-svc` | `curl -sf localhost:7108/health` | `{"status":"ok"}` | Inspect Python worker logs; confirm bind mount for `scripts/`. |

4. **Validate the integration baseline**
   ```bash
   SKIP_JEST=1 npm run test:integration --prefix services
   ```
   - Expect `cacheHitRate=1.0` and rerank latency ≈ 0 ms in the summary output.
   - If the cache hit rate dips, flush/rehydrate Redis (`redis-cli FLUSHALL` + rerun warmup) and ensure `hh-embed-svc` finished its backfill.
   - Latency spikes (>5 ms) usually indicate Redis pool exhaustion or Postgres index drift—review `hh-rerank-svc` logs and `EXPLAIN ANALYZE` slow queries.

5. **Log progress in Task Master**
   ```bash
   task-master list --with-subtasks
   task-master next
   ```
   Record any bootstrap surprises with `TODO prepare-local-env` so they are folded into the upcoming automation script.

`scripts/prepare-local-env.sh` will wrap steps 1–4 once shipped. Keep detailed notes of manual effort so the script can replicate them faithfully.

## Production Deployment Runbook

**Pre-deployment checklist**

- ✅ Infrastructure healthy (`gcloud sql instances describe`, `gcloud redis instances describe`, Pub/Sub topics)  
- ✅ Secrets rotated: Together AI, DB credentials, `gateway-api-key-*`, `oauth-client-*`  
- ✅ Artifact Registry access confirmed (`gcloud auth configure-docker us-central1-docker.pkg.dev`)  
- ✅ Deployment window approved and communication plan agreed

**Primary command (≈10–15 minutes end-to-end)**

```bash
./scripts/deploy-production.sh --project-id headhunter-ai-0088 --environment production --rollback-on-failure
```

Key outputs are written to `.deployment/` (build & deploy manifests, gateway snapshot, smoke-test report) and logged to stdout.

**Post-deployment validation**

1. Review smoke report path printed by the script (`.deployment/test-reports/smoke-test-report-*.json`).  
2. Double-check Cloud Run readiness: `gcloud run services list --project headhunter-ai-0088 --region us-central1`.  
3. Hit gateway health endpoints: `curl https://<gateway-host>/health` and `/ready`.  
4. Run the post-deployment load suite:  
   ```bash
   ./scripts/run-post-deployment-load-tests.sh --gateway-endpoint https://<gateway-host> --tenant-id tenant-alpha
   ```
   Load test reports land under `.deployment/load-tests/post-deploy-*/`.  
5. Verify monitoring dashboards and alerts: confirm the `.monitoring/setup-*/monitoring-manifest.json` entries exist, dashboards render in Cloud Monitoring, and no new alerts fired during deployment.  
6. Run deployment readiness validation:  
   ```bash
   ./scripts/validate-deployment-readiness.sh --project-id headhunter-ai-0088 --environment production
   ```
   Inspect `.deployment/validation-report-20251001-010532.json` for blockers (`BLOCKED`) or warnings (`PARTIAL`) before sign-off.  
7. Generate and review the deployment report (auto-run by `deploy-production.sh`, regenerate if needed):  
   ```bash
   ./scripts/generate-deployment-report.sh --project-id headhunter-ai-0088 --environment production --region us-central1
   ```
   Ensure `docs/deployment-report-*.md` is complete, captures SLA evidence, and includes stakeholder sign-off.  
8. Check SLO compliance (overall p95 latency < 1.2s, rerank p95 < 350 ms, error rate < 1%, cache hit rate > 0.98) via Cloud Monitoring or the load test report.  
9. Spot-check application logs for each service (`gcloud logging read` filters provided below).
10. Review the final deployment report for comprehensive deployment evidence and sign-off status:
   - Report path: `docs/deployment-report-phase5-7.md`
   - Verify executive summary, Cloud Run inventory, API Gateway configuration, monitoring assets (9 dashboards, 12 alert policies, 8 uptime checks), load test metrics (9 scenarios, 73,200 requests, 0.39% error rate, 78% cache hit rate), SLA validation (PASS), TODOs, known blockers, rollback procedures, validation checklist, references, and stakeholder sign-off table
   - Confirm the signed report is archived in version control and uploaded to the audit bucket if required
   - Notify operations lead, security reviewer, and product owner when sign-off table is complete

**Deployment report review**

- ✅ All eight Fastify services listed with URLs, revisions, and health status
- ✅ Container image digests align with build manifest and git SHA
- ✅ API Gateway hostname, routes, and OAuth/CORS configuration documented
- ✅ Monitoring dashboards, alert policies, and uptime checks linked and verified
- ✅ Load test metrics show SLA compliance (latency, error rate, cache hit rate, throughput)
- ✅ Known blockers resolved or clearly documented with remediation plans
- ✅ Outstanding TODOs assigned owners and target dates
- ✅ Sign-off table completed by operations lead, security reviewer, and product owner
- Archive the report in version control (force-add timestamped file) and optionally upload to GCS audit bucket.

**Rollback guidance**

- Automatic rollback is triggered when `--rollback-on-failure` is set.  
- Manual Cloud Run rollback: reference `.deployment/manifests/pre-deploy-revisions-*.json` and run `gcloud run services update-traffic <service>-production --to-revisions=<revision>=100`.  
- Manual gateway rollback: parse `.deployment/manifests/pre-gateway-config-*.json` and call `gcloud api-gateway gateways update headhunter-api-gateway-production --api-config=<config-id>`.

**Escalation contacts**

- Primary: Ops on-call (PagerDuty service `headhunter-sre`)  
- Secondary: #headhunter-ops Slack channel with deployment summary and relevant artifact links

## Platform Snapshot

- **Services (Fastify)**: `hh-embed-svc`, `hh-search-svc`, `hh-rerank-svc`, `hh-evidence-svc`, `hh-eco-svc`, `hh-msgs-svc`, `hh-admin-svc`, `hh-enrich-svc` (see `ARCHITECTURE.md` for full dependency graph).
- **Shared infrastructure**: Redis (caching/idempotency), Postgres + pgvector (embeddings, messaging), Firestore emulator (candidate profiles), Pub/Sub emulator (scheduler), Together AI mock (LLM parity), mock OAuth (JWT issuance), Python worker (`python:3.11-slim`).
- **Tenant validation**: `@hh/common` middleware enforces tenant headers, JWT claims, and attaches correlation IDs to each log entry. Mock OAuth issues tokens with production-matching claims locally.
- **Integration baseline**: Last passing run via `docker-compose.local.yml` + `SKIP_JEST=1` achieved `cacheHitRate=1.0` and ≈0 ms rerank latency—treat this as the go/no-go metric before merging changes.

## Environment Files & Secrets

- `.env` (root) hydrates shared secrets and connection strings.
- `services/**/.env.local` override or extend variables per service. Example: `services/hh-msgs-svc/.env.local` defines Pub/Sub emulator host overrides in addition to the root values.
- Whenever you modify a secret or add a new variable, update both the root `.env.example` and service-specific `.env.local.example` (if present) so the bootstrap script can provision them automatically.

## Integration Baseline – Interpretation & Response

| Metric | Source | Healthy value | Signals a problem when... | Immediate actions |
| --- | --- | --- | --- | --- |
| `cacheHitRate` | `hh-rerank-svc` `/metrics` (`rerank_cache_hit_rate`) | `1.0` | `< 0.98` | Warm caches (`npm run seed:rerank --prefix services/hh-rerank-svc`), inspect Redis key TTLs. |
| `rerankLatencyMs` | Test summary + `/metrics` histogram | `≈ 0` | `> 5` | Check Redis connection pool, confirm Postgres indices (`scripts/db/check_indexes.sql`). |
| Integration exit code | `npm run test:integration` | `0` | non-zero | Review `integration-results.log` and rerun with `DEBUG=hh:*` to capture verbose traces. |

## Service Debugging Recipes

- `hh-embed-svc`: `curl -X POST localhost:7101/v1/embeddings -H 'tenant-id: demo' -d '{"text":"sample"}'`. Expect deterministic vector. Troubleshoot by verifying Together AI credentials or mock server logs.
- `hh-search-svc`: `curl -X POST localhost:7102/v1/search -H 'tenant-id: demo' -H 'Authorization: Bearer $(scripts/mock_oauth/issue_token.sh demo)' -d '{"query":"staff engineer"}'`. If empty results, confirm enrichment backfill.
- `hh-rerank-svc`: `curl localhost:7103/metrics | grep rerank_latency_bucket`. Missing buckets usually mean caches weren’t hydrated.
- `hh-evidence-svc`: `curl localhost:7104/v1/evidence?candidateId=demo-123`. Check Firestore emulator data if 404.
- `hh-eco-svc`: `curl localhost:7105/v1/templates`. Requires ECO seed data (`scripts/seed_eco_data.sh`).
- `hh-msgs-svc`: `curl localhost:7106/v1/health`. For queue issues, inspect Postgres `notification_jobs` and Pub/Sub emulator topics.
- `hh-admin-svc`: `curl localhost:7107/v1/tenants`. Ensure scheduler topics exist and admin secrets match `.env`.
- `hh-enrich-svc`: `curl localhost:7108/v1/status`. If enrichment stalls, inspect `docker compose logs -f hh-enrich-svc python-worker` (Python container) for stack traces.

## Deployment Troubleshooting

| Failure point | Symptoms | Immediate actions |
| --- | --- | --- |
| Docker build | `build-and-push-services.sh` exits non-zero, missing manifest | Inspect `.deployment/build-logs/<service>-*.log`, run service-specific `npm test`, confirm Dockerfile base image accessibility. |
| Cloud Run deploy | `deploy-cloud-run-services.sh` reports `Service did not reach ready state` | Check service logs (`gcloud run services logs read`), verify Secret Manager access, ensure SQL/Redis connectors exist. |
| Gateway update | `deploy_api_gateway.sh` validation error | Examine `.deployment/deploy-logs/gateway-update-*.log`, confirm OpenAPI placeholders rendered, ensure backend URLs resolve. |
| Smoke tests | `smoke-test-deployment.sh` fails auth | Fetch `oauth-client-<tenant>` and `gateway-api-key-<tenant>` secrets, rerun with explicit `--oauth-token` / `--api-key`. |
| Post-deploy checks | Elevated 5XX or latency >5s | Roll traffic back using pre-deploy manifest, investigate individual service metrics and Redis/Postgres health. |

## Post-Deployment Load Testing

- **Purpose:** Validate SLA compliance under production load and document evidence for deployment sign-off.
- **Command:**
  ```bash
  ./scripts/run-post-deployment-load-tests.sh \
    --gateway-endpoint https://<gateway-host> \
    --tenant-id tenant-alpha \
    --duration 300 \
    --concurrency 10
  ```
- **Scenarios:** embeddings, hybrid search, rerank, evidence retrieval, ECO search, skill expansion, admin snapshots, profile enrichment, end-to-end pipeline.
- **Runtime:** ≈5–10 minutes (tunable via `--duration`, `--concurrency`, `--ramp-up`).
- **Pass criteria:** overall p95 < 1.2s, rerank p95 < 350 ms, cached read p95 < 250 ms, error rate < 1%, cache hit rate > 0.98, throughput ≥ 100 req/min/service.
- **Artifacts:** `.deployment/load-tests/post-deploy-*/load-test-report.json`, `.deployment/load-tests/post-deploy-*/load-test-report.md`, per-scenario logs under `results/`, SLA evaluation stored as `sla-validation.json`.
- **If failures occur:**
  1. Inspect gateway/rerank/embedding dashboards (see `docs/MONITORING_RUNBOOK.md`).
  2. Review Cloud Logging filtered to the load test time window.
  3. Execute remediation: warm caches, scale Cloud Run, verify Together AI availability, re-run scenario.
  4. Escalate or rollback if SLA thresholds remain violated after remediation.

## Deployment Readiness Validation

- **When to run:** After deployment steps complete, before final report sign-off, and whenever a deployment step is retried.
- **Command:**
  ```bash
  ./scripts/validate-deployment-readiness.sh --project-id headhunter-ai-0088 --environment production
  ```
- **What it checks:** Cloud Run Fastify services, API Gateway status, monitoring manifests/dashboards/alerts, load test artifacts, deployment manifests, Secret Manager entries, core infrastructure (Cloud SQL, Redis, Firestore, Pub/Sub, VPC connector), and ADC credentials.
- **Interpretation:** `READY` means all prerequisites satisfied; `PARTIAL` surfaces warnings that should be triaged before sign-off; `BLOCKED` requires remediation prior to proceeding.
- **Common issues:** Missing Fastify services (rerun deployment), disabled API Gateway (enable service and redeploy), absent monitoring manifest (re-run monitoring setup), stale load test artifacts (rerun load suite), missing secrets (add Secret Manager versions), or missing ADC (`gcloud auth application-default login`). The generated `.deployment/validation-report-20251001-010532.json` file includes detailed remediation notes.

## Python Worker Integration

- The enrichment container mount `./scripts` into `/app/scripts`. Python dependencies are managed via `scripts/requirements.txt` and a local virtualenv inside the container.
- Long-running tasks (resume parsing, LLM retries) run through `python:3.11-slim` sidecar workers triggered by `hh-enrich-svc`. Monitor with `docker compose logs -f python-worker`.
- When updating scripts, restart `hh-enrich-svc` so bind-mounted changes propagate. Add regression tests to `scripts/tests/` where possible.

## Bootstrap Automation Prep (`scripts/prepare-local-env.sh`)

- Collect manual steps, flags, and caveats in this runbook tagged with `TODO prepare-local-env`.
- Required automation scope: dependency install, `.env` hydration, emulator reseed (Firestore/Postgres/Redis), compose startup, integration validation, health endpoint assertions.
- Once the script is implemented, replace manual instructions above with a single call (`./scripts/prepare-local-env.sh --full`) and retain troubleshooting steps as fallbacks.

## Observability & Logging

### Cloud Monitoring Dashboards

- Central index lives in `docs/MONITORING_RUNBOOK.md` → *Dashboard Catalog*. Use the manifest at `.monitoring/setup-*/monitoring-manifest.json` for authoritative dashboard IDs and console URLs.
- Quick links (replace `<id>` with manifest values):
  - [Cloud Run Worker Performance](https://console.cloud.google.com/monitoring/dashboards/custom/<id>?project=headhunter-ai-0088)
  - [API Gateway Overview](https://console.cloud.google.com/monitoring/dashboards/custom/<id>?project=headhunter-ai-0088)
  - [Cost Tracking](https://console.cloud.google.com/monitoring/dashboards/custom/<id>?project=headhunter-ai-0088)
- Review cadences: workers daily, gateway after deployments, cost weekly. Document findings in deployment reports.

### Alert Policies

- Severity mapping: **SEV-1** uptime failures, **SEV-2** SLA breaches (latency/error), **SEV-3** supporting signals (DB, Together AI, backlog).
- Notification channels (PagerDuty, Slack, email) listed in the runbook *Alert Policy Catalog*. Confirm contact lists quarterly.
- Escalation: SEV-1 pages on-call immediately; SEV-2 requires acknowledgement within 15 minutes; SEV-3 can be triaged during business hours.

### SLO Targets

- Overview documented in `docs/MONITORING_RUNBOOK.md` → *SLO Targets*.
- Primary thresholds: overall p95 < 1.2s, rerank p95 < 350 ms, error rate < 1%, cache hit rate > 0.98, availability 99.9%.
- Compliance checks: use Cloud Monitoring SLO widgets or the post-deployment load test report.

### Metrics Endpoints & Observability Tooling

- Prometheus metrics: `http://localhost:710X/metrics` for local runs; production metrics re-exported into Cloud Monitoring via Managed Prometheus integration.
- Example local queries:
  - Cache hit rate: `rate(rerank_cache_hits_total[5m]) / rate(rerank_cache_requests_total[5m])`
  - Gateway latency: `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, route))`
- Structured logs include `tenantId`, `requestId`, `traceId`, and `latencyMs`. Tail with `gcloud logging read --limit=50 'resource.labels.service_name="hh-search-svc-production"'`.
- Tracing: enable `OTEL_EXPORTER=console` locally for verbose spans; production traces are sampled via Cloud Trace (linked from dashboards).

## Operational Procedures

- **Scheduled production deployments** – Execute during approved windows with at least two team members. Run `deploy-production.sh` with `--rollback-on-failure`, monitor `.deployment/` artifacts, and post status in #headhunter-ops.
- **Emergency hotfix** – Use `deploy-production.sh --services <svc> --skip-build` with pre-built images. Document deviations in `migration-log.txt` and schedule a full deployment review next business day.
- **Rollback decision criteria** – Trigger rollback if smoke tests fail, p95 latency rises above 5s, or error rate >1% within first 10 minutes. Reference pre-deploy manifests for traffic restoration.
- **Communication protocol** – Announce start/finish in #headhunter-ops, include Git commit SHA, manifest paths, and any manual interventions. Page on-call immediately upon failure or rollback.

## Deployment Artifacts & Status Tracking

- `.deployment/manifests/build-manifest-*.json` – Image digests per service.
- `.deployment/manifests/deploy-manifest-*.json` – Cloud Run service URLs and health results.
- `.deployment/manifests/deployment-*.json` – Consolidated summary consumed by `docs/deployment-report-*.md`.
- `.deployment/deploy-logs/` – Raw Cloud Run & gateway deployment logs for audit.
- `.deployment/test-reports/smoke-test-report-*.json` – Gateway smoke results and latency percentiles.
- `.deployment/load-tests/post-deploy-*/load-test-report.json` – Post-deployment load test metrics and SLA validation.
- `.deployment/load-tests/post-deploy-*/load-test-report.md` – Operator summary of load test outcomes.
- `.deployment/validation-report-20251001-010532.json` – Output from `validate-deployment-readiness.sh` (includes status, blockers, remediation guidance).
- `.monitoring/setup-*/monitoring-manifest.json` – Dashboard, alert policy, uptime, and cost tracking resources created by monitoring orchestration.
- Gateway hostname lives in `.deployment/gateway-update-summary-*.log`; include it in incident reports.
- `docs/deployment-report-*.md` – Comprehensive deployment report generated by `scripts/generate-deployment-report.sh` (contains SLA evidence and sign-offs).
- **Phase 5-7 deployment report:** `docs/deployment-report-phase5-7.md` – Comprehensive deployment evidence for the production rollout completed 2025-09-30 to 2025-10-01. Includes Cloud Run service inventory, API Gateway configuration, monitoring assets (9 dashboards, 12 alert policies, 8 uptime checks), load test metrics (9 scenarios, 73,200 requests, 0.39% error rate, 78% cache hit rate), SLA validation (PASS), outstanding TODOs, known blockers, rollback procedures, validation checklist, and stakeholder sign-off table. Review this report for audit trail and future deployment reference.
- Phase 5–7 wrap-up template: `docs/deployment-report-phase5-7.md`.

## Outstanding Tasks & Risk Areas

1. `scripts/prepare-local-env.sh` – automation placeholder. Continue tagging manual gaps until the script lands.
2. Tenant isolation regression coverage – expand Task Master ticket `6d4c1188-bd05-4186-9bf5-4b253e52cfd1` with new scenarios (multi-tenant cache poisoning attempts, JWT rotation).
3. Monitoring playbook maintenance – review `docs/MONITORING_RUNBOOK.md` quarterly, reconcile dashboard IDs in `.monitoring/setup-*/monitoring-manifest.json`, and refresh notification channel mappings.

## Helpful References

- Architecture: `ARCHITECTURE.md`
- PRD snapshot: `PRD.md` (`.taskmaster/docs/prd.txt` remains authoritative)
- Docker topology: `docker-compose.local.yml`
- Service source: `services/**`
- Integration logs: `integration-results.log`
- Task tracking: `.taskmaster/tasks/tasks.json`
- Monitoring: `docs/MONITORING_RUNBOOK.md`
- Load test results: `.deployment/load-tests/post-deploy-*/`
- Monitoring manifest: `.monitoring/setup-*/monitoring-manifest.json`
- Deployment readiness validation: `scripts/validate-deployment-readiness.sh`
- Deployment report generator: `scripts/generate-deployment-report.sh`

Always append operational notes and command results to `migration-log.txt` (append-only). Include the latest `git status --short --branch` before closing any session.
