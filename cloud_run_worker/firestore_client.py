"""
Firestore client for candidate data operations
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from .config import Config

logger = logging.getLogger(__name__)


class FirestoreClient:
    """Client for Firestore database operations"""
    
    def __init__(self, config: Config):
        self.config = config
        self.project_id = config.project_id
        self.collection_name = config.firestore_collection
        self.timeout = config.firestore_timeout
        
        self.db: Optional[firestore.Client] = None
        
    async def initialize(self):
        """Initialize Firestore client"""
        try:
            self.db = firestore.Client(project=self.project_id)
            logger.info(f"Firestore client initialized for project: {self.project_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore client: {e}")
            raise
    
    async def shutdown(self):
        """Cleanup Firestore client"""
        if self.db:
            self.db.close()
            logger.info("Firestore client shutdown complete")
    
    async def get_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve candidate document from Firestore
        
        Args:
            candidate_id: ID of candidate to retrieve
            
        Returns:
            Dict[str, Any]: Candidate data or None if not found
        """
        try:
            if not self.db:
                raise Exception("Firestore client not initialized")
            
            # Get document reference
            doc_ref = self.db.collection(self.collection_name).document(candidate_id)
            
            # Execute get operation in thread pool to avoid blocking
            doc = await asyncio.get_event_loop().run_in_executor(
                None, 
                doc_ref.get
            )
            
            if doc.exists:
                data = doc.to_dict()
                logger.debug(f"Retrieved candidate: {candidate_id}")
                return data
            else:
                logger.warning(f"Candidate not found: {candidate_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get candidate {candidate_id}: {e}")
            raise
    
    async def update_candidate(self, candidate_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update candidate document in Firestore
        
        Args:
            candidate_id: ID of candidate to update
            update_data: Data to update
            
        Returns:
            bool: True if update was successful
        """
        try:
            if not self.db:
                raise Exception("Firestore client not initialized")
            
            # Add update timestamp
            update_data["updated_at"] = datetime.now()
            
            # Get document reference
            doc_ref = self.db.collection(self.collection_name).document(candidate_id)
            
            # Execute update operation in thread pool
            await asyncio.get_event_loop().run_in_executor(
                None,
                doc_ref.update,
                update_data
            )
            
            logger.debug(f"Updated candidate: {candidate_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update candidate {candidate_id}: {e}")
            return False
    
    async def create_candidate(self, candidate_id: str, candidate_data: Dict[str, Any]) -> bool:
        """
        Create new candidate document in Firestore
        
        Args:
            candidate_id: ID for new candidate
            candidate_data: Candidate information
            
        Returns:
            bool: True if creation was successful
        """
        try:
            if not self.db:
                raise Exception("Firestore client not initialized")
            
            # Add creation timestamp
            candidate_data["created_at"] = datetime.now()
            candidate_data["updated_at"] = datetime.now()
            
            # Get document reference
            doc_ref = self.db.collection(self.collection_name).document(candidate_id)
            
            # Execute set operation in thread pool
            await asyncio.get_event_loop().run_in_executor(
                None,
                doc_ref.set,
                candidate_data
            )
            
            logger.info(f"Created candidate: {candidate_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create candidate {candidate_id}: {e}")
            return False
    
    async def get_candidates_by_org(self, org_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve candidates for a specific organization
        
        Args:
            org_id: Organization ID
            limit: Maximum number of candidates to return
            
        Returns:
            List[Dict[str, Any]]: List of candidate documents
        """
        try:
            if not self.db:
                raise Exception("Firestore client not initialized")
            
            # Build query
            collection_ref = self.db.collection(self.collection_name)
            query = collection_ref.where(
                filter=FieldFilter("org_id", "==", org_id)
            ).limit(limit)
            
            # Execute query in thread pool
            docs = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: list(query.stream())
            )
            
            # Convert to list of dictionaries
            candidates = []
            for doc in docs:
                data = doc.to_dict()
                data["candidate_id"] = doc.id
                candidates.append(data)
            
            logger.debug(f"Retrieved {len(candidates)} candidates for org: {org_id}")
            return candidates
            
        except Exception as e:
            logger.error(f"Failed to get candidates for org {org_id}: {e}")
            return []
    
    async def get_candidates_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve candidates by processing status
        
        Args:
            status: Processing status to filter by
            limit: Maximum number of candidates to return
            
        Returns:
            List[Dict[str, Any]]: List of candidate documents
        """
        try:
            if not self.db:
                raise Exception("Firestore client not initialized")
            
            # Build query
            collection_ref = self.db.collection(self.collection_name)
            query = collection_ref.where(
                filter=FieldFilter("status", "==", status)
            ).limit(limit)
            
            # Execute query in thread pool
            docs = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: list(query.stream())
            )
            
            # Convert to list of dictionaries
            candidates = []
            for doc in docs:
                data = doc.to_dict()
                data["candidate_id"] = doc.id
                candidates.append(data)
            
            logger.debug(f"Retrieved {len(candidates)} candidates with status: {status}")
            return candidates
            
        except Exception as e:
            logger.error(f"Failed to get candidates by status {status}: {e}")
            return []
    
    async def batch_update_candidates(self, updates: List[Dict[str, Any]]) -> int:
        """
        Perform batch updates on multiple candidates
        
        Args:
            updates: List of update operations, each containing 'candidate_id' and 'data'
            
        Returns:
            int: Number of successful updates
        """
        try:
            if not self.db:
                raise Exception("Firestore client not initialized")
            
            # Firestore batch limit is 500 operations
            batch_size = 500
            successful_updates = 0
            
            for i in range(0, len(updates), batch_size):
                batch_updates = updates[i:i + batch_size]
                
                # Create batch
                batch = self.db.batch()
                
                for update in batch_updates:
                    candidate_id = update["candidate_id"]
                    update_data = update["data"]
                    update_data["updated_at"] = datetime.now()
                    
                    doc_ref = self.db.collection(self.collection_name).document(candidate_id)
                    batch.update(doc_ref, update_data)
                
                # Execute batch in thread pool
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    batch.commit
                )
                
                successful_updates += len(batch_updates)
                logger.debug(f"Batch updated {len(batch_updates)} candidates")
            
            logger.info(f"Successfully batch updated {successful_updates} candidates")
            return successful_updates
            
        except Exception as e:
            logger.error(f"Failed to batch update candidates: {e}")
            return 0
    
    async def delete_candidate(self, candidate_id: str) -> bool:
        """
        Delete candidate document from Firestore
        
        Args:
            candidate_id: ID of candidate to delete
            
        Returns:
            bool: True if deletion was successful
        """
        try:
            if not self.db:
                raise Exception("Firestore client not initialized")
            
            # Get document reference
            doc_ref = self.db.collection(self.collection_name).document(candidate_id)
            
            # Execute delete operation in thread pool
            await asyncio.get_event_loop().run_in_executor(
                None,
                doc_ref.delete
            )
            
            logger.info(f"Deleted candidate: {candidate_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete candidate {candidate_id}: {e}")
            return False
    
    async def health_check(self) -> bool:
        """
        Perform health check on Firestore connection
        
        Returns:
            bool: True if Firestore is accessible
        """
        try:
            if not self.db:
                return False
            
            # Simple read operation to test connectivity
            collection_ref = self.db.collection(self.collection_name)
            query = collection_ref.limit(1)
            
            # Execute in thread pool with timeout
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: list(query.stream())
                ),
                timeout=self.timeout
            )
            
            return True
            
        except Exception as e:
            logger.warning(f"Firestore health check failed: {e}")
            return False
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics
        
        Returns:
            Dict[str, Any]: Collection statistics
        """
        try:
            if not self.db:
                raise Exception("Firestore client not initialized")
            
            collection_ref = self.db.collection(self.collection_name)
            
            # Count documents by status
            status_counts = {}
            for status in ["pending_enrichment", "enriched", "failed", "processing"]:
                query = collection_ref.where(
                    filter=FieldFilter("status", "==", status)
                )
                
                # Count documents
                docs = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda q=query: list(q.stream())
                )
                status_counts[status] = len(docs)
            
            return {
                "collection": self.collection_name,
                "status_counts": status_counts,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                "collection": self.collection_name,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }