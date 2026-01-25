---
phase: 12-natural-language-search
plan: 02
subsystem: nlp
tags: [together-ai, json-mode, entity-extraction, llm, nlp]

# Dependency graph
requires:
  - phase: 12-01
    provides: NLP types (ExtractedEntities)
provides:
  - EntityExtractor class with Together AI JSON mode
  - Hallucination filtering for skill extraction
  - Portuguese term normalization (pleno -> mid, gerente -> manager)
  - Abbreviation matching (js -> JavaScript, k8s -> Kubernetes)
affects: [12-03-query-expander, 12-04-query-parser, search-service integration]

# Tech tracking
tech-stack:
  added: [together-ai@0.33.0]
  patterns: [LLM JSON mode extraction, hallucination filtering, graceful fallback]

key-files:
  created:
    - services/hh-search-svc/src/nlp/entity-extractor.ts
    - services/hh-search-svc/src/nlp/__tests__/entity-extractor.spec.ts
  modified:
    - services/hh-search-svc/package.json

key-decisions:
  - "150ms timeout for extraction (per RESEARCH.md latency budget)"
  - "Post-extraction hallucination filtering - validate skills against query text"
  - "Abbreviation matching both directions (js -> JavaScript, JavaScript -> js)"

patterns-established:
  - "LLM extraction with JSON schema: Use response_format.json_schema for structured output"
  - "Skill validation: Filter LLM output against original query to prevent hallucination"
  - "Seniority normalization: Map Portuguese and abbreviations to standard enum values"

# Metrics
duration: 6min
completed: 2026-01-25
---

# Phase 12 Plan 02: Entity Extractor Summary

**LLM-based entity extraction using Together AI JSON mode with hallucination filtering and Portuguese term normalization**

## Performance

- **Duration:** 6 min
- **Started:** 2026-01-25T20:59:28Z
- **Completed:** 2026-01-25T21:05:45Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- EntityExtractor class with Together AI JSON mode for structured entity extraction
- Hallucination filtering that validates extracted skills against original query text
- Portuguese term normalization (pleno -> mid, senhor -> senior, gerente -> manager)
- Abbreviation matching for skills (js -> JavaScript, k8s -> Kubernetes, gql -> GraphQL)
- Comprehensive test suite with 33 passing tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement EntityExtractor with Together AI JSON mode** - `6c33fdb` (feat)
2. **Task 2: Add unit tests for entity extractor** - `b764b3f` (test)

## Files Created/Modified
- `services/hh-search-svc/src/nlp/entity-extractor.ts` - EntityExtractor class with LLM extraction
- `services/hh-search-svc/src/nlp/__tests__/entity-extractor.spec.ts` - 33 unit tests
- `services/hh-search-svc/package.json` - Added together-ai@0.33.0 dependency

## Decisions Made
- **150ms default timeout**: Per RESEARCH.md latency budget, extraction should complete quickly with fallback to empty entities on timeout
- **Post-extraction skill validation**: Instead of relying solely on LLM prompt instructions, filter extracted skills against query text to prevent hallucination
- **Bidirectional abbreviation matching**: Support both "js developer" -> JavaScript and "JavaScript" mentioned when "js" in query

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Initial mock approach for together-ai package failed due to Vitest requiring class constructors - resolved by using proper class mock pattern

## User Setup Required

None - no external service configuration required. Uses existing TOGETHER_API_KEY environment variable.

## Next Phase Readiness
- EntityExtractor ready for integration with query parser (12-04)
- Together AI package installed and tested
- Types from 12-01 (ExtractedEntities) integrated successfully
- Ready for 12-03 (query expander) which will use extracted skills for ontology expansion

---
*Phase: 12-natural-language-search*
*Completed: 2026-01-25*
