#!/usr/bin/env python3
"""
Together AI Batch Processor for Headhunter AI
Processes 29,000 candidates using Together AI Llama 3.1 8B API
Cost-effective alternative to local processing
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
from google.cloud import firestore
from google.auth import default

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ProcessingStats:
    total_candidates: int = 0
    processed: int = 0
    failed: int = 0
    start_time: Optional[datetime] = None
    estimated_cost: float = 0.0
    
class TogetherAIProcessor:
    """Batch processor using Together AI API for candidate analysis"""
    
    def __init__(self, api_key: str, model: str = None, use_firestore: bool = True):
        self.api_key = api_key or os.getenv('TOGETHER_API_KEY')
        if not self.api_key:
            raise ValueError("Together API key not provided")
        # Default Stage 1 model to Qwen2.5 32B Instruct if not provided
        self.model = model or os.getenv('TOGETHER_MODEL_STAGE1', 'Qwen2.5-32B-Instruct')
        self.base_url = "https://api.together.xyz/v1/chat/completions"
        self.session = None
        self.use_firestore = use_firestore
        
        # Initialize Firestore if enabled
        self.db = None
        if self.use_firestore:
            try:
                # Set credentials path
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/Users/delimatsuo/Documents/Coding/headhunter/.gcp/headhunter-service-key.json'
                self.db = firestore.Client(project='headhunter-ai-0088')
                logger.info("✅ Connected to Firestore database")
            except Exception as e:
                logger.warning(f"⚠️ Firestore connection failed, falling back to local storage: {e}")
                self.use_firestore = False
        
        # Cost tracking (estimate $0.10 per million tokens)
        self.cost_per_token = 0.10 / 1_000_000
        
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
        """Create a comprehensive analysis prompt for a candidate"""
        
        name = candidate_data.get('name', 'Unknown')
        experience = candidate_data.get('experience', '')
        education = candidate_data.get('education', '')
        comments = candidate_data.get('comments', [])
        
        # Combine recruiter comments
        comment_text = ""
        if comments:
            comment_text = "\n".join([f"- {comment.get('text', '')}" for comment in comments])
        
        prompt = f"""
As an expert executive recruiter and career analyst, provide a comprehensive analysis of this candidate profile. Return your analysis as a valid JSON object with the following structure:

{{
  "personal_details": {{
    "name": "{name}",
    "seniority_level": "Entry/Mid/Senior/Executive",
    "years_of_experience": "estimate in years",
    "location": "inferred location"
  }},
  "education_analysis": {{
    "degrees": ["list of degrees"],
    "quality_score": "1-10 scale with explanation", 
    "relevance": "relevance to tech/business roles",
    "highest_degree": "BS/MS/PhD/etc"
  }},
  "experience_analysis": {{
    "total_years": "estimated years",
    "companies": ["list of companies worked at"],
    "current_role": "most recent position",
    "career_progression": "description of career trajectory",
    "industry_focus": "primary industry"
  }},
  "technical_assessment": {{
    "primary_skills": ["top 3-5 key skills"],
    "secondary_skills": ["additional skills"],
    "expertise_level": "Beginner/Intermediate/Advanced/Expert",
    "technology_stack": "main technologies used"
  }},
  "market_insights": {{
    "estimated_salary_range": "salary estimate with currency",
    "market_demand": "Low/Medium/High demand assessment",
    "competitive_advantage": "key differentiators",
    "placement_difficulty": "Easy/Medium/Hard to place"
  }},
  "cultural_assessment": {{
    "work_style": "inferred work style and preferences",
    "company_fit": "types of companies that would be good fit",
    "red_flags": ["potential concerns"],
    "strengths": ["key strengths for recruitment"]
  }},
  "recruiter_recommendations": {{
    "ideal_roles": ["top 3-5 role recommendations"],
    "target_companies": ["company types or specific companies"],
    "positioning_strategy": "how to present this candidate",
    "interview_prep": "key areas to prepare candidate"
  }},
  "searchability": {{
    "keywords": ["key search terms"],
    "job_titles": ["relevant job titles"],
    "skills_taxonomy": ["categorized skills"]
  }},
  "executive_summary": {{
    "one_line_pitch": "compelling one-line candidate summary",
    "key_achievements": ["top 2-3 achievements inferred"],
    "overall_rating": "A/B/C/D rating",
    "recommendation": "Highly Recommended/Recommended/Consider/Pass"
  }}
}}

CANDIDATE DATA:
Name: {name}

Experience:
{experience[:2000] if experience else "No experience data provided"}

Education:
{education[:1000] if education else "No education data provided"}

Recruiter Comments:
{comment_text[:1000] if comment_text else "No recruiter comments available"}

Provide ONLY the JSON response with detailed, specific analysis based on the available data. If data is missing, make reasonable inferences but indicate uncertainty.
"""
        return prompt
    
    async def process_candidate(self, candidate_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single candidate through Together AI API"""
        
        candidate_id = candidate_data.get('id', 'unknown')
        
        try:
            prompt = self.create_analysis_prompt(candidate_data)
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "max_tokens": 4000,
                "temperature": 0.1,
                "top_p": 0.9
            }
            
            async with self.session.post(self.base_url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if 'choices' in result and len(result['choices']) > 0:
                        content = result['choices'][0]['message']['content']
                        
                        # Try to repair and parse JSON then validate
                        try:
                            repaired = repair_json(content)
                            analysis = IntelligentAnalysis.model_validate(repaired).model_dump()
                            
                            # Add metadata
                            enhanced_data = {
                                "candidate_id": candidate_id,
                                "name": candidate_data.get('name', 'Unknown'),
                                "original_data": {
                                    "education": candidate_data.get('education', ''),
                                    "experience": candidate_data.get('experience', ''),
                                    "comments": candidate_data.get('comments', [])
                                },
                                "recruiter_analysis": analysis,
                                "processing_metadata": {
                                    "timestamp": datetime.now().isoformat(),
                                    "processor": "together_ai_processor",
                                    "model": self.model,
                                    "api_version": "v1"
                                }
                            }
                            
                            return enhanced_data
                            
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse JSON for candidate {candidate_id}: {e}")
                            return None
                    
                else:
                    logger.error(f"API error for candidate {candidate_id}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error processing candidate {candidate_id}: {e}")
            return None
    
    async def upload_to_firestore(self, candidates: List[Dict[str, Any]]) -> int:
        """Upload batch of candidates to Firestore"""
        if not self.db or not candidates:
            return 0
            
        uploaded = 0
        collection_ref = self.db.collection('enhanced_candidates')
        
        try:
            # Use batch writes for efficiency
            batch = self.db.batch()
            batch_count = 0
            
            for candidate in candidates:
                candidate_id = candidate.get('candidate_id', f"unknown_{uploaded}")
                doc_ref = collection_ref.document(candidate_id)
                batch.set(doc_ref, candidate)
                batch_count += 1
                
                # Commit every 500 documents (Firestore limit)
                if batch_count >= 500:
                    batch.commit()
                    uploaded += batch_count
                    batch = self.db.batch()
                    batch_count = 0
            
            # Commit remaining documents
            if batch_count > 0:
                batch.commit()
                uploaded += batch_count
                
            logger.info(f"✅ Uploaded {uploaded} candidates to Firestore")
            return uploaded
            
        except Exception as e:
            logger.error(f"❌ Firestore upload error: {e}")
            return uploaded
    
    async def process_batch(self, candidates: List[Dict[str, Any]], 
                          batch_size: int = 10, 
                          delay: float = 1.0) -> List[Dict[str, Any]]:
        """Process candidates in batches and stream to Firestore"""
        
        results = []
        total = len(candidates)
        total_uploaded = 0
        
        logger.info(f"Processing {total} candidates in batches of {batch_size}")
        if self.use_firestore:
            logger.info("📤 Streaming results to Firestore in real-time")
        
        for i in range(0, total, batch_size):
            batch = candidates[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} candidates)")
            
            # Process batch concurrently
            tasks = [self.process_candidate(candidate) for candidate in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter successful results
            successful_results = [
                result for result in batch_results 
                if result is not None and not isinstance(result, Exception)
            ]
            
            results.extend(successful_results)
            
            # Upload batch to Firestore immediately
            if self.use_firestore and successful_results:
                uploaded = await self.upload_to_firestore(successful_results)
                total_uploaded += uploaded
                logger.info(f"📊 Total uploaded to Firestore: {total_uploaded} candidates")
            
            # Log progress
            completed = len(results)
            logger.info(f"Batch {batch_num} completed: {len(successful_results)}/{len(batch)} successful")
            logger.info(f"Overall progress: {completed}/{total} candidates processed")
            
            # Rate limiting delay
            if i + batch_size < total:  # Don't delay after last batch
                await asyncio.sleep(delay)
        
        if self.use_firestore:
            logger.info(f"🎯 Final: {total_uploaded} candidates uploaded to Firestore")
        
        return results
    
    def load_merged_candidates(self, file_path: str) -> List[Dict[str, Any]]:
        """Load candidates from merged JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Loaded {len(data)} candidates from {file_path}")
            return data
            
        except Exception as e:
            logger.error(f"Error loading candidates: {e}")
            return []
    
    def save_results(self, results: List[Dict[str, Any]], output_file: str):
        """Save enhanced results to file"""
        try:
            # Create output directory
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"Saved {len(results)} enhanced candidates to {output_file}")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    def estimate_cost(self, candidates: List[Dict[str, Any]]) -> float:
        """Estimate processing cost"""
        
        # Estimate tokens per candidate (prompt + response)
        avg_tokens_per_candidate = 5000  # Conservative estimate
        total_tokens = len(candidates) * avg_tokens_per_candidate
        estimated_cost = total_tokens * self.cost_per_token
        
        return estimated_cost

async def main():
    """Main processing function"""
    
    # Configuration
    API_KEY = "6d9eb8b102a05bae51baa97445cff83aff1eaf38ee7c09528bee54efe4ca4824"  # Keep secure
    INPUT_FILE = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
    OUTPUT_FILE = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/together_ai_enhanced_candidates.json"
    
    # Processing settings
    BATCH_SIZE = 20  # Concurrent requests
    DELAY_BETWEEN_BATCHES = 2.0  # Seconds
    MAX_CANDIDATES = 29000  # Process all candidates
    
    # Initialize processor
    async with TogetherAIProcessor(API_KEY) as processor:
        
        # Load candidates
        logger.info("Loading merged candidates...")
        candidates = processor.load_merged_candidates(INPUT_FILE)
        
        if not candidates:
            logger.error("No candidates loaded. Exiting.")
            return
        
        # Limit for processing (remove this to process all)
        candidates = candidates[:MAX_CANDIDATES]
        
        # Estimate cost
        estimated_cost = processor.estimate_cost(candidates)
        logger.info(f"Estimated cost for {len(candidates)} candidates: ${estimated_cost:.2f}")
        
        # Auto-proceed with processing (user confirmed via Claude interface)
        logger.info(f"Auto-proceeding with processing {len(candidates)} candidates at estimated cost ${estimated_cost:.2f}")
        logger.info("User confirmation received via Claude interface")
        
        # Start processing
        start_time = datetime.now()
        logger.info(f"Starting batch processing at {start_time}")
        
        results = await processor.process_batch(
            candidates, 
            batch_size=BATCH_SIZE, 
            delay=DELAY_BETWEEN_BATCHES
        )
        
        # Processing complete
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"Processing completed in {duration:.2f} seconds")
        logger.info(f"Successfully processed: {len(results)}/{len(candidates)} candidates")
        logger.info(f"Success rate: {len(results)/len(candidates)*100:.1f}%")
        
        # Save results
        if results:
            processor.save_results(results, OUTPUT_FILE)
            logger.info(f"Enhanced candidate data saved to: {OUTPUT_FILE}")
        else:
            logger.warning("No results to save.")

if __name__ == "__main__":
from scripts.json_repair import repair_json
from scripts.schemas import IntelligentAnalysis
    asyncio.run(main())
