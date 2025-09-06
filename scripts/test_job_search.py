#!/usr/bin/env python3
"""
Test script for Job Search API functionality
"""

import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path

def create_test_job_descriptions():
    """Create diverse test job descriptions for API testing"""
    
    job_descriptions = [
        {
            "id": "job_001",
            "title": "Senior Machine Learning Engineer",
            "company": "TechCorp AI",
            "description": """
                We're looking for a Senior Machine Learning Engineer to join our AI team.
                You'll be working on cutting-edge ML models and leading technical initiatives.
                
                Requirements:
                - 7+ years of experience in machine learning
                - Strong Python and TensorFlow/PyTorch skills
                - Experience with distributed systems and Kubernetes
                - Leadership experience with 5+ person teams
                - PhD in Computer Science or related field preferred
                - Experience at top-tier tech companies
                
                Nice to have:
                - Research publications in ML/AI
                - Open source contributions
                - Conference speaking experience
            """,
            "expected_matches": ["vector_test_001"],  # Alice Chen
            "reason": "Strong ML background with leadership at big tech"
        },
        {
            "id": "job_002",
            "title": "Frontend React Developer",
            "company": "StartupCo",
            "description": """
                Fast-growing startup seeking a Frontend Developer with React expertise.
                Build amazing user experiences in a fast-paced environment.
                
                Requirements:
                - 3-5 years of frontend development experience
                - Expert in React, TypeScript, and modern JavaScript
                - Experience with Node.js and full-stack development
                - Startup experience preferred
                - Strong problem-solving skills
                
                Great to have:
                - Hackathon participation
                - Side projects portfolio
                - Mobile development experience
            """,
            "expected_matches": ["vector_test_002"],  # Bob Rodriguez
            "reason": "React expertise with startup experience"
        },
        {
            "id": "job_003",
            "title": "Principal Platform Engineer",
            "company": "CloudScale Inc",
            "description": """
                Seeking a Principal Engineer to architect our next-gen platform.
                Lead the design and implementation of distributed systems at scale.
                
                Requirements:
                - 10+ years building distributed systems
                - Expert in Kubernetes, Docker, and cloud infrastructure
                - Strong Go or Java programming skills
                - Experience with AWS/GCP at scale
                - Track record of leading 10+ person engineering teams
                - Experience at FAANG or equivalent companies
                
                Responsibilities:
                - Design platform serving 100M+ users
                - Lead technical strategy and architecture
                - Mentor senior engineers
            """,
            "expected_matches": ["vector_test_003"],  # Carol Kim
            "reason": "Platform expertise with scale and leadership experience"
        },
        {
            "id": "job_004",
            "title": "Full Stack Engineer - AI Team",
            "company": "AI Innovations",
            "description": """
                Join our AI team as a Full Stack Engineer working on ML-powered products.
                
                Requirements:
                - 5+ years full stack development
                - Python backend experience
                - React/TypeScript frontend skills
                - Basic understanding of machine learning
                - AWS or cloud experience
                - Collaborative team player
                
                Ideal candidate has:
                - Experience integrating ML models into products
                - Strong technical communication skills
                - Interest in AI/ML technologies
            """,
            "expected_matches": ["vector_test_001", "vector_test_002"],
            "reason": "Could match both ML-focused and full-stack candidates"
        },
        {
            "id": "job_005",
            "title": "Engineering Manager - Infrastructure",
            "company": "MegaCorp",
            "description": """
                Lead our infrastructure team building the foundation for our products.
                
                Requirements:
                - 8+ years software engineering experience
                - 3+ years people management experience
                - Deep knowledge of cloud infrastructure and DevOps
                - Experience with Kubernetes and microservices
                - Strong technical and strategic thinking
                - Proven track record at scale
                
                You'll be:
                - Managing a team of 10-15 engineers
                - Setting technical direction for infrastructure
                - Working with product and other engineering teams
            """,
            "expected_matches": ["vector_test_003", "vector_test_001"],
            "reason": "Leadership role matching experienced technical leaders"
        }
    ]
    
    return job_descriptions

def test_job_search_api():
    """Test the job search API with various queries"""
    print("🔍 Testing Job Search API functionality...")
    
    job_descriptions = create_test_job_descriptions()
    
    print("\nTest Job Descriptions:")
    print("-" * 50)
    
    for i, job in enumerate(job_descriptions, 1):
        print(f"\n{i}. {job['title']} at {job['company']}")
        print(f"   Job ID: {job['id']}")
        print(f"   Expected matches: {job['expected_matches']}")
        print(f"   Reason: {job['reason']}")
    
    print("\n" + "=" * 50)
    print("Firebase Functions Shell Commands to Test:")
    print("-" * 50)
    
    for job in job_descriptions:
        # Format for Firebase Functions shell
        print(f"\n// Test: {job['title']}")
        print(f"searchJobCandidates({{")
        print(f"  jobDescription: {{")
        print(f"    title: \"{job['title']}\",")
        print(f"    company: \"{job['company']}\",")
        print(f"    description: `{job['description'].strip()}`")
        print(f"  }},")
        print(f"  limit: 10")
        print(f"}})")
        print()
        
        # Quick match version
        print(f"// Quick match version:")
        print(f"quickMatch({{")
        print(f"  description: `{job['title']} - {job['description'][:100].strip()}...`")
        print(f"}})")
        print()
    
    return job_descriptions

def create_api_documentation():
    """Generate API documentation for the search endpoints"""
    
    api_docs = {
        "endpoints": [
            {
                "name": "searchJobCandidates",
                "method": "POST",
                "description": "Search for candidates matching a job description",
                "request": {
                    "jobDescription": {
                        "title": "string - Job title",
                        "company": "string - Company name",
                        "description": "string - Full job description with requirements",
                        "required_skills": "string[] - Optional list of required skills",
                        "nice_to_have": "string[] - Optional list of nice-to-have skills",
                        "min_experience": "number - Optional minimum years of experience",
                        "max_experience": "number - Optional maximum years of experience",
                        "leadership_required": "boolean - Optional flag for leadership requirement"
                    },
                    "limit": "number - Maximum number of results (default: 20)"
                },
                "response": {
                    "success": "boolean",
                    "matches": [{
                        "candidate": "CandidateProfile object",
                        "score": "number (0-100)",
                        "similarity": "number (0-1)",
                        "rationale": {
                            "strengths": "string[]",
                            "gaps": "string[]",
                            "risk_factors": "string[]",
                            "overall_assessment": "string"
                        }
                    }],
                    "insights": {
                        "total_candidates": "number",
                        "avg_match_score": "number",
                        "top_skills_matched": "string[]",
                        "common_gaps": "string[]",
                        "market_analysis": "string",
                        "recommendations": "string[]"
                    },
                    "query_time_ms": "number"
                }
            },
            {
                "name": "quickMatch",
                "method": "POST",
                "description": "Quick candidate matching with simple text description",
                "request": {
                    "description": "string - Simple text description of the role",
                    "limit": "number - Optional limit (default: 10)"
                },
                "response": {
                    "success": "boolean",
                    "matches": [{
                        "candidate_id": "string",
                        "name": "string",
                        "score": "number",
                        "summary": "string"
                    }]
                }
            }
        ],
        "scoring": {
            "weights": {
                "skills_match": 0.40,
                "experience_match": 0.30,
                "leadership_match": 0.20,
                "education_match": 0.10
            },
            "factors": [
                "Technical skills alignment",
                "Years of experience range",
                "Leadership experience if required",
                "Company tier and pedigree",
                "Educational background",
                "Cultural fit indicators",
                "Career trajectory alignment"
            ]
        },
        "caching": {
            "enabled": True,
            "ttl_minutes": 30,
            "key_generation": "Hash of job description + limit"
        }
    }
    
    docs_path = Path(__file__).parent / "job_search_api_docs.json"
    with open(docs_path, 'w') as f:
        json.dump(api_docs, f, indent=2)
    
    print(f"📄 API documentation saved to: {docs_path}")
    
    return api_docs

def create_deployment_test():
    """Create deployment validation checklist"""
    
    validation_steps = [
        {
            "step": 1,
            "task": "Deploy Functions",
            "command": "./scripts/deploy_functions.sh",
            "expected": "All functions deployed successfully"
        },
        {
            "step": 2,
            "task": "Test searchJobCandidates",
            "command": "firebase functions:shell -> searchJobCandidates({...})",
            "expected": "Returns ranked candidates with rationales"
        },
        {
            "step": 3,
            "task": "Test quickMatch",
            "command": "firebase functions:shell -> quickMatch({...})",
            "expected": "Returns simplified match results"
        },
        {
            "step": 4,
            "task": "Verify Caching",
            "command": "Run same query twice and check response time",
            "expected": "Second query significantly faster (cached)"
        },
        {
            "step": 5,
            "task": "Test Error Handling",
            "command": "Send invalid requests",
            "expected": "Graceful error messages returned"
        },
        {
            "step": 6,
            "task": "Check Firestore",
            "command": "Firebase Console -> Firestore -> search_cache",
            "expected": "Cached search results visible"
        }
    ]
    
    print("\n🔍 Job Search API Deployment Validation")
    print("=" * 50)
    
    for step in validation_steps:
        print(f"Step {step['step']}: {step['task']}")
        print(f"  Command: {step['command']}")
        print(f"  Expected: {step['expected']}")
        print()
    
    return validation_steps

def main():
    """Main test function"""
    print("🎯 Job Search API Testing Suite")
    print("=" * 50)
    
    # Create test job descriptions
    job_descriptions = test_job_search_api()
    
    # Generate API documentation
    api_docs = create_api_documentation()
    
    # Create deployment validation checklist
    validation_steps = create_deployment_test()
    
    print("\n✅ Job Search API Test Setup Complete!")
    print(f"\nNext Steps:")
    print("1. Deploy functions: cd functions && npm run deploy")
    print("2. Test with Firebase shell: cd functions && npm run shell")
    print("3. Run the test queries above")
    print("4. Verify caching and performance")
    print("5. Check match quality and rationales")
    
    # Save all test data
    test_data = {
        "job_descriptions": job_descriptions,
        "api_documentation": api_docs,
        "validation_steps": validation_steps,
        "timestamp": datetime.now().isoformat()
    }
    
    test_file = Path(__file__).parent / "job_search_test_data.json"
    with open(test_file, 'w') as f:
        json.dump(test_data, f, indent=2)
    
    print(f"\n📄 Test data saved to: {test_file}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)