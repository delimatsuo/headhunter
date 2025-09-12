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
from scripts.json_validator import JSONValidator
from scripts.prompt_builder import PromptBuilder
from scripts.firestore_streamer import FirestoreStreamer

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
    failed_validations: int = 0
    start_time: Optional[datetime] = None
    estimated_cost: float = 0.0
    
class IntelligentSkillProcessor:
    """Processes candidates with intelligent skill inference and probabilistic analysis"""
    
    def __init__(self, api_key: str = None):
        # Require API key via env or parameter (no hardcoded defaults)
        self.api_key = api_key or os.getenv('TOGETHER_API_KEY')
        if not self.api_key:
            raise ValueError("Together API key not provided")

        # Stage 1 model configurable via env; default to Qwen2.5 32B Instruct
        # Adjust to the exact Together model ID during deployment if needed
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
        
        # JSON validation system
        self.json_validator = JSONValidator()
        
        # Enhanced Firestore streaming system
        if self.use_firestore:
            # Ensure checkpoint directory exists
            checkpoint_dir = ".checkpoints"
            if not os.path.exists(checkpoint_dir):
                os.makedirs(checkpoint_dir, exist_ok=True)
                
            self.firestore_streamer = FirestoreStreamer(
                firestore_client=self.db,
                batch_size=10,  # Smaller batches for real-time processing
                collections=["candidates", "enriched_profiles"],
                checkpoint_file=f"{checkpoint_dir}/intelligent_processor_checkpoint.json"
            )
        else:
            self.firestore_streamer = None
        
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
        builder = PromptBuilder()
        return builder.build_resume_analysis_prompt(candidate_data)
    
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
                            # Use JSON validation system with repair and quarantine
                            validation_result = self.json_validator.validate(content, candidate_id=candidate_id)
                            
                            if validation_result.is_valid:
                                analysis = validation_result.data
                            else:
                                # JSON validation failed and was quarantined
                                logger.error(f"❌ JSON validation failed for candidate {candidate_id}")
                                logger.error(f"   Errors: {validation_result.errors}")
                                if validation_result.quarantined:
                                    logger.error(f"   Quarantined as: {validation_result.quarantine_id}")
                                
                                self.stats.failed_validations += 1
                                return None  # Skip this candidate
                            
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

                            # Add analysis confidence and quality flags for downstream ranking/UX
                            enhanced_data["analysis_confidence"] = self._estimate_analysis_confidence(analysis)
                            enhanced_data["quality_flags"] = self._quality_flags(analysis, enhanced_data["analysis_confidence"]) 
                            
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

    def _estimate_analysis_confidence(self, analysis: Dict[str, Any]) -> float:
        """Estimate overall analysis confidence in [0,1] from signal density.
        Combines counts of explicit & inferred skills, average inferred confidence,
        and presence of evidence/reasoning fields.
        """
        try:
            explicit = analysis.get("explicit_skills", {}).get("technical_skills", [])
            inferred = analysis.get("inferred_skills", {})
            hp = inferred.get("highly_probable_skills", [])
            p = inferred.get("probable_skills", [])

            # Average confidence across inferred skills
            confs = []
            for bucket in (hp, p):
                for item in bucket:
                    c = item.get("confidence")
                    if isinstance(c, (int, float)):
                        confs.append(max(0.0, min(1.0, float(c) / 100.0)))
            avg_conf = sum(confs) / len(confs) if confs else 0.0

            # Evidence density proxy
            evidence_hits = 0
            for bucket in (hp, p):
                for item in bucket:
                    if item.get("reasoning") or item.get("evidence"):
                        evidence_hits += 1

            score = 0.0
            score += min(len(explicit), 8) / 8.0 * 0.35
            score += min(len(hp), 8) / 8.0 * 0.25
            score += min(len(p), 12) / 12.0 * 0.15
            score += avg_conf * 0.20
            score += min(evidence_hits, 8) / 8.0 * 0.05
            return round(max(0.0, min(1.0, score)), 3)
        except Exception:
            return 0.4

    def _quality_flags(self, analysis: Dict[str, Any], conf: float) -> List[str]:
        flags: List[str] = []
        if conf < 0.45:
            flags.append("low_content")
        # basic missing experience structure
        if not analysis.get("experience_analysis") and not analysis.get("companies"):
            flags.append("missing_experience_structure")
        return flags
    
    async def upload_batch_to_firestore(self, candidates: List[Dict[str, Any]]) -> int:
        """Upload batch to Firestore using enhanced streaming system"""
        
        if not self.firestore_streamer or not candidates:
            return 0
            
        uploaded = 0
        
        try:
            for candidate in candidates:
                candidate_id = candidate.get('candidate_id', f"unknown_{uploaded}")
                
                # Add to main candidates collection
                result = self.firestore_streamer.add_document(
                    "candidates", 
                    candidate_id, 
                    candidate,
                    upsert=True
                )
                
                if result.success:
                    uploaded += 1
                    
                    # Also add to enriched_profiles collection for specialized queries
                    if "intelligent_analysis" in candidate:
                        enriched_doc = {
                            "candidate_id": candidate_id,
                            "name": candidate.get("name"),
                            "intelligent_analysis": candidate["intelligent_analysis"],
                            "processing_metadata": candidate.get("processing_metadata"),
                            "enrichment_timestamp": firestore.SERVER_TIMESTAMP
                        }
                        
                        self.firestore_streamer.add_document(
                            "enriched_profiles",
                            candidate_id,
                            enriched_doc,
                            upsert=True
                        )
            
            # Flush any remaining documents
            flush_result = await self.firestore_streamer.flush_batch()
            
            if flush_result.success:
                self.stats.uploaded += uploaded
                
                # Get streaming metrics
                streaming_metrics = self.firestore_streamer.get_metrics()
                logger.info(f"""📤 Enhanced streaming upload complete:
   ✅ Documents: {uploaded} candidates + {uploaded} enriched profiles
   📊 Streaming metrics:
      - Total streamed: {streaming_metrics['total_documents']}
      - Success rate: {streaming_metrics['successful_writes']}/{streaming_metrics['total_documents']}
      - Avg latency: {streaming_metrics['write_latency_ms']:.1f}ms
      - Throughput: {streaming_metrics['documents_per_second']:.1f} docs/sec""")
                
                return uploaded
            else:
                logger.error(f"Flush failed: {flush_result.error_message}")
                return 0
            
        except Exception as e:
            logger.error(f"Enhanced Firestore streaming error: {e}")
            return 0
    
    async def process_batch_streaming(self, candidates: List[Dict[str, Any]], 
                                    batch_size: int = 5) -> None:
        """Process candidates with intelligent analysis and stream to Firestore"""
        
        self.stats.total_candidates = len(candidates)
        self.stats.start_time = datetime.now()
        
        logger.info(f"🚀 Starting INTELLIGENT SKILL ANALYSIS for {self.stats.total_candidates} candidates")
        logger.info("🧠 Using probabilistic inference to identify likely skills based on roles and companies")
        logger.info("📊 Separating explicit skills (100% confidence) from inferred skills (with probability scores)")
        
        # Check for existing checkpoint
        start_index = 0
        if self.firestore_streamer:
            checkpoint = self.firestore_streamer.load_checkpoint()
            if checkpoint:
                logger.info(f"💾 Found checkpoint: resuming from {checkpoint.get('last_processed_id')}")
                additional_data = checkpoint.get('additional_data', {})
                start_batch = additional_data.get('batch_number', 0)
                start_index = start_batch * batch_size
                
                # Restore stats from checkpoint
                if 'processed_count' in additional_data:
                    self.stats.processed = additional_data['processed_count']
                if 'upload_count' in additional_data:
                    self.stats.uploaded = additional_data['upload_count']
                    
                logger.info(f"📊 Resuming from batch {start_batch + 1}, processed: {self.stats.processed}")
        
        for i in range(start_index, self.stats.total_candidates, batch_size):
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
                
                # Save checkpoint after successful upload
                if self.firestore_streamer:
                    last_candidate_id = successful_results[-1].get('candidate_id', f'batch_{batch_num}')
                    self.firestore_streamer.save_checkpoint(
                        last_processed_id=last_candidate_id,
                        additional_data={
                            'batch_number': batch_num,
                            'total_batches': total_batches,
                            'processed_count': self.stats.processed,
                            'upload_count': self.stats.uploaded
                        }
                    )
            
            # Progress update
            elapsed = (datetime.now() - self.stats.start_time).total_seconds()
            rate = self.stats.processed / elapsed if elapsed > 0 else 0
            eta_seconds = (self.stats.total_candidates - self.stats.processed) / rate if rate > 0 else 0
            
            logger.info(f"""
📊 Batch {batch_num}/{total_batches} Complete:
   ✅ Intelligent Analysis Complete: {self.stats.processed}/{self.stats.total_candidates}
   📤 Uploaded with Skill Inference: {self.stats.uploaded}
   ❌ Failed: {self.stats.failed}
   🔧 JSON Validation Failures: {self.stats.failed_validations}
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
        
        # Final summary with validation metrics
        total_time = (datetime.now() - self.stats.start_time).total_seconds()
        validation_metrics = self.json_validator.get_metrics()
        
        logger.info(f"""
🎯 INTELLIGENT ANALYSIS COMPLETE:
   ✅ Successfully analyzed: {self.stats.processed}/{self.stats.total_candidates}
   📤 Uploaded to Firestore: {self.stats.uploaded}
   ❌ Failed: {self.stats.failed}
   🔧 JSON Validation Failures: {self.stats.failed_validations}
   ⏱️ Total time: {total_time/60:.1f} minutes
   💰 Estimated cost: ${self.stats.processed * 6000 * self.cost_per_token:.2f}
   
   📊 JSON VALIDATION METRICS:
      - Total validations: {validation_metrics.get('total_validations', 0)}
      - Successful validations: {validation_metrics.get('successful_validations', 0)}
      - Repair attempts: {validation_metrics.get('repair_attempts', 0)}
      - Quarantined responses: {validation_metrics.get('quarantined_count', 0)}
      - Avg processing time: {validation_metrics.get('avg_processing_time_ms', 0):.1f}ms
   
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
