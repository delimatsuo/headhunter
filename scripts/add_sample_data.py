#!/usr/bin/env python3
"""
Add sample candidate data directly to the system for testing
This simulates the data processing pipeline output
"""

import json
import os
import sys
from datetime import datetime

def create_sample_candidates():
    """Create realistic sample candidate data"""
    return [
        {
            "candidate_id": "sample-001",
            "name": "Sarah Chen",
            "current_role": "Senior Engineering Manager",
            "current_company": "Meta",
            "resume_analysis": {
                "career_trajectory": {
                    "current_level": "Senior Manager",
                    "progression_speed": "steady",
                    "trajectory_type": "technical_leadership",
                    "domain_expertise": ["Machine Learning", "Distributed Systems", "Team Leadership"]
                },
                "years_experience": 8,
                "technical_skills": [
                    "Python", "React", "TypeScript", "AWS", "Machine Learning", 
                    "Kubernetes", "System Design", "GraphQL"
                ],
                "soft_skills": ["Leadership", "Mentoring", "Communication", "Strategic Planning"],
                "leadership_scope": {
                    "has_leadership": True,
                    "team_size": 12,
                    "leadership_level": "Engineering Manager",
                    "leadership_style": ["Collaborative", "Data-driven"],
                    "mentorship_experience": True
                },
                "company_pedigree": {
                    "tier_level": "tier_1",
                    "recent_companies": ["Meta", "Google", "Stripe"],
                    "company_types": ["Big Tech", "Fintech"],
                    "brand_recognition": "high"
                },
                "education": {
                    "highest_degree": "MS Computer Science",
                    "institutions": ["Stanford University"],
                    "fields_of_study": ["Computer Science", "Machine Learning"]
                }
            },
            "recruiter_insights": {
                "sentiment": "very_positive",
                "strengths": [
                    "Exceptional technical leadership at scale",
                    "Proven track record building ML platforms",
                    "Strong cultural fit and communication skills"
                ],
                "concerns": ["May be overqualified for IC roles"],
                "recommendation": "strong_hire",
                "readiness_level": "immediately_available",
                "key_themes": ["Technical depth", "Leadership growth", "Cultural ambassador"],
                "competitive_advantages": ["ML expertise", "Big tech experience", "Team building"]
            },
            "overall_score": 0.92,
            "processing_timestamp": datetime.now().isoformat()
        },
        {
            "candidate_id": "sample-002", 
            "name": "Marcus Rodriguez",
            "current_role": "Principal Software Engineer",
            "current_company": "Spotify",
            "resume_analysis": {
                "career_trajectory": {
                    "current_level": "Principal",
                    "progression_speed": "fast",
                    "trajectory_type": "individual_contributor",
                    "domain_expertise": ["Backend Systems", "API Design", "Performance Optimization"]
                },
                "years_experience": 6,
                "technical_skills": [
                    "Node.js", "Python", "Go", "Docker", "Kubernetes", 
                    "GraphQL", "Microservices", "Redis", "PostgreSQL"
                ],
                "soft_skills": ["Problem-solving", "Innovation", "Collaboration", "Mentoring"],
                "leadership_scope": {
                    "has_leadership": False,
                    "team_size": 0,
                    "leadership_level": "Individual Contributor",
                    "mentorship_experience": True
                },
                "company_pedigree": {
                    "tier_level": "tier_2",
                    "recent_companies": ["Spotify", "Airbnb", "Shopify"],
                    "company_types": ["Music/Media", "Travel", "E-commerce"],
                    "brand_recognition": "high"
                },
                "education": {
                    "highest_degree": "BS Computer Engineering", 
                    "institutions": ["UC Berkeley"],
                    "fields_of_study": ["Computer Engineering"]
                }
            },
            "recruiter_insights": {
                "sentiment": "positive",
                "strengths": [
                    "Deep backend expertise with modern stack",
                    "Fast learner with strong problem-solving",
                    "Great cultural fit for product-driven teams"
                ],
                "concerns": ["Limited leadership experience"],
                "recommendation": "hire",
                "readiness_level": "available_in_month",
                "key_themes": ["Technical excellence", "Growth mindset", "Product focus"],
                "competitive_advantages": ["Modern tech stack", "Scale experience", "Product intuition"]
            },
            "overall_score": 0.85,
            "processing_timestamp": datetime.now().isoformat()
        },
        {
            "candidate_id": "sample-003",
            "name": "Dr. Emily Watson",
            "current_role": "Distinguished Engineer",
            "current_company": "Amazon",
            "resume_analysis": {
                "career_trajectory": {
                    "current_level": "Distinguished",
                    "progression_speed": "steady", 
                    "trajectory_type": "technical_architecture",
                    "domain_expertise": ["Distributed Systems", "System Architecture", "Platform Engineering"]
                },
                "years_experience": 12,
                "technical_skills": [
                    "Java", "Python", "System Design", "Microservices", "AWS", 
                    "Kafka", "Cassandra", "Terraform", "Docker"
                ],
                "soft_skills": ["Architecture", "Mentoring", "Strategic thinking", "Technical writing"],
                "leadership_scope": {
                    "has_leadership": True,
                    "team_size": 25,
                    "leadership_level": "Distinguished Engineer",
                    "leadership_style": ["Technical", "Mentoring-focused"],
                    "mentorship_experience": True
                },
                "company_pedigree": {
                    "tier_level": "tier_1",
                    "recent_companies": ["Amazon", "Netflix", "Uber"],
                    "company_types": ["Cloud/Infrastructure", "Streaming", "Mobility"],
                    "brand_recognition": "very_high"
                },
                "education": {
                    "highest_degree": "PhD Computer Science",
                    "institutions": ["MIT"],
                    "fields_of_study": ["Computer Science", "Distributed Systems"]
                }
            },
            "recruiter_insights": {
                "sentiment": "very_positive",
                "strengths": [
                    "World-class system architecture expertise",
                    "Proven ability to scale teams and systems",
                    "Thought leader in distributed systems"
                ],
                "concerns": ["Very senior - limited roles at this level"],
                "recommendation": "strong_hire",
                "readiness_level": "exploring_options",
                "key_themes": ["Technical authority", "Architecture leadership", "Industry recognition"],
                "competitive_advantages": ["PhD + industry experience", "Published research", "Scale expertise"]
            },
            "overall_score": 0.95,
            "processing_timestamp": datetime.now().isoformat()
        },
        {
            "candidate_id": "sample-004",
            "name": "Alex Kim",
            "current_role": "Senior Frontend Engineer",
            "current_company": "Airbnb",
            "resume_analysis": {
                "career_trajectory": {
                    "current_level": "Senior",
                    "progression_speed": "steady",
                    "trajectory_type": "frontend_specialist",
                    "domain_expertise": ["Frontend Architecture", "User Experience", "Design Systems"]
                },
                "years_experience": 5,
                "technical_skills": [
                    "React", "TypeScript", "Next.js", "GraphQL", "CSS", 
                    "Webpack", "Testing", "Figma", "Storybook"
                ],
                "soft_skills": ["Design thinking", "User empathy", "Collaboration", "Attention to detail"],
                "leadership_scope": {
                    "has_leadership": False,
                    "team_size": 0,
                    "leadership_level": "Individual Contributor",
                    "mentorship_experience": True
                },
                "company_pedigree": {
                    "tier_level": "tier_2",
                    "recent_companies": ["Airbnb", "Pinterest", "Figma"],
                    "company_types": ["Travel", "Social", "Design Tools"],
                    "brand_recognition": "high"
                },
                "education": {
                    "highest_degree": "BS Computer Science",
                    "institutions": ["UC San Diego"],
                    "fields_of_study": ["Computer Science", "Human-Computer Interaction"]
                }
            },
            "recruiter_insights": {
                "sentiment": "positive",
                "strengths": [
                    "Exceptional frontend skills and design sense",
                    "Strong user experience focus",
                    "Great at building design systems"
                ],
                "concerns": ["Limited full-stack experience"],
                "recommendation": "hire",
                "readiness_level": "available_in_weeks",
                "key_themes": ["Design excellence", "User focus", "Technical craftsmanship"],
                "competitive_advantages": ["Design + engineering hybrid", "UX expertise", "Modern frontend stack"]
            },
            "overall_score": 0.82,
            "processing_timestamp": datetime.now().isoformat()
        }
    ]

def save_candidates_to_json(candidates, filename="sample_candidates.json"):
    """Save candidates to JSON file"""
    filepath = os.path.join(os.path.dirname(__file__), filename)
    
    with open(filepath, 'w') as f:
        json.dump(candidates, f, indent=2)
    
    print(f"✅ Saved {len(candidates)} candidates to {filepath}")
    return filepath

def print_candidate_summary(candidates):
    """Print a summary of the candidates"""
    print("\n📊 Candidate Summary:")
    print("-" * 50)
    
    for candidate in candidates:
        name = candidate['name']
        role = candidate['current_role']
        company = candidate['current_company']
        score = candidate['overall_score']
        experience = candidate['resume_analysis']['years_experience']
        skills = candidate['resume_analysis']['technical_skills'][:3]  # First 3 skills
        
        print(f"👤 {name}")
        print(f"   {role} at {company}")
        print(f"   {experience} years exp | Score: {score*100:.0f}% | Skills: {', '.join(skills)}...")
        print()

def main():
    """Main function to create and save sample data"""
    print("🗃️  Creating Sample Candidate Data for Headhunter AI")
    print("=" * 55)
    
    candidates = create_sample_candidates()
    print_candidate_summary(candidates)
    
    # Save to JSON file
    filepath = save_candidates_to_json(candidates)
    
    print("\n🧪 Testing Instructions:")
    print("-" * 30)
    print("1. Import this data into Firestore 'candidates' collection")
    print("2. Generate embeddings: call generateEmbedding for each candidate")
    print("3. Test search with job descriptions matching these profiles:")
    print("   • 'Senior Engineering Manager with ML experience'")
    print("   • 'Backend engineer with microservices expertise'") 
    print("   • 'Principal engineer for distributed systems'")
    print("   • 'Frontend developer with React and design skills'")
    
    print(f"\n📁 Sample data saved to: {filepath}")
    
    # Also create a simple CSV for the Python processor
    csv_file = os.path.join(os.path.dirname(__file__), "sample_candidates.csv")
    with open(csv_file, 'w') as f:
        f.write("candidate_id,name,current_role,current_company,years_experience,technical_skills\n")
        for candidate in candidates:
            skills = "|".join(candidate['resume_analysis']['technical_skills'])
            f.write(f"{candidate['candidate_id']},{candidate['name']},{candidate['current_role']},{candidate['current_company']},{candidate['resume_analysis']['years_experience']},{skills}\n")
    
    print(f"📄 CSV version saved to: {csv_file}")

if __name__ == "__main__":
    main()