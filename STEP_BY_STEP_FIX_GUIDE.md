# Step-by-Step Fix Guide

**Date:** October 25, 2025
**Estimated Time:** 30-40 minutes
**Difficulty:** Medium (requires Cloud Shell access)

---

## Overview

This guide will:
1. ✅ Commit schema fixes (prevent future issues)
2. 🔧 Fix the database (restore correct dimension)
3. 🔄 Re-embed all candidates (~11 minutes)
4. 🔄 Restart services
5. ✅ Verify everything works

**Impact During Fix:**
- ❌ Search unavailable (10-15 minutes)
- ❌ Embedding generation unavailable (10-15 minutes)
- ✅ Other services unaffected

---

## Prerequisites

- [x] Terminal access to project directory
- [x] Git configured and authenticated
- [x] GCP access (`gcloud` authenticated)
- [x] Cloud Shell access (for database fix)

---

## STEP 1: Commit Schema File Changes

**Purpose:** Prevent future dimension reverts when infrastructure scripts run

**Time:** 2-3 minutes

### 1.1 Navigate to project directory

```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter"
```

### 1.2 Verify changes look correct

```bash
git diff scripts/setup_database_schemas.sql | head -20
```

**You should see:**
```diff
-    embedding VECTOR(1536) NOT NULL,
+    embedding VECTOR(768) NOT NULL,
```

✅ If you see this, continue. ❌ If not, stop and ask for help.

### 1.3 Stage the schema files

```bash
git add scripts/setup_database_schemas.sql
git add scripts/setup_database_schemas_clean.sql
git add scripts/setup_database_schemas_postgres.sql
git add scripts/setup_database_tables_fixed.sql
git add scripts/setup_database_tables_only.sql
```

### 1.4 Stage the documentation

```bash
git add PREVENT_DIMENSION_REVERT.md
git add FIX_EMBEDDING_DIMENSION.md
git add ROOT_CAUSE_AND_FIX_SUMMARY.md
git add SEARCH_TEST_STATUS.md
git add STEP_BY_STEP_FIX_GUIDE.md
```

### 1.5 Stage the enhanced logging

```bash
git add services/hh-embed-svc/src/pgvector-client.ts
```

### 1.6 Commit the changes

```bash
git commit -m "fix: correct embedding dimension to 768 in all schema files

Infrastructure scripts were applying VECTOR(1536) instead of VECTOR(768),
causing dimension mismatches when provisioning ran. This broke all search
functionality when someone ran provision-gcp-infrastructure.sh.

Changes:
- Fixed all 5 setup_database_*.sql files: VECTOR(1536) → VECTOR(768)
- Added dimension debug logging to pgvector-client.ts
- Created comprehensive documentation and recovery guides

Prevents future dimension reverts. See PREVENT_DIMENSION_REVERT.md

Model: VertexAI text-embedding-004 (768 dimensions)
Affects: 17,969+ candidate embeddings"
```

### 1.7 Push to remote

```bash
git push origin main
```

**Expected output:**
```
Enumerating objects: XX, done.
Counting objects: 100% (XX/XX), done.
...
To github.com:your-org/headhunter.git
   xxxxxxx..yyyyyyy  main -> main
```

✅ **Checkpoint 1 Complete:** Schema files fixed in codebase

---

## STEP 2: Fix the Database

**Purpose:** Restore correct dimension in production database

**Time:** 5-10 minutes

**⚠️ WARNING:** This will delete all existing embeddings. They will be regenerated in Step 3.

### 2.1 Open Cloud Shell

Go to: https://console.cloud.google.com/?project=headhunter-ai-0088

Click the **Cloud Shell** icon (top right, `>_` symbol)

### 2.2 Connect to the database

In Cloud Shell, run:

```bash
gcloud sql connect sql-hh-core \
  --user=postgres \
  --database=headhunter \
  --project=headhunter-ai-0088
```

**When prompted for password, enter:**
```
TempAdmin123!
```

**Expected output:**
```
Allowlisting your IP for incoming connection for 5 minutes...done.
Connecting to database with SQL user [postgres].Password:
psql (15.x)
Type "help" for help.

headhunter=>
```

✅ You should now see the `headhunter=>` prompt.

### 2.3 Verify current (incorrect) dimension

At the `headhunter=>` prompt, run:

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

**Expected output (WRONG dimension):**
```
 column_name | atttypmod | dimension |   full_type
-------------+-----------+-----------+---------------
 embedding   |      1540 |      1536 | vector(1536)
```

If you see `dimension` is anything OTHER than 768, continue.

### 2.4 Check embeddings count (for verification later)

```sql
SELECT COUNT(*) as total_embeddings
FROM search.candidate_embeddings;
```

**Expected output:**
```
 total_embeddings
------------------
            17969
```

Note this number - we'll verify it's restored after re-embedding.

### 2.5 Apply the fix (CRITICAL STEP)

Copy and paste this entire SQL block:

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

COMMIT;
```

**Expected output:**
```
BEGIN
NOTICE:  drop cascades to ...
ALTER TABLE
ALTER TABLE
ALTER TABLE
CREATE INDEX
CREATE INDEX
COMMIT
```

✅ If you see `COMMIT`, the fix was applied successfully!

### 2.6 Verify the fix

```sql
SELECT
    attname,
    atttypmod,
    atttypmod - 4 as dimension,
    format_type(atttypid, atttypmod) as full_type
FROM pg_attribute
WHERE attrelid = 'search.candidate_embeddings'::regclass
  AND attname = 'embedding';
```

**Expected output (CORRECT dimension):**
```
  attname  | atttypmod | dimension |  full_type
-----------+-----------+-----------+-------------
 embedding |       772 |       768 | vector(768)
```

✅ If you see `dimension | 768`, the database is fixed!

### 2.7 Exit Cloud Shell

```sql
\q
```

Then close the Cloud Shell tab.

✅ **Checkpoint 2 Complete:** Database has correct dimension

---

## STEP 3: Re-embed All Enriched Candidates

**Purpose:** Restore the 17,969 embeddings that were deleted

**Time:** 10-12 minutes

### 3.1 Navigate to project (if not already there)

```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter"
```

### 3.2 Verify the re-embedding script exists

```bash
ls -lh scripts/reembed_all_enriched.py
```

**Expected:** File exists with ~8KB size

### 3.3 Delete old progress file (start fresh)

```bash
rm -f data/enriched/reembed_progress.json
rm -f data/enriched/reembed_failed.json
```

### 3.4 Run the re-embedding script

```bash
python3 scripts/reembed_all_enriched.py
```

**Expected output:**
```
🚀 Re-embedding Enriched Candidates
============================================================

📂 Loading candidates from data/enriched/enriched_candidates_full.json...
   Total candidates: 17969
   Already processed: 0
   Remaining to process: 17969

🔄 Processing batch 1/899 (20 candidates)...
   ✅ Success: 20, ❌ Failed: 0
   Progress: 20/17969 | Rate: 27.6/s | ETA: 10.8m
...
```

**This will take approximately 10-12 minutes.**

☕ Take a break! The script will:
- Process 20 candidates at a time
- Save progress every batch (resumable if interrupted)
- Show progress and ETA
- Report any failures

### 3.5 Wait for completion

**Expected final output:**
```
============================================================
✅ Re-embedding Complete!
============================================================
   Total processed: 17969
   Successful: 17969
   Failed: 0
   Duration: 10.8 minutes
   Average rate: 27.6 candidates/second
```

✅ **Checkpoint 3 Complete:** All embeddings restored

---

## STEP 4: Restart Services

**Purpose:** Services need to re-check the database schema

**Time:** 3-5 minutes

### 4.1 Restart hh-embed-svc

```bash
gcloud run services update hh-embed-svc-production \
  --region us-central1 \
  --project headhunter-ai-0088 \
  --update-env-vars="RESTART_TIMESTAMP=$(date +%s)"
```

**Expected output:**
```
Deploying...
Creating Revision........done
Routing traffic.....done
Done.
Service [hh-embed-svc-production] revision [hh-embed-svc-production-0006X-xxx] has been deployed...
```

### 4.2 Wait for deployment (30-60 seconds)

```bash
sleep 60
```

### 4.3 Restart hh-search-svc

```bash
gcloud run services update hh-search-svc-production \
  --region us-central1 \
  --project headhunter-ai-0088 \
  --update-env-vars="RESTART_TIMESTAMP=$(date +%s)"
```

**Expected output:**
```
Deploying...
Creating Revision........done
Routing traffic.....done
Done.
Service [hh-search-svc-production] revision [hh-search-svc-production-0006X-xxx] has been deployed...
```

### 4.4 Wait for deployment (30-60 seconds)

```bash
sleep 60
```

✅ **Checkpoint 4 Complete:** Services restarted

---

## STEP 5: Verify Everything Works

**Purpose:** Confirm services are healthy and search works

**Time:** 2-3 minutes

### 5.1 Check service health

```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter"
python3 scripts/check_service_health.py
```

**Expected output (HEALTHY):**
```
Checking hh-embed-svc-production-akcoqbr7sa-uc.a.run.app/health/detailed
================================================================================
Status: 200 (or 404 is OK - route doesn't exist)

Checking hh-search-svc-production-akcoqbr7sa-uc.a.run.app/health/detailed
================================================================================
Status: 200
Response:
{
  "status": "ok",
  "pgvector": {
    "status": "healthy",
    "totalCandidates": 17969
  },
  "redis": {
    "status": "healthy"
  },
  "embeddings": {
    "status": "healthy"  ← This should NOT say "unavailable"
  },
  "rerank": {
    "status": "healthy"
  }
}
```

✅ **Key check:** `embeddings.status` should be `"healthy"`, NOT `"unavailable"`

### 5.2 Test search functionality

```bash
python3 scripts/test_hybrid_search_api.py
```

**Expected output (WORKING):**
```
================================================================================
HYBRID SEARCH API TEST - Senior Java Software Engineer
================================================================================

🔐 Getting auth token...
   ✅ Token obtained

📝 Job Description:
...

🔍 Searching for matching candidates...

================================================================================
TOP 10 MATCHING CANDIDATES
================================================================================

1. Candidate ID: 123456
   Relevance Score: 0.8542
   Profile:
      Skills: Java, Spring Boot, Docker, Kubernetes, AWS
      Career Level: Senior
      Experience: 10 years

...

✅ Hybrid search API working correctly!
✅ Found 10 matching candidates
✅ Top match score: 0.8542

The embeddings are working properly with enriched data!
```

✅ **If you see candidates returned, search is working!**

### 5.3 Final verification - Check database

Let's verify the embeddings are actually in the database:

```bash
python3 << 'EOF'
import subprocess

# Check via embed service health
result = subprocess.run([
    'python3', 'scripts/check_embed_health.py'
], capture_output=True, text=True)

print(result.stdout)

# Look for "healthy" status
if '"status":"unhealthy"' in result.stdout:
    print("\n❌ Service still unhealthy - something went wrong")
    exit(1)
elif 'Status: 503' in result.stdout:
    print("\n❌ Service returning 503 - check logs")
    exit(1)
else:
    print("\n✅ Embed service appears healthy!")
EOF
```

✅ **Checkpoint 5 Complete:** Everything verified working

---

## ✅ SUCCESS! You're Done!

### What We Accomplished

1. ✅ **Committed schema fixes** - Future infrastructure runs won't break it
2. ✅ **Fixed database** - Correct 768 dimension restored
3. ✅ **Re-embedded 17,969 candidates** - All embeddings restored
4. ✅ **Restarted services** - Services now healthy
5. ✅ **Verified search works** - Full functionality restored

### System Status

- ✅ Embedding service: Healthy
- ✅ Search service: Healthy
- ✅ Database: Correct dimension (768)
- ✅ Embeddings: 17,969 candidates indexed
- ✅ Search: Fully operational

---

## Troubleshooting

### If Step 1.7 (git push) fails

**Error:** `rejected - non-fast-forward`

**Solution:**
```bash
git pull --rebase origin main
git push origin main
```

### If Step 2.5 (database fix) fails

**Error:** `permission denied` or `must be owner`

**Solution:** Make sure you're connected as `postgres` user (not `hh_app`)

### If Step 3.4 (re-embedding) fails

**Error:** `Failed to create embedding: 503`

**Solution:** The database might not be fixed yet. Go back to Step 2 and verify.

**Error:** `Authentication failed`

**Solution:**
```bash
gcloud auth login
gcloud auth application-default login
```

### If Step 5.1 (health check) shows embeddings unavailable

**Error:** `"embeddings": {"status": "unavailable"}`

**Solution:** Check embed service logs:
```bash
gcloud logging read \
  "resource.labels.service_name=hh-embed-svc-production" \
  --limit 20 \
  --project headhunter-ai-0088
```

Look for dimension mismatch errors. If found, database might not be fixed - return to Step 2.

### If Step 5.2 (search test) fails

**Error:** `HTTP 500 - internal error`

**Solution:** Services might need more time to initialize. Wait 2 minutes and try again:
```bash
sleep 120
python3 scripts/test_hybrid_search_api.py
```

---

## Need Help?

### Check Documentation
- `PREVENT_DIMENSION_REVERT.md` - Why it broke, how to prevent
- `FIX_EMBEDDING_DIMENSION.md` - Detailed fix procedure
- `ROOT_CAUSE_AND_FIX_SUMMARY.md` - Complete analysis

### Check Logs
```bash
# Embed service logs
gcloud logging read \
  "resource.labels.service_name=hh-embed-svc-production" \
  --limit 50 \
  --project headhunter-ai-0088

# Search service logs
gcloud logging read \
  "resource.labels.service_name=hh-search-svc-production" \
  --limit 50 \
  --project headhunter-ai-0088
```

### Verify Database State
Open Cloud Shell and run:
```sql
SELECT atttypmod - 4 as dimension
FROM pg_attribute
WHERE attrelid = 'search.candidate_embeddings'::regclass
  AND attname = 'embedding';
```

Should return `768`.

---

**End of Guide**

Total time: 30-40 minutes
All systems should be operational after completing all steps.
