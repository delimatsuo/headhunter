#!/usr/bin/env python3
"""
Direct Cloud Function Test - Test deployed functions directly via HTTP
"""

import json
import os
import sys
import time
import random
from pathlib import Path
import requests
from datetime import datetime

# Cloud Function URLs (update these after deployment)
CLOUD_FUNCTION_URLS = {
    'enrichProfile': 'https://us-central1-headhunter-ai-0088.cloudfunctions.net/enrichProfile',
    'searchCandidates': 'https://us-central1-headhunter-ai-0088.cloudfunctions.net/searchCandidates', 
    'healthCheck': 'https://us-central1-headhunter-ai-0088.cloudfunctions.net/healthCheck',
    'generateAllEmbeddings': 'https://us-central1-headhunter-ai-0088.cloudfunctions.net/generateAllEmbeddings'
}

def get_test_candidates(limit=10):
    """Get 10 candidates for testing (smaller batch for direct testing)"""
    enhanced_dir = Path(__file__).parent / "enhanced_analysis"
    
    if not enhanced_dir.exists():
        print(f"❌ Enhanced profiles directory not found: {enhanced_dir}")
        return []
    
    json_files = list(enhanced_dir.glob("*_enhanced.json"))[:limit]
    
    candidates = []
    for file_path in json_files:
        try:
            with open(file_path, 'r') as f:
                candidate_data = json.load(f)
                
                # Convert to Cloud Function format
                profile_data = {
                    "candidate_id": file_path.stem.split('_')[0],
                    "name": candidate_data.get('personal_details', {}).get('name', 'Test Candidate'),
                    "resume_analysis": {
                        "career_trajectory": {
                            "current_level": candidate_data.get('experience_analysis', {}).get('seniority_level', 'Senior'),
                            "progression_speed": "steady",
                            "trajectory_type": "technical",
                            "domain_expertise": [candidate_data.get('technical_assessment', {}).get('primary_skills', ['Technology'])[0] if candidate_data.get('technical_assessment', {}).get('primary_skills') else 'Technology']
                        },
                        "leadership_scope": {
                            "has_leadership": "leadership" in str(candidate_data).lower(),
                            "team_size": 5,
                            "leadership_level": "Team Lead"
                        },
                        "company_pedigree": {
                            "tier_level": "Tier1",
                            "company_types": ["Technology"],
                            "brand_recognition": "Strong"
                        },
                        "years_experience": 7,
                        "technical_skills": candidate_data.get('technical_assessment', {}).get('primary_skills', [])[:5],
                        "soft_skills": ["Communication", "Leadership", "Problem Solving"]
                    },
                    "recruiter_insights": {
                        "sentiment": "positive",
                        "strengths": ["Technical expertise", "Leadership potential"],
                        "cultural_fit": {
                            "cultural_alignment": "strong"
                        },
                        "recommendation": "strong_hire",
                        "readiness_level": "immediate",
                        "key_themes": ["technical excellence"]
                    },
                    "overall_score": 0.85
                }
                
                candidates.append(profile_data)
                
        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")
    
    return candidates

def test_health_check():
    """Test the health check function"""
    print("🏥 Testing Health Check...")
    
    try:
        response = requests.post(CLOUD_FUNCTION_URLS['healthCheck'], 
                               json={'data': {}}, 
                               timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Health Check passed")
            print(f"   Status: {result.get('result', {}).get('status', 'unknown')}")
            return True
        else:
            print(f"❌ Health Check failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Health Check error: {e}")
        return False

def test_enrichment(candidates):
    """Test profile enrichment"""
    print(f"🧠 Testing Profile Enrichment with {len(candidates)} candidates...")
    
    enriched_results = []
    
    for i, candidate in enumerate(candidates, 1):
        print(f"  [{i}/{len(candidates)}] Enriching {candidate['candidate_id']}")
        
        try:
            payload = {'data': {'profile': candidate}}
            response = requests.post(CLOUD_FUNCTION_URLS['enrichProfile'], 
                                   json=payload, 
                                   timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                enriched_profile = result.get('result', {}).get('enriched_profile', {})
                
                enrichment_version = enriched_profile.get('enrichment', {}).get('enrichment_version', 'unknown')
                print(f"    ✅ Success (version: {enrichment_version})")
                
                enriched_results.append({
                    'candidate_id': candidate['candidate_id'],
                    'enrichment_version': enrichment_version,
                    'data': enriched_profile,
                    'has_career_analysis': 'career_analysis' in enriched_profile.get('enrichment', {}),
                    'has_strategic_fit': 'strategic_fit' in enriched_profile.get('enrichment', {}),
                    'ai_summary_length': len(enriched_profile.get('enrichment', {}).get('ai_summary', ''))
                })
                
            else:
                print(f"    ❌ Failed: {response.status_code}")
                print(f"    Response: {response.text[:200]}...")
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
        
        # Small delay between requests
        time.sleep(1)
    
    return enriched_results

def test_search():
    """Test candidate search"""
    print("🔍 Testing Candidate Search...")
    
    try:
        search_query = {
            'query': {
                'min_years_experience': 5,
                'current_level': 'Senior'
            },
            'limit': 10
        }
        
        payload = {'data': search_query}
        response = requests.post(CLOUD_FUNCTION_URLS['searchCandidates'], 
                               json=payload, 
                               timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            candidates = result.get('result', {}).get('candidates', [])
            print(f"✅ Search successful - found {len(candidates)} candidates")
            return candidates
        else:
            print(f"❌ Search failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Search error: {e}")
        return []

def test_embeddings():
    """Test embeddings generation"""
    print("🧮 Testing Embeddings Generation...")
    
    try:
        payload = {'data': {}}
        response = requests.post(CLOUD_FUNCTION_URLS['generateAllEmbeddings'], 
                               json=payload, 
                               timeout=300)  # 5 minutes timeout
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Embeddings generation triggered")
            print(f"   Message: {result.get('message', 'No message')}")
            return True
        else:
            print(f"❌ Embeddings failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Embeddings error: {e}")
        return False

def generate_test_report(health_status, enrichment_results, search_results, embeddings_status):
    """Generate test report"""
    
    gemini_count = len([r for r in enrichment_results if '1.0-gemini' in r.get('enrichment_version', '')])
    fallback_count = len([r for r in enrichment_results if '1.0-fallback' in r.get('enrichment_version', '')])
    
    report = {
        "test_timestamp": datetime.now().isoformat(),
        "health_check": {
            "status": "pass" if health_status else "fail"
        },
        "enrichment_test": {
            "total_tested": len(enrichment_results),
            "success_rate": len(enrichment_results) / 10 * 100,
            "gemini_enrichments": gemini_count,
            "fallback_enrichments": fallback_count,
            "enrichment_versions": list(set([r.get('enrichment_version', 'unknown') for r in enrichment_results]))
        },
        "search_test": {
            "candidates_found": len(search_results),
            "search_successful": len(search_results) > 0
        },
        "embeddings_test": {
            "generation_triggered": embeddings_status
        },
        "sample_enrichments": enrichment_results[:3]
    }
    
    # Save report
    report_path = Path(__file__).parent / f"direct_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    return report, report_path

def main():
    """Main test function"""
    print("🧪 DIRECT CLOUD FUNCTION TEST")
    print("=" * 50)
    
    # Get test candidates
    candidates = get_test_candidates(10)
    if not candidates:
        print("❌ No test candidates available")
        return False
    
    print(f"📋 Testing with {len(candidates)} candidates")
    
    # Run tests
    health_status = test_health_check()
    enrichment_results = test_enrichment(candidates)
    search_results = test_search()
    embeddings_status = test_embeddings()
    
    # Generate report
    report, report_path = generate_test_report(health_status, enrichment_results, search_results, embeddings_status)
    
    # Print summary
    print(f"\n📊 TEST RESULTS SUMMARY")
    print("=" * 30)
    print(f"Health Check: {'✅ PASS' if health_status else '❌ FAIL'}")
    print(f"Enrichment Success Rate: {report['enrichment_test']['success_rate']:.1f}%")
    print(f"Gemini Enrichments: {report['enrichment_test']['gemini_enrichments']}")
    print(f"Fallback Enrichments: {report['enrichment_test']['fallback_enrichments']}")
    print(f"Search Results: {report['search_test']['candidates_found']} candidates found")
    print(f"Embeddings: {'✅ Triggered' if embeddings_status else '❌ Failed'}")
    print(f"Report saved to: {report_path}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)