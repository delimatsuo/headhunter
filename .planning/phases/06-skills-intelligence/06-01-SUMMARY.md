---
phase: 06
plan: 01
subsystem: skills-intelligence
tags: [skills, graph, bfs, expansion, cache]
dependency_graph:
  requires: [05-01]
  provides: [skill-expansion, bidirectional-traversal, lru-cache]
  affects: [06-02, search-integration]
tech_stack:
  added: []
  patterns: [bfs-traversal, inverted-index, lru-cache]
key_files:
  created:
    - functions/src/shared/skills-graph.ts
  modified:
    - functions/src/shared/skills-service.ts
decisions:
  - id: bidirectional-in-task1
    choice: "Implemented bidirectional relationships in Task 1"
    rationale: "Integral to BFS expansion design; separating would be artificial"
metrics:
  duration: ~10 minutes
  completed: 2026-01-25
---

# Phase 6 Plan 1: Skill Expansion Graph Summary

**One-liner:** BFS-based skill expansion with bidirectional traversal and LRU caching (254 relationships).

## What Was Built

Created `functions/src/shared/skills-graph.ts` providing graph-based skill expansion using BFS traversal of the 468-skill taxonomy.

### Core Implementation

**SkillExpansionResult type:**
```typescript
interface SkillExpansionResult {
  originalSkill: string;
  originalSkillId: string | null;
  relatedSkills: Array<{
    skillId: string;
    skillName: string;
    relationshipType: 'direct' | 'indirect';
    distance: number;
    confidence: number;
  }>;
}
```

**Key functions:**
- `expandSkills(skillName, maxDepth=2, maxResults=10)` - BFS expansion
- `getCachedSkillExpansion(skillName, maxDepth=2)` - Cached version for hot paths
- `getRelatedSkillIds(skillId)` - Combined forward+backward relationships
- `clearSkillExpansionCache()` - For testing

### Data Structures

**REVERSE_RELATIONSHIPS Map:**
- Built at module load from MASTER_SKILLS relatedSkillIds
- Enables bidirectional traversal (Django -> Python, not just Python -> Django)
- 254 reverse relationships indexed

**SKILL_BY_ID Map:**
- O(1) skill lookup by ID
- Built at module load

**LRU Cache:**
- 500 entry limit
- 1 hour TTL (3600000ms)
- Map-based LRU via insertion order

### Confidence Scoring

| Distance | Base Confidence | With Critical Demand |
|----------|-----------------|---------------------|
| 1 (direct) | 0.9 | 1.0 |
| 2+ (indirect) | 0.6 | 0.7 |

## Verification Results

**Python expansion test:**
```
Python -> Django (direct, 0.9), Flask (direct, 0.9), FastAPI (direct, 0.9)...
```

**Bidirectional test:**
```
Django -> Python (direct, 1.0) - VERIFIED
```

**Relationship counts:**
- Forward: 254 relationships from MASTER_SKILLS
- Reverse: 254 relationships built for bidirectional traversal

## Commits

| Task | Hash | Description |
|------|------|-------------|
| 1 | 889695d | Create skills-graph.ts with BFS expansion |
| 2 | (in task 1) | Bidirectional relationships included in task 1 |
| 3 | 9361253 | Export skills-graph from skills-service |

## Deviations from Plan

### Task 2 Merged into Task 1

**Reason:** Task 2 (bidirectional relationship support) was implemented proactively in Task 1 as it's integral to the BFS expansion design. The REVERSE_RELATIONSHIPS map and getRelatedSkillIds() function were necessary for correct BFS behavior from the start.

**Impact:** None - all functionality delivered, just organized differently.

## Key Links

```typescript
// skills-graph.ts imports from skills-master.ts
import { MASTER_SKILLS, getSkillByName, type Skill } from './skills-master';

// skills-service.ts re-exports from skills-graph.ts
export { expandSkills, getCachedSkillExpansion, getRelatedSkillIds, clearSkillExpansionCache, type SkillExpansionResult } from './skills-graph';
```

## Usage Example

```typescript
import { expandSkills, getCachedSkillExpansion } from './shared/skills-service';

// Find candidates with Python OR related skills
const result = expandSkills('Python', 2, 10);
// Returns: Django (0.9), Flask (0.9), FastAPI (0.9), ML (1.0), Data Analysis (1.0)...

// Use cached version in search hot path
const cached = getCachedSkillExpansion('Python', 2);
```

## Next Phase Readiness

Ready for 06-02 (Skill Matching Score) which will:
- Use expandSkills to find related skills
- Calculate skill match scores using confidence values
- Integrate into the multi-signal scoring framework

## Files Modified

| File | Change |
|------|--------|
| `functions/src/shared/skills-graph.ts` | Created - BFS expansion with LRU cache |
| `functions/src/shared/skills-service.ts` | Added re-exports for skills-graph functions |

## Success Criteria Met

- [x] skills-graph.ts exists with BFS expansion, confidence decay, and LRU caching
- [x] Bidirectional relationships supported (Django -> Python works)
- [x] All functions exported via skills-service.ts
- [x] TypeScript compiles cleanly
- [x] Module initialization logs show cache ready and relationship counts
