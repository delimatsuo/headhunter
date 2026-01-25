---
phase: 11-performance-foundation
plan: 01
subsystem: search-infrastructure
tags: [pgvectorscale, streamingdiskann, performance, postgresql, vector-search]
requires:
  - pgvector extension installed
  - PostgreSQL with vector support
provides:
  - pgvectorscale extension migration
  - StreamingDiskANN index migration
  - Index type feature flag (PGVECTOR_INDEX_TYPE)
  - Query-time tuning support
affects:
  - 11-02: Connection pooling benefits from optimized index performance
  - 11-03: Parallel execution works with either index type
  - 11-05: Performance tracking can measure index type impact
tech-stack:
  added:
    - pgvectorscale: PostgreSQL extension for StreamingDiskANN indices
  patterns:
    - Feature flag for index A/B testing
    - Runtime parameter tuning
    - Graceful fallback when extension unavailable
key-files:
  created:
    - scripts/migrations/011_pgvectorscale_extension.sql: Extension installation
    - scripts/migrations/012_streamingdiskann_index.sql: DiskANN index creation
  modified:
    - services/hh-search-svc/src/config.ts: Index type configuration
    - services/hh-search-svc/src/pgvector-client.ts: Index-aware query execution
decisions:
  - decision: Use StreamingDiskANN alongside HNSW for A/B testing
    rationale: Research shows 28x latency improvement; side-by-side comparison validates performance in production
    phase: 11
  - decision: Default to HNSW, opt-in to DiskANN via env var
    rationale: HNSW is proven and stable; DiskANN requires Cloud SQL compatibility verification
    phase: 11
  - decision: Make search_list_size tunable at runtime
    rationale: Allows fine-tuning recall vs latency tradeoff without redeployment
    phase: 11
metrics:
  duration: 201
  completed: 2026-01-25
---

# Phase 11 Plan 01: pgvectorscale and StreamingDiskANN Index Summary

**One-liner:** Install pgvectorscale extension and create StreamingDiskANN index with feature flag for 28x vector search performance improvement

## What Was Built

Installed pgvectorscale extension and created StreamingDiskANN index infrastructure to enable dramatic vector search latency improvements while maintaining HNSW as a fallback option.

### Core Components

1. **pgvectorscale Extension Migration** (011_pgvectorscale_extension.sql)
   - Checks for pgvector prerequisite
   - Installs vectorscale extension via CREATE EXTENSION IF NOT EXISTS
   - Verifies installation with error handling
   - Gracefully fails if extension unavailable

2. **StreamingDiskANN Index Migration** (012_streamingdiskann_index.sql)
   - Creates diskann index on search.candidate_embeddings
   - Configured parameters:
     - num_neighbors=50 (graph degree for 23K candidates)
     - search_list_size=100 (default search depth)
     - max_alpha=1.2 (pruning aggressiveness)
     - num_bits_per_dimension=2 (high-quality SBQ compression)
   - Runs alongside existing HNSW index
   - Includes verification query

3. **Index Type Configuration** (config.ts)
   - Added indexType: 'hnsw' | 'diskann' field to PgVectorConfig
   - Added diskannSearchListSize runtime tuning parameter
   - Environment variables: PGVECTOR_INDEX_TYPE, DISKANN_SEARCH_LIST_SIZE
   - Default: 'hnsw' for backward compatibility

4. **Index-Aware Query Execution** (pgvector-client.ts)
   - Conditional runtime parameter setting:
     - DiskANN: `SET LOCAL diskann.query_search_list_size = N`
     - HNSW: `SET LOCAL hnsw.ef_search = N`
   - Debug logging for index type tracking
   - indexType included in RRF hybrid search summary
   - Health check reports active index type

## Architecture Impact

### Before
- Single HNSW index for vector search
- ef_search as only tuning parameter
- ~100ms vector search latency (estimated baseline)

### After
- Dual index support: HNSW + StreamingDiskANN
- Feature flag enables A/B testing in production
- Runtime tuning for both index types
- Expected 28x improvement when using DiskANN (research-backed)

### Integration Points

**Upstream Dependencies:**
- pgvector extension (must exist before vectorscale)
- PostgreSQL 12+ with vector support

**Downstream Consumers:**
- hh-search-svc hybrid search queries (transparent index switching)
- Performance monitoring (index type in logs)
- Health checks (index type visibility)

## Decisions Made

### Technical Decisions

1. **Side-by-side index approach**
   - Keep both HNSW and DiskANN indices active
   - Switch via environment variable, not code deployment
   - Rationale: Zero-downtime A/B testing; instant rollback if issues

2. **Conservative defaults**
   - Default to HNSW (proven stable)
   - Require explicit PGVECTOR_INDEX_TYPE=diskann opt-in
   - Rationale: DiskANN needs Cloud SQL compatibility validation first

3. **Graceful degradation**
   - Migrations check for vectorscale availability
   - Skip DiskANN index creation if extension missing
   - Rationale: Local dev may not have pgvectorscale; avoid blocking

4. **Runtime tuning exposed**
   - diskannSearchListSize configurable via env var
   - Allows recall/latency tradeoff adjustment
   - Rationale: Avoid redeployment for performance tuning experiments

## Implementation Notes

### Migration Order
1. Run 011_pgvectorscale_extension.sql first
2. Then run 012_streamingdiskann_index.sql
3. Both are idempotent (IF NOT EXISTS, DROP IF EXISTS)

### Cloud SQL Compatibility
**BLOCKER for production deployment:**
- pgvectorscale extension may not be available on Cloud SQL
- Need to verify: `SELECT * FROM pg_available_extensions WHERE name = 'vectorscale';`
- Fallback: Stick with HNSW if vectorscale unsupported

### Index Build Time
- StreamingDiskANN index creation is resource-intensive
- For 23,000 candidates: Estimated 5-15 minutes build time
- Run migration during low-traffic window

### Performance Expectations
- Research indicates 28x latency improvement
- HNSW: ~100ms for kNN search (baseline)
- DiskANN: ~3.5ms for kNN search (expected)
- Actual results depend on:
  - Cloud SQL instance specs
  - Concurrent query load
  - search_list_size parameter

## Testing & Verification

### Local Verification
```bash
# 1. Check if vectorscale extension is available
psql -h localhost -U postgres -d headhunter -c "SELECT * FROM pg_available_extensions WHERE name = 'vectorscale';"

# 2. Run extension migration
psql -h localhost -U postgres -d headhunter -f scripts/migrations/011_pgvectorscale_extension.sql

# 3. Run index migration
psql -h localhost -U postgres -d headhunter -f scripts/migrations/012_streamingdiskann_index.sql

# 4. Verify index exists
psql -h localhost -U postgres -d headhunter -c "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'search' AND tablename = 'candidate_embeddings';"

# 5. Build TypeScript
npm run build --prefix services/hh-search-svc
```

### A/B Testing Protocol
```bash
# Test HNSW (control)
export PGVECTOR_INDEX_TYPE=hnsw
# Run search queries, measure p95 latency

# Test DiskANN (experiment)
export PGVECTOR_INDEX_TYPE=diskann
export DISKANN_SEARCH_LIST_SIZE=100
# Run same queries, measure p95 latency

# Compare results
# Expected: DiskANN p95 < HNSW p95 / 28
```

### Health Check Validation
```bash
curl http://localhost:7102/health
# Response should include: "indexType": "hnsw" or "diskann"
```

## Next Phase Readiness

### Blockers Identified
1. **Cloud SQL vectorscale compatibility** - Must verify before production deployment
2. **Index build time** - Need maintenance window for initial index creation

### Concerns
1. **Memory overhead** - Dual indices consume more RAM; monitor Cloud SQL memory
2. **Write amplification** - Updates must maintain both indices; watch write latency

### Recommendations for Phase 11-02 (Connection Pooling)
- Monitor pool saturation during index build
- Increase poolMax temporarily if index creation causes connection spikes
- DiskANN's lower latency should reduce connection hold time

### Recommendations for Phase 11-05 (Performance Tracking)
- Add index type to performance metrics dashboard
- Track p95 latency breakdown: HNSW vs DiskANN
- Monitor index size growth over time

## Risk Assessment

### Low Risk
- TypeScript changes are non-breaking (new optional fields)
- Migrations are idempotent and safe to re-run
- Default behavior unchanged (HNSW)

### Medium Risk
- DiskANN index build may lock table briefly
- **Mitigation:** Run during low-traffic window, test on staging first

### High Risk
- Cloud SQL may not support pgvectorscale extension
- **Mitigation:** Verify extension availability before production deployment
- **Fallback:** Continue using HNSW if vectorscale unavailable

## Files Changed

### Created
- `scripts/migrations/011_pgvectorscale_extension.sql` (23 lines)
- `scripts/migrations/012_streamingdiskann_index.sql` (38 lines)

### Modified
- `services/hh-search-svc/src/config.ts` (+4 lines)
  - Added indexType and diskannSearchListSize to PgVectorConfig
  - Added environment variable parsing
- `services/hh-search-svc/src/pgvector-client.ts` (+9 lines, -2 lines)
  - Added index-aware runtime parameter setting
  - Added indexType to health check response
  - Added indexType to hybrid search logging

## Commits

1. **cfeed12** - feat(11-01): create pgvectorscale extension migration
2. **4f59f28** - feat(11-01): create StreamingDiskANN index migration
3. **aadd87b** - feat(11-01): add index type configuration and query-time tuning

## Deviations from Plan

None - plan executed exactly as written.

## Success Criteria Met

- [x] pgvectorscale extension migration file created
- [x] StreamingDiskANN index migration file created
- [x] Config supports PGVECTOR_INDEX_TYPE=diskann|hnsw
- [x] Query-time tuning applied based on index type
- [x] Logging includes index type for observability
- [x] TypeScript compiles without errors
- [x] Health check reports index type

## Performance Impact

**Latency Budget Allocation (Phase 11 Target: <500ms p95):**
- Vector search baseline (HNSW): ~100ms
- Vector search with DiskANN: ~3.5ms (28x improvement)
- **Latency savings:** ~96.5ms available for other pipeline stages

This creates substantial headroom for:
- Multi-signal scoring overhead
- Natural language query parsing (Phase 12)
- ML trajectory prediction (Phase 13)

## Environment Variables Added

```bash
# Index type selection (default: hnsw)
PGVECTOR_INDEX_TYPE=hnsw|diskann

# DiskANN search list size for runtime tuning (default: 100)
DISKANN_SEARCH_LIST_SIZE=100
```

## Documentation Updates Needed

- [ ] Update README.md with pgvectorscale installation instructions
- [ ] Document Cloud SQL extension verification steps
- [ ] Add A/B testing protocol to deployment runbook
- [ ] Update .env.example with new environment variables

---

**Phase 11-01 Status:** COMPLETE
**Next Plan:** 11-02 (Connection Pool Tuning)
**Duration:** 3 minutes 21 seconds
