# Task 84: Rerank Service Integration Fix

**Date**: 2025-10-09
**Service**: hh-search-svc-production
**Issue**: Rerank service not triggering during hybrid searches (rankingMs consistently 0ms)

## Root Cause

Missing environment variable: `RERANK_SERVICE_AUDIENCE`

### Analysis

The rerank service integration requires three configuration elements:
1. `RERANK_SERVICE_URL` - URL of the rerank service ✅ (was present)
2. `ENABLE_RERANK` - Feature flag to enable rerank ✅ (was present, set to true)
3. `RERANK_SERVICE_AUDIENCE` - Audience for Cloud Run service-to-service authentication ❌ **(was missing)**

The missing `RERANK_SERVICE_AUDIENCE` environment variable prevented the RerankClient from properly authenticating with the hh-rerank-svc Cloud Run service. While the embed service had its corresponding `EMBED_SERVICE_AUDIENCE` variable configured, the rerank service configuration was incomplete.

### Code Path

In `search-service.ts`, the `applyRerankIfEnabled()` method (lines 364-414) checks:
```typescript
if (!this.config.rerank.enabled || !this.rerankClient || !this.rerankClient.isEnabled()) {
  return null;
}
```

The rerank client initialization in `index.ts` (lines 104-110) creates the client but without proper authentication configuration, resulting in silent failures.

## Solution

Added `RERANK_SERVICE_AUDIENCE` environment variable to the hh-search-svc Cloud Run configuration.

### Changes Made

**File**: `config/cloud-run/hh-search-svc.yaml`

Added environment variable after line 88:
```yaml
- name: RERANK_SERVICE_URL
  value: https://hh-rerank-svc-${SERVICE_ENVIRONMENT}-akcoqbr7sa-uc.a.run.app
- name: RERANK_SERVICE_AUDIENCE
  value: https://hh-rerank-svc-${SERVICE_ENVIRONMENT}-akcoqbr7sa-uc.a.run.app
```

### Deployment

**Revision**: hh-search-svc-production-00054-b6v
**Deployed**: 2025-10-09 13:01 UTC
**Status**: ✅ Healthy and serving 100% traffic

**Verified Environment Variables**:
```bash
RERANK_SERVICE_URL=https://hh-rerank-svc-production-akcoqbr7sa-uc.a.run.app
RERANK_SERVICE_AUDIENCE=https://hh-rerank-svc-production-akcoqbr7sa-uc.a.run.app
ENABLE_RERANK=true
```

## Validation Plan

To validate the fix, execute hybrid search queries via API Gateway and verify:

1. **Rerank timing is non-zero**: `timings.rankingMs > 0`
2. **Results include rerank metadata**: Check for rerank-specific fields
3. **Logs show rerank activity**: Look for "Rerank request completed" messages

### Test Command

```bash
# Get API key
API_KEY=$(gcloud secrets versions access latest --secret="gateway-api-key-tenant-alpha" --project=headhunter-ai-0088)

# Execute hybrid search
curl -X POST \
  "https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/search/hybrid" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenant-alpha" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "jobDescription": "Senior software engineer with Python and AWS",
    "limit": 5
  }' | jq '.timings.rankingMs'
```

**Expected Result**: Non-zero ranking time (previously 0ms)

### Log Query

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND
   resource.labels.service_name="hh-search-svc-production" AND
   resource.labels.revision_name="hh-search-svc-production-00054-b6v" AND
   (jsonPayload.message=~"Rerank" OR jsonPayload.message=~"rerank")' \
  --project headhunter-ai-0088 \
  --limit 20
```

**Expected**: Log entries showing "Rerank request completed" with latency measurements

## Impact

**Before Fix**:
- Rerank service never invoked
- Results ordered by vector similarity + text score only
- No match quality refinement
- rankingMs = 0ms consistently

**After Fix**:
- Rerank service should be invoked for eligible queries
- Top-K candidates re-scored by Together AI reranker
- Improved result relevance for job-candidate matching
- rankingMs should show rerank latency (target: <350ms per Task 84 requirements)

## Related Tasks

- **Task 80**: Hybrid Search Validation (identified this issue)
- **Task 83**: Cold Start Latency Fix (pending)
- **Task 85**: BM25 Text Scoring (pending)

## Next Steps

1. ✅ Deploy configuration fix (complete)
2. ⏳ Execute validation test queries via API Gateway
3. ⏳ Monitor logs for rerank invocation
4. ⏳ Update Task 80 validation report with rerank metrics
5. ⏳ Mark Task 84 as complete once validation passes

## Notes

- The deployment script reported "failed" but the revision actually deployed successfully
- This appears to be a false negative in the health check logic
- Service is healthy and serving 100% of production traffic
- No errors in Cloud Run logs for revision 00054-b6v

---

**Status**: Awaiting production validation
