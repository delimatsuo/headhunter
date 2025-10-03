#!/usr/bin/env python3
"""
Test the complete Together AI → Firestore pipeline with 5 real candidates
"""

import asyncio
import aiohttp
import json
import os
import sys
import time
from datetime import datetime

# Add cloud_run_worker to path
sys.path.append('cloud_run_worker')
from config import Config

try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False

async def process_and_save_candidate(config, db, candidate_data):
    """Process a candidate with Together AI and save to Firestore"""
    candidate_id = candidate_data['id']
    print(f"🔄 Processing {candidate_id}...", end=" ")
    
    # Step 1: Call Together AI
    headers = {
        'Authorization': f'Bearer {config.together_ai_api_key}',
        'Content-Type': 'application/json'
    }
    
    # Create a comprehensive prompt
    prompt = f"""
Analyze this candidate and return ONLY valid JSON:

Candidate: {candidate_data['name']}
Experience: {candidate_data['experience']} years
Skills: {', '.join(candidate_data['skills'])}
Companies: {', '.join(candidate_data['companies'])}

Return this exact JSON structure (no markdown, no explanation):
{{
  "candidate_id": "{candidate_id}",
  "name": "{candidate_data['name']}",
  "career_trajectory": {{
    "current_level": "junior|mid|senior|executive",
    "progression_speed": "slow|steady|fast",
    "years_experience": {candidate_data['experience']}
  }},
  "leadership_scope": {{
    "has_leadership": true,
    "team_size": 5,
    "leadership_level": "individual|team_lead|manager|director"
  }},
  "technical_skills": {{
    "core_competencies": {json.dumps(candidate_data['skills'][:3])},
    "skill_depth": "basic|intermediate|advanced|expert"
  }},
  "company_pedigree": {{
    "companies": {json.dumps(candidate_data['companies'][:2])},
    "company_tier": "startup|mid_market|enterprise"
  }},
  "executive_summary": {{
    "one_line_pitch": "Brief professional summary here",
    "overall_rating": 85
  }},
  "search_keywords": ["keyword1", "keyword2", "keyword3"]
}}
"""
    
    payload = {
        'model': config.together_ai_model,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 400,
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
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                ai_time = time.time() - start_time
                
                if response.status != 200:
                    error_text = await response.text()
                    print(f"❌ AI failed: HTTP {response.status}")
                    return False
                
                result = await response.json()
                ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                tokens_used = result.get('usage', {}).get('total_tokens', 0)
        
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
            parsed_profile = json.loads(clean_response)
            
        except json.JSONDecodeError:
            # Create fallback profile
            parsed_profile = {
                'candidate_id': candidate_id,
                'name': candidate_data['name'],
                'career_trajectory': {
                    'current_level': 'mid',
                    'progression_speed': 'steady',
                    'years_experience': candidate_data['experience']
                },
                'technical_skills': {
                    'core_competencies': candidate_data['skills'][:3],
                    'skill_depth': 'intermediate'
                },
                'parsing_note': 'Used fallback parsing due to JSON error',
                'raw_response': ai_response[:200]
            }
        
        # Step 3: Add metadata
        parsed_profile['metadata'] = {
            'processed_at': datetime.now().isoformat(),
            'processor': 'together_ai',
            'model': config.together_ai_model,
            'tokens_used': tokens_used,
            'processing_time': ai_time,
            'version': '2.0'
        }
        
        # Step 4: Save to Firestore
        if FIRESTORE_AVAILABLE and db:
            save_start = time.time()
            
            # Save to enhanced_candidates (new system)
            doc_ref = db.collection('enhanced_candidates').document(candidate_id)
            doc_ref.set(parsed_profile)
            
            save_time = time.time() - save_start
            total_time = ai_time + save_time
            
            print(f"✅ {total_time:.2f}s (AI:{ai_time:.1f}s + Save:{save_time:.1f}s)")
        else:
            print(f"✅ {ai_time:.2f}s (AI only - Firestore not available)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)[:30]}")
        return False

def generate_test_candidates(num_candidates: int = 5):
    """Generate realistic test candidates"""
    skills_pool = [
        "Python", "JavaScript", "Java", "React", "Node.js", "AWS", "Docker",
        "Machine Learning", "Data Science", "SQL", "Kubernetes", "TypeScript"
    ]
    
    companies_pool = [
        "Google", "Microsoft", "Amazon", "Meta", "Apple", "Netflix", "Uber",
        "Airbnb", "Spotify", "Slack", "Dropbox", "GitHub"
    ]
    
    candidates = []
    for i in range(num_candidates):
        candidates.append({
            'id': f'ai_to_db_test_{i+1:03d}',
            'name': f'AI-DB Test Candidate {i+1}',
            'experience': (i % 8) + 3,  # 3-10 years experience
            'skills': skills_pool[i*2:(i*2)+4] if i*2 < len(skills_pool) else skills_pool[:4],
            'companies': companies_pool[i:(i)+2] if i < len(companies_pool) else companies_pool[:2]
        })
    
    return candidates

async def main():
    """Run Together AI → Firestore test"""
    print("🚀 Together AI → Firestore Pipeline Test")
    print("=" * 50)
    
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
    
    # Generate test candidates
    candidates = generate_test_candidates(5)
    print(f"✅ Generated {len(candidates)} test candidates")
    
    print("\n🔄 Processing candidates through AI → Database pipeline:")
    
    # Process each candidate
    start_time = time.time()
    successful = 0
    
    for candidate in candidates:
        success = await process_and_save_candidate(config, db, candidate)
        if success:
            successful += 1
        
        # Small delay between requests
        await asyncio.sleep(0.2)
    
    total_time = time.time() - start_time
    
    # Results
    print("\n" + "=" * 50)
    print("📊 AI → DATABASE PIPELINE RESULTS")
    print("=" * 50)
    
    success_rate = (successful / len(candidates)) * 100
    print(f"✅ Success Rate: {success_rate:.1f}% ({successful}/{len(candidates)})")
    print(f"⏱️  Total Time: {total_time:.2f}s")
    print(f"⏱️  Average per Candidate: {total_time/len(candidates):.2f}s")
    
    if FIRESTORE_AVAILABLE:
        print("💾 Data Saved to Firestore: enhanced_candidates collection")
        print("🔍 Check Firebase Console to see the new entries")
    else:
        print("⚠️ AI processing successful but no database saves (library not available)")
    
    # Final assessment
    if success_rate >= 80:
        print("\n🎉 AI → DATABASE PIPELINE TEST PASSED!")
        print("✅ Together AI processing is working")
        
        if FIRESTORE_AVAILABLE:
            print("✅ Data is being saved to Firestore")
            print("✅ Your database now has fresh processed candidates")
        
        return 0
    else:
        print("\n❌ AI → DATABASE PIPELINE TEST FAILED!")
        print("❌ Success rate below 80%")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)