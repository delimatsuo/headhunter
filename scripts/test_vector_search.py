#!/usr/bin/env python3
"""
Test script for Vector Search functionality
"""

import sys
import os
import json
import tempfile
from datetime import datetime
from pathlib import Path

def create_test_profiles():
    """Create diverse test candidate profiles for vector search testing"""
    
    profiles = [
        {
            "candidate_id": "vector_test_001",
            "name": "Alice Chen",
            "resume_analysis": {
                "career_trajectory": {
                    "current_level": "Senior",
                    "progression_speed": "Fast",
                    "trajectory_type": "Technical Leadership",
                    "career_changes": 2,
                    "domain_expertise": ["Machine Learning", "Cloud Architecture"]
                },
                "leadership_scope": {
                    "has_leadership": True,
                    "team_size": 8,
                    "leadership_level": "Team Lead",
                    "leadership_style": ["Technical", "Collaborative"],
                    "mentorship_experience": True
                },
                "company_pedigree": {
                    "tier_level": "Tier1",
                    "company_types": ["Big Tech", "AI Company"],
                    "brand_recognition": "High",
                    "recent_companies": ["Google", "OpenAI"]
                },
                "years_experience": 9,
                "technical_skills": ["Python", "TensorFlow", "Kubernetes", "AWS", "PostgreSQL"],
                "soft_skills": ["Leadership", "Problem Solving", "Communication"],
                "education": {
                    "highest_degree": "PhD Computer Science",
                    "institutions": ["MIT"],
                    "fields_of_study": ["Machine Learning", "Distributed Systems"]
                },
                "cultural_signals": ["Research publications", "Open source contributor", "Conference speaker"]
            },
            "recruiter_insights": {
                "sentiment": "positive",
                "strengths": ["Exceptional technical depth", "Strong leadership", "Research background"],
                "concerns": ["May be overqualified for some roles"],
                "red_flags": [],
                "leadership_indicators": ["Led ML platform team", "Published 10+ papers"],
                "cultural_fit": {
                    "cultural_alignment": "excellent",
                    "work_style": ["Independent", "Collaborative"],
                    "values_alignment": ["Innovation", "Excellence", "Learning"],
                    "team_fit": "excellent",
                    "communication_style": "Clear and technical",
                    "adaptability": "high",
                    "cultural_add": ["Research expertise", "Technical thought leadership"]
                },
                "recommendation": "strong_hire",
                "readiness_level": "ready_now",
                "key_themes": ["Technical Excellence", "ML Expertise", "Leadership"],
                "development_areas": ["Business strategy"],
                "competitive_advantages": ["Unique ML research background", "Big tech experience"]
            },
            "overall_score": 0.95,
            "recommendation": "strong_hire"
        },
        {
            "candidate_id": "vector_test_002", 
            "name": "Bob Rodriguez",
            "resume_analysis": {
                "career_trajectory": {
                    "current_level": "Mid",
                    "progression_speed": "Moderate",
                    "trajectory_type": "Full-Stack Development",
                    "career_changes": 1,
                    "domain_expertise": ["Frontend Development", "Mobile Apps"]
                },
                "leadership_scope": {
                    "has_leadership": False,
                    "team_size": 0,
                    "leadership_level": "Individual Contributor",
                    "mentorship_experience": False
                },
                "company_pedigree": {
                    "tier_level": "Tier2",
                    "company_types": ["Startup", "E-commerce"],
                    "brand_recognition": "Medium",
                    "recent_companies": ["Shopify", "Local startup"]
                },
                "years_experience": 5,
                "technical_skills": ["React", "Node.js", "TypeScript", "MongoDB", "AWS"],
                "soft_skills": ["Problem Solving", "Adaptability", "Creativity"],
                "education": {
                    "highest_degree": "BS Computer Science",
                    "institutions": ["UC Berkeley"],
                    "fields_of_study": ["Computer Science"]
                },
                "cultural_signals": ["Hackathon winner", "Side projects"]
            },
            "recruiter_insights": {
                "sentiment": "positive",
                "strengths": ["Strong frontend skills", "Great problem solver", "Startup experience"],
                "concerns": ["Limited backend experience", "No leadership experience"],
                "red_flags": [],
                "leadership_indicators": [],
                "cultural_fit": {
                    "cultural_alignment": "good",
                    "work_style": ["Independent", "Creative"],
                    "values_alignment": ["Innovation", "Speed"],
                    "team_fit": "good",
                    "communication_style": "Casual and friendly",
                    "adaptability": "very high",
                    "cultural_add": ["Startup agility", "Creative problem solving"]
                },
                "recommendation": "hire",
                "readiness_level": "ready_now",
                "key_themes": ["Frontend Excellence", "Startup Agility"],
                "development_areas": ["Backend skills", "Leadership"],
                "competitive_advantages": ["Full-stack versatility", "Startup experience"]
            },
            "overall_score": 0.78,
            "recommendation": "hire"
        },
        {
            "candidate_id": "vector_test_003",
            "name": "Carol Kim",
            "resume_analysis": {
                "career_trajectory": {
                    "current_level": "Principal",
                    "progression_speed": "Fast",
                    "trajectory_type": "Platform Engineering",
                    "career_changes": 3,
                    "domain_expertise": ["Distributed Systems", "Infrastructure", "Platform Engineering"]
                },
                "leadership_scope": {
                    "has_leadership": True,
                    "team_size": 15,
                    "leadership_level": "Engineering Manager",
                    "leadership_style": ["Technical", "Strategic"],
                    "mentorship_experience": True
                },
                "company_pedigree": {
                    "tier_level": "Tier1",
                    "company_types": ["Big Tech", "Cloud Provider"],
                    "brand_recognition": "High",
                    "recent_companies": ["Amazon", "Microsoft"]
                },
                "years_experience": 12,
                "technical_skills": ["Go", "Kubernetes", "Terraform", "AWS", "Microservices", "Docker"],
                "soft_skills": ["Strategic Thinking", "Leadership", "Technical Communication"],
                "education": {
                    "highest_degree": "MS Computer Engineering",
                    "institutions": ["Stanford"],
                    "fields_of_study": ["Distributed Systems", "Computer Engineering"]
                },
                "cultural_signals": ["Tech blog author", "Platform engineering community leader"]
            },
            "recruiter_insights": {
                "sentiment": "positive",
                "strengths": ["Deep platform expertise", "Proven at scale", "Strong technical leadership"],
                "concerns": ["May require significant compensation"],
                "red_flags": [],
                "leadership_indicators": ["Built platform serving 100M+ users", "Led 15-person team"],
                "cultural_fit": {
                    "cultural_alignment": "excellent",
                    "work_style": ["Strategic", "Collaborative"],
                    "values_alignment": ["Excellence", "Scale", "Reliability"],
                    "team_fit": "excellent", 
                    "communication_style": "Technical and strategic",
                    "adaptability": "high",
                    "cultural_add": ["Platform expertise", "Scale experience"]
                },
                "recommendation": "strong_hire",
                "readiness_level": "ready_now",
                "key_themes": ["Platform Engineering", "Technical Leadership", "Scale"],
                "development_areas": ["Product strategy"],
                "competitive_advantages": ["Unique platform expertise", "Big tech scale experience"]
            },
            "overall_score": 0.92,
            "recommendation": "strong_hire"
        }
    ]
    
    return profiles

def upload_test_profiles():
    """Upload test profiles to trigger Cloud Function processing"""
    print("📤 Uploading test profiles for vector search...")
    
    profiles = create_test_profiles()
    bucket_name = "headhunter-ai-0088-profiles"
    
    uploaded_files = []
    
    for profile in profiles:
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(profile, f, indent=2)
            temp_file = f.name
        
        try:
            # Upload to GCS
            gcs_path = f"profiles/{profile['candidate_id']}.json"
            
            import subprocess
            result = subprocess.run([
                "gsutil", "cp", temp_file, f"gs://{bucket_name}/{gcs_path}"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Uploaded: {profile['name']} ({profile['candidate_id']})")
                uploaded_files.append(gcs_path)
            else:
                print(f"❌ Failed to upload {profile['candidate_id']}: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Upload error for {profile['candidate_id']}: {e}")
        finally:
            # Clean up temp file
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    print(f"\n📊 Uploaded {len(uploaded_files)}/{len(profiles)} test profiles")
    print("⏳ Wait 2-3 minutes for Cloud Functions to process and generate embeddings")
    
    return uploaded_files

def test_semantic_search():
    """Test semantic search with various queries"""
    print("🔍 Testing semantic search functionality...")
    
    # Test queries with expected matches
    test_queries = [
        {
            "query": "Senior machine learning engineer with leadership experience at big tech companies",
            "expected_matches": ["vector_test_001"],
            "description": "Should match Alice Chen (ML + Leadership + Big Tech)"
        },
        {
            "query": "Frontend developer with React and startup experience",
            "expected_matches": ["vector_test_002"],  
            "description": "Should match Bob Rodriguez (React + Startup)"
        },
        {
            "query": "Platform engineering expert with distributed systems and Kubernetes",
            "expected_matches": ["vector_test_003"],
            "description": "Should match Carol Kim (Platform + Distributed Systems)"
        },
        {
            "query": "Technical leader with team management experience",
            "expected_matches": ["vector_test_001", "vector_test_003"],
            "description": "Should match both Alice and Carol (both have leadership)"
        },
        {
            "query": "Full stack developer with modern JavaScript frameworks",
            "expected_matches": ["vector_test_002"],
            "description": "Should match Bob Rodriguez (React/Node.js)"
        }
    ]
    
    print("Test queries to run manually after deployment:")
    print("-" * 50)
    
    for i, query in enumerate(test_queries, 1):
        print(f"{i}. Query: \"{query['query']}\"")
        print(f"   Expected: {query['expected_matches']}")
        print(f"   Description: {query['description']}")
        print()
        
        # Firebase Functions call example
        print("   Firebase Shell Command:")
        print(f"   > semanticSearch({{ query_text: \"{query['query']}\", limit: 5 }})")
        print()
    
    return test_queries

def test_embedding_generation():
    """Test manual embedding generation"""
    print("🧮 Testing embedding generation...")
    
    test_candidates = ["vector_test_001", "vector_test_002", "vector_test_003"]
    
    print("Manual embedding generation commands:")
    print("-" * 40)
    
    for candidate_id in test_candidates:
        print(f"generateEmbedding({{ candidate_id: \"{candidate_id}\" }})")
    
    print("\nVector search statistics command:")
    print("vectorSearchStats({})")
    
    return test_candidates

def create_deployment_validation():
    """Create validation checklist for vector search deployment"""
    
    validation_steps = [
        {
            "step": 1,
            "task": "Deploy Functions",
            "command": "./scripts/deploy_functions.sh",
            "expected": "All functions deployed successfully"
        },
        {
            "step": 2, 
            "task": "Upload Test Profiles",
            "command": "python3 scripts/test_vector_search.py",
            "expected": "3 profiles uploaded to Cloud Storage"
        },
        {
            "step": 3,
            "task": "Verify Processing", 
            "command": "Check Firebase Functions logs",
            "expected": "Profiles processed and embeddings generated"
        },
        {
            "step": 4,
            "task": "Test Semantic Search",
            "command": "firebase functions:shell -> semanticSearch({query_text: '...'})",
            "expected": "Relevant candidates returned with similarity scores"
        },
        {
            "step": 5,
            "task": "Check Statistics",
            "command": "firebase functions:shell -> vectorSearchStats({})",
            "expected": "Shows 3 embeddings and health status"
        }
    ]
    
    print("🔍 Vector Search Deployment Validation")
    print("=" * 50)
    
    for step in validation_steps:
        print(f"Step {step['step']}: {step['task']}")
        print(f"  Command: {step['command']}")
        print(f"  Expected: {step['expected']}")
        print()
    
    return validation_steps

def main():
    """Main test function"""
    print("🎯 Vector Search Integration Testing")
    print("=" * 50)
    
    # Create and upload test profiles
    uploaded_files = upload_test_profiles()
    
    # Create test queries
    test_queries = test_semantic_search()
    
    # Test embedding generation
    test_candidates = test_embedding_generation()
    
    # Create validation checklist
    validation_steps = create_deployment_validation()
    
    print("\n✅ Vector Search Test Setup Complete!")
    print("\nNext Steps:")
    print("1. Wait 2-3 minutes for profile processing")
    print("2. Deploy functions: ./scripts/deploy_functions.sh")  
    print("3. Test semantic search with the queries above")
    print("4. Verify embeddings and statistics")
    
    # Save test data for reference
    test_data = {
        "profiles": create_test_profiles(),
        "queries": test_queries,
        "validation_steps": validation_steps,
        "timestamp": datetime.now().isoformat()
    }
    
    test_file = Path(__file__).parent / "vector_search_test_data.json"
    with open(test_file, 'w') as f:
        json.dump(test_data, f, indent=2)
    
    print(f"📄 Test data saved to: {test_file}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)