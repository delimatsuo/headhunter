#!/usr/bin/env python3
"""
Corrected Quality Test - Using Original Enhanced Analysis Structure

Uses the proven prompt from enhanced_together_ai_processor.py that generates
the superior nested enhanced_analysis structure with deep recruiter insights.
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

def create_deep_analysis_prompt(candidate_data: Dict[str, Any]) -> str:
    """Create the ORIGINAL sophisticated recruiter-level analysis prompt"""
    
    name = candidate_data.get('name', 'Unknown')
    experience = f"{candidate_data.get('experience', 0)} years experience with skills: {', '.join(candidate_data.get('skills', []))}"
    education = f"Background at companies: {', '.join(candidate_data.get('companies', []))}"
    comments = candidate_data.get('comments', 'Strong technical background with excellent communication skills.')
    
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
Education: {education}
Recruiter Comments: {comments}

Provide ONLY a JSON response with this EXACT structure:

{{
  "career_trajectory_analysis": {{
    "current_level": "entry/mid/senior/lead/principal/director/vp/c-level",
    "years_to_current_level": 7,
    "promotion_velocity": {{
      "speed": "slow/average/fast/exceptional",
      "average_time_between_promotions": "2.5 years",
      "performance_indicator": "below-average/average/above-average/top-performer",
      "explanation": "Brief explanation of promotion pattern"
    }},
    "career_progression_pattern": "linear/accelerated/stalled/declining/lateral",
    "trajectory_highlights": ["Key career milestone 1", "Key career milestone 2"],
    "career_momentum": "accelerating/steady/slowing/stalled"
  }},
  
  "company_pedigree_analysis": {{
    "company_tier_progression": "improving/stable/declining",
    "current_company_tier": "startup/growth/midmarket/enterprise/fortune500/faang",
    "best_company_worked": "Company name from experience",
    "company_trajectory": [
      {{"company": "Name", "tier": "tier", "years": 2, "role_level": "level"}}
    ],
    "brand_value": "high/medium/low",
    "industry_reputation": "thought-leader/respected/average/unknown"
  }},
  
  "performance_indicators": {{
    "promotion_pattern_analysis": "Detailed analysis of promotion patterns",
    "estimated_performance_tier": "top-10%/top-25%/above-average/average/below-average",
    "key_achievements": ["Achievement that indicates high performance"],
    "special_recognition": ["Awards, special projects, retained through layoffs"],
    "competitive_advantages": ["What makes them stand out"],
    "market_positioning": "highly-sought/in-demand/marketable/challenging-to-place"
  }},
  
  "leadership_scope_evolution": {{
    "has_leadership": true,
    "leadership_growth_pattern": "expanding/stable/contracting/none",
    "max_team_size_managed": 10,
    "current_scope": "IC/team-lead/manager/senior-manager/director/executive",
    "leadership_trajectory": "high-potential/steady-growth/plateaued/unclear",
    "p&l_responsibility": false,
    "cross_functional_leadership": false
  }},
  
  "domain_expertise_assessment": {{
    "primary_domain": "Main area of expertise",
    "expertise_depth": "specialist/expert/generalist/beginner",
    "years_in_domain": 10,
    "technical_skills_trajectory": "expanding/deepening/stagnant/declining",
    "skill_relevance": "cutting-edge/current/dated/obsolete",
    "market_demand_for_skills": "very-high/high/moderate/low"
  }},
  
  "red_flags_and_risks": {{
    "job_stability": "very-stable/stable/moderate/unstable",
    "average_tenure": "2.5 years",
    "concerning_patterns": ["Any red flags observed"],
    "career_risks": ["Potential risks for recruiters"],
    "explanation_needed": ["Things that need clarification in interview"]
  }},
  
  "cultural_indicators": {{
    "work_environment_preference": "startup/scaleup/enterprise/flexible",
    "leadership_style": "collaborative/directive/coaching/hands-off",
    "cultural_values": ["innovation", "stability", "growth"],
    "team_fit": "team-player/independent/both"
  }},
  
  "market_assessment": {{
    "salary_positioning": "$80,000 - $120,000",
    "total_comp_expectation": "$95,000 - $140,000",
    "equity_preference": "cash-focused/balanced/equity-heavy",
    "compensation_motivators": ["base_salary", "equity_upside", "benefits", "title"],
    "market_competitiveness": "highly-competitive/competitive/average/below-market",
    "placement_difficulty": "easy/moderate/challenging/very-difficult",
    "ideal_next_role": "Specific role recommendation",
    "career_ceiling": "Director",
    "years_to_next_level": 3,
    "geographic_flexibility": "local-only/regional/remote-friendly/global",
    "industry_transferability": "high/medium/low"
  }},
  
  "recruiter_verdict": {{
    "overall_rating": "A+/A/B+/B/C+/C/D",
    "recommendation": "highly-recommend/recommend/consider/pass",
    "one_line_pitch": "Compelling one-sentence summary for clients",
    "key_selling_points": ["Strong technical skills", "Leadership abilities", "Ambitious career goals"],
    "competitive_differentiators": ["What makes them unique in market"],
    "interview_strategy": {{
      "focus_areas": ["Technical depth", "Leadership examples", "Career motivation"],
      "potential_concerns": ["Overqualification", "Salary expectations", "Culture fit"],
      "recommended_interviewers": ["Tech lead for depth", "Manager for culture"],
      "assessment_approach": "technical/behavioral/case-study/panel"
    }},
    "placement_intelligence": {{
      "decision_timeline": "fast/moderate/slow",
      "reference_quality": "strong/good/concerning",
      "responsiveness": "immediate/prompt/delayed/poor",
      "opportunity_criteria": ["role_type", "company_stage", "compensation", "growth"]
    }},
    "risk_assessment": {{
      "retention_risk": "low/medium/high",
      "counteroffer_risk": "low/medium/high",
      "cultural_risk": "low/medium/high",
      "performance_risk": "low/medium/high"
    }},
    "client_fit": {{
      "best_fit_companies": ["Types of companies or specific names"],
      "company_stage_preference": ["startup", "growth", "enterprise"],
      "avoid_companies": ["Types to avoid"],
      "culture_requirements": ["innovation", "autonomy", "structure"]
    }}
  }}
}}

Think like a recruiter: faster promotions = better performance, company quality matters, leadership scope growth indicates trust.
"""
    
    return prompt

async def process_candidate_with_enhanced_analysis(config, db, candidate_data):
    """Process a candidate with the original enhanced analysis structure"""
    candidate_id = candidate_data['id']
    print(f"🔄 Processing {candidate_id} with enhanced analysis structure...", end=" ")
    
    # Step 1: Call Together AI with the ORIGINAL proven prompt
    headers = {
        'Authorization': f'Bearer {config.together_ai_api_key}',
        'Content-Type': 'application/json'
    }
    
    enhanced_prompt = create_deep_analysis_prompt(candidate_data)
    
    payload = {
        'model': config.together_ai_model,
        'messages': [{'role': 'user', 'content': enhanced_prompt}],
        'max_tokens': 4000,  # Increased for comprehensive analysis
        'temperature': 0.2  # Lower temperature for consistent analysis
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
            
            # Parse JSON - this should be the nested enhanced_analysis structure
            enhanced_analysis = json.loads(clean_response)
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing failed: {str(e)[:50]}...")
            return None
        
        # Step 3: Create the ORIGINAL enhanced document structure
        enhanced_document = {
            "candidate_id": candidate_id,
            "name": candidate_data.get('name', 'Unknown'),
            "original_data": {
                "education": "",
                "experience": f"{candidate_data.get('experience', 0)} years with {', '.join(candidate_data.get('skills', []))}",
                "comments": [{"text": candidate_data.get('comments', 'Strong technical background')}]
            },
            "enhanced_analysis": enhanced_analysis,  # This is the key - nested analysis structure
            "processing_metadata": {
                "timestamp": datetime.now(),
                "processor": "enhanced_together_ai",
                "model": config.together_ai_model,
                "version": "3.0",
                "analysis_depth": "deep"
            },
            # Flattened fields for easy querying (but keep the nested structure too)
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
        
        # Step 4: Save to Firestore
        if FIRESTORE_AVAILABLE and db:
            save_start = time.time()
            
            # Save to enhanced_candidates collection with the original structure
            doc_ref = db.collection('enhanced_candidates').document(candidate_id)
            doc_ref.set(enhanced_document)
            
            save_time = time.time() - save_start
            total_time = ai_time + save_time
            
            print(f"✅ {total_time:.2f}s (AI:{ai_time:.1f}s + Save:{save_time:.1f}s, ${cost:.4f})")
        else:
            print(f"✅ {ai_time:.2f}s (AI only - Firestore not available, ${cost:.4f})")
        
        return enhanced_document
        
    except Exception as e:
        print(f"❌ Error: {str(e)[:30]}")
        return None

def generate_realistic_test_candidates(num_candidates: int = 10) -> List[Dict[str, Any]]:
    """Generate realistic test candidates with varied backgrounds"""
    
    skills_by_role = {
        'frontend': ['React', 'TypeScript', 'JavaScript', 'CSS', 'HTML', 'Vue.js'],
        'backend': ['Python', 'Node.js', 'Java', 'Go', 'PostgreSQL', 'Redis'],
        'fullstack': ['React', 'Python', 'TypeScript', 'PostgreSQL', 'AWS', 'Docker'],
        'data': ['Python', 'SQL', 'Machine Learning', 'TensorFlow', 'Pandas', 'Spark'],
        'devops': ['AWS', 'Docker', 'Kubernetes', 'Terraform', 'Jenkins', 'Python']
    }
    
    companies_by_tier = {
        'faang': ['Google', 'Meta', 'Amazon', 'Apple', 'Netflix'],
        'enterprise': ['IBM', 'Oracle', 'Salesforce', 'Adobe', 'VMware'],
        'growth': ['Stripe', 'Airbnb', 'Uber', 'Lyft', 'Zoom', 'Slack'],
        'startup': ['Series A Startup', 'Series B Fintech', 'Early Stage AI Company']
    }
    
    comments_templates = [
        "Strong technical background with excellent communication skills. Very collaborative and shows great leadership potential.",
        "Proven leadership experience managing cross-functional teams. High growth potential with deep technical expertise.",
        "Deep domain expertise in fintech with scaling experience. Looking for senior IC or tech lead role at growth company.",
        "Full-stack engineer with startup experience. Prefers fast-paced environments with high autonomy and impact.",
        "Data science expert with production ML experience. Strong analytical skills and business acumen."
    ]
    
    candidates = []
    role_types = list(skills_by_role.keys())
    tier_types = list(companies_by_tier.keys())
    
    for i in range(num_candidates):
        # Rotate through role types for variety
        role_type = role_types[i % len(role_types)]
        tier = tier_types[i % len(tier_types)]
        
        # Generate experience level (senior focus)
        experience_years = 5 + (i % 8)  # 5-12 years experience
        
        # Select skills for this role type
        available_skills = skills_by_role[role_type]
        selected_skills = available_skills[:4]  # 4 core skills
        
        # Select companies from tier
        available_companies = companies_by_tier[tier]
        selected_companies = available_companies[:2]  # 2 companies
        
        # Select comment
        comment = comments_templates[i % len(comments_templates)]
        
        candidate = {
            'id': f'corrected_test_{i+1:03d}',
            'name': f'Enhanced Test Candidate {i+1}',
            'experience': experience_years,
            'role_type': role_type,
            'tier': tier,
            'skills': selected_skills,
            'companies': selected_companies,
            'comments': comment
        }
        
        candidates.append(candidate)
    
    return candidates

def analyze_enhanced_structure_quality(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze the quality of the enhanced_analysis nested structure"""
    
    quality_metrics = {
        'has_enhanced_analysis': False,
        'nested_sections': 0,
        'missing_sections': [],
        'section_completeness': {},
        'overall_score': 0
    }
    
    # Check for the key enhanced_analysis structure
    if 'enhanced_analysis' in profile and isinstance(profile['enhanced_analysis'], dict):
        quality_metrics['has_enhanced_analysis'] = True
        enhanced = profile['enhanced_analysis']
        
        # Expected sections in enhanced_analysis
        expected_sections = [
            'career_trajectory_analysis', 'company_pedigree_analysis', 'performance_indicators',
            'leadership_scope_evolution', 'domain_expertise_assessment', 'red_flags_and_risks',
            'cultural_indicators', 'market_assessment', 'recruiter_verdict'
        ]
        
        for section in expected_sections:
            if section in enhanced and enhanced[section]:
                quality_metrics['nested_sections'] += 1
                # Check sub-fields for key sections
                if section == 'career_trajectory_analysis':
                    sub_fields = ['current_level', 'promotion_velocity', 'career_momentum']
                    filled_fields = sum(1 for field in sub_fields if field in enhanced[section])
                    quality_metrics['section_completeness'][section] = filled_fields / len(sub_fields)
                elif section == 'recruiter_verdict':
                    sub_fields = ['overall_rating', 'recommendation', 'one_line_pitch']
                    filled_fields = sum(1 for field in sub_fields if field in enhanced[section])
                    quality_metrics['section_completeness'][section] = filled_fields / len(sub_fields)
                else:
                    quality_metrics['section_completeness'][section] = 1.0
            else:
                quality_metrics['missing_sections'].append(section)
        
        quality_metrics['overall_score'] = quality_metrics['nested_sections'] / len(expected_sections)
    
    return quality_metrics

async def main():
    """Run corrected quality test with original enhanced analysis structure"""
    print("🚀 Corrected Quality Test - Original Enhanced Analysis Structure")
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
    
    # Generate realistic test candidates (smaller batch for testing)
    candidates = generate_realistic_test_candidates(10)
    print(f"✅ Generated {len(candidates)} realistic test candidates")
    print("   - Testing original enhanced_analysis structure")
    print("   - Focus on nested career analysis and recruiter insights")
    
    print("\\n🔄 Processing candidates with enhanced analysis structure:")
    
    # Process each candidate
    start_time = time.time()
    successful_profiles = []
    total_cost = 0.0
    
    for i, candidate in enumerate(candidates):
        profile = await process_candidate_with_enhanced_analysis(config, db, candidate)
        if profile:
            successful_profiles.append(profile)
            total_cost += profile['processing_metadata'].get('tokens_used', 0) * 0.0000002  # Cost calculation
        
        # Small delay between requests
        if i < len(candidates) - 1:
            await asyncio.sleep(0.5)
    
    total_time = time.time() - start_time
    
    # Analyze enhanced structure quality
    print("\\n" + "=" * 80)
    print("📊 ENHANCED STRUCTURE QUALITY ANALYSIS")
    print("=" * 80)
    
    if successful_profiles:
        # Analyze enhanced structure quality
        quality_analyses = [analyze_enhanced_structure_quality(profile) for profile in successful_profiles]
        
        has_enhanced = sum(1 for qa in quality_analyses if qa['has_enhanced_analysis'])
        avg_nested_sections = sum(qa['nested_sections'] for qa in quality_analyses) / len(quality_analyses)
        avg_completeness = sum(qa['overall_score'] for qa in quality_analyses) / len(quality_analyses)
        
        print(f"✅ Successfully processed: {len(successful_profiles)}/{len(candidates)} candidates ({len(successful_profiles)/len(candidates)*100:.1f}%)")
        print(f"✅ Have enhanced_analysis structure: {has_enhanced}/{len(successful_profiles)} ({has_enhanced/len(successful_profiles)*100:.1f}%)")
        print(f"⏱️  Total processing time: {total_time:.2f}s")
        print(f"⏱️  Average per candidate: {total_time/len(candidates):.2f}s")
        print(f"💰 Total cost: ${total_cost:.4f}")
        
        print("\\n📊 ENHANCED ANALYSIS STRUCTURE METRICS:")
        print(f"   - Average nested sections: {avg_nested_sections:.1f}/9")
        print(f"   - Structure completeness: {avg_completeness:.1%}")
        
        # Sample enhanced analysis
        if successful_profiles and successful_profiles[0].get('enhanced_analysis'):
            print("\\n🔍 SAMPLE ENHANCED ANALYSIS STRUCTURE:")
            sample = successful_profiles[0]
            enhanced = sample.get('enhanced_analysis', {})
            
            print(f"   - Candidate: {sample.get('name')}")
            print(f"   - Current Level: {enhanced.get('career_trajectory_analysis', {}).get('current_level')}")
            print(f"   - Promotion Speed: {enhanced.get('career_trajectory_analysis', {}).get('promotion_velocity', {}).get('speed')}")
            print(f"   - Performance Tier: {enhanced.get('performance_indicators', {}).get('estimated_performance_tier')}")
            print(f"   - Overall Rating: {enhanced.get('recruiter_verdict', {}).get('overall_rating')}")
            print(f"   - One-line Pitch: {enhanced.get('recruiter_verdict', {}).get('one_line_pitch')}")
            print(f"   - Salary Range: {enhanced.get('market_assessment', {}).get('salary_positioning')}")
            
            # Show the nested structure exists
            nested_sections = list(enhanced.keys())
            print(f"   - Nested Sections: {', '.join(nested_sections)}")
        
        # Quality assessment
        if avg_completeness >= 0.9 and has_enhanced == len(successful_profiles):
            print("\\n🎉 EXCELLENT - ORIGINAL STRUCTURE RESTORED!")
            print("✅ All profiles have proper enhanced_analysis structure")
            print(f"✅ Deep nested analysis with {avg_completeness:.1%} completeness")
            print("✅ Ready for production use with enhanced profiles")
            
            return 0
        elif avg_completeness >= 0.7:
            print("\\n✅ GOOD STRUCTURE QUALITY")
            print(f"⚠️ {avg_completeness:.1%} structure completeness")
            print("✅ Enhanced analysis structure is working")
            
            return 0
        else:
            print("\\n❌ STRUCTURE QUALITY ISSUES")
            print(f"❌ Only {avg_completeness:.1%} structure completeness")
            print("❌ May need prompt refinement")
            
            return 1
    
    else:
        print("\\n❌ CORRECTED QUALITY TEST FAILED!")
        print("❌ No successful profile generations")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)