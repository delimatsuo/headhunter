#!/usr/bin/env python3
"""
Intelligent Skill Inference Processor with Probabilistic Analysis
Infers likely skills based on roles, companies, and industry patterns
Separates explicit vs inferred competencies with confidence scores
"""

import json
import os
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
from scripts.json_repair import repair_json
from scripts.schemas import IntelligentAnalysis

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
    
class IntelligentSkillProcessor:
    """Processes candidates with intelligent skill inference and probabilistic analysis"""
    
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
    
    def create_intelligent_analysis_prompt(self, candidate_data: Dict[str, Any]) -> str:
        """Create prompt with probabilistic skill inference"""
        
        name = candidate_data.get('name', 'Unknown')
        experience = candidate_data.get('experience', '')
        education = candidate_data.get('education', '')
        comments = candidate_data.get('comments', [])
        
        comment_text = ""
        if comments:
            comment_text = "\n".join([f"- {comment.get('text', '')}" for comment in comments])
        
        prompt = f"""
You are an elite executive recruiter with deep knowledge of role requirements across industries. Analyze this candidate with sophisticated skill inference.

CRITICAL FRAMEWORK FOR SKILL INFERENCE:
1. EXPLICIT SKILLS: Only skills directly mentioned in the resume (100% confidence)
2. INFERRED SKILLS: Skills typically required for their roles (with probability)
3. CORE COMPETENCIES: Standard skills for each position type
4. COMPANY-SPECIFIC SKILLS: Skills typically required at specific companies

SKILL INFERENCE RULES:
- Principal Engineer at FAANG → 95% system design, distributed systems, mentoring, code review
- FP&A Analyst at Fortune 500 → 90% Excel modeling, SQL, budgeting, forecasting, Tableau
- Product Manager at Startup → 85% agile, user research, A/B testing, roadmapping
- Software Engineer at Enterprise → 80% JIRA, Confluence, enterprise patterns
- Data Scientist at Tech → 90% Python, ML frameworks, statistics, A/B testing

CANDIDATE DATA:
Name: {name}
Experience: {experience[:3000] if experience else "No experience data"}
Education: {education[:1500] if education else "No education data"}
Recruiter Comments: {comment_text[:1500] if comment_text else "No comments"}

Provide ONLY a JSON response with this EXACT structure:

{{
  "explicit_skills": {{
    "technical_skills": ["Skills directly mentioned in resume"],
    "tools_technologies": ["Tools explicitly stated"],
    "soft_skills": ["Soft skills explicitly mentioned"],
    "certifications": ["Certifications listed"],
    "confidence": "100%"
  }},
  
  "inferred_skills": {{
    "highly_probable_skills": [
      {{"skill": "skill name", "confidence": 95, "reasoning": "Principal Engineer at Google typically requires this"}}
    ],
    "probable_skills": [
      {{"skill": "skill name", "confidence": 85, "reasoning": "Common for this role level"}}
    ],
    "likely_skills": [
      {{"skill": "skill name", "confidence": 75, "reasoning": "Often associated with this domain"}}
    ],
    "possible_skills": [
      {{"skill": "skill name", "confidence": 60, "reasoning": "May have based on background"}}
    ]
  }},
  
  "role_based_competencies": {{
    "current_role_competencies": {{
      "role": "Current or most recent role",
      "core_competencies": ["Standard skills for this role"],
      "typical_tools": ["Common tools for this role"],
      "domain_knowledge": ["Domain expertise typically required"]
    }},
    "historical_competencies": [
      {{
        "role": "Previous role",
        "acquired_skills": ["Skills likely gained in this role"],
        "transferable_skills": ["Skills that transfer to other roles"]
      }}
    ]
  }},
  
  "company_context_skills": {{
    "company_specific": [
      {{
        "company": "Company name",
        "typical_stack": ["Tech stack typically used"],
        "methodologies": ["Common practices at this company"],
        "scale_experience": "startup/midmarket/enterprise/hyperscale"
      }}
    ],
    "industry_skills": ["Skills common in their industry"]
  }},
  
  "skill_evolution_analysis": {{
    "skill_trajectory": "expanding/specializing/pivoting/stagnant",
    "emerging_skills": ["New skills they're likely developing"],
    "skill_gaps": ["Skills they likely lack for next level"],
    "learning_velocity": "fast/moderate/slow",
    "skill_currency": "cutting-edge/current/aging/outdated"
  }},
  
  "composite_skill_profile": {{
    "primary_expertise": ["Top 5 most certain skills (explicit + high confidence inferred)"],
    "secondary_expertise": ["Next tier of skills"],
    "domain_specialization": "Area of deepest expertise",
    "skill_breadth": "specialist/t-shaped/generalist",
    "unique_combination": ["Rare skill combinations they possess"]
  }},
  
  "career_trajectory_analysis": {{
    "current_level": "entry/mid/senior/lead/principal/director/vp/c-level",
    "years_experience": <number>,
    "promotion_velocity": "slow/average/fast/exceptional",
    "career_progression": "linear/accelerated/lateral/varied",
    "performance_indicator": "below-average/average/above-average/top-performer"
  }},
  
  "market_positioning": {{
    "skill_market_value": "low/moderate/high/exceptional",
    "skill_rarity": "common/uncommon/rare/unique",
    "competitive_advantage": ["Skills that differentiate them"],
    "placement_difficulty": "easy/moderate/challenging/difficult",
    "ideal_next_roles": ["Roles that match their skill profile"],
    "salary_range": "$XXX,XXX - $XXX,XXX"
  }},
  
  "recruiter_insights": {{
    "overall_rating": "A+/A/B+/B/C+/C/D",
    "recommendation": "highly-recommend/recommend/consider/pass",
    "confidence_in_assessment": "high/medium/low",
    "verification_needed": ["Skills that need verification in interview"],
    "red_flags": ["Concerning patterns or gaps"],
    "selling_points": ["Top reasons to hire"],
    "interview_focus": ["Key areas to probe"],
    "one_line_pitch": "Compelling summary for clients"
  }}
}}

Remember: Separate what you KNOW (explicit) from what you INFER (probabilistic). Be precise about confidence levels.
"""
        
        return prompt
    
    async def process_candidate(self, candidate_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process single candidate with intelligent skill inference"""
        
        candidate_id = candidate_data.get('id', 'unknown')
        
        try:
            prompt = self.create_intelligent_analysis_prompt(candidate_data)
            
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4500,
                "temperature": 0.2,  # Lower temperature for consistent analysis
                "top_p": 0.95
            }
            
            async with self.session.post(self.base_url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if 'choices' in result and len(result['choices']) > 0:
                        content = result['choices'][0]['message']['content']
                        
                        try:
                            # Repair and parse JSON then validate against schema
                            repaired = repair_json(content)
                            analysis = IntelligentAnalysis.model_validate(repaired).model_dump()
                            
                            # Create enhanced document with intelligent analysis
                            enhanced_data = {
                                "candidate_id": candidate_id,
                                "name": candidate_data.get('name', 'Unknown'),
                                "original_data": {
                                    "education": candidate_data.get('education', ''),
                                    "experience": candidate_data.get('experience', ''),
                                    "comments": candidate_data.get('comments', [])
                                },
                                "intelligent_analysis": analysis,
                                "processing_metadata": {
                                    "timestamp": firestore.SERVER_TIMESTAMP,
                                    "processor": "intelligent_skill_processor",
                                    "model": self.model,
                                    "version": "4.0",
                                    "analysis_type": "probabilistic_skill_inference"
                                },
                                # Flattened fields for querying
                                "explicit_skills": analysis.get("explicit_skills", {}).get("technical_skills", []),
                                "inferred_skills_high_confidence": [
                                    s["skill"] for s in analysis.get("inferred_skills", {}).get("highly_probable_skills", [])
                                ],
                                "all_probable_skills": self._extract_all_probable_skills(analysis),
                                "current_level": analysis.get("career_trajectory_analysis", {}).get("current_level", "Unknown"),
                                "skill_market_value": analysis.get("market_positioning", {}).get("skill_market_value", "moderate"),
                                "overall_rating": analysis.get("recruiter_insights", {}).get("overall_rating", "C"),
                                "recommendation": analysis.get("recruiter_insights", {}).get("recommendation", "consider"),
                                "primary_expertise": analysis.get("composite_skill_profile", {}).get("primary_expertise", []),
                                "search_keywords": self._generate_search_keywords(candidate_data, analysis)
                            }
                            
                            return enhanced_data
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON parse error for {candidate_id}: {e}")
                            self.stats.failed += 1
                            return None
                    
                elif response.status == 429:
                    # Rate limit - wait and retry
                    logger.warning(f"Rate limited for {candidate_id}, waiting 10 seconds...")
                    await asyncio.sleep(10)
                    return await self.process_candidate(candidate_data)  # Retry
                    
                else:
                    logger.error(f"API error for {candidate_id}: Status {response.status}")
                    self.stats.failed += 1
                    return None
                    
        except Exception as e:
            logger.error(f"Error processing {candidate_id}: {e}")
            self.stats.failed += 1
            return None
    
    def _extract_all_probable_skills(self, analysis: Dict) -> List[str]:
        """Extract all skills with >75% confidence"""
        skills = []
        inferred = analysis.get("inferred_skills", {})
        
        for category in ["highly_probable_skills", "probable_skills"]:
            for skill_item in inferred.get(category, []):
                if skill_item.get("confidence", 0) >= 75:
                    skills.append(skill_item["skill"])
        
        return skills
    
    def _generate_search_keywords(self, candidate_data: Dict, analysis: Dict) -> str:
        """Generate comprehensive search keywords"""
        keywords = [
            candidate_data.get('name', ''),
            analysis.get("career_trajectory_analysis", {}).get("current_level", ""),
            analysis.get("composite_skill_profile", {}).get("domain_specialization", "")
        ]
        
        # Add explicit skills
        keywords.extend(analysis.get("explicit_skills", {}).get("technical_skills", [])[:5])
        
        # Add high confidence inferred skills
        for skill_item in analysis.get("inferred_skills", {}).get("highly_probable_skills", [])[:3]:
            keywords.append(skill_item.get("skill", ""))
        
        # Add company names
        for company in analysis.get("company_context_skills", {}).get("company_specific", [])[:2]:
            keywords.append(company.get("company", ""))
        
        return " ".join(filter(None, keywords)).lower()
    
    async def upload_batch_to_firestore(self, candidates: List[Dict[str, Any]]) -> int:
        """Upload batch to Firestore"""
        
        if not self.db or not candidates:
            return 0
            
        uploaded = 0
        
        try:
            batch = self.db.batch()
            
            for candidate in candidates:
                candidate_id = candidate.get('candidate_id', f"unknown_{uploaded}")
                # Use candidates collection (main collection)
                doc_ref = self.db.collection('candidates').document(candidate_id)
                batch.set(doc_ref, candidate, merge=True)
                uploaded += 1
            
            batch.commit()
            self.stats.uploaded += uploaded
            
            logger.info(f"📤 Uploaded {uploaded} intelligently analyzed candidates (Total: {self.stats.uploaded})")
            return uploaded
            
        except Exception as e:
            logger.error(f"Firestore upload error: {e}")
            return 0
    
    async def process_batch_streaming(self, candidates: List[Dict[str, Any]], 
                                    batch_size: int = 5) -> None:
        """Process candidates with intelligent analysis and stream to Firestore"""
        
        self.stats.total_candidates = len(candidates)
        self.stats.start_time = datetime.now()
        
        logger.info(f"🚀 Starting INTELLIGENT SKILL ANALYSIS for {self.stats.total_candidates} candidates")
        logger.info("🧠 Using probabilistic inference to identify likely skills based on roles and companies")
        logger.info("📊 Separating explicit skills (100% confidence) from inferred skills (with probability scores)")
        
        for i in range(0, self.stats.total_candidates, batch_size):
            batch = candidates[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (self.stats.total_candidates + batch_size - 1) // batch_size
            
            # Process batch with intelligent analysis
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
   ✅ Intelligent Analysis Complete: {self.stats.processed}/{self.stats.total_candidates}
   📤 Uploaded with Skill Inference: {self.stats.uploaded}
   ❌ Failed: {self.stats.failed}
   ⚡ Rate: {rate:.1f} candidates/sec
   ⏱️ ETA: {eta_seconds/60:.1f} minutes
   
   🧠 Analysis includes:
      - Explicit skills (100% confidence)
      - Inferred skills with probability scores
      - Role-based competencies
      - Company-specific typical skills
            """)
            
            # Rate limit handling
            if i + batch_size < self.stats.total_candidates:
                await asyncio.sleep(2.0)  # Slower pace to avoid rate limits
        
        # Final summary
        total_time = (datetime.now() - self.stats.start_time).total_seconds()
        
        logger.info(f"""
🎯 INTELLIGENT ANALYSIS COMPLETE:
   ✅ Successfully analyzed: {self.stats.processed}/{self.stats.total_candidates}
   📤 Uploaded to Firestore: {self.stats.uploaded}
   ❌ Failed: {self.stats.failed}
   ⏱️ Total time: {total_time/60:.1f} minutes
   💰 Estimated cost: ${self.stats.processed * 6000 * self.cost_per_token:.2f}
   
   🧠 Analysis included:
      - Explicit vs Inferred skill separation
      - Probabilistic skill confidence scores
      - Role-based competency mapping
      - Company-specific skill inference
      - Career trajectory analysis
      - Market positioning assessment
   
   🔍 View results at: https://headhunter-ai-0088.web.app/dashboard
        """)

async def main():
    """Main execution"""
    
    # Configuration
    INPUT_FILE = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
    
    # Load candidates
    logger.info("📂 Loading candidates for INTELLIGENT SKILL ANALYSIS...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        candidates = json.load(f)
    
    logger.info(f"✅ Loaded {len(candidates)} candidates")
    
    # Process with intelligent analysis
    async with IntelligentSkillProcessor() as processor:
        # Start with smaller batch for testing
        candidates = candidates[:50]  # Test with 50 for quality check
        
        # Smaller batch size to avoid rate limits
        await processor.process_batch_streaming(candidates, batch_size=5)

if __name__ == "__main__":
    asyncio.run(main())
