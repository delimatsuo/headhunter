"""
Candidate processing logic for Cloud Run worker
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
import json

from .config import Config
from .models import (
    CandidateData, 
    EnrichedCandidateData, 
    ProcessingStatus, 
    ProcessingResult
)
from .together_ai_client import TogetherAIClient
from .firestore_client import FirestoreClient

logger = logging.getLogger(__name__)


class CandidateProcessor:
    """Main processor for candidate enrichment workflow"""
    
    def __init__(self, config: Config):
        self.config = config
        self.together_ai_client = TogetherAIClient(config)
        self.firestore_client = FirestoreClient(config)
        
        # Processing status tracking
        self._processing_status: Dict[str, ProcessingStatus] = {}
        
        # Retry configuration
        self.max_retries = config.retry_max_attempts
        self.base_delay = config.retry_base_delay
        
    async def initialize(self):
        """Initialize processor components"""
        await self.together_ai_client.initialize()
        await self.firestore_client.initialize()
        logger.info("Candidate processor initialized")
    
    async def shutdown(self):
        """Cleanup processor components"""
        await self.together_ai_client.shutdown()
        await self.firestore_client.shutdown()
        logger.info("Candidate processor shutdown complete")
    
    async def fetch_candidate_data(self, candidate_id: str) -> CandidateData:
        """
        Fetch candidate data from Firestore
        
        Args:
            candidate_id: ID of candidate to fetch
            
        Returns:
            CandidateData: Candidate information
            
        Raises:
            ValueError: If candidate not found
        """
        try:
            logger.info(f"Fetching candidate data: {candidate_id}")
            
            raw_data = await self.firestore_client.get_candidate(candidate_id)
            if not raw_data:
                raise ValueError(f"Candidate {candidate_id} not found")
            
            # Convert to CandidateData model
            candidate_data = CandidateData(
                candidate_id=raw_data.get("candidate_id", candidate_id),
                name=raw_data.get("name", "Unknown"),
                email=raw_data.get("email"),
                resume_text=raw_data.get("resume_text"),
                recruiter_comments=raw_data.get("recruiter_comments"),
                org_id=raw_data.get("org_id", ""),
                uploaded_at=raw_data.get("uploaded_at", datetime.now().isoformat()),
                status=raw_data.get("status", "pending_enrichment"),
                metadata=raw_data.get("metadata", {})
            )
            
            logger.info(f"Successfully fetched candidate: {candidate_id}")
            return candidate_data
            
        except Exception as e:
            logger.error(f"Failed to fetch candidate {candidate_id}: {e}")
            raise
    
    async def process_with_together_ai(self, candidate_data: CandidateData) -> EnrichedCandidateData:
        """
        Process candidate with Together AI for enrichment
        
        Args:
            candidate_data: Raw candidate information
            
        Returns:
            EnrichedCandidateData: AI-enriched candidate profile
        """
        try:
            logger.info(f"Processing candidate with Together AI: {candidate_data.candidate_id}")
            
            # Prepare input for Together AI
            input_data = {
                "name": candidate_data.name,
                "resume_text": candidate_data.resume_text or "",
                "recruiter_comments": candidate_data.recruiter_comments or "",
                "metadata": candidate_data.metadata
            }
            
            # Call Together AI for enrichment
            ai_response = await self.together_ai_client.enrich_candidate(input_data)
            
            # Convert response to structured data
            enriched_data = EnrichedCandidateData(
                resume_analysis=ai_response.get("resume_analysis", {}),
                recruiter_insights=ai_response.get("recruiter_insights", {}),
                overall_score=ai_response.get("overall_score", 0.0),
                processing_metadata={
                    "processed_at": datetime.now().isoformat(),
                    "model_version": self.config.together_ai_model,
                    "processing_time": ai_response.get("processing_time", 0),
                    "token_usage": ai_response.get("token_usage", {})
                }
            )
            
            logger.info(f"Successfully enriched candidate: {candidate_data.candidate_id}")
            return enriched_data
            
        except Exception as e:
            logger.error(f"Failed to process candidate {candidate_data.candidate_id} with Together AI: {e}")
            raise
    
    async def store_processing_result(self, candidate_id: str, enriched_data: EnrichedCandidateData) -> bool:
        """
        Store enriched candidate data back to Firestore
        
        Args:
            candidate_id: ID of candidate
            enriched_data: Enriched candidate information
            
        Returns:
            bool: True if storage was successful
        """
        try:
            logger.info(f"Storing processing results: {candidate_id}")
            
            # Prepare update data
            update_data = {
                "resume_analysis": enriched_data.resume_analysis,
                "recruiter_insights": enriched_data.recruiter_insights,
                "overall_score": enriched_data.overall_score,
                "processing_metadata": enriched_data.processing_metadata,
                "status": "enriched",
                "enriched_at": datetime.now().isoformat()
            }
            
            # Update in Firestore
            success = await self.firestore_client.update_candidate(candidate_id, update_data)
            
            if success:
                logger.info(f"Successfully stored results for candidate: {candidate_id}")
            else:
                logger.error(f"Failed to store results for candidate: {candidate_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error storing results for candidate {candidate_id}: {e}")
            return False
    
    async def process_single_candidate(self, candidate_id: str) -> ProcessingResult:
        """
        Process a single candidate through the complete enrichment pipeline
        
        Args:
            candidate_id: ID of candidate to process
            
        Returns:
            ProcessingResult: Result of processing
        """
        start_time = datetime.now()
        
        try:
            # Update status
            self.update_processing_status(candidate_id, ProcessingStatus.IN_PROGRESS)
            
            # Fetch candidate data
            candidate_data = await self.fetch_candidate_data(candidate_id)
            
            # Process with Together AI
            enriched_data = await self.process_with_together_ai(candidate_data)
            
            # Store results
            success = await self.store_processing_result(candidate_id, enriched_data)
            
            if not success:
                raise Exception("Failed to store processing results")
            
            # Update status
            self.update_processing_status(candidate_id, ProcessingStatus.COMPLETED)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return ProcessingResult(
                candidate_id=candidate_id,
                status="completed",
                processing_time_seconds=processing_time,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            # Update status
            self.update_processing_status(candidate_id, ProcessingStatus.FAILED)
            
            return ProcessingResult(
                candidate_id=candidate_id,
                status="failed",
                error=str(e),
                timestamp=datetime.now().isoformat()
            )
    
    async def process_batch(self, candidate_ids: List[str], max_concurrent: int = 5) -> List[ProcessingResult]:
        """
        Process multiple candidates concurrently
        
        Args:
            candidate_ids: List of candidate IDs to process
            max_concurrent: Maximum number of concurrent processes
            
        Returns:
            List[ProcessingResult]: Results for each candidate
        """
        logger.info(f"Starting batch processing for {len(candidate_ids)} candidates")
        
        # Use semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(candidate_id: str):
            async with semaphore:
                return await self.process_single_candidate(candidate_id)
        
        # Process all candidates concurrently
        results = await asyncio.gather(
            *[process_with_semaphore(cid) for cid in candidate_ids],
            return_exceptions=True
        )
        
        # Convert exceptions to failed results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(ProcessingResult(
                    candidate_id=candidate_ids[i],
                    status="failed",
                    error=str(result),
                    timestamp=datetime.now().isoformat()
                ))
            else:
                final_results.append(result)
        
        successful = sum(1 for r in final_results if r.status == "completed")
        logger.info(f"Batch processing complete: {successful}/{len(candidate_ids)} successful")
        
        return final_results
    
    async def retry_with_backoff(self, func, max_retries: int = None, *args, **kwargs):
        """
        Execute function with exponential backoff retry logic
        
        Args:
            func: Async function to execute
            max_retries: Maximum number of retries
            *args, **kwargs: Arguments for the function
            
        Returns:
            Result of function execution
        """
        if max_retries is None:
            max_retries = self.max_retries
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt == max_retries:
                    # Final attempt failed
                    break
                
                # Calculate delay with exponential backoff
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                
                await asyncio.sleep(delay)
        
        # All retries exhausted
        raise last_exception
    
    def update_processing_status(self, candidate_id: str, status: ProcessingStatus):
        """Update processing status for a candidate"""
        self._processing_status[candidate_id] = status
        logger.debug(f"Updated status for {candidate_id}: {status.value}")
    
    def get_processing_status(self, candidate_id: str) -> Optional[ProcessingStatus]:
        """Get current processing status for a candidate"""
        return self._processing_status.get(candidate_id)
    
    async def health_check(self) -> bool:
        """
        Perform health check on processor components
        
        Returns:
            bool: True if all components are healthy
        """
        try:
            # Check Firestore connectivity
            firestore_healthy = await self.firestore_client.health_check()
            
            # Check Together AI connectivity
            together_ai_healthy = await self.together_ai_client.health_check()
            
            return firestore_healthy and together_ai_healthy
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False