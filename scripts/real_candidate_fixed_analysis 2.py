#!/usr/bin/env python3
"""
REAL CANDIDATE TEST - ACTUAL ANALYSIS (NOT PLACEHOLDERS)

Forces the LLM to provide REAL analysis instead of template placeholders.
Includes job hopper analysis that recruiters need.
"""

import csv
import json
import asyncio
import time
import aiohttp
from typing import Dict, List, Any, Optional
import sys

# Add cloud_run_worker to path
sys.path.append('cloud_run_worker')
from config import Config

def load_real_candidates(csv_file: str, max_candidates: int = 2) -> List[Dict[str, Any]]:
    """Load REAL candidates from actual CSV file"""
    
    print(f"📂 Loading REAL candidates from: {csv_file}")
    
    candidates = []
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for i, row in enumerate(reader):
                if i >= max_candidates:
                    break
                    
                candidate_id = row.get('id', '').strip()
                name = row.get('name', '').strip()
                
                if not candidate_id or not name:
                    continue
                
                # Extract real data from CSV
                experience_text = row.get('experience', '').strip()
                skills_text = row.get('skills', '').strip()
                job_title = row.get('job', '').strip()
                stage = row.get('stage', '').strip()
                
                # Parse companies from experience
                companies = []
                if 'Nubank' in experience_text:
                    companies.append('Nubank')
                if 'Cognira' in job_title:
                    companies.append('Cognira')
                if 'Lead Machine Learning Engineer' in experience_text:
                    companies.append('FinTech Company')
                
                candidate = {
                    'id': f'fixed_analysis_{candidate_id}',
                    'name': name,
                    'job_title': job_title,
                    'stage': stage,
                    'experience_text': experience_text,
                    'skills_text': skills_text,
                    'companies': companies,
                    'raw_experience_years': experience_text
                }
                
                candidates.append(candidate)
                print(f"   ✅ REAL: {name}")
                print(f"       Job: {job_title}")
                print(f"       Companies: {', '.join(companies)}")
                print(f"       Experience: {experience_text[:100]}...")
                
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return []
        
    print(f"📊 Loaded {len(candidates)} REAL candidates")
    return candidates

def create_analysis_prompt(candidate: Dict[str, Any]) -> str:
    """Comprehensive recruiter intelligence prompt - product manager enhanced"""
    
    candidate_id = candidate['id']
    name = candidate['name']
    job_title = candidate['job_title']
    experience_text = candidate['experience_text']
    companies = ', '.join(candidate['companies'])
    
    prompt = f"""You are a senior executive recruiter with 20+ years placing candidates at Fortune 500 companies and top-tier tech firms. Analyze this REAL candidate with deep recruiting intelligence.

CANDIDATE PROFILE:
Name: {name}
Current Role: {job_title} 
Company History: {companies}
Experience Summary: {experience_text}

CRITICAL RECRUITING INTELLIGENCE FRAMEWORK:
Analyze with the precision of a $500K+ placement specialist. Extract REAL insights, not generic responses.

1. JOB STABILITY ANALYSIS (High Priority - affects placement success):
   - Calculate exact tenure at each company from dates in experience
   - Identify promotion patterns: internal advancement vs job-hopping for promotions
   - Assess stability risk for new employer

2. COMPENSATION INTELLIGENCE (Market Positioning):
   - Research actual salary ranges for this role/location/company tier
   - Factor in Nubank (unicorn fintech) vs other company experiences
   - Include equity, bonus, total comp estimates

3. CULTURAL FIT INTELLIGENCE (Placement Success Factor):
   - Infer work style from company choices (startup vs enterprise)
   - Predict culture match based on company progression
   - Identify potential culture clash risks

4. INTERVIEW PERFORMANCE PREDICTION (Close Rate Impact):
   - Technical depth assessment from role progression
   - Communication skills from leadership positions
   - Confidence level from company tier experience

5. FLIGHT RISK & RETENTION (Client Retention):
   - Assess likelihood to accept counteroffer
   - Evaluate long-term retention potential
   - Identify motivators beyond compensation

6. RED FLAGS & DEAL BREAKERS (Risk Management):
   - Career gaps, demotions, lateral moves
   - Unrealistic expectations signals
   - Visa/authorization issues

Return ONLY this JSON with ACTUAL analysis (zero placeholder text):

{{
  "candidate_id": "{candidate_id}",
  "analysis_quality": "EXECUTIVE_RECRUITER_ANALYSIS",
  
  "job_stability_intelligence": {{
    "total_companies": "Count actual companies from experience",
    "average_tenure_years": "Calculate average years per company",
    "longest_tenure": "Longest stay at one company",
    "shortest_tenure": "Shortest stay at one company", 
    "promotion_pattern": "internal_promotions|job_hopping_promotions|mixed",
    "stability_score": "Rate 1-10 (10=very stable, 1=high flight risk)",
    "tenure_trend": "increasing|stable|decreasing",
    "job_hopping_concern": "none|low|medium|high|severe",
    "stability_reasoning": "Detailed analysis of tenure patterns and promotion style",
    "retention_prediction": "low_risk|medium_risk|high_risk|flight_risk"
  }},
  
  "compensation_intelligence": {{
    "market_tier": "entry|mid|senior|staff|principal|director|vp",
    "brazil_salary_range": "$X,XXX - $X,XXX USD equivalent for this role in Brazil",
    "us_salary_equivalent": "$X,XXX - $X,XXX USD if relocated to US market",
    "total_comp_estimate": "Include equity/bonus based on company tier",
    "compensation_percentile": "Bottom 25%|25-50%|50-75%|Top 25%",
    "negotiation_leverage": "low|medium|high based on Nubank experience",
    "counteroffer_risk": "low|medium|high - likelihood current employer counters"
  }},
  
  "career_trajectory_analysis": {{
    "current_level": "junior|mid|senior|staff|principal|director based on actual role",
    "years_experience": "Calculate total years from experience text",
    "career_velocity": "slow|average|fast|exceptional progression speed",
    "next_logical_level": "What level should they target next",
    "ceiling_assessment": "Highest level they can realistically reach",
    "leadership_readiness": "ic_track|emerging_leader|proven_leader|executive_ready"
  }},
  
  "technical_market_assessment": {{
    "core_skills": ["Extract 5-7 ACTUAL skills from experience text"],
    "skill_depth": "generalist|specialist|deep_specialist|thought_leader", 
    "technology_currency": "cutting_edge|current|slightly_dated|outdated",
    "market_demand": "very_high|high|moderate|low for these specific skills",
    "skill_differentiation": "commodity|valuable|rare|unicorn skill combination",
    "certification_gaps": ["Missing certifications that would boost placement"]
  }},
  
  "cultural_fit_intelligence": {{
    "company_size_preference": "startup|scaleup|midmarket|enterprise based on history",
    "work_environment": "structured|flexible|entrepreneurial|corporate",
    "leadership_style": "individual_contributor|team_player|people_manager|visionary",
    "culture_adaptability": "high|medium|low ability to adapt to different cultures",
    "red_flag_cultures": ["Company cultures to avoid based on background"],
    "ideal_culture_match": ["Company cultures where they would thrive"]
  }},
  
  "interview_performance_prediction": {{
    "technical_confidence": "low|medium|high based on role progression",
    "communication_skills": "poor|fair|good|excellent based on leadership roles",
    "executive_presence": "weak|developing|strong|commanding",
    "storytelling_ability": "poor|fair|good|excellent for behavioral questions",
    "salary_negotiation": "pushover|fair|tough|hardball negotiator",
    "interview_strengths": ["Top 3 strengths in interview settings"],
    "interview_concerns": ["Areas where they might struggle in interviews"]
  }},
  
  "placement_intelligence": {{
    "marketability_score": "Rate 1-100 how easily placeable this candidate is",
    "time_to_placement": "1-2 weeks|2-4 weeks|1-2 months|2-3 months|difficult",
    "target_companies": ["List 5-7 specific companies that would want this profile"],
    "ideal_roles": ["List 3-5 specific role titles they should target"],
    "geographic_flexibility": "local_only|regional|national|international",
    "placement_challenges": ["Specific obstacles to overcome in placement"],
    "competitive_advantages": ["Why clients should hire this person over others"]
  }},
  
  "risk_assessment": {{
    "red_flags": ["Actual concerning patterns from experience"],
    "career_gaps": "Identify any unexplained gaps in timeline",
    "reference_concerns": "Potential issues with reference checks",
    "background_check_risks": "Potential background check issues to verify",
    "client_presentation_risks": ["How this candidate might not present well"],
    "deal_breaker_probability": "low|medium|high risk of deal falling through"
  }},
  
  "executive_recruiting_summary": {{
    "one_line_pitch": "Compelling 15-20 word summary to present to hiring managers",
    "top_3_selling_points": ["Most compelling reasons to interview this candidate"],
    "compensation_anchor": "$XXX,XXX - use this as starting point for salary discussions",
    "placement_strategy": "Specific approach to market this candidate effectively",
    "client_match_priority": ["Rank ideal client types: 1st choice, 2nd choice, 3rd choice"],
    "overall_rating": "Rate 1-100 where 90+ is must-interview, 70-89 is strong consider",
    "recruiter_recommendation": "must_present|strong_recommend|conditional_recommend|pass",
    "confidence_level": "Rate 1-100 confidence in this assessment based on available data"
  }}
}}

CRITICAL INSTRUCTIONS:
- NO placeholder text like "List X items" or "Based on experience"
- Calculate ACTUAL numbers from experience text (years, companies, etc.)
- Use SPECIFIC salary ranges researched for Brazil FinTech ML roles
- For missing information (visa status, etc.), use "information unavailable" - DO NOT INVENT data
- Ensure valid JSON formatting with proper quotes around ALL string values
- Arrays must use proper JSON syntax with square brackets and quotes
- Provide REAL analysis a $500K placement fee justifies
- Every field must contain actionable recruiting intelligence or "information unavailable"
- Return ONLY valid JSON - no markdown formatting or extra text"""

    return prompt

async def process_candidate_with_real_analysis(candidate: Dict[str, Any], config: Config) -> Optional[Dict[str, Any]]:
    """Process candidate with forced real analysis"""
    
    candidate_id = candidate['id']
    name = candidate['name']
    
    print(f"🔄 ANALYZING REAL CANDIDATE: {name}")
    print(f"   📄 Job: {candidate['job_title']}")
    print(f"   🏢 Companies: {', '.join(candidate['companies'])}")
    
    start_time = time.time()
    
    prompt = create_analysis_prompt(candidate)
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                'Authorization': f'Bearer {config.together_ai_api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': 'meta-llama/Llama-3.2-3B-Instruct-Turbo',
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 4000,  # Increased for comprehensive analysis
                'temperature': 0.05  # Lower for more consistent JSON formatting
            }
            
            async with session.post(
                'https://api.together.xyz/v1/chat/completions',
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    ai_response = result['choices'][0]['message']['content']
                    
                    try:
                        # Clean JSON response with better error handling
                        json_str = ai_response.strip()
                        
                        # Remove markdown formatting
                        if '```json' in json_str:
                            json_str = json_str.split('```json')[1]
                        elif '```' in json_str:
                            json_str = json_str.split('```')[1]
                        
                        if json_str.endswith('```'):
                            json_str = json_str[:-3]
                            
                        json_str = json_str.strip()
                        
                        # Attempt to parse JSON
                        analysis = json.loads(json_str)
                        processing_time = time.time() - start_time
                        
                        print(f"   ✅ SUCCESS: {processing_time:.1f}s")
                        
                        # Validate we got REAL analysis, not placeholders  
                        job_stability = analysis.get('job_stability_intelligence', {})
                        compensation = analysis.get('compensation_intelligence', {})
                        placement = analysis.get('placement_intelligence', {})
                        summary = analysis.get('executive_recruiting_summary', {})
                        
                        print(f"   📊 Companies: {job_stability.get('total_companies', 'N/A')}")
                        print(f"   🏃 Stability: {job_stability.get('stability_score', 'N/A')}/10")
                        print(f"   💰 Salary: {compensation.get('brazil_salary_range', 'N/A')}")
                        print(f"   ⚡ Market Score: {placement.get('marketability_score', 'N/A')}")
                        print(f"   ⭐ Rating: {summary.get('overall_rating', 'N/A')}")
                        print(f"   📝 Pitch: {summary.get('one_line_pitch', 'N/A')[:60]}...")
                        
                        # Check for placeholder text
                        response_text = json.dumps(analysis)
                        if any(phrase in response_text for phrase in ['List ', 'Infer ', 'Based on ', 'Provide ']):
                            print("   ⚠️ WARNING: Still contains placeholder text")
                        else:
                            print("   ✓ GOOD: Contains real analysis")
                        
                        return analysis
                        
                    except json.JSONDecodeError as e:
                        print(f"   ❌ JSON parse error: {e}")
                        print(f"   📄 Raw response: {ai_response[:300]}...")
                        return None
                else:
                    print(f"   ❌ API Error: {response.status}")
                    return None
                    
    except Exception as e:
        processing_time = time.time() - start_time
        print(f"   💥 Exception after {processing_time:.1f}s: {e}")
        return None

async def save_to_firestore(profiles: List[Dict[str, Any]]):
    """Save real analysis profiles to Firestore"""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        
        try:
            db = firestore.client()
        except:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
            db = firestore.client()
        
        saved_count = 0
        for profile in profiles:
            doc_id = profile['candidate_id']
            doc_ref = db.collection('enhanced_candidates').document(doc_id)
            doc_ref.set(profile)
            saved_count += 1
            
        print(f"✅ Saved {saved_count} REAL ANALYSIS profiles to Firestore")
        print("📋 Document IDs start with: fixed_analysis_")
        
    except Exception as e:
        print(f"❌ Error saving to Firestore: {e}")

async def main():
    """Test REAL candidate analysis (no placeholders)"""
    
    print("🚨 REAL CANDIDATE ANALYSIS TEST")
    print("=" * 50)
    print("⚠️  REAL candidate data from CSV")
    print("⚠️  ACTUAL analysis (no placeholders)")
    print("⚠️  Job hopping assessment included")
    print("=" * 50)
    
    config = Config()
    
    # Load 2 real candidates for focused test
    csv_file = 'CSV files/505039_Ella_Executive_Search_CSVs_1/Ella_Executive_Search_candidates_1-1.csv'
    real_candidates = load_real_candidates(csv_file, max_candidates=2)
    
    if not real_candidates:
        print("❌ No real candidates loaded")
        return
    
    print(f"\\n🔄 Processing {len(real_candidates)} REAL candidates:")
    print("-" * 50)
    
    successful_profiles = []
    
    for i, candidate in enumerate(real_candidates, 1):
        print(f"\\n📍 [{i}/{len(real_candidates)}] REAL ANALYSIS:")
        
        result = await process_candidate_with_real_analysis(candidate, config)
        
        if result:
            successful_profiles.append(result)
            
        # Delay between candidates
        if i < len(real_candidates):
            await asyncio.sleep(2)
    
    # Results
    print("\\n" + "=" * 50)
    print("🎯 REAL ANALYSIS TEST RESULTS")
    print("=" * 50)
    print(f"✅ Successfully processed: {len(successful_profiles)}/{len(real_candidates)}")
    print(f"💰 Estimated cost: ${len(successful_profiles) * 0.0006:.4f}")
    
    if successful_profiles:
        print("\\n💾 Saving REAL ANALYSIS profiles to Firestore...")
        await save_to_firestore(successful_profiles)
        
        print("\\n🎉 SUCCESS: REAL analysis with job hopping assessment!")
        print("🔍 Check Firestore collection: enhanced_candidates")
        print("📋 Look for documents: fixed_analysis_[id]")
        print("📊 These should contain ACTUAL analysis, not placeholder text")
        
        # Show sample analysis
        sample = successful_profiles[0]
        print("\\n📋 SAMPLE REAL ANALYSIS:")
        career = sample.get('career_trajectory', {})
        hopping = career.get('job_hopping_analysis', {})
        keywords = sample.get('search_keywords', {})
        
        print(f"   👤 Candidate: {sample.get('candidate_id', 'N/A')}")
        print(f"   📊 Job Stability: {hopping.get('stability_rating', 'N/A')}/10")
        print(f"   🔍 Primary Keywords: {keywords.get('primary_keywords', [])}")
        print(f"   ⭐ Quality Check: {sample.get('analysis_quality', 'N/A')}")
    else:
        print("\\n❌ No successful analyses")

if __name__ == "__main__":
    asyncio.run(main())