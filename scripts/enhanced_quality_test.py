#!/usr/bin/env python3
"""
Enhanced Quality Test - 20 Candidates with Comprehensive Profiles

Tests the complete Together AI → comprehensive profile generation → Firestore pipeline
with detailed 15+ field candidate profiles optimized for recruiter search workflows.
"""

import asyncio
import aiohttp
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Any

# Add cloud_run_worker to path
sys.path.append('cloud_run_worker')
from config import Config

try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False

def create_comprehensive_prompt(candidate_data: Dict[str, Any]) -> str:
    """Create comprehensive prompt for detailed candidate analysis"""
    
    candidate_id = candidate_data['id']
    name = candidate_data['name']
    experience = candidate_data['experience']
    skills = ', '.join(candidate_data['skills'])
    companies = ', '.join(candidate_data['companies'])
    comments = candidate_data.get('comments', 'No additional comments')
    
    prompt = f"""Analyze this candidate and return ONLY valid JSON with comprehensive details for recruiter search optimization.

CANDIDATE DATA:
Name: {name}
Experience: {experience} years
Skills: {skills}
Companies: {companies}
Recruiter Comments: {comments}

Return this EXACT JSON structure with detailed analysis (no markdown, no explanation, ONLY the JSON):

{{
  "candidate_id": "{candidate_id}",
  "personal_info": {{
    "name": "{name}",
    "current_title": "Infer from experience and skills",
    "location": "Infer likely location from companies",
    "linkedin_url": "https://linkedin.com/in/example",
    "email": "example@email.com",
    "phone": "+1-555-0000"
  }},
  "processing_metadata": {{
    "processed_by": "together_ai_llama3.2_3b",
    "processed_at": "{datetime.now().isoformat()}",
    "processing_time_seconds": 2.3,
    "model_version": "meta-llama/Llama-3.2-3B-Instruct-Turbo",
    "api_cost_dollars": 0.0045,
    "confidence_score": 0.92
  }},
  "career_trajectory": {{
    "current_level": "junior|mid|senior|staff|principal|executive",
    "progression_speed": "slow|steady|fast",
    "trajectory_type": "individual_contributor|technical_leadership|management|hybrid",
    "years_total_experience": {experience},
    "years_current_role": 2,
    "career_velocity": "plateauing|steady|accelerating",
    "promotion_frequency": "every_1_2_years|every_2_3_years|every_3_plus_years",
    "role_transitions": ["Provide 2-3 career progression steps"]
  }},
  "leadership_scope": {{
    "has_leadership": true,
    "team_size_managed": 5,
    "leadership_level": "individual|team_lead|manager|director|vp",
    "leadership_style": "collaborative|directive|servant_leadership|results_oriented",
    "direct_reports": 3,
    "cross_functional_collaboration": "low|medium|high",
    "mentorship_experience": "none|some|extensive"
  }},
  "company_pedigree": {{
    "current_company": "Most recent from list",
    "company_tier": "startup|growth|mid_market|enterprise|faang",
    "company_list": {json.dumps(candidate_data['companies'][:3])},
    "company_trajectory": "declining|stable|scaling_up",
    "stability_pattern": "job_hopper|strategic_moves|very_stable",
    "industry_focus": ["List 2-3 relevant industries"],
    "company_stage_preference": "early_stage|growth_stage|mature"
  }},
  "technical_skills": {{
    "primary_languages": {json.dumps(candidate_data['skills'][:3])},
    "frameworks": ["Infer relevant frameworks"],
    "cloud_platforms": ["AWS", "GCP"],
    "databases": ["PostgreSQL", "MongoDB"],
    "tools": ["Docker", "Git", "Jenkins"],
    "specializations": ["List 2-3 tech specializations"],
    "skill_depth": "beginner|intermediate|advanced|expert",
    "learning_velocity": "low|medium|high",
    "technical_breadth": "specialist|full_stack|polyglot"
  }},
  "domain_expertise": {{
    "industries": ["Infer 2-3 industries from companies"],
    "business_functions": ["product_engineering", "platform_development"],
    "domain_depth": "novice|intermediate|expert",
    "vertical_knowledge": ["Specific domain knowledge areas"],
    "regulatory_experience": ["Any relevant compliance experience"]
  }},
  "soft_skills": {{
    "communication": "poor|developing|strong|exceptional",
    "leadership": "poor|developing|strong|exceptional", 
    "collaboration": "poor|developing|strong|exceptional",
    "problem_solving": "basic|good|strong|expert",
    "adaptability": "low|medium|high",
    "emotional_intelligence": "low|medium|high",
    "conflict_resolution": "poor|developing|strong|exceptional",
    "presentation_skills": "poor|developing|strong|exceptional"
  }},
  "cultural_signals": {{
    "work_style": "independent|collaborative|hybrid|autonomous",
    "cultural_strengths": ["List 3-4 positive cultural traits"],
    "values_alignment": ["growth_mindset", "customer_focus", "excellence"],
    "red_flags": [],
    "team_dynamics": "negative|neutral|positive_influence",
    "change_adaptability": "struggles_with_change|adapts_slowly|thrives_in_change",
    "feedback_receptiveness": "low|medium|high"
  }},
  "compensation_insights": {{
    "current_salary_range": "Estimate based on level and location",
    "total_compensation": "Including equity estimate",
    "salary_expectations": "below_market|market_rate|above_market",
    "equity_preference": "cash_focused|balanced|equity_focused",
    "compensation_motivators": ["base_salary", "equity_upside", "benefits"],
    "negotiation_flexibility": "rigid|moderate|flexible"
  }},
  "recruiter_insights": {{
    "engagement_history": "unresponsive|slow|responsive|very_responsive",
    "placement_likelihood": "low|medium|high|very_high",
    "best_fit_roles": ["List 3-4 ideal role matches"],
    "cultural_fit_companies": ["List 2-3 company types that would be good fits"],
    "interview_strengths": ["List 2-3 likely interview strengths"],
    "potential_concerns": ["List 1-2 potential concerns if any"],
    "recruiter_notes": "Detailed recruiter assessment based on profile"
  }},
  "search_optimization": {{
    "primary_keywords": ["List 5 most important search keywords"],
    "secondary_keywords": ["List 5 additional relevant keywords"],
    "skill_tags": ["List 4-5 skill-based tags"],
    "location_tags": ["List location-related tags"],
    "industry_tags": ["List industry tags"],
    "seniority_indicators": ["List experience level indicators"]
  }},
  "matching_profiles": {{
    "ideal_role_types": ["List 3-4 ideal role types"],
    "company_size_preference": ["startup|small|medium|large|enterprise"],
    "technology_stack_match": 0.85,
    "leadership_readiness": 0.75,
    "domain_transferability": 0.80,
    "cultural_fit_score": 0.90
  }},
  "executive_summary": {{
    "one_line_pitch": "Compelling one-line summary for recruiters",
    "key_differentiators": ["List 3 unique selling points"],
    "ideal_next_role": "Specific role recommendation based on trajectory",
    "career_narrative": "2-3 sentence career story highlighting progression",
    "overall_rating": 85,
    "recommendation_tier": "bottom_25_percent|middle_50_percent|top_25_percent|top_10_percent|top_5_percent"
  }},
  "embeddings_metadata": {{
    "embedding_model": "text-embedding-004", 
    "embedding_dimensions": 768,
    "last_embedded": "{datetime.now().isoformat()}",
    "similarity_cache_updated": "{datetime.now().isoformat()}"
  }}
}}

Ensure all fields are filled with realistic, detailed information based on the candidate data provided. Focus on creating rich profiles that recruiters can use for effective search and matching."""

    return prompt

async def process_candidate_with_comprehensive_profile(config, db, candidate_data):
    """Process a candidate with comprehensive profile generation"""
    candidate_id = candidate_data['id']
    print(f"🔄 Processing {candidate_id} with comprehensive analysis...", end=" ")
    
    # Step 1: Call Together AI with comprehensive prompt
    headers = {
        'Authorization': f'Bearer {config.together_ai_api_key}',
        'Content-Type': 'application/json'
    }
    
    comprehensive_prompt = create_comprehensive_prompt(candidate_data)
    
    payload = {
        'model': config.together_ai_model,
        'messages': [{'role': 'user', 'content': comprehensive_prompt}],
        'max_tokens': 1500,  # Increased for comprehensive profiles
        'temperature': 0.1
    }
    
    try:
        start_time = time.time()
        
        # Call Together AI
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{config.together_ai_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=45)
            ) as response:
                ai_time = time.time() - start_time
                
                if response.status != 200:
                    error_text = await response.text()
                    print(f"❌ AI failed: HTTP {response.status}")
                    return None
                
                result = await response.json()
                ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                tokens_used = result.get('usage', {}).get('total_tokens', 0)
                cost = (tokens_used / 1000000) * 0.20  # Together AI pricing
        
        # Step 2: Parse AI response
        try:
            # Clean the response
            clean_response = ai_response.strip()
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()
            
            # Parse JSON
            comprehensive_profile = json.loads(clean_response)
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing failed: {str(e)[:50]}...")
            return None
        
        # Step 3: Add source metadata
        comprehensive_profile['source'] = 'enhanced_quality_test'
        comprehensive_profile['processing_metadata']['tokens_used'] = tokens_used
        comprehensive_profile['processing_metadata']['api_cost_dollars'] = cost
        comprehensive_profile['processing_metadata']['processing_time_seconds'] = ai_time
        
        # Step 4: Save to Firestore
        if FIRESTORE_AVAILABLE and db:
            save_start = time.time()
            
            # Save to enhanced_candidates collection
            doc_ref = db.collection('enhanced_candidates').document(candidate_id)
            doc_ref.set(comprehensive_profile)
            
            save_time = time.time() - save_start
            total_time = ai_time + save_time
            
            print(f"✅ {total_time:.2f}s (AI:{ai_time:.1f}s + Save:{save_time:.1f}s, ${cost:.4f})")
        else:
            print(f"✅ {ai_time:.2f}s (AI only - Firestore not available, ${cost:.4f})")
        
        return comprehensive_profile
        
    except Exception as e:
        print(f"❌ Error: {str(e)[:30]}")
        return None

def generate_realistic_test_candidates(num_candidates: int = 20) -> List[Dict[str, Any]]:
    """Generate realistic test candidates with varied backgrounds"""
    
    skills_by_role = {
        'frontend': ['React', 'TypeScript', 'JavaScript', 'CSS', 'HTML', 'Vue.js', 'Angular'],
        'backend': ['Python', 'Node.js', 'Java', 'Go', 'PostgreSQL', 'Redis', 'Docker'],
        'fullstack': ['React', 'Python', 'TypeScript', 'PostgreSQL', 'AWS', 'Docker', 'Node.js'],
        'data': ['Python', 'SQL', 'Machine Learning', 'TensorFlow', 'Pandas', 'Spark', 'Airflow'],
        'devops': ['AWS', 'Docker', 'Kubernetes', 'Terraform', 'Jenkins', 'Python', 'Linux'],
        'mobile': ['React Native', 'Swift', 'Kotlin', 'TypeScript', 'iOS', 'Android', 'Flutter'],
        'ai_ml': ['Python', 'TensorFlow', 'PyTorch', 'Machine Learning', 'Deep Learning', 'NLP', 'Computer Vision']
    }
    
    companies_by_tier = {
        'faang': ['Google', 'Meta', 'Amazon', 'Apple', 'Netflix', 'Microsoft'],
        'enterprise': ['IBM', 'Oracle', 'Salesforce', 'Adobe', 'VMware', 'Cisco'],
        'growth': ['Stripe', 'Airbnb', 'Uber', 'Lyft', 'Zoom', 'Slack', 'Figma'],
        'startup': ['Series A Startup', 'Series B Fintech', 'Early Stage AI Company', 'YC Startup']
    }
    
    comments_templates = [
        "Strong technical background with excellent communication skills. Very collaborative.",
        "Proven leadership experience managing cross-functional teams. High growth potential.",
        "Deep domain expertise in fintech. Looking for senior IC or tech lead role.",
        "Full-stack engineer with startup experience. Prefers fast-paced environments.",
        "Data science expert with production ML experience. Open to remote roles.",
        "Senior mobile developer with consumer app experience. Strong product sense.",
        "DevOps engineer with cloud expertise. Has built scalable infrastructure.",
        "AI/ML researcher with academic background. Interested in applied roles."
    ]
    
    candidates = []
    role_types = list(skills_by_role.keys())
    tier_types = list(companies_by_tier.keys())
    
    for i in range(num_candidates):
        # Rotate through role types for variety
        role_type = role_types[i % len(role_types)]
        tier = tier_types[i % len(tier_types)]
        
        # Generate experience level (junior to principal)
        experience_years = 3 + (i % 12)  # 3-14 years
        
        # Select skills for this role type
        available_skills = skills_by_role[role_type]
        num_skills = min(4 + (i % 4), len(available_skills))  # 4-7 skills
        selected_skills = available_skills[:num_skills]
        
        # Select companies from tier
        available_companies = companies_by_tier[tier]
        num_companies = min(2 + (i % 3), len(available_companies))  # 2-4 companies
        selected_companies = available_companies[:num_companies]
        
        # Select comment
        comment = comments_templates[i % len(comments_templates)]
        
        candidate = {
            'id': f'quality_test_{i+1:03d}',
            'name': f'Test Candidate {i+1}',
            'experience': experience_years,
            'role_type': role_type,
            'tier': tier,
            'skills': selected_skills,
            'companies': selected_companies,
            'comments': comment
        }
        
        candidates.append(candidate)
    
    return candidates

def analyze_profile_quality(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze the quality and completeness of a generated profile"""
    
    quality_metrics = {
        'total_fields': 0,
        'populated_fields': 0,
        'empty_fields': [],
        'field_completeness': {},
        'overall_score': 0
    }
    
    # Expected top-level sections
    expected_sections = [
        'personal_info', 'processing_metadata', 'career_trajectory', 'leadership_scope',
        'company_pedigree', 'technical_skills', 'domain_expertise', 'soft_skills',
        'cultural_signals', 'compensation_insights', 'recruiter_insights', 
        'search_optimization', 'matching_profiles', 'executive_summary', 'embeddings_metadata'
    ]
    
    for section in expected_sections:
        if section in profile:
            section_data = profile[section]
            if isinstance(section_data, dict):
                total_fields = len(section_data)
                populated_fields = sum(1 for v in section_data.values() if v and v != [] and v != "")
                quality_metrics['total_fields'] += total_fields
                quality_metrics['populated_fields'] += populated_fields
                quality_metrics['field_completeness'][section] = populated_fields / total_fields if total_fields > 0 else 0
                
                # Check for empty fields
                for field, value in section_data.items():
                    if not value or value == [] or value == "":
                        quality_metrics['empty_fields'].append(f"{section}.{field}")
        else:
            quality_metrics['empty_fields'].append(section)
    
    # Calculate overall score
    if quality_metrics['total_fields'] > 0:
        quality_metrics['overall_score'] = quality_metrics['populated_fields'] / quality_metrics['total_fields']
    
    return quality_metrics

async def main():
    """Run enhanced 20-candidate quality test"""
    print("🚀 Enhanced Quality Test - 20 Candidates with Comprehensive Profiles")
    print("=" * 80)
    
    # Setup
    os.environ['GOOGLE_CLOUD_PROJECT'] = 'headhunter-ai-0088'
    config = Config()
    
    print(f"✅ Together AI configured: {config.together_ai_model}")
    
    # Initialize Firestore if available
    db = None
    if FIRESTORE_AVAILABLE:
        db = firestore.Client()
        print("✅ Firestore client initialized")
    else:
        print("⚠️ Firestore not available - will test AI processing only")
    
    # Generate realistic test candidates
    candidates = generate_realistic_test_candidates(20)
    print(f"✅ Generated {len(candidates)} realistic test candidates")
    print("   - Role types: Frontend, Backend, Full-stack, Data, DevOps, Mobile, AI/ML")
    print("   - Company tiers: FAANG, Enterprise, Growth, Startup")
    print("   - Experience range: 3-14 years")
    
    print("\\n🔄 Processing candidates with comprehensive AI analysis:")
    
    # Process each candidate
    start_time = time.time()
    successful_profiles = []
    total_cost = 0.0
    
    for i, candidate in enumerate(candidates):
        profile = await process_candidate_with_comprehensive_profile(config, db, candidate)
        if profile:
            successful_profiles.append(profile)
            total_cost += profile['processing_metadata'].get('api_cost_dollars', 0)
        
        # Small delay between requests
        if i < len(candidates) - 1:
            await asyncio.sleep(0.3)
    
    total_time = time.time() - start_time
    
    # Analyze profile quality
    print("\\n" + "=" * 80)
    print("📊 QUALITY ANALYSIS RESULTS")
    print("=" * 80)
    
    if successful_profiles:
        # Analyze quality metrics
        quality_analyses = [analyze_profile_quality(profile) for profile in successful_profiles]
        
        avg_total_fields = sum(qa['total_fields'] for qa in quality_analyses) / len(quality_analyses)
        avg_populated_fields = sum(qa['populated_fields'] for qa in quality_analyses) / len(quality_analyses)
        avg_completeness = sum(qa['overall_score'] for qa in quality_analyses) / len(quality_analyses)
        
        print(f"✅ Successfully processed: {len(successful_profiles)}/20 candidates ({len(successful_profiles)/20*100:.1f}%)")
        print(f"⏱️  Total processing time: {total_time:.2f}s")
        print(f"⏱️  Average per candidate: {total_time/len(candidates):.2f}s")
        print(f"💰 Total cost: ${total_cost:.4f}")
        print(f"💰 Average cost per candidate: ${total_cost/len(candidates):.4f}")
        print("\\n📊 PROFILE QUALITY METRICS:")
        print(f"   - Average total fields: {avg_total_fields:.1f}")
        print(f"   - Average populated fields: {avg_populated_fields:.1f}")
        print(f"   - Average completeness: {avg_completeness:.1%}")
        
        # Show section completeness
        print("\\n📋 SECTION COMPLETENESS:")
        section_scores = {}
        for qa in quality_analyses:
            for section, score in qa['field_completeness'].items():
                if section not in section_scores:
                    section_scores[section] = []
                section_scores[section].append(score)
        
        for section, scores in section_scores.items():
            avg_score = sum(scores) / len(scores)
            print(f"   - {section}: {avg_score:.1%}")
        
        # Sample profile analysis
        if successful_profiles:
            print("\\n🔍 SAMPLE PROFILE ANALYSIS (Candidate 1):")
            sample_profile = successful_profiles[0]
            sample_quality = quality_analyses[0]
            
            print(f"   - Name: {sample_profile.get('personal_info', {}).get('name', 'N/A')}")
            print(f"   - Current Level: {sample_profile.get('career_trajectory', {}).get('current_level', 'N/A')}")
            print(f"   - Technical Skills: {len(sample_profile.get('technical_skills', {}).get('primary_languages', []))} languages")
            print(f"   - Companies: {len(sample_profile.get('company_pedigree', {}).get('company_list', []))} companies")
            print(f"   - Overall Rating: {sample_profile.get('executive_summary', {}).get('overall_rating', 'N/A')}")
            print(f"   - Profile Completeness: {sample_quality['overall_score']:.1%}")
            print(f"   - One-line Pitch: {sample_profile.get('executive_summary', {}).get('one_line_pitch', 'N/A')}")
        
        # Quality assessment
        if avg_completeness >= 0.9:
            print("\\n🎉 EXCELLENT PROFILE QUALITY!")
            print(f"✅ Profiles have {avg_completeness:.1%} field completeness")
            print("✅ Rich, detailed candidate data suitable for recruiter search")
            print("✅ Ready for vector embedding and semantic search")
            
            return 0
        elif avg_completeness >= 0.8:
            print("\\n✅ GOOD PROFILE QUALITY")
            print(f"⚠️ Profiles have {avg_completeness:.1%} field completeness")
            print("✅ Suitable for basic search functionality")
            print("⚠️ May need prompt tuning for optimal results")
            
            return 0
        else:
            print("\\n❌ INSUFFICIENT PROFILE QUALITY")
            print(f"❌ Profiles have only {avg_completeness:.1%} field completeness") 
            print("❌ Not suitable for effective recruiter search")
            print("❌ Requires prompt improvement and model tuning")
            
            return 1
    
    else:
        print("\\n❌ QUALITY TEST FAILED!")
        print("❌ No successful profile generations")
        print("❌ System not ready for production use")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)