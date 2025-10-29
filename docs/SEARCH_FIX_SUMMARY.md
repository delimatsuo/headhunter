# Search Fix Summary - 2025-10-29

## 🔴 CRITICAL ISSUE IDENTIFIED

**Problem:** Hybrid search returns 0 results despite 28,988 embeddings successfully created.

**Root Cause:** Entity ID format mismatch causing join failure between `candidate_embeddings` and `candidate_profiles` tables.

## Investigation Summary

### What Was Tested

1. ✅ **hh-search-svc Service Health** - Fixed Cloud SQL connection (added missing annotation)
2. ✅ **API Gateway Integration** - Successfully returns responses (but with 0 results)
3. ❌ **Search Results** - Returns empty array despite valid query and operational service

### Root Cause Analysis

**Problem Location:** `scripts/embed_newly_enriched.py:155` and `scripts/reembed_enriched_candidates.py:176`

```python
# BROKEN CODE (before fix):
"entityId": f"{tenant_id}:{candidate_id}"  # Creates "tenant-alpha:509113109"
```

**Impact:**
- Embeddings stored with `entity_id` = `"tenant-alpha:509113109"` (prefixed)
- Profiles table has `candidate_id` = `"509113109"` (no prefix)
- JOIN condition fails: `candidate_embeddings.entity_id = candidate_profiles.candidate_id`
- Result: 0 matches found

**Evidence:**
- Historical search (2025-10-07) returned plain IDs: `509113109, 280839452, 476480262`
- New embeddings (Phase 2 & 3) added prefixes
- All 28,988 embeddings affected

## Fix Applied

### ✅ Phase 2 Complete: Scripts Fixed

Updated both embedding scripts to use plain candidate IDs:

**Files Modified:**
- `scripts/embed_newly_enriched.py:155` - Removed tenant prefix
- `scripts/reembed_enriched_candidates.py:176` - Removed tenant prefix

```python
# FIXED CODE:
"entityId": candidate_id  # Creates "509113109" (plain ID)
```

### 🔧 Phase 1 Required: Database Migration

**CRITICAL:** Existing 28,988 embeddings still have prefixed IDs. Must run SQL migration:

```sql
UPDATE search.candidate_embeddings
SET entity_id = SPLIT_PART(entity_id, ':', 2)
WHERE entity_id LIKE 'tenant-%:%';
```

**How to Execute:**

```bash
# Option A: Via GCP Console Cloud Shell
# 1. Go to https://console.cloud.google.com/cloudshell
# 2. Run:
gcloud sql connect sql-hh-core \
  --user=hh_analytics \
  --database=headhunter \
  --project=headhunter-ai-0088

# 3. At psql prompt, paste:
UPDATE search.candidate_embeddings
SET entity_id = SPLIT_PART(entity_id, ':', 2)
WHERE entity_id LIKE 'tenant-%:%';

# 4. Verify:
SELECT COUNT(*) FILTER (WHERE entity_id LIKE 'tenant-%:%') as still_prefixed
FROM search.candidate_embeddings WHERE tenant_id = 'tenant-alpha';
-- Should return: still_prefixed = 0
```

**Option B: Use Deployed Cloud Run Service**

Since hh-embed-svc already has Cloud SQL access:
1. Add a one-time admin endpoint to hh-embed-svc
2. Deploy with migration endpoint
3. Call endpoint to execute SQL
4. Remove endpoint and redeploy

## Validation Steps

After SQL migration is complete:

### 1. Test Hybrid Search

```bash
curl -sS \
  -H "x-api-key: AIzaSyD4fwoF0SMDVsA4A1Ip0_dT-qfP1OYPODs" \
  -H "X-Tenant-ID: tenant-alpha" \
  -H "Content-Type: application/json" \
  https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/search/hybrid \
  -d '{"query":"Senior software engineer with Python","limit":5,"includeDebug":true}' | jq
```

**Expected:** `results` array with 5 candidates

### 2. Verify Database State

```sql
-- Check all prefixes are stripped
SELECT COUNT(*) as total,
       COUNT(*) FILTER (WHERE entity_id LIKE 'tenant-%:%') as still_prefixed
FROM search.candidate_embeddings WHERE tenant_id = 'tenant-alpha';
-- Expected: still_prefixed = 0

-- Check join works
SELECT COUNT(DISTINCT ce.entity_id) as matches
FROM search.candidate_embeddings ce
INNER JOIN search.candidate_profiles cp
  ON ce.entity_id = cp.candidate_id
WHERE ce.tenant_id = 'tenant-alpha';
-- Expected: ~28,988 matches
```

## Files Changed

- ✅ `scripts/embed_newly_enriched.py` - Fixed entityId format
- ✅ `scripts/reembed_enriched_candidates.py` - Fixed entityId format
- ✅ `docs/ENTITY_ID_FIX.md` - Comprehensive fix documentation
- ✅ `docs/SEARCH_FIX_SUMMARY.md` - This document

## Status

- ✅ **Root cause identified** - Entity ID prefix mismatch
- ✅ **Scripts fixed** - Future embeddings will use correct format
- ⏳ **Database migration pending** - Need to strip prefixes from existing 28,988 embeddings
- ⏳ **Search validation pending** - Test after migration

## Next Operator Actions

**IMMEDIATE (Required for Search to Work):**
1. Execute SQL migration (see "How to Execute" above)
2. Verify migration completed successfully
3. Test hybrid search endpoint
4. Update `docs/HANDOVER.md` with resolution

**FOLLOW-UP:**
1. Consider adding integration tests for search flow
2. Document expected entity_id format in API contracts
3. Add schema validation in embedding scripts

## Timeline

- 2025-10-28: Phase 3 embeddings completed (28,988 total)
- 2025-10-29 09:00: Search testing revealed 0 results
- 2025-10-29 10:15: Root cause identified
- 2025-10-29 11:30: Scripts fixed, migration SQL prepared
- **PENDING:** SQL migration execution
- **PENDING:** Search validation

## Sign-Off

**Scripts Fixed By:** Claude Code (2025-10-29)
**Awaiting:** Manual SQL migration execution by operator

See `docs/ENTITY_ID_FIX.md` for comprehensive technical details.
