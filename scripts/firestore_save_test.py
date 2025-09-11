#!/usr/bin/env python3
"""
Simple test to verify we can save processed data to Firestore
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# Add cloud_run_worker to path
sys.path.append('cloud_run_worker')
from config import Config

try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
    print("✅ Firestore library available")
except ImportError:
    FIRESTORE_AVAILABLE = False
    print("❌ Firestore library not available")

async def test_firestore_save():
    """Test saving a processed candidate to Firestore"""
    
    # Set up configuration
    os.environ['GOOGLE_CLOUD_PROJECT'] = 'headhunter-ai-0088'
    config = Config()
    
    print(f"🔧 Configuration loaded for project: {config.project_id}")
    
    if not FIRESTORE_AVAILABLE:
        print("❌ Cannot test Firestore - library not available")
        return False
    
    try:
        # Initialize Firestore client
        db = firestore.Client()
        print("✅ Firestore client initialized")
        
        # Create a test processed candidate profile (like what Together AI would generate)
        test_candidate = {
            'candidate_id': 'test_candidate_001',
            'name': 'Test Candidate from Together AI',
            'career_trajectory': {
                'current_level': 'senior',
                'progression_speed': 'fast',
                'years_experience': 8
            },
            'leadership_scope': {
                'has_leadership': True,
                'leadership_level': 'manager'
            },
            'technical_skills': {
                'core_competencies': ['Python', 'AWS', 'Machine Learning'],
                'skill_depth': 'expert'
            },
            'company_pedigree': {
                'companies': ['Google', 'Meta'],
                'company_tier': 'enterprise'
            },
            'executive_summary': {
                'one_line_pitch': 'Senior AI engineer with leadership experience',
                'overall_rating': 89
            },
            'search_keywords': ['python', 'machine learning', 'leadership'],
            'metadata': {
                'processed_at': datetime.now().isoformat(),
                'processor': 'together_ai_test',
                'model': 'meta-llama/Llama-3.2-3B-Instruct-Turbo',
                'version': '2.0'
            },
            'source': 'end_to_end_test'
        }
        
        # Save to enhanced_candidates collection (for new system)
        print("💾 Saving to enhanced_candidates collection...")
        doc_ref = db.collection('enhanced_candidates').document(test_candidate['candidate_id'])
        doc_ref.set(test_candidate)
        print("✅ Saved to enhanced_candidates collection")
        
        # Also save to candidates collection (for compatibility)
        print("💾 Saving to candidates collection...")
        doc_ref2 = db.collection('candidates').document(test_candidate['candidate_id'])
        doc_ref2.set(test_candidate)
        print("✅ Saved to candidates collection")
        
        # Verify we can read it back
        print("🔍 Verifying data was saved...")
        saved_doc = doc_ref.get()
        if saved_doc.exists:
            saved_data = saved_doc.to_dict()
            print(f"✅ Successfully retrieved saved document")
            print(f"   - Candidate: {saved_data.get('name')}")
            print(f"   - Rating: {saved_data.get('executive_summary', {}).get('overall_rating')}")
            print(f"   - Processed at: {saved_data.get('metadata', {}).get('processed_at')}")
            
            return True
        else:
            print("❌ Could not retrieve saved document")
            return False
            
    except Exception as e:
        print(f"❌ Firestore test failed: {e}")
        return False

async def main():
    """Main test execution"""
    print("🚀 Testing Firestore Save Capability")
    print("=" * 50)
    
    success = await test_firestore_save()
    
    if success:
        print("\n🎉 FIRESTORE TEST PASSED!")
        print("✅ We can save processed candidate data to Firestore")
        print("✅ This confirms the end-to-end pipeline can persist data")
        return 0
    else:
        print("\n❌ FIRESTORE TEST FAILED!")
        print("⚠️ The end-to-end pipeline cannot save data")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    print(f"\nFirestore test completed with exit code: {exit_code}")
    sys.exit(exit_code)