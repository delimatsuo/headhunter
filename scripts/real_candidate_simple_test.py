#!/usr/bin/env python3
"""
REAL CANDIDATE TEST - SIMPLIFIED

Uses the EXACT same processing code that worked in the 50-candidate test,
but with REAL candidate data from CSV files.
"""

import csv
import json
import asyncio
import time
import aiohttp
from typing import Dict, List, Any, Optional
import sys
import os

# Add cloud_run_worker to path
sys.path.append('cloud_run_worker')
from config import Config

def load_real_candidates(csv_file: str, max_candidates: int = 3) -> List[Dict[str, Any]]:
    """Load REAL candidates from actual CSV file"""
    
    print(f"📂 Loading REAL candidates from: {csv_file}")
    
    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        return []
        
    candidates = []
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for i, row in enumerate(reader):
                if i >= max_candidates:
                    break
                    
                # Only process candidates with real data
                candidate_id = row.get('id', '').strip()
                name = row.get('name', '').strip()
                
                if not candidate_id or not name:
                    continue
                    
                # Build real resume text from CSV data
                resume_parts = []
                
                if row.get('headline', '').strip():
                    resume_parts.append(f"Professional Title: {row['headline'].strip()}")
                    
                if row.get('summary', '').strip():
                    resume_parts.append(f"Professional Summary: {row['summary'].strip()}")
                    
                if row.get('experience', '').strip():
                    resume_parts.append(f"Professional Experience: {row['experience'].strip()}")
                    
                if row.get('education', '').strip():
                    resume_parts.append(f"Education: {row['education'].strip()}")
                    
                if row.get('skills', '').strip():
                    resume_parts.append(f"Technical Skills: {row['skills'].strip()}")
                
                resume_text = '\\n\\n'.join(resume_parts) if resume_parts else f"Professional: {name}"
                
                candidate = {
                    'id': f'real_candidate_{candidate_id}',  # Mark as real data
                    'name': name,
                    'current_title': row.get('job', 'Software Engineer').strip(),
                    'recruiter_comments': f"Stage: {row.get('stage', '')}. Real candidate from Ella Executive Search database.",
                    'raw_data': {
                        'resume_text': resume_text,
                        'linkedin_profile': row.get('social_profiles', '').strip(),
                        'email': row.get('email', '').strip()
                    }
                }
                
                candidates.append(candidate)
                print(f"   ✅ REAL: {name} (ID: {candidate_id}) - {candidate['current_title']}")
                
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return []
        
    print(f"📊 Loaded {len(candidates)} REAL candidates")
    return candidates

async def process_real_candidate_with_ai(candidate: Dict[str, Any], config: Config) -> Optional[Dict[str, Any]]:
    """Process ONE real candidate using Together AI - same code that worked in tests"""
    
    candidate_id = candidate['id']
    name = candidate['name']
    
    print(f"🔄 Processing REAL candidate: {name} ({candidate_id})")
    print(f"   💼 Job: {candidate.get('current_title', 'N/A')}")
    print(f"   📄 Resume: {candidate['raw_data']['resume_text'][:100]}...")
    
    start_time = time.time()
    
    # Use the EXACT same prompt structure that worked in successful tests
    prompt = f'''
You are an elite executive recruiter analyzing candidate profiles for senior technical positions.

CANDIDATE INFORMATION:
Name: {name}
Current Title: {candidate.get("current_title", "Software Engineer")}
Resume/Profile Text: {candidate["raw_data"]["resume_text"]}
Recruiter Comments: {candidate.get("recruiter_comments", "No additional comments")}

COMPREHENSIVE ANALYSIS REQUIRED:
Analyze this candidate and provide detailed insights in this EXACT JSON structure:

{{
  "candidate_id": "{candidate_id}",
  "name": "{name}",
  "personal_info": {{
    "current_title": "{candidate.get("current_title", "Software Engineer")}",
    "location": "Not specified",
    "phone": "Not specified",
    "email": "{candidate["raw_data"].get("email", "Not specified")}"
  }},
  "enhanced_analysis": {{
    "career_trajectory_analysis": {{
      "current_level": "senior",
      "years_experience": 8,
      "career_momentum": "strong",
      "progression_speed": "steady"
    }},
    "leadership_scope": {{
      "has_leadership": true,
      "team_size_managed": 5,
      "leadership_level": "team_lead"
    }},
    "company_pedigree": {{
      "company_tier": "enterprise",
      "career_stability": "stable"
    }},
    "skill_assessment": {{
      "technical_skills": {{
        "core_competencies": ["Python", "AWS", "SQL"],
        "skill_depth": "advanced"
      }}
    }},
    "executive_summary": {{
      "one_line_pitch": "Experienced software engineer with strong technical background",
      "overall_rating": 85,
      "recommendation": "strong-consider"
    }}
  }}
}}

Respond with ONLY the JSON object. No additional text.
'''
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                'Authorization': f'Bearer {config.together_ai_api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': 'meta-llama/Llama-3.2-3B-Instruct-Turbo',
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 2000,
                'temperature': 0.1
            }
            
            async with session.post(
                'https://api.together.xyz/v1/chat/completions',
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    ai_response = result['choices'][0]['message']['content']
                    
                    # Parse JSON response
                    try:
                        enhanced_profile = json.loads(ai_response)
                        processing_time = time.time() - start_time
                        
                        print(f"   ✅ SUCCESS: {processing_time:.1f}s")
                        
                        # Show analysis results
                        analysis = enhanced_profile.get('enhanced_analysis', {})
                        career = analysis.get('career_trajectory_analysis', {})
                        summary = analysis.get('executive_summary', {})
                        
                        print(f"   📊 Level: {career.get('current_level', 'N/A')}")
                        print(f"   🎯 Rating: {summary.get('overall_rating', 'N/A')}")
                        print(f"   📝 Pitch: {summary.get('one_line_pitch', 'N/A')}")
                        
                        return enhanced_profile
                        
                    except json.JSONDecodeError as e:
                        print(f"   ❌ JSON parse error: {e}")
                        print(f"   📄 Raw response: {ai_response[:200]}...")
                        return None
                else:
                    print(f"   ❌ API Error: {response.status}")
                    error_text = await response.text()
                    print(f"   📄 Error: {error_text[:200]}...")
                    return None
                    
    except Exception as e:
        processing_time = time.time() - start_time
        print(f"   💥 Exception after {processing_time:.1f}s: {e}")
        return None

async def save_to_firestore(profiles: List[Dict[str, Any]]):
    """Save real candidate profiles to Firestore"""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        
        # Initialize Firebase
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
            print(f"   💾 Saved {profile['name']} to Firestore")
            
        print(f"✅ Saved {saved_count} REAL profiles to Firestore")
        print(f"🔍 Check collection: enhanced_candidates")
        print(f"📋 Document IDs start with: real_candidate_")
        
    except Exception as e:
        print(f"❌ Error saving to Firestore: {e}")

async def main():
    """Run REAL candidate test with actual CSV data"""
    
    print("🚨 REAL CANDIDATE END-TO-END TEST")
    print("=" * 50)
    print("⚠️  Using ACTUAL candidate data from CSV files")
    print("⚠️  NO MOCK DATA - Only real profiles")
    print("=" * 50)
    
    # Load configuration
    config = Config()
    
    # Load 3 real candidates
    csv_file = 'CSV files/505039_Ella_Executive_Search_CSVs_1/Ella_Executive_Search_candidates_1-1.csv'
    real_candidates = load_real_candidates(csv_file, max_candidates=3)
    
    if not real_candidates:
        print("❌ No real candidates loaded - test failed")
        return
    
    print(f"\\n🔄 Processing {len(real_candidates)} REAL candidates:")
    print("-" * 40)
    
    successful_profiles = []
    failed_count = 0
    
    for i, candidate in enumerate(real_candidates, 1):
        print(f"\\n📍 [{i}/{len(real_candidates)}] Processing...")
        
        result = await process_real_candidate_with_ai(candidate, config)
        
        if result:
            successful_profiles.append(result)
        else:
            failed_count += 1
            
        # Short delay between candidates
        if i < len(real_candidates):
            await asyncio.sleep(2)
    
    # Results summary
    total = len(real_candidates)
    success_rate = (len(successful_profiles) / total) * 100 if total > 0 else 0
    
    print(f"\\n" + "=" * 50)
    print(f"🎯 REAL CANDIDATE TEST RESULTS")
    print(f"=" * 50)
    print(f"✅ Successfully processed: {len(successful_profiles)}/{total} ({success_rate:.1f}%)")
    print(f"❌ Failed: {failed_count}")
    print(f"💰 Estimated cost: ${len(successful_profiles) * 0.0005:.4f}")
    
    # Save to Firestore
    if successful_profiles:
        print(f"\\n💾 Saving REAL profiles to Firestore...")
        await save_to_firestore(successful_profiles)
        
        print(f"\\n🎉 SUCCESS: Real candidates processed and saved!")
        print(f"🔍 Review in Firestore: enhanced_candidates collection")
        print(f"📋 Look for documents: real_candidate_[id]")
    else:
        print(f"\\n❌ No successful profiles to save")

if __name__ == "__main__":
    asyncio.run(main())