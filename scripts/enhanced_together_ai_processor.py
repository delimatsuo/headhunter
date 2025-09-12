#!/usr/bin/env python3
"""
Enhanced Together AI Processor with Deep Recruiter Analysis
Uses sophisticated prompts to analyze career velocity, promotion patterns, and performance indicators
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
    try:
        firebase_admin.initialize_app()
        logger.info("✅ Initialized Firebase with default credentials")
    except:
        try:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {'projectId': 'headhunter-ai-0088'})
            logger.info("✅ Initialized Firebase with application default credentials")
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize Firebase: {e}")

@dataclass
class ProcessingStats:
    total_candidates: int = 0
    processed: int = 0
    uploaded: int = 0
    failed: int = 0
    start_time: Optional[datetime] = None
    estimated_cost: float = 0.0
    
class EnhancedTogetherAIProcessor:
    """Processes candidates with deep recruiter-level analysis"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('TOGETHER_API_KEY')
        if not self.api_key:
            raise ValueError("Together API key not provided")
            
        self.model = os.getenv('TOGETHER_MODEL_STAGE1', 'Qwen/Qwen2.5-32B-Instruct')
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
    
    def create_deep_analysis_prompt(self, candidate_data: Dict[str, Any]) -> str:
        """Create expert-engineered analysis prompt with interview comment integration"""
        
        # Build comprehensive prompt with interview comments
        name = candidate_data.get('name', 'Unknown')
        experience = candidate_data.get('experience', '')
        education = candidate_data.get('education', '')
        comments = candidate_data.get('comments', [])
        
        # Build interview comments section
        comment_analysis = ""
        if comments:
            comment_analysis = "INTERVIEW COMMENTS AND RECRUITER FEEDBACK:\n"
            for comment in comments[:10]:  # Include up to 10 comments
                date = comment.get('date', '')
                author = comment.get('author', '')
                text = comment.get('text', '')
                if text:
                    comment_analysis += f"[{date}] {author}: {text}\n"
            comment_analysis += "\n"
        
        return f"""You are a senior executive recruiter with 20+ years of experience placing candidates at Fortune 500 and top-tier tech companies.

CANDIDATE: {name}

EXPERIENCE:
{experience}

EDUCATION:
{education}

{comment_analysis}

Analyze this candidate comprehensively, incorporating ALL available data including interview feedback. Return ONLY valid JSON with this exact structure:

{{
  "executive_summary": {{
    "overall_rating": [integer 0-100],
    "one_line_pitch": "[compelling summary in 15-20 words]",
    "key_strengths": ["strength1", "strength2", "strength3"],
    "concerns": ["concern1", "concern2"]
  }},
  "career_trajectory": {{
    "current_level": "[junior/mid/senior/staff/principal/vp/c-level]",
    "trajectory_type": "[fast_growth/steady_progression/lateral_moves/career_change]",
    "progression_speed": "[fast/moderate/slow]",
    "years_experience": [integer]
  }},
  "skill_assessment": {{
    "explicit_skills": {{
      "technical_skills": ["skill1", "skill2", "skill3"],
      "soft_skills": ["leadership", "communication"],
      "tools_technologies": ["tool1", "tool2"],
      "certifications": ["cert1", "cert2"],
      "confidence": "100%"
    }},
    "inferred_skills": {{
      "highly_probable_skills": [
        {{"skill": "system design", "confidence": 95, "reasoning": "Senior engineer typically requires this"}},
        {{"skill": "mentoring", "confidence": 90, "reasoning": "Leadership role indicates this skill"}}
      ],
      "probable_skills": [
        {{"skill": "agile", "confidence": 85, "reasoning": "Common for this role level"}},
        {{"skill": "code review", "confidence": 80, "reasoning": "Standard practice at this level"}}
      ],
      "likely_skills": [
        {{"skill": "JIRA", "confidence": 75, "reasoning": "Often associated with this domain"}},
        {{"skill": "architecture", "confidence": 70, "reasoning": "Senior role requirement"}}
      ],
      "possible_skills": [
        {{"skill": "Python", "confidence": 60, "reasoning": "May have based on background"}},
        {{"skill": "cloud platforms", "confidence": 55, "reasoning": "Modern tech role assumption"}}
      ]
    }},
    "composite_skill_profile": {{
      "domain_specialization": "[primary domain like 'Backend Engineering', 'Data Science']",
      "skill_breadth": "[specialist/generalist/hybrid]",
      "primary_expertise": ["core skill 1", "core skill 2"],
      "secondary_expertise": ["supporting skill 1", "supporting skill 2"],
      "unique_combination": ["unique skill combo description"]
    }},
    "market_positioning": {{
      "skill_rarity": "[common/uncommon/rare/very_rare]",
      "skill_market_value": "[low/medium/high/very_high]",
      "competitive_advantage": ["advantage 1", "advantage 2"],
      "salary_range": "$X - $Y based on skill profile"
    }}
  }},
  "recruiter_insights": {{
    "placement_likelihood": "[very_high/high/moderate/low/very_low]",
    "best_fit_roles": ["role1", "role2"],
    "concerns": ["concern1", "concern2"],
    "recruiter_notes": "[synthesis of interview feedback and assessment]",
    "selling_points": ["unique strength 1", "unique strength 2"],
    "verification_needed": ["skill to verify", "experience to confirm"]
  }},
  "cultural_signals": {{
    "strengths": ["teamwork", "leadership", "innovation"],
    "growth_areas": ["area1", "area2"],
    "work_style": "[collaborative/independent/hybrid]",
    "communication_style": "[direct/diplomatic/technical]"
  }},
  "leadership_scope": {{
    "has_leadership": [true/false],
    "team_size": [integer or null],
    "leadership_level": "[individual_contributor/team_lead/manager/director/vp]"
  }}
}}

CRITICAL REQUIREMENTS:
- Return ONLY the JSON object
- No markdown formatting, no explanations, no extra text
- For missing information, use "information unavailable" - NEVER invent data
- Base skill inferences on actual experience, roles, and companies
- Include confidence scores (0-100) for all inferred skills with reasoning
- Base recruiter_notes on actual interview comments when available
- Ensure skill_assessment includes both explicit (clearly stated) and inferred (probable) skills
- Make salary estimates realistic based on skills and experience level"""
    
    async def process_candidate(self, candidate_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process single candidate with deep analysis"""
        
        candidate_id = candidate_data.get('id', 'unknown')
        
        try:
            prompt = self.create_deep_analysis_prompt(candidate_data)
            
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4000,
                "temperature": 0.2,  # Lower temperature for more consistent analysis
                "top_p": 0.95
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
                            
                            # Create enhanced document with deep analysis
                            enhanced_data = {
                                "candidate_id": candidate_id,
                                "name": candidate_data.get('name', 'Unknown'),
                                "original_data": {
                                    "education": candidate_data.get('education', ''),
                                    "experience": candidate_data.get('experience', ''),
                                    "comments": candidate_data.get('comments', [])
                                },
                                "enhanced_analysis": analysis,  # Deep recruiter analysis
                                "processing_metadata": {
                                    "timestamp": firestore.SERVER_TIMESTAMP,
                                    "processor": "enhanced_together_ai",
                                    "model": self.model,
                                    "version": "3.0",
                                    "analysis_depth": "deep"
                                },
                                # Flattened fields for querying
                                "current_level": analysis.get("career_trajectory_analysis", {}).get("current_level", "Unknown"),
                                "promotion_velocity": analysis.get("career_trajectory_analysis", {}).get("promotion_velocity", {}).get("speed", "unknown"),
                                "performance_tier": analysis.get("performance_indicators", {}).get("estimated_performance_tier", "average"),
                                "overall_rating": analysis.get("recruiter_verdict", {}).get("overall_rating", "C"),
                                "recommendation": analysis.get("recruiter_verdict", {}).get("recommendation", "consider"),
                                "salary_range": analysis.get("market_assessment", {}).get("salary_positioning", "Unknown"),
                                "placement_difficulty": analysis.get("market_assessment", {}).get("placement_difficulty", "moderate"),
                                "search_keywords": " ".join([
                                    candidate_data.get('name', ''),
                                    analysis.get("career_trajectory_analysis", {}).get("current_level", ""),
                                    analysis.get("company_pedigree_analysis", {}).get("best_company_worked", ""),
                                    analysis.get("domain_expertise_assessment", {}).get("primary_domain", "")
                                ]).lower()
                            }
                            
                            return enhanced_data
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON parse error for {candidate_id}: {e}")
                            logger.debug(f"Raw content: {content[:500]}")
                            self.stats.failed += 1
                            return None
                    
                else:
                    logger.error(f"API error for {candidate_id}: Status {response.status}")
                    self.stats.failed += 1
                    return None
                    
        except Exception as e:
            logger.error(f"Error processing {candidate_id}: {e}")
            self.stats.failed += 1
            return None
    
    async def upload_batch_to_firestore(self, candidates: List[Dict[str, Any]]) -> int:
        """Upload batch to Firestore"""
        
        if not self.db or not candidates:
            return 0
            
        uploaded = 0
        
        try:
            batch = self.db.batch()
            
            for candidate in candidates:
                candidate_id = candidate.get('candidate_id', f"unknown_{uploaded}")
                # Use enhanced_candidates collection for deep analysis
                doc_ref = self.db.collection('enhanced_candidates').document(candidate_id)
                batch.set(doc_ref, candidate, merge=True)
                uploaded += 1
            
            batch.commit()
            self.stats.uploaded += uploaded
            
            logger.info(f"📤 Uploaded {uploaded} deeply analyzed candidates (Total: {self.stats.uploaded})")
            return uploaded
            
        except Exception as e:
            logger.error(f"Firestore upload error: {e}")
            return 0
    
    async def process_batch_streaming(self, candidates: List[Dict[str, Any]], 
                                    batch_size: int = 10) -> None:
        """Process candidates with deep analysis and stream to Firestore"""
        
        self.stats.total_candidates = len(candidates)
        self.stats.start_time = datetime.now()
        
        logger.info(f"🚀 Starting DEEP ANALYSIS for {self.stats.total_candidates} candidates")
        logger.info("🧠 Using sophisticated recruiter-level prompts for career velocity and performance analysis")
        
        for i in range(0, self.stats.total_candidates, batch_size):
            batch = candidates[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (self.stats.total_candidates + batch_size - 1) // batch_size
            
            # Process batch with deep analysis
            tasks = [self.process_candidate(candidate) for candidate in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter successful results
            successful_results = [
                result for result in batch_results 
                if result is not None and not isinstance(result, Exception)
            ]
            
            self.stats.processed += len(successful_results)
            
            # Upload to Firestore
            if successful_results:
                await self.upload_batch_to_firestore(successful_results)
            
            # Progress update
            elapsed = (datetime.now() - self.stats.start_time).total_seconds()
            rate = self.stats.processed / elapsed if elapsed > 0 else 0
            eta_seconds = (self.stats.total_candidates - self.stats.processed) / rate if rate > 0 else 0
            
            logger.info(f"""
📊 Batch {batch_num}/{total_batches} Complete:
   ✅ Deep Analysis Complete: {self.stats.processed}/{self.stats.total_candidates}
   📤 Uploaded with Enhanced Analysis: {self.stats.uploaded}
   ❌ Failed: {self.stats.failed}
   ⚡ Rate: {rate:.1f} candidates/sec
   ⏱️ ETA: {eta_seconds/60:.1f} minutes
   🧠 Analysis includes: promotion velocity, performance tier, career trajectory
            """)
            
            # Small delay between batches
            if i + batch_size < self.stats.total_candidates:
                await asyncio.sleep(1.0)
        
        # Final summary
        total_time = (datetime.now() - self.stats.start_time).total_seconds()
        
        logger.info(f"""
🎯 DEEP ANALYSIS COMPLETE:
   ✅ Successfully analyzed: {self.stats.processed}/{self.stats.total_candidates}
   📤 Uploaded to enhanced_candidates: {self.stats.uploaded}
   ❌ Failed: {self.stats.failed}
   ⏱️ Total time: {total_time/60:.1f} minutes
   💰 Estimated cost: ${self.stats.processed * 5000 * self.cost_per_token:.2f}
   
   🧠 Analysis included:
      - Promotion velocity (performance proxy)
      - Company tier progression
      - Leadership scope evolution
      - Performance tier estimation
      - Market positioning
      - Red flags and risks
   
   🔍 View enhanced results at: https://headhunter-ai-0088.web.app/dashboard
        """)

async def main():
    """Main execution"""
    
    # Configuration
    INPUT_FILE = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
    
    # Load candidates
    logger.info("📂 Loading candidates for DEEP ANALYSIS...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        candidates = json.load(f)
    
    logger.info(f"✅ Loaded {len(candidates)} candidates")
    
    # Process with deep analysis
    async with EnhancedTogetherAIProcessor() as processor:
        # Test with smaller batch first
        candidates = candidates[:100]  # Test with 100 for quality check
        
        # Lower batch size for deeper analysis
        await processor.process_batch_streaming(candidates, batch_size=10)

if __name__ == "__main__":
    asyncio.run(main())
