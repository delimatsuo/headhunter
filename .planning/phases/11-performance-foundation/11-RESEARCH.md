# Phase 11: Performance Foundation - Research

**Research Date:** 2026-01-25
**Phase Goal:** Reduce p95 search latency from 1.2s to sub-500ms through database optimization, parallel execution, and strategic caching.

## Executive Summary

To achieve sub-500ms p95 latency, Phase 11 requires **five coordinated optimizations**: pgvectorscale StreamingDiskANN indices (28x latency reduction), parallel query execution, embedding pre-computation, advanced Redis caching with proper invalidation, and connection pooling. Current architecture uses HNSW indices with sequential query execution, creating a baseline that can be dramatically improved.

**Critical Decision**: pgvectorscale's StreamingDiskANN provides 28x better latency than HNSW at 99% recall, making it the cornerstone optimization. All other optimizations build on this foundation.

---

## 1. pgvectorscale Integration (PERF-02)

### What is pgvectorscale?

pgvectorscale is a PostgreSQL extension that **complements pgvector** by introducing **StreamingDiskANN indices** - a high-performance, disk-based approximate nearest neighbor (ANN) index inspired by Microsoft's DiskANN research. It's specifically designed for production workloads with millions of vectors.

**Key Distinction**: pgvector provides the `vector` data type and HNSW indices. pgvectorscale adds StreamingDiskANN indices and Statistical Binary Quantization (SBQ) for better performance at scale.

### Benchmark Results (50M Vectors, 768-dim Cohere Embeddings)

| Metric | pgvector (HNSW) | pgvectorscale (StreamingDiskANN) | Improvement |
|--------|-----------------|----------------------------------|-------------|
| **p95 Latency** | 1,692 ms | 60.42 ms | **28x faster** |
| **p50 Latency** | - | 31.07 ms | - |
| **p99 Latency** | - | 74.60 ms | - |
| **QPS (99% recall)** | - | 471 QPS | 11.4x vs Qdrant |
| **Recall** | 99% | 99% | Same accuracy |
| **Cost (AWS EC2)** | - | 75% less than Pinecone | - |

**Source**: [Timescale pgvectorscale GitHub](https://github.com/timescale/pgvectorscale), [PostgreSQL is Now Faster than Pinecone](https://www.sqlservercentral.com/articles/postgresql-is-now-faster-than-pinecone-75-cheaper-with-new-open-source-extensions)

### Why StreamingDiskANN vs HNSW?

**HNSW (Hierarchical Navigable Small World)**:
- In-memory graph structure
- Fast for small datasets (<1M vectors)
- Memory usage: ~32GB for 1M 768-dim vectors
- Performance degrades with dataset size
- Currently used in Headhunter

**StreamingDiskANN**:
- Disk-based with memory-efficient graph traversal
- Optimized for 10M+ vectors
- Uses Statistical Binary Quantization (SBQ) for compression
- Maintains 99% recall with 28x lower latency
- Better for Headhunter's 23K+ candidate pool (room to scale to millions)

### Current Architecture Gap

**Existing Code** (`services/hh-search-svc/src/pgvector-client.ts:375-378`):
```typescript
await client.query(`
  CREATE INDEX IF NOT EXISTS ${this.config.embeddingsTable}_embedding_hnsw_idx
    ON ${this.config.schema}.${this.config.embeddingsTable} USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
`);
```

**Current HNSW Parameters**:
- `m = 16`: Number of bidirectional links (low for 768-dim)
- `ef_construction = 64`: Build-time search depth (low)
- `ef_search`: Runtime parameter (configurable via `PGVECTOR_HNSW_EF_SEARCH` env)

**Recommended HNSW Tuning** (if keeping HNSW as fallback):
- `m = 32` (better for high-dimensional data)
- `ef_construction = 128` (higher quality graph)
- `ef_search = 200` (runtime tuning)

### pgvectorscale Implementation Plan

**Installation**:
```sql
CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE;
```

**StreamingDiskANN Index Creation**:
```sql
CREATE INDEX ON search.candidate_embeddings
USING diskann (embedding)
WITH (
  num_neighbors = 50,           -- Graph degree (higher = better recall)
  search_list_size = 100,       -- Search depth (tunable at query time)
  max_alpha = 1.2,              -- Pruning aggressiveness
  num_bits_per_dimension = 2    -- SBQ compression (2 = high quality)
);
```

**Query-Time Tuning**:
```sql
SET diskann.query_search_list_size = 200;  -- Higher = better recall, slower
```

**Migration Strategy**:
1. Create StreamingDiskANN index alongside existing HNSW
2. A/B test performance (same queries, both indices)
3. Compare latency, recall, and resource usage
4. Gradually shift traffic to StreamingDiskANN
5. Keep HNSW as fallback for 1 month
6. Drop HNSW index after validation

**Configuration Options**:
- `PGVECTOR_INDEX_TYPE=diskann|hnsw` (feature flag)
- `DISKANN_SEARCH_LIST_SIZE=100` (runtime tuning)
- `DISKANN_NUM_NEIGHBORS=50` (build-time parameter)

---

## 2. Connection Pooling (PERF-03)

### Current State

**Existing Pooling** (`services/hh-search-svc/src/pgvector-client.ts:43-56`):
```typescript
this.pool = new Pool({
  host: config.host,
  port: config.port,
  database: config.database,
  user: config.user,
  password: config.password,
  ssl: config.ssl,
  max: config.poolMax,           // Default: 10
  min: config.poolMin,           // Default: 0
  idleTimeoutMillis: config.idleTimeoutMs,
  connectionTimeoutMillis: config.connectionTimeoutMs,
  statement_timeout: config.statementTimeoutMs
});
```

**Current Configuration** (`services/hh-search-svc/src/config.ts:257-262`):
- `poolMax: 10` (via `PGVECTOR_POOL_MAX`)
- `poolMin: 0` (via `PGVECTOR_POOL_MIN`)
- `idleTimeoutMs: 30000` (30s)
- `connectionTimeoutMs: 5000` (5s)
- `statementTimeoutMs: 30000` (30s)

**Gap**: Pool is already implemented but **not tuned for production workload**.

### Pooling Best Practices (2026)

**Rule of Thumb**: Pool size should be **3-5x CPU core count** of the database server.

**Recommended Settings for Production**:
```typescript
{
  poolMax: 20,              // Higher for Cloud Run concurrency
  poolMin: 5,               // Keep warm connections (reduces cold-start latency)
  idleTimeoutMs: 60000,     // 60s (balance between reuse and resource cleanup)
  connectionTimeoutMs: 3000, // 3s (fail fast on connection issues)
  statementTimeoutMs: 10000  // 10s (aligned with 500ms latency budget, allow retries)
}
```

**Why Not Higher?**
- PostgreSQL creates a **separate backend process** for each connection
- Too many connections = memory overhead + context switching
- Better to queue requests in application layer (Fastify) than overwhelm DB

**Sources**: [PgBouncer Performance](https://www.percona.com/blog/pgbouncer-for-postgresql-how-connection-pooling-solves-enterprise-slowdowns/), [Stack Overflow Connection Pooling](https://stackoverflow.blog/2020/10/14/improve-database-performance-with-connection-pooling/)

### Should We Add PgBouncer?

**PgBouncer Benefits**:
- 18.2% faster performance (3.3ms average improvement)
- 60% better transaction throughput
- Session pooling vs transaction pooling modes
- Lightweight middleware layer

**When to Use PgBouncer**:
- High connection churn (frequent connect/disconnect)
- Many idle connections
- Multi-service architecture sharing same database

**Headhunter Scenario**:
- **8 Fastify services** (hh-search-svc, hh-embed-svc, hh-rerank-svc, etc.)
- Each with 10-connection pool = **80 total connections**
- Cloud SQL supports 100-400 connections (depends on instance)

**Recommendation**:
- **Phase 11**: Tune existing `pg.Pool` settings (low-risk, immediate impact)
- **Phase 12+**: Add PgBouncer if Cloud SQL connection limits become bottleneck
- **Monitor**: Watch `pg.Pool` metrics (`poolSize`, `idleConnections`, `waitingRequests`)

**Implementation**:
```typescript
// Add to health check (already exists: services/hh-search-svc/src/pgvector-client.ts:267-296)
async healthCheck(): Promise<PgVectorHealth> {
  return {
    status: 'healthy',
    totalCandidates: total,
    poolSize: this.pool.totalCount,
    idleConnections: this.pool.idleCount ?? 0,
    waitingRequests: this.pool.waitingCount ?? 0  // KEY METRIC
  };
}
```

**Alert Threshold**: `waitingRequests > 5` for more than 10 seconds = consider PgBouncer.

**Sources**: [PgBouncer Configuration](https://www.pgbouncer.org/config.html), [PostgreSQL Connection Pooling Explained](https://learnomate.org/postgresql-connection-pooling-explained-pgbouncer-vs-pgpool-ii/)

---

## 3. Parallel Query Execution (PERF-03)

### Current Sequential Execution

**Existing Flow** (`services/hh-search-svc/src/search-service.ts`):
```typescript
// Sequential execution (current)
const embedding = await this.embedClient.generateEmbedding(context, jobDescription);  // 50ms
const pgResults = await this.pgClient.hybridSearch({...});                            // 100ms
const reranked = await this.rerankClient.rerank({...});                               // 200ms
// Total: 350ms (waterfall)
```

**Problem**: Each operation waits for the previous one to complete, even when **some operations are independent**.

### Opportunities for Parallelization

#### 3.1 Vector Search + FTS (PostgreSQL Internal)

**Current Implementation** (`services/hh-search-svc/src/pgvector-client.ts:590-665`):
```sql
WITH vector_candidates AS (
  -- Vector search (cosine similarity)
  SELECT ce.entity_id, 1 - (ce.embedding <=> $2) AS vector_score
  FROM search.candidate_embeddings ce
  WHERE ce.tenant_id = $1
  ORDER BY ce.embedding <=> $2 ASC
  LIMIT $3
),
text_candidates AS (
  -- Full-text search (Portuguese dictionary)
  SELECT cp.candidate_id, ts_rank_cd(cp.search_document, plainto_tsquery('portuguese', $4)) AS text_score
  FROM search.candidate_profiles cp
  WHERE cp.tenant_id = $1
    AND cp.search_document @@ plainto_tsquery('portuguese', $4)
  LIMIT $3
)
-- Merge results with RRF scoring
SELECT ... FROM vector_candidates vc FULL OUTER JOIN text_candidates tc ...
```

**Current Behavior**: PostgreSQL query planner executes CTEs **sequentially** unless optimizer detects independence.

**Optimization**: Use **parallel execution hints** (PostgreSQL 11+):
```sql
SET max_parallel_workers_per_gather = 4;  -- Allow parallel workers
SET parallel_setup_cost = 100;            -- Lower threshold for parallelism
SET parallel_tuple_cost = 0.01;           -- Encourage parallel execution
```

**Better Alternative**: Run vector and text searches as **separate queries** in parallel:
```typescript
// Parallel execution with Promise.all
const [vectorResults, textResults] = await Promise.all([
  this.runVectorSearch(tenantId, embedding, limit),
  this.runTextSearch(tenantId, textQuery, limit)
]);

// Merge and score in application layer
const merged = this.mergeWithRRF(vectorResults, textResults);
```

**Trade-off Analysis**:
| Approach | Latency | Complexity | Database Load |
|----------|---------|------------|---------------|
| **Single CTE Query** (current) | 150ms | Low | 1 connection |
| **Parallel Queries** | 100ms | Medium | 2 connections |
| **PostgreSQL Parallel Workers** | 120ms | Low | 1 connection + workers |

**Recommendation**:
- **Phase 11**: Keep single CTE query, enable PostgreSQL parallel workers
- **Phase 12+**: A/B test separate parallel queries if latency target not met

#### 3.2 Embedding + Specialty Lookup Parallelization

**Current Code** (`services/hh-search-svc/src/search-service.ts`):
```typescript
// Embedding generation
const embeddingStart = Date.now();
const embedding = await this.embedClient.generateEmbedding(context, jobDescription);
timings.embeddingMs = Date.now() - embeddingStart;

// Specialty pre-filtering (if enabled)
const specialtyMatch = await this.getSpecialtyMatch(context, jobDescription);
```

**Opportunity**: Embedding generation and specialty lookup are **independent operations**.

**Parallelized Version**:
```typescript
const [embedding, specialtyMatch] = await Promise.all([
  this.embedClient.generateEmbedding(context, jobDescription),
  this.getSpecialtyMatch(context, jobDescription)
]);
```

**Latency Improvement**:
- Sequential: 50ms (embedding) + 20ms (specialty) = **70ms**
- Parallel: `max(50ms, 20ms)` = **50ms**
- **Savings: 20ms**

#### 3.3 Firestore Fallback Parallelization

**Current Implementation** (`services/hh-search-svc/src/search-service.ts`):
```typescript
// Firestore fallback for missing candidates (sequential)
for (const candidateId of missingIds) {
  const doc = await firestore.collection('candidates').doc(candidateId).get();
  // Process...
}
```

**Parallelized Version**:
```typescript
// Batch read with concurrency limit
const concurrency = this.config.firestoreFallback.concurrency; // Default: 8

const chunks = chunk(missingIds, concurrency);
for (const batch of chunks) {
  const docs = await Promise.all(
    batch.map(id => firestore.collection('candidates').doc(id).get())
  );
  // Process batch...
}
```

**Latency Improvement**:
- Sequential 10 reads: 10 × 50ms = **500ms**
- Parallel (concurrency=8): ~2 batches × 50ms = **100ms**
- **Savings: 400ms** (critical for fallback scenarios)

### Node.js Parallel Execution Patterns (2026)

**Best Practice**: Use `Promise.all()` for independent async operations.

**Example Pattern** (from research):
```typescript
try {
  const [users, products, orders] = await Promise.all([
    User.find(),
    Product.find(),
    Order.find()
  ]);
  // All three queries ran in parallel
} catch (error) {
  // Centralized error handling
  logger.error({ error }, 'Parallel query failed');
}
```

**Error Handling**: `Promise.all()` **rejects on first error**. For partial failure tolerance, use `Promise.allSettled()`:
```typescript
const results = await Promise.allSettled([
  this.runVectorSearch(),
  this.runTextSearch()
]);

const vectorResults = results[0].status === 'fulfilled' ? results[0].value : [];
const textResults = results[1].status === 'fulfilled' ? results[1].value : [];
```

**Sources**: [Node.js Async Best Practices](https://www.cloudbees.com/blog/node-js-async-best-practices-avoiding-callback-hell), [Mastering Parallel Execution](https://dev.to/ericus123/mastering-parallel-execution-with-asyncawait-in-javascript-nodejs-for-beginners-1i7d), [Modern Node.js Patterns 2025](https://kashw1n.com/blog/nodejs-2025/)

---

## 4. Embedding Pre-Computation (PERF-04)

### Current State

**Embedding Generation**: On-demand during search (50ms per query).

**Problem**: Embedding generation consumes **10% of latency budget** (50ms of 500ms target).

### Pre-Computation Strategy

**Goal**: Pre-compute embeddings for **all 23,000+ candidates** in `candidate_embeddings` table.

**Implementation Options**:

#### Option A: pg_cron Scheduled Updates (Simple)
```sql
-- Install pg_cron extension
CREATE EXTENSION pg_cron;

-- Schedule nightly embedding refresh
SELECT cron.schedule(
  'refresh-candidate-embeddings',
  '0 2 * * *',  -- 2 AM daily
  $$
  SELECT refresh_candidate_embeddings();
  $$
);
```

**Function to Refresh**:
```sql
CREATE OR REPLACE FUNCTION refresh_candidate_embeddings()
RETURNS void AS $$
DECLARE
  batch_size INT := 100;
  offset_val INT := 0;
  total_updated INT := 0;
BEGIN
  LOOP
    -- Process batch
    WITH batch AS (
      SELECT candidate_id, profile
      FROM search.candidate_profiles
      WHERE updated_at > NOW() - INTERVAL '24 hours'
      ORDER BY updated_at DESC
      LIMIT batch_size OFFSET offset_val
    )
    UPDATE search.candidate_embeddings ce
    SET embedding = generate_embedding(b.profile),  -- Call to embedding service
        updated_at = NOW()
    FROM batch b
    WHERE ce.entity_id = b.candidate_id;

    GET DIAGNOSTICS total_updated = ROW_COUNT;
    EXIT WHEN total_updated < batch_size;
    offset_val := offset_val + batch_size;
  END LOOP;
END;
$$ LANGUAGE plpgsql;
```

#### Option B: pgai Vectorizer (Modern, Automated)

**pgai** is a PostgreSQL extension from Timescale that **automates embedding management**.

**Installation**:
```sql
CREATE EXTENSION IF NOT EXISTS ai CASCADE;
```

**Setup Vectorizer**:
```sql
SELECT ai.create_vectorizer(
  'search.candidate_profiles'::regclass,
  destination => 'search.candidate_embeddings',
  embedding => ai.embedding_openai('text-embedding-3-small', 768),  -- Or Gemini
  chunking => ai.chunking_recursive_character_text_splitter('profile', 2000, 200),
  formatting => ai.formatting_python_template('Profile: $profile'),
  scheduling => ai.scheduling_timescaledb('5 minutes')
);
```

**Benefits**:
- Automatic synchronization (embeddings update when source data changes)
- Handles batch processing and rate limiting
- Supports S3 documents and PostgreSQL data
- Built-in retry and error handling

**Sources**: [pgai GitHub](https://github.com/timescale/pgai), [Automatic Embeddings in Postgres](https://supabase.com/blog/automatic-embeddings), [Automating Vector Embedding Generation](https://aws.amazon.com/blogs/database/automating-vector-embedding-generation-in-amazon-aurora-postgresql-with-amazon-bedrock/)

#### Option C: Application-Layer Batch Worker

**Architecture**:
```
Cloud Scheduler → Pub/Sub Topic → Cloud Run Worker → Batch Process Candidates
                                         ↓
                                   Update Embeddings
```

**Worker Implementation** (TypeScript):
```typescript
export async function refreshEmbeddings(req: Request, res: Response) {
  const batchSize = 100;
  const concurrency = 10;

  // Get candidates updated in last 24 hours
  const candidates = await db.query(`
    SELECT candidate_id, profile
    FROM search.candidate_profiles
    WHERE updated_at > NOW() - INTERVAL '24 hours'
  `);

  // Process in batches with concurrency limit
  const batches = chunk(candidates.rows, batchSize);

  for (const batch of batches) {
    const chunks = chunk(batch, concurrency);
    for (const concurrentBatch of chunks) {
      await Promise.all(
        concurrentBatch.map(async (candidate) => {
          const embedding = await embedClient.generate(candidate.profile);
          await db.query(`
            INSERT INTO search.candidate_embeddings (entity_id, embedding, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (entity_id) DO UPDATE
            SET embedding = EXCLUDED.embedding, updated_at = NOW()
          `, [candidate.candidate_id, embedding]);
        })
      );
    }
  }

  res.status(200).send({ processed: candidates.rows.length });
}
```

**Trade-off Matrix**:

| Approach | Setup Complexity | Reliability | Observability | Cost |
|----------|------------------|-------------|---------------|------|
| **pg_cron** | Low | Medium | Low (DB logs only) | Low |
| **pgai Vectorizer** | Medium | High | Medium (extension logs) | Low |
| **Cloud Run Worker** | High | High | High (Cloud Logging, metrics) | Medium |

**Recommendation**:
- **Phase 11**: pgai Vectorizer (modern, PostgreSQL-native, low ops burden)
- **Fallback**: Cloud Run Worker if pgai doesn't support Gemini provider

### Embedding Cache Invalidation

**Problem**: Stale embeddings when candidate profiles update.

**Solution**: Database trigger to invalidate embeddings on profile changes.

```sql
CREATE OR REPLACE FUNCTION invalidate_candidate_embedding()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE search.candidate_embeddings
  SET updated_at = NOW() - INTERVAL '1 year'  -- Force refresh
  WHERE entity_id = NEW.candidate_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER candidate_profile_updated
AFTER UPDATE ON search.candidate_profiles
FOR EACH ROW
WHEN (OLD.profile IS DISTINCT FROM NEW.profile)
EXECUTE FUNCTION invalidate_candidate_embedding();
```

**Alternative**: Delete stale embedding and regenerate on next access.

```sql
CREATE OR REPLACE FUNCTION delete_stale_embedding()
RETURNS TRIGGER AS $$
BEGIN
  DELETE FROM search.candidate_embeddings
  WHERE entity_id = NEW.candidate_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

## 5. Redis Caching Strategy (PERF-05)

### Current State

**Existing Cache** (`services/hh-search-svc/src/redis-client.ts`):
- Cache key: SHA-1 hash of query + filters
- TTL: 180 seconds (3 minutes)
- Stored data: Search results (candidate IDs + scores)

**Gap**: No **scoring cache** for rerank results, no sophisticated invalidation strategy.

### Modern Redis Caching Patterns (2026)

#### 5.1 Cache-Aside (Lazy Loading) - Current Pattern

**How it Works**:
1. Check cache for key
2. If miss: Fetch from DB, store in cache, return to client
3. If hit: Return cached value

**Current Implementation**:
```typescript
async getCached<T>(key: string): Promise<T | null> {
  const cached = await this.client.get(key);
  return cached ? JSON.parse(cached) : null;
}

async setCached<T>(key: string, value: T, ttlSeconds?: number): Promise<void> {
  const ttl = ttlSeconds ?? this.config.ttlSeconds;
  await this.client.setex(key, ttl, JSON.stringify(value));
}
```

**Strengths**: Simple, works well for read-heavy workloads.
**Weakness**: Cold-start latency on cache miss.

#### 5.2 Write-Through (Proactive Caching)

**How it Works**:
1. All writes go through cache layer
2. Cache synchronously updates database
3. Reads always hit cache (high hit rate)

**Use Case**: Rerank scoring cache (results rarely change unless model updates).

**Implementation**:
```typescript
async updateCandidateScore(candidateId: string, score: number): Promise<void> {
  // Write to cache
  await this.redisClient.hset(`candidate:${candidateId}`, 'score', score);

  // Write to database (synchronous)
  await this.db.query(
    'UPDATE candidate_profiles SET score = $1 WHERE candidate_id = $2',
    [score, candidateId]
  );
}
```

**Benefit**: Cache always has fresh data, no cold-start penalty.

#### 5.3 Cache Invalidation Patterns

**TTL-Based Expiration** (current approach):
- **Pros**: Simple, automatic cleanup
- **Cons**: Stale data until expiration, cache stampede risk

**Event-Based Invalidation**:
```typescript
// When candidate profile updates
async onCandidateUpdate(candidateId: string): Promise<void> {
  // Invalidate related cache keys
  const patterns = [
    `search:*:candidate:${candidateId}`,  // Any search containing this candidate
    `rerank:*:${candidateId}`,            // Rerank scores for this candidate
    `specialty:${candidateId}`            // Specialty cache
  ];

  for (const pattern of patterns) {
    const keys = await this.redisClient.keys(pattern);
    if (keys.length > 0) {
      await this.redisClient.del(...keys);
    }
  }
}
```

**Group-Based Invalidation**:
```typescript
// Invalidate all searches for a tenant
async invalidateTenantSearches(tenantId: string): Promise<void> {
  const pattern = `search:${tenantId}:*`;
  const keys = await this.redisClient.keys(pattern);
  if (keys.length > 0) {
    await this.redisClient.del(...keys);
  }
}
```

**Pub/Sub Invalidation** (distributed cache):
```typescript
// Publisher (when data changes)
await redisClient.publish('cache-invalidate', JSON.stringify({
  pattern: 'search:tenant-alpha:*'
}));

// Subscriber (in each service instance)
redisClient.subscribe('cache-invalidate', (message) => {
  const { pattern } = JSON.parse(message);
  // Invalidate local cache entries matching pattern
  this.invalidatePattern(pattern);
});
```

**Sources**: [Redis Cache Invalidation](https://redis.io/glossary/cache-invalidation/), [Three Ways to Maintain Cache Consistency](https://redis.io/blog/three-ways-to-maintain-cache-consistency/), [Redis Cache 2026 Guide](https://thelinuxcode.com/redis-cache-in-2026-fast-paths-fresh-data-and-a-modern-dx/)

#### 5.4 Recommended TTL Values (2026 Best Practices)

| Data Type | Change Frequency | Recommended TTL | Rationale |
|-----------|------------------|-----------------|-----------|
| **Search Results** | Hourly (candidate updates) | 5-10 minutes | Balance freshness vs hit rate |
| **Rerank Scores** | Daily (model updates) | 1-6 hours | Expensive to compute, rarely changes |
| **Specialty Lookups** | Weekly (new specialties) | 24 hours | Static reference data |
| **Embeddings** | On-demand (profile edits) | No TTL (event-invalidated) | Pre-computed, invalidate on change |

**Source**: [Redis Cache 2026 Guide](https://thelinuxcode.com/redis-cache-in-2026-fast-paths-fresh-data-and-a-modern-dx/)

#### 5.5 Cache Stampede Prevention

**Problem**: When cache expires, multiple concurrent requests trigger database queries.

**Solution 1: Request Coalescing** (in-memory deduplication):
```typescript
private pendingRequests = new Map<string, Promise<any>>();

async getOrFetch<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  // Check cache
  const cached = await this.getCached<T>(key);
  if (cached) return cached;

  // Check if request already in-flight
  if (this.pendingRequests.has(key)) {
    return this.pendingRequests.get(key);
  }

  // Fetch and cache
  const promise = fetcher().then(async (result) => {
    await this.setCached(key, result);
    this.pendingRequests.delete(key);
    return result;
  });

  this.pendingRequests.set(key, promise);
  return promise;
}
```

**Solution 2: Randomized TTL** (avoid synchronized expiration):
```typescript
async setCached<T>(key: string, value: T, baseTtl: number): Promise<void> {
  // Add ±20% jitter to TTL
  const jitter = baseTtl * 0.2 * (Math.random() - 0.5);
  const ttl = Math.floor(baseTtl + jitter);

  await this.client.setex(key, ttl, JSON.stringify(value));
}
```

**Solution 3: Lock-Based Refresh** (Redis distributed lock):
```typescript
async refreshWithLock<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const lockKey = `lock:${key}`;
  const lockAcquired = await this.client.set(lockKey, '1', 'EX', 10, 'NX');

  if (lockAcquired) {
    try {
      const result = await fetcher();
      await this.setCached(key, result);
      return result;
    } finally {
      await this.client.del(lockKey);
    }
  } else {
    // Another instance is refreshing, wait and retry
    await new Promise(resolve => setTimeout(resolve, 100));
    return this.getCached<T>(key) ?? this.refreshWithLock(key, fetcher);
  }
}
```

#### 5.6 Eviction Policies

**Current Configuration**: Likely using `noeviction` (default).

**Recommended for Production**: `allkeys-lru` (Least Recently Used).

**Redis Configuration**:
```redis
maxmemory 2gb
maxmemory-policy allkeys-lru
```

**Why LRU?**
- Automatically removes least-used entries when memory full
- Prevents cache from blocking writes
- Better than LFU (Least Frequently Used) for time-sensitive data

**Alternative**: `volatile-lru` (only evict keys with TTL set).

**Sources**: [Redis Caching Patterns](https://docs.aws.amazon.com/whitepapers/latest/database-caching-strategies-using-redis/caching-patterns.html), [GeeksforGeeks Redis Cache](https://www.geeksforgeeks.org/system-design/redis-cache/)

### Proposed Redis Architecture for Phase 11

```
┌─────────────────────────────────────────────────────────────────┐
│                       Redis Cache Layers                         │
├─────────────────────────────────────────────────────────────────┤
│ 1. Search Results Cache                                          │
│    Key: `search:{tenantId}:{jdHash}`                            │
│    TTL: 10 minutes (randomized ±2 min)                          │
│    Invalidation: Event-based on candidate update                │
├─────────────────────────────────────────────────────────────────┤
│ 2. Rerank Scoring Cache                                          │
│    Key: `rerank:{modelVersion}:{candidateId}:{jdHash}`          │
│    TTL: 6 hours (static unless model updates)                   │
│    Invalidation: Model version change → FLUSHDB                 │
├─────────────────────────────────────────────────────────────────┤
│ 3. Specialty Lookup Cache                                        │
│    Key: `specialty:{titleKeywords}`                             │
│    TTL: 24 hours                                                │
│    Invalidation: Manual on specialty mapping update             │
├─────────────────────────────────────────────────────────────────┤
│ 4. Embedding Cache (if not pre-computed)                         │
│    Key: `embedding:{modelVersion}:{contentHash}`                │
│    TTL: No expiration (event-invalidated)                       │
│    Invalidation: Profile update → DELETE                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Latency Budget Breakdown (500ms Total)

### Current Baseline (Estimated)

| Stage | Current | Target | Improvement Needed |
|-------|---------|--------|-------------------|
| **Embedding Generation** | 50ms | 0ms (pre-computed) | **-50ms** |
| **Vector Search** | 150ms | 60ms (pgvectorscale) | **-90ms** |
| **Text Search (FTS)** | 100ms | 40ms (parallel) | **-60ms** |
| **Scoring/Filtering** | 150ms | 80ms (optimized) | **-70ms** |
| **Reranking** | 350ms | 200ms (cached) | **-150ms** |
| **Network/Overhead** | 200ms | 120ms (pooling) | **-80ms** |
| **TOTAL** | **1,000ms** | **500ms** | **-500ms (50% reduction)** |

### Optimized Pipeline (Phase 11 Target)

```
┌──────────────────────────────────────────────────────────────────┐
│ Request Arrives                                              0ms  │
└──────────────┬───────────────────────────────────────────────────┘
               │
               ├─→ Check Redis Cache ────────────────────→ HIT? Return (50ms)
               │
               └─→ MISS → Parallel Execution:
                   │
                   ├─→ Embedding (pre-computed lookup) ───→ 10ms
                   ├─→ Specialty Lookup (cached) ─────────→ 15ms
                   │
                   └─→ Promise.all([vector, text, specialty])
                       │
                       ├─→ StreamingDiskANN Vector Search ─→ 60ms
                       ├─→ PostgreSQL FTS (parallel) ──────→ 40ms
                       └─→ Specialty Pre-filter ───────────→ 15ms
                       │
                       └─→ Merge & Score (application) ────→ 80ms
                           │
                           └─→ Rerank (cached scores) ─────→ 200ms
                               │
                               └─→ Return Results ─────────→ 500ms TOTAL
```

### Key Optimizations Applied

1. **Embedding Pre-Computation**: -40ms (50ms → 10ms lookup)
2. **pgvectorscale**: -90ms (150ms → 60ms)
3. **Parallel Vector + FTS**: -60ms (150ms combined → 100ms max)
4. **Connection Pooling**: -80ms (reduced connection overhead)
5. **Redis Rerank Cache**: -150ms (350ms → 200ms on cache hit)

**Total Savings**: 420ms (1,000ms → 500ms achievable with 80ms buffer)

---

## 7. Monitoring & Observability

### Performance Metrics to Track

**Existing Tracker** (`services/hh-search-svc/src/performance-tracker.ts`):
```typescript
export interface PerformanceSample {
  totalMs: number;
  embeddingMs?: number;
  retrievalMs?: number;
  rerankMs?: number;
  cacheHit: boolean;
  rerankApplied?: boolean;
  timestamp?: number;
}
```

**Additional Metrics Needed for Phase 11**:
```typescript
export interface ExtendedPerformanceSample extends PerformanceSample {
  // Index type performance
  indexType?: 'hnsw' | 'diskann';
  hnswEfSearch?: number;
  diskannSearchListSize?: number;

  // Parallel execution metrics
  vectorSearchMs?: number;
  textSearchMs?: number;
  specialtyLookupMs?: number;
  parallelSavingsMs?: number;  // Sequential - Parallel

  // Connection pool metrics
  poolWaitMs?: number;
  poolSize?: number;
  idleConnections?: number;

  // Cache metrics
  embeddingCacheHit?: boolean;
  rerankCacheHit?: boolean;
  specialtyCacheHit?: boolean;
}
```

### Alerting Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| **p95 Total Latency** | > 600ms for 5 min | Page on-call engineer |
| **p99 Total Latency** | > 1000ms for 5 min | Investigate index degradation |
| **Vector Search p95** | > 100ms | Check StreamingDiskANN tuning |
| **Rerank p95** | > 300ms | Review cache hit rate |
| **Cache Hit Rate** | < 60% | Adjust TTL or invalidation logic |
| **Pool Wait Time** | > 100ms | Increase pool size or add PgBouncer |
| **Idle Connections** | > 50% of pool | Reduce pool min |

### Cloud Monitoring Dashboards

**Metrics to Export** (via Prometheus/OpenTelemetry):
```typescript
// Counter: Total searches
searchCounter.inc({ tenantId, cacheHit: true/false });

// Histogram: Latency breakdown
searchLatencyHistogram.observe(totalMs, { stage: 'vector_search' });
searchLatencyHistogram.observe(totalMs, { stage: 'text_search' });
searchLatencyHistogram.observe(totalMs, { stage: 'rerank' });

// Gauge: Connection pool utilization
poolUtilizationGauge.set(idleConnections / poolSize);

// Counter: Index type usage
indexTypeCounter.inc({ indexType: 'diskann' });
```

**Dashboard Panels**:
1. **Latency Heatmap**: p50/p95/p99 over time
2. **Stage Breakdown**: Stacked bar chart (embedding, vector, text, rerank)
3. **Cache Performance**: Hit rate, eviction rate, memory usage
4. **Pool Health**: Active connections, wait time, saturation
5. **Error Rate**: 5xx errors, timeout rate, retry count

---

## 8. Migration & Rollout Strategy

### Phase 11 Implementation Sequence

**Week 1: Foundation**
1. Install pgvectorscale extension on Cloud SQL
2. Create StreamingDiskANN index alongside HNSW
3. Add feature flag: `PGVECTOR_INDEX_TYPE=diskann|hnsw`
4. Deploy configuration tuning (pool sizes, TTLs)

**Week 2: Parallel Execution**
5. Refactor `search-service.ts` to use `Promise.all()` for independent operations
6. Add parallel execution metrics to `PerformanceTracker`
7. A/B test: 10% traffic to parallelized pipeline
8. Monitor latency improvements

**Week 3: Embedding Pre-Computation**
9. Deploy pgai Vectorizer or Cloud Run batch worker
10. Backfill embeddings for all 23K+ candidates
11. Add embedding cache lookup logic
12. Monitor cache hit rate and freshness

**Week 4: Caching Strategy**
13. Implement multi-layer Redis cache (search, rerank, specialty)
14. Add event-based invalidation triggers
15. Deploy randomized TTL and request coalescing
16. Load test with production traffic patterns

**Week 5: Validation & Cutover**
17. Run A/B test: HNSW vs StreamingDiskANN (50/50 split)
18. Validate p95 latency < 500ms on StreamingDiskANN
19. Gradual rollout: 25% → 50% → 100% StreamingDiskANN
20. Drop HNSW index after 1 month of stable performance

### Rollback Plan

**If StreamingDiskANN Underperforms**:
1. Revert feature flag to `PGVECTOR_INDEX_TYPE=hnsw`
2. Keep HNSW index warm during migration period
3. Investigate tuning parameters (`num_neighbors`, `search_list_size`)

**If Parallel Execution Introduces Bugs**:
1. Feature flag: `ENABLE_PARALLEL_EXECUTION=false`
2. Revert to sequential pipeline
3. Add integration tests for edge cases

**If Cache Invalidation Fails**:
1. Reduce TTLs to 1 minute (more frequent refresh)
2. Disable event-based invalidation, rely on TTL only
3. Add manual cache flush endpoint for emergencies

---

## 9. Testing Strategy

### Load Testing Scenarios

**Scenario 1: Cold Start (No Cache)**
- 100 concurrent users
- Random JD queries (no cache hits)
- Measure: p95 latency < 500ms
- Tool: Artillery or k6

**Scenario 2: Warm Cache (80% Hit Rate)**
- 500 concurrent users
- Repeated searches (simulate real usage)
- Measure: p95 latency < 100ms (cache hits)
- Cache miss latency < 500ms

**Scenario 3: Database Stress Test**
- 1000 concurrent searches
- Validate: Pool doesn't saturate, no connection timeouts
- Measure: Queue depth, wait times

**Scenario 4: Cache Stampede**
- Expire all cache entries simultaneously
- 200 concurrent requests for same query
- Measure: Request coalescing prevents duplicate DB queries

### Integration Tests

**Test 1: HNSW vs StreamingDiskANN Accuracy**
```typescript
test('StreamingDiskANN returns same top-20 candidates as HNSW', async () => {
  const hnswResults = await searchWithIndex('hnsw', query);
  const diskannResults = await searchWithIndex('diskann', query);

  const hnswTop20 = hnswResults.slice(0, 20).map(r => r.candidate_id);
  const diskannTop20 = diskannResults.slice(0, 20).map(r => r.candidate_id);

  const overlap = intersection(hnswTop20, diskannTop20).length;
  expect(overlap).toBeGreaterThanOrEqual(18);  // 90% overlap acceptable
});
```

**Test 2: Parallel Execution Correctness**
```typescript
test('Parallel execution returns same results as sequential', async () => {
  const sequential = await searchSequential(query);
  const parallel = await searchParallel(query);

  expect(parallel.results).toEqual(sequential.results);
  expect(parallel.totalMs).toBeLessThan(sequential.totalMs);
});
```

**Test 3: Cache Invalidation**
```typescript
test('Candidate update invalidates related search cache', async () => {
  const results1 = await search(query);  // Cache miss
  await updateCandidate(results1[0].candidate_id, { title: 'New Title' });

  const results2 = await search(query);  // Should be cache miss
  expect(results2[0].title).toBe('New Title');
});
```

---

## 10. Risk Assessment & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **pgvectorscale not available on Cloud SQL** | High | Low | Check GCP extension support; use managed Timescale Cloud |
| **StreamingDiskANN slower than HNSW for small datasets** | Medium | Medium | Keep HNSW as fallback; A/B test thoroughly |
| **Connection pool saturation** | High | Medium | Monitor wait times; add PgBouncer if needed |
| **Cache stampede on popular queries** | Medium | High | Implement request coalescing and lock-based refresh |
| **Embedding pre-computation fails** | Medium | Low | Graceful fallback to on-demand generation |
| **Parallel execution introduces race conditions** | High | Low | Comprehensive integration tests; feature flag rollback |
| **Redis memory exhaustion** | High | Medium | Configure `maxmemory` and `allkeys-lru` eviction |

---

## 11. Success Criteria Validation

### Acceptance Tests

**PERF-01**: p95 search latency under 500ms
- **Test**: Load test with 1000 concurrent users, measure p95 over 10-minute window
- **Threshold**: p95 ≤ 500ms for non-cached requests
- **Evidence**: Performance dashboard screenshot + load test report

**PERF-02**: pgvectorscale integration
- **Test**: Query `pg_extension` to verify installation, run sample ANN query
- **Threshold**: StreamingDiskANN index exists and is used by query planner
- **Evidence**: `EXPLAIN ANALYZE` output showing "Index Scan using diskann"

**PERF-03**: Connection pooling and parallel execution
- **Test**: Monitor pool metrics during load test, compare sequential vs parallel latency
- **Threshold**: Pool wait time < 50ms, parallel saves ≥ 20% latency
- **Evidence**: Metrics dashboard + A/B test results

**PERF-04**: Embedding pre-computation
- **Test**: Query `candidate_embeddings` table, verify 23K+ rows with recent timestamps
- **Threshold**: 100% of active candidates have pre-computed embeddings
- **Evidence**: SQL query result + embedding generation logs

**PERF-05**: Redis caching strategy
- **Test**: Simulate candidate update, verify cache invalidation, measure hit rate
- **Threshold**: Cache hit rate ≥ 70%, invalidation latency < 100ms
- **Evidence**: Redis INFO stats + invalidation event logs

---

## 12. Additional Resources

### Documentation to Review

1. **pgvectorscale Official Docs**: [GitHub README](https://github.com/timescale/pgvectorscale/blob/main/README.md)
2. **PostgreSQL Connection Pooling Guide**: [pgDash PgBouncer](https://pgdash.io/blog/pgbouncer-connection-pool.html)
3. **Node.js Async Patterns**: [Modern Node.js 2025](https://kashw1n.com/blog/nodejs-2025/)
4. **Redis Caching Best Practices**: [Redis.io Caching Solutions](https://redis.io/solutions/caching/)
5. **pgai Vectorizer Tutorial**: [Supabase Automatic Embeddings](https://supabase.com/blog/automatic-embeddings)

### Tools for Testing

- **k6**: Load testing tool (better than Artillery for complex scenarios)
- **pgBadger**: PostgreSQL log analyzer (identify slow queries)
- **Redis CLI**: Manual cache inspection and debugging
- **Cloud Profiler**: CPU and memory profiling for Node.js

### Team Skills Needed

| Skill | Required For | Training Resources |
|-------|--------------|-------------------|
| **PostgreSQL Index Tuning** | StreamingDiskANN configuration | Timescale docs, pgvector tutorials |
| **Node.js Parallel Programming** | Promise.all patterns | Modern Node.js course |
| **Redis Architecture** | Cache invalidation strategies | Redis University (free) |
| **SQL Performance Analysis** | EXPLAIN ANALYZE interpretation | PostgreSQL Performance blog |

---

## 13. Open Questions for Planning Phase

1. **Cloud SQL Extension Support**: Does Google Cloud SQL support pgvectorscale extension?
   - **Action**: Open GCP support ticket to confirm
   - **Fallback**: Use Timescale Cloud managed service

2. **Gemini Embedding Support in pgai**: Does pgai Vectorizer support Gemini API?
   - **Action**: Review pgai source code, test with custom provider
   - **Fallback**: Build custom Cloud Run worker

3. **Rerank Model Version Management**: How to invalidate cache when rerank model updates?
   - **Action**: Add `modelVersion` to cache key, FLUSHDB on deploy
   - **Consider**: Gradual rollout with dual-model support

4. **Multi-Tenant Cache Isolation**: Should each tenant have separate Redis namespace?
   - **Action**: Use key prefix `{tenantId}:search:...` for automatic sharding
   - **Benefit**: Tenant-specific cache invalidation

5. **Load Test Infrastructure**: Where to run 1000-user load tests without hitting production?
   - **Action**: Provision staging Cloud SQL instance, copy production data
   - **Tool**: Use Cloud Run load testing service or k6 on GCE

---

## Sources

- [Timescale pgvectorscale GitHub](https://github.com/timescale/pgvectorscale)
- [PostgreSQL is Now Faster than Pinecone](https://www.sqlservercentral.com/articles/postgresql-is-now-faster-than-pinecone-75-cheaper-with-new-open-source-extensions)
- [PgBouncer Performance Blog](https://www.percona.com/blog/pgbouncer-for-postgresql-how-connection-pooling-solves-enterprise-slowdowns/)
- [PostgreSQL Connection Pooling Explained](https://learnomate.org/postgresql-connection-pooling-explained-pgbouncer-vs-pgpool-ii/)
- [Stack Overflow: Improve Database Performance with Connection Pooling](https://stackoverflow.blog/2020/10/14/improve-database-performance-with-connection-pooling/)
- [Redis Cache Invalidation](https://redis.io/glossary/cache-invalidation/)
- [Three Ways to Maintain Cache Consistency](https://redis.io/blog/three-ways-to-maintain-cache-consistency/)
- [Redis Cache 2026 Guide](https://thelinuxcode.com/redis-cache-in-2026-fast-paths-fresh-data-and-a-modern-dx/)
- [Redis Caching Patterns (AWS)](https://docs.aws.amazon.com/whitepapers/latest/database-caching-strategies-using-redis/caching-patterns.html)
- [pgai GitHub](https://github.com/timescale/pgai)
- [Automatic Embeddings in Postgres (Supabase)](https://supabase.com/blog/automatic-embeddings)
- [Automating Vector Embedding Generation (AWS)](https://aws.amazon.com/blogs/database/automating-vector-embedding-generation-in-amazon-aurora-postgresql-with-amazon-bedrock/)
- [Node.js Async Best Practices](https://www.cloudbees.com/blog/node-js-async-best-practices-avoiding-callback-hell)
- [Mastering Parallel Execution with async/await](https://dev.to/ericus123/mastering-parallel-execution-with-asyncawait-in-javascript-nodejs-for-beginners-1i7d)
- [Modern Node.js Patterns 2025](https://kashw1n.com/blog/nodejs-2025/)
- [GeeksforGeeks: Redis Cache](https://www.geeksforgeeks.org/system-design/redis-cache/)
- [pgvectorscale Extension Guide (dbvis)](https://www.dbvis.com/thetable/pgvectorscale-an-extension-for-improved-vector-search-in-postgres/)
