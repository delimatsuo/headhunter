#!/usr/bin/env python3
"""
Direct Firebase upload - Create and upload 3 sample enhanced profiles immediately
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import firebase_admin
from firebase_admin import credentials, firestore
import asyncio
import httpx

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DirectTogetherAI:
    def __init__(self):
        # Together AI API setup
        self.api_key = "59b3c0c17b73b5b42d0b1a6a3d5c2e8d5fb5e8e5b5c5b5c5b5c5b5c5b5c5b5c5"  # Your API key
        self.base_url = "https://api.together.xyz"
        self.model = "meta-llama/Llama-3.2-3B-Instruct-Turbo"
        
        # Initialize Firebase
        try:
            firebase_admin.get_app()
        except ValueError:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
        
        self.db = firestore.client()
        logger.info("✅ Initialized Firebase and Together AI")

    async def process_candidate_direct(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Process candidate with direct API call"""
        
        name = candidate.get('name', 'Unknown')
        experience = candidate.get('experience', '')
        education = candidate.get('education', '')
        comments = candidate.get('comments', [])
        
        # Build prompt with interview comments
        comment_text = ""
        if comments:
            comment_text = "INTERVIEW COMMENTS AND RECRUITER FEEDBACK:\n"
            for comment in comments[:5]:  # Include up to 5 comments
                date = comment.get('date', '')
                author = comment.get('author', '')
                text = comment.get('text', '')
                if text:
                    comment_text += f"[{date}] {author}: {text}\n"
            comment_text += "\n"
        
        prompt = f"""You are a senior executive recruiter with 20+ years of experience placing candidates at Fortune 500 and top-tier tech companies.

CANDIDATE: {name}

EXPERIENCE:
{experience}

EDUCATION:
{education}

{comment_text}

Analyze this candidate and provide a comprehensive assessment. Return ONLY valid JSON with this structure:

{{
  "executive_summary": {{
    "overall_rating": [0-100 integer],
    "one_line_pitch": "[compelling summary in 15-20 words]",
    "key_strengths": ["strength1", "strength2", "strength3"],
    "concerns": ["concern1", "concern2"] 
  }},
  "career_trajectory": {{
    "current_level": "[junior/mid/senior/staff/principal/vp/c-level]",
    "trajectory_type": "[fast_growth/steady_progression/lateral_moves/career_change]",
    "progression_speed": "[fast/moderate/slow]"
  }},
  "recruiter_insights": {{
    "placement_likelihood": "[very_high/high/moderate/low/very_low]",
    "best_fit_roles": ["role1", "role2"],
    "concerns": ["concern1", "concern2"],
    "recruiter_notes": "[synthesis of interview feedback and assessment]"
  }},
  "cultural_signals": {{
    "strengths": ["teamwork", "leadership", "innovation"],
    "growth_areas": ["area1", "area2"],
    "work_style": "[collaborative/independent/hybrid]",
    "communication_style": "[direct/diplomatic/technical]"
  }}
}}

CRITICAL: Return ONLY the JSON object. No markdown, no explanations, no extra text."""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 2000,
                        "temperature": 0.1
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"].strip()
                    
                    # Parse JSON response
                    try:
                        analysis = json.loads(content)
                        
                        # Create full profile
                        enhanced_profile = {
                            "candidate_id": str(candidate.get('id', candidate.get('candidate_id', 'unknown'))),
                            "name": name,
                            "original_data": {
                                "experience": experience[:500] if experience else "",
                                "education": education[:500] if education else "",
                                "comments_count": len(comments)
                            },
                            "enhanced_analysis": analysis,
                            "processor_info": {
                                "processor": "direct_together_ai",
                                "model": self.model,
                                "timestamp": datetime.now().isoformat()
                            },
                            "timestamp": datetime.now().isoformat(),
                            "test_batch": "direct_firebase_upload"
                        }
                        
                        return enhanced_profile
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON parsing failed for {name}: {e}")
                        logger.error(f"Raw response: {content[:200]}...")
                        return None
                        
                else:
                    logger.error(f"API error for {name}: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"Processing failed for {name}: {e}")
            return None

async def main():
    """Generate and upload 3 enhanced profiles directly"""
    
    print("🎯 DIRECT FIREBASE UPLOAD TEST")
    print("=" * 50)
    print("✅ Processing 3 candidates with interview comments")
    print("✅ Uploading directly to Firebase")
    print("=" * 50)
    
    # Initialize processor
    processor = DirectTogetherAI()
    
    # Load candidates
    merged_file = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json")
    
    if not merged_file.exists():
        print("❌ Merged candidates file not found")
        return
    
    with open(merged_file, 'r') as f:
        all_candidates = json.load(f)
    
    # Select 3 candidates with good data
    selected = []
    for candidate in all_candidates:
        if len(candidate.get('experience', '')) > 200 and len(candidate.get('comments', [])) >= 2:
            selected.append(candidate)
            if len(selected) >= 3:
                break
    
    if not selected:
        print("❌ No suitable candidates found")
        return
    
    print("📋 PROCESSING CANDIDATES:")
    print("-" * 30)
    
    successful_uploads = 0
    
    for i, candidate in enumerate(selected, 1):
        name = candidate.get('name', 'N/A')
        print(f"📍 [{i}/3] Processing: {name}")
        
        # Process with Together AI
        enhanced_profile = await processor.process_candidate_direct(candidate)
        
        if enhanced_profile:
            # Upload to Firebase
            try:
                candidate_id = enhanced_profile['candidate_id']
                doc_ref = processor.db.collection('enhanced_candidates').document(candidate_id)
                doc_ref.set(enhanced_profile)
                
                # Show preview
                analysis = enhanced_profile['enhanced_analysis']
                rating = analysis.get('executive_summary', {}).get('overall_rating', 'N/A')
                pitch = analysis.get('executive_summary', {}).get('one_line_pitch', 'N/A')
                
                print(f"   ✅ UPLOADED - Rating: {rating}/100")
                print(f"   📝 Pitch: {pitch}")
                successful_uploads += 1
                
            except Exception as e:
                print(f"   ❌ UPLOAD FAILED: {e}")
        else:
            print("   ❌ PROCESSING FAILED")
        
        print()
    
    if successful_uploads > 0:
        print("🎉 SUCCESS!")
        print("=" * 50)
        print(f"✅ {successful_uploads}/3 profiles uploaded to Firebase")
        print()
        print("🔍 VIEW IN FIREBASE CONSOLE:")
        print("   https://console.firebase.google.com/project/headhunter-ai-0088")
        print("   Collection: enhanced_candidates")
        print("   Filter: test_batch = 'direct_firebase_upload'")
        print()
        print("📊 QUALITY REVIEW POINTS:")
        print("   ✓ Overall rating (0-100 scale)")
        print("   ✓ Recruiter insights from interview comments")
        print("   ✓ Cultural signals analysis")
        print("   ✓ Career trajectory assessment")
    else:
        print("❌ No profiles uploaded successfully")

if __name__ == "__main__":
    asyncio.run(main())