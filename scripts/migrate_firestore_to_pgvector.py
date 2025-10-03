#!/usr/bin/env python3
"""
Migration script: Firestore embeddings to Cloud SQL pgvector
PRD Reference: Lines 141, 143 - Migration from Vertex AI Vector Search to pgvector

This script migrates existing candidate embeddings from Firestore to Cloud SQL pgvector
while maintaining data integrity and implementing idempotent operations.
"""
import asyncio
import os
import logging
from typing import List, Dict, Any
from datetime import datetime, timezone
import numpy as np

# Standard library imports
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Try importing Firebase (available in existing codebase)
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from google.cloud import firestore as firestore_client
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

# Try importing pgvector store (may fail if asyncpg not installed)
try:
    from scripts.pgvector_store import PgVectorStore, EmbeddingRecord, create_pgvector_store
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FirestoreToPgVectorMigrator:
    """Migrate candidate embeddings from Firestore to Cloud SQL pgvector."""
    
    def __init__(self, project_id: str, pgvector_connection_string: str):
        """
        Initialize migrator with Firebase and pgvector connections.
        
        Args:
            project_id: GCP project ID for Firestore
            pgvector_connection_string: PostgreSQL connection string
        """
        self.project_id = project_id
        self.pgvector_connection_string = pgvector_connection_string
        self.firestore_client = None
        self.pgvector_store = None
        
    async def initialize(self):
        """Initialize Firebase and pgvector connections."""
        # Initialize Firebase
        if not firebase_admin._apps:
            # Use default credentials or service account key
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {
                'projectId': self.project_id
            })
        
        self.firestore_client = firestore.client()
        logger.info("Firestore client initialized")
        
        # Initialize pgvector store
        if PGVECTOR_AVAILABLE:
            self.pgvector_store = await create_pgvector_store(
                self.pgvector_connection_string, 
                pool_size=20  # Higher pool for migration
            )
            logger.info("PgVector store initialized")
        else:
            logger.warning("PgVector store not available - will generate migration data only")
    
    async def close(self):
        """Close connections."""
        if self.pgvector_store:
            await self.pgvector_store.close()
    
    def get_firestore_embeddings(self, batch_size: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve embeddings from Firestore in batches.
        
        Args:
            batch_size: Number of documents to fetch per batch
            
        Yields:
            Batches of embedding documents
        """
        # Check common collection names for embeddings
        collection_names = [
            'candidate_embeddings',
            'embeddings',
            'enriched_profiles',  # May contain embeddings
            'candidates'  # May contain embeddings as fields
        ]
        
        all_embeddings = []
        
        for collection_name in collection_names:
            try:
                collection_ref = self.firestore_client.collection(collection_name)
                
                # Check if collection exists and has documents
                docs = list(collection_ref.limit(1).stream())
                if not docs:
                    logger.info(f"Collection '{collection_name}' is empty or doesn't exist")
                    continue
                
                logger.info(f"Processing collection: {collection_name}")
                
                # Stream all documents in batches
                query = collection_ref
                last_doc = None
                
                while True:
                    if last_doc:
                        query = collection_ref.order_by('__name__').start_after(last_doc)
                    else:
                        query = collection_ref.order_by('__name__')
                    
                    docs = list(query.limit(batch_size).stream())
                    
                    if not docs:
                        break
                    
                    batch_embeddings = []
                    for doc in docs:
                        data = doc.to_dict()
                        
                        # Extract embedding data based on document structure
                        embedding_data = self._extract_embedding_from_document(doc.id, data)
                        if embedding_data:
                            batch_embeddings.extend(embedding_data)
                    
                    all_embeddings.extend(batch_embeddings)
                    last_doc = docs[-1]
                    
                    logger.info(f"Processed {len(batch_embeddings)} embeddings from {collection_name}")
                
            except Exception as e:
                logger.error(f"Error processing collection '{collection_name}': {e}")
                continue
        
        logger.info(f"Total embeddings found: {len(all_embeddings)}")
        
        # Yield in batches
        for i in range(0, len(all_embeddings), batch_size):
            yield all_embeddings[i:i + batch_size]
    
    def _extract_embedding_from_document(self, doc_id: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract embedding data from a Firestore document.
        
        Args:
            doc_id: Document ID
            data: Document data
            
        Returns:
            List of embedding records (may be multiple per document)
        """
        embeddings = []
        
        # Pattern 1: Direct embedding field
        if 'embedding' in data and isinstance(data['embedding'], list):
            embeddings.append({
                'candidate_id': doc_id,
                'embedding': data['embedding'],
                'model_version': data.get('model_version', 'vertex-ai-textembedding-gecko'),
                'chunk_type': data.get('chunk_type', 'full_profile'),
                'metadata': {
                    'source': 'firestore',
                    'migrated_at': datetime.now(timezone.utc).isoformat(),
                    'original_doc_id': doc_id,
                    **{k: v for k, v in data.items() if k not in ['embedding', 'model_version', 'chunk_type']}
                }
            })
        
        # Pattern 2: Multiple embeddings in a document
        if 'embeddings' in data and isinstance(data['embeddings'], dict):
            for chunk_type, embedding_data in data['embeddings'].items():
                if isinstance(embedding_data, dict) and 'vector' in embedding_data:
                    embeddings.append({
                        'candidate_id': doc_id,
                        'embedding': embedding_data['vector'],
                        'model_version': embedding_data.get('model', 'vertex-ai-textembedding-gecko'),
                        'chunk_type': chunk_type,
                        'metadata': {
                            'source': 'firestore',
                            'migrated_at': datetime.now(timezone.utc).isoformat(),
                            'original_doc_id': doc_id,
                            'confidence': embedding_data.get('confidence'),
                            **{k: v for k, v in data.items() if k != 'embeddings'}
                        }
                    })
        
        # Pattern 3: Vertex AI Vector Search format
        if 'vector' in data and isinstance(data['vector'], list):
            embeddings.append({
                'candidate_id': data.get('candidate_id', doc_id),
                'embedding': data['vector'],
                'model_version': data.get('model_name', 'vertex-ai-textembedding-gecko'),
                'chunk_type': 'full_profile',
                'metadata': {
                    'source': 'vertex_ai_vector_search',
                    'migrated_at': datetime.now(timezone.utc).isoformat(),
                    'original_doc_id': doc_id,
                    **{k: v for k, v in data.items() if k not in ['vector', 'candidate_id', 'model_name']}
                }
            })
        
        # Pattern 4: Nested in profile data
        if 'profile' in data and isinstance(data['profile'], dict):
            profile = data['profile']
            if 'embeddings' in profile:
                # Recursively process nested embeddings
                nested_embeddings = self._extract_embedding_from_document(doc_id, profile)
                embeddings.extend(nested_embeddings)
        
        # Validate embeddings
        valid_embeddings = []
        for embedding in embeddings:
            if self._validate_embedding(embedding):
                valid_embeddings.append(embedding)
        
        return valid_embeddings
    
    def _validate_embedding(self, embedding_data: Dict[str, Any]) -> bool:
        """Validate embedding data before migration."""
        try:
            # Check required fields
            required_fields = ['candidate_id', 'embedding', 'model_version']
            for field in required_fields:
                if field not in embedding_data:
                    logger.warning(f"Missing required field '{field}' in embedding")
                    return False
            
            # Validate embedding vector
            embedding = embedding_data['embedding']
            if not isinstance(embedding, list):
                logger.warning("Embedding is not a list")
                return False
            
            if len(embedding) != 768:
                logger.warning(f"Embedding has wrong dimension: {len(embedding)}, expected 768")
                return False
            
            # Check if all values are numeric
            if not all(isinstance(x, (int, float)) and not np.isnan(x) for x in embedding):
                logger.warning("Embedding contains non-numeric or NaN values")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error validating embedding: {e}")
            return False
    
    async def migrate_embeddings(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Migrate embeddings from Firestore to pgvector.
        
        Args:
            dry_run: If True, only validate and count embeddings without storing
            
        Returns:
            Migration statistics
        """
        stats = {
            'total_processed': 0,
            'successfully_migrated': 0,
            'validation_failures': 0,
            'storage_failures': 0,
            'duplicates_updated': 0,
            'start_time': datetime.now(timezone.utc),
            'collections_processed': [],
            'errors': []
        }
        
        try:
            # Process embeddings in batches
            for batch in self.get_firestore_embeddings(batch_size=50):
                stats['total_processed'] += len(batch)
                
                if dry_run:
                    # Just validate in dry run mode
                    for embedding_data in batch:
                        if self._validate_embedding(embedding_data):
                            stats['successfully_migrated'] += 1
                        else:
                            stats['validation_failures'] += 1
                else:
                    # Actually migrate the embeddings
                    await self._migrate_batch(batch, stats)
                
                # Log progress
                if stats['total_processed'] % 100 == 0:
                    logger.info(f"Processed {stats['total_processed']} embeddings")
        
        except Exception as e:
            logger.error(f"Migration error: {e}")
            stats['errors'].append(str(e))
        
        stats['end_time'] = datetime.now(timezone.utc)
        stats['duration_seconds'] = (stats['end_time'] - stats['start_time']).total_seconds()
        
        return stats
    
    async def _migrate_batch(self, batch: List[Dict[str, Any]], stats: Dict[str, Any]):
        """Migrate a batch of embeddings to pgvector."""
        if not PGVECTOR_AVAILABLE or not self.pgvector_store:
            logger.error("PgVector store not available for migration")
            stats['storage_failures'] += len(batch)
            return
        
        embedding_records = []
        
        for embedding_data in batch:
            try:
                # Validate before creating record
                if not self._validate_embedding(embedding_data):
                    stats['validation_failures'] += 1
                    continue
                
                # Create EmbeddingRecord
                record = EmbeddingRecord(
                    candidate_id=embedding_data['candidate_id'],
                    embedding=embedding_data['embedding'],
                    model_version=embedding_data['model_version'],
                    chunk_type=embedding_data.get('chunk_type', 'full_profile'),
                    metadata=embedding_data.get('metadata', {})
                )
                
                embedding_records.append(record)
                
            except Exception as e:
                logger.error(f"Error creating embedding record: {e}")
                stats['validation_failures'] += 1
                stats['errors'].append(str(e))
        
        # Store batch in pgvector
        if embedding_records:
            try:
                await self.pgvector_store.batch_store_embeddings(embedding_records)
                stats['successfully_migrated'] += len(embedding_records)
                
            except Exception as e:
                logger.error(f"Error storing embedding batch: {e}")
                stats['storage_failures'] += len(embedding_records)
                stats['errors'].append(str(e))
    
    def generate_migration_report(self, stats: Dict[str, Any]) -> str:
        """Generate a detailed migration report."""
        report = f"""
# Firestore to pgvector Migration Report

## Summary
- **Total embeddings processed**: {stats['total_processed']}
- **Successfully migrated**: {stats['successfully_migrated']}
- **Validation failures**: {stats['validation_failures']}
- **Storage failures**: {stats['storage_failures']}
- **Success rate**: {stats['successfully_migrated'] / max(stats['total_processed'], 1) * 100:.2f}%

## Timing
- **Start time**: {stats['start_time']}
- **End time**: {stats['end_time']}
- **Duration**: {stats['duration_seconds']:.2f} seconds
- **Throughput**: {stats['total_processed'] / max(stats['duration_seconds'], 1):.2f} embeddings/second

## Collections Processed
{chr(10).join(f"- {collection}" for collection in stats['collections_processed'])}

## Errors
{chr(10).join(f"- {error}" for error in stats['errors'][:10])}  # Show first 10 errors
{"... and more" if len(stats['errors']) > 10 else ""}

## Next Steps
1. Verify data integrity with pgvector queries
2. Test similarity search functionality
3. Update application to use pgvector instead of Firestore
4. Consider archiving Firestore embeddings after validation period
"""
        return report


async def main():
    """Main migration function."""
    # Configuration
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'your-project-id')
    pgvector_connection_string = os.getenv('PGVECTOR_CONNECTION_STRING')
    
    if not pgvector_connection_string:
        logger.error("PGVECTOR_CONNECTION_STRING environment variable not set")
        sys.exit(1)
    
    if not FIREBASE_AVAILABLE:
        logger.error("Firebase SDK not available - please install firebase-admin")
        sys.exit(1)
    
    # Parse command line arguments
    dry_run = '--dry-run' in sys.argv
    
    logger.info("Starting Firestore to pgvector migration")
    logger.info(f"Project ID: {project_id}")
    logger.info(f"Dry run mode: {dry_run}")
    
    migrator = FirestoreToPgVectorMigrator(project_id, pgvector_connection_string)
    
    try:
        await migrator.initialize()
        
        # Run migration
        stats = await migrator.migrate_embeddings(dry_run=dry_run)
        
        # Generate and save report
        report = migrator.generate_migration_report(stats)
        
        # Save report to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"migration_report_{timestamp}.md"
        
        with open(report_file, 'w') as f:
            f.write(report)
        
        logger.info(f"Migration report saved to: {report_file}")
        print(report)
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
    
    finally:
        await migrator.close()


if __name__ == "__main__":
    if len(sys.argv) < 1:
        print("Usage: python3 migrate_firestore_to_pgvector.py [--dry-run]")
        print("Environment variables required:")
        print("  GOOGLE_CLOUD_PROJECT - GCP project ID")
        print("  PGVECTOR_CONNECTION_STRING - PostgreSQL connection string")
        sys.exit(1)
    
    asyncio.run(main())