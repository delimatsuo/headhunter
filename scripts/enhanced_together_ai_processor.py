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
        self.api_key = api_key or os.getenv('TOGETHER_API_KEY', '6d9eb8b102a05bae51baa97445cff83aff1eaf38ee7c09528bee54efe4ca4824')
        if not self.api_key:
            raise ValueError("Together API key not provided")
            
        self.model = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
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
        """Create sophisticated recruiter-level analysis prompt"""
        
        name = candidate_data.get('name', 'Unknown')
        experience = candidate_data.get('experience', '')
        education = candidate_data.get('education', '')
        comments = candidate_data.get('comments', [])
        
        comment_text = ""
        if comments:
            comment_text = "\n".join([f"- {comment.get('text', '')}" for comment in comments])
        
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
Experience: {experience[:3000] if experience else "No experience data"}
Education: {education[:1500] if education else "No education data"}
Recruiter Comments: {comment_text[:1500] if comment_text else "No comments"}

Provide ONLY a JSON response with this EXACT structure:

{{
  "career_trajectory_analysis": {{
    "current_level": "entry/mid/senior/lead/principal/director/vp/c-level",
    "years_to_current_level": <number>,
    "promotion_velocity": {{
      "speed": "slow/average/fast/exceptional",
      "average_time_between_promotions": "<X years>",
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
    "best_company_worked": "Company name",
    "company_trajectory": [
      {{"company": "Name", "tier": "tier", "years": X, "role_level": "level"}}
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
    "has_leadership": true/false,
    "leadership_growth_pattern": "expanding/stable/contracting/none",
    "max_team_size_managed": <number>,
    "current_scope": "IC/team-lead/manager/senior-manager/director/executive",
    "leadership_trajectory": "high-potential/steady-growth/plateaued/unclear",
    "p&l_responsibility": true/false,
    "cross_functional_leadership": true/false
  }},
  
  "domain_expertise_assessment": {{
    "primary_domain": "Main area of expertise",
    "expertise_depth": "specialist/expert/generalist/beginner",
    "years_in_domain": <number>,
    "technical_skills_trajectory": "expanding/deepening/stagnant/declining",
    "skill_relevance": "cutting-edge/current/dated/obsolete",
    "market_demand_for_skills": "very-high/high/moderate/low"
  }},
  
  "red_flags_and_risks": {{
    "job_stability": "very-stable/stable/moderate/unstable",
    "average_tenure": "<X years>",
    "concerning_patterns": ["Any red flags observed"],
    "career_risks": ["Potential risks for recruiters"],
    "explanation_needed": ["Things that need clarification in interview"]
  }},
  
  "cultural_indicators": {{
    "work_environment_preference": "startup/scaleup/enterprise/flexible",
    "leadership_style": "collaborative/directive/coaching/hands-off",
    "cultural_values": ["innovation", "stability", "growth", etc],
    "team_fit": "team-player/independent/both"
  }},
  
  "market_assessment": {{
    "salary_positioning": "$XXX,XXX - $XXX,XXX",
    "market_competitiveness": "highly-competitive/competitive/average/below-market",
    "placement_difficulty": "easy/moderate/challenging/very-difficult",
    "ideal_next_role": "Specific role recommendation",
    "career_ceiling": "Current level / potential highest level",
    "years_to_next_level": <number>
  }},
  
  "recruiter_verdict": {{
    "overall_rating": "A+/A/B+/B/C+/C/D",
    "recommendation": "highly-recommend/recommend/consider/pass",
    "one_line_pitch": "Compelling one-sentence summary for clients",
    "key_selling_points": ["Top 3 reasons to hire"],
    "interview_focus_areas": ["Key areas to probe in interview"],
    "best_fit_companies": ["Types of companies or specific names"],
    "retention_risk": "low/medium/high",
    "counteroffer_risk": "low/medium/high"
  }}
}}

Think like a recruiter: faster promotions = better performance, company quality matters, leadership scope growth indicates trust.
"""
        
        return prompt
    
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