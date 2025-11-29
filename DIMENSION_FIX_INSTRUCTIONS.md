# Database Dimension Fix - Execution Instructions

## Problem Summary
The production `search.candidate_embeddings` table was created with **3072 dimensions** (OpenAI text-embedding-3-large) but the service is now configured for **768 dimensions** (VertexAI text-embedding-004). This mismatch prevents the embedding service from functioning.

## Solution: Execute Migration SQL via Cloud Console

### Step 1: Open Cloud SQL Query Editor

```bash
# Open the Cloud SQL instance in browser
open "https://console.cloud.google.com/sql/instances/sql-hh-core/query?project=headhunter-ai-0088"
```

### Step 2: Authenticate and Connect
1. Click **"OPEN CLOUD SHELL EDITOR"** or **"Connect using Cloud Shell"**
2. Authenticate as prompted
3. Select database: **headhunter**

### Step 3: Execute Migration SQL

Copy and paste this SQL:

```sql
-- DATABASE DIMENSION MIGRATION
-- Changes embedding column from 3072 to 768 dimensions

BEGIN;

-- Check current dimension
DO $$
DECLARE
    current_dim INTEGER;
BEGIN
    SELECT atttypmod - 4 INTO current_dim
    FROM pg_attribute
    WHERE attrelid = 'search.candidate_embeddings'::regclass
    AND attname = 'embedding';

    RAISE NOTICE 'Current embedding dimension: %', current_dim;
END $$;

-- Drop and recreate with correct dimension
ALTER TABLE search.candidate_embeddings DROP COLUMN IF EXISTS embedding CASCADE;
ALTER TABLE search.candidate_embeddings ADD COLUMN embedding vector(768) NOT NULL;

-- Recreate indexes for performance
CREATE INDEX IF NOT EXISTS idx_candidate_embeddings_hnsw
  ON search.candidate_embeddings
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_candidate_embeddings_ivfflat
  ON search.candidate_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- Verify new dimension
DO $$
DECLARE
    new_dim INTEGER;
BEGIN
    SELECT atttypmod - 4 INTO new_dim
    FROM pg_attribute
    WHERE attrelid = 'search.candidate_embeddings'::regclass
    AND attname = 'embedding';

    RAISE NOTICE 'New embedding dimension: %', new_dim;

    IF new_dim != 768 THEN
        RAISE EXCEPTION 'Migration failed: dimension is %, expected 768', new_dim;
    END IF;

    RAISE NOTICE '✅ Migration successful! Embedding column now has 768 dimensions';
END $$;

COMMIT;
```

### Step 4: Verify Success

You should see output like:
```
NOTICE:  Current embedding dimension: 3072
NOTICE:  New embedding dimension: 768
NOTICE:  ✅ Migration successful! Embedding column now has 768 dimensions
```

### Step 5: Test the Service

After migration, test that hh-embed-svc works:

```bash
# From your terminal
python3 << 'EOF'
import subprocess
import json
import http.client

# Get auth token
result = subprocess.run(
    ["gcloud", "auth", "print-identity-token"],
    capture_output=True, text=True, check=True
)
token = result.stdout.strip()

# Test embedding
conn = http.client.HTTPSConnection("hh-embed-svc-production-1034162584026.us-central1.run.app")
headers = {
    "Authorization": f"Bearer {token}",
    "X-Tenant-ID": "tenant-alpha",
    "Content-Type": "application/json"
}
payload = json.dumps({
    "entityId": "test-fix-verification",
    "text": "Senior Python developer with ML experience",
    "metadata": {"test": True},
    "chunkType": "default"
})

conn.request("POST", "/v1/embeddings/upsert", payload, headers)
response = conn.getresponse()
data = response.read().decode()

if response.status in [200, 201]:
    print(f"✅ SUCCESS! Service is working (Status: {response.status})")
    result = json.loads(data)
    print(f"   Entity ID: {result.get('entityId')}")
    print(f"   Model: {result.get('modelVersion')}")
else:
    print(f"❌ Error: {response.status}")
    print(f"   Response: {data}")
EOF
```

## Alternative: Execute via gcloud (if Cloud Shell is available)

```bash
# Connect to Cloud SQL
gcloud sql connect sql-hh-core --user=postgres --project=headhunter-ai-0088 --database=headhunter

# Then paste the migration SQL above
```

## What This Does

1. **Drops the embedding column** - Removes the incorrectly configured 3072-dimension column
2. **Recreates with 768 dimensions** - Matches VertexAI text-embedding-004
3. **Rebuilds indexes** - HNSW and IVFFlat for efficient similarity search
4. **Verifies success** - Checks that new dimension is exactly 768

## Why This is Safe

- All existing embeddings were using **raw resume data** (incorrect)
- Embeddings need to be regenerated from **enriched AI analysis** anyway
- No data loss of actual candidate information (stored in Firestore)
- 17,969 candidates will be re-embedded with correct enriched profiles

## Next Steps After Migration

1. Verify hh-embed-svc responds successfully (test script above)
2. Run parallel re-embedding for 17,969 enriched candidates
3. Run parallel enrichment for 11,173 remaining candidates
4. Verify embedding quality

---

**SQL Script Location**: `/Volumes/Extreme Pro/myprojects/headhunter/scripts/sql/fix_embedding_dimensions.sql`
