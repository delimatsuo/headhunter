# Codebase Concerns

**Analysis Date:** 2026-01-24

## Tech Debt

**Pagination Implementation in Firestore Service:**
- Issue: Quick Find pagination is incomplete - uses fixed batches and `startAfter()` is commented out as unimplemented
- Files: `headhunter-ui/src/services/firestore-direct.ts` (line 203)
- Impact: Client-side searches cannot reliably paginate through large result sets; pagination may be incomplete or incorrect
- Fix approach: Implement proper cursor-based pagination using `startAfter()` with document snapshots; add pagination tests

**Multiple Schema Initialization Files:**
- Issue: Multiple overlapping PostgreSQL schema files exist (`pgvector_schema.sql`, `pgvector_schema_init.sql`, `setup_database_schemas.sql`, etc.)
- Files: `scripts/pgvector_schema.sql`, `scripts/pgvector_schema_init.sql`, `scripts/setup_database_schemas.sql`, `scripts/setup_database_schemas_clean.sql`
- Impact: Unclear which schema is authoritative; risk of applying wrong migrations or schema versions in production
- Fix approach: Consolidate into single authoritative versioned migration file; document migration order and dependencies

**JSON Parsing Fragility in Reranking:**
- Issue: Two-pass reranking workaround suggests unstable JSON parsing from LLM responses
- Files: `functions/src/gemini-reranking-service.ts` (line 845)
- Impact: Reranking can fail intermittently when LLM returns malformed JSON; requires retry logic
- Fix approach: Implement strict JSON validation before parsing; add fallback parsing with lenient mode; increase test coverage for edge cases

**Debug Logging Left in Production Code:**
- Issue: Extensive `console.log('[DEBUG]')` statements in Redis client and other services
- Files: `services/hh-rerank-svc/src/redis-client.ts` (lines 72-130), `cloud_run_worker/candidate_processor.py` (lines 190-210)
- Impact: Verbose logging degrades performance and security; logs may contain sensitive data
- Fix approach: Replace with proper structured logging via pino; use log levels (debug/info/warn) appropriately; remove before production

**Missing Email Column Migration:**
- Issue: TODO comment indicates email column may not exist in sourcing.candidates table
- Files: `functions/src/pgvector-client.ts` (line 763)
- Impact: Email-based enrichment or lookups could silently fail
- Fix approach: Verify email column exists in sourcing schema; add migration if missing; update enrichment pipeline

**Dashboard Error Handling Gaps:**
- Issue: Error notification logic is stubbed out with TODO comment
- Files: `headhunter-ui/src/components/Dashboard/Dashboard.tsx` (line 442)
- Impact: Dashboard errors are silently swallowed; users see no feedback when operations fail
- Fix approach: Implement proper error notifications via snackbar/alert; surface actionable messages to users

## Known Bugs

**Specialty Filter Mismatch in Search:**
- Symptoms: Search results missing candidates with correct specialties; filtering inconsistent between frontend and backend
- Files: `functions/src/engines/legacy-engine.ts` (line 131), `functions/src/vector-search.ts` (line 43-44)
- Trigger: Searching for specialized roles (backend, frontend, ML) returns incomplete results
- Workaround: Use keyword search instead of specialty filtering
- Status: Recently patched (commit f634df8) - needs post-deployment testing

**PostgreSQL Connection SSL Configuration Issues:**
- Symptoms: Intermittent "connection refused" or SSL handshake errors to Cloud SQL
- Files: `functions/src/engines/legacy-engine.ts` (lines 32-54), `services/hh-search-svc/src/index.ts` (line 95)
- Trigger: Non-localhost connections without proper SSL setup fail; localhost connections sometimes require explicit SSL disable
- Workaround: Set `PGVECTOR_SSL_MODE=disable` for local dev; auto-detect for Cloud SQL
- Status: Partially fixed (commit 9ef9bf4) - SSL auto-detection logic may need refinement

**Two-Pass Reranking JSON Parse Failures:**
- Symptoms: Reranking crashes with JSON parsing errors; requires manual retry
- Files: `functions/src/gemini-reranking-service.ts` (line 845)
- Trigger: Gemini returns multiline JSON or malformed responses
- Workaround: Two-pass reranking catches failures and retries (commit 845ace0)
- Status: Mitigated but not root-fixed; LLM response validation needed

**Quick Find Role Extraction Inaccuracy:**
- Symptoms: Role extraction from job titles returns wrong or partial titles
- Files: `headhunter-ui/src/components/Search/SearchResults.tsx`
- Trigger: Non-standard job titles or role names not in training data
- Workaround: Show extracted role with similarity badge removed (commit d5e5e94)
- Status: Improved but still imprecise - consider NER model

**N+1 Query Pattern in Vector Search:**
- Symptoms: Searching returns candidates but then performs individual Firestore lookups per candidate for org filtering
- Files: `functions/src/vector-search.ts` (lines 509-516, 577-584)
- Trigger: Any search with org_id filter in multi-tenant setup
- Impact: Database load increases linearly with result count; slow searches for large result sets
- Workaround: Batch candidates and use collection group queries (not currently implemented)
- Fix approach: Implement batch Firestore reads or move org_id to PostgreSQL

## Security Considerations

**Ella Organization Bypass in Multi-Tenant Filtering:**
- Risk: `org_ella_main` is hardcoded bypass allowing access to all candidates regardless of tenant
- Files: `headhunter-ui/src/services/firestore-direct.ts` (lines 182-183), `functions/src/vector-search.ts` (lines 506-507)
- Current mitigation: Token-based org_id validation from JWT claims
- Recommendations:
  - Add audit logging for all `org_ella_main` queries
  - Implement fine-grained access control rules in Firestore security rules
  - Document this exception in security policy
  - Consider time-limiting Ella bypass or requiring explicit approval

**Unvalidated User Input in Search Queries:**
- Risk: Search queries passed directly to Gemini without sanitization
- Files: `functions/src/gemini-reranking-service.ts`, `functions/src/vector-search.ts`
- Current mitigation: Gemini API itself filters dangerous content
- Recommendations:
  - Add input validation/sanitization before sending to LLM
  - Rate-limit search requests per user
  - Log suspicious search patterns

**JWT Validation Complexity:**
- Risk: Multiple ISSUER_CONFIGS paths and conditional token validation logic
- Files: `services/common/src/config.ts` (lines 305-320)
- Current mitigation: ALLOWED_TOKEN_ISSUERS environment variable validation
- Recommendations:
  - Add comprehensive JWT validation tests
  - Document all supported issuer patterns
  - Add monitoring for failed token validations
  - Implement token rotation policy

**Firestore Security Rules Not Documented:**
- Risk: Security model relies on undocumented Firestore rules
- Files: Firestore rules not in codebase (emulator only)
- Current mitigation: Code-level filtering via org_id checks
- Recommendations:
  - Export and version control Firestore security rules
  - Document rule intent and enforcement
  - Test rules in staging before production deploy

## Performance Bottlenecks

**Dashboard Data Fetching with Fallback Chain:**
- Problem: Dashboard makes parallel API + Firestore calls, then falls back to API again if Firestore fails
- Files: `headhunter-ui/src/components/Dashboard/Dashboard.tsx` (lines 107-139)
- Cause: Multiple overlapping data sources without clear priority; unnecessary redundancy
- Current latency: ~2-5 seconds for dashboard load
- Improvement path:
  - Choose single source of truth (API or Firestore) per data type
  - Remove unnecessary fallback chains
  - Implement request deduplication/caching
  - Target: <1 second load time

**N+1 Firestore Queries in Vector Search Results:**
- Problem: Each search result triggers individual Firestore document lookup for org filtering
- Files: `functions/src/vector-search.ts` (lines 509-516)
- Cause: Org_id filtering not available in pgvector; must check Firestore per candidate
- Current impact: +50-500ms per search depending on result count
- Improvement path:
  - Add org_id column to sourcing.candidates in PostgreSQL
  - Move filtering to SQL WHERE clause
  - Eliminate Firestore round-trips
  - Target: Consistent <100ms latency

**Search Service Dependency Initialization Timeout:**
- Problem: Service waits for all dependencies (pgvector, Redis, Embed, Rerank) in sequence
- Files: `services/hh-search-svc/src/index.ts` (lines 81-150)
- Cause: Linear initialization order without parallelization
- Current latency: ~15+ seconds for full initialization
- Improvement path:
  - Parallelize independent dependency initialization (pgvector + Redis + Embed)
  - Rerank optional - can initialize separately
  - Add async health endpoints that report partial readiness
  - Target: <5 seconds to ready state

**Redis Memory Inefficiency in Reranking Cache:**
- Problem: Rerank cache stores full candidate objects when only IDs and scores needed
- Files: `services/hh-rerank-svc/src/redis-client.ts` (lines 113-130)
- Cause: Serializing entire cache payloads without compression
- Current impact: High Redis memory usage for large result sets
- Improvement path:
  - Store only score data, not full objects
  - Implement Redis compression for large payloads
  - Use pipelining for batch operations
  - Target: 50% memory reduction

## Fragile Areas

**Vector Search Engine Selection Logic:**
- Files: `functions/src/index.ts` (engine routing), `functions/src/engines/legacy-engine.ts`
- Why fragile: Job classification failure causes entire search to fail with no fallback
- Lines 110-121 in legacy-engine.ts show FAIL FAST approach - any classification error throws
- Safe modification:
  - Always have a fallback classification (generic/mid level)
  - Test all edge cases: malformed job descriptions, empty titles, etc.
  - Add circuit breaker for classification service
  - Implement graceful degradation mode
- Test coverage: Search classification tests in `functions/src/__tests__/api-endpoints.test.ts` (900 lines) need expanded coverage

**PostgreSQL Connection Pool Lifecycle:**
- Files: `functions/src/engines/legacy-engine.ts` (lines 32-54), `services/hh-embed-svc/src/pgvector-client.ts`
- Why fragile: Global pool singleton created on first use; no cleanup on errors; can leak connections
- Safe modification:
  - Always call `pool.end()` in cleanup handlers
  - Test connection exhaustion scenarios
  - Add max retry limit for broken connections
  - Monitor pool usage metrics
- Test coverage: Limited pool error tests; needs connection failure simulation

**Dashboard Stats Calculation with Sampling:**
- Files: `headhunter-ui/src/services/firestore-direct.ts` (lines 99-130)
- Why fragile: Stats calculated from first 500 documents only; skewed for large datasets
- Safe modification:
  - Use count aggregation for totals (already done)
  - Document sampling limitation in UI
  - Either sample larger set or use random sampling with weighted stats
  - Add warning when dataset > 500 docs
- Test coverage: No tests for large dataset scenarios

**Legacy Function-Based Retrieval in Executive Search:**
- Files: `functions/src/engines/legacy-engine.ts` (lines 148-200)
- Why fragile: Executive search relies on title matching which can miss variations
- Safe modification:
  - Add fuzzy matching for similar titles
  - Test with actual LinkedIn title variations
  - Fall back to level-based matching if function match fails
  - Add debug logging for title matching decisions
- Test coverage: Executive search tests minimal; needs real-world examples

## Scaling Limits

**PostgreSQL Connection Pool Per Instance:**
- Current capacity: 10-20 connections per service instance
- Limit: Each Cloud Run instance reserves pool; total database connections = instances × pool size
- At 50 instances: 500-1000 concurrent connections (Cloud SQL standard has 100 default)
- Scaling path:
  - Implement centralized connection pooling (e.g., PgBouncer)
  - Use connection pooling mode in Cloud SQL
  - Monitor `pg_stat_activity` for connection count
  - Auto-scale based on connection ratio

**Firestore N+1 Query Pattern:**
- Current capacity: ~100 results with org filtering = ~100-200 Firestore reads per search
- Limit: Firestore 50k reads/day plan = ~500 searches max before hitting limits
- Scaling path:
  - Move org_id to PostgreSQL (eliminates N+1)
  - Implement batch Firestore reads (max 100 docs per batch)
  - Cache org_id mappings in Redis
  - Target: Single SQL WHERE clause instead of Firestore loop

**Gemini Reranking Throughput:**
- Current capacity: Reranking ~50 candidates per request; Gemini quota ~100 QPM
- Limit: At 20 searches/minute with 50 candidates = 1000 candidates/min = 600k candidates/hour
- Scaling path:
  - Implement result caching by job description hash
  - Use batch reranking endpoint if available
  - Fall back to Redis-based scoring when Gemini quota exhausted
  - Monitor quota usage and implement backpressure

**Redis Cache Size for Reranking:**
- Current capacity: Default Redis 6GB instance
- Limit: Storing full candidate payloads; cache hit rate must stay high (target 1.0) to justify memory
- Scaling path:
  - Reduce payload size (store only scores)
  - Implement TTL-based eviction
  - Move to larger Redis instance or cluster
  - Monitor cache hit rate; if <0.8, investigate access patterns

## Dependencies at Risk

**Firebase Admin SDK (v12.0.0):**
- Risk: Major version; breaking changes possible in future updates
- Current use: Firestore initialization, token verification, admin operations
- Impact: If updated, code using removed APIs will break silently
- Migration plan:
  - Lock to specific patch version, not caret (^)
  - Run comprehensive integration tests before upgrading
  - Use Firestore client library directly for reads (more stable)

**Gemini API Integration (no versioning in code):**
- Risk: API calls use latest Gemini model; no pinned version
- Current use: `gemini-embedding-001` for embeddings, Gemini for reranking
- Impact: Model changes could degrade quality or change output format
- Migration plan:
  - Pin `gemini-1.5-pro` or equivalent with explicit version
  - Add model versioning config
  - Test embedding and reranking output with new models before deploy
  - Implement fallback model strategy

**pg (PostgreSQL Client v8.x):**
- Risk: Connection pool implementation fragile; version mismatch with pgvector types
- Current use: All PostgreSQL access in services and functions
- Impact: Pool exhaustion or connection leaks under high load
- Migration plan:
  - Evaluate upgrading to pg v9 if available and compatible
  - Add connection pool metrics and alerts
  - Implement graceful degradation when pool exhausted

**Fastify Framework (v4.26.2):**
- Risk: Plugin ecosystem evolving; some plugins may be unmaintained
- Current use: HTTP server for all services; under-pressure plugin for health checks
- Impact: Security vulnerabilities in plugins; potential performance issues
- Migration plan:
  - Audit all Fastify plugins for maintenance status
  - Keep Fastify updated; security patches critical
  - Test plugin compatibility when upgrading
  - Consider moving away from `@fastify/under-pressure` if no longer maintained

## Missing Critical Features

**Structured Logging in Frontend:**
- Problem: Frontend uses `console.log()` everywhere; logs not captured in Cloud Logging
- Blocks: Cannot debug production issues; no audit trail for user actions
- Current state: `headhunter-ui/src/services/firestore-direct.ts` has extensive console logs
- Impact: Ops cannot diagnose search failures; security cannot audit data access
- Implementation approach:
  - Integrate pino client SDK in React app
  - Send logs to Cloud Logging via API endpoint
  - Implement structured fields: tenantId, userId, traceId
  - Target: All user actions logged with context

**Performance Metrics Export:**
- Problem: Search latency, rerank cache hit rate not exposed to monitoring system
- Blocks: Cannot track SLO compliance; cannot detect performance regressions
- Current state: Performance data in memory in services; no export
- Implementation approach:
  - Export Prometheus metrics from all services
  - Dashboard in Cloud Monitoring for latency distribution
  - Alert on cache hit rate <0.98, p95 latency >1.2s
  - Integration tests validate baseline metrics

**Database Migration System:**
- Problem: Multiple schema files but no versioning or rollback capability
- Blocks: Cannot safely roll back failed migrations; unclear migration order
- Current state: Ad-hoc schema files in `scripts/migrations/`
- Implementation approach:
  - Implement numbered migration system (001_*, 002_*, etc.)
  - Add migration lock table to prevent concurrent runs
  - Version control migration checksums
  - Test rollback procedures before production

**Multi-Tenant Isolation Tests:**
- Problem: Org_id filtering is critical security feature but has no dedicated test suite
- Blocks: Cannot verify tenants cannot access each other's data
- Current state: Ad-hoc filtering in code; no comprehensive test
- Implementation approach:
  - Test suite covering org_id in: searches, results, dashboard stats
  - Test Ella org bypass specifically
  - Test token-based org_id extraction
  - Add security regression tests for all isolation layers

## Test Coverage Gaps

**Vector Search Integration Tests:**
- Untested areas: Specialty filtering with multiple specialties, org_id filtering with pgvector fallback
- Files: `functions/src/__tests__/api-endpoints.test.ts` (900 lines)
- Risk: Specialty filtering bug (commit f634df8) suggests test gaps
- Priority: High - search is critical path

**Redis Connection Resilience:**
- Untested areas: Connection failures, pool exhaustion, timeout scenarios
- Files: `services/hh-search-svc/src/redis-client.ts` has no dedicated tests
- Risk: Silent cache misses or degradation
- Priority: High - cache is performance critical

**Firestore Pagination Edge Cases:**
- Untested areas: Large result sets (>10k), pagination with filtering, concurrent pagination
- Files: `headhunter-ui/src/services/firestore-direct.ts` (lines 172-210)
- Risk: Data loss or duplicate results when paginating
- Priority: Medium - affects large customer use cases

**PostgreSQL Migration Rollback:**
- Untested areas: Rolling back 010_firestore_migration_phase_a.sql, reversing specialty column addition
- Files: All in `scripts/migrations/`
- Risk: Cannot recover from migration failure
- Priority: Medium - needed for production safety

**Error Boundary Coverage in Dashboard:**
- Untested areas: Component error recovery, failed data loads, partial failures
- Files: `headhunter-ui/src/components/Dashboard/Dashboard.tsx` (1031 lines)
- Risk: Silent failures, blank dashboard without error message
- Priority: Medium - affects user experience

---

*Concerns audit: 2026-01-24*
