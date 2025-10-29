# Entity ID Format Fix

**Date:** 2025-10-29
**Status:** 🔴 **CRITICAL - Search Broken**
**Impact:** Hybrid search returns 0 results due to entity_id format mismatch

## Root Cause

After investigating zero search results, identified TWO critical issues:

###  1. Entity ID Prefix Mismatch

**Problem:**
- Embedding scripts send `entityId: "tenant-alpha:509113109"` (with tenant prefix)
- hh-embed-svc stores this directly in `search.candidate_embeddings.entity_id`
- hh-search-svc joins `candidate_embeddings.entity_id` with `candidate_profiles.candidate_id`
- But `candidate_profiles.candidate_id` = `"509113109"` (no prefix)
- **JOIN FAILS** → 0 results returned

**Evidence:**
- `scripts/embed_newly_enriched.py:155`: `"entityId": f"{tenant_id}:{candidate_id}"`
- `scripts/reembed_enriched_candidates.py:176`: `"entityId": f"{tenant_id}:{candidate_id}"`
- `services/hh-embed-svc/src/pgvector-client.ts:121`: Stores `record.entityId` directly to `entity_id` column
- `services/hh-search-svc/src/pgvector-client.ts:197-198`: Joins on `candidate_id` fields

**Historical Context:**
- Search worked on 2025-10-07 (see `docs/HANDOVER.md:155-180`)
- Returned IDs: `509113109, 280839452, 476480262` (plain numbers, no prefix)
- New embeddings (Phase 2 & 3) added prefixes → broke search

### 2. Schema Inconsistency (Potential)

**hh-embed-svc** creates table with:
```sql
entity_id TEXT NOT NULL
```

**hh-search-svc** expects table with:
```sql
candidate_id TEXT NOT NULL
```

Both use `candidate_embeddings` table name. Schema mismatch may cause additional issues.

## Impact Assessment

- **All 28,988 embeddings** created in Phase 2 & 3 have prefixed `entity_id`
- **100% search failure rate** (returns 0 results)
- Search service is operational but cannot find any matches due to join failure

## Solution

### Option A: SQL Migration (RECOMMENDED - Fastest)

Strip prefixes from existing embeddings via SQL UPDATE:

```sql
UPDATE search.candidate_embeddings
SET entity_id = SPLIT_PART(entity_id, ':', 2)
WHERE entity_id LIKE 'tenant-%:%';
```

**Pros:**
- Fixes all 28,988 embeddings in <1 minute
- No service downtime
- Immediate search restoration

**Cons:**
- Requires database access
- Cannot be easily tested/rolled back

### Option B: Re-embed Without Prefix

Update scripts to send plain IDs, then re-run:

```python
# BEFORE:
"entityId": f"{tenant_id}:{candidate_id}"

# AFTER:
"entityId": candidate_id
```

**Pros:**
- Clean fix at source
- Testable before production

**Cons:**
- Requires re-embedding all 28,988 candidates (~2-3 hours)
- Temporary search downtime

### Option C: Update hh-search-svc to Strip Prefix

Modify search service to strip prefix during query:

```sql
-- Change join condition
ON SPLIT_PART(ce.entity_id, ':', 2) = cp.candidate_id
```

**Pros:**
- No data migration needed
- Backward compatible

**Cons:**
- Performance impact (cannot use indexes efficiently)
- Doesn't fix root cause

## Recommended Implementation

### Phase 1: Immediate Fix (SQL Migration)

1. **Deploy Cloud Run Job** to execute SQL:
```bash
gcloud run jobs create fix-entity-ids \
  --image=gcr.io/google.com/cloudsdktool/google-cloud-cli:alpine \
  --region=us-central1 \
  --project=headhunter-ai-0088 \
  --set-cloudsql-instances=headhunter-ai-0088:us-central1:sql-hh-core \
  --set-secrets=DB_PASSWORD=hh-db-primary-password:latest \
  --command="/bin/bash" \
  --args="-c","apk add --no-cache postgresql-client && psql \"host=/cloudsql/headhunter-ai-0088:us-central1:sql-hh-core dbname=headhunter user=hh_analytics\" -c \"UPDATE search.candidate_embeddings SET entity_id = SPLIT_PART(entity_id, ':', 2) WHERE entity_id LIKE 'tenant-%:%';\""
```

2. **Execute the job:**
```bash
gcloud run jobs execute fix-entity-ids \
  --region=us-central1 \
  --project=headhunter-ai-0088 \
  --wait
```

3. **Verify fix:**
```bash
# Test search again
curl -sS \
  -H "x-api-key: AIzaSyD4fwoF0SMDVsA4A1Ip0_dT-qfP1OYPODs" \
  -H "X-Tenant-ID: tenant-alpha" \
  -H "Content-Type: application/json" \
  https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/search/hybrid \
  -d '{"query":"Senior Java Software Engineer","limit":5}'
```

### Phase 2: Prevent Future Issues

1. **Update embedding scripts** to use plain IDs:

**File:** `scripts/embed_newly_enriched.py:155`
```python
# BEFORE:
"entityId": f"{tenant_id}:{candidate_id}",

# AFTER:
"entityId": candidate_id,
```

**File:** `scripts/reembed_enriched_candidates.py:176`
```python
# BEFORE:
"entityId": f"{tenant_id}:{candidate_id}",

# AFTER:
"entityId": candidate_id,
```

2. **Commit changes:**
```bash
git add scripts/embed_newly_enriched.py scripts/reembed_enriched_candidates.py
git commit -m "fix: remove tenant prefix from entityId in embedding scripts

- Strip tenant prefix to match candidate_profiles.candidate_id format
- Fixes search join condition to return results
- Prevents future entity_id format mismatches"
```

### Phase 3: Schema Alignment (Future)

Consider aligning schemas between hh-embed-svc and hh-search-svc:
- Standardize on column name (`entity_id` vs `candidate_id`)
- Add schema migration/validation tests
- Document expected ID format in API contracts

## Validation Steps

After applying the fix:

1. **Verify database update:**
```sql
SELECT
  COUNT(*) as total,
  COUNT(*) FILTER (WHERE entity_id LIKE 'tenant-%:%') as still_prefixed
FROM search.candidate_embeddings
WHERE tenant_id = 'tenant-alpha';
```

Expected: `still_prefixed = 0`

2. **Test join works:**
```sql
SELECT COUNT(DISTINCT ce.entity_id)
FROM search.candidate_embeddings ce
INNER JOIN search.candidate_profiles cp
  ON ce.entity_id = cp.candidate_id
WHERE ce.tenant_id = 'tenant-alpha';
```

Expected: `~28,988` (or close to it)

3. **Test hybrid search:**
```bash
curl -sS \
  -H "x-api-key: AIzaSyD4fwoF0SMDVsA4A1Ip0_dT-qfP1OYPODs" \
  -H "X-Tenant-ID: tenant-alpha" \
  -H "Content-Type: application/json" \
  https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/search/hybrid \
  -d '{"query":"Senior software engineer","limit":5,"includeDebug":true}' | jq '.results | length'
```

Expected: `> 0` results

## Files Modified

- `scripts/embed_newly_enriched.py` - Remove tenant prefix from entityId
- `scripts/reembed_enriched.py` - Remove tenant prefix from entityId
- `docs/ENTITY_ID_FIX.md` - This document

## Related Issues

- [X] hh-search-svc returns 0 results (2025-10-29)
- [ ] Schema inconsistency between hh-embed-svc and hh-search-svc
- [ ] Missing integration tests for search flow

## Sign-off

**Next Operator:** Execute Phase 1 SQL migration to restore search functionality immediately. Then apply Phase 2 script fixes to prevent recurrence.
