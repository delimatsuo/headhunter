---
description: How to import new candidates from CSV and process them through the full pipeline
---

# Upload New Candidates from CSV

This workflow imports candidates from an ATS CSV export and processes them through classification, enrichment, and embedding generation.

// turbo-all

## Prerequisites

- CSV file from ATS (new format with columns: Name, Email, Experiences, Social profiles, etc.)
- Python 3.9+ with firebase-admin installed
- Node.js 18+ for classification

## Step 1: Import CSV to Firestore

```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter"

# Dry run first (preview what will be imported)
python3 scripts/import_new_csv_format.py --file "/path/to/your/candidates.csv" --dry-run --limit 50

# Full import
python3 scripts/import_new_csv_format.py --file "/path/to/your/candidates.csv"
```

**What it does:**
- Parses CSV with Title Case headers (Name, Email, Experiences, Social profiles)
- Extracts LinkedIn URL from "Social profiles" text field
- Parses experience text to get current title/company
- Deduplicates by email (skips if already in DB)
- Skips disqualified candidates
- Sets `processing.needs_classification = true` for pipeline

## Step 2: Deduplicate by LinkedIn URL

After import, remove duplicates using LinkedIn URL as unique identifier:

```bash
# Dry run to see duplicates
python3 scripts/deduplicate_by_linkedin.py --dry-run

# Delete older duplicates (keeps newest)
python3 scripts/deduplicate_by_linkedin.py
```

## Step 3: Run LLM Classification

Classifies candidates by function, level, and specialty:

```bash
cd functions

# Edit scripts/run-backfill.js to set batch count (line ~255)
# Set: runBackfill(50, null, 30)  # 30 batches = ~1500 candidates

node scripts/run-backfill.js > /tmp/backfill.log 2>&1 &
tail -f /tmp/backfill.log
```

## Step 4: Run Enrichment (Optional but Recommended)

Uses LLM to analyze career trajectory and generate deeper insights:

```bash
# Via Cloud Function (preferred)
curl -X POST "https://us-central1-headhunter-ai-0088.cloudfunctions.net/batchEnrichCandidates?batchSize=50&force=false"

# Or queue candidates for enrichment
python3 scripts/complete_pipeline.py
```

## Step 5: Generate Embeddings for Search

Creates vector embeddings for semantic search:

```bash
python3 scripts/reembed_enriched_candidates.py > /tmp/embeddings.log 2>&1 &
tail -f /tmp/embeddings.log
```

## Quick One-Liner (Full Pipeline)

```bash
# Import -> Dedupe -> Classify -> Enrich -> Embed
python3 scripts/import_new_csv_format.py --file "/path/to/candidates.csv" && \
python3 scripts/deduplicate_by_linkedin.py && \
cd functions && node scripts/run-backfill.js && cd .. && \
python3 scripts/reembed_enriched_candidates.py
```

## Monitoring Progress

```bash
# Check running processes
ps aux | grep -E "(run-backfill|reembed|import)" | grep -v grep

# Check classification logs
tail -f /tmp/backfill.log

# Check embedding logs
tail -f /tmp/embeddings.log

# Get pipeline stats
python3 -c "
import firebase_admin
from firebase_admin import credentials, firestore
firebase_admin.initialize_app()
db = firestore.client()
print('Total:', sum(1 for _ in db.collection('candidates').stream()))
"
```

## CSV Format Expected

New ATS export format with these columns:
- Name, Email, Phone
- Job title (role applied for)
- Job location
- Experiences (pipe-separated work history)
- Educations
- Social profiles (contains LinkedIn URL)
- Stage, Tags, Source
- Disqualified (Yes/No)

## Troubleshooting

**Import skips too many candidates:**
- Check if they're already in DB (duplicate email)
- Check if they're disqualified in CSV

**Classification fails:**
- Check Gemini API quota
- Reduce batch size in run-backfill.js

**Embeddings not generating:**
- Check hh-embed-svc is deployed
- Check auth token is valid
