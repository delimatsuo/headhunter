---
phase: 12-natural-language-search
plan: 01
subsystem: search
tags: [nlp, embeddings, cosine-similarity, intent-classification, semantic-router]

# Dependency graph
requires:
  - phase: 11-performance-foundation
    provides: embedding infrastructure, vector search foundation
provides:
  - NLP type definitions (IntentType, IntentRoute, ParsedQuery, etc.)
  - Vector utilities (cosineSimilarity, averageEmbeddings)
  - IntentRouter class with semantic routing
  - Intent classification for natural language queries
affects: [12-02-entity-extraction, 12-03-query-expansion, hh-search-svc routes]

# Tech tracking
tech-stack:
  added: []  # No new dependencies, pure TypeScript
  patterns:
    - Semantic router lite pattern for intent classification
    - Lazy initialization with concurrent call protection
    - Deterministic embedding-based routing (no LLM latency)

key-files:
  created:
    - services/hh-search-svc/src/nlp/types.ts
    - services/hh-search-svc/src/nlp/vector-utils.ts
    - services/hh-search-svc/src/nlp/intent-router.ts
    - services/hh-search-svc/src/nlp/__tests__/intent-router.spec.ts
  modified: []

key-decisions:
  - "Confidence threshold 0.6 default for intent classification"
  - "Lazy initialization with concurrent call protection via Promise"
  - "Portuguese utterances included for Brazilian recruiter support"

patterns-established:
  - "Semantic router pattern: classify via cosine similarity to route embeddings"
  - "Vector utils module for reusable math operations"
  - "NLP types module for shared type definitions across Phase 12"

# Metrics
duration: 3min
completed: 2026-01-25
---

# Phase 12 Plan 01: Semantic Router Lite Summary

**Embedding-based intent classification using cosine similarity with lazy route initialization and Portuguese support**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-25T20:59:20Z
- **Completed:** 2026-01-25T21:02:00Z
- **Tasks:** 3
- **Files created:** 4

## Accomplishments
- IntentRouter class with lazy initialization and concurrent call protection
- Three intent routes: structured_search, similarity_search, keyword_fallback
- Fast classification (<5ms for cosine similarity calculation)
- Portuguese utterances for Brazilian recruiter market support
- 19 passing unit tests covering initialization, classification, and edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1: Create NLP types and vector utilities** - `1bf0a33` (feat)
2. **Task 2: Implement IntentRouter with route definitions** - `ee702df` (feat)
3. **Task 3: Add unit tests for intent router** - `3edaafc` (test)

## Files Created/Modified
- `services/hh-search-svc/src/nlp/types.ts` - NLP type definitions (IntentType, IntentRoute, ParsedQuery, NLPConfig, ExtractedEntities)
- `services/hh-search-svc/src/nlp/vector-utils.ts` - Vector utilities (cosineSimilarity, averageEmbeddings)
- `services/hh-search-svc/src/nlp/intent-router.ts` - IntentRouter class with semantic routing
- `services/hh-search-svc/src/nlp/__tests__/intent-router.spec.ts` - Comprehensive unit tests (19 tests)

## Decisions Made
- **Confidence threshold 0.6:** Default threshold balances precision (avoid false positives) vs recall (catch valid queries)
- **Lazy initialization:** Route embeddings computed on first use to avoid startup latency impact
- **Portuguese support:** Added Brazilian Portuguese utterances for structured_search route to support recruiters in Brazil market

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all verification steps passed on first attempt.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- IntentRouter ready for integration with search routes
- Types and utilities ready for 12-02 (Entity Extraction)
- Entity extraction can build on ParsedQuery and ExtractedEntities types

---
*Phase: 12-natural-language-search*
*Completed: 2026-01-25*
