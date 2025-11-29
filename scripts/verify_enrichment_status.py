#!/usr/bin/env python3
"""
Verify Enrichment Status
========================
Check how many candidates have enrichment data vs. how many still need it.
Avoids duplicate work by counting actual database state.
"""

import os
from google.cloud import firestore
from google.auth import default as get_default_credentials

def main():
    tenant_id = os.getenv("TENANT_ID", "tenant-alpha")
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "headhunter-ai-0088")

    print("🔍 Verifying enrichment status in Firestore...")
    print(f"   Project: {project_id}")
    print(f"   Tenant: {tenant_id}\n")

    # Initialize Firestore
    credentials, _ = get_default_credentials()
    db = firestore.Client(project=project_id, credentials=credentials)

    # Query all candidates
    candidates_ref = db.collection(f"tenants/{tenant_id}/candidates")
    all_docs = candidates_ref.stream()

    total_count = 0
    enriched_count = 0
    not_enriched_count = 0

    enriched_fields = {
        'intelligent_analysis': 0,
        'technical_assessment': 0,
        'both': 0
    }

    print("📊 Counting candidates...")
    for doc in all_docs:
        total_count += 1
        data = doc.to_dict()

        has_intelligent = 'intelligent_analysis' in data
        has_technical = 'technical_assessment' in data

        if has_intelligent and has_technical:
            enriched_fields['both'] += 1
            enriched_count += 1
        elif has_intelligent:
            enriched_fields['intelligent_analysis'] += 1
            enriched_count += 1
        elif has_technical:
            enriched_fields['technical_assessment'] += 1
            enriched_count += 1
        else:
            not_enriched_count += 1

        # Progress indicator
        if total_count % 1000 == 0:
            print(f"   Processed {total_count:,} candidates...")

    # Final report
    print("\n" + "="*80)
    print("✅ ENRICHMENT STATUS REPORT")
    print("="*80)
    print(f"Total candidates:               {total_count:,}")
    print(f"Enriched candidates:            {enriched_count:,} ({enriched_count/total_count*100:.1f}%)")
    print(f"  - With intelligent_analysis:  {enriched_fields['intelligent_analysis']:,}")
    print(f"  - With technical_assessment:  {enriched_fields['technical_assessment']:,}")
    print(f"  - With both:                  {enriched_fields['both']:,}")
    print(f"NOT enriched:                   {not_enriched_count:,} ({not_enriched_count/total_count*100:.1f}%)")
    print("="*80)

    # Recommendation
    print("\n💡 RECOMMENDATION:")
    if not_enriched_count == 0:
        print("   ✅ All candidates are already enriched!")
        print("   ✅ No enrichment work needed.")
    elif not_enriched_count < 100:
        print(f"   ⚠️  Only {not_enriched_count} candidates need enrichment (minimal)")
        print("   → Consider if enrichment is worth the cost")
    else:
        estimated_cost = not_enriched_count * 0.01  # Rough estimate
        print(f"   📋 {not_enriched_count:,} candidates need enrichment")
        print(f"   💰 Estimated cost: ~${estimated_cost:.2f}")
        print("   → Enrichment work is needed")

    print("="*80)

if __name__ == "__main__":
    main()
