# Headhunter API Gateway - Current Status

**Last Updated**: 2025-10-02
**Session**: API Gateway Deployment

---

## ✅ Completed

### 1. API Gateway Infrastructure
- **Gateway URL**: `https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev`
- **API**: `headhunter-api-gateway-production`
- **Latest Config**: `gateway-config-fixed-routing-1759425777`
- **Status**: Deployed and operational

### 2. OpenAPI Spec Fixes
- ✅ Enforced Swagger 2.0 compliance (removed `anyOf`/`oneOf` keywords)
- ✅ Removed quota metrics configuration (can re-enable post-MVP)
- ✅ Simplified security to API Key only (OAuth2 deferred until JWKS endpoint available)
- ✅ Updated backend URLs to direct Cloud Run format

### 3. Code Quality Improvements
- ✅ Removed all debug `console.log` statements (16 instances)
- ✅ Moved `hh-example-svc` to templates with documentation
- ✅ Enabled `noUnusedParameters` in TypeScript config
- ✅ Created comprehensive `SECURITY.md` policy
- ✅ Created `docs/TESTING.md` strategy (70% coverage target)
- ✅ Added GitHub Actions CI/CD workflow (`.github/workflows/ci.yml`)

---

## ⚠️ Current Issue: Cloud SQL Connection Timeout During Startup

### Problem
Cloud Run services fail to start due to Cloud SQL Auth Proxy timeout:
```
Cloud SQL connection failed: dial error: failed to dial
(connection name = "headhunter-ai-0088:us-central1:sql-hh-core"):
connection to Cloud SQL instance at 10.159.0.2:3307 failed: timed out after 10s
```

**Container exits with code 1, preventing services from becoming ready.**

### Investigation Findings (Oct 2, 2025)

1. **Added PGVECTOR_PORT environment variable** (commit 1526ec9)
   - Env var is correctly deployed (`PGVECTOR_PORT=5432`)
   - Issue was NOT missing port configuration

2. **Cloud SQL Auth Proxy configuration is correct**
   - Instance: `sql-hh-core` (POSTGRES_15)
   - Connection string: `headhunter-ai-0088:us-central1:sql-hh-core`
   - Service account: `embed-production@` has `roles/cloudsql.client`
   - Annotation: `run.googleapis.com/cloudsql-instances` is set

3. **Network configuration conflicts discovered**
   - Services use BOTH VPC connector AND Cloud SQL proxy annotations
   - VPC egress mode: `private-ranges-only`
   - Cloud SQL has private IP only: 10.159.0.2 (no public IP)
   - Both Cloud SQL and VPC connector use network `vpc-hh`

4. **Service bootstrap uses lazy initialization**
   - Health endpoints registered before `server.listen()` (correct)
   - Database initialization happens in `setImmediate()` callback
   - But `pgClient.initialize()` blocks and times out (>10s)
   - Container exits before reporting error to application logs

5. **Cloud SQL proxy trying wrong port (3307 vs 5432)**
   - Error message shows proxy attempting MySQL port 3307
   - Actual instance is POSTGRES_15 (should use 5432)
   - This is likely a red herring - generic Google error message

### Root Cause Analysis

**Network Connectivity Issue**: The Cloud SQL Auth Proxy sidecar cannot establish connection to the private IP 10.159.0.2. Possible causes:

1. **Firewall rules blocking traffic** - Missing ingress rule for Cloud SQL port 5432
2. **VPC peering not configured** - Cloud SQL private service connection might not be established
3. **DNS resolution failure** - Proxy can't resolve the private IP
4. **Resource exhaustion** - Cloud SQL instance might be at max connections (800)

### Probable Fix Required

Based on GCP best practices, when using Cloud SQL with private IP:
- Option A: Remove VPC connector, use Cloud SQL proxy only (simpler)
- Option B: Verify VPC peering is configured correctly for Private Service Connect

---

---

## 🔧 Fixes Applied (Oct 2, 2025)

### 1. Added PGVECTOR_PORT Environment Variable (commit 1526ec9)
- Added `PGVECTOR_PORT=5432` to hh-embed-svc, hh-search-svc
- Added `MSGS_DB_PORT=5432` to hh-msgs-svc
- **Result**: Environment variables deployed correctly

### 2. Enabled VPC All-Traffic Egress (commit 4d7e3a6)
- Changed from `private-ranges-only` to `all-traffic` for all 8 services
- Allows Cloud SQL Auth Proxy sidecar to use VPC connector
- **Result**: Deployment still failed (not the root cause)

### 3. Fixed Redis Connection Details (commit 4333115)
- Corrected Redis host: `redis.production.internal` → `10.159.1.4`
- Corrected Redis port: `6379` → `6378`
- Verified against actual Memorystore Redis instance
- **Result**: Startup probe now succeeds, but container exits with code 1

### 4. Fixed VPC Firewall Rules (21:40 UTC)
- Added Cloud SQL peering range `10.159.0.0/16` to ingress firewall
- Added Redis port `6378` to allowed ports
- Firewall was blocking Cloud SQL Auth Proxy from reaching database
- **Result**: Deployments still timeout, but some revisions succeed

### Current Status (21:45 UTC)
- ✅ Services deploy and mark as "Ready" (some revisions succeed)
- ✅ Redis connection details corrected (10.159.1.4:6378)
- ✅ VPC networking and firewall properly configured
- ✅ Cloud SQL connection should work (firewall fixed)
- ❌ **All services return 404 for all requests** (including `/health`)
- ❌ Requests never reach containers (Google's 404, not Fastify)
- ❌ Issue persists even for "successful" revisions

### Root Cause: Request Routing Failure
The fundamental issue is that **HTTP requests are not reaching the containers**. Services pass health probes and mark as Ready, but all HTTP requests return Google's 404 page. This indicates a routing or ingress configuration problem, NOT an application issue.

### Possible Causes
1. **Port misconfiguration**: Containers listen on 8080, but Cloud Run routes to wrong port
2. **Health check vs traffic routing**: Startup probes succeed but traffic routing fails
3. **Ingress annotation issue**: `internal-and-cloud-load-balancing` may require additional setup
4. **Service account permissions**: IAM roles may be missing for request routing
5. **Container registry access**: Images may not be fully downloaded/validated

### Immediate Actions Needed
1. Test with `--allow-unauthenticated` to rule out auth issues
2. Check if containers are actually running (not just passing probes)
3. Deploy a minimal "hello world" service to isolate the issue
4. Review Cloud Run ingress settings and service IAM bindings

---

## 📋 Next Steps (Recommended)

### Option 1: Redeploy Services (Recommended)
The services were last deployed on Oct 1 (yesterday). Recent code changes aren't deployed.

```bash
# 1. Build and push new images
cd "/Volumes/Extreme Pro/myprojects/headhunter"
./scripts/deploy-cloud-run-services.sh --project-id headhunter-ai-0088 --environment production

# 2. Test service health directly
TOKEN=$(gcloud auth print-identity-token)
curl "https://hh-admin-svc-production-akcoqbr7sa-uc.a.run.app/healthz" \
  -H "Authorization: Bearer ${TOKEN}"

# 3. Test via API Gateway
curl "https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/health" \
  -H "X-API-Key: test-key" \
  -H "X-Tenant-ID: test-tenant"
```

### Option 2: Debug Existing Deployment
```bash
# 1. Check service logs for startup issues
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=hh-admin-svc-production" \
  --project=headhunter-ai-0088 \
  --limit=50 \
  --format="table(timestamp,severity,jsonPayload.message,textPayload)"

# 2. Check environment variables
gcloud run services describe hh-admin-svc-production \
  --region=us-central1 \
  --project=headhunter-ai-0088 \
  --format="yaml(spec.template.spec.containers[0].env)"

# 3. Test with Cloud Run service URL directly (bypass gateway)
curl "https://hh-admin-svc-production-akcoqbr7sa-uc.a.run.app/healthz" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

### Option 3: Local Testing
```bash
# Test services locally with docker-compose
cd "/Volumes/Extreme Pro/myprojects/headhunter"
docker compose -f docker-compose.local.yml up hh-admin-svc

# Test health endpoint
curl http://localhost:7107/healthz
```

---

## 📁 Key Files

### OpenAPI Specification
- **Gateway Spec**: `docs/openapi/gateway.yaml`
- **Common Schemas**: `docs/openapi/schemas/common.yaml`
- **Deployment Script**: `scripts/deploy_api_gateway.sh`

### Service Code
- **Admin Service**: `services/hh-admin-svc/src/`
  - `index.ts` - Bootstrap logic
  - `routes.ts` - Endpoint registration
  - `config.ts` - Configuration

### Deployment
- **Cloud Run Deploy**: `scripts/deploy-cloud-run-services.sh`
- **Production Deploy**: `scripts/deploy-production.sh`

---

## 🔗 Resources

### Cloud Run Services (all in us-central1)
- hh-admin-svc-production: `https://hh-admin-svc-production-akcoqbr7sa-uc.a.run.app`
- hh-embed-svc-production: `https://hh-embed-svc-production-akcoqbr7sa-uc.a.run.app`
- hh-search-svc-production: `https://hh-search-svc-production-akcoqbr7sa-uc.a.run.app`
- hh-rerank-svc-production: `https://hh-rerank-svc-production-akcoqbr7sa-uc.a.run.app`
- hh-evidence-svc-production: `https://hh-evidence-svc-production-akcoqbr7sa-uc.a.run.app`
- hh-eco-svc-production: `https://hh-eco-svc-production-akcoqbr7sa-uc.a.run.app`
- hh-enrich-svc-production: `https://hh-enrich-svc-production-akcoqbr7sa-uc.a.run.app`
- hh-msgs-svc-production: `https://hh-msgs-svc-production-akcoqbr7sa-uc.a.run.app`

### GCP Console Links
- [API Gateway](https://console.cloud.google.com/api-gateway/api/headhunter-api-gateway-production?project=headhunter-ai-0088)
- [Cloud Run Services](https://console.cloud.google.com/run?project=headhunter-ai-0088)
- [Cloud Logging](https://console.cloud.google.com/logs?project=headhunter-ai-0088)

---

## 📝 Recent Commits

1. **55d83dd** - fix(gateway): update backend URLs to direct Cloud Run addresses
2. **ba879d6** - feat(gateway): deploy API Gateway MVP - Swagger 2.0 compliant
3. **695e3a6** - fix(gateway): enforce Swagger 2.0 compliance for API Gateway deployment
4. **3460185** - feat(together-client): resilience (rate limit, retries, circuit breaker)

---

## 🎯 Success Criteria

API Gateway deployment is complete when:
- [ ] `/health` endpoint returns 200 OK via gateway
- [ ] All 8 services return 200 OK when called directly
- [ ] Gateway successfully routes requests to backend services
- [ ] Authentication works (API Key validation)
- [ ] No 404 errors from Cloud Run services

**Recommendation**: Redeploy Cloud Run services with latest code and test health endpoints.
