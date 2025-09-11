# PgVector Configuration Guide

This document explains how to configure and deploy the pgvector integration for the Headhunter Vector Search service.

## Environment Configuration

### Local Development

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Update the values in `.env` for your local PostgreSQL instance with pgvector extension.

### Cloud Functions Deployment

1. Update `functions/.env.yaml` with your Cloud SQL connection details.

2. For Cloud SQL Proxy connection:
   ```yaml
   PGVECTOR_HOST: /cloudsql/PROJECT_ID:REGION:INSTANCE_NAME
   PGVECTOR_SSL_MODE: disable
   ```

3. For Cloud SQL Private IP connection:
   ```yaml
   PGVECTOR_HOST: 10.x.x.x
   PGVECTOR_SSL_MODE: require
   ```

## Feature Flag Migration

The integration uses a feature flag for gradual migration from Firestore to pgvector:

- `USE_PGVECTOR=false` - Uses Firestore (default, legacy behavior)
- `USE_PGVECTOR=true` - Uses pgvector for vector storage and search

## Required Cloud SQL Setup

1. **Create Cloud SQL instance** with PostgreSQL 14+ 
2. **Enable pgvector extension**:
   ```sql
   CREATE EXTENSION vector;
   ```
3. **Run schema creation** (see `pgvector_schema.sql`)
4. **Create database functions** for optimized operations
5. **Set up proper indexes** for vector similarity search

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `USE_PGVECTOR` | Enable pgvector backend | `false` | No |
| `PGVECTOR_HOST` | Database host | `localhost` | Yes |
| `PGVECTOR_PORT` | Database port | `5432` | No |
| `PGVECTOR_DATABASE` | Database name | `headhunter` | Yes |
| `PGVECTOR_USER` | Database user | `postgres` | Yes |
| `PGVECTOR_PASSWORD` | Database password | - | Yes |
| `PGVECTOR_SSL_MODE` | SSL mode | `disable` | No |
| `PGVECTOR_MAX_CONNECTIONS` | Connection pool size | `20` | No |
| `PGVECTOR_IDLE_TIMEOUT_MILLIS` | Idle timeout | `30000` | No |

## API Compatibility

The VectorSearchService maintains full API compatibility:

- All existing endpoints work without changes
- Response formats remain identical  
- Performance improvements are transparent
- Fallback to Firestore if pgvector fails

## Health Check

The health check endpoint (`/health`) now includes pgvector status:

```json
{
  "status": "healthy",
  "embedding_service": "operational",
  "storage_connection": "connected", 
  "firestore_connection": "connected",
  "pgvector_connection": "connected",
  "pgvector_enabled": true,
  "total_embeddings": 1250
}
```

## Migration Process

1. **Deploy with feature flag disabled** (`USE_PGVECTOR=false`)
2. **Verify all functions work** with existing Firestore data
3. **Set up Cloud SQL** with pgvector schema
4. **Enable feature flag** (`USE_PGVECTOR=true`) 
5. **Monitor performance** and error rates
6. **Migrate existing embeddings** if needed (batch operation)

## Performance Benefits

- **Faster similarity search** using native vector operations
- **Reduced memory usage** by avoiding in-memory cosine calculations
- **Better scalability** with database-optimized vector indexes
- **Lower Cloud Function cold start times** with connection pooling