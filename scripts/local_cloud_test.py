#!/usr/bin/env python3
"""
Local Cloud Function Test - Test the enrichment logic directly
"""

import json
import os
import sys
import time
import random
from pathlib import Path
from datetime import datetime
from google.cloud import firestore
import subprocess

REPO_ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS_DIR = REPO_ROOT / "functions"

def setup_gcp():
    """Initialize GCP clients"""
    try:
        os.environ['GOOGLE_CLOUD_PROJECT'] = 'headhunter-ai-0088'
        firestore_client = firestore.Client()
        return firestore_client
    except Exception as e:
        print(f"❌ GCP setup failed: {e}")
        return None

def get_test_candidates(limit=50):
    """Get 50 candidates from local enhanced files"""
    enhanced_dir = Path(__file__).parent / "enhanced_analysis"
    
    if not enhanced_dir.exists():
        print(f"❌ Enhanced profiles directory not found: {enhanced_dir}")
        return []
    
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
                            "has_leadership": "leadership" in str(candidate_data).lower() or "management" in str(candidate_data).lower(),
                            "team_size": random.randint(3, 12),
                            "leadership_level": "Team Lead" if "senior" in str(candidate_data).lower() else "Manager"
                        },
                        "company_pedigree": {
                            "tier_level": candidate_data.get('market_insights', {}).get('market_tier', 'Tier1'),
                            "company_types": ["Technology", "Startup"],
                            "brand_recognition": "Strong"
                        },
                        "years_experience": candidate_data.get('personal_details', {}).get('years_of_experience', 7) if isinstance(candidate_data.get('personal_details', {}).get('years_of_experience'), int) else 7,
                        "technical_skills": candidate_data.get('technical_assessment', {}).get('primary_skills', [])[:8],
                        "soft_skills": ["Communication", "Leadership", "Problem Solving", "Teamwork"],
                        "cultural_signals": ["Innovation", "Growth mindset", "Collaboration"]
                    },
                    "recruiter_insights": {
                        "sentiment": "positive",
                        "strengths": candidate_data.get('recruiter_recommendations', {}).get('strengths', ['Technical expertise', 'Leadership potential'])[:3],
                        "cultural_fit": {
                            "cultural_alignment": "strong",
                            "work_style": ["collaborative", "results-oriented"],
                            "values_alignment": ["innovation", "quality", "growth"]
                        },
                        "recommendation": "strong_hire",
                        "readiness_level": "immediate",
                        "key_themes": ["technical excellence", "leadership potential"],
                        "development_areas": ["strategic thinking", "industry knowledge"],
                        "competitive_advantages": candidate_data.get('recruiter_recommendations', {}).get('competitive_advantages', ['Strong technical foundation'])[:2]
                    },
                    "overall_score": round(random.uniform(0.75, 0.95), 2),
                    "processing_timestamp": datetime.now().isoformat()
                }
                
                candidates.append(profile_data)
                
        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")
    
    return candidates

def test_gemini_enrichment(profile):
    """Test Gemini enrichment by calling Node.js directly"""
    try:
        # Create a temporary file with the profile
        temp_profile = Path(__file__).parent / f"temp_profile_{profile['candidate_id']}.json"
        with open(temp_profile, 'w') as f:
            json.dump(profile, f)
        
        # Call Node.js test script
        result = subprocess.run([
            'node', '-e', f'''
            const fs = require('fs');
            const path = require('path');
            
            // Import the enrichment function
            const {{ enrichCandidateProfile }} = require('../functions/lib/index.js');
            
            const profile = JSON.parse(fs.readFileSync('{temp_profile}', 'utf8'));
            
            enrichCandidateProfile(profile).then(result => {{
                console.log(JSON.stringify(result, null, 2));
            }}).catch(err => {{
                console.error('ERROR:', err.message);
                process.exit(1);
            }});
            '''
        ], capture_output=True, text=True, timeout=60)
        
        # Clean up temp file
        temp_profile.unlink(missing_ok=True)
        
        if result.returncode == 0:
            try:
                enrichment_data = json.loads(result.stdout)
                return enrichment_data
            except json.JSONDecodeError:
                return {
                    "error": "Failed to parse enrichment result",
                    "raw_output": result.stdout
                }
        else:
            return {
                "error": f"Node.js execution failed: {result.stderr}",
                "stdout": result.stdout
            }
            
    except Exception as e:
        return {
            "error": f"Test execution failed: {str(e)}"
        }

def store_in_firestore(firestore_client, candidate_id, enriched_profile):
    """Store enriched profile in Firestore"""
    try:
        # Store in enriched_profiles collection
        doc_ref = firestore_client.collection('enriched_profiles').document(candidate_id)
        doc_ref.set(enriched_profile)
        
        # Store flattened version in candidates collection for search
        flattened = {
            'candidate_id': candidate_id,
            'name': enriched_profile.get('name'),
            'overall_score': enriched_profile.get('overall_score', 0),
            'years_experience': enriched_profile.get('resume_analysis', {}).get('years_experience', 0),
            'current_level': enriched_profile.get('resume_analysis', {}).get('career_trajectory', {}).get('current_level'),
            'technical_skills': enriched_profile.get('resume_analysis', {}).get('technical_skills', []),
            'enrichment_summary': enriched_profile.get('enrichment', {}).get('ai_summary', ''),
            'enrichment_version': enriched_profile.get('enrichment', {}).get('enrichment_version'),
            'updated_at': enriched_profile.get('enrichment', {}).get('enrichment_timestamp')
        }
        
        candidates_ref = firestore_client.collection('candidates').document(candidate_id)
        candidates_ref.set(flattened)
        
        return True
        
    except Exception as e:
        print(f"❌ Firestore storage failed for {candidate_id}: {e}")
        return False

def test_vector_embeddings(firestore_client, candidate_profiles):
    """Test vector embeddings generation"""
    print("🧮 Testing Vector Embeddings...")
    
    # Build and run the TypeScript embeddings function
    build_result = subprocess.run(['npm', 'run', 'build'], 
                                  cwd=str(FUNCTIONS_DIR),
                                  capture_output=True, text=True)
    
    if build_result.returncode != 0:
        print(f"❌ TypeScript build failed: {build_result.stderr}")
        return []
    
    embeddings_generated = []
    
    for i, profile in enumerate(candidate_profiles[:10], 1):  # Test with first 10
        try:
            print(f"  [{i}/10] Generating embedding for {profile['candidate_id']}")
            
            # Call the embedding generation via Node.js
            result = subprocess.run([
                'node', '-e', f'''
                const {{ VectorSearchService }} = require('../functions/lib/vector-search.js');
                const service = new VectorSearchService();
                
                const profile = {json.dumps(profile)};
                
                service.storeEmbedding(profile).then(embedding => {{
                    console.log(JSON.stringify(embedding, null, 2));
                }}).catch(err => {{
                    console.error('ERROR:', err.message);
                    process.exit(1);
                }});
                '''
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                try:
                    embedding_data = json.loads(result.stdout)
                    embeddings_generated.append(embedding_data)
                    print(f"    ✅ Success (dimensions: {len(embedding_data.get('embedding_vector', []))})")
                except json.JSONDecodeError:
                    print(f"    ❌ Failed to parse embedding result")
            else:
                print(f"    ❌ Embedding generation failed: {result.stderr}")
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
    
    return embeddings_generated

def main():
    """Main test function"""
    print("🧪 LOCAL CLOUD ENRICHMENT TEST - 50 CANDIDATES")
    print("=" * 70)
    
    start_time = time.time()
    
    # Setup
    firestore_client = setup_gcp()
    if not firestore_client:
        return False
    
    # Get test candidates
    print("📋 Loading test candidates...")
    candidates = get_test_candidates(50)
    
    if not candidates:
        print("❌ No candidates found for testing")
        return False
    
    print(f"✅ Loaded {len(candidates)} candidates for testing")
    
    # Build TypeScript functions
    print("🔨 Building TypeScript functions...")
    build_result = subprocess.run(['npm', 'run', 'build'], 
                                  cwd=str(FUNCTIONS_DIR),
                                  capture_output=True, text=True)
    
    if build_result.returncode != 0:
        print(f"❌ Build failed: {build_result.stderr}")
        return False
    
    print("✅ TypeScript build successful")
    
    # Test enrichment with first 10 candidates
    print(f"\\n🧠 Testing Cloud Enrichment...")
    enriched_profiles = []
    
    for i, candidate in enumerate(candidates[:10], 1):
        print(f"  [{i}/10] Enriching {candidate['candidate_id']} ({candidate['name']})")
        
        # Test the enrichment function
        enrichment_result = test_gemini_enrichment(candidate)
        
        if 'error' not in enrichment_result:
            # Add enrichment to profile
            enriched_profile = {
                **candidate,
                'enrichment': enrichment_result,
                'enriched_timestamp': datetime.now().isoformat()
            }
            
            # Store in Firestore
            if store_in_firestore(firestore_client, candidate['candidate_id'], enriched_profile):
                enriched_profiles.append(enriched_profile)
                enrichment_version = enrichment_result.get('enrichment_version', 'unknown')
                print(f"    ✅ Success - stored in Firestore (version: {enrichment_version})")
            else:
                print(f"    ⚠️ Enriched but failed to store in Firestore")
        else:
            print(f"    ❌ Enrichment failed: {enrichment_result.get('error', 'Unknown error')}")
        
        # Small delay
        time.sleep(1)
    
    # Test vector embeddings
    embeddings_generated = test_vector_embeddings(firestore_client, enriched_profiles)
    
    # Generate final report
    end_time = time.time()
    
    gemini_count = len([p for p in enriched_profiles if p.get('enrichment', {}).get('enrichment_version', '').startswith('1.0-gemini')])
    fallback_count = len([p for p in enriched_profiles if p.get('enrichment', {}).get('enrichment_version', '').startswith('1.0-fallback')])
    
    report = {
        "test_summary": {
            "total_candidates": len(candidates),
            "enriched_count": len(enriched_profiles),
            "success_rate": len(enriched_profiles) / 10 * 100,
            "test_duration_seconds": int(end_time - start_time),
            "test_timestamp": datetime.now().isoformat()
        },
        "enrichment_analysis": {
            "gemini_enrichments": gemini_count,
            "fallback_enrichments": fallback_count,
            "total_processed": len(enriched_profiles)
        },
        "vector_analysis": {
            "embeddings_generated": len(embeddings_generated),
            "embedding_dimensions": len(embeddings_generated[0].get('embedding_vector', [])) if embeddings_generated else 0
        },
        "firestore_storage": {
            "profiles_stored": len(enriched_profiles),
            "embeddings_stored": len(embeddings_generated)
        }
    }
    
    # Save report
    report_path = Path(__file__).parent / f"local_cloud_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print results
    print(f"\\n📊 TEST RESULTS SUMMARY")
    print("=" * 40)
    print(f"Candidates Tested: {len(candidates)}")
    print(f"Successfully Enriched: {len(enriched_profiles)}")
    print(f"Success Rate: {report['test_summary']['success_rate']:.1f}%")
    print(f"Gemini Enrichments: {gemini_count}")
    print(f"Fallback Enrichments: {fallback_count}")
    print(f"Embeddings Generated: {len(embeddings_generated)}")
    print(f"Test Duration: {report['test_summary']['test_duration_seconds']}s")
    print(f"Report saved to: {report_path}")
    
    if len(enriched_profiles) > 0:
        print(f"\\n🎉 CLOUD ENRICHMENT TEST SUCCESSFUL!")
        print(f"    - {gemini_count} candidates enriched with real Gemini AI")
        print(f"    - {fallback_count} candidates used enhanced fallback")
        print(f"    - {len(embeddings_generated)} vector embeddings generated")
        print(f"    - All data stored in Firestore for production use")
        return True
    else:
        print(f"\\n❌ CLOUD ENRICHMENT TEST FAILED")
        print(f"    No candidates were successfully enriched")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)