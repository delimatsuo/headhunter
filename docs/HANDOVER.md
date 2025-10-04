# Handover & Recovery Runbook (Updated 2025-10-03)

> Canonical repository path: `/Volumes/Extreme Pro/myprojects/headhunter`. Do **not** work from `/Users/delimatsuo/Documents/Coding/headhunter`.
> Guardrail: all automation wrappers under `scripts/` source `scripts/utils/repo_guard.sh` and exit immediately when invoked from non-canonical clones.

This runbook is the single source of truth for resuming work or restoring local parity with production. It reflects the Fastify microservice mesh that replaced the legacy Cloud Functions stack.

## 🚨 CRITICAL: Production Deployment Status (2025-10-03)

**CURRENT STATE: API GATEWAY ROUTING FIXED ✅**

All 8 Fastify services are **DEPLOYED AND HEALTHY** in production. API Gateway routing issue has been **RESOLVED**.

### Current Deployment Status

| Component | Status | Details |
|-----------|--------|---------|
| Fastify Services (8) | ✅ HEALTHY | All services deployed, passing health checks |
| Cloud Run Ingress | ✅ FIXED | All services now accept API Gateway traffic |
| Service Authentication | ✅ CONFIGURED | Gateway token support enabled on hh-embed-svc |
| Tenant Validation | ✅ FIXED | Code supports both Firebase and gateway JWTs |
| API Gateway Config | ✅ DEPLOYED | Config using correct managed service name |
| Gateway Routing | ✅ FIXED | All routes now reach backend services |
| Authenticated Routes | ⚠️ PARTIAL | Routes reach backends (need gateway token config) |

### Resolved Issue: API Gateway 404s (2025-10-03)

**Root Cause Identified and Fixed:**

The 404 errors were caused by **TWO separate issues**:

1. **OpenAPI Spec - Wrong Managed Service Name** ✅ FIXED
   - Problem: Spec used gateway hostname instead of managed service name
   - Impact: API Gateway couldn't validate API keys against correct service
   - Fix: Updated specs to use `${MANAGED_SERVICE_NAME}` placeholder
   - Deploy script now fetches and injects correct managed service name
   - Validation added to ensure correct injection

2. **Cloud Run Ingress Settings** ✅ FIXED
   - Problem: Services had `ingress: internal-and-cloud-load-balancing`
   - Impact: API Gateway (ESPv2) traffic was blocked at infrastructure level
   - Fix: Changed all services to `ingress: all`
   - Security: IAM `roles/run.invoker` still enforced

**Evidence:**
- Before fix: Authenticated routes → 404 "Page not found"
- After fix: Authenticated routes → 401 "Invalid gateway token" (reaches backend)
- Health endpoint: Always worked (routes to hh-admin-svc with `ingress: all`)

### Recent Completions (2025-10-03)

1. **✅ API Gateway Routing Fix** (Commit: 565861b)
   - Updated OpenAPI specs with managed service name placeholder
   - Enhanced deploy script with managed service name resolution
   - Added validation for Swagger 2.0 and OpenAPI 3.0 specs
   - Fixed Cloud Run ingress settings for all 7 affected services
   - Deployed config: `gateway-config-20251003-195253`

2. **✅ Tenant Validation Fix** (Commit: 67c1090)
   - Modified `services/common/src/tenant.ts:77-89`
   - Supports gateway-issued JWTs without `orgId` claims
   - For Firebase tokens: validates `orgId` matches `X-Tenant-ID` (existing behavior)
   - For gateway tokens: trusts `X-Tenant-ID` since API Gateway validated API key
   - Code built, tested, committed, and pushed to main

3. **✅ hh-embed-svc Gateway Token Configuration**
   - Revision: `hh-embed-svc-production-00032-x97` (100% traffic)
   - Environment variables:
     ```
     ENABLE_GATEWAY_TOKENS=true
     AUTH_MODE=hybrid
     GATEWAY_AUDIENCE=https://hh-embed-svc-production-akcoqbr7sa-uc.a.run.app
     ALLOWED_TOKEN_ISSUERS=gateway-production@headhunter-ai-0088.iam.gserviceaccount.com/
     ISSUER_CONFIGS=gateway-production@headhunter-ai-0088.iam.gserviceaccount.com|https://www.googleapis.com/service_accounts/v1/jwk/gateway-production@headhunter-ai-0088.iam.gserviceaccount.com
     ```

### Next Operator Actions

**Priority 1: Configure Gateway Tokens on Remaining Services**

All services now receive API Gateway requests but need gateway token authentication:
- hh-search-svc
- hh-rerank-svc
- hh-evidence-svc
- hh-eco-svc
- hh-msgs-svc
- hh-admin-svc
- hh-enrich-svc

For each service, deploy with these environment variables:
```bash
ENABLE_GATEWAY_TOKENS=true
AUTH_MODE=hybrid
GATEWAY_AUDIENCE=https://{service-name}-production-akcoqbr7sa-uc.a.run.app
ALLOWED_TOKEN_ISSUERS=gateway-production@headhunter-ai-0088.iam.gserviceaccount.com/
ISSUER_CONFIGS=gateway-production@headhunter-ai-0088.iam.gserviceaccount.com|https://www.googleapis.com/service_accounts/v1/jwk/gateway-production@headhunter-ai-0088.iam.gserviceaccount.com
```

**Priority 2: Run End-to-End Tests**
- Execute: `./scripts/comprehensive_smoke_test.sh`
- Generate embeddings for test candidates
- Validate search pipeline: embed → search → rerank → evidence

### Key Files for Investigation

**OpenAPI Specs:**
- Source: `/Volumes/Extreme Pro/myprojects/headhunter/docs/openapi/gateway.yaml`
- Merged: `/tmp/gateway-merged.yaml` (created 2025-10-03)
- Common schemas: `/Volumes/Extreme Pro/myprojects/headhunter/docs/openapi/schemas/common.yaml`

**Deployment Scripts:**
- Gateway deploy: `./scripts/deploy_api_gateway.sh`
- Gateway update: `./scripts/update-gateway-routes.sh`
- Service deploy: `./scripts/deploy-cloud-run-services.sh`
- Build images: `./scripts/build-and-push-services.sh`

**Critical Code:**
- Tenant validation: `services/common/src/tenant.ts:65-101`
- Auth plugin: `services/common/src/auth.ts:76-144`
- Service routes: `services/hh-embed-svc/src/routes.ts:22-137`

**Deployment Artifacts:**
- Build manifest: `.deployment/manifests/build-manifest-20251003-221111.json`
- Deploy manifest: `.deployment/manifests/deploy-manifest-20251003-222005.json`

### GCP Resources

**Project:** headhunter-ai-0088
**Region:** us-central1

**Cloud Run Services (all HEALTHY):**
```
hh-embed-svc-production    https://hh-embed-svc-production-akcoqbr7sa-uc.a.run.app
hh-search-svc-production   https://hh-search-svc-production-akcoqbr7sa-uc.a.run.app
hh-rerank-svc-production   https://hh-rerank-svc-production-akcoqbr7sa-uc.a.run.app
hh-evidence-svc-production https://hh-evidence-svc-production-akcoqbr7sa-uc.a.run.app
hh-eco-svc-production      https://hh-eco-svc-production-akcoqbr7sa-uc.a.run.app
hh-msgs-svc-production     https://hh-msgs-svc-production-akcoqbr7sa-uc.a.run.app
hh-admin-svc-production    https://hh-admin-svc-production-akcoqbr7sa-uc.a.run.app
hh-enrich-svc-production   https://hh-enrich-svc-production-akcoqbr7sa-uc.a.run.app
```

**API Gateway:**
- Gateway: `headhunter-api-gateway-production`
- URL: `https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev`
- Active Config: `gateway-config-20251003-231022`
- Service Account: `gateway-production@headhunter-ai-0088.iam.gserviceaccount.com`

**Test Tenant:**
- Tenant ID: `test-tenant`
- Firestore collection: `organizations/test-tenant`
- Test candidates: 6 profiles in Firestore

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
   Must pass:
   - `cacheHitRate=1.0` (from `hh-rerank-svc`)
   - Rerank latency ≈ 0 ms (sub-millisecond)

---

## Architecture Overview

### Service Mesh (8 Fastify Services, Ports 7101-7108)

| Service | Port | Primary Responsibilities |
|---------|------|-------------------------|
| `hh-embed-svc` | 7101 | Normalizes profiles, requests embedding jobs, hands off to enrichment |
| `hh-search-svc` | 7102 | Multi-tenant search, pgvector recalls with deterministic filters, rerank orchestration |
| `hh-rerank-svc` | 7103 | Redis-backed scoring caches, enforces `cacheHitRate=1.0` baseline |
| `hh-evidence-svc` | 7104 | Provenance artifacts and evidence APIs |
| `hh-eco-svc` | 7105 | ECO data pipelines, occupation normalization, templates |
| `hh-msgs-svc` | 7106 | Notifications, queue fan-out, Pub/Sub bridging |
| `hh-admin-svc` | 7107 | Scheduler, tenant onboarding, policy enforcement |
| `hh-enrich-svc` | 7108 | Long-running enrichment, calls Python workers via bind-mounted `scripts/` |

### Shared Infrastructure (docker-compose.local.yml)

- **Postgres** (`ankane/pgvector:v0.5.1`) - master store for search, embeddings, transactional data
- **Redis** (`redis:7-alpine`) - request cache, idempotency locks, rerank scoring
- **Firestore emulator** - candidate profiles, operational data
- **Pub/Sub emulator** - scheduler topics, async messaging
- **Mock OAuth** - JWT issuance for local development
- **Mock Together AI** - LLM API contract emulation
- **Python worker** (`python:3.11-slim`) - bind-mounted `scripts/` for enrichment pipelines

---

## Production Stack

**AI Processing:** Together AI (meta-llama/Llama-3.1-8B-Instruct-Turbo)
**Embeddings:** Vertex AI text-embedding-004 OR Together AI
**Storage:** Firestore (profiles), Cloud SQL + pgvector (search, embeddings)
**Cache:** Redis (Memorystore)
**API:** Fastify services on Cloud Run
**Messaging:** Pub/Sub + Cloud Scheduler
**Secrets:** Secret Manager
**Monitoring:** Cloud Monitoring, custom dashboards, alert policies

---

## Key Documentation

- **`ARCHITECTURE.md`** - Detailed architecture, dependency graph, bootstrap context
- **`README.md`** - Quick start, infrastructure provisioning, deployment workflow
- **`docs/HANDOVER.md`** - This file - operator runbook, recovery procedures
- **`docs/TDD_PROTOCOL.md`** - Test-driven development guidelines
- **`docs/PRODUCTION_DEPLOYMENT_GUIDE.md`** - End-to-end deployment runbook
- **`docs/MONITORING_RUNBOOK.md`** - Monitoring and alerting operations
- **`docs/gcp-infrastructure-setup.md`** - Infrastructure provisioning checklist
- **`.taskmaster/docs/prd.txt`** - Authoritative PRD
- **`.taskmaster/CLAUDE.md`** - Task Master commands and workflows

---

## Troubleshooting: API Gateway 404 Issue

### Symptoms
- Gateway returns HTML 404 for all authenticated routes
- `/health` endpoint works (unauthenticated)
- No requests reach backend services
- All services are healthy and properly configured

### Debug Commands
```bash
# Check gateway status
gcloud api-gateway gateways describe headhunter-api-gateway-production \
  --location=us-central1 --project=headhunter-ai-0088

# List API configs
gcloud api-gateway api-configs list \
  --api=headhunter-api-gateway-production --project=headhunter-ai-0088

# Test endpoints
API_KEY=$(gcloud secrets versions access latest --secret=api-gateway-key --project=headhunter-ai-0088)

# This works (no auth):
curl -s https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/health

# This fails with 404 (requires API key):
curl -s -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-ID: test-tenant" \
  -H "Content-Type: application/json" \
  -d '{"text":"test"}' \
  https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/embeddings/generate

# Check service logs for requests
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=hh-embed-svc-production AND \
  httpRequest.requestUrl=~\"embeddings\"" \
  --limit=10 --project=headhunter-ai-0088
```

### Investigation Steps
1. Compare OpenAPI config for `/health` (works) vs `/v1/embeddings/generate` (fails)
2. Check API Gateway managed service logs for routing errors
3. Verify `securityDefinitions` and `security` are properly configured
4. Test if issue is specific to routes with API key requirement
5. Check if there's a config version mismatch between gateway and API

---

## Emergency Contact Protocol

If this session fails or you need to handover:
1. **Current blocker**: API Gateway routing issue - all authenticated routes return 404
2. **Technical solution complete**: Tenant validation code supports gateway tokens (commit 67c1090)
3. **Configuration ready**: hh-embed-svc has gateway token authentication enabled
4. **Needs investigation**: Why API Gateway routes with `security: [TenantApiKey]` fail while unauthenticated routes work
5. **Next operator**: Start with API Gateway routing diagnosis using specialized agent
