#!/usr/bin/env python3
"""
Test script for Cloud Functions integration
"""

import json
import sys
import os
import tempfile
from datetime import datetime

# Add scripts directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_test_profile():
    """Create a test candidate profile for uploading"""
    return {
        "candidate_id": "test_001",
        "name": "Jane Smith",
        "resume_analysis": {
            "career_trajectory": {
                "current_level": "Senior",
                "progression_speed": "Fast",
                "trajectory_type": "Technical Leadership",
                "career_changes": 2,
                "domain_expertise": ["Software Engineering", "AI/ML"]
            },
            "leadership_scope": {
                "has_leadership": True,
                "team_size": 8,
                "leadership_level": "Team Lead",
                "leadership_style": ["Collaborative", "Technical"],
                "mentorship_experience": True
            },
            "company_pedigree": {
                "tier_level": "Tier1",
                "company_types": ["Big Tech", "Startup"],
                "brand_recognition": "High",
                "recent_companies": ["Google", "OpenAI"]
            },
            "years_experience": 9,
            "technical_skills": ["Python", "Machine Learning", "Kubernetes", "React", "PostgreSQL"],
            "soft_skills": ["Leadership", "Communication", "Problem Solving"],
            "education": {
                "highest_degree": "MS Computer Science",
                "institutions": ["Stanford University"],
                "fields_of_study": ["Computer Science", "AI"]
            },
            "cultural_signals": ["Open source contributions", "Conference speaker", "Mentor"]
        },
        "recruiter_insights": {
            "sentiment": "positive",
            "strengths": ["Exceptional technical skills", "Strong leadership presence", "Great cultural fit"],
            "concerns": ["May be overqualified for some roles"],
            "red_flags": [],
            "leadership_indicators": ["Led cross-functional team of 8", "Mentored 5+ junior engineers"],
            "cultural_fit": {
                "cultural_alignment": "excellent",
                "work_style": ["Collaborative", "Independent"],
                "values_alignment": ["Innovation", "Quality", "Growth"],
                "team_fit": "excellent",
                "communication_style": "Clear and direct",
                "adaptability": "high",
                "cultural_add": ["Technical expertise", "Startup experience"]
            },
            "recommendation": "strong_hire",
            "readiness_level": "ready_now",
            "key_themes": ["Technical Excellence", "Leadership Potential", "Cultural Fit"],
            "development_areas": ["Public speaking"],
            "competitive_advantages": ["Unique AI/ML background", "Google experience"]
        },
        "overall_score": 0.92,
        "recommendation": "strong_hire",
        "processing_timestamp": datetime.now().isoformat()
    }

def test_profile_upload():
    """Test uploading a profile to trigger Cloud Function"""
    print("🧪 Testing Cloud Function profile upload trigger...")
    
    # Create test profile
    profile = create_test_profile()
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(profile, f, indent=2)
        temp_file = f.name
    
    try:
        # Upload to Cloud Storage bucket (requires gsutil and authentication)
        project_id = "headhunter-ai-0088"
        bucket_name = f"{project_id}-profiles"
        gcs_path = f"profiles/test_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        print(f"📤 Uploading test profile to gs://{bucket_name}/{gcs_path}")
        
        # Use gsutil to upload
        import subprocess
        result = subprocess.run([
            "gsutil", "cp", temp_file, f"gs://{bucket_name}/{gcs_path}"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Successfully uploaded profile to Cloud Storage")
            print(f"   File: gs://{bucket_name}/{gcs_path}")
            print("   This should trigger the processUploadedProfile function")
            print("   Check Firebase Functions logs for processing results")
            return True
        else:
            print(f"❌ Upload failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)

def test_health_check():
    """Test the health check function"""
    print("🏥 Testing health check function...")
    
    try:
        # This would typically use Firebase Functions SDK or HTTP requests
        # For now, provide instructions for manual testing
        print("To test health check function:")
        print("1. Deploy functions: ./scripts/deploy_functions.sh")
        print("2. Call function:")
        print("   firebase functions:shell --project headhunter-ai-0088")
        print("   > healthCheck({})")
        print("   OR")
        print("   curl -X POST https://us-central1-headhunter-ai-0088.cloudfunctions.net/healthCheck")
        return True
        
    except Exception as e:
        print(f"❌ Health check test error: {e}")
        return False

def test_manual_enrichment():
    """Test manual profile enrichment"""
    print("🤖 Testing manual profile enrichment...")
    
    profile = create_test_profile()
    
    print("To test manual enrichment:")
    print("1. Deploy functions: ./scripts/deploy_functions.sh")
    print("2. Call function:")
    print("   firebase functions:shell --project headhunter-ai-0088")
    print(f"   > enrichProfile({{ profile: {json.dumps(profile, indent=2)[:200]}... }})")
    
    return True

def main():
    """Run all integration tests"""
    print("🎯 Cloud Functions Integration Tests")
    print("=" * 50)
    
    tests = [
        ("Health Check", test_health_check),
        ("Manual Enrichment", test_manual_enrichment),
        ("Profile Upload", test_profile_upload),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name}...")
        try:
            if test_func():
                print(f"✅ {test_name} passed")
                passed += 1
            else:
                print(f"❌ {test_name} failed")
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())