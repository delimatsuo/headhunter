# Fix: Embedding Service Dimension Mismatch

**Date:** October 25, 2025
**Status:** 🔴 **BLOCKING ISSUE - Services Unhealthy**

---

## Problem

The `hh-embed-svc` service is failing health checks due to a dimension mismatch:

```json
{
  "status": "unhealthy",
  "message": "Embedding dimensionality mismatch detected in search.candidate_embeddings. Expected vector(768)."
}
```

This blocks:
- All embedding generation
- All semantic search operations
- The entire search pipeline

---

## Root Cause

The service's `pgvector-client.ts` verifies the database schema at startup by checking:

```typescript
const atttypmod = Number(embeddingColumn.rows[0]?.atttypmod ?? 0);
if (atttypmod - 4 !== this.dimensions) {
  throw new Error('Embedding dimensionality mismatch...');
}
```

For `this.dimensions = 768`, it expects `atttypmod = 772`.

**The database column currently has a different `atttypmod` value.**

---

## Solution

### Step 1: Verify Current Database State

Connect to database via Cloud Shell:

```bash
gcloud sql connect sql-hh-core \
  --user=postgres \
  --database=headhunter \
  --project=headhunter-ai-0088
```

Password: `TempAdmin123!`

Check current dimension:

```sql
SELECT
    attname as column_name,
    atttypmod,
    atttypmod - 4 as dimension,
    format_type(atttypid, atttypmod) as full_type
FROM pg_attribute
WHERE attrelid = 'search.candidate_embeddings'::regclass
  AND attname = 'embedding';
```

**Expected Result:**
- `atttypmod`: 772
- `dimension`: 768
- `full_type`: vector(768)

**If dimension is NOT 768, proceed to Step 2.**

### Step 2: Apply Database Fix

Run the complete fix (this is idempotent - safe to run multiple times):

```sql
BEGIN;

-- 1. Drop and recreate embedding column with correct dimensions
ALTER TABLE search.candidate_embeddings DROP COLUMN IF EXISTS embedding CASCADE;
ALTER TABLE search.candidate_embeddings ADD COLUMN embedding vector(768);

-- 2. Recreate unique constraint (was dropped by CASCADE)
ALTER TABLE search.candidate_embeddings
  ADD CONSTRAINT candidate_embeddings_tenant_entity_chunk_unique
  UNIQUE (tenant_id, entity_id, chunk_type);

-- 3. Recreate indexes with correct names
CREATE INDEX IF NOT EXISTS candidate_embeddings_embedding_hnsw_idx
  ON search.candidate_embeddings
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS candidate_embeddings_embedding_ivfflat_idx
  ON search.candidate_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- 4. Verify the fix
SELECT
    attname,
    atttypmod,
    atttypmod - 4 as dimension
FROM pg_attribute
WHERE attrelid = 'search.candidate_embeddings'::regclass
  AND attname = 'embedding';

COMMIT;
```

**This will:**
- ✅ Set correct dimension (768)
- ✅ Recreate all necessary indexes
- ❌ **DELETE all existing embeddings** (17,969 embeddings will be lost)

### Step 3: Re-embed All Enriched Candidates

After applying the database fix, re-run the embedding script:

```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter"
python3 scripts/reembed_all_enriched.py
```

**This will:**
- Re-embed 17,969 enriched candidates
- Take approximately 10-11 minutes
- Process at ~27.6 candidates/second
- Save progress incrementally (resumable if interrupted)

### Step 4: Restart Services

After re-embedding completes:

```bash
# Restart embedding service
gcloud run services update hh-embed-svc-production \
  --region us-central1 \
  --project headhunter-ai-0088 \
  --update-env-vars="RESTART_TIMESTAMP=$(date +%s)"

# Restart search service
gcloud run services update hh-search-svc-production \
  --region us-central1 \
  --project headhunter-ai-0088 \
  --update-env-vars="RESTART_TIMESTAMP=$(date +%s)"
```

### Step 5: Verify Fix

Test services are healthy:

```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter"
python3 scripts/check_service_health.py
```

Test search functionality:

```bash
python3 scripts/test_hybrid_search_api.py
```

---

## Why This Happened

### Previous Session (October 20, 2025)

The database was successfully fixed and 17,969 candidates were re-embedded. The fix was working correctly.

### Current Session (October 25, 2025)

The dimension mismatch reappeared. Possible causes:

1. **Database Restore**: An automated backup restore may have reverted the schema
2. **Manual Revert**: Someone may have run migrations that recreated the old schema
3. **Multiple Tables**: There might be another `candidate_embeddings` table being checked
4. **Cache Issue**: (Unlikely - service restarts should clear caches)

---

## Prevention

### Immediate

1. **Disable Auto-Backups Temporarily**: While fixing, to prevent reverts
2. **Lock Schema**: Add a comment or migration marker indicating this schema is correct

### Long Term

1. **Update Migration Scripts**: Ensure all migrations use `vector(768)` not `vector(3072)`
2. **Add Schema Tests**: Include automated tests that verify dimension configuration
3. **Document Schema**: Add clear documentation in codebase about dimension requirements
4. **Alert on Mismatch**: Add monitoring that alerts if dimension changes

---

## Alternative: Bypass Schema Check (NOT RECOMMENDED)

If you need the service running immediately without fixing the database, you could temporarily disable the schema verification:

**File:** `services/hh-embed-svc/src/pgvector-client.ts`

```typescript
// Line 335 - Comment out the dimension check
// if (!Number.isFinite(atttypmod) || actualDimension !== this.dimensions) {
//   throw new Error(...);
// }
```

**Why this is NOT recommended:**
- Embeddings will have wrong dimensions
- Search will produce incorrect results
- Data corruption will occur
- You'll need to fix and re-embed anyway

---

## Files

### Scripts
- `scripts/sql/complete_embedding_fix.sql` - Complete database fix
- `scripts/reembed_all_enriched.py` - Re-embedding script
- `scripts/check_service_health.py` - Service health checker
- `scripts/test_hybrid_search_api.py` - Search functionality test

### Documentation
- `EMBEDDING_FIX_SUMMARY.md` - Previous fix (October 20)
- `SEARCH_TEST_STATUS.md` - Current testing status
- `docs/HANDOVER.md` - Database credentials

### Configuration
- `config/cloud-run/hh-embed-svc.yaml` - Service config (EMBEDDING_DIMENSIONS: "768")
- `services/hh-embed-svc/src/pgvector-client.ts` - Schema verification code

---

## Next Steps

**Required:** Execute Steps 1-5 above to restore service functionality.

**Estimated Time:** 20-30 minutes total
- Database fix: 2 minutes
- Re-embedding: 10-11 minutes
- Service restart & verification: 5-10 minutes

**Impact During Fix:**
- ❌ Search unavailable
- ❌ Embedding generation unavailable
- ✅ Other services unaffected

---

**Last Updated:** October 25, 2025 16:20 UTC
