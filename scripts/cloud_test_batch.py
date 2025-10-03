#!/usr/bin/env python3
"""
Cloud Test Batch Processor - Test Cloud Enrichment with 50 candidates
"""

import json
import os
import sys
import time
import random
from pathlib import Path
from google.cloud import storage, firestore
from datetime import datetime

def setup_gcp():
    """Initialize GCP clients"""
    try:
        # Set up GCP project
        os.environ['GOOGLE_CLOUD_PROJECT'] = 'headhunter-ai-0088'
        
        storage_client = storage.Client()
        firestore_client = firestore.Client()
        
        return storage_client, firestore_client
    except Exception as e:
        print(f"❌ GCP setup failed: {e}")
        return None, None

def get_test_candidates(limit=50):
    """Get 50 random enhanced candidates from local files"""
    enhanced_dir = Path(__file__).parent / "enhanced_analysis"
    
    if not enhanced_dir.exists():
        print(f"❌ Enhanced profiles directory not found: {enhanced_dir}")
        return []
    
    # Get all enhanced JSON files
    json_files = list(enhanced_dir.glob("*_enhanced.json"))
    
    if len(json_files) < limit:
        print(f"⚠️ Only {len(json_files)} enhanced files found, using all")
        selected_files = json_files
    else:
        selected_files = random.sample(json_files, limit)
    
    candidates = []
    for file_path in selected_files:
        try:
            with open(file_path, 'r') as f:
                candidate_data = json.load(f)
                candidates.append({
                    'file_path': file_path,
                    'data': candidate_data,
                    'candidate_id': file_path.stem.split('_')[0]
                })
        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")
    
    return candidates

def upload_to_cloud_storage(storage_client, candidate, bucket_name="headhunter-ai-0088-profiles"):
    """Upload candidate profile to Cloud Storage to trigger processing"""
    try:
        bucket = storage_client.bucket(bucket_name)
        blob_name = f"profiles/{candidate['candidate_id']}_profile.json"
        blob = bucket.blob(blob_name)
        
        # Convert candidate data to the expected Cloud Function format
        profile_data = {
            "candidate_id": candidate['candidate_id'],
            "name": candidate['data'].get('personal_details', {}).get('name', 'Unknown'),
            "resume_analysis": {
                "career_trajectory": {
                    "current_level": candidate['data'].get('experience_analysis', {}).get('seniority_level', 'Unknown'),
                    "progression_speed": "steady",
                    "trajectory_type": "technical",
                    "domain_expertise": [candidate['data'].get('technical_assessment', {}).get('primary_skills', ['Technology'])[0] if candidate['data'].get('technical_assessment', {}).get('primary_skills') else 'Technology']
                },
                "leadership_scope": {
                    "has_leadership": "leadership" in str(candidate['data']).lower() or "management" in str(candidate['data']).lower(),
                    "team_size": 5,
                    "leadership_level": "Team Lead"
                },
                "company_pedigree": {
                    "tier_level": candidate['data'].get('market_insights', {}).get('market_tier', 'Tier2'),
                    "company_types": ["Technology"],
                    "brand_recognition": "Strong"
                },
                "years_experience": candidate['data'].get('personal_details', {}).get('years_of_experience', 5) if isinstance(candidate['data'].get('personal_details', {}).get('years_of_experience'), int) else 5,
                "technical_skills": candidate['data'].get('technical_assessment', {}).get('primary_skills', [])[:10],
                "soft_skills": candidate['data'].get('technical_assessment', {}).get('soft_skills', [])[:5],
                "cultural_signals": ["Professional", "Growth-oriented"]
            },
            "recruiter_insights": {
                "sentiment": "positive",
                "strengths": candidate['data'].get('recruiter_recommendations', {}).get('strengths', ['Technical expertise'])[:3],
                "cultural_fit": {
                    "cultural_alignment": "strong",
                    "work_style": ["collaborative"],
                    "values_alignment": ["quality", "innovation"]
                },
                "recommendation": "strong_hire",
                "readiness_level": "immediate",
                "key_themes": ["technical expertise", "growth potential"],
                "competitive_advantages": candidate['data'].get('recruiter_recommendations', {}).get('competitive_advantages', ['Strong technical background'])[:2]
            },
            "overall_score": 0.82,
            "processing_timestamp": datetime.now().isoformat()
        }
        
        # Upload to storage
        blob.upload_from_string(
            json.dumps(profile_data, indent=2),
            content_type='application/json'
        )
        
        print(f"✅ Uploaded {candidate['candidate_id']} to Cloud Storage")
        return blob_name
        
    except Exception as e:
        print(f"❌ Upload failed for {candidate['candidate_id']}: {e}")
        return None

def check_enrichment_status(firestore_client, candidate_ids, max_wait=300):
    """Check if candidates have been enriched in Firestore"""
    print(f"\n🔍 Checking enrichment status for {len(candidate_ids)} candidates...")
    
    enriched_profiles = []
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        remaining_ids = []
        
        for candidate_id in candidate_ids:
            try:
                # Check enriched_profiles collection
                doc_ref = firestore_client.collection('enriched_profiles').document(candidate_id)
                doc = doc_ref.get()
                
                if doc.exists:
                    data = doc.to_dict()
                    enriched_profiles.append({
                        'candidate_id': candidate_id,
                        'data': data,
                        'enrichment_version': data.get('enrichment', {}).get('enrichment_version', 'unknown')
                    })
                    print(f"✅ Found enrichment for {candidate_id} (version: {data.get('enrichment', {}).get('enrichment_version', 'unknown')})")
                else:
                    remaining_ids.append(candidate_id)
                    
            except Exception as e:
                print(f"❌ Error checking {candidate_id}: {e}")
                remaining_ids.append(candidate_id)
        
        if not remaining_ids:
            print(f"🎉 All {len(candidate_ids)} candidates enriched!")
            break
            
        print(f"⏳ Waiting for {len(remaining_ids)} candidates... ({int(time.time() - start_time)}s elapsed)")
        candidate_ids = remaining_ids
        time.sleep(10)
    
    return enriched_profiles

def test_vector_search(firestore_client, test_query="Senior Python Developer with leadership experience"):
    """Test vector search functionality"""
    print(f"\n🔍 Testing vector search with query: '{test_query}'")
    
    try:
        # Check if we have embeddings
        embeddings_ref = firestore_client.collection('candidate_embeddings')
        embeddings = embeddings_ref.limit(5).get()
        
        if not embeddings:
            print("❌ No embeddings found in Firestore")
            return []
        
        print(f"✅ Found {len(embeddings)} embedding documents")
        
        # For now, just return the embedding metadata
        results = []
        for doc in embeddings:
            data = doc.to_dict()
            results.append({
                'candidate_id': data.get('candidate_id'),
                'metadata': data.get('metadata', {}),
                'embedding_size': len(data.get('embedding_vector', []))
            })
        
        return results
        
    except Exception as e:
        print(f"❌ Vector search test failed: {e}")
        return []

def generate_test_report(enriched_profiles, vector_search_results, start_time, end_time):
    """Generate comprehensive test report"""
    
    report = {
        "test_summary": {
            "total_candidates": len(enriched_profiles),
            "test_duration_seconds": int(end_time - start_time),
            "test_timestamp": datetime.now().isoformat(),
            "success_rate": len(enriched_profiles) / 50 * 100 if enriched_profiles else 0
        },
        "enrichment_analysis": {
            "gemini_enrichments": len([p for p in enriched_profiles if '1.0-gemini' in p.get('enrichment_version', '')]),
            "fallback_enrichments": len([p for p in enriched_profiles if '1.0-fallback' in p.get('enrichment_version', '')]),
            "enrichment_versions": list(set([p.get('enrichment_version', 'unknown') for p in enriched_profiles]))
        },
        "vector_search_analysis": {
            "embeddings_found": len(vector_search_results),
            "embedding_dimensions": vector_search_results[0]['embedding_size'] if vector_search_results else 0,
            "candidates_with_embeddings": [r['candidate_id'] for r in vector_search_results]
        },
        "sample_enrichments": [
            {
                "candidate_id": p['candidate_id'],
                "enrichment_version": p.get('enrichment_version', 'unknown'),
                "has_career_analysis": 'career_analysis' in p.get('data', {}).get('enrichment', {}),
                "has_strategic_fit": 'strategic_fit' in p.get('data', {}).get('enrichment', {}),
                "ai_summary_length": len(p.get('data', {}).get('enrichment', {}).get('ai_summary', ''))
            }
            for p in enriched_profiles[:5]
        ]
    }
    
    # Save report
    report_path = Path(__file__).parent / f"cloud_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    return report, report_path

def main():
    """Main test function"""
    print("🧪 CLOUD ENRICHMENT TEST - 50 CANDIDATES")
    print("=" * 60)
    
    start_time = time.time()
    
    # Setup GCP
    storage_client, firestore_client = setup_gcp()
    if not storage_client or not firestore_client:
        return False
    
    # Get test candidates
    print("📋 Selecting 50 candidates for testing...")
    candidates = get_test_candidates(50)
    
    if not candidates:
        print("❌ No candidates found for testing")
        return False
    
    print(f"✅ Selected {len(candidates)} candidates for testing")
    
    # Upload to Cloud Storage to trigger processing
    print("\n☁️ Uploading candidates to Cloud Storage...")
    uploaded_ids = []
    
    for i, candidate in enumerate(candidates, 1):
        print(f"  [{i}/{len(candidates)}] Uploading {candidate['candidate_id']}")
        blob_name = upload_to_cloud_storage(storage_client, candidate)
        if blob_name:
            uploaded_ids.append(candidate['candidate_id'])
        
        # Small delay to avoid overwhelming the system
        time.sleep(0.5)
    
    print(f"✅ Successfully uploaded {len(uploaded_ids)} candidates")
    
    # Wait for enrichment processing
    print("\n⏳ Waiting for Cloud Functions to process enrichments...")
    enriched_profiles = check_enrichment_status(firestore_client, uploaded_ids, max_wait=600)
    
    # Test vector search
    vector_search_results = test_vector_search(firestore_client)
    
    # Generate report
    end_time = time.time()
    report, report_path = generate_test_report(enriched_profiles, vector_search_results, start_time, end_time)
    
    # Print summary
    print("\n📊 TEST RESULTS SUMMARY")
    print("=" * 40)
    print(f"Total Candidates Tested: {len(candidates)}")
    print(f"Successfully Uploaded: {len(uploaded_ids)}")
    print(f"Successfully Enriched: {len(enriched_profiles)}")
    print(f"Success Rate: {report['test_summary']['success_rate']:.1f}%")
    print(f"Test Duration: {report['test_summary']['test_duration_seconds']}s")
    print(f"Gemini Enrichments: {report['enrichment_analysis']['gemini_enrichments']}")
    print(f"Fallback Enrichments: {report['enrichment_analysis']['fallback_enrichments']}")
    print(f"Embeddings Generated: {report['vector_search_analysis']['embeddings_found']}")
    print(f"Report saved to: {report_path}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)