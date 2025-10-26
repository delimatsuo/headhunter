# How to Prevent Embedding Dimension Revert

**Created:** October 25, 2025
**Severity:** 🔴 CRITICAL

---

## What Happened

The database embedding dimension was manually fixed from 3072→768 on October 20, 2025. However, between October 20-22, the dimension reverted to 1536, breaking all search functionality.

## Root Cause

**Infrastructure provisioning scripts** were re-run, which applied schema files containing the wrong dimension:

```bash
# This script applies the schema:
scripts/setup_cloud_sql_headhunter.sh

# Which is called by:
scripts/provision-gcp-infrastructure.sh
scripts/setup_headhunter_infrastructure.sh
```

The schema files had `VECTOR(1536)` instead of `VECTOR(768)`, causing the revert.

---

## The Fix Applied

✅ **All schema files updated** (October 25, 2025):

1. `scripts/setup_database_schemas.sql`
2. `scripts/setup_database_schemas_clean.sql`
3. `scripts/setup_database_schemas_postgres.sql`
4. `scripts/setup_database_tables_fixed.sql`
5. `scripts/setup_database_tables_only.sql`

All now use `VECTOR(768)` instead of `VECTOR(1536)`.

**Git Status:** These changes must be committed to prevent future issues.

---

## Prevention Rules

### Rule 1: Never Run Schema Scripts on Production Without Review

**Before running ANY of these scripts:**
- ✅ Review schema files for correct dimensions
- ✅ Test on staging first
- ✅ Verify no production data will be lost
- ✅ Check service health after running

**Scripts that apply schemas:**
```bash
scripts/setup_cloud_sql_headhunter.sh
scripts/provision-gcp-infrastructure.sh
scripts/setup_headhunter_infrastructure.sh
```

### Rule 2: Always Check Dimension Configuration

**Before any database operation:**
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

**Expected result:**
- `dimension`: 768
- `full_type`: vector(768)

### Rule 3: Service Configuration Must Match Database

**Service configuration** (`config/cloud-run/hh-embed-svc.yaml`):
```yaml
- name: EMBEDDING_PROVIDER
  value: vertexai
- name: EMBEDDING_DIMENSIONS
  value: "768"
- name: VERTEX_AI_MODEL
  value: text-embedding-004
```

**Database configuration:**
```sql
embedding VECTOR(768)
```

**These MUST always match.**

### Rule 4: Commit Schema Changes Immediately

After fixing schema files:
```bash
git add scripts/setup_database*.sql
git commit -m "fix: correct embedding dimension to 768 (VertexAI)"
git push origin main
```

**If schema files are not committed, they will be overwritten by git pulls.**

---

## Detection & Monitoring

### Early Warning Signs

1. **Service health checks failing** with "dimension mismatch"
2. **Embedding generation returning 500 errors**
3. **Search service reporting embeddings unavailable**

### Manual Check Command

```bash
# Check service health
cd "/Volumes/Extreme Pro/myprojects/headhunter"
python3 scripts/check_service_health.py

# Check embed service specifically
python3 scripts/check_embed_health.py
```

### Automated Monitoring (TODO)

Add Cloud Monitoring alert:
```
resource.type="cloud_run_revision"
resource.labels.service_name="hh-embed-svc-production"
jsonPayload.message:"dimensionality mismatch"
```

Alert when this appears in logs.

---

## Recovery Procedure

If dimension mismatch occurs again:

### Step 1: Verify Schema Files Are Correct

```bash
grep "VECTOR(" scripts/setup_database*.sql
```

All should show `VECTOR(768)`.

### Step 2: Apply Database Fix

See: `FIX_EMBEDDING_DIMENSION.md` for complete procedure.

Quick summary:
1. Connect to database via Cloud Shell
2. Run complete fix SQL (drops and recreates column)
3. Re-embed all enriched candidates (~11 minutes)
4. Restart services
5. Verify functionality

### Step 3: Identify Who Ran the Script

Check Cloud Logging:
```bash
gcloud logging read "textPayload:\"Applying database schema\"" \
  --project headhunter-ai-0088 \
  --format=json \
  --limit=10
```

This shows when `setup_cloud_sql_headhunter.sh` was run.

---

## Long-Term Solutions

### Immediate (Required)

- [x] Fix all schema files to use VECTOR(768)
- [ ] Commit and push schema file changes
- [ ] Add comment in setup scripts warning about dimension
- [ ] Document in HANDOVER.md

### Short-Term (Next Week)

- [ ] Add dimension validation to schema scripts
- [ ] Create pre-deployment validation script
- [ ] Add Cloud Monitoring alerts for dimension mismatch
- [ ] Update infrastructure runbooks

### Long-Term (Next Month)

- [ ] Implement schema versioning/migrations
- [ ] Add automated testing for schema changes
- [ ] Create staging environment for schema testing
- [ ] Add schema change approval workflow

---

## Schema File Safeguard

Add this comment to all schema files:

```sql
-- CRITICAL: This table uses VECTOR(768) for VertexAI text-embedding-004
-- DO NOT change this dimension without:
-- 1. Updating service configuration (EMBEDDING_DIMENSIONS env var)
-- 2. Re-embedding all candidates (17,969+ records, ~11 minutes)
-- 3. Testing on staging first
-- Last updated: 2025-10-25 (VertexAI migration)
```

---

## Testing Checklist

After any database or schema change:

- [ ] Check dimension: `SELECT atttypmod - 4 FROM pg_attribute WHERE...`
- [ ] Verify service health: `python3 scripts/check_service_health.py`
- [ ] Test embedding generation: `python3 scripts/test_embed_service.py`
- [ ] Test search: `python3 scripts/test_hybrid_search_api.py`
- [ ] Monitor logs for errors: Check Cloud Logging for 30 minutes

---

## Key Files

### Schema Files (All Fixed)
- `scripts/setup_database_schemas.sql` ✅
- `scripts/setup_database_schemas_clean.sql` ✅
- `scripts/setup_database_schemas_postgres.sql` ✅
- `scripts/setup_database_tables_fixed.sql` ✅
- `scripts/setup_database_tables_only.sql` ✅

### Scripts That Apply Schemas
- `scripts/setup_cloud_sql_headhunter.sh` (line 253-274)
- `scripts/provision-gcp-infrastructure.sh` (calls setup script)
- `scripts/setup_headhunter_infrastructure.sh` (calls setup script)

### Service Configuration
- `config/cloud-run/hh-embed-svc.yaml` (EMBEDDING_DIMENSIONS: "768")
- `services/hh-embed-svc/src/pgvector-client.ts` (dimension verification)

### Testing Scripts
- `scripts/check_service_health.py` (health checker)
- `scripts/check_embed_health.py` (embed service checker)
- `scripts/test_hybrid_search_api.py` (search test)

### Recovery Scripts
- `scripts/sql/complete_embedding_fix.sql` (database fix)
- `scripts/reembed_all_enriched.py` (re-embedding)

---

## Critical Commits Required

```bash
# Commit the schema fixes
git add scripts/setup_database*.sql
git commit -m "fix: correct embedding dimension to 768 in all schema files

All setup_database_*.sql files incorrectly had VECTOR(1536).
This caused dimension mismatches when infrastructure scripts
were run, reverting the production database to wrong dimensions.

Changed: VECTOR(1536) → VECTOR(768) to match VertexAI text-embedding-004

Affects:
- setup_database_schemas.sql
- setup_database_schemas_clean.sql
- setup_database_schemas_postgres.sql
- setup_database_tables_fixed.sql
- setup_database_tables_only.sql

References: FIX_EMBEDDING_DIMENSION.md, PREVENT_DIMENSION_REVERT.md"

# Push immediately
git push origin main
```

---

**BOTTOM LINE:**

Infrastructure provisioning scripts overwrote the manual database fix by applying schema files with wrong dimensions. This has been fixed, but changes MUST be committed to prevent recurrence.

**Action Required:** Commit and push the schema file changes immediately.
