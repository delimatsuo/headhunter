# Search Fix Validation Guide

This guide explains how to run the comprehensive validation script to verify the search fix is complete.

## 📋 Prerequisites

The validation script requires:
1. Cloud SQL proxy running on port 5433
2. Access to Secret Manager (for database password)
3. Python 3 with `psycopg2` and `aiohttp` libraries
4. Network access to production API Gateway

## 🚀 Option 1: Run in Cloud Shell (RECOMMENDED)

Cloud Shell has all prerequisites pre-installed and configured.

### Step 1: Open Cloud Shell

```bash
# Go to https://console.cloud.google.com/cloudshell
# Or click the Cloud Shell button in GCP Console
```

### Step 2: Clone Repository (if needed)

```bash
git clone https://github.com/delimatsuo/headhunter.git
cd headhunter
```

### Step 3: Install Python Dependencies

```bash
pip3 install psycopg2-binary aiohttp --user
```

### Step 4: Start Cloud SQL Proxy

```bash
# Download proxy (if not already installed)
wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -O cloud_sql_proxy
chmod +x cloud_sql_proxy

# Start proxy in background
./cloud_sql_proxy -instances=headhunter-ai-0088:us-central1:sql-hh-core=tcp:5433 &

# Wait for it to start
sleep 5

# Verify it's running
lsof -i :5433
```

### Step 5: Run Validation

```bash
python3 scripts/validate_search_fix.py
```

Expected output:
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    SEARCH FIX VALIDATION                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

================================================================================
🗄️  DATABASE VALIDATION
================================================================================

📊 Test 1: Overall Embedding Statistics
--------------------------------------------------------------------------------
Total embeddings: 75,000
Has vectors: 72,500 (96.7%)
NULL vectors: 2,500
Status: ✅ PASS (Expected: ≥95% complete)

🏷️  Test 2: Entity ID Format Validation
--------------------------------------------------------------------------------
Total embeddings: 75,000
Prefixed IDs: 0
Plain IDs: 75,000
Status: ✅ PASS (Expected: 0 prefixed IDs)

... [more tests] ...

================================================================================
📋 FINAL SUMMARY
================================================================================

Database Validation: ✅ PASS
Search Validation: ✅ PASS

🎉 ============================================================================
🎉 ALL TESTS PASSED - SEARCH FIX IS COMPLETE!
🎉 ============================================================================

✅ Entity ID format: Fixed (no prefixes)
✅ Embedding vectors: Generated (768 dimensions)
✅ Database JOIN: Working
✅ Hybrid search: Returning results

Next steps:
1. Update docs/HANDOVER.md with resolution
2. Mark incident as closed
3. Monitor production metrics
```

## 🖥️ Option 2: Run Locally

If you prefer to run from your local machine:

### Step 1: Install Dependencies

```bash
# Install Cloud SQL Proxy v2 (recommended)
brew install cloud-sql-proxy  # macOS
# OR download from: https://github.com/GoogleCloudPlatform/cloud-sql-proxy/releases

# Install Python dependencies
pip3 install psycopg2-binary aiohttp
```

### Step 2: Authenticate

```bash
gcloud auth login
gcloud config set project headhunter-ai-0088
gcloud auth application-default login
```

### Step 3: Start Cloud SQL Proxy

```bash
# Using Cloud SQL Proxy v2 (TCP mode)
cloud-sql-proxy --address 0.0.0.0 --port 5433 headhunter-ai-0088:us-central1:sql-hh-core &

# Wait for startup
sleep 5

# Verify
lsof -i :5433
```

### Step 4: Run Validation

```bash
cd /path/to/headhunter
python3 scripts/validate_search_fix.py
```

## 📊 What the Validation Checks

### Database Tests (6 tests)

1. **Overall Statistics** - Verifies ≥95% of embeddings have actual vectors
2. **Entity ID Format** - Confirms 0 prefixed IDs remain
3. **Vector Dimensions** - Validates all vectors are 768 dimensions
4. **Source Breakdown** - Checks phase2_structured_reembedding has ≥25,000 embeddings
5. **Sample Embeddings** - Spot-checks recent embeddings for quality
6. **JOIN Compatibility** - Verifies embeddings JOIN properly with profiles

### Search Tests (4 tests)

Tests hybrid search with various queries:
1. Python + Machine Learning
2. Java + Spring Boot
3. Full Stack + React/Node.js
4. DevOps + Kubernetes

Each test verifies:
- HTTP 200 response
- Results array not empty
- Total > 0
- Debug info shows vector results and profile JOINs

## 🔍 Interpreting Results

### ✅ All Tests Pass

```
🎉 ALL TESTS PASSED - SEARCH FIX IS COMPLETE!
```

**Actions:**
1. Update `docs/HANDOVER.md` with resolution
2. Mark incident as closed in tracking system
3. Monitor production metrics for 24-48 hours

### ❌ Database Tests Fail

**Possible Issues:**

**Issue 1: Low vector completion (<95%)**
```
Has vectors: 40,000 (53.3%)
Status: ❌ FAIL (Expected: ≥95% complete)
```

**Solution:** Re-embedding batch may not have completed. Check:
```bash
# Check re-embedding script status
ps aux | grep reembed

# Check Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision
  AND resource.labels.service_name=hh-embed-svc-production
  AND timestamp>\"2025-10-29T13:00:00Z\"" --limit 100
```

**Issue 2: Prefixed IDs still exist**
```
Prefixed IDs: 15,000
Status: ❌ FAIL (Expected: 0 prefixed IDs)
```

**Solution:** SQL migration didn't complete. Re-run:
```sql
UPDATE search.candidate_embeddings
SET entity_id = SPLIT_PART(entity_id, ':', 2)
WHERE entity_id LIKE 'tenant-%:%';
```

**Issue 3: Wrong dimensions**
```
Dimension 384: 50,000 embeddings
Status: ❌ FAIL (Expected: All 768 dimensions)
```

**Solution:** Wrong embedding model was used. Check hh-embed-svc configuration.

### ❌ Search Tests Fail

**Issue: No results returned**
```
Results returned: 0
Status: ❌ FAIL (Expected: results > 0)
```

**Solutions:**

1. **Check service health:**
```bash
curl -sS https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/health
```

2. **Check Cloud Run logs:**
```bash
gcloud logging read "resource.type=cloud_run_revision
  AND resource.labels.service_name=hh-search-svc-production
  AND severity>=ERROR" --limit 50
```

3. **Verify embeddings completed:**
Run database validation SQL queries manually

4. **Test direct search service:**
```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "X-Tenant-ID: tenant-alpha" \
  https://hh-search-svc-production-akcoqbr7sa-uc.a.run.app/v1/search/hybrid \
  -d '{"query":"Python developer","limit":5}'
```

## 📁 Output Files

The validation script creates:
- `/tmp/search_validation_results.json` - Full results in JSON format

Example:
```json
{
  "database": {
    "passed": true,
    "results": {
      "total_embeddings": 75000,
      "has_vectors": 72500,
      "percent_complete": 96.7,
      ...
    }
  },
  "search": {
    "passed": true,
    "results": {
      "query_1": {"status": "success", "num_results": 5, "total": 247}
      ...
    }
  }
}
```

## 🆘 Troubleshooting

### Cloud SQL Proxy Connection Errors

```
ERROR: connection to server at "localhost", port 5433 failed: Connection refused
```

**Solutions:**
1. Verify proxy is running: `lsof -i :5433`
2. Check proxy logs for errors
3. Ensure correct instance connection string
4. Verify IAM permissions (Cloud SQL Client role)

### Secret Manager Access Errors

```
ERROR: Failed to get database password: permission denied
```

**Solutions:**
1. Verify authentication: `gcloud auth list`
2. Check IAM permissions: Secret Manager Secret Accessor role
3. Ensure secret exists:
```bash
gcloud secrets list --filter="name:db-analytics-password" --project=headhunter-ai-0088
```

### API Gateway 401/403 Errors

```
❌ HTTP 401: Unauthorized
```

**Solutions:**
1. Verify API key is correct
2. Check API Gateway configuration
3. Ensure tenant-alpha is configured

## 📚 Additional Resources

- **Complete Fix Documentation:** `docs/SEARCH_FIX_COMPLETE.md`
- **Technical Details:** `docs/ENTITY_ID_FIX.md`
- **Operator Runbook:** `docs/HANDOVER.md`
- **Validation Script:** `scripts/validate_search_fix.py`

## ✅ Success Criteria Summary

The fix is complete when validation shows:

| Check | Target | Critical |
|-------|--------|----------|
| Embeddings with vectors | ≥95% | ✅ Yes |
| Entity ID format | 0 prefixed | ✅ Yes |
| Vector dimensions | 100% at 768 | ✅ Yes |
| phase2_structured_reembedding | ≥25,000 | ✅ Yes |
| JOIN with profiles | ≥25,000 | ✅ Yes |
| Search queries returning results | 4/4 pass | ✅ Yes |

---

**For Questions or Issues:**
- Check validation output in `/tmp/search_validation_results.json`
- Review Cloud Logging for service errors
- Consult `docs/SEARCH_FIX_COMPLETE.md` for detailed troubleshooting
