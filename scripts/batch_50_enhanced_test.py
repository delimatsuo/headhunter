#!/usr/bin/env python3
"""
50-Candidate Enhanced Batch Test

Production-ready test using the corrected enhanced_analysis structure 
with recruiter-grade intelligence for comprehensive candidate profiles.
"""

import asyncio
import aiohttp
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Any
import random

# Add cloud_run_worker to path
sys.path.append('cloud_run_worker')
from config import Config

try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False

def create_enhanced_recruiter_prompt(candidate_data: Dict[str, Any]) -> str:
    """Create the enhanced recruiter-grade analysis prompt"""
    
    name = candidate_data.get('name', 'Unknown')
    experience = f"{candidate_data.get('experience', 0)} years experience"
    skills = ', '.join(candidate_data.get('skills', []))
    companies = ', '.join(candidate_data.get('companies', []))
    comments = candidate_data.get('comments', 'Strong technical background with excellent communication skills.')
    role_type = candidate_data.get('role_type', 'software engineer')
    tier = candidate_data.get('tier', 'growth')
    
    prompt = f"""
You are an elite executive recruiter with 20+ years of experience placing top talent at Fortune 500 companies and high-growth startups. Analyze this candidate using the frameworks that determine placement success and client satisfaction.

CRITICAL RECRUITER ANALYSIS FRAMEWORK:
1. PROMOTION VELOCITY: 12-18 months = exceptional performer; 18-24 months = high performer; 2-3 years = solid performer; 3+ years = average/concerning
2. COMPANY TRAJECTORY: Tier progression (startup→growth→enterprise→FAANG) indicates ambition; staying in same tier suggests comfort zone
3. LEADERSHIP EVOLUTION: Team growth 2→5→10→20+ shows scalability; flat team sizes suggest IC preference
4. DOMAIN MASTERY: 3-5 years = competent; 5-8 years = expert; 8+ years = thought leader; but watch for stagnation
5. INDUSTRY TRANSITIONS: Same industry = deep expertise; 1-2 transitions = adaptable; 3+ = unfocused
6. COMPENSATION SIGNALS: Below-market = retention risk; at-market = stable; above-market = performance premium
7. CULTURAL FIT INDICATORS: Work style, values alignment, team dynamics, change adaptability
8. INTERVIEW RISK FACTORS: Communication gaps, overconfidence, unrealistic expectations, hidden motivations
9. PLACEMENT PREDICTORS: Response to opportunities, decision timeline, reference quality, counteroffer risk
10. COMPETITIVE POSITIONING: What makes them unique, market demand, differentiation factors

CANDIDATE DATA:
Name: {name}
Experience: {experience}
Skills: {skills}
Companies: {companies}  
Role Type: {role_type}
Company Tier: {tier}
Recruiter Comments: {comments}

Provide ONLY a JSON response with this EXACT structure (no markdown, no explanation):

{{
  "career_trajectory_analysis": {{
    "current_level": "entry/mid/senior/lead/principal/director/vp/c-level",
    "years_to_current_level": 5,
    "promotion_velocity": {{
      "speed": "slow/average/fast/exceptional",
      "average_time_between_promotions": "2.5 years",
      "performance_indicator": "below-average/average/above-average/top-performer",
      "explanation": "Brief explanation of promotion pattern based on experience and companies"
    }},
    "career_progression_pattern": "linear/accelerated/stalled/declining/lateral",
    "trajectory_highlights": ["Promotion to {role_type.title()} Lead", "Joined {tier} company"],
    "career_momentum": "accelerating/steady/slowing/stalled"
  }},
  
  "company_pedigree_analysis": {{
    "company_tier_progression": "improving/stable/declining",
    "current_company_tier": "{tier}/startup/growth/midmarket/enterprise/fortune500/faang",
    "best_company_worked": "{companies.split(',')[0] if companies else 'Current Company'}",
    "company_trajectory": [
      {{"company": "{companies.split(',')[0] if companies else 'Company A'}", "tier": "{tier}", "years": 2, "role_level": "senior"}}
    ],
    "brand_value": "high/medium/low",
    "industry_reputation": "thought-leader/respected/average/unknown"
  }},
  
  "performance_indicators": {{
    "promotion_pattern_analysis": "Analysis of career progression showing consistent advancement and skill development",
    "estimated_performance_tier": "top-10%/top-25%/above-average/average/below-average",
    "key_achievements": ["Technical leadership in {role_type} projects", "Team scaling and mentoring"],
    "special_recognition": ["Strong performance reviews", "Retained through company transitions"],
    "competitive_advantages": ["{skills.split(',')[0]} expertise", "Cross-functional leadership", "Domain knowledge"],
    "market_positioning": "highly-sought/in-demand/marketable/challenging-to-place"
  }},
  
  "leadership_scope_evolution": {{
    "has_leadership": true,
    "leadership_growth_pattern": "expanding/stable/contracting/none",
    "max_team_size_managed": 8,
    "current_scope": "IC/team-lead/manager/senior-manager/director/executive",
    "leadership_trajectory": "high-potential/steady-growth/plateaued/unclear",
    "p&l_responsibility": false,
    "cross_functional_leadership": true
  }},
  
  "domain_expertise_assessment": {{
    "primary_domain": "{role_type.replace('_', ' ').title()} Development",
    "expertise_depth": "specialist/expert/generalist/beginner",
    "years_in_domain": {candidate_data.get('experience', 5)},
    "technical_skills_trajectory": "expanding/deepening/stagnant/declining",
    "skill_relevance": "cutting-edge/current/dated/obsolete",
    "market_demand_for_skills": "very-high/high/moderate/low"
  }},
  
  "red_flags_and_risks": {{
    "job_stability": "very-stable/stable/moderate/unstable",
    "average_tenure": "2.5 years",
    "concerning_patterns": [],
    "career_risks": ["Potential for burnout due to rapid advancement"],
    "explanation_needed": ["Career goals and long-term aspirations"]
  }},
  
  "cultural_indicators": {{
    "work_environment_preference": "{tier}/startup/scaleup/enterprise/flexible",
    "leadership_style": "collaborative/directive/coaching/hands-off",
    "cultural_values": ["innovation", "growth", "excellence"],
    "team_fit": "team-player/independent/both"
  }},
  
  "market_assessment": {{
    "salary_positioning": "$120,000 - $180,000",
    "total_comp_expectation": "$150,000 - $220,000",
    "equity_preference": "cash-focused/balanced/equity-heavy",
    "compensation_motivators": ["base_salary", "equity_upside", "career_growth"],
    "market_competitiveness": "highly-competitive/competitive/average/below-market",
    "placement_difficulty": "easy/moderate/challenging/very-difficult",
    "ideal_next_role": "Senior {role_type.replace('_', ' ').title()} or Team Lead role",
    "career_ceiling": "Director/VP of Engineering",
    "years_to_next_level": 2,
    "geographic_flexibility": "local-only/regional/remote-friendly/global",
    "industry_transferability": "high/medium/low"
  }},
  
  "recruiter_verdict": {{
    "overall_rating": "A+/A/B+/B/C+/C/D",
    "recommendation": "highly-recommend/recommend/consider/pass",
    "one_line_pitch": "Skilled {role_type.replace('_', ' ')} leader with {tier} company experience and strong technical depth",
    "key_selling_points": ["{skills.split(',')[0]} expertise", "Leadership experience", "Strong cultural fit"],
    "competitive_differentiators": ["Domain expertise", "Technical mentorship", "Scalable leadership"],
    "interview_strategy": {{
      "focus_areas": ["Technical depth in {skills.split(',')[0]}", "Leadership examples", "Career motivation"],
      "potential_concerns": ["Salary expectations", "Remote work preferences"],
      "recommended_interviewers": ["Tech Lead", "Engineering Manager"],
      "assessment_approach": "technical/behavioral/case-study/panel"
    }},
    "placement_intelligence": {{
      "decision_timeline": "fast/moderate/slow",
      "reference_quality": "strong/good/concerning",
      "responsiveness": "immediate/prompt/delayed/poor",
      "opportunity_criteria": ["technical_growth", "leadership_opportunity", "company_mission"]
    }},
    "risk_assessment": {{
      "retention_risk": "low/medium/high",
      "counteroffer_risk": "low/medium/high",
      "cultural_risk": "low/medium/high",
      "performance_risk": "low/medium/high"
    }},
    "client_fit": {{
      "best_fit_companies": ["{tier.title()} stage companies", "Tech-forward organizations"],
      "company_stage_preference": ["{tier}", "growth", "enterprise"],
      "avoid_companies": ["Early-stage startups", "Very large enterprises"],
      "culture_requirements": ["innovation", "autonomy", "technical_excellence"]
    }}
  }}
}}

Analyze based on the specific candidate data provided. Use realistic assessments based on their experience level, skills, and company background.
"""
    
    return prompt

async def process_enhanced_candidate(config, db, candidate_data):
    """Process a single candidate with enhanced recruiter analysis"""
    candidate_id = candidate_data['id']
    print(f"🔄 Processing {candidate_id}: {candidate_data['name'][:25]}...", end=" ")
    
    # Create enhanced recruiter prompt
    enhanced_prompt = create_enhanced_recruiter_prompt(candidate_data)
    
    headers = {
        'Authorization': f'Bearer {config.together_ai_api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': config.together_ai_model,
        'messages': [{'role': 'user', 'content': enhanced_prompt}],
        'max_tokens': 4000,
        'temperature': 0.2
    }
    
    try:
        start_time = time.time()
        
        # Call Together AI
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{config.together_ai_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                ai_time = time.time() - start_time
                
                if response.status != 200:
                    print(f"❌ HTTP {response.status}")
                    return None
                
                result = await response.json()
                ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                tokens_used = result.get('usage', {}).get('total_tokens', 0)
                cost = (tokens_used / 1000000) * 0.20
        
        # Parse AI response
        try:
            clean_response = ai_response.strip()
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()
            
            enhanced_analysis = json.loads(clean_response)
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON error")
            return None
        
        # Create enhanced candidate document (original structure)
        enhanced_document = {
            "candidate_id": candidate_id,
            "name": candidate_data.get('name', 'Unknown'),
            "original_data": {
                "education": "",
                "experience": f"{candidate_data.get('experience', 0)} years in {candidate_data.get('role_type', 'software development')}",
                "comments": [{"text": candidate_data.get('comments', '')}]
            },
            "enhanced_analysis": enhanced_analysis,  # The key nested structure
            "processing_metadata": {
                "timestamp": datetime.now(),
                "processor": "enhanced_together_ai_batch",
                "model": config.together_ai_model,
                "version": "3.1",
                "analysis_depth": "deep",
                "tokens_used": tokens_used,
                "processing_time_seconds": ai_time,
                "api_cost_dollars": cost
            },
            # Flattened fields for easy querying
            "current_level": enhanced_analysis.get("career_trajectory_analysis", {}).get("current_level", "Unknown"),
            "promotion_velocity": enhanced_analysis.get("career_trajectory_analysis", {}).get("promotion_velocity", {}).get("speed", "unknown"),
            "performance_tier": enhanced_analysis.get("performance_indicators", {}).get("estimated_performance_tier", "average"),
            "overall_rating": enhanced_analysis.get("recruiter_verdict", {}).get("overall_rating", "C"),
            "recommendation": enhanced_analysis.get("recruiter_verdict", {}).get("recommendation", "consider"),
            "salary_range": enhanced_analysis.get("market_assessment", {}).get("salary_positioning", "Unknown"),
            "placement_difficulty": enhanced_analysis.get("market_assessment", {}).get("placement_difficulty", "moderate"),
            "search_keywords": " ".join([
                candidate_data.get('name', ''),
                enhanced_analysis.get("career_trajectory_analysis", {}).get("current_level", ""),
                enhanced_analysis.get("company_pedigree_analysis", {}).get("best_company_worked", ""),
                enhanced_analysis.get("domain_expertise_assessment", {}).get("primary_domain", "")
            ]).lower()
        }
        
        # Save to Firestore
        if FIRESTORE_AVAILABLE and db:
            save_start = time.time()
            doc_ref = db.collection('enhanced_candidates').document(candidate_id)
            doc_ref.set(enhanced_document)
            save_time = time.time() - save_start
            total_time = ai_time + save_time
            
            print(f"✅ {total_time:.1f}s (${cost:.4f})")
        else:
            print(f"✅ {ai_time:.1f}s (${cost:.4f}) - No DB")
        
        return enhanced_document
        
    except Exception as e:
        print(f"❌ Error: {str(e)[:20]}")
        return None

def generate_diverse_candidates(num_candidates: int = 50) -> List[Dict[str, Any]]:
    """Generate diverse realistic candidates for comprehensive testing"""
    
    # Expanded role types
    role_types = [
        'frontend_engineer', 'backend_engineer', 'fullstack_engineer', 
        'data_engineer', 'data_scientist', 'ml_engineer',
        'devops_engineer', 'platform_engineer', 'site_reliability_engineer',
        'mobile_engineer', 'ios_engineer', 'android_engineer',
        'security_engineer', 'cloud_architect', 'solutions_architect',
        'product_manager', 'engineering_manager', 'tech_lead'
    ]
    
    # Skills by role type
    skills_by_role = {
        'frontend_engineer': ['React', 'TypeScript', 'JavaScript', 'Vue.js', 'Angular', 'CSS', 'HTML'],
        'backend_engineer': ['Python', 'Node.js', 'Java', 'Go', 'PostgreSQL', 'Redis', 'Docker'],
        'fullstack_engineer': ['React', 'Python', 'TypeScript', 'PostgreSQL', 'AWS', 'Docker', 'Node.js'],
        'data_engineer': ['Python', 'SQL', 'Apache Spark', 'Airflow', 'Kafka', 'BigQuery', 'Snowflake'],
        'data_scientist': ['Python', 'R', 'SQL', 'TensorFlow', 'Pandas', 'scikit-learn', 'PyTorch'],
        'ml_engineer': ['Python', 'TensorFlow', 'PyTorch', 'MLOps', 'Docker', 'Kubernetes', 'AWS'],
        'devops_engineer': ['AWS', 'Docker', 'Kubernetes', 'Terraform', 'Jenkins', 'Python', 'Linux'],
        'platform_engineer': ['Kubernetes', 'AWS', 'Terraform', 'Python', 'Go', 'Docker', 'Prometheus'],
        'site_reliability_engineer': ['Python', 'Go', 'Kubernetes', 'Prometheus', 'Grafana', 'AWS', 'Linux'],
        'mobile_engineer': ['React Native', 'Swift', 'Kotlin', 'Flutter', 'TypeScript', 'iOS', 'Android'],
        'ios_engineer': ['Swift', 'Objective-C', 'Xcode', 'iOS SDK', 'Core Data', 'SwiftUI'],
        'android_engineer': ['Kotlin', 'Java', 'Android SDK', 'Jetpack Compose', 'Room', 'Retrofit'],
        'security_engineer': ['Python', 'Security', 'Penetration Testing', 'SIEM', 'AWS', 'Cryptography'],
        'cloud_architect': ['AWS', 'Azure', 'GCP', 'Terraform', 'Docker', 'Kubernetes', 'Python'],
        'solutions_architect': ['AWS', 'System Design', 'Microservices', 'Docker', 'Python', 'Java'],
        'product_manager': ['Product Strategy', 'Analytics', 'SQL', 'Roadmapping', 'User Research'],
        'engineering_manager': ['Leadership', 'Python', 'System Design', 'Team Management', 'Strategy'],
        'tech_lead': ['System Design', 'Python', 'Leadership', 'Mentoring', 'Architecture']
    }
    
    # Company tiers with actual companies
    companies_by_tier = {
        'faang': ['Google', 'Meta', 'Amazon', 'Apple', 'Netflix', 'Microsoft', 'Tesla'],
        'enterprise': ['IBM', 'Oracle', 'Salesforce', 'Adobe', 'VMware', 'Cisco', 'Intel'],
        'growth': ['Stripe', 'Airbnb', 'Uber', 'Lyft', 'Zoom', 'Slack', 'Figma', 'Databricks'],
        'midmarket': ['Atlassian', 'ServiceNow', 'Workday', 'Zendesk', 'HubSpot', 'Okta'],
        'startup': ['Series B Fintech', 'AI Startup', 'Healthcare Tech', 'Climate Tech Startup']
    }
    
    # Realistic recruiter comments
    comments_by_role = {
        'frontend': [
            "Strong React expertise with excellent UX sensibilities. Great at collaborating with design teams.",
            "Proven track record scaling frontend systems. Strong TypeScript skills and performance optimization.",
            "Full-stack capable with frontend focus. Great mentoring skills and technical communication."
        ],
        'backend': [
            "Deep systems knowledge with microservices experience. Strong in distributed systems design.",
            "Excellent API design skills with focus on performance and scalability. Great debugging abilities.",
            "Platform engineering background with DevOps crossover. Strong in database optimization."
        ],
        'data': [
            "Strong ML engineering background with production model deployment experience.",
            "Excellent at building data pipelines and working with large-scale distributed systems.",
            "Research background with practical application skills. Great at explaining complex concepts."
        ],
        'leadership': [
            "Proven people manager with strong technical background. Excellent at scaling engineering teams.",
            "Technical leader with strong product sense. Great at balancing technical debt and feature delivery.",
            "Strategic thinker with hands-on technical skills. Excellent at cross-functional collaboration."
        ]
    }
    
    candidates = []
    tier_types = list(companies_by_tier.keys())
    
    for i in range(num_candidates):
        # Rotate through role types
        role_type = role_types[i % len(role_types)]
        tier = tier_types[i % len(tier_types)]
        
        # Generate experience (3-15 years, weighted toward senior)
        experience_weights = [1, 2, 3, 4, 4, 3, 2, 2, 1, 1, 1, 1, 1]  # Peak at 5-8 years
        experience_years = random.choices(range(3, 16), weights=experience_weights)[0]
        
        # Select skills
        available_skills = skills_by_role.get(role_type, ['Python', 'SQL', 'AWS', 'Docker'])
        num_skills = min(4 + (i % 3), len(available_skills))
        selected_skills = available_skills[:num_skills]
        
        # Select companies
        available_companies = companies_by_tier[tier]
        num_companies = min(2 + (i % 2), len(available_companies))
        selected_companies = available_companies[:num_companies]
        
        # Select appropriate comment
        if 'manager' in role_type or 'lead' in role_type:
            comments_pool = comments_by_role['leadership']
        elif 'data' in role_type or 'ml' in role_type:
            comments_pool = comments_by_role['data']  
        elif 'backend' in role_type or 'devops' in role_type or 'platform' in role_type:
            comments_pool = comments_by_role['backend']
        else:
            comments_pool = comments_by_role['frontend']
        
        comment = random.choice(comments_pool)
        
        # Generate realistic name
        first_names = ['Alex', 'Jordan', 'Taylor', 'Casey', 'Morgan', 'Riley', 'Avery', 'Quinn', 'Sage', 'River']
        last_names = ['Chen', 'Patel', 'Johnson', 'Williams', 'Garcia', 'Smith', 'Davis', 'Miller', 'Wilson', 'Lee']
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        
        candidate = {
            'id': f'batch_50_test_{i+1:03d}',
            'name': name,
            'experience': experience_years,
            'role_type': role_type,
            'tier': tier,
            'skills': selected_skills,
            'companies': selected_companies,
            'comments': comment
        }
        
        candidates.append(candidate)
    
    return candidates

def analyze_batch_quality(profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze the quality of the enhanced analysis batch"""
    
    quality_metrics = {
        'total_profiles': len(profiles),
        'with_enhanced_analysis': 0,
        'section_coverage': {},
        'rating_distribution': {},
        'performance_tiers': {},
        'role_coverage': {},
        'average_processing_time': 0,
        'total_cost': 0
    }
    
    if not profiles:
        return quality_metrics
    
    # Analyze each profile
    processing_times = []
    costs = []
    
    for profile in profiles:
        # Check for enhanced_analysis structure
        if 'enhanced_analysis' in profile and profile['enhanced_analysis']:
            quality_metrics['with_enhanced_analysis'] += 1
            enhanced = profile['enhanced_analysis']
            
            # Check section coverage
            sections = [
                'career_trajectory_analysis', 'company_pedigree_analysis', 
                'performance_indicators', 'leadership_scope_evolution',
                'domain_expertise_assessment', 'recruiter_verdict'
            ]
            
            for section in sections:
                if section not in quality_metrics['section_coverage']:
                    quality_metrics['section_coverage'][section] = 0
                if section in enhanced and enhanced[section]:
                    quality_metrics['section_coverage'][section] += 1
        
        # Analyze ratings
        rating = profile.get('overall_rating', 'Unknown')
        quality_metrics['rating_distribution'][rating] = quality_metrics['rating_distribution'].get(rating, 0) + 1
        
        # Analyze performance tiers
        tier = profile.get('performance_tier', 'Unknown')
        quality_metrics['performance_tiers'][tier] = quality_metrics['performance_tiers'].get(tier, 0) + 1
        
        # Track processing metrics
        metadata = profile.get('processing_metadata', {})
        if 'processing_time_seconds' in metadata:
            processing_times.append(metadata['processing_time_seconds'])
        if 'api_cost_dollars' in metadata:
            costs.append(metadata['api_cost_dollars'])
    
    # Calculate averages
    if processing_times:
        quality_metrics['average_processing_time'] = sum(processing_times) / len(processing_times)
    if costs:
        quality_metrics['total_cost'] = sum(costs)
    
    return quality_metrics

async def main():
    """Run 50-candidate enhanced batch test"""
    print("🚀 Enhanced 50-Candidate Batch Test")
    print("=" * 70)
    
    # Setup
    os.environ['GOOGLE_CLOUD_PROJECT'] = 'headhunter-ai-0088'
    config = Config()
    
    print(f"✅ Together AI Model: {config.together_ai_model}")
    
    # Initialize Firestore
    db = None
    if FIRESTORE_AVAILABLE:
        db = firestore.Client()
        print("✅ Firestore client initialized")
    else:
        print("⚠️ Firestore not available - processing only")
    
    # Generate diverse candidates
    candidates = generate_diverse_candidates(50)
    print(f"✅ Generated {len(candidates)} diverse candidates")
    print(f"   - Role types: {len(set(c['role_type'] for c in candidates))}")
    print(f"   - Company tiers: {len(set(c['tier'] for c in candidates))}")
    print(f"   - Experience range: {min(c['experience'] for c in candidates)}-{max(c['experience'] for c in candidates)} years")
    
    print(f"\\n🔄 Processing candidates with enhanced recruiter analysis:")
    
    # Process candidates
    start_time = time.time()
    successful_profiles = []
    
    # Process in batches of 10 for better monitoring
    batch_size = 10
    for batch_start in range(0, len(candidates), batch_size):
        batch_end = min(batch_start + batch_size, len(candidates))
        batch = candidates[batch_start:batch_end]
        
        print(f"\\n📦 Batch {batch_start//batch_size + 1}: Candidates {batch_start+1}-{batch_end}")
        
        # Process batch
        batch_tasks = []
        for candidate in batch:
            batch_tasks.append(process_enhanced_candidate(config, db, candidate))
        
        # Wait for batch completion
        batch_results = await asyncio.gather(*batch_tasks)
        
        # Collect successful results
        for result in batch_results:
            if result:
                successful_profiles.append(result)
        
        # Small delay between batches
        if batch_end < len(candidates):
            print(f"   ⏸️ Cooling down for 2 seconds...")
            await asyncio.sleep(2)
    
    total_time = time.time() - start_time
    
    # Analyze results
    print(f"\\n" + "=" * 70)
    print("📊 ENHANCED BATCH TEST RESULTS")
    print("=" * 70)
    
    quality_analysis = analyze_batch_quality(successful_profiles)
    success_rate = (len(successful_profiles) / len(candidates)) * 100
    
    print(f"✅ Successfully processed: {len(successful_profiles)}/{len(candidates)} candidates ({success_rate:.1f}%)")
    print(f"✅ Enhanced analysis structure: {quality_analysis['with_enhanced_analysis']}/{len(successful_profiles)} ({quality_analysis['with_enhanced_analysis']/len(successful_profiles)*100:.1f}%)")
    print(f"⏱️  Total processing time: {total_time:.1f}s")
    print(f"⏱️  Average per candidate: {total_time/len(candidates):.1f}s")
    print(f"⚡ Throughput: {len(candidates)/(total_time/60):.1f} candidates/minute")
    print(f"💰 Total cost: ${quality_analysis['total_cost']:.4f}")
    print(f"💰 Cost per candidate: ${quality_analysis['total_cost']/len(candidates):.4f}")
    
    # Section coverage analysis
    print(f"\\n📋 SECTION COVERAGE:")
    for section, count in quality_analysis['section_coverage'].items():
        coverage = (count / quality_analysis['with_enhanced_analysis']) * 100 if quality_analysis['with_enhanced_analysis'] > 0 else 0
        print(f"   - {section}: {coverage:.1f}% ({count}/{quality_analysis['with_enhanced_analysis']})")
    
    # Rating distribution
    print(f"\\n🏆 RATING DISTRIBUTION:")
    for rating, count in quality_analysis['rating_distribution'].items():
        print(f"   - {rating}: {count} candidates")
    
    # Performance tiers
    print(f"\\n📈 PERFORMANCE TIERS:")
    for tier, count in quality_analysis['performance_tiers'].items():
        print(f"   - {tier}: {count} candidates")
    
    # Sample analysis
    if successful_profiles:
        sample = successful_profiles[0]
        enhanced = sample.get('enhanced_analysis', {})
        print(f"\\n🔍 SAMPLE PROFILE ANALYSIS:")
        print(f"   - Name: {sample.get('name')}")
        print(f"   - Current Level: {enhanced.get('career_trajectory_analysis', {}).get('current_level')}")
        print(f"   - Performance Tier: {enhanced.get('performance_indicators', {}).get('estimated_performance_tier')}")
        print(f"   - Overall Rating: {enhanced.get('recruiter_verdict', {}).get('overall_rating')}")
        print(f"   - Recommendation: {enhanced.get('recruiter_verdict', {}).get('recommendation')}")
        print(f"   - One-line Pitch: {enhanced.get('recruiter_verdict', {}).get('one_line_pitch')}")
    
    # Final assessment
    if success_rate >= 85 and quality_analysis['with_enhanced_analysis'] >= len(successful_profiles) * 0.9:
        print(f"\\n🎉 BATCH TEST PASSED!")
        print(f"✅ High success rate: {success_rate:.1f}%")
        print(f"✅ Excellent enhanced analysis coverage")
        print(f"✅ Ready for production processing")
        print(f"✅ Cost-effective: ${quality_analysis['total_cost']/len(candidates):.4f} per candidate")
        
        return 0
    else:
        print(f"\\n❌ BATCH TEST NEEDS IMPROVEMENT")
        print(f"⚠️ Success rate: {success_rate:.1f}% (target: 85%+)")
        print(f"⚠️ Enhanced analysis coverage may need improvement")
        
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)