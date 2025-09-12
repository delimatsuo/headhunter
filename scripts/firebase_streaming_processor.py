#!/usr/bin/env python3
"""
Firebase Streaming Processor with Together AI
Processes 29,000 candidates and streams directly to Firestore
Uses Firebase Admin SDK for authentication
"""

import json
import os
import time
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    # Try to use default credentials first (if running in GCP)
    try:
        firebase_admin.initialize_app()
        logger.info("✅ Initialized Firebase with default credentials")
    except:
        # Fall back to service account or application default credentials
        try:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {
                'projectId': 'headhunter-ai-0088',
            })
            logger.info("✅ Initialized Firebase with application default credentials")
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize Firebase: {e}")
            logger.info("Running without Firebase - will save locally")

@dataclass
class ProcessingStats:
    total_candidates: int = 0
    processed: int = 0
    uploaded: int = 0
    failed: int = 0
    start_time: Optional[datetime] = None
    estimated_cost: float = 0.0
    
class FirebaseStreamingProcessor:
    """Processes candidates via Together AI and streams to Firestore"""
    
    def __init__(self, api_key: str = None):
        # Get API key from env or parameter (no hardcoded fallback)
        self.api_key = api_key or os.getenv('TOGETHER_API_KEY')
        if not self.api_key:
            raise ValueError("Together API key not provided")

        # Configurable Stage 1 model (default to Qwen2.5 32B Instruct)
        self.model = os.getenv('TOGETHER_MODEL_STAGE1', 'Qwen2.5-32B-Instruct')
        self.base_url = "https://api.together.xyz/v1/chat/completions"
        self.session = None
        
        # Initialize Firestore
        try:
            self.db = firestore.client()
            self.use_firestore = True
            logger.info("✅ Connected to Firestore database")
        except Exception as e:
            logger.warning(f"⚠️ Firestore not available: {e}")
            self.db = None
            self.use_firestore = False
        
        # Cost tracking
        self.cost_per_token = 0.10 / 1_000_000
        self.stats = ProcessingStats()
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=120),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def create_analysis_prompt(self, candidate_data: Dict[str, Any]) -> str:
        """Create comprehensive analysis prompt"""
        
        name = candidate_data.get('name', 'Unknown')
        experience = candidate_data.get('experience', '')
        education = candidate_data.get('education', '')
        comments = candidate_data.get('comments', [])
        
        comment_text = ""
        if comments:
            comment_text = "\n".join([f"- {comment.get('text', '')}" for comment in comments])
        
        prompt = f"""
As an expert executive recruiter, analyze this candidate and return ONLY a valid JSON object:

{{
  "personal_details": {{
    "name": "{name}",
    "seniority_level": "Entry/Mid/Senior/Executive",
    "years_of_experience": "number",
    "location": "city, state/country"
  }},
  "education_analysis": {{
    "degrees": ["list of degrees"],
    "quality_score": "1-10",
    "relevance": "Low/Medium/High"
  }},
  "experience_analysis": {{
    "companies": ["company names"],
    "current_role": "title",
    "career_progression": "description",
    "industry_focus": "industry"
  }},
  "technical_assessment": {{
    "primary_skills": ["top 5 skills"],
    "expertise_level": "Beginner/Intermediate/Advanced/Expert"
  }},
  "market_insights": {{
    "estimated_salary_range": "$XXX,XXX - $XXX,XXX",
    "market_demand": "Low/Medium/High",
    "placement_difficulty": "Easy/Medium/Hard"
  }},
  "recruiter_recommendations": {{
    "ideal_roles": ["3-5 roles"],
    "target_companies": ["company types"],
    "strengths": ["key strengths"],
    "red_flags": ["concerns if any"]
  }},
  "executive_summary": {{
    "one_line_pitch": "one sentence summary",
    "overall_rating": "A/B/C/D",
    "recommendation": "Highly Recommended/Recommended/Consider/Pass"
  }}
}}

CANDIDATE DATA:
Name: {name}
Experience: {experience[:2000] if experience else "No data"}
Education: {education[:1000] if education else "No data"}
Comments: {comment_text[:1000] if comment_text else "No comments"}

Return ONLY the JSON object, no other text."""
        
        return prompt
    
    async def process_candidate(self, candidate_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process single candidate through Together AI"""
        
        candidate_id = candidate_data.get('id', 'unknown')
        
        try:
            prompt = self.create_analysis_prompt(candidate_data)
            
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000,
                "temperature": 0.1,
                "top_p": 0.9
            }
            
            async with self.session.post(self.base_url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if 'choices' in result and len(result['choices']) > 0:
                        content = result['choices'][0]['message']['content']
                        
                        try:
                            # Clean and parse JSON
                            content = content.strip()
                            if content.startswith("```json"):
                                content = content[7:]
                            if content.endswith("```"):
                                content = content[:-3]
                            
                            analysis = json.loads(content)
                            
                            # Create enhanced document
                            enhanced_data = {
                                "candidate_id": candidate_id,
                                "name": candidate_data.get('name', 'Unknown'),
                                "original_data": {
                                    "education": candidate_data.get('education', ''),
                                    "experience": candidate_data.get('experience', ''),
                                    "comments": candidate_data.get('comments', [])
                                },
                                "ai_analysis": analysis,
                                "processing_metadata": {
                                    "timestamp": firestore.SERVER_TIMESTAMP,
                                    "processor": "firebase_streaming",
                                    "model": self.model,
                                    "version": "2.0"
                                },
                                # Flattened fields for querying
                                "seniority_level": analysis.get("personal_details", {}).get("seniority_level", "Unknown"),
                                "years_experience": analysis.get("personal_details", {}).get("years_of_experience", 0),
                                "current_role": analysis.get("experience_analysis", {}).get("current_role", "Unknown"),
                                "overall_rating": analysis.get("executive_summary", {}).get("overall_rating", "D"),
                                "recommendation": analysis.get("executive_summary", {}).get("recommendation", "Pass"),
                                "primary_skills": analysis.get("technical_assessment", {}).get("primary_skills", []),
                                "search_keywords": " ".join([
                                    candidate_data.get('name', ''),
                                    analysis.get("experience_analysis", {}).get("current_role", ""),
                                    " ".join(analysis.get("technical_assessment", {}).get("primary_skills", [])),
                                    " ".join(analysis.get("experience_analysis", {}).get("companies", []))
                                ]).lower()
                            }
                            
                            return enhanced_data
                            
                        except json.JSONDecodeError:
                            self.stats.failed += 1
                            return None
                    
                else:
                    self.stats.failed += 1
                    return None
                    
        except Exception as e:
            logger.error(f"Error processing {candidate_id}: {e}")
            self.stats.failed += 1
            return None
    
    async def upload_batch_to_firestore(self, candidates: List[Dict[str, Any]]) -> int:
        """Upload batch directly to Firestore"""
        
        if not self.db or not candidates:
            return 0
            
        uploaded = 0
        
        try:
            batch = self.db.batch()
            
            for candidate in candidates:
                candidate_id = candidate.get('candidate_id', f"unknown_{uploaded}")
                doc_ref = self.db.collection('candidates').document(candidate_id)
                batch.set(doc_ref, candidate, merge=True)
                uploaded += 1
            
            batch.commit()
            self.stats.uploaded += uploaded
            
            logger.info(f"📤 Uploaded {uploaded} candidates to Firestore (Total: {self.stats.uploaded})")
            return uploaded
            
        except Exception as e:
            logger.error(f"Firestore upload error: {e}")
            return 0
    
    def save_batch_locally(self, candidates: List[Dict[str, Any]], batch_num: int):
        """Save batch to local file as backup"""
        output_dir = "/Users/delimatsuo/Documents/Coding/headhunter/data/processed_batches"
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{output_dir}/batch_{batch_num:04d}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(candidates, f, indent=2, default=str)
        
        logger.info(f"💾 Saved batch {batch_num} locally to {filename}")
    
    async def process_batch_streaming(self, candidates: List[Dict[str, Any]], 
                                    batch_size: int = 20) -> None:
        """Process candidates and stream to Firestore or save locally"""
        
        self.stats.total_candidates = len(candidates)
        self.stats.start_time = datetime.now()
        
        logger.info(f"🚀 Starting processing for {self.stats.total_candidates} candidates")
        
        if self.use_firestore:
            logger.info("📊 Results will stream to Firestore and appear in dashboard immediately")
        else:
            logger.info("💾 Firestore not available - will save batches locally")
        
        for i in range(0, self.stats.total_candidates, batch_size):
            batch = candidates[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (self.stats.total_candidates + batch_size - 1) // batch_size
            
            # Process batch
            tasks = [self.process_candidate(candidate) for candidate in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter successful results
            successful_results = [
                result for result in batch_results 
                if result is not None and not isinstance(result, Exception)
            ]
            
            self.stats.processed += len(successful_results)
            
            # Upload to Firestore or save locally
            if successful_results:
                if self.use_firestore:
                    await self.upload_batch_to_firestore(successful_results)
                else:
                    self.save_batch_locally(successful_results, batch_num)
            
            # Progress update
            elapsed = (datetime.now() - self.stats.start_time).total_seconds()
            rate = self.stats.processed / elapsed if elapsed > 0 else 0
            eta_seconds = (self.stats.total_candidates - self.stats.processed) / rate if rate > 0 else 0
            
            logger.info(f"""
📈 Batch {batch_num}/{total_batches} Complete:
   ✅ Processed: {self.stats.processed}/{self.stats.total_candidates}
   📤 Uploaded: {self.stats.uploaded if self.use_firestore else 'N/A (saving locally)'}
   ❌ Failed: {self.stats.failed}
   ⚡ Rate: {rate:.1f} candidates/sec
   ⏱️ ETA: {eta_seconds/60:.1f} minutes
            """)
            
            # Small delay between batches
            if i + batch_size < self.stats.total_candidates:
                await asyncio.sleep(1.0)
        
        # Final summary
        total_time = (datetime.now() - self.stats.start_time).total_seconds()
        
        logger.info(f"""
🎯 PROCESSING COMPLETE:
   ✅ Successfully processed: {self.stats.processed}/{self.stats.total_candidates}
   {'📤 Uploaded to Firestore: ' + str(self.stats.uploaded) if self.use_firestore else '💾 Saved locally in batches'}
   ❌ Failed: {self.stats.failed}
   ⏱️ Total time: {total_time/60:.1f} minutes
   💰 Estimated cost: ${self.stats.processed * 5000 * self.cost_per_token:.2f}
   
   {'🔍 View results at: https://headhunter-ai-0088.web.app/dashboard' if self.use_firestore else '📁 Results saved in: /Users/delimatsuo/Documents/Coding/headhunter/data/processed_batches/'}
        """)

async def main():
    """Main execution"""
    
    # Configuration
    INPUT_FILE = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
    
    # Load candidates
    logger.info("📂 Loading candidates...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        candidates = json.load(f)
    
    logger.info(f"✅ Loaded {len(candidates)} candidates")
    
    # Process with streaming
    async with FirebaseStreamingProcessor() as processor:
        # Test with smaller batch first
        # candidates = candidates[:100]  # Uncomment to test with 100
        
        # Process all candidates
        await processor.process_batch_streaming(candidates, batch_size=20)

if __name__ == "__main__":
    asyncio.run(main())
