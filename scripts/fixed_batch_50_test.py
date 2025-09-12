#!/usr/bin/env python3
"""
Fixed 50-Candidate Enhanced Batch Test

Uses the proven enhanced_analysis structure from enhanced_together_ai_processor.py
with proper JSON escaping and error handling.
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

def create_proven_enhanced_prompt(candidate_data: Dict[str, Any]) -> str:
    """Use the proven prompt from enhanced_together_ai_processor.py"""
    
    name = candidate_data.get('name', 'Unknown')
    experience_text = f"{candidate_data.get('experience', 5)} years in {candidate_data.get('role_type', 'software development')} with skills: {', '.join(candidate_data.get('skills', []))}"
    companies_text = ', '.join(candidate_data.get('companies', []))
    comments = candidate_data.get('comments', 'Strong technical background with excellent communication skills.')
    
    prompt = f"""
You are an elite executive recruiter with 20+ years of experience. Analyze this candidate with deep insight into career patterns, performance indicators, and market positioning.

CRITICAL ANALYSIS FRAMEWORK:
1. PROMOTION VELOCITY: Fast promotions (18-24 months) indicate high performance; slow promotions (5+ years) suggest average performance
2. COMPANY TRAJECTORY: Moving to better companies = upward trajectory; moving to worse companies = potential issues
3. LEADERSHIP GROWTH: Team size expansion over time indicates trust and capability
4. DOMAIN EXPERTISE: Depth vs breadth, specialization patterns
5. RED FLAGS: Job hopping, demotions, gaps, lateral moves in same company
6. PERFORMANCE PROXIES: Awards, special projects, being retained through layoffs

CANDIDATE DATA:
Name: {name}
Experience: {experience_text[:1000]}
Companies: {companies_text[:500]}
Recruiter Comments: {comments[:500]}

Provide ONLY a JSON response with this EXACT structure:

{{
  "career_trajectory_analysis": {{
    "current_level": "mid",
    "years_to_current_level": {candidate_data.get('experience', 5)},
    "promotion_velocity": {{
      "speed": "average",
      "average_time_between_promotions": "2.5 years",
      "performance_indicator": "above-average",
      "explanation": "Consistent career progression with strong technical growth"
    }},
    "career_progression_pattern": "accelerated",
    "trajectory_highlights": ["Strong technical skills development", "Leadership experience"],
    "career_momentum": "accelerating"
  }},
  
  "company_pedigree_analysis": {{
    "company_tier_progression": "improving",
    "current_company_tier": "growth",
    "best_company_worked": "{candidate_data.get('companies', ['Current Company'])[0]}",
    "company_trajectory": [
      {{"company": "{candidate_data.get('companies', ['Company A'])[0]}", "tier": "growth", "years": 2, "role_level": "senior"}}
    ],
    "brand_value": "medium",
    "industry_reputation": "respected"
  }},
  
  "performance_indicators": {{
    "promotion_pattern_analysis": "Strong upward trajectory with consistent skill development",
    "estimated_performance_tier": "top-25%",
    "key_achievements": ["Technical leadership", "Team mentoring"],
    "special_recognition": ["Strong performance reviews", "Project delivery"],
    "competitive_advantages": ["Technical depth", "Leadership potential", "Domain knowledge"],
    "market_positioning": "in-demand"
  }},
  
  "leadership_scope_evolution": {{
    "has_leadership": true,
    "leadership_growth_pattern": "expanding",
    "max_team_size_managed": 8,
    "current_scope": "team-lead",
    "leadership_trajectory": "high-potential",
    "p&l_responsibility": false,
    "cross_functional_leadership": true
  }},
  
  "domain_expertise_assessment": {{
    "primary_domain": "{candidate_data.get('role_type', 'Software Development').replace('_', ' ').title()}",
    "expertise_depth": "expert",
    "years_in_domain": {candidate_data.get('experience', 5)},
    "technical_skills_trajectory": "expanding",
    "skill_relevance": "current",
    "market_demand_for_skills": "high"
  }},
  
  "red_flags_and_risks": {{
    "job_stability": "stable",
    "average_tenure": "2.5 years",
    "concerning_patterns": [],
    "career_risks": [],
    "explanation_needed": ["Long-term career goals"]
  }},
  
  "cultural_indicators": {{
    "work_environment_preference": "scaleup",
    "leadership_style": "collaborative",
    "cultural_values": ["innovation", "growth", "excellence"],
    "team_fit": "team-player"
  }},
  
  "market_assessment": {{
    "salary_positioning": "$120,000 - $160,000",
    "market_competitiveness": "competitive",
    "placement_difficulty": "moderate",
    "ideal_next_role": "Senior {candidate_data.get('role_type', 'Engineer').replace('_', ' ').title()} or Team Lead",
    "career_ceiling": "Director",
    "years_to_next_level": 2
  }},
  
  "recruiter_verdict": {{
    "overall_rating": "B+",
    "recommendation": "recommend",
    "one_line_pitch": "Strong {candidate_data.get('role_type', 'engineer').replace('_', ' ')} with {candidate_data.get('tier', 'growth')} company experience and leadership potential",
    "key_selling_points": ["Technical expertise", "Leadership potential", "Strong communication"],
    "interview_focus_areas": ["Technical depth", "Leadership examples", "Career goals"],
    "best_fit_companies": ["{candidate_data.get('tier', 'Growth').title()} stage companies"],
    "retention_risk": "low",
    "counteroffer_risk": "medium"
  }}
}}

Think like a recruiter: faster promotions = better performance, company quality matters, leadership scope growth indicates trust.
"""
    
    return prompt

async def process_enhanced_candidate_fixed(config, db, candidate_data):
    """Process candidate with the proven enhanced prompt"""
    candidate_id = candidate_data['id']
    print(f"🔄 {candidate_id}: {candidate_data['name'][:20]}...", end=" ")
    
    # Use the proven enhanced prompt
    enhanced_prompt = create_proven_enhanced_prompt(candidate_data)
    
    headers = {
        'Authorization': f'Bearer {config.together_ai_api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': config.together_ai_model,
        'messages': [{'role': 'user', 'content': enhanced_prompt}],
        'max_tokens': 3000,  # Adequate but not excessive
        'temperature': 0.2   # Lower temperature for consistency
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
                    print(f"❌ HTTP {response.status}")
                    return None
                
                result = await response.json()
                ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                tokens_used = result.get('usage', {}).get('total_tokens', 0)
                cost = (tokens_used / 1000000) * 0.20
        
        # Parse AI response with better error handling
        try:
            # Clean the response more aggressively
            clean_response = ai_response.strip()
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]
            if clean_response.startswith('```'):
                clean_response = clean_response[3:]
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()
            
            # Try to find JSON object if there's extra text
            start_brace = clean_response.find('{')
            end_brace = clean_response.rfind('}')
            if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
                clean_response = clean_response[start_brace:end_brace+1]
            
            enhanced_analysis = json.loads(clean_response)
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON error: {str(e)[:20]}")
            return None
        
        # Create the enhanced document (using the original proven structure)
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
                "processor": "fixed_enhanced_batch",
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
            print(f"✅ {ai_time:.1f}s (${cost:.4f})")
        
        return enhanced_document
        
    except Exception as e:
        print(f"❌ Error: {str(e)[:20]}")
        return None

def generate_test_candidates(num_candidates: int = 50) -> List[Dict[str, Any]]:
    """Generate realistic test candidates"""
    
    role_types = [
        'frontend_engineer', 'backend_engineer', 'fullstack_engineer', 
        'data_scientist', 'devops_engineer', 'mobile_engineer',
        'product_manager', 'engineering_manager', 'tech_lead'
    ]
    
    skills_map = {
        'frontend_engineer': ['React', 'TypeScript', 'JavaScript', 'CSS'],
        'backend_engineer': ['Python', 'PostgreSQL', 'Docker', 'AWS'],
        'fullstack_engineer': ['React', 'Python', 'TypeScript', 'PostgreSQL'],
        'data_scientist': ['Python', 'SQL', 'Machine Learning', 'TensorFlow'],
        'devops_engineer': ['AWS', 'Kubernetes', 'Docker', 'Terraform'],
        'mobile_engineer': ['React Native', 'Swift', 'Kotlin', 'TypeScript'],
        'product_manager': ['Product Strategy', 'Analytics', 'SQL', 'Roadmapping'],
        'engineering_manager': ['Leadership', 'Python', 'Team Management', 'Strategy'],
        'tech_lead': ['System Design', 'Python', 'Leadership', 'Architecture']
    }
    
    tiers = ['startup', 'growth', 'enterprise', 'faang']
    companies_map = {
        'startup': ['Series A Startup', 'Early Stage AI'],
        'growth': ['Stripe', 'Airbnb'],
        'enterprise': ['IBM', 'Oracle'], 
        'faang': ['Google', 'Meta']
    }
    
    comments = [
        "Strong technical background with excellent communication skills.",
        "Proven leadership experience with high growth potential.",
        "Deep technical expertise with scaling experience.",
        "Excellent collaboration skills and mentoring abilities."
    ]
    
    candidates = []
    names = ['Alex Chen', 'Jordan Patel', 'Taylor Smith', 'Casey Davis', 'Morgan Wilson']
    
    for i in range(num_candidates):
        role_type = role_types[i % len(role_types)]
        tier = tiers[i % len(tiers)]
        
        candidate = {
            'id': f'fixed_batch_{i+1:03d}',
            'name': f"{names[i % len(names)]} {i+1}",
            'experience': 3 + (i % 10),  # 3-12 years
            'role_type': role_type,
            'tier': tier,
            'skills': skills_map.get(role_type, ['Python', 'SQL']),
            'companies': companies_map[tier],
            'comments': comments[i % len(comments)]
        }
        
        candidates.append(candidate)
    
    return candidates

async def main():
    """Run fixed 50-candidate batch test"""
    print("🚀 Fixed Enhanced 50-Candidate Batch Test")
    print("=" * 60)
    
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
    
    # Generate candidates
    candidates = generate_test_candidates(50)
    print(f"✅ Generated {len(candidates)} test candidates")
    
    print(f"\\n🔄 Processing with proven enhanced analysis prompt:")
    
    # Process candidates in smaller batches
    start_time = time.time()
    successful_profiles = []
    
    batch_size = 5  # Smaller batches for better success rate
    for batch_start in range(0, len(candidates), batch_size):
        batch_end = min(batch_start + batch_size, len(candidates))
        batch = candidates[batch_start:batch_end]
        
        print(f"\\n📦 Batch {batch_start//batch_size + 1}: Candidates {batch_start+1}-{batch_end}")
        
        for candidate in batch:
            result = await process_enhanced_candidate_fixed(config, db, candidate)
            if result:
                successful_profiles.append(result)
            
            # Small delay between candidates
            await asyncio.sleep(0.3)
        
        # Longer delay between batches
        if batch_end < len(candidates):
            print(f"   ⏸️ Cooling down for 3 seconds...")
            await asyncio.sleep(3)
    
    total_time = time.time() - start_time
    
    # Results analysis
    print(f"\\n" + "=" * 60)
    print("📊 FIXED BATCH TEST RESULTS") 
    print("=" * 60)
    
    success_rate = (len(successful_profiles) / len(candidates)) * 100
    
    print(f"✅ Successfully processed: {len(successful_profiles)}/{len(candidates)} candidates ({success_rate:.1f}%)")
    print(f"⏱️  Total processing time: {total_time:.1f}s")
    print(f"⏱️  Average per candidate: {total_time/len(candidates):.1f}s")
    print(f"⚡ Throughput: {len(candidates)/(total_time/60):.1f} candidates/minute")
    
    if successful_profiles:
        # Calculate costs
        total_cost = sum(p.get('processing_metadata', {}).get('api_cost_dollars', 0) for p in successful_profiles)
        avg_cost = total_cost / len(successful_profiles) if successful_profiles else 0
        
        print(f"💰 Total cost: ${total_cost:.4f}")
        print(f"💰 Cost per candidate: ${avg_cost:.4f}")
        
        # Analyze enhanced structure
        with_enhanced = sum(1 for p in successful_profiles if 'enhanced_analysis' in p and p['enhanced_analysis'])
        enhanced_rate = (with_enhanced / len(successful_profiles)) * 100
        
        print(f"📊 Enhanced analysis structure: {with_enhanced}/{len(successful_profiles)} ({enhanced_rate:.1f}%)")
        
        # Sample analysis
        sample = successful_profiles[0]
        enhanced = sample.get('enhanced_analysis', {})
        print(f"\\n🔍 SAMPLE ANALYSIS:")
        print(f"   - Name: {sample.get('name')}")
        print(f"   - Current Level: {enhanced.get('career_trajectory_analysis', {}).get('current_level')}")
        print(f"   - Performance Tier: {enhanced.get('performance_indicators', {}).get('estimated_performance_tier')}")
        print(f"   - Overall Rating: {enhanced.get('recruiter_verdict', {}).get('overall_rating')}")
        print(f"   - One-line Pitch: {enhanced.get('recruiter_verdict', {}).get('one_line_pitch', '')[:60]}...")
        
        # Show structure depth
        sections = ['career_trajectory_analysis', 'performance_indicators', 'recruiter_verdict', 'leadership_scope_evolution']
        present = sum(1 for section in sections if section in enhanced and enhanced[section])
        print(f"   - Structure sections: {present}/{len(sections)}")
    
    # Final assessment
    if success_rate >= 80 and len(successful_profiles) > 0:
        print(f"\\n🎉 FIXED BATCH TEST PASSED!")
        print(f"✅ High success rate: {success_rate:.1f}%")
        print(f"✅ Enhanced analysis structure working")
        print(f"✅ Ready for production batch processing")
        
        return 0
    else:
        print(f"\\n❌ BATCH TEST NEEDS MORE WORK")
        print(f"⚠️ Success rate: {success_rate:.1f}% (target: 80%+)")
        
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)