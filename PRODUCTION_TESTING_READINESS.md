# Production Testing Readiness Checklist

**Date**: October 3, 2025
**Project**: Headhunter AI v2.0 MVP
**Environment**: headhunter-ai-0088 (us-central1)

---

## Current Status Summary

### ✅ Infrastructure Ready
- [✅] All 8 Cloud Run services deployed and running
- [✅] Cloud SQL (PostgreSQL + pgvector) operational
- [✅] Redis Memorystore operational
- [✅] Firestore configured
- [✅] Pub/Sub topics created
- [✅] API Gateway routing functional
- [✅] VPC networking configured
- [✅] Secret Manager configured

### ⚠️ Services Reporting Unhealthy
**Issue**: Services return 503 "unhealthy" status due to failed health checks:
```json
{"status":"unhealthy","checks":{"pubsub":false,"jobs":false,"monitoring":{"healthy":true,"optional":false}}}
```

**Root Cause**: Background dependency initialization hasn't completed yet OR dependencies not properly configured.

---

## Blockers for Production Testing

### 🚨 HIGH PRIORITY (Must Fix Before Testing)

#### 1. Service Health Issues
**Problem**: Pub/Sub and Jobs health checks failing

**Investigation Needed**:
```bash
# Check service logs for initialization errors
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=hh-admin-svc-production" \
  --limit=50 --format=json --project=headhunter-ai-0088 | jq '.[] | select(.severity=="ERROR")'

# Check Pub/Sub subscription status
gcloud pubsub subscriptions describe profiles.refresh.request.sub \
  --project=headhunter-ai-0088

# Check if Cloud Run Jobs exist
gcloud run jobs list --region=us-central1 --project=headhunter-ai-0088
```

**Likely Causes**:
- Cloud Run Jobs not created (admin service expects them)
- Pub/Sub subscriptions not created
- Service account permissions missing for Pub/Sub/Jobs
- Environment variables not set correctly

**Action**: Debug and fix service health checks before proceeding

#### 2. Authentication Not Configured
**Problem**: No authentication mechanism for external API access

**Current State**:
- Gateway has `TenantApiKey` security definition
- No actual API keys provisioned
- OAuth2 client credentials not configured

**Required**:
```bash
# Option A: Create API keys for testing
gcloud api-keys create headhunter-test-key \
  --display-name="Production Test Key" \
  --api-target=service=headhunter-api-gateway-production \
  --project=headhunter-ai-0088

# Option B: Configure OAuth2 (requires OAuth provider)
# See: config/security/oauth2-setup.md
```

**Action**: Set up at least one authentication method

#### 3. No Test Data in Production
**Problem**: Empty database - cannot test search without candidates

**Required**:
- Load sample candidate data (anonymized/synthetic)
- Verify embeddings generated
- Test search index populated

**Scripts Available**:
```bash
# Upload test candidates to Firestore
python3 scripts/upload_to_firestore.py \
  --project-id headhunter-ai-0088 \
  --collection candidates \
  --data-file datasets/test_candidates.json

# Generate embeddings for test data
# (requires Together AI or Vertex AI credentials)
python3 scripts/generate_embeddings.py \
  --project-id headhunter-ai-0088
```

**Action**: Load test dataset before testing search functionality

---

## Pre-Testing Setup Steps

### Step 1: Fix Service Health (CRITICAL)

**1.1 Check Service Logs**
```bash
# Admin service logs
gcloud run services logs read hh-admin-svc-production \
  --region=us-central1 \
  --project=headhunter-ai-0088 \
  --limit=100

# Look for errors related to:
# - Pub/Sub client initialization
# - Jobs client initialization
# - Database connections
```

**1.2 Verify Pub/Sub Configuration**
```bash
# Check subscriptions exist
gcloud pubsub subscriptions list --project=headhunter-ai-0088

# If missing, create them:
./scripts/setup_pubsub_headhunter.sh --project-id headhunter-ai-0088
```

**1.3 Verify Cloud Run Jobs**
```bash
# Check if jobs exist
gcloud run jobs list --region=us-central1 --project=headhunter-ai-0088

# Expected jobs:
# - postings-refresh-job
# - profiles-refresh-job

# If missing, deployment scripts need to be run
```

**1.4 Check Service Account Permissions**
```bash
# Admin service account should have:
# - roles/pubsub.publisher
# - roles/run.invoker (for jobs)
# - roles/cloudsql.client
# - roles/secretmanager.secretAccessor

gcloud projects get-iam-policy headhunter-ai-0088 \
  --flatten="bindings[].members" \
  --filter="bindings.members:admin-production@headhunter-ai-0088.iam.gserviceaccount.com"
```

### Step 2: Configure Authentication

**2.1 Create Test API Key**
```bash
# Create API key for testing
gcloud alpha services api-keys create \
  --display-name="Production Test Key" \
  --project=headhunter-ai-0088

# Get the key value
gcloud alpha services api-keys list --project=headhunter-ai-0088

# Update OpenAPI spec if needed to use API keys
```

**2.2 Test Authenticated Request**
```bash
# With API key
curl https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/health \
  -H "X-API-Key: YOUR_API_KEY"

# Or with JWT (service-to-service)
curl https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/health \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

### Step 3: Load Test Data

**3.1 Create Test Dataset**
```bash
# Generate synthetic candidate data
python3 scripts/create_sample_candidate_data.py \
  --count=50 \
  --output datasets/test_candidates_production.json

# OR use existing test data (anonymized)
# Verify no PII in test dataset
```

**3.2 Upload to Firestore**
```bash
python3 scripts/upload_to_firestore.py \
  --project-id headhunter-ai-0088 \
  --environment production \
  --collection candidates \
  --data-file datasets/test_candidates_production.json
```

**3.3 Generate Embeddings**
```bash
# Set Together AI API key if not already in Secret Manager
export TOGETHER_API_KEY="your-api-key"

# Generate embeddings for test candidates
python3 scripts/generate_embeddings.py \
  --project-id headhunter-ai-0088 \
  --collection candidates \
  --batch-size 10
```

**3.4 Verify Data Loaded**
```bash
# Check Firestore
gcloud firestore databases describe --database=(default) --project=headhunter-ai-0088

# Check pgvector (requires Cloud SQL proxy or connection)
# psql -h 10.159.0.2 -U embed_writer -d headhunter -c "SELECT COUNT(*) FROM embeddings;"
```

### Step 4: Run Smoke Tests

**4.1 Health Check All Services**
```bash
# Run comprehensive health check
./scripts/validate-all-services-health.sh \
  --project-id headhunter-ai-0088 \
  --environment production
```

**4.2 Test Critical Endpoints**
```bash
# 1. Embeddings generation
curl -X POST https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/embeddings/generate \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Senior software engineer with 10 years Python experience"}'

# 2. Search endpoint
curl -X POST https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/search \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "Python engineer", "limit": 10}'

# 3. Admin snapshot
curl https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/admin/snapshots \
  -H "X-API-Key: YOUR_API_KEY"
```

---

## Production Testing Plan

### Phase 1: Functional Testing (MVP Acceptance Criteria)

**Test Case 1: End-to-End Search Flow**
```
Given: Job description in English or Portuguese
When: Submit search via /v1/search endpoint
Then: Returns top-20 candidates with:
  - Candidate name, seniority, experience
  - Match score and ranking
  - "Why match" evidence bullets
  - LinkedIn URL (if available)
  - Compliance fields (legal_basis, consent_record)
```

**Test Case 2: Embedding Generation**
```
Given: Candidate profile text
When: Call /v1/embeddings/generate
Then: Returns embedding vector
  - Dimension matches model (1536 for text-embedding-004)
  - Vector normalized (cosine similarity ready)
```

**Test Case 3: Rerank Performance**
```
Given: 200 candidate results from hybrid search
When: Rerank via Together AI
Then: Returns top-20 in ≤350ms (p95)
  - Cache hit rate ≥98%
  - Results properly scored
```

**Test Case 4: Data Privacy Compliance**
```
Given: Candidate profile
When: Query via search
Then: Response includes:
  - legal_basis field (legitimate_interest, consent, etc.)
  - consent_record (if applicable)
  - transfer_mechanism (if cross-border)
  - Exportable processing register available
```

### Phase 2: Performance Testing

**Latency Requirements** (from PRD):
- Search p95 ≤ 1.2s
- Rerank ≤ 350ms @ K≤200
- Cache hit rate ≥98%

**Load Test**:
```bash
# Run production load test
./scripts/run-post-deployment-load-tests.sh \
  --gateway-endpoint https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev \
  --tenant-id ella-executive-search \
  --duration 300s \
  --rps 10
```

**Metrics to Capture**:
- Request latency (p50, p95, p99)
- Error rate
- Cache hit rate
- Database connection pool usage
- Memory/CPU utilization

### Phase 3: Integration Testing

**Test Scenarios**:
1. Upload candidate → Process → Embed → Search → Rerank
2. Admin refresh flow (postings, profiles)
3. Monitoring and alerting (trigger test alert)
4. Error handling (malformed input, timeouts)
5. Multi-tenant isolation (if applicable)

---

## Monitoring During Testing

### Key Metrics to Watch

```bash
# View service metrics
gcloud monitoring time-series list \
  --filter='resource.type="cloud_run_revision"' \
  --project=headhunter-ai-0088

# Critical metrics:
# - request_count (throughput)
# - request_latencies (p95, p99)
# - billable_instance_time (cost)
# - container/cpu/utilizations (performance)
# - container/memory/utilizations (resource usage)
```

### Log Monitoring

```bash
# Real-time error tracking
gcloud logging tail "resource.type=cloud_run_revision severity>=ERROR" \
  --project=headhunter-ai-0088

# Search for specific errors
gcloud logging read "resource.type=cloud_run_revision jsonPayload.error=~'timeout'" \
  --limit=20 --project=headhunter-ai-0088
```

---

## Rollback Plan

If critical issues are discovered during testing:

```bash
# 1. Stop incoming traffic (if needed)
# Update API Gateway to return maintenance mode

# 2. Roll back specific service
gcloud run services update-traffic SERVICE_NAME \
  --to-revisions=PREVIOUS_REVISION=100 \
  --region=us-central1 \
  --project=headhunter-ai-0088

# 3. Check previous revision numbers
cat .deployment/manifests/pre-deploy-revisions-*.json

# 4. Full rollback using deployment manifest
./scripts/rollback_production_deployment.sh \
  --manifest .deployment/manifests/pre-deploy-revisions-20251003-*.json
```

---

## Success Criteria

Testing can be considered successful when:

- [ ] **All services healthy**: No "unhealthy" status responses
- [ ] **Authentication working**: Can make authenticated requests via gateway
- [ ] **End-to-end search works**: JD → candidates with evidence
- [ ] **Performance meets SLOs**: p95 ≤ 1.2s, rerank ≤ 350ms
- [ ] **Cache functioning**: Hit rate ≥98%
- [ ] **No critical errors**: Zero ERROR-level logs under normal load
- [ ] **Data privacy compliance**: All required fields present
- [ ] **Monitoring operational**: Dashboards show live metrics

---

## Current Blockers Summary

### Must Fix Before Testing

1. **Service Health Failures** 🚨
   - Pub/Sub initialization failing
   - Jobs client initialization failing
   - Need to debug service logs and fix configuration

2. **No Authentication Configured** 🚨
   - Cannot make authenticated requests
   - Need API keys or OAuth setup

3. **No Test Data Loaded** ⚠️
   - Empty database
   - Cannot test search without candidates

### Nice to Have (Can Test Without)

4. **Monitoring dashboards** (can test without, manual monitoring via logs)
5. **Alert policies** (can test without, manual incident detection)
6. **Full CI/CD pipeline** (can deploy manually for testing)

---

## Immediate Next Steps

1. **Debug service health** (30-60 min)
   - Check logs for all services
   - Verify Pub/Sub subscriptions created
   - Verify Cloud Run Jobs created
   - Fix IAM permissions if needed

2. **Set up authentication** (15-30 min)
   - Create test API key
   - Update gateway config if needed
   - Test authenticated request

3. **Load test data** (30-60 min)
   - Generate or obtain test dataset
   - Upload to Firestore
   - Generate embeddings
   - Verify data accessible

4. **Run smoke tests** (15 min)
   - Test each critical endpoint
   - Verify responses
   - Check for errors

**Total Estimated Time**: 2-3 hours to ready for production testing

---

## Related Documentation

- `SUCCESS_STATUS.md` - Current deployment status
- `CURRENT_STATUS.md` - System health and next actions
- `PRODUCTION_MONITORING_SETUP.md` - Monitoring configuration
- `AUDIT_REPORT.md` - Security and quality audit
- `.taskmaster/docs/prd.txt` - MVP requirements and acceptance criteria

---

**Created**: October 3, 2025
**Owner**: Engineering Team
**Priority**: HIGH - Blocking production testing
