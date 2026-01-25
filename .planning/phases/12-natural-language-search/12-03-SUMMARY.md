---
phase: 12
plan: 03
subsystem: nlp
tags: [query-expansion, skills-ontology, search-recall]
requires: []
provides: [query-expander, skills-graph-services]
affects: [12-04, 12-05]
tech-stack:
  added: []
  patterns: [graph-expansion, lru-caching, confidence-decay]
key-files:
  created:
    - services/hh-search-svc/src/shared/skills-master.ts
    - services/hh-search-svc/src/shared/skills-graph.ts
    - services/hh-search-svc/src/nlp/query-expander.ts
    - services/hh-search-svc/src/nlp/__tests__/query-expander.spec.ts
  modified: []
decisions:
  - id: DEC-12-03-01
    title: Copy skills ontology to services workspace
    rationale: Enables direct imports without cross-workspace path issues
  - id: DEC-12-03-02
    title: Suppress console.log in production/test
    rationale: Avoid noisy logs in CI and production environments
  - id: DEC-12-03-03
    title: Default confidence threshold 0.8
    rationale: Balance between recall and precision for skill expansion
metrics:
  duration: ~7 minutes
  completed: 2026-01-25
---

# Phase 12 Plan 03: Query Expander Summary

Skills ontology-based query expansion using BFS graph traversal with configurable confidence thresholds and weight decay.

## One-Liner

QueryExpander wraps skills-graph.ts for intelligent skill expansion with 0.6x weight decay on expanded skills.

## What Was Built

### 1. Skills Ontology Files (Task 0)

Copied from functions workspace to services workspace:

- **skills-master.ts**: 200+ skills with aliases, categories, market data
- **skills-graph.ts**: BFS expansion with bidirectional relationships

Key modifications from original:
- Suppressed console.log statements in production/test environments
- Maintains same API: `getCachedSkillExpansion()`, `expandSkills()`

### 2. QueryExpander Class (Task 1)

**File**: `services/hh-search-svc/src/nlp/query-expander.ts`

**Capabilities**:
- `expandSkills(skills: string[])`: Expand skills using ontology
- `getSearchSkills(skills: string[])`: Flat array for search queries
- `getSkillWeights(skills: string[])`: Map of skill -> weight for scoring
- `updateConfig()`: Runtime configuration updates

**Configuration**:
```typescript
interface QueryExpanderConfig {
  enabled: boolean;              // Default: true
  maxDepth: number;              // Default: 1 (direct relations only)
  confidenceThreshold: number;   // Default: 0.8
  maxExpansionsPerSkill: number; // Default: 5
  expandedSkillWeight: number;   // Default: 0.6
}
```

**Example**:
```typescript
const expander = new QueryExpander(logger);
const result = expander.expandSkills(['Python']);
// result.allSkills = ['Python', 'Django', 'Flask', 'FastAPI', ...]
// result.expandedSkills[1].confidence = 0.54 (0.9 * 0.6)
```

### 3. Unit Tests (Task 2)

**File**: `services/hh-search-svc/src/nlp/__tests__/query-expander.spec.ts`

**Coverage**: 23 test cases covering:
- Skill expansion (Python -> Django, Flask)
- Confidence threshold filtering (>=0.8)
- Direct relations only (no indirect expansions)
- Max expansions per skill limit
- Deduplication across multiple input skills
- Weight mapping for scoring
- Graceful fallback for unknown skills
- Edge cases (case-insensitive, boundary thresholds)

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Copy to services workspace | Avoids cross-workspace import issues; enables local customization |
| Suppress console.log | Production code should be quiet; logs add noise in tests |
| Default depth=1 | Direct relations provide highest confidence; deeper traversal adds noise |
| Confidence threshold 0.8 | Skills graph uses 0.9 base confidence for direct; 0.8 filters weak relations |
| Weight 0.6x for expanded | Explicit skills should dominate scoring; expanded skills provide recall boost |

## Key Integration Points

### Input
- Array of skill strings from EntityExtractor
- Optional config overrides

### Output
```typescript
interface QueryExpansionResult {
  explicitSkills: string[];
  expandedSkills: ExpandedSkill[];
  allSkills: string[];
  timingMs: number;
}
```

### Usage in Search Pipeline
```typescript
// 1. Extract skills from query
const entities = await entityExtractor.extractEntities(query);

// 2. Expand skills for better recall
const expansion = queryExpander.expandSkills(entities.skills);

// 3. Use allSkills for vector/FTS search
const candidates = await vectorSearch(expansion.allSkills);

// 4. Use weights for scoring
const weights = queryExpander.getSkillWeights(entities.skills);
for (const candidate of candidates) {
  score += calculateSkillScore(candidate.skills, weights);
}
```

## Commits

| Hash | Description |
|------|-------------|
| c63bf88 | feat(12-03): copy skills ontology to services workspace |
| 0d1f314 | feat(12-03): implement QueryExpander using local skills-graph |
| 397ae1b | test(12-03): add unit tests for QueryExpander |

## Verification Results

| Check | Status |
|-------|--------|
| Skills ontology files copied | Pass |
| TypeScript compiles | Pass |
| Tests pass (23/23) | Pass |
| Expansion timing <5ms | Pass (in-memory graph lookup) |
| Confidence threshold respected | Pass |
| Weight decay applied | Pass |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed pre-existing TypeScript error in entity-extractor.spec.ts**
- **Found during:** Task 0 verification
- **Issue:** Unused variable 'result' in line 551 caused typecheck failure
- **Fix:** Added assertion `expect(result).toBeDefined()` to use the variable
- **Files modified:** services/hh-search-svc/src/nlp/__tests__/entity-extractor.spec.ts
- **Note:** This file was created by parallel Plan 12-02; fix was minimal and non-invasive

## Performance

- **Expansion latency**: <1ms (in-memory graph lookup with LRU cache)
- **Cache size**: 500 entries max
- **Cache TTL**: 1 hour
- **Skills count**: 200+ in ontology

## Next Phase Readiness

Plan 12-04 (Semantic Router) can now use:
- `QueryExpander` to expand skill entities before routing
- `getSkillWeights()` for weighted scoring in search results

Plan 12-05 (Pipeline Integration) will integrate:
- EntityExtractor (12-02)
- QueryExpander (12-03)
- Semantic Router (12-04)
