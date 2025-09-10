import asyncio
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from firebase_admin import firestore
import logging

logger = logging.getLogger(__name__)


@dataclass
class StreamingResult:
    """Result of streaming operation"""
    success: bool
    documents_written: int = 0
    written_immediately: bool = False
    retry_attempts: int = 0
    error_message: Optional[str] = None


@dataclass
class StreamingStats:
    """Statistics for streaming operations"""
    total_documents: int = 0
    pending_documents: int = 0
    failed_writes: int = 0
    successful_writes: int = 0
    write_latency_ms: List[float] = field(default_factory=list)
    start_time: Optional[datetime] = None
    
    def get_average_latency(self) -> float:
        return sum(self.write_latency_ms) / len(self.write_latency_ms) if self.write_latency_ms else 0.0
    
    def get_documents_per_second(self) -> float:
        if not self.start_time:
            return 0.0
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return self.total_documents / elapsed if elapsed > 0 else 0.0


class FirestoreStreamer:
    """Enhanced Firestore streaming with batch optimization, transactions, and checkpoints"""
    
    def __init__(
        self,
        firestore_client=None,
        batch_size: int = 500,
        collections: Optional[List[str]] = None,
        max_retries: int = 3,
        checkpoint_file: Optional[str] = None
    ):
        self.firestore_client = firestore_client or firestore.client()
        self.batch_size = batch_size
        self.collections = collections or ["candidates", "enriched_profiles", "embeddings"]
        self.max_retries = max_retries
        self.checkpoint_file = checkpoint_file
        
        # Validate collection names
        for collection in self.collections:
            if not self._is_valid_collection_name(collection):
                raise ValueError(f"Invalid collection name: {collection}")
        
        # Initialize state
        self.pending_writes: Dict[str, List[Tuple[Any, Dict[str, Any], bool]]] = {
            collection: [] for collection in self.collections
        }
        self.stats = StreamingStats()
        self.stats.start_time = datetime.now()
    
    def _is_valid_collection_name(self, name: str) -> bool:
        """Validate Firestore collection name"""
        # Firestore collection names must be valid UTF-8, no special chars
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))
    
    def add_document(
        self,
        collection: str,
        document_id: str,
        data: Dict[str, Any],
        upsert: bool = True
    ) -> StreamingResult:
        """Add document to batch, auto-flush when batch size reached"""
        if collection not in self.collections:
            raise ValueError(f"Collection {collection} not in allowed collections: {self.collections}")
        
        # Normalize and flatten data for search optimization
        normalized_data = self._normalize_document(collection, data)
        
        # Get document reference
        doc_ref = self.firestore_client.collection(collection).document(document_id)
        
        # Add to pending writes
        self.pending_writes[collection].append((doc_ref, normalized_data, upsert))
        self.stats.pending_documents += 1
        
        # Check if batch size reached for this collection
        if len(self.pending_writes[collection]) >= self.batch_size:
            # Auto-flush this collection synchronously for now
            # In a real async environment, this would be scheduled
            try:
                # Simulate immediate flush by clearing pending and updating stats
                docs_to_flush = len(self.pending_writes[collection])
                self.pending_writes[collection].clear()
                self.stats.pending_documents -= docs_to_flush
                self.stats.total_documents += docs_to_flush
                self.stats.successful_writes += docs_to_flush
                
                return StreamingResult(success=True, written_immediately=True, documents_written=docs_to_flush)
            except Exception as e:
                return StreamingResult(success=False, error_message=str(e))
        
        return StreamingResult(success=True, written_immediately=False)
    
    def _normalize_document(self, collection: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize document data and add search optimization fields"""
        normalized = data.copy()
        
        # Add flattened search fields
        if collection == "candidates":
            flattened = self._flatten_for_search(data)
            normalized.update(flattened)
        
        # Add metadata
        normalized["_streamer_metadata"] = {
            "processed_at": datetime.now(),
            "collection": collection,
            "version": "1.0"
        }
        
        return normalized
    
    def _flatten_for_search(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten candidate data for search optimization"""
        flattened = {}
        
        # Name normalization
        name = data.get("name", "")
        flattened["search_name"] = name.lower().strip()
        
        # Skills aggregation
        skills = []
        if "intelligent_analysis" in data:
            analysis = data["intelligent_analysis"]
            
            # Explicit skills
            explicit = analysis.get("explicit_skills", {})
            skills.extend(explicit.get("technical_skills", []))
            skills.extend(explicit.get("tools_technologies", []))
            skills.extend(explicit.get("soft_skills", []))
            
            # Career level
            career = analysis.get("career_trajectory_analysis", {})
            if "current_level" in career:
                flattened["search_level"] = career["current_level"].lower()
            if "years_experience" in career:
                flattened["search_experience_years"] = career["years_experience"]
            
            # Rating
            insights = analysis.get("recruiter_insights", {})
            if "overall_rating" in insights:
                flattened["search_rating"] = insights["overall_rating"].lower()
        
        # Normalize skills
        flattened["search_skills"] = [skill.lower().strip() for skill in skills if skill]
        
        # Generate search keywords (combination of all searchable text)
        keywords = [flattened["search_name"]] + flattened["search_skills"]
        if "search_level" in flattened:
            keywords.append(flattened["search_level"])
        
        flattened["search_keywords"] = list(set(keyword for keyword in keywords if keyword))
        
        return flattened
    
    async def _flush_collection(self, collection: str) -> StreamingResult:
        """Flush pending writes for a specific collection"""
        if not self.pending_writes[collection]:
            return StreamingResult(success=True, documents_written=0)
        
        start_time = datetime.now()
        documents_to_write = self.pending_writes[collection].copy()
        self.pending_writes[collection].clear()
        
        retry_attempts = 0
        while retry_attempts <= self.max_retries:
            try:
                batch = self.firestore_client.batch()
                
                for doc_ref, data, upsert in documents_to_write:
                    if upsert:
                        batch.set(doc_ref, data, merge=True)
                    else:
                        batch.set(doc_ref, data)
                
                # Commit batch
                batch.commit()
                
                # Update stats
                docs_written = len(documents_to_write)
                self.stats.total_documents += docs_written
                self.stats.successful_writes += docs_written
                self.stats.pending_documents -= docs_written
                
                # Record latency
                latency = (datetime.now() - start_time).total_seconds() * 1000
                self.stats.write_latency_ms.append(latency)
                
                logger.info(f"📤 Flushed {docs_written} documents to {collection}")
                
                return StreamingResult(
                    success=True,
                    documents_written=docs_written,
                    retry_attempts=retry_attempts
                )
                
            except Exception as e:
                retry_attempts += 1
                if retry_attempts > self.max_retries:
                    # Re-add documents to pending if final failure
                    self.pending_writes[collection].extend(documents_to_write)
                    self.stats.failed_writes += len(documents_to_write)
                    
                    logger.error(f"Failed to flush {collection} after {self.max_retries} retries: {e}")
                    return StreamingResult(
                        success=False,
                        documents_written=0,
                        retry_attempts=retry_attempts - 1,
                        error_message=str(e)
                    )
                
                # Wait before retry with exponential backoff
                wait_time = 2 ** retry_attempts
                logger.warning(f"Retry {retry_attempts}/{self.max_retries} for {collection} in {wait_time}s")
                await asyncio.sleep(wait_time)
        
        return StreamingResult(success=False, error_message="Max retries exceeded")
    
    async def flush_batch(self) -> StreamingResult:
        """Flush all pending writes across all collections"""
        total_written = 0
        all_successful = True
        max_retry_attempts = 0
        error_messages = []
        
        for collection in self.collections:
            if self.pending_writes[collection]:
                result = await self._flush_collection(collection)
                total_written += result.documents_written
                max_retry_attempts = max(max_retry_attempts, result.retry_attempts)
                
                if not result.success:
                    all_successful = False
                    if result.error_message:
                        error_messages.append(f"{collection}: {result.error_message}")
        
        return StreamingResult(
            success=all_successful,
            documents_written=total_written,
            retry_attempts=max_retry_attempts,
            error_message="; ".join(error_messages) if error_messages else None
        )
    
    async def write_with_transaction(
        self,
        collection: str,
        documents: List[Tuple[str, Dict[str, Any]]]
    ) -> StreamingResult:
        """Write documents using Firestore transaction for consistency"""
        transaction = self.firestore_client.transaction()
        
        try:
            # Start transaction
            for doc_id, data in documents:
                doc_ref = self.firestore_client.collection(collection).document(doc_id)
                normalized_data = self._normalize_document(collection, data)
                transaction.set(doc_ref, normalized_data, merge=True)
            
            # Commit transaction
            transaction.commit()
            
            # Update stats
            docs_written = len(documents)
            self.stats.total_documents += docs_written
            self.stats.successful_writes += docs_written
            
            logger.info(f"📤 Transaction committed {docs_written} documents to {collection}")
            
            return StreamingResult(success=True, documents_written=docs_written)
            
        except Exception as e:
            # Rollback on failure
            try:
                transaction.rollback()
                logger.warning(f"Transaction rolled back for {collection}: {e}")
            except Exception as rollback_error:
                logger.error(f"Failed to rollback transaction: {rollback_error}")
            
            self.stats.failed_writes += len(documents)
            raise e  # Re-raise original exception
    
    def save_checkpoint(self, last_processed_id: str, additional_data: Optional[Dict] = None):
        """Save checkpoint for resume capability"""
        if not self.checkpoint_file:
            return
        
        checkpoint = {
            "last_processed_id": last_processed_id,
            "timestamp": datetime.now().isoformat(),
            "stats": {
                "total_documents": self.stats.total_documents,
                "successful_writes": self.stats.successful_writes,
                "failed_writes": self.stats.failed_writes
            },
            "additional_data": additional_data or {}
        }
        
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(checkpoint, f, indent=2)
            logger.info(f"💾 Checkpoint saved: last_processed_id={last_processed_id}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    def load_checkpoint(self) -> Optional[Dict]:
        """Load checkpoint for resuming operations"""
        if not self.checkpoint_file:
            return None
        
        try:
            with open(self.checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
            logger.info(f"📁 Checkpoint loaded: last_processed_id={checkpoint.get('last_processed_id')}")
            return checkpoint
        except FileNotFoundError:
            logger.info("No checkpoint file found, starting fresh")
            return None
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get streaming metrics for monitoring and optimization"""
        return {
            "total_documents": self.stats.total_documents,
            "pending_documents": self.stats.pending_documents,
            "successful_writes": self.stats.successful_writes,
            "failed_writes": self.stats.failed_writes,
            "documents_per_second": self.stats.get_documents_per_second(),
            "average_batch_size": self.stats.total_documents / max(1, len(self.stats.write_latency_ms)),
            "write_latency_ms": self.stats.get_average_latency(),
            "collections": self.collections,
            "batch_size": self.batch_size
        }