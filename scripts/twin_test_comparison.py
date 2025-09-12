#!/usr/bin/env python3
"""
Twin Test Comparison - Enhanced vs Original Prompts

Compares the enhanced recruiter-grade prompt against the original prompt
using identical candidate data to evaluate quality improvements.
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

def create_original_prompt(candidate_data: Dict[str, Any]) -> str:
    """Original basic prompt for comparison"""
    
    name = candidate_data.get('name', 'Unknown')
    experience = f"{candidate_data.get('experience', 0)} years"
    skills = ', '.join(candidate_data.get('skills', []))
    companies = ', '.join(candidate_data.get('companies', []))
    comments = candidate_data.get('comments', 'Strong technical background.')
    
    prompt = f"""Analyze this candidate and return ONLY valid JSON:

Candidate: {name}
Experience: {experience}
Skills: {skills}
Companies: {companies}
Comments: {comments}

Return this exact JSON structure (no markdown, no explanation):
{{
  "candidate_id": "{candidate_data['id']}",
  "name": "{name}",
  "career_trajectory": {{
    "current_level": "junior|mid|senior|executive",
    "progression_speed": "slow|steady|fast",
    "years_experience": {candidate_data.get('experience', 5)}
  }},
  "leadership_scope": {{
    "has_leadership": true,
    "team_size": 5,
    "leadership_level": "individual|team_lead|manager|director"
  }},
  "technical_skills": {{
    "core_competencies": {json.dumps(candidate_data.get('skills', [])[:3])},
    "skill_depth": "basic|intermediate|advanced|expert"
  }},
  "company_pedigree": {{
    "companies": {json.dumps(candidate_data.get('companies', [])[:2])},
    "company_tier": "startup|mid_market|enterprise"
  }},
  "executive_summary": {{
    "one_line_pitch": "Brief professional summary here",
    "overall_rating": 85
  }},
  "search_keywords": ["keyword1", "keyword2", "keyword3"]
}}"""
    
    return prompt

def create_enhanced_prompt(candidate_data: Dict[str, Any]) -> str:
    """Enhanced recruiter-grade prompt"""
    
    name = candidate_data.get('name', 'Unknown')
    experience = f"{candidate_data.get('experience', 0)} years"
    skills = ', '.join(candidate_data.get('skills', []))
    companies = ', '.join(candidate_data.get('companies', []))
    comments = candidate_data.get('comments', 'Strong technical background.')
    role_type = candidate_data.get('role_type', 'software engineer')
    tier = candidate_data.get('tier', 'growth')
    
    prompt = f"""
You are an elite executive recruiter with 20+ years of experience. Analyze this candidate with deep insight into career patterns, performance indicators, and market positioning.

CRITICAL ANALYSIS FRAMEWORK:
1. PROMOTION VELOCITY: 12-18 months = exceptional; 18-24 months = high performer; 2-3 years = solid; 3+ years = concerning
2. COMPANY TRAJECTORY: Tier progression indicates ambition; lateral moves suggest comfort zone
3. LEADERSHIP EVOLUTION: Team growth patterns show scalability
4. DOMAIN MASTERY: Depth vs breadth, specialization patterns
5. MARKET POSITIONING: Competitive differentiation and placement difficulty

CANDIDATE DATA:
Name: {name}
Experience: {experience}
Skills: {skills}
Companies: {companies}
Role Type: {role_type}
Tier: {tier}
Comments: {comments}

Provide ONLY a JSON response with this enhanced structure:

{{
  "career_trajectory_analysis": {{
    "current_level": "entry/mid/senior/lead/principal/director",
    "years_to_current_level": 5,
    "promotion_velocity": {{
      "speed": "slow/average/fast/exceptional",
      "average_time_between_promotions": "2.5 years",
      "performance_indicator": "below-average/average/above-average/top-performer",
      "explanation": "Brief analysis of promotion pattern"
    }},
    "career_progression_pattern": "linear/accelerated/stalled/declining",
    "trajectory_highlights": ["Key milestone 1", "Key milestone 2"],
    "career_momentum": "accelerating/steady/slowing/stalled"
  }},
  
  "performance_indicators": {{
    "estimated_performance_tier": "top-10%/top-25%/above-average/average/below-average",
    "key_achievements": ["Achievement that indicates high performance"],
    "competitive_advantages": ["What makes them stand out"],
    "market_positioning": "highly-sought/in-demand/marketable/challenging-to-place"
  }},
  
  "recruiter_verdict": {{
    "overall_rating": "A+/A/B+/B/C+/C/D",
    "recommendation": "highly-recommend/recommend/consider/pass",
    "one_line_pitch": "Compelling recruiter summary",
    "key_selling_points": ["Strength 1", "Strength 2", "Strength 3"],
    "placement_intelligence": {{
      "decision_timeline": "fast/moderate/slow",
      "responsiveness": "immediate/prompt/delayed/poor",
      "counteroffer_risk": "low/medium/high"
    }}
  }}
}}

Focus on recruiter-relevant insights for placement success.
"""
    
    return prompt

async def process_candidate_twin_test(config, candidate_data, prompt_type: str):
    """Process candidate with specified prompt type"""
    
    if prompt_type == "original":
        prompt = create_original_prompt(candidate_data)
    elif prompt_type == "enhanced":
        prompt = create_enhanced_prompt(candidate_data)
    else:
        raise ValueError(f"Unknown prompt type: {prompt_type}")
    
    headers = {
        'Authorization': f'Bearer {config.together_ai_api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': config.together_ai_model,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 2000 if prompt_type == "original" else 4000,
        'temperature': 0.1
    }
    
    try:
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{config.together_ai_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=45)
            ) as response:
                ai_time = time.time() - start_time
                
                if response.status != 200:
                    return None, ai_time
                
                result = await response.json()
                ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                tokens_used = result.get('usage', {}).get('total_tokens', 0)
                cost = (tokens_used / 1000000) * 0.20
        
        # Parse response
        try:
            clean_response = ai_response.strip()
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()
            
            parsed_result = json.loads(clean_response)
            
            # Add metadata
            parsed_result['twin_test_metadata'] = {
                'prompt_type': prompt_type,
                'processing_time_seconds': ai_time,
                'tokens_used': tokens_used,
                'api_cost_dollars': cost,
                'timestamp': datetime.now().isoformat()
            }
            
            return parsed_result, ai_time
            
        except json.JSONDecodeError:
            return None, ai_time
            
    except Exception:
        return None, time.time() - start_time

def analyze_prompt_quality(results: List[Dict[str, Any]], prompt_type: str) -> Dict[str, Any]:
    """Analyze quality metrics for a prompt type"""
    
    if not results:
        return {'prompt_type': prompt_type, 'total_profiles': 0}
    
    analysis = {
        'prompt_type': prompt_type,
        'total_profiles': len(results),
        'successful_parses': len([r for r in results if r is not None]),
        'average_fields': 0,
        'depth_score': 0,
        'recruiter_intelligence_score': 0,
        'average_processing_time': 0,
        'total_cost': 0
    }
    
    successful_results = [r for r in results if r is not None]
    if not successful_results:
        return analysis
    
    # Calculate field counts
    total_fields = []
    for result in successful_results:
        field_count = count_nested_fields(result)
        total_fields.append(field_count)
    
    analysis['average_fields'] = sum(total_fields) / len(total_fields) if total_fields else 0
    
    # Depth score (nested structure quality)
    depth_scores = []
    for result in successful_results:
        depth_score = calculate_depth_score(result, prompt_type)
        depth_scores.append(depth_score)
    
    analysis['depth_score'] = sum(depth_scores) / len(depth_scores) if depth_scores else 0
    
    # Recruiter intelligence score
    intelligence_scores = []
    for result in successful_results:
        intelligence_score = calculate_intelligence_score(result, prompt_type)
        intelligence_scores.append(intelligence_score)
    
    analysis['recruiter_intelligence_score'] = sum(intelligence_scores) / len(intelligence_scores) if intelligence_scores else 0
    
    # Performance metrics
    processing_times = []
    costs = []
    for result in successful_results:
        metadata = result.get('twin_test_metadata', {})
        if 'processing_time_seconds' in metadata:
            processing_times.append(metadata['processing_time_seconds'])
        if 'api_cost_dollars' in metadata:
            costs.append(metadata['api_cost_dollars'])
    
    analysis['average_processing_time'] = sum(processing_times) / len(processing_times) if processing_times else 0
    analysis['total_cost'] = sum(costs)
    
    return analysis

def count_nested_fields(obj: Any, depth: int = 0) -> int:
    """Count total fields in nested structure"""
    if not isinstance(obj, dict):
        return 1
    
    total = 0
    for value in obj.values():
        if isinstance(value, dict):
            total += count_nested_fields(value, depth + 1)
        elif isinstance(value, list):
            total += len(value)
        else:
            total += 1
    
    return total

def calculate_depth_score(result: Dict[str, Any], prompt_type: str) -> float:
    """Calculate depth/structure quality score (0-1)"""
    
    if prompt_type == "original":
        # Check for basic expected fields
        expected_sections = ['career_trajectory', 'leadership_scope', 'technical_skills', 'company_pedigree']
        present_sections = sum(1 for section in expected_sections if section in result and result[section])
        return present_sections / len(expected_sections)
    
    elif prompt_type == "enhanced":
        # Check for enhanced analysis sections  
        expected_sections = ['career_trajectory_analysis', 'performance_indicators', 'recruiter_verdict']
        present_sections = 0
        
        for section in expected_sections:
            if section in result and result[section]:
                present_sections += 1
                # Bonus for nested structure depth
                if isinstance(result[section], dict) and len(result[section]) >= 3:
                    present_sections += 0.5
        
        return min(present_sections / len(expected_sections), 1.0)
    
    return 0

def calculate_intelligence_score(result: Dict[str, Any], prompt_type: str) -> float:
    """Calculate recruiter intelligence quality score (0-1)"""
    
    intelligence_indicators = []
    
    if prompt_type == "enhanced":
        # Look for advanced recruiter insights
        if 'career_trajectory_analysis' in result:
            traj = result['career_trajectory_analysis']
            if 'promotion_velocity' in traj and isinstance(traj['promotion_velocity'], dict):
                intelligence_indicators.append(1)
            if 'career_momentum' in traj:
                intelligence_indicators.append(1)
        
        if 'performance_indicators' in result:
            perf = result['performance_indicators']
            if 'competitive_advantages' in perf:
                intelligence_indicators.append(1)
            if 'market_positioning' in perf:
                intelligence_indicators.append(1)
        
        if 'recruiter_verdict' in result:
            verdict = result['recruiter_verdict']
            if 'placement_intelligence' in verdict:
                intelligence_indicators.append(2)  # Double weight for placement intelligence
            if 'key_selling_points' in verdict:
                intelligence_indicators.append(1)
    
    else:  # original
        # Basic intelligence indicators
        if 'executive_summary' in result:
            intelligence_indicators.append(1)
        if 'search_keywords' in result:
            intelligence_indicators.append(0.5)
    
    max_possible = 7 if prompt_type == "enhanced" else 1.5
    return min(sum(intelligence_indicators) / max_possible, 1.0)

def generate_twin_test_candidates(num_candidates: int = 10) -> List[Dict[str, Any]]:
    """Generate candidates for twin testing"""
    
    role_types = ['frontend_engineer', 'backend_engineer', 'data_scientist', 'devops_engineer', 'product_manager']
    tiers = ['startup', 'growth', 'enterprise', 'faang']
    
    candidates = []
    
    for i in range(num_candidates):
        role_type = role_types[i % len(role_types)]
        tier = tiers[i % len(tiers)]
        
        skills_map = {
            'frontend_engineer': ['React', 'TypeScript', 'JavaScript', 'CSS'],
            'backend_engineer': ['Python', 'PostgreSQL', 'Docker', 'AWS'],
            'data_scientist': ['Python', 'SQL', 'Machine Learning', 'TensorFlow'],
            'devops_engineer': ['AWS', 'Kubernetes', 'Docker', 'Terraform'],
            'product_manager': ['Product Strategy', 'Analytics', 'SQL', 'Roadmapping']
        }
        
        companies_map = {
            'startup': ['Series A Startup', 'Early Stage AI'],
            'growth': ['Stripe', 'Airbnb'],
            'enterprise': ['IBM', 'Oracle'],
            'faang': ['Google', 'Meta']
        }
        
        candidate = {
            'id': f'twin_test_{i+1:03d}',
            'name': f'Twin Test Candidate {i+1}',
            'experience': 4 + (i % 6),  # 4-9 years
            'role_type': role_type,
            'tier': tier,
            'skills': skills_map[role_type],
            'companies': companies_map[tier],
            'comments': f'Strong {role_type.replace("_", " ")} with {tier} company experience. Excellent technical skills and collaboration abilities.'
        }
        
        candidates.append(candidate)
    
    return candidates

async def main():
    """Run twin test comparison"""
    print("🔬 Twin Test: Enhanced vs Original Prompt Comparison")
    print("=" * 65)
    
    # Setup
    os.environ['GOOGLE_CLOUD_PROJECT'] = 'headhunter-ai-0088'
    config = Config()
    
    print(f"✅ Together AI Model: {config.together_ai_model}")
    
    # Generate test candidates
    candidates = generate_twin_test_candidates(10)
    print(f"✅ Generated {len(candidates)} test candidates for comparison")
    
    print(f"\\n🔄 Processing candidates with BOTH prompt types:")
    
    # Process each candidate with both prompts
    original_results = []
    enhanced_results = []
    
    for i, candidate in enumerate(candidates):
        print(f"\\n📊 Candidate {i+1}: {candidate['name']}")
        
        # Process with original prompt
        print(f"  🔹 Original prompt...", end=" ")
        original_result, original_time = await process_candidate_twin_test(config, candidate, "original")
        if original_result:
            original_results.append(original_result)
            print(f"✅ {original_time:.1f}s")
        else:
            original_results.append(None)
            print(f"❌ {original_time:.1f}s")
        
        # Small delay
        await asyncio.sleep(0.5)
        
        # Process with enhanced prompt
        print(f"  🔸 Enhanced prompt...", end=" ")
        enhanced_result, enhanced_time = await process_candidate_twin_test(config, candidate, "enhanced")
        if enhanced_result:
            enhanced_results.append(enhanced_result)
            print(f"✅ {enhanced_time:.1f}s")
        else:
            enhanced_results.append(None)
            print(f"❌ {enhanced_time:.1f}s")
        
        # Delay between candidates
        if i < len(candidates) - 1:
            await asyncio.sleep(1)
    
    # Analyze results
    print(f"\\n" + "=" * 65)
    print("📊 TWIN TEST COMPARISON RESULTS")
    print("=" * 65)
    
    original_analysis = analyze_prompt_quality(original_results, "original")
    enhanced_analysis = analyze_prompt_quality(enhanced_results, "enhanced")
    
    # Display comparison
    print(f"\\n📈 PROMPT PERFORMANCE COMPARISON:")
    print(f"")
    print(f"{'Metric':<30} {'Original':<15} {'Enhanced':<15} {'Improvement'}")
    print(f"{'-'*30} {'-'*15} {'-'*15} {'-'*12}")
    
    # Success rate
    orig_success = (original_analysis['successful_parses'] / original_analysis['total_profiles']) * 100
    enh_success = (enhanced_analysis['successful_parses'] / enhanced_analysis['total_profiles']) * 100
    success_improvement = enh_success - orig_success
    print(f"{'Success Rate (%)':<30} {orig_success:<15.1f} {enh_success:<15.1f} {success_improvement:+.1f}%")
    
    # Average fields
    field_improvement = enhanced_analysis['average_fields'] - original_analysis['average_fields']
    print(f"{'Average Fields':<30} {original_analysis['average_fields']:<15.1f} {enhanced_analysis['average_fields']:<15.1f} {field_improvement:+.1f}")
    
    # Depth score
    depth_improvement = enhanced_analysis['depth_score'] - original_analysis['depth_score']
    print(f"{'Structure Depth (0-1)':<30} {original_analysis['depth_score']:<15.2f} {enhanced_analysis['depth_score']:<15.2f} {depth_improvement:+.2f}")
    
    # Intelligence score
    intel_improvement = enhanced_analysis['recruiter_intelligence_score'] - original_analysis['recruiter_intelligence_score']
    print(f"{'Recruiter Intelligence (0-1)':<30} {original_analysis['recruiter_intelligence_score']:<15.2f} {enhanced_analysis['recruiter_intelligence_score']:<15.2f} {intel_improvement:+.2f}")
    
    # Processing time
    time_change = enhanced_analysis['average_processing_time'] - original_analysis['average_processing_time']
    print(f"{'Avg Processing Time (s)':<30} {original_analysis['average_processing_time']:<15.1f} {enhanced_analysis['average_processing_time']:<15.1f} {time_change:+.1f}")
    
    # Cost
    cost_change = enhanced_analysis['total_cost'] - original_analysis['total_cost']
    print(f"{'Total Cost ($)':<30} {original_analysis['total_cost']:<15.4f} {enhanced_analysis['total_cost']:<15.4f} {cost_change:+.4f}")
    
    # Sample comparison
    if enhanced_results and enhanced_results[0] and original_results and original_results[0]:
        print(f"\\n🔍 SAMPLE QUALITY COMPARISON:")
        
        orig_sample = original_results[0]
        enh_sample = enhanced_results[0]
        
        print(f"\\n📋 Original Prompt Output:")
        print(f"   - Fields: {count_nested_fields(orig_sample)}")
        print(f"   - Structure: Basic flat fields")
        print(f"   - One-line Pitch: {orig_sample.get('executive_summary', {}).get('one_line_pitch', 'N/A')[:60]}...")
        
        print(f"\\n📋 Enhanced Prompt Output:")
        print(f"   - Fields: {count_nested_fields(enh_sample)}")
        print(f"   - Structure: Deep nested analysis")
        if 'recruiter_verdict' in enh_sample:
            print(f"   - One-line Pitch: {enh_sample['recruiter_verdict'].get('one_line_pitch', 'N/A')[:60]}...")
        if 'career_trajectory_analysis' in enh_sample:
            print(f"   - Career Analysis: {enh_sample['career_trajectory_analysis'].get('career_momentum', 'N/A')}")
    
    # Final verdict
    improvements = [
        enh_success > orig_success,
        enhanced_analysis['depth_score'] > original_analysis['depth_score'],
        enhanced_analysis['recruiter_intelligence_score'] > original_analysis['recruiter_intelligence_score']
    ]
    
    if sum(improvements) >= 2:
        print(f"\\n🎉 ENHANCED PROMPT WINS!")
        print(f"✅ Superior structure depth and recruiter intelligence")
        print(f"✅ Better suited for professional recruitment workflows")
        print(f"✅ Provides actionable insights for candidate placement")
        return 0
    else:
        print(f"\\n🤔 MIXED RESULTS")
        print(f"⚠️ Enhanced prompt may need further refinement")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)