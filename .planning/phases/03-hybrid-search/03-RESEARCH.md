# Phase 3: Hybrid Search - Research

**Researched:** 2026-01-24
**Domain:** Hybrid Search / RRF Fusion / PostgreSQL Full-Text Search
**Confidence:** HIGH

## Summary

Phase 3 implements true hybrid search combining semantic vector similarity with exact keyword matching. The system already has substantial hybrid search infrastructure in place, but **the text search (BM25) component is not contributing to results** - textScore is always 0. This phase fixes that gap and implements proper Reciprocal Rank Fusion (RRF).

The existing `hh-search-svc/src/pgvector-client.ts` already includes a hybrid search query structure with vector and text candidates, but the fusion uses weighted linear combination instead of RRF. Additionally, the `sourcing` schema has FTS infrastructure (tsvector, GIN index, Portuguese dictionary) but is not being utilized in the unified search path.

**Primary recommendation:** Fix the text search contribution (textScore=0 issue), implement RRF fusion with configurable k parameter, and unify the FTS infrastructure across schemas. No new extensions required - PostgreSQL's native ts_rank_cd provides sufficient ranking for hybrid fusion.

## Standard Stack

The system already has all required infrastructure. No new libraries or extensions needed.

### Core (Already Deployed)
| Component | Version | Purpose | Status |
|-----------|---------|---------|--------|
| pg + pgvector | 0.5.1+ | Vector similarity search | Working |
| PostgreSQL FTS | native | tsvector + ts_rank_cd | Exists but textScore=0 |
| GIN Index | native | Full-text search acceleration | Deployed |
| HNSW Index | pgvector | Vector similarity acceleration | Deployed |

### Supporting (Already Deployed)
| Component | Purpose | Status |
|-----------|---------|--------|
| Portuguese dictionary | Language-specific stemming | Configured |
| unaccent extension | Accent normalization for PT-BR | Deployed |
| Trigger functions | Auto-update search_document | Working |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ts_rank_cd | ParadeDB pg_search (true BM25) | Rust extension, not available in Cloud SQL |
| ts_rank_cd | pg_textsearch (Tiger Data) | External extension, deployment complexity |
| Weighted fusion | RRF | RRF is simpler, no normalization needed |

**No new dependencies required** - PostgreSQL native FTS with ts_rank_cd is sufficient when combined with RRF fusion. True BM25 extensions are not available in managed Cloud SQL environments.

## Architecture Patterns

### Current Data Flow (Partial - textScore=0)

```
Search Query
     |
     v
[1] Generate Embedding (Gemini)              -> 768-dim vector
     |
     v
[2] Vector Search (pgvector HNSW)            -> top N by cosine similarity
     |
     v
[3] Text Search (PostgreSQL FTS)             -> SKIPPED (textScore=0)
     |
     v
[4] Weighted Combination (0.65v + 0.35t)     -> Effectively just vector
     |
     v
[5] Results
```

**Root Cause of textScore=0:** Analysis of `hh-search-svc/src/pgvector-client.ts` lines 187-228 shows:
1. Text candidates CTE exists but may not match due to:
   - Empty or malformed `textQuery` parameter
   - Mismatched dictionary configuration
   - Missing or sparse `search_document` data
2. The `sourcing.embeddings` query path (lines 370-450) doesn't include FTS at all

### Target Data Flow (RRF Fusion)

```
Search Query
     |
     +----------------+----------------+
     |                                 |
     v                                 v
[1] Vector Search                 [2] Text Search
    (pgvector HNSW)                   (ts_rank_cd)
    ORDER BY similarity               ORDER BY text_rank
    LIMIT 100                         LIMIT 100
     |                                 |
     v                                 v
  Assign ranks                     Assign ranks
  (1, 2, 3, ...)                  (1, 2, 3, ...)
     |                                 |
     +----------------+----------------+
                      |
                      v
               [3] RRF Fusion
               score = SUM(1 / (k + rank))
               k = 60 (configurable)
                      |
                      v
               [4] Final Ranking
               ORDER BY rrf_score DESC
                      |
                      v
               Top 50 Results
```

### Key Architectural Principle

**RRF > Weighted Linear Combination**
- Current: `hybrid_score = (0.65 * vector_score) + (0.35 * text_score)`
- Problem: Requires score normalization, different scales cause imbalance
- RRF: `rrf_score = 1/(k+rank_vector) + 1/(k+rank_text)`
- Benefit: Only uses rank positions, no normalization needed

## Recommended Project Structure

No new files needed. Changes are in existing files:

```
services/hh-search-svc/src/
├── config.ts           # Add RRF_K_PARAMETER env var
├── pgvector-client.ts  # Rewrite hybridSearch to use RRF CTEs
├── types.ts            # Add rrfScore field to results (already has vectorScore, textScore)
└── routes.ts           # No changes needed
```

### Pattern: RRF SQL Implementation

**Source:** [ParadeDB Hybrid Search Guide](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual), [Jonathan Katz pgvector hybrid search](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/)

```sql
WITH vector_candidates AS (
  SELECT
    candidate_id,
    ROW_NUMBER() OVER (ORDER BY embedding <=> $2 ASC) AS vector_rank,
    1 - (embedding <=> $2) AS vector_score
  FROM {schema}.{embeddings_table}
  WHERE tenant_id = $1
  ORDER BY embedding <=> $2 ASC
  LIMIT $3
),
text_candidates AS (
  SELECT
    candidate_id,
    ROW_NUMBER() OVER (ORDER BY ts_rank_cd(search_document, plainto_tsquery('portuguese', $4)) DESC) AS text_rank,
    ts_rank_cd(search_document, plainto_tsquery('portuguese', $4)) AS text_score
  FROM {schema}.{profiles_table}
  WHERE tenant_id = $1
    AND search_document @@ plainto_tsquery('portuguese', $4)
  ORDER BY text_score DESC
  LIMIT $3
),
rrf_scored AS (
  SELECT
    COALESCE(v.candidate_id, t.candidate_id) AS candidate_id,
    COALESCE(1.0 / ($5 + v.vector_rank), 0) AS rrf_vector,
    COALESCE(1.0 / ($5 + t.text_rank), 0) AS rrf_text,
    COALESCE(1.0 / ($5 + v.vector_rank), 0) + COALESCE(1.0 / ($5 + t.text_rank), 0) AS rrf_score,
    v.vector_score,
    t.text_score
  FROM vector_candidates v
  FULL OUTER JOIN text_candidates t ON v.candidate_id = t.candidate_id
)
SELECT
  rs.candidate_id,
  rs.rrf_score,
  rs.vector_score,
  rs.text_score,
  cp.*
FROM rrf_scored rs
JOIN {schema}.{profiles_table} cp ON cp.candidate_id = rs.candidate_id
WHERE cp.tenant_id = $1
ORDER BY rs.rrf_score DESC
LIMIT $6
OFFSET $7;
```

**Parameters:**
- $1: tenant_id
- $2: query embedding vector
- $3: per-method limit (100)
- $4: text query string
- $5: RRF k parameter (default 60)
- $6: final limit
- $7: offset

### Anti-Patterns to Avoid

- **Score Multiplication:** Don't multiply vector_score * text_score - products of small numbers become tiny
- **Weighted Sum Without Normalization:** Current approach, fails when scales differ
- **Intersection Instead of Union:** Using INNER JOIN misses candidates found by only one method
- **Low Limits Per Method:** Limiting to 20 per method may miss good candidates; use 100+

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| BM25 scoring | Custom PL/pgSQL BM25 | ts_rank_cd + RRF | RRF compensates for ts_rank_cd limitations |
| Score normalization | Min-max scaling | RRF (rank-based) | RRF needs no normalization |
| Accent handling | String replacement | unaccent extension | Already deployed, handles Portuguese accents |
| Synonym expansion | Custom synonym table | Embedding similarity | Vector search handles semantics |

**Key insight:** ts_rank_cd is not true BM25 (lacks IDF, document length normalization), but RRF fusion compensates by focusing on rank positions rather than absolute scores. The semantic vector search catches what FTS misses, and FTS catches exact keyword matches that vector search might rank lower.

## Common Pitfalls

### Pitfall 1: textScore Always 0
**What goes wrong:** FTS query returns no matches, textScore=0 for all candidates
**Why it happens:**
- Empty `textQuery` passed to SQL
- search_document column not populated
- Dictionary mismatch (e.g., 'simple' vs 'portuguese')
- Query contains only stopwords
**How to avoid:**
- Verify search_document population: `SELECT COUNT(*) FROM sourcing.candidates WHERE search_document IS NOT NULL`
- Use same dictionary in query and index
- Log the plainto_tsquery output for debugging
**Warning signs:** All results have textScore=0, all scores are purely vector-based

### Pitfall 2: FULL OUTER JOIN Explosion
**What goes wrong:** FULL OUTER JOIN on large result sets causes memory issues
**Why it happens:** Trying to join millions of candidates instead of top-N
**How to avoid:**
- Always LIMIT both CTEs to reasonable numbers (100-200)
- Use UNION ALL approach as fallback if needed
- Monitor query execution plans
**Warning signs:** Slow queries (>1s), high memory usage, timeouts

### Pitfall 3: Sourcing Schema FTS Not Used
**What goes wrong:** Code paths query `sourcing.embeddings` directly without FTS
**Why it happens:** Legacy query in pgvector-client.ts lines 370-430 for sourcing schema
**Current code (functions/src/pgvector-client.ts):**
```typescript
if (isSourcingSchema) {
  sql = `
   SELECT e.candidate_id::text as candidate_id,
          1 - (e.embedding <=> $1) as similarity,
          -- NO FTS HERE
          e.model_version, 'default' as chunk_type
   FROM sourcing.embeddings e
   JOIN sourcing.candidates c ON c.id = e.candidate_id
  `;
}
```
**How to avoid:**
- Add text_candidates CTE for sourcing schema
- Join with sourcing.candidates for search_document
- Use RRF fusion for both schemas

### Pitfall 4: RRF k Parameter Too High or Low
**What goes wrong:** k=60 may not be optimal for this dataset
**Research findings:**
- k too low (<20): Top ranks dominate excessively
- k too high (>100): Rankings become nearly uniform
- Standard: k=60 works well in most cases
**How to avoid:**
- Make k configurable via env var
- Start with k=60, tune based on A/B testing
- Monitor score distribution across results

### Pitfall 5: Portuguese Dictionary Edge Cases
**What goes wrong:** Searches fail for English tech terms
**Why it happens:** Portuguese stemmer may not handle English words correctly
**Current config:** `PG_FTS_DICTIONARY = 'portuguese'`
**How to avoid:**
- Consider dual-dictionary approach for mixed content
- Verify tech terms appear in search_document properly
- Test with common search patterns: "Python developer", "Senior engineer AWS"

## Code Examples

### Example 1: Verify FTS Infrastructure
```sql
-- Check search_document population across schemas
SELECT
  'sourcing' as schema,
  COUNT(*) as total,
  COUNT(search_document) as has_fts,
  COUNT(CASE WHEN length(search_document::text) > 20 THEN 1 END) as has_content
FROM sourcing.candidates
WHERE deleted_at IS NULL;

SELECT
  'search' as schema,
  COUNT(*) as total,
  COUNT(search_document) as has_fts,
  COUNT(CASE WHEN length(search_document::text) > 20 THEN 1 END) as has_content
FROM search.candidate_profiles;
```

### Example 2: Test FTS Query
```sql
-- Verify Portuguese FTS works for a sample query
SELECT
  id,
  first_name || ' ' || last_name as name,
  headline,
  ts_rank_cd(search_document, plainto_tsquery('portuguese', 'python senior')) as text_score
FROM sourcing.candidates
WHERE search_document @@ plainto_tsquery('portuguese', 'python senior')
ORDER BY text_score DESC
LIMIT 10;
```

### Example 3: RRF Score Function
**Source:** [Jonathan Katz pgvector hybrid search](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/)

```sql
-- Create reusable RRF score function
CREATE OR REPLACE FUNCTION rrf_score(rank int, rrf_k int DEFAULT 60)
RETURNS numeric
LANGUAGE SQL
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT COALESCE(1.0 / ($1 + $2), 0.0);
$$;

-- Usage in query
SELECT
  candidate_id,
  rrf_score(vector_rank) + rrf_score(text_rank) as rrf_score
FROM ...
```

### Example 4: Configurable RRF k Parameter

```typescript
// In config.ts
const search: SearchRuntimeConfig = {
  vectorWeight: parseNumber(process.env.SEARCH_HYBRID_VECTOR_WEIGHT, 0.65),
  textWeight: parseNumber(process.env.SEARCH_HYBRID_TEXT_WEIGHT, 0.35),
  minSimilarity: parseNumber(process.env.SEARCH_MIN_SIMILARITY, 0.25),
  rrfK: parseNumber(process.env.SEARCH_RRF_K, 60), // NEW
  maxResults: Math.max(1, parseNumber(process.env.SEARCH_MAX_RESULTS, 50)),
  // ...
};
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Weighted linear fusion | RRF fusion | 2023-2024 | Standard in modern hybrid search |
| Single-dictionary FTS | Multi-dictionary | 2024+ | Better for multilingual content |
| ts_rank | ts_rank_cd | Long established | Covers document density |
| Pure vector search | Hybrid search | 2022+ | 8-15% accuracy improvement |

**Deprecated/outdated:**
- ParadeDB pg_search: Not available in Cloud SQL managed environments
- IVFFlat index: Already upgraded to HNSW in migration 007

**Current best practice:**
- RRF fusion with k=60 is production-proven across Elasticsearch, OpenSearch, and PostgreSQL implementations
- FULL OUTER JOIN or UNION ALL approaches both work; UNION ALL is slightly simpler
- ts_rank_cd is sufficient when combined with RRF - true BM25 is ideal but not available in Cloud SQL

## Implementation Priorities

### Priority 1: Fix textScore=0 (HIGH)
**Files:** `services/hh-search-svc/src/pgvector-client.ts`
**Actions:**
1. Verify textQuery is passed correctly
2. Add logging for FTS query results
3. Check search_document population in production
4. Ensure dictionary matches ('portuguese' everywhere)

### Priority 2: Implement RRF Fusion (HIGH)
**Files:** `services/hh-search-svc/src/pgvector-client.ts`, `services/hh-search-svc/src/config.ts`
**Actions:**
1. Add rrfK config parameter
2. Rewrite hybridSearch SQL to use RRF CTEs
3. Change from weighted sum to rank-based RRF
4. Add FULL OUTER JOIN for union of results

### Priority 3: Unify Sourcing Schema FTS (MEDIUM)
**Files:** `functions/src/pgvector-client.ts`
**Actions:**
1. Add FTS CTE to sourcing schema query path
2. Use sourcing.candidates.search_document
3. Apply same RRF pattern

### Priority 4: Add Configuration (MEDIUM)
**Files:** `services/hh-search-svc/src/config.ts`
**Actions:**
1. Add SEARCH_RRF_K env var (default 60)
2. Add SEARCH_PER_METHOD_LIMIT env var (default 100)
3. Document configuration in README

## Open Questions

### 1. search_document Population Rate
**What we know:** Migration 007 backfilled sourcing.candidates.search_document
**What's unclear:** Current population percentage across 23,000+ candidates
**Recommendation:**
- Run audit query before implementation
- If <80% populated, prioritize backfill

### 2. English vs Portuguese Terms
**What we know:** Most tech terms are English, candidate data is Portuguese
**What's unclear:** How well Portuguese dictionary handles "Python", "AWS", etc.
**Recommendation:**
- Test with common tech stack searches
- Consider 'simple' dictionary for tech terms if issues found

### 3. Weighted RRF
**What we know:** Standard RRF weights both methods equally
**What's unclear:** Whether we should weight vector higher (e.g., 0.7) or text higher
**Recommendation:**
- Start with equal weights (standard RRF)
- Expose as config for A/B testing
- Current config has vectorWeight=0.65, textWeight=0.35 which can inform initial weighted RRF

## Success Criteria

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| textScore > 0 | 0% of results | 50%+ of results | Log search responses |
| Exact keyword matches | Missing | Present | Search for "AWS Solutions Architect" |
| Semantic matches | Working | Still working | Search for "K8s" returns "Kubernetes" |
| RRF k configurable | No | Yes | SEARCH_RRF_K env var |
| Search latency | <1s | <1s (no regression) | Timings in response |

## Sources

### Primary (HIGH confidence)
- `services/hh-search-svc/src/pgvector-client.ts` - Current hybrid search implementation
- `services/hh-search-svc/src/config.ts` - Current configuration
- `scripts/migrations/007_sourcing_search_unification.sql` - FTS infrastructure
- `docs/hybrid-search-validation-report.md` - Validates textScore=0 issue

### Secondary (MEDIUM confidence)
- [ParadeDB Hybrid Search Guide](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual) - RRF SQL patterns
- [Jonathan Katz pgvector hybrid search](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/) - RRF implementation
- [OpenSearch RRF](https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/) - RRF theory

### Tertiary (LOW confidence)
- ts_rank_cd vs BM25 comparison - WebSearch findings, need to validate with actual data

## Metadata

**Confidence breakdown:**
- RRF implementation: HIGH - Standard pattern, well-documented
- textScore=0 fix: HIGH - Root cause identified in code and docs
- PostgreSQL FTS: HIGH - Native feature, well-tested
- Performance impact: MEDIUM - Needs validation with production data

**Research date:** 2026-01-24
**Valid until:** Until major changes to search architecture

---

## Implementation Notes for Planner

### Dependency Chain

1. **Audit FTS data** - Must verify search_document population first
2. **Fix textScore=0** - Unblocks RRF implementation
3. **Implement RRF** - Core change
4. **Add configuration** - Enables tuning
5. **Update sourcing schema** - Unifies both code paths

### Testing Strategy

1. **Unit test RRF function:**
   ```typescript
   expect(rrfScore(1, 60)).toBe(1/61);
   expect(rrfScore(2, 60)).toBe(1/62);
   ```

2. **Integration test hybrid search:**
   - Query "AWS Solutions Architect" - should have textScore > 0
   - Query "K8s" - should return "Kubernetes" candidates (vector match)
   - Query common terms - should have both scores > 0

3. **Regression test:**
   - Existing searches should still return relevant results
   - Latency should not increase significantly (<100ms)

### Estimated Effort

- FTS audit and fix: 2-3 hours
- RRF implementation: 3-4 hours
- Configuration: 1 hour
- Testing: 2-3 hours
- Documentation: 1 hour
- Total: 9-12 hours

### Risk Mitigation

- **Feature flag:** `ENABLE_RRF=true/false` to toggle between weighted sum and RRF
- **Gradual rollout:** Deploy behind flag, verify with shadow traffic
- **Fallback:** Keep existing weighted sum code path as backup
