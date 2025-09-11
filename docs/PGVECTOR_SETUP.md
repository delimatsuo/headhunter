# Cloud SQL pgvector Setup Guide

This document provides comprehensive instructions for setting up Cloud SQL with PostgreSQL and pgvector extension for the Headhunter AI recruitment system.

**PRD Reference**: Lines 141, 143 - Embedding worker with pgvector and idempotent upserts

## Overview

The pgvector setup replaces Vertex AI Vector Search with a more cost-effective and performant solution using Cloud SQL PostgreSQL with the pgvector extension for semantic candidate search.

## Architecture

```
┌─────────────────────┐    ┌────────────────────┐    ┌─────────────────────┐
│   Together AI       │    │   Cloud Functions  │    │   Cloud SQL         │
│   (Embeddings)      │───▶│   (API Gateway)    │───▶│   (pgvector)        │
└─────────────────────┘    └────────────────────┘    └─────────────────────┘
         │                           │                          │
         ▼                           ▼                          ▼
┌─────────────────────┐    ┌────────────────────┐    ┌─────────────────────┐
│   Cloud Run         │    │   Firebase          │    │   Vector Indexes    │
│   (Batch Worker)    │    │   (Metadata)        │    │   (IVFFlat/HNSW)    │
└─────────────────────┘    └────────────────────┘    └─────────────────────┘
```

## Prerequisites

1. **GCP Project** with billing enabled
2. **Cloud SQL Admin API** enabled
3. **gcloud CLI** installed and authenticated
4. **Cloud SQL Proxy** for secure connections
5. **Python 3.9+** with required dependencies

## Quick Start

### 1. Deploy Cloud SQL Instance

```bash
# Deploy complete Cloud SQL pgvector setup
python3 scripts/deploy_pgvector.py YOUR_PROJECT_ID
```

This script will:
- Create Cloud SQL PostgreSQL 15 instance
- Enable pgvector extension
- Create database and application user
- Configure networking and security
- Generate connection credentials

### 2. Install Dependencies

```bash
# Install required Python packages
pip install asyncpg pgvector numpy SQLAlchemy psycopg2-binary
```

### 3. Deploy Database Schema

```bash
# Start Cloud SQL Proxy
cloud_sql_proxy -instances=PROJECT:REGION:INSTANCE=tcp:5432 &

# Deploy pgvector schema
psql -h localhost -p 5432 -U headhunter_app -d headhunter -f scripts/pgvector_schema.sql
```

### 4. Test Connection

```bash
# Test pgvector functionality
python3 scripts/pgvector_store.py
```

## Detailed Setup

### Step 1: Cloud SQL Instance Configuration

#### Create Instance with pgvector Support

```bash
gcloud sql instances create headhunter-pgvector \
    --database-version=POSTGRES_15 \
    --tier=db-custom-2-7680 \
    --region=us-central1 \
    --storage-type=SSD \
    --storage-size=100GB \
    --storage-auto-increase \
    --backup-start-time=03:00 \
    --backup-location=us \
    --database-flags=shared_preload_libraries=vector \
    --deletion-protection
```

#### Instance Specifications
- **Version**: PostgreSQL 15 (required for pgvector)
- **Tier**: db-custom-2-7680 (2 vCPUs, 7.5GB RAM)
- **Storage**: 100GB SSD with auto-increase
- **Flags**: `shared_preload_libraries=vector`

### Step 2: Database and User Setup

```bash
# Create database
gcloud sql databases create headhunter --instance=headhunter-pgvector

# Create application user
gcloud sql users create headhunter_app \
    --instance=headhunter-pgvector \
    --password=SECURE_PASSWORD
```

### Step 3: Schema Deployment

The schema includes:
- **candidate_embeddings**: Main table for vector storage
- **embedding_metadata**: Processing status and metadata
- **Vector indexes**: IVFFlat for performance, optional HNSW for accuracy
- **Functions**: similarity_search, upsert_candidate_embedding
- **Views**: Statistics and monitoring

Key features:
- **768-dimensional vectors** (compatible with most embedding models)
- **Idempotent upserts** (PRD requirement line 143)
- **Multiple chunk types** (full_profile, skills, experience)
- **Metadata storage** with JSONB
- **Performance optimizations** with appropriate indexes

### Step 4: Connection Configuration

#### Environment Variables

```bash
export PGVECTOR_CONNECTION_STRING="postgresql://headhunter_app:PASSWORD@localhost:5432/headhunter"
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

#### Cloud SQL Proxy Setup

```bash
# Download Cloud SQL Proxy
curl -o cloud_sql_proxy https://dl.google.com/cloudsql/cloud_sql_proxy.darwin.amd64
chmod +x cloud_sql_proxy

# Start proxy (replace with your connection name)
./cloud_sql_proxy -instances=PROJECT:REGION:INSTANCE=tcp:5432
```

## Usage Examples

### Basic Operations

```python
from scripts.pgvector_store import create_pgvector_store
import numpy as np

# Initialize store
store = await create_pgvector_store()

# Store embedding
embedding_id = await store.store_embedding(
    candidate_id="candidate_001",
    embedding=np.random.rand(768).tolist(),
    metadata={"source": "together_ai", "quality": 0.95}
)

# Similarity search
results = await store.similarity_search(
    query_embedding=np.random.rand(768).tolist(),
    similarity_threshold=0.8,
    max_results=10
)

# Batch operations
embeddings = [
    EmbeddingRecord(
        candidate_id=f"candidate_{i}",
        embedding=np.random.rand(768).tolist(),
        metadata={"batch": "migration_001"}
    ) for i in range(100)
]

await store.batch_store_embeddings(embeddings)
```

### Integration with Existing Pipeline

```python
# In your Together AI processor
from scripts.pgvector_store import create_pgvector_store

async def process_and_store_embedding(candidate_data):
    # Generate embedding with Together AI
    embedding = await generate_together_ai_embedding(candidate_data)
    
    # Store in pgvector
    store = await create_pgvector_store()
    await store.store_embedding(
        candidate_id=candidate_data['id'],
        embedding=embedding,
        model_version="together-ai-embeddings-v1",
        metadata={
            "processed_at": datetime.utcnow().isoformat(),
            "source": "together_ai_processor"
        }
    )
```

## Migration from Firestore

### Automated Migration

```bash
# Dry run to validate data
python3 scripts/migrate_firestore_to_pgvector.py --dry-run

# Full migration
python3 scripts/migrate_firestore_to_pgvector.py
```

### Migration Features

- **Automatic discovery** of embedding collections
- **Data validation** (dimension checks, format validation)
- **Batch processing** for performance
- **Idempotent operations** (safe to re-run)
- **Detailed reporting** with statistics and errors
- **Multiple document formats** supported

### Migration Report Example

```
Total embeddings processed: 29,847
Successfully migrated: 29,203 (97.8%)
Validation failures: 644 (2.2%)
Duration: 142.5 seconds
Throughput: 209.4 embeddings/second
```

## Performance Optimization

### Index Configuration

The schema includes optimized indexes:

```sql
-- IVFFlat index (faster, approximate)
CREATE INDEX idx_candidate_embeddings_ivfflat 
ON candidate_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- HNSW index (slower, exact) - optional
CREATE INDEX idx_candidate_embeddings_hnsw 
ON candidate_embeddings 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### Query Performance

- **IVFFlat Index**: ~50ms for 10k vectors
- **HNSW Index**: ~25ms for 10k vectors (higher memory usage)
- **Batch Inserts**: >1000 embeddings/second
- **Connection Pooling**: 10-20 connections recommended

### Tuning Parameters

```sql
-- Adjust based on dataset size
-- lists = sqrt(total_rows) for IVFFlat
-- m = 16, ef_construction = 64 for HNSW

-- Memory settings for large datasets
SET maintenance_work_mem = '2GB';
SET max_parallel_workers = 4;
```

## Monitoring and Maintenance

### Health Checks

```python
# Check pgvector health
health = await store.health_check()
print(f"Status: {health['status']}")
print(f"Total embeddings: {health['total_embeddings']}")
```

### Statistics Views

```sql
-- Embedding distribution
SELECT * FROM embedding_stats;

-- Processing status
SELECT * FROM processing_stats;

-- Query performance
EXPLAIN ANALYZE 
SELECT candidate_id, 1 - (embedding <=> $1) as similarity
FROM candidate_embeddings 
ORDER BY embedding <=> $1 
LIMIT 10;
```

### Backup and Recovery

```bash
# Automated backups (configured during instance creation)
gcloud sql backups list --instance=headhunter-pgvector

# Manual backup
gcloud sql backups create --instance=headhunter-pgvector

# Point-in-time recovery available for 7 days
```

## Security Configuration

### Network Security

```bash
# Private IP configuration (recommended)
gcloud sql instances patch headhunter-pgvector \
    --network=default \
    --no-assign-ip

# Authorized networks (for development)
gcloud sql instances patch headhunter-pgvector \
    --authorized-networks=YOUR_IP/32
```

### Access Control

```sql
-- Application user with minimal privileges
GRANT SELECT, INSERT, UPDATE, DELETE ON candidate_embeddings TO headhunter_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON embedding_metadata TO headhunter_app;
GRANT EXECUTE ON FUNCTION similarity_search TO headhunter_app;
GRANT EXECUTE ON FUNCTION upsert_candidate_embedding TO headhunter_app;
```

## Troubleshooting

### Common Issues

1. **pgvector extension not found**
   ```sql
   CREATE EXTENSION vector;
   ```

2. **Connection timeouts**
   - Check Cloud SQL Proxy status
   - Verify network connectivity
   - Increase connection timeout

3. **Index not being used**
   ```sql
   ANALYZE candidate_embeddings;
   REINDEX INDEX idx_candidate_embeddings_ivfflat;
   ```

4. **Memory issues with large datasets**
   - Increase instance memory
   - Tune index parameters
   - Use batch operations

### Performance Issues

1. **Slow similarity searches**
   - Check if indexes are being used (EXPLAIN ANALYZE)
   - Increase IVFFlat lists parameter
   - Consider HNSW index for exact searches

2. **Slow insertions**
   - Use batch operations
   - Increase connection pool size
   - Disable indexes during bulk loads

### Monitoring Queries

```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch 
FROM pg_stat_user_indexes 
WHERE schemaname = 'public';

-- Query performance
SELECT query, mean_exec_time, calls, total_exec_time 
FROM pg_stat_statements 
WHERE query LIKE '%embedding%' 
ORDER BY mean_exec_time DESC;
```

## Cost Optimization

### Instance Sizing

- **Development**: db-custom-1-3840 (1 vCPU, 3.75GB RAM)
- **Production**: db-custom-2-7680 (2 vCPUs, 7.5GB RAM)  
- **High-throughput**: db-custom-4-15360 (4 vCPUs, 15GB RAM)

### Storage Management

- Start with 100GB, enable auto-increase
- Monitor storage growth patterns
- Archive old embeddings if not needed

### Connection Management

- Use connection pooling (pgbouncer/Cloud SQL Proxy)
- Monitor active connections
- Scale connections based on workload

## Integration with Cloud Functions

### Search API Example

```javascript
// Cloud Function for semantic search
const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.PGVECTOR_CONNECTION_STRING,
  max: 5
});

exports.semanticSearch = async (req, res) => {
  const { query_embedding, max_results = 10 } = req.body;
  
  const client = await pool.connect();
  try {
    const result = await client.query(
      'SELECT * FROM similarity_search($1, 0.7, $2)',
      [query_embedding, max_results]
    );
    
    res.json({ results: result.rows });
  } finally {
    client.release();
  }
};
```

## Next Steps

1. **Deploy to Production**: Use the deployment script with your GCP project
2. **Migrate Existing Data**: Run the Firestore migration script
3. **Update Application**: Integrate pgvector_store.py into your pipeline
4. **Monitor Performance**: Set up monitoring and alerting
5. **Scale as Needed**: Adjust instance size based on usage patterns

## Support and Resources

- **pgvector Documentation**: https://github.com/pgvector/pgvector
- **Cloud SQL Documentation**: https://cloud.google.com/sql/docs
- **PostgreSQL Performance**: https://wiki.postgresql.org/wiki/Performance_Optimization
- **Vector Database Best Practices**: https://www.pinecone.io/learn/vector-database/

For issues specific to this implementation, check the logs in:
- Cloud SQL instance logs
- Cloud Functions logs
- Application logs in Cloud Logging