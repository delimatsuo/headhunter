#!/usr/bin/env python3
"""
PgVectorStore - Cloud SQL pgvector client for candidate embeddings
PRD Reference: Lines 141, 143 - Embedding worker with pgvector and idempotent upserts

This module provides an async interface to PostgreSQL with pgvector extension
for storing and searching candidate embeddings in Cloud SQL.
"""
import asyncio
import asyncpg
import numpy as np
import logging
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import os
from contextlib import asynccontextmanager


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EmbeddingRecord:
    """Data class for embedding records with validation."""
    candidate_id: str
    embedding: List[float]
    model_version: str = "vertex-ai-textembedding-gecko"
    chunk_type: str = "full_profile"
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate embedding dimensions and format."""
        if not self.embedding:
            raise ValueError("Embedding cannot be empty")
        
        if len(self.embedding) != 768:
            raise ValueError(f"Embedding must be 768-dimensional, got {len(self.embedding)}")
        
        if not all(isinstance(x, (int, float)) for x in self.embedding):
            raise ValueError("All embedding values must be numeric")
        
        # Normalize to ensure proper vector format
        self.embedding = [float(x) for x in self.embedding]
        
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return asdict(self)


@dataclass 
class SearchResult:
    """Data class for similarity search results."""
    candidate_id: str
    similarity: float
    metadata: Dict[str, Any]
    model_version: str
    chunk_type: str


class PgVectorStore:
    """
    Async PostgreSQL client with pgvector for candidate embeddings.
    
    Provides idempotent upsert operations as specified in PRD line 143
    and optimized similarity search for semantic candidate matching.
    """
    
    def __init__(self, connection_string: str, pool_size: int = 10):
        """
        Initialize PgVectorStore with database connection.
        
        Args:
            connection_string: PostgreSQL connection string with pgvector support
            pool_size: Maximum number of database connections in pool
        """
        self.connection_string = connection_string
        self.pool_size = pool_size
        self.pool: Optional[asyncpg.Pool] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize database connection pool and ensure schema exists."""
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=1,
                max_size=self.pool_size,
                command_timeout=60,
                server_settings={
                    'application_name': 'headhunter-pgvector-client',
                    'search_path': 'public'
                }
            )
            
            # Verify pgvector extension and schema
            async with self.pool.acquire() as conn:
                # Check pgvector extension
                extensions = await conn.fetch(
                    "SELECT extname FROM pg_extension WHERE extname = 'vector'"
                )
                if not extensions:
                    logger.warning("pgvector extension not found - attempting to create")
                    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                
                # Check required tables exist
                tables = await conn.fetch("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('candidate_embeddings', 'embedding_metadata')
                """)
                
                if len(tables) < 2:
                    logger.warning("Required tables not found - please run pgvector_schema.sql")
            
            self._initialized = True
            logger.info(f"PgVectorStore initialized with pool size {self.pool_size}")
            
        except Exception as e:
            logger.error(f"Failed to initialize PgVectorStore: {e}")
            raise
    
    async def close(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            self._initialized = False
            logger.info("PgVectorStore connection pool closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Context manager for database connections."""
        if not self._initialized:
            await self.initialize()
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def store_embedding(
        self,
        candidate_id: str,
        embedding: List[float],
        model_version: str = "vertex-ai-textembedding-gecko",
        chunk_type: str = "full_profile",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a candidate embedding with idempotent upsert (PRD line 143).
        
        Args:
            candidate_id: Unique candidate identifier
            embedding: 768-dimensional embedding vector
            model_version: Embedding model version
            chunk_type: Type of content embedded (full_profile, skills, etc.)
            metadata: Additional metadata for the embedding
            
        Returns:
            UUID of the stored embedding record
        """
        record = EmbeddingRecord(
            candidate_id=candidate_id,
            embedding=embedding,
            model_version=model_version,
            chunk_type=chunk_type,
            metadata=metadata or {}
        )
        
        async with self.get_connection() as conn:
            try:
                # Use the database function for idempotent upsert
                result_id = await conn.fetchval(
                    """SELECT upsert_candidate_embedding($1, $2, $3, $4, $5)""",
                    candidate_id,
                    embedding,  # pgvector handles the array conversion
                    model_version,
                    chunk_type,
                    json.dumps(metadata) if metadata else None
                )
                
                logger.debug(f"Stored embedding for candidate {candidate_id} with ID {result_id}")
                return str(result_id)
                
            except Exception as e:
                logger.error(f"Failed to store embedding for candidate {candidate_id}: {e}")
                raise
    
    async def batch_store_embeddings(
        self,
        embeddings: List[EmbeddingRecord],
        batch_size: int = 100
    ) -> List[str]:
        """
        Store multiple embeddings in batches for performance.
        
        Args:
            embeddings: List of EmbeddingRecord objects
            batch_size: Number of embeddings to process per batch
            
        Returns:
            List of UUIDs for stored embeddings
        """
        if not embeddings:
            return []
        
        # Validate all embeddings first
        for record in embeddings:
            if not isinstance(record, EmbeddingRecord):
                raise ValueError("All items must be EmbeddingRecord instances")
        
        result_ids = []
        
        async with self.get_connection() as conn:
            async with conn.transaction():
                for i in range(0, len(embeddings), batch_size):
                    batch = embeddings[i:i + batch_size]
                    
                    # Use prepared statement for better performance
                    batch_ids = await conn.fetch(
                        """SELECT upsert_candidate_embedding($1, $2, $3, $4, $5) AS id""",
                        *[(
                            record.candidate_id,
                            record.embedding,
                            record.model_version,
                            record.chunk_type,
                            json.dumps(record.metadata) if record.metadata else None
                        ) for record in batch]
                    )
                    
                    result_ids.extend([str(row['id']) for row in batch_ids])
                    
                    logger.info(f"Batch stored {len(batch)} embeddings (batch {i//batch_size + 1})")
        
        logger.info(f"Successfully stored {len(result_ids)} embeddings in {len(embeddings)//batch_size + 1} batches")
        return result_ids
    
    async def similarity_search(
        self,
        query_embedding: List[float],
        similarity_threshold: float = 0.7,
        max_results: int = 10,
        model_version: Optional[str] = None,
        chunk_type: str = "full_profile"
    ) -> List[SearchResult]:
        """
        Perform semantic similarity search using cosine distance.
        
        Args:
            query_embedding: 768-dimensional query embedding
            similarity_threshold: Minimum similarity score (0-1)
            max_results: Maximum number of results to return
            model_version: Filter by embedding model version
            chunk_type: Filter by chunk type
            
        Returns:
            List of SearchResult objects ordered by similarity
        """
        if len(query_embedding) != 768:
            raise ValueError(f"Query embedding must be 768-dimensional, got {len(query_embedding)}")
        
        async with self.get_connection() as conn:
            try:
                # Use the database function for optimized search
                results = await conn.fetch(
                    """SELECT * FROM similarity_search($1, $2, $3, $4, $5)""",
                    query_embedding,
                    similarity_threshold,
                    max_results,
                    model_version,
                    chunk_type
                )
                
                search_results = [
                    SearchResult(
                        candidate_id=row['candidate_id'],
                        similarity=float(row['similarity']),
                        metadata=row['metadata'] or {},
                        model_version=row['model_version'],
                        chunk_type=row['chunk_type']
                    )
                    for row in results
                ]
                
                logger.info(f"Similarity search returned {len(search_results)} results")
                return search_results
                
            except Exception as e:
                logger.error(f"Similarity search failed: {e}")
                raise
    
    async def get_candidate_embeddings(
        self,
        candidate_id: str,
        model_version: Optional[str] = None
    ) -> List[EmbeddingRecord]:
        """
        Retrieve all embeddings for a specific candidate.
        
        Args:
            candidate_id: Unique candidate identifier
            model_version: Optional filter by model version
            
        Returns:
            List of EmbeddingRecord objects
        """
        async with self.get_connection() as conn:
            query = """
                SELECT candidate_id, embedding, model_version, chunk_type, metadata
                FROM candidate_embeddings 
                WHERE candidate_id = $1
            """
            params = [candidate_id]
            
            if model_version:
                query += " AND model_version = $2"
                params.append(model_version)
            
            query += " ORDER BY created_at DESC"
            
            rows = await conn.fetch(query, *params)
            
            return [
                EmbeddingRecord(
                    candidate_id=row['candidate_id'],
                    embedding=row['embedding'],
                    model_version=row['model_version'],
                    chunk_type=row['chunk_type'],
                    metadata=row['metadata'] or {}
                )
                for row in rows
            ]
    
    async def delete_candidate_embeddings(self, candidate_id: str) -> int:
        """
        Delete all embeddings for a candidate.
        
        Args:
            candidate_id: Unique candidate identifier
            
        Returns:
            Number of embeddings deleted
        """
        async with self.get_connection() as conn:
            async with conn.transaction():
                # Delete from both tables
                embedding_result = await conn.execute(
                    "DELETE FROM candidate_embeddings WHERE candidate_id = $1",
                    candidate_id
                )
                
                metadata_result = await conn.execute(
                    "DELETE FROM embedding_metadata WHERE candidate_id = $1", 
                    candidate_id
                )
                
                # Parse deletion count from result
                deleted_count = int(embedding_result.split()[-1]) if embedding_result.split() else 0
                
                logger.info(f"Deleted {deleted_count} embeddings for candidate {candidate_id}")
                return deleted_count
    
    async def get_embedding_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored embeddings.
        
        Returns:
            Dictionary with embedding statistics
        """
        async with self.get_connection() as conn:
            # Use the database views for statistics
            embedding_stats = await conn.fetch("SELECT * FROM embedding_stats")
            processing_stats = await conn.fetch("SELECT * FROM processing_stats")
            
            total_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT candidate_id) as total_candidates,
                    COUNT(*) as total_embeddings,
                    MAX(updated_at) as last_updated
                FROM candidate_embeddings
            """)
            
            return {
                'total_candidates': total_stats['total_candidates'],
                'total_embeddings': total_stats['total_embeddings'], 
                'last_updated': total_stats['last_updated'].isoformat() if total_stats['last_updated'] else None,
                'model_stats': [dict(row) for row in embedding_stats],
                'processing_stats': [dict(row) for row in processing_stats]
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on database connection and pgvector functionality.
        
        Returns:
            Health check results
        """
        health = {
            'status': 'unknown',
            'database_connected': False,
            'pgvector_available': False,
            'tables_exist': False,
            'indexes_exist': False,
            'connection_pool_size': 0,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            async with self.get_connection() as conn:
                # Check basic connection
                await conn.fetchval("SELECT 1")
                health['database_connected'] = True
                
                # Check pgvector extension
                extension = await conn.fetchval(
                    "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
                )
                health['pgvector_available'] = bool(extension)
                
                # Check required tables
                tables = await conn.fetch("""
                    SELECT COUNT(*) as count FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('candidate_embeddings', 'embedding_metadata')
                """)
                health['tables_exist'] = tables[0]['count'] == 2
                
                # Check vector indexes
                indexes = await conn.fetch("""
                    SELECT COUNT(*) as count FROM pg_indexes 
                    WHERE tablename = 'candidate_embeddings'
                    AND indexname LIKE '%vector%'
                """)
                health['indexes_exist'] = indexes[0]['count'] > 0
                
                health['connection_pool_size'] = self.pool.get_size() if self.pool else 0
                
                if all([
                    health['database_connected'],
                    health['pgvector_available'], 
                    health['tables_exist']
                ]):
                    health['status'] = 'healthy'
                else:
                    health['status'] = 'degraded'
                    
        except Exception as e:
            health['status'] = 'unhealthy'
            health['error'] = str(e)
            logger.error(f"Health check failed: {e}")
        
        return health


# Utility functions for common operations
async def create_pgvector_store(
    connection_string: Optional[str] = None,
    pool_size: int = 10
) -> PgVectorStore:
    """
    Factory function to create and initialize PgVectorStore.
    
    Args:
        connection_string: PostgreSQL connection string or None to use environment
        pool_size: Database connection pool size
        
    Returns:
        Initialized PgVectorStore instance
    """
    if connection_string is None:
        # Try to get from environment variables
        connection_string = os.getenv('PGVECTOR_CONNECTION_STRING')
        
        if connection_string is None:
            # Build from individual components
            host = os.getenv('PGVECTOR_HOST', 'localhost')
            port = os.getenv('PGVECTOR_PORT', '5432')
            database = os.getenv('PGVECTOR_DATABASE', 'headhunter')
            user = os.getenv('PGVECTOR_USER', 'postgres')
            password = os.getenv('PGVECTOR_PASSWORD', '')
            
            connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    
    store = PgVectorStore(connection_string, pool_size)
    await store.initialize()
    return store


# Example usage and testing
async def main():
    """Example usage of PgVectorStore."""
    # This would typically use environment variables for production
    connection_string = "postgresql://postgres:password@localhost:5432/headhunter_test"
    
    store = PgVectorStore(connection_string)
    
    try:
        await store.initialize()
        
        # Health check
        health = await store.health_check()
        print(f"Health check: {health}")
        
        # Store sample embedding
        sample_embedding = np.random.rand(768).tolist()
        embedding_id = await store.store_embedding(
            candidate_id="test_candidate_001",
            embedding=sample_embedding,
            metadata={"source": "test", "quality": 0.95}
        )
        print(f"Stored embedding with ID: {embedding_id}")
        
        # Perform similarity search
        query_embedding = np.random.rand(768).tolist()
        results = await store.similarity_search(
            query_embedding=query_embedding,
            max_results=5
        )
        print(f"Found {len(results)} similar candidates")
        
        # Get statistics
        stats = await store.get_embedding_stats()
        print(f"Embedding stats: {stats}")
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
    
    finally:
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())