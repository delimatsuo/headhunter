#!/usr/bin/env python3
"""
Upload enriched candidates from local JSON to production Firestore.
Establishes the production flow: Firestore -> Embed Service -> pgvector
"""

import json
import sys
from pathlib import Path
from google.cloud import firestore
from google.auth import default as get_default_credentials

def upload_enriched_candidates():
    """Upload enriched candidates to production Firestore"""

    # Configuration
    project_id = "headhunter-ai-0088"
    tenant_id = "tenant-alpha"
    enriched_file = Path(__file__).parent.parent / "data/enriched/enriched_candidates_full.json"

    if not enriched_file.exists():
        print(f"ERROR: Enriched data file not found: {enriched_file}")
        sys.exit(1)

    # Initialize Firestore
    print(f"Initializing Firestore client for project {project_id}...")
    credentials, _ = get_default_credentials()
    db = firestore.Client(project=project_id, credentials=credentials)

    # Load enriched data
    print(f"Loading enriched data from {enriched_file}...")
    with open(enriched_file, 'r') as f:
        candidates = json.load(f)

    print(f"Found {len(candidates)} enriched candidates")

    if not candidates:
        print("No candidates to upload")
        return

    # Upload in batches
    # Firestore has 10MB transaction size limit
    # Enriched candidates are ~10KB each, so use smaller batches
    batch_size = 20
    success_count = 0
    error_count = 0

    candidates_ref = db.collection(f"tenants/{tenant_id}/candidates")

    total_batches = (len(candidates) + batch_size - 1) // batch_size

    for i in range(0, len(candidates), batch_size):
        batch_num = (i // batch_size) + 1
        print(f"Uploading batch {batch_num}/{total_batches}...")
        batch_data = candidates[i:i + batch_size]
        batch = db.batch()

        for candidate in batch_data:
            candidate_id = candidate.get('candidate_id')
            if not candidate_id:
                print(f"Warning: Skipping candidate without ID: {candidate.get('name', 'Unknown')}")
                error_count += 1
                continue

            doc_ref = candidates_ref.document(candidate_id)

            # Add metadata
            candidate['updated_at'] = firestore.SERVER_TIMESTAMP
            candidate['enrichment_version'] = 'v1'

            batch.set(doc_ref, candidate, merge=True)
            success_count += 1

        try:
            batch.commit()
        except Exception as e:
            print(f"ERROR committing batch {i // batch_size + 1}: {e}")
            error_count += len(batch_data)
            success_count -= len(batch_data)

    print(f"\n{'='*60}")
    print(f"Upload complete!")
    print(f"Success: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Total: {len(candidates)}")
    print(f"{'='*60}")

if __name__ == "__main__":
    upload_enriched_candidates()
