# Phase 5: Skills Infrastructure - Research

**Researched:** 2026-01-24
**Domain:** Skills taxonomy integration and synonym normalization for search
**Confidence:** HIGH

## Summary

Phase 5 integrates the EllaAI skills taxonomy (200+ skills with built-in aliases) into the Headhunter search infrastructure. The source file (`skills-master.ts` from EllaAI) already provides comprehensive skill definitions, categories, aliases, and helper functions. The work is primarily integration - copying the file, creating normalized lookup utilities, and replacing hardcoded synonym maps in the existing search services.

The EllaAI skills-master.ts is a well-structured, production-ready TypeScript module with:
- 200+ skills across 15 categories
- Built-in alias support (JS=JavaScript, K8s=Kubernetes, etc.)
- Helper functions for lookup, normalization, and matching
- Type definitions for TypeScript safety
- Legacy ID mapping for backward compatibility

**Primary recommendation:** Copy skills-master.ts to functions/src/shared/, create a thin skills-service.ts wrapper with search-optimized functions, then refactor the 3 files with hardcoded synonyms to use the new service.

## Standard Stack

The phase uses existing project patterns - no new libraries required.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| TypeScript | 5.x | Type-safe skills module | Already in project |
| None | - | No new dependencies | Skills-master.ts is self-contained |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Vitest/Jest | Existing | Unit testing for skills service | Required for TDD |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Static skills file | Database-backed skills | Static file is simpler, sufficient for 200 skills, no runtime DB dependency |
| Custom normalization | fuzzy-search library | Built-in matchSkillName already handles partial/alias matching |

**Installation:**
```bash
# No new packages required - skills-master.ts is self-contained TypeScript
```

## Architecture Patterns

### Recommended Project Structure
```
functions/src/
├── shared/
│   ├── skills-master.ts       # Copied from EllaAI (source of truth)
│   └── skills-service.ts      # Search-optimized wrapper functions
├── vector-search.ts           # Refactor: import from skills-service
├── skill-aware-search.ts      # Refactor: import from skills-service
└── ...
```

### Pattern 1: Single Source of Truth for Skills
**What:** All skill definitions, aliases, and normalization logic in one module
**When to use:** Always - avoids duplicate synonym maps scattered across codebase
**Example:**
```typescript
// functions/src/shared/skills-service.ts
import {
  MASTER_SKILLS,
  getSkillByName,
  matchSkillName,
  normalizeSkillToId
} from './skills-master';

// Search-optimized: build reverse alias map once at startup
const ALIAS_TO_CANONICAL = new Map<string, string>();
for (const skill of MASTER_SKILLS) {
  ALIAS_TO_CANONICAL.set(skill.name.toLowerCase(), skill.name);
  if (skill.aliases) {
    for (const alias of skill.aliases) {
      ALIAS_TO_CANONICAL.set(alias.toLowerCase(), skill.name);
    }
  }
}

/**
 * Normalize any skill name/alias to canonical form
 * O(1) lookup - safe for hot paths in search
 */
export function normalizeSkillName(input: string): string {
  const normalized = input.toLowerCase().trim();
  return ALIAS_TO_CANONICAL.get(normalized) || input;
}

/**
 * Check if two skill names refer to the same skill
 */
export function skillsMatch(skill1: string, skill2: string): boolean {
  return normalizeSkillName(skill1) === normalizeSkillName(skill2);
}

/**
 * Get all aliases for a canonical skill name
 */
export function getSkillAliases(skillName: string): string[] {
  const skill = getSkillByName(skillName);
  return skill?.aliases || [];
}

// Re-export commonly used functions
export {
  MASTER_SKILLS,
  getSkillByName,
  matchSkillName,
  searchSkills,
  SKILL_CATEGORIES
} from './skills-master';
```

### Pattern 2: Replace Hardcoded Synonyms
**What:** Remove inline synonym maps, use skills-service instead
**When to use:** During refactoring of existing search files
**Example:**
```typescript
// BEFORE (in vector-search.ts lines 1287-1306):
const synonyms: Record<string, string[]> = {
  'javascript': ['js', 'ecmascript', 'node.js', 'nodejs'],
  'python': ['py', 'python3'],
  'kubernetes': ['k8s'],
  // ... hardcoded
};

// AFTER:
import { normalizeSkillName, skillsMatch } from './shared/skills-service';

// In findMatchingSkill():
const normalizedTarget = normalizeSkillName(targetSkill);
const exactMatch = candidateSkills.find(s =>
  normalizeSkillName(s.skill) === normalizedTarget
);
```

### Pattern 3: Lazy Initialization for Service Files
**What:** Build lookup maps once, not on every function call
**When to use:** For search-hot-path functions
**Example:**
```typescript
// Skills service initializes maps at module load time
// This happens once per cold start, not per request
const ALIAS_TO_CANONICAL = buildAliasMap(); // Called once

// Then exported functions use the pre-built map
export function normalizeSkillName(input: string): string {
  return ALIAS_TO_CANONICAL.get(input.toLowerCase()) || input;
}
```

### Anti-Patterns to Avoid
- **Duplicate synonym definitions:** Never define synonyms in multiple files. All synonyms should be in skills-master.ts aliases field only.
- **Building maps per-request:** The alias lookup map should be built once at module load, not inside request handlers.
- **Case-sensitive matching:** Always normalize to lowercase before comparison.
- **Modifying skills-master.ts heavily:** Keep it close to EllaAI source for easy future syncs. Put customizations in skills-service.ts wrapper.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Skill synonyms | Custom synonym map | skills-master.ts aliases | Already has 50+ alias mappings |
| Fuzzy skill match | Levenshtein distance | matchSkillName() | Word-boundary matching prevents false positives |
| Skill normalization | toLowerCase + manual | normalizeSkillToId() | Handles edge cases (C#, .NET, etc.) |
| Category lookup | String parsing | SKILL_CATEGORIES + getCategoryById() | Type-safe category metadata |
| Skill search | Array.filter | searchSkills() | Searches both name and aliases |

**Key insight:** The EllaAI skills-master.ts already provides 90% of the needed functionality. The wrapper (skills-service.ts) only needs to add search-optimized O(1) lookups via pre-built Maps.

## Common Pitfalls

### Pitfall 1: Case Sensitivity in Skill Matching
**What goes wrong:** "JavaScript" !== "javascript" causes missed matches
**Why it happens:** Direct string comparison without normalization
**How to avoid:** Always use normalizeSkillName() which lowercases consistently
**Warning signs:** Skills that "should match" don't appear in search results

### Pitfall 2: Partial Alias Matching (False Positives)
**What goes wrong:** "C" matches "Executive" because "C" is contained in the string
**Why it happens:** Using string.includes() instead of word-boundary matching
**How to avoid:** Use matchSkillName() which has word-boundary logic for short terms
**Warning signs:** Unrelated candidates appearing in skill-filtered searches

### Pitfall 3: Stale Synonym Maps After Refactoring
**What goes wrong:** Hardcoded synonyms in one file, skills-master in another
**Why it happens:** Incremental refactoring leaves some files using old patterns
**How to avoid:** Delete all hardcoded synonym maps completely, not just add imports
**Warning signs:** Different synonym behavior in different search paths

### Pitfall 4: Forgetting Legacy ID Mapping
**What goes wrong:** Frontend sends "skill-javascript", backend expects "javascript"
**Why it happens:** EllaAI uses "skill-" prefixed IDs in some places
**How to avoid:** Use legacyIdToNewId() when receiving external input
**Warning signs:** Skill filters silently returning no matches

### Pitfall 5: Missing Skills for Domain-Specific Terms
**What goes wrong:** Searches for "React Native" or "SwiftUI" fail
**Why it happens:** Assuming skills-master.ts has every possible skill
**How to avoid:** Check MASTER_SKILLS coverage, add missing skills to skills-master.ts
**Warning signs:** Console logs showing "skill not found" for legitimate terms

## Code Examples

Verified patterns from EllaAI skills-master.ts:

### Skill Lookup by Name (Including Aliases)
```typescript
// Source: EllaAI skills-master.ts getSkillByName()
export const getSkillByName = (name: string): Skill | undefined => {
    const normalized = name.toLowerCase().trim();
    return MASTER_SKILLS.find(s =>
        s.name.toLowerCase() === normalized ||
        s.aliases?.some(a => a.toLowerCase() === normalized)
    );
};

// Usage:
const skill = getSkillByName('JS');     // Returns JavaScript skill
const skill2 = getSkillByName('K8s');   // Returns Kubernetes skill
```

### Word-Boundary Skill Matching
```typescript
// Source: EllaAI skills-master.ts matchSkillName()
export const matchSkillName = (name: string): Skill | null => {
    // Exact match first
    const exact = getSkillByName(name);
    if (exact) return exact;

    const normalized = name.toLowerCase().trim();

    // For single-char terms (like "C", "R"), require exact word match
    // For longer terms, allow partial word matches
    const matchesAsWord = (text: string, term: string): boolean => {
        if (term.length < 2) {
            const words = text.split(/\s+/);
            return words.some(word => word === term);
        }
        const regex = new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`, 'i');
        return regex.test(text);
    };
    // ... rest of matching logic
};
```

### Normalize Skill to ID
```typescript
// Source: EllaAI skills-master.ts normalizeSkillToId()
export const normalizeSkillToId = (name: string): string => {
    const skill = getSkillByName(name);
    return skill?.id || name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
};

// Usage:
normalizeSkillToId('JavaScript');  // Returns 'javascript'
normalizeSkillToId('JS');          // Returns 'javascript' (via alias lookup)
normalizeSkillToId('C#');          // Returns 'csharp' (special char handling)
```

### Search Skills
```typescript
// Source: EllaAI skills-master.ts searchSkills()
export const searchSkills = (query: string): Skill[] => {
    const normalized = query.toLowerCase().trim();
    if (!normalized) return MASTER_SKILLS;

    return MASTER_SKILLS.filter(s =>
        s.name.toLowerCase().includes(normalized) ||
        s.aliases?.some(a => a.toLowerCase().includes(normalized))
    );
};

// Usage:
searchSkills('script');  // Returns JavaScript, TypeScript, etc.
searchSkills('k8');      // Returns Kubernetes (via alias 'K8s')
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded synonyms per file | Centralized skills taxonomy | This phase | Single source of truth, consistent matching |
| String.includes() matching | Word-boundary matching | Already in EllaAI | Prevents false positives like "C" matching "Executive" |
| O(n) skill lookup | O(1) Map-based lookup | This phase (wrapper) | Hot-path performance for search |

**Deprecated/outdated:**
- Hardcoded synonym maps in vector-search.ts, skill-aware-search.ts: Replace with skills-service imports

## Open Questions

Things that couldn't be fully resolved:

1. **Skill coverage completeness**
   - What we know: skills-master.ts has 200+ skills covering major tech categories
   - What's unclear: Are there Headhunter-specific skills (recruiter domain terms) missing?
   - Recommendation: Review search logs for "skill not found" after deployment, add missing skills

2. **Legacy ID usage in frontend**
   - What we know: EllaAI uses "skill-javascript" format in some places
   - What's unclear: Does Headhunter UI send prefixed or unprefixed skill IDs?
   - Recommendation: Check frontend code, add legacyIdToNewId() call if needed

3. **Category filtering in search**
   - What we know: Skills have categories (programming-languages, cloud-devops, etc.)
   - What's unclear: Does Headhunter search need to filter by skill category?
   - Recommendation: Defer category filtering to future phase if not immediately needed

## Sources

### Primary (HIGH confidence)
- EllaAI skills-master.ts - Full file analysis (894 lines)
  - Type definitions: lines 25-65
  - SKILL_CATEGORIES: lines 70-191
  - MASTER_SKILLS: lines 197-468
  - Helper functions: lines 474-605
  - Legacy ID mapping: lines 631-828

### Secondary (HIGH confidence)
- Headhunter codebase analysis:
  - functions/src/vector-search.ts - Current synonym handling (lines 1267-1309)
  - functions/src/skill-aware-search.ts - Current normalization (lines 130-146)
  - services/hh-search-svc/src/search-service.ts - Search skill matching (lines 33-56)

### Tertiary (N/A)
- No external sources needed - this is internal codebase integration

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new libraries, self-contained TypeScript module
- Architecture: HIGH - Clear integration points identified in existing codebase
- Pitfalls: HIGH - Based on direct code analysis of existing search implementations

**Research date:** 2026-01-24
**Valid until:** N/A - This is codebase-specific, not library version dependent

## Implementation Summary

Files to modify (in order):
1. **Copy:** `/Volumes/Extreme Pro/myprojects/EllaAI/react-spa/src/data/skills-master.ts` -> `functions/src/shared/skills-master.ts`
2. **Create:** `functions/src/shared/skills-service.ts` (search-optimized wrapper)
3. **Refactor:** `functions/src/vector-search.ts` (remove hardcoded synonyms lines 1287-1306)
4. **Refactor:** `functions/src/skill-aware-search.ts` (remove normalizeSkill function lines 130-146)
5. **Optional:** `services/hh-search-svc/src/search-service.ts` (if it needs shared skills module)

Test coverage needed:
- Alias normalization (JS -> JavaScript, K8s -> Kubernetes)
- Case insensitivity (PYTHON, Python, python all match)
- Word-boundary matching (C does not match Executive)
- Missing skill handling (graceful fallback)
