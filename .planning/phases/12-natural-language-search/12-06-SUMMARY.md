---
phase: 12
plan: 06
subsystem: nlp
tags: [nlp, semantic-synonyms, seniority, roles, search]
depends_on:
  requires: [12-04, 12-05]
  provides: [semantic-synonyms-module, queryparser-startup, nlp-health-endpoint]
  affects: [search-pipeline, ui-filters]
tech_stack:
  added: []
  patterns: [semantic-expansion, background-initialization, health-reporting]
key_files:
  created:
    - services/hh-search-svc/src/nlp/semantic-synonyms.ts
    - services/hh-search-svc/src/nlp/__tests__/semantic-synonyms.spec.ts
  modified:
    - services/hh-search-svc/src/nlp/types.ts
    - services/hh-search-svc/src/nlp/index.ts
    - services/hh-search-svc/src/nlp/query-parser.ts
    - services/hh-search-svc/src/index.ts
    - services/hh-search-svc/src/routes.ts
decisions:
  - id: semantic-higher-levels
    choice: Include higher seniority levels by default
    rationale: "Lead" should match "Senior", "Staff", "Principal" candidates
  - id: background-nlp-init
    choice: Non-blocking QueryParser initialization
    rationale: Faster Cloud Run startup, NLP ready before first search
  - id: nlp-health-endpoint
    choice: Report NLP status in health endpoint
    rationale: Observability for NLP initialization state
metrics:
  duration: 291s
  completed: 2026-01-25
---

# Phase 12 Plan 06: NLP Integration & Semantic Synonyms Summary

Semantic expansion for seniority levels and role titles, plus QueryParser initialization at service startup with health endpoint reporting.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create semantic synonyms expansion module | d6ee8f1 | semantic-synonyms.ts, semantic-synonyms.spec.ts, types.ts |
| 2 | Wire up QueryParser initialization at startup | 554a429 | index.ts, routes.ts |
| 3 | Update NLP barrel export and integrate semantic synonyms | bf2e8c5 | nlp/index.ts, query-parser.ts |

## Deliverables

### Semantic Synonyms Module (`semantic-synonyms.ts`)

**Data Structures:**
- `SENIORITY_SYNONYMS`: Maps 10 seniority levels to synonyms
  - junior, mid, senior, staff, principal, lead, manager, director, vp, c-level
  - Portuguese support: junior->junir, senior->senior, manager->gerente, director->diretor
- `ROLE_SYNONYMS`: Maps common roles to equivalent titles
  - developer <-> engineer (bidirectional)
  - devops <-> sre <-> platform engineer
  - data scientist <-> ml engineer <-> data engineer
  - Portuguese support: desenvolvedor, engenheiro
- `SENIORITY_HIERARCHY`: Ordered array for level comparison

**Functions:**
- `expandSenioritySynonyms(seniority, includeHigherLevels)`: Expand seniority term
  - Returns all synonyms (e.g., "senior" -> ["senior", "sr", "sr.", "senior"])
  - With `includeHigherLevels=true`: Also returns staff, principal, lead, etc.
- `expandRoleSynonyms(role)`: Expand role term
  - "developer" -> ["developer", "engineer", "programmer", "coder", "dev", "desenvolvedor"]
- `expandSemanticSynonyms(entities)`: Full expansion for entities object
  - Expands both role and seniority from extracted entities
  - Returns `{ expandedRoles, expandedSeniorities }`
- `matchesSeniorityLevel(candidateLevel, targetLevel, allowHigher)`: Level matching
- `getSeniorityIndex(seniority)`: Get hierarchy position
- `compareSeniorityLevels(a, b)`: Compare two levels

**Test Coverage:** 44 tests covering all functions

### QueryParser Initialization (`index.ts`)

**Initialization Flow:**
1. Check if NLP is enabled via `config.nlp.enabled`
2. Create `NLPConfig` from environment-based configuration
3. Instantiate `QueryParser` with embed client's `generateEmbedding`
4. Initialize in background (non-blocking) via Promise
5. Track `state.nlpInitialized` on completion
6. Pass `queryParser` to `SearchService` constructor

**Logging:**
- Logs NLP configuration at startup
- Logs initialization success with config details
- Error logging if initialization fails (service continues in degraded mode)

### Health Endpoint Enhancement (`routes.ts`)

**NLP Health Status:**
```typescript
nlp: {
  enabled: boolean,      // config.nlp.enabled
  initialized: boolean,  // queryParser.isInitialized()
  status: 'ready' | 'initializing' | 'disabled'
}
```

- Included in both healthy and degraded responses
- Non-blocking check (reads initialized flag)

### ParsedQuery Enhancement (`types.ts`, `query-parser.ts`)

**New Field:**
```typescript
semanticExpansion?: {
  expandedRoles: string[];
  expandedSeniorities: string[];
}
```

- Populated by `expandSemanticSynonyms()` in Step 6 of parse pipeline
- Used by `SearchService.applyNlpFilters()` to expand seniority filters

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Include higher levels | Default true for seniority | "Lead engineer" should match Senior, Staff, Principal candidates |
| Background init | Non-blocking Promise | Cloud Run fast startup, NLP ready before first search request |
| Health endpoint NLP | Include nlp status | Observability for initialization state, debugging |
| Portuguese support | Include BR terms | Brazilian recruiter market support per Phase 12 requirements |
| Bidirectional roles | developer <-> engineer | Common interchangeable titles in job postings |

## Test Results

```
Test Files:  5 passed (5)
     Tests:  144 passed (144)
  Duration:  580ms

Breakdown:
- semantic-synonyms.spec.ts: 44 tests
- query-parser.spec.ts: 25 tests
- query-expander.spec.ts: 23 tests
- intent-router.spec.ts: 19 tests
- entity-extractor.spec.ts: 33 tests
```

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

1. **TypeScript compiles**: YES - `npm run typecheck` passes
2. **All NLP tests pass**: 144/144 tests passing
3. **Service starts with NLP enabled**: YES - QueryParser initialized in background
4. **Health endpoint reports NLP status**: YES - `nlp.enabled`, `nlp.initialized`, `nlp.status`
5. **Semantic synonyms expand "Lead"**: YES
   - Includes: lead, tech lead, team lead, lead engineer, lead developer, senior, staff

## Integration Points

### Search Service Integration (from 12-05)

The `SearchService.applyNlpFilters()` method now uses `semanticExpansion`:
- If `parsed.semanticExpansion.expandedSeniorities` exists and no explicit seniority filters
- Apply expanded seniorities to `filters.seniorityLevels`
- Enables "Lead engineer" to match candidates with "Senior", "Staff", "Principal" titles

### Health Check Integration

Health endpoint now reports full NLP status:
```json
{
  "status": "ok",
  "pgvector": {...},
  "redis": {...},
  "embeddings": {...},
  "rerank": {...},
  "nlp": {
    "enabled": true,
    "initialized": true,
    "status": "ready"
  }
}
```

## Next Phase Readiness

**Phase 12 Complete:** All 6 plans executed successfully.

**Phase 12 Deliverables:**
- IntentRouter: Semantic intent classification (19 tests)
- EntityExtractor: LLM-based entity extraction (33 tests)
- QueryExpander: Skills ontology expansion (23 tests)
- QueryParser: Pipeline orchestrator (25 tests)
- SemanticSynonyms: Seniority/role expansion (44 tests)
- SearchService integration: NLP filters, semantic expansion

**Ready for Phase 13:** ML Trajectory Prediction
- NLP infrastructure provides structured entities for ML features
- Seniority/role expansion enables better candidate matching
- Performance baseline established with 144 passing tests
