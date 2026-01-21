# Session Summary - 2026-01-21

## What Was Accomplished

### Deep Fix: Tech Stack Threading + Smart Seniority for Gemini Reranking

**Problem:** Search returned wrong candidates because:
1. Tech stack extracted but never passed to Gemini reranking
2. Seniority logic too weak - Managers/Staff appeared with 37% scores but still in results
3. All backend engineers treated equally - Java/Python developers ranked same as Node.js developers

**Evidence:** For a Node.js Senior Backend Engineer search:
- Node.js developers ranked 47-72%
- Java/Python developers ranked 77% (higher than correct matches!)
- Engineering Managers at 37% still appeared in results

**Root Causes:**
| Issue | Location | Problem |
|-------|----------|---------|
| No tech_stack in JobContext | `gemini-reranking-service.ts:31-36` | Interface only had function/level/title |
| Rubric is generic | `gemini-reranking-service.ts:390-407` | Said "Senior Backend" not "Senior Node.js" |
| required_skills not passed | `legacy-engine.ts:405-416` | Only passed function/level/title to Gemini |
| Seniority is soft guidance | `gemini-reranking-service.ts:269` | "unlikely to accept" but no hard scoring |

**Solution Implemented:**

### 1. Extended JobContext Interface (`gemini-reranking-service.ts:31-40`)
```typescript
interface JobContext {
    function: string;
    level: string;
    title?: string;
    description?: string;
    // NEW FIELDS
    requiredSkills?: string[];      // Core tech: ["Node.js", "TypeScript", "NestJS"]
    avoidSkills?: string[];         // Anti-patterns: ["Oracle", "legacy"]
    companyContext?: string;        // "early-stage fintech startup"
}
```

### 2. Added Helper Methods
- `buildTechStackGuidance(jobContext)` - Generates tech stack scoring guidance
- `buildSeniorityGuidance(jobContext)` - Generates seniority constraints by role level
- `inferCompanyContext(description)` - Detects company stage and industry from JD

### 3. Enhanced PASS 2 Prompt
The Gemini prompt now includes:
- Explicit tech stack requirements with scoring guidance
- Level-specific seniority constraints (who would REALISTICALLY take this role)
- Clear scoring rules:
  - Wrong primary stack: score <60 even if senior
  - Managers/Staff stepping down: score <40

### 4. Updated JobDescription Type (`types.ts`)
```typescript
interface JobDescription {
    // ... existing fields ...
    sourcing_strategy?: {
        tech_stack?: {
            core?: string[];    // ["Node.js", "TypeScript"]
            avoid?: string[];   // ["Oracle", "legacy"]
        };
        target_companies?: string[];
        target_industries?: string[];
    };
}
```

### 5. Updated Schema Validation (`engine-search.ts`)
Added `sourcing_strategy` with `tech_stack` to the Zod schema validation.

## Files Modified

| File | Changes |
|------|---------|
| `functions/src/gemini-reranking-service.ts` | Extended JobContext, added `buildTechStackGuidance()` and `buildSeniorityGuidance()`, enhanced PASS 2 prompt |
| `functions/src/engines/legacy-engine.ts` | Pass `requiredSkills`, `avoidSkills`, `companyContext` to Gemini; added `inferCompanyContext()` |
| `functions/src/engines/types.ts` | Added `sourcing_strategy` to JobDescription interface |
| `functions/src/engine-search.ts` | Added tech_stack to schema validation |

## Expected Results After Fix

| Candidate Type | Before | After | Reason |
|----------------|--------|-------|--------|
| Node.js Senior Dev | 72% | **90%** | Exact tech + level match |
| Java Senior Dev | 77% | **45%** | Wrong primary stack |
| Python Senior Dev | 75% | **50%** | Wrong primary stack |
| Frontend Dev | 70% | **30%** | Wrong specialty |
| Engineering Manager | 37% | **20%** | Won't step down to IC |
| Staff Engineer | 26% | **25%** | Too senior for role |

## Deployment

- **Deployed to production**: Firebase Functions (78 functions) updated on `headhunter-ai-0088`
- **Deployment time**: 2026-01-21
- **Method**: `npm run deploy` in functions directory
- **All functions**: Successfully updated

## Git Commits

- `feat: thread tech stack through Gemini reranking for intelligent matching`

## Verification Plan

1. **Test with Node.js JD:**
   - Input: "Senior Backend Engineer at early-stage fintech... Node.js, TypeScript, NestJS; AWS, Fargate, Lambda"

2. **Expected ranking:**
   - Top 10 should be Node.js/TypeScript developers
   - Java/Python developers should rank lower (40-50%)
   - Managers/Staff should be near bottom or excluded

3. **Verify in console logs:**
   - Look for `[LegacyEngine] Gemini reranking with context:`
   - Should include `requiredSkills: ["Node.js", "TypeScript", ...]`

## What Needs to Be Done Next

1. **Test search quality** - Verify tech stack filtering works in production
2. **Monitor Gemini scores** - Check console logs to ensure correct scoring patterns
3. **Resume enrichment pipeline** - 10,519 candidates still pending enrichment
4. **Generate embeddings** - After enrichment completes

## Quick Start for Next Session

```bash
# Test search quality with tech stack
# Use UI or API to search for "Senior Node.js Engineer"
# Verify Node.js developers rank higher than Java/Python

# Check logs for Gemini context
gcloud functions logs read engineSearch --limit=50 | grep "Gemini reranking"

# Resume enrichment if needed
python scripts/sourcing_gemini_enrichment.py --max-cost 100

# Generate embeddings for sourcing candidates
python scripts/sourcing_embeddings.py
```

## Key Insight

The core improvement is teaching Gemini to think like a recruiter:
- **Tech stack matters**: "Backend" is not enough - primary language/framework matters
- **Career excitement**: The best candidate is EXCITED about the opportunity
- **Seniority reality**: Managers won't step down to IC, Staff engineers expect Staff+ roles

By giving Gemini full context (tech stack + seniority constraints), it can make nuanced decisions that match real recruiter thinking.
