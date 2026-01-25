# Phase 9: Match Transparency - Research Findings

**Research Question**: What do I need to know to PLAN this phase well?

**Date**: 2026-01-24
**Phase Goal**: Recruiters understand why each candidate matched and how they scored.

---

## Executive Summary

Phase 9 implements **match transparency** - showing recruiters why candidates matched their search and how scoring components combined to produce the final ranking. This is critical for both **regulatory compliance** (NYC Local Law 144, EU AI Act) and **user trust** (recruiters need to understand AI decisions to act on them).

**Key Finding**: 95% of the infrastructure is already in place. The backend computes and returns:
- Overall match scores (0-100)
- Individual signal scores (7 core signals + 5 Phase 7 signals)
- Match reasons as text bullets
- All data flows through the search response

The work is primarily **frontend UI development** to display this data effectively, plus **selective LLM-generated rationale** for top candidates.

---

## Current State Analysis

### Backend Infrastructure (✅ Ready)

#### 1. Signal Scoring Framework

The search service (`hh-search-svc`) implements a comprehensive multi-signal scoring system:

**Core Signals** (Phase 4):
- `vectorSimilarity`: Semantic embedding match (0-1)
- `levelMatch`: Seniority alignment (0-1)
- `specialtyMatch`: Backend/frontend/fullstack fit (0-1)
- `techStackMatch`: Technology compatibility (0-1)
- `functionMatch`: Engineering/product/design alignment (0-1)
- `trajectoryFit`: Career progression fit (0-1)
- `companyPedigree`: Company tier quality (0-1)

**Phase 7 Signals** (Computed):
- `skillsExactMatch`: Required skill coverage (0-1)
- `skillsInferred`: Transferable skill match (0-1)
- `seniorityAlignment`: Level fit with tier adjustment (0-1)
- `recencyBoost`: Skill recency decay (0-1)
- `companyRelevance`: Company/industry alignment (0-1)

**Implementation Reference**:
```typescript
// /services/hh-search-svc/src/types.ts (lines 51-92)
export interface SignalScores {
  vectorSimilarity: number;
  levelMatch: number;
  specialtyMatch: number;
  techStackMatch: number;
  functionMatch: number;
  trajectoryFit: number;
  companyPedigree: number;

  // Phase 7 signals
  skillsExactMatch?: number;
  skillsInferred?: number;
  seniorityAlignment?: number;
  recencyBoost?: number;
  companyRelevance?: number;
}
```

Each search result already includes:
```typescript
// /services/hh-search-svc/src/types.ts (lines 94-135)
export interface HybridSearchResultItem {
  candidateId: string;
  score: number;
  signalScores?: SignalScores;      // ✅ All component scores
  weightsApplied?: SignalWeightConfig; // ✅ Weights used
  roleTypeUsed?: RoleType;          // ✅ Preset used
  matchReasons: string[];           // ✅ Text explanations
}
```

#### 2. Signal Calculation Logic

**Transparent, Deterministic Scoring**:
- Each signal has a pure function that returns 0-1 scores
- Functions in `/services/hh-search-svc/src/signal-calculators.ts` (531 lines)
- Documented formulas for all signals

**Examples**:
- **Seniority Alignment** (lines 303-353): Distance-based scoring with FAANG +1 level adjustment
- **Skills Exact Match** (lines 134-164): Coverage ratio with alias handling
- **Recency Boost** (lines 373-427): Time-decay formula: `1.0 - (years_since * 0.16)`

#### 3. Weight Configuration

**Role-Based Presets** (`/services/hh-search-svc/src/signal-weights.ts`):
- `executive`: Function (0.20) and company pedigree (0.12) weighted high
- `manager`: Balanced across all signals
- `ic`: Skills exact match (0.14) and recency (0.08) weighted high
- `default`: Evenly distributed

**Request-Level Overrides**: Supported via `HybridSearchRequest.signalWeights`

#### 4. Match Reasons Generation

**Text Bullets Already Generated**:
```typescript
// /services/hh-search-svc/src/search-service.ts (lines 453-476)
const matchReasons: string[] = [];
if (matches.length > 0) {
  matchReasons.push(`Matches required skills: ${matches.join(', ')}`);
}
if (request.filters?.locations && row.location) {
  matchReasons.push(`Located in preferred market (${row.location})`);
}
if (request.filters?.countries && row.country) {
  matchReasons.push(`Located in ${row.country}`);
}
// ... more reasons
```

**Output**: Array of human-readable strings explaining why the candidate matched

#### 5. Debug Mode Support

**Enhanced Debug Output**:
```typescript
// /services/hh-search-svc/src/search-service.ts (lines 376-415)
if (request.includeDebug) {
  response.debug = {
    candidateCount: ranked.length,
    filtersApplied: request.filters ?? {},
    signalScoringConfig: {
      roleType,
      weightsApplied: resolvedWeights,
      requestOverrides: request.signalWeights ?? null
    },
    scoreBreakdown: ranked.slice(0, 5).map(r => ({
      candidateId: r.candidateId,
      score: r.score,
      vectorScore: r.vectorScore,
      textScore: r.textScore,
      signalScores: r.signalScores // ✅ All signals
    })),
    phase7Breakdown: ranked.slice(0, 5).map(r => ({
      candidateId: r.candidateId,
      skillsExactMatch: r.signalScores?.skillsExactMatch,
      skillsInferred: r.signalScores?.skillsInferred,
      seniorityAlignment: r.signalScores?.seniorityAlignment,
      recencyBoost: r.signalScores?.recencyBoost,
      companyRelevance: r.signalScores?.companyRelevance
    }))
  };
}
```

**Impact**: Full transparency into how scores were computed

---

### Frontend Infrastructure (⚠️ Partial)

#### 1. Existing Candidate Card Component

**Component**: `SkillAwareCandidateCard.tsx` (635 lines)

**Current Features**:
- Overall match score display (lines 494-510)
- Vector similarity score (when different from match score)
- Score color coding: excellent (≥80%), good (≥60%), fair (≥40%), poor (<40%)
- AI-generated rationale section (lines 515-543)
- Skill matching visualization (lines 546-562)
- Expandable details section (lines 564-625)

**Gaps**:
- ❌ No signal score breakdown display
- ❌ No component score visualization
- ❌ No confidence indicators for inferred skills
- ⚠️ Rationale is static (from backend data), not LLM-generated on-demand

#### 2. Search Results UI

**Component**: `SearchResults.tsx` (353 lines)

**Current Features**:
- List view of candidates (lines 257-270)
- Pass-through of match scores to `SkillAwareCandidateCard`
- Results summary (lines 94-115)
- AI analysis summary (collapsible, lines 118-223)

**Gaps**:
- ❌ No sorting/filtering by individual signal scores
- ❌ No transparency controls (show/hide signal details)

#### 3. Type Definitions

**Frontend Types**: `/headhunter-ui/src/types/index.ts`

**Current Types**:
```typescript
export interface CandidateProfile {
  matchScore?: number;
  matchReasons?: string[];
  rationale?: {
    overall_assessment: string;
    strengths: string[];
    gaps: string[];
    risk_factors: string[];
  };
  // ... other fields
}
```

**Gaps**:
- ❌ No `signalScores` interface in frontend types
- ❌ No `SignalWeightConfig` type
- ❌ Need to mirror backend `SignalScores` interface

---

## LLM Rationale Generation Requirements

### Current Backend LLM Integration

**Together AI Integration**:
- Client: `/services/hh-rerank-svc/src/together-client.ts` (210 lines)
- Model: Qwen 2.5 32B Instruct (from PRD)
- Purpose: Reranking candidates (not rationale generation currently)

**Rerank Service**:
- Endpoint: `POST /v1/search/rerank`
- Takes: Job description + candidate summaries
- Returns: Reranked results with reasons
- Performance: Target ≤350ms for K≤200 candidates

**Key Insight**: The rerank service already generates "reasons" for ranking:
```typescript
// /services/hh-search-svc/src/rerank-client.ts (lines 50-57)
export interface RerankResult {
  candidateId: string;
  rank: number;
  score: number;
  reasons: string[];  // ✅ Already generating explanations
  summary?: string;
  payload?: Record<string, unknown>;
}
```

**Gap**: These reasons are focused on ranking, not match explanation. Need dedicated rationale generation.

### LLM Rationale Design Options

#### Option A: Extend Rerank Service
**Pros**:
- Reuses existing Together AI integration
- Already has caching infrastructure
- Proven latency performance

**Cons**:
- Couples two concerns (ranking + explanation)
- Rerank runs on top-K≈200, rationale only for top-10

**Approach**: Add optional `includeMatchRationale: boolean` flag to rerank request

#### Option B: New Explanation Service
**Pros**:
- Separation of concerns
- Can optimize prompts specifically for explanation
- Independent caching strategy

**Cons**:
- New service to build/deploy
- Duplicates Together AI client code

**Approach**: New `hh-explain-svc` service with dedicated `/v1/candidates/:id/explain` endpoint

#### Option C: Frontend-Triggered Cloud Function
**Pros**:
- Lightweight integration
- Can use existing Cloud Functions patterns
- Natural request/response caching

**Cons**:
- Latency (cold starts)
- Less control over batching
- Not part of Fastify service mesh

**Approach**: Cloud Function that calls Together AI and stores in Firestore cache

### Recommended Approach: **Option A (Extend Rerank)**

**Rationale**:
1. **Already integrated**: Rerank service has Together AI client, caching, auth
2. **Proven latency**: ≤350ms target proven feasible
3. **Context available**: Rerank already has job description + candidate features
4. **Incremental**: Add feature flag, no new service
5. **Cost-effective**: Batch generation during rerank pass

**Implementation Path**:
```typescript
// Add to RerankRequest
export interface RerankRequest {
  // ... existing fields
  includeMatchRationale?: boolean;  // NEW
  rationaleLimit?: number;          // Default: 10
}

// Add to RerankResult
export interface RerankResult {
  // ... existing fields
  matchRationale?: {                // NEW
    summary: string;               // "Why this candidate matches"
    keyStrengths: string[];        // 2-3 bullets
    signalHighlights: {            // Which signals drove the match
      signal: string;
      score: number;
      reason: string;
    }[];
  };
}
```

**Prompt Template** (pseudocode):
```
Given:
- Job Description: {jobDescription}
- Candidate: {candidateSummary}
- Top Signals: {topSignals} (skills: 0.92, trajectory: 0.87, ...)

Generate a brief match explanation (2-3 sentences) focusing on:
1. What makes this candidate a strong fit
2. Which specific signals are most relevant
3. Any standout qualifications

Output JSON: { "summary": "...", "keyStrengths": [...], "signalHighlights": [...] }
```

**Caching Strategy**:
- Cache key: `rationale:${candidateId}:${jdHash}`
- TTL: 24 hours (rationale stable for same JD)
- Storage: Redis (same as rerank cache)

**Cost Analysis**:
- Tokens per rationale: ~200 input + 150 output = 350 tokens
- Top 10 candidates: 3,500 tokens ≈ $0.001 per search (Together AI pricing)
- Annual (1000 searches): ~$1.00

---

## Regulatory Compliance Mapping

### NYC Local Law 144 (Automated Employment Decision Tools)

**Requirements**:
1. ✅ **Bias audit**: Signal scoring is deterministic, auditable
2. ✅ **Notice**: UI can display "AI-assisted ranking" notice
3. ✅ **Explanation**: Signal scores + weights satisfy transparency requirement
4. ⚠️ **Data retention**: Need to log search parameters + results for audit trail

**Implementation Needs**:
- Store search queries + top 20 results + signal scores in `search_logs` collection
- Retention: 3 years minimum
- Export capability for audits

### EU AI Act (High-Risk AI Systems)

**Requirements**:
1. ✅ **Transparency**: User must be informed when interacting with AI
2. ✅ **Human oversight**: Recruiters make final decisions (system is assistive)
3. ✅ **Technical documentation**: Signal formulas documented in code
4. ✅ **Record-keeping**: Search logs satisfy audit trail requirement
5. ⚠️ **Risk management**: Need to monitor for bias in signal scores

**Implementation Needs**:
- Monthly bias audits (compare signal score distributions by protected characteristics if available)
- Documented review process for signal weight changes
- User notification banner: "This search uses AI-assisted ranking"

---

## UI/UX Design Patterns

### Industry Best Practices

#### 1. **Progressive Disclosure** (LinkedIn Talent Insights)
- Default: Overall score + 1-line summary
- Expand: Show top 3 contributing signals
- Deep dive: Full signal breakdown on click

**Apply to Headhunter**:
- Collapsed state: Match score (87%) + AI insight
- First expand: Top 3 signals (skills: 92%, trajectory: 87%, recency: 85%)
- Second expand: All 12 signals with formulas

#### 2. **Visual Score Breakdown** (Indeed Resume Search)
- Radial chart showing component scores
- Color-coded: green (strong), yellow (medium), gray (weak)
- Hover tooltips with explanations

**Apply to Headhunter**:
- Horizontal bar chart for each signal (0-100%)
- Color scale: 0-40% (red), 40-70% (yellow), 70-100% (green)
- Tooltip: Signal name + formula + candidate value

#### 3. **Confidence Indicators** (HireVue)
- High confidence: ✓ icon, solid color
- Medium confidence: ⚠ icon, striped background
- Low confidence: ? icon, dashed border

**Apply to Headhunter**:
- Inferred skills: Badge showing confidence % (High: >80%, Medium: 50-80%, Low: <50%)
- Explicit skills: No badge (100% confidence)
- Phase 7 signals use confidence thresholds

#### 4. **Sortable/Filterable Results** (Greenhouse Candidate Pipeline)
- Sort by: Overall score | Skill match | Experience | Recency
- Filter by: Min skill score | Min trajectory score

**Apply to Headhunter**:
- Dropdown: "Sort by: Best Match | Skills | Experience | Recency"
- Sliders: "Min Skill Match: 70%" (filter out below threshold)

---

## Technical Implementation Requirements

### Frontend Changes

#### 1. Type Definitions
**File**: `/headhunter-ui/src/types/index.ts`

**Add**:
```typescript
export interface SignalScores {
  vectorSimilarity: number;
  levelMatch: number;
  specialtyMatch: number;
  techStackMatch: number;
  functionMatch: number;
  trajectoryFit: number;
  companyPedigree: number;
  skillsExactMatch?: number;
  skillsInferred?: number;
  seniorityAlignment?: number;
  recencyBoost?: number;
  companyRelevance?: number;
}

export interface SignalWeightConfig {
  // Mirror backend interface
  vectorSimilarity: number;
  levelMatch: number;
  // ... all weights
}

export interface MatchRationale {
  summary: string;
  keyStrengths: string[];
  signalHighlights: Array<{
    signal: string;
    score: number;
    reason: string;
  }>;
}

export interface CandidateMatch {
  candidate: CandidateProfile;
  score: number;
  signalScores?: SignalScores;      // NEW
  weightsApplied?: SignalWeightConfig; // NEW
  roleTypeUsed?: string;            // NEW
  matchRationale?: MatchRationale;  // NEW
  similarity: number;
  rationale: MatchRationale;
}
```

#### 2. Signal Score Breakdown Component
**New File**: `/headhunter-ui/src/components/Match/SignalScoreBreakdown.tsx`

**Features**:
- Display all 12 signals as horizontal bars
- Color-code by score range
- Tooltips with signal explanations
- Show weights applied (visualize as bar thickness)
- Expandable/collapsible

**Pseudocode**:
```tsx
interface Props {
  signalScores: SignalScores;
  weightsApplied: SignalWeightConfig;
  expanded: boolean;
}

const SignalScoreBreakdown: React.FC<Props> = ({ signalScores, weightsApplied, expanded }) => {
  const signals = [
    { name: 'Skills Match', score: signalScores.skillsExactMatch, weight: weightsApplied.skillsExactMatch },
    { name: 'Trajectory Fit', score: signalScores.trajectoryFit, weight: weightsApplied.trajectoryFit },
    // ... all signals
  ];

  return (
    <div className="signal-breakdown">
      {signals.map(signal => (
        <SignalBar
          key={signal.name}
          name={signal.name}
          score={signal.score}
          weight={signal.weight}
          tooltip={SIGNAL_EXPLANATIONS[signal.name]}
        />
      ))}
    </div>
  );
};
```

#### 3. Enhanced Candidate Card
**File**: `/headhunter-ui/src/components/Candidate/SkillAwareCandidateCard.tsx`

**Additions**:
- Add `<SignalScoreBreakdown>` in expanded state
- Display LLM-generated rationale if available (lines 515-543, extend)
- Show confidence badges for inferred skills
- "Why this candidate?" section with signal highlights

**Insertion Points**:
- After line 543 (AI hero section): Add rationale from backend
- After line 562 (skill cloud): Add signal breakdown toggle
- After line 589 (timeline): Add signal score breakdown

#### 4. Search Results Enhancements
**File**: `/headhunter-ui/src/components/Search/SearchResults.tsx`

**Additions**:
- Sort dropdown (lines 93-115, extend)
- Filter controls for signal thresholds
- Toggle: "Show signal details" (default: off)

**Pseudocode**:
```tsx
const [sortBy, setSortBy] = useState<'overall' | 'skills' | 'trajectory' | 'recency'>('overall');
const [minSkillScore, setMinSkillScore] = useState(0);
const [showSignalDetails, setShowSignalDetails] = useState(false);

const sortedAndFiltered = matches
  .filter(m => (m.signalScores?.skillsExactMatch ?? 0) >= minSkillScore / 100)
  .sort((a, b) => {
    if (sortBy === 'skills') return (b.signalScores?.skillsExactMatch ?? 0) - (a.signalScores?.skillsExactMatch ?? 0);
    if (sortBy === 'trajectory') return (b.signalScores?.trajectoryFit ?? 0) - (a.signalScores?.trajectoryFit ?? 0);
    // ... other sorts
    return b.score - a.score; // default
  });
```

### Backend Changes

#### 1. Extend Rerank Service
**File**: `/services/hh-rerank-svc/src/together-client.ts`

**Add Method**:
```typescript
async generateMatchRationale(
  jobDescription: string,
  candidate: { summary: string; signalScores: SignalScores },
  topSignals: Array<{ name: string; score: number }>
): Promise<MatchRationale> {
  const prompt = buildRationalePrompt(jobDescription, candidate, topSignals);
  const response = await this.chat(prompt);
  return parseRationaleResponse(response);
}
```

**Update Rerank Request**:
```typescript
export interface RerankRequest {
  // ... existing
  includeMatchRationale?: boolean;
  rationaleLimit?: number;
}
```

**Update Rerank Response**:
```typescript
export interface RerankResult {
  // ... existing
  matchRationale?: MatchRationale;
}
```

#### 2. Search Service Integration
**File**: `/services/hh-search-svc/src/search-service.ts`

**Modify** `applyRerankIfEnabled` (lines 594-644):
- Pass `includeMatchRationale: true` when `request.includeDebug` or top-20
- Merge rationale into results

**Pseudocode**:
```typescript
const rerankRequest: RerankRequest = {
  // ... existing fields
  includeMatchRationale: candidates.length <= 20, // Only for top 20
  rationaleLimit: 10 // Top 10 get full rationale
};
```

#### 3. Logging for Compliance
**New File**: `/services/hh-search-svc/src/audit-logger.ts`

**Features**:
- Log every search request to Firestore `search_audit_logs` collection
- Schema: `{ tenantId, userId, timestamp, query, filters, resultIds, signalScores, weights }`
- Retention: Auto-delete after 3 years (Firestore TTL)

**Integration**:
```typescript
// In search-service.ts, after generating results
await auditLogger.logSearch({
  tenantId: context.tenant.id,
  userId: context.user?.uid,
  query: request.query,
  filters: request.filters,
  results: response.results.slice(0, 20).map(r => ({
    candidateId: r.candidateId,
    score: r.score,
    signalScores: r.signalScores
  })),
  weights: resolvedWeights,
  timestamp: new Date()
});
```

---

## Inferred Skills Confidence Display

### Backend Data Available

**From Signal Calculators** (`/services/hh-search-svc/src/signal-calculators.ts`):
- `skillsInferred` score: 0-1 based on transferability rules (lines 232-279)
- Transferability scores defined: e.g., React → Vue.js = 0.75 (lines 182-215)

**From Candidate Metadata** (PRD lines 68-69):
- Together AI enrichment produces:
  - `explicit_skills`: 100% confidence
  - `inferred_skills`: Array with confidence (0-100) and evidence/reasoning

**Example Data**:
```json
{
  "intelligent_analysis": {
    "explicit_skills": {
      "technical_skills": ["Python", "AWS", "Docker"]
    },
    "inferred_skills": {
      "highly_probable_skills": [
        { "skill": "Kubernetes", "confidence": 0.92, "reasoning": "5 years Docker + cloud architecture" }
      ],
      "probable_skills": [
        { "skill": "Terraform", "confidence": 0.68, "reasoning": "AWS + IaC keywords in resume" }
      ]
    }
  }
}
```

### UI Display Strategy

#### Confidence Thresholds
- **High**: confidence ≥ 0.8 → Green badge "High confidence"
- **Medium**: 0.5 ≤ confidence < 0.8 → Yellow badge "Likely"
- **Low**: confidence < 0.5 → Gray badge "Possible"

#### Visual Design
**Skill Chip with Badge**:
```tsx
<div className="skill-chip inferred">
  Kubernetes
  <span className="confidence-badge high">High</span>
  <Tooltip content="5 years Docker + cloud architecture">ℹ️</Tooltip>
</div>
```

**Color Scheme**:
- Explicit skills: Blue background (existing)
- Inferred high: Green border + badge
- Inferred medium: Yellow border + badge
- Inferred low: Gray border + badge

#### Implementation in SkillAwareCandidateCard

**Modify** lines 546-562 (skill cloud):
```tsx
const allSkills = [
  ...technicalSkills.map(s => ({ skill: s, type: 'explicit', confidence: 1.0 })),
  ...(candidate.intelligent_analysis?.inferred_skills?.highly_probable_skills || [])
    .map(s => ({ skill: s.skill, type: 'inferred', confidence: s.confidence }))
];

const displaySkills = allSkills.slice(0, 12);

{displaySkills.map((skill, i) => (
  <SkillChip
    key={i}
    skill={skill.skill}
    type={skill.type}
    confidence={skill.confidence}
    evidence={skill.reasoning}
    isMatched={topSkills.includes(skill.skill)}
  />
))}
```

**New Component**: `SkillChip.tsx`
```tsx
interface Props {
  skill: string;
  type: 'explicit' | 'inferred';
  confidence: number;
  evidence?: string;
  isMatched: boolean;
}

const SkillChip: React.FC<Props> = ({ skill, type, confidence, evidence, isMatched }) => {
  const confidenceLevel = confidence >= 0.8 ? 'high' : confidence >= 0.5 ? 'medium' : 'low';

  return (
    <Tooltip content={type === 'inferred' ? evidence : undefined}>
      <span className={`skill-chip ${type} ${confidenceLevel} ${isMatched ? 'matched' : ''}`}>
        {skill}
        {type === 'inferred' && (
          <span className={`confidence-badge ${confidenceLevel}`}>
            {confidenceLevel === 'high' ? 'High' : confidenceLevel === 'medium' ? 'Likely' : 'Possible'}
          </span>
        )}
      </span>
    </Tooltip>
  );
};
```

---

## Performance Considerations

### Latency Budget

**Current Performance** (from PRD):
- p95 latency target: ≤ 1.2s
- Rerank target: ≤ 350ms @ K≤200

**Phase 9 Additions**:
- LLM rationale generation: +50-150ms (Together AI single pass)
- Frontend rendering: +10-20ms (signal breakdown UI)

**Total Impact**: +60-170ms (within 1.2s budget)

**Optimization Strategies**:
1. **Batch rationale generation**: Generate for all top-10 in single request
2. **Cache aggressively**: Redis cache with 24h TTL (same JD = same rationale)
3. **Progressive loading**: Show results immediately, load rationale async
4. **Skip for low-priority**: Only generate for top-10 (not all 20)

### Caching Strategy

**Redis Cache Keys**:
```
rationale:{candidateId}:{jdHash}:{modelVersion}
TTL: 86400 (24 hours)
```

**Cache Hit Rate Target**: ≥95% (same JDs searched repeatedly)

**Cache Invalidation**:
- Profile update: Clear all rationale keys for `candidateId`
- Model update: Bump `modelVersion` in keys
- Manual: Admin tool to flush rationale cache

---

## Testing Strategy

### Unit Tests

**Backend**:
1. **Signal Calculators** (existing in `/services/hh-search-svc/src/__tests__/signal-calculators.spec.ts` presumably)
   - Test each signal function with edge cases
   - Verify 0-1 normalization
   - Test transferability rules

2. **Rationale Generation** (new)
   - Mock Together AI responses
   - Test JSON parsing
   - Test cache hit/miss logic

**Frontend**:
1. **SignalScoreBreakdown Component**
   - Render with all signals
   - Test color coding logic
   - Test tooltip display

2. **SkillChip Component**
   - Test confidence badge logic
   - Test explicit vs inferred styling
   - Test tooltip evidence display

### Integration Tests

**End-to-End Flow**:
1. Search with job description
2. Verify top-20 results have `signalScores`
3. Verify top-10 results have `matchRationale`
4. Verify UI renders signal breakdown
5. Verify inferred skills show confidence badges

**Performance Tests**:
1. Measure latency with rationale generation (target: ≤1.2s p95)
2. Measure cache hit rate (target: ≥95%)
3. Load test: 100 concurrent searches (ensure no degradation)

### User Acceptance Testing

**Recruiter Scenarios**:
1. **Scenario 1**: "Why is this senior engineer ranked #1?"
   - Expectation: See skills match (92%), trajectory fit (87%), clear summary

2. **Scenario 2**: "What skills are inferred vs confirmed?"
   - Expectation: Green badges on high-confidence, yellow on medium, tooltips with evidence

3. **Scenario 3**: "How do I find candidates with strong trajectory?"
   - Expectation: Sort by "Trajectory Fit", filter with slider

4. **Scenario 4**: "Why did this candidate rank lower?"
   - Expectation: Expand signal breakdown, see low recency score (0.3), understand impact

---

## Open Questions & Decisions Needed

### 1. Signal Breakdown Display Defaults

**Question**: Should signal breakdown be:
- A) Collapsed by default (click to expand)
- B) Visible for top-3 candidates only
- C) Always visible for all results

**Recommendation**: **Option A** (collapsed by default)
- **Rationale**: Reduces visual clutter, progressive disclosure best practice
- **Exception**: Show for top-3 if "explainability mode" toggle enabled

### 2. LLM Rationale Scope

**Question**: Generate rationale for:
- A) Top-10 only (cost-optimized)
- B) Top-20 (full first page)
- C) On-demand (click to generate)

**Recommendation**: **Option A** (top-10)
- **Rationale**: Balances cost ($0.001/search) with value (recruiters rarely look past top-10)
- **Fallback**: Show signal breakdown without LLM summary for #11-20

### 3. Confidence Threshold for "Needs Verification"

**Question**: At what confidence level do we show "Needs verification" badge?
- A) < 0.75 (conservative)
- B) < 0.50 (moderate)
- C) < 0.30 (permissive)

**Recommendation**: **Option A** (< 0.75)
- **Rationale**: PRD mentions 0.75 as default threshold (line 191)
- **Aligns with**: "High confidence" ≥ 0.8 means medium (0.5-0.8) gets caution

### 4. Sort/Filter UI Placement

**Question**: Where to place sort/filter controls?
- A) Sticky header above results
- B) Right sidebar panel
- C) Dropdown menu in results summary

**Recommendation**: **Option A** (sticky header)
- **Rationale**: Always visible, standard pattern (LinkedIn, Indeed)
- **Design**: Horizontal bar with "Sort by:" dropdown + "Filter:" sliders

### 5. Audit Log Storage

**Question**: Store audit logs in:
- A) Firestore (easy queries, auto-TTL)
- B) Cloud SQL (relational, better for analytics)
- C) BigQuery (GDPR-compliant, data warehouse)

**Recommendation**: **Option A** (Firestore)
- **Rationale**: Simple integration, auto-TTL support, sufficient query capability
- **Future**: Export to BigQuery for long-term analytics if needed

---

## Risk Assessment

### High-Risk Items

1. **LLM Rationale Quality** (HIGH)
   - **Risk**: Generated explanations may be generic or incorrect
   - **Mitigation**: Human review of 50 samples, fallback to signal-only display
   - **Detection**: Log user feedback ("Was this helpful?") on rationale

2. **Frontend Performance** (MEDIUM)
   - **Risk**: Rendering 12 signal bars for 20 candidates may cause lag
   - **Mitigation**: Virtual scrolling, lazy render for collapsed state
   - **Detection**: Lighthouse performance audits, < 100ms target

3. **Compliance Gap** (MEDIUM)
   - **Risk**: Audit logs may not capture all required data
   - **Mitigation**: Legal review of log schema before launch
   - **Detection**: Quarterly compliance audits

### Low-Risk Items

1. **Type Mismatches** (LOW)
   - **Risk**: Frontend types may drift from backend
   - **Mitigation**: Generate frontend types from backend OpenAPI schema
   - **Detection**: CI type-check job

2. **Cache Staleness** (LOW)
   - **Risk**: Cached rationale may not reflect profile updates
   - **Mitigation**: TTL + invalidation on profile change
   - **Detection**: Monitor cache hit rate (should be ~95%)

---

## Success Metrics

### Functional Metrics

1. **Coverage**:
   - ✅ 100% of search results include `signalScores`
   - ✅ Top-10 results include `matchRationale` (when enabled)
   - ✅ All inferred skills show confidence badges

2. **Accuracy**:
   - ✅ Signal scores match documented formulas (unit test validation)
   - ✅ Rationale mentions at least 2 of top-3 signals (sample validation)
   - ✅ Confidence badges reflect thresholds (High ≥0.8, Medium 0.5-0.8, Low <0.5)

### Performance Metrics

1. **Latency**:
   - ✅ p95 search latency ≤ 1.2s (with rationale generation)
   - ✅ Rationale generation ≤ 150ms (Together AI single pass)
   - ✅ Frontend render time ≤ 100ms (signal breakdown UI)

2. **Reliability**:
   - ✅ Cache hit rate ≥ 95% (for rationale)
   - ✅ JSON parse success rate ≥ 99% (Together AI responses)
   - ✅ Zero crashes from missing signalScores (defensive defaults)

### User Metrics

1. **Engagement**:
   - Target: ≥60% of recruiters expand signal breakdown at least once per session
   - Target: ≥40% of recruiters use sort/filter by signal scores

2. **Satisfaction**:
   - Survey: "I understand why candidates were ranked this way" ≥ 4.5/5
   - Survey: "Inferred skill confidence badges are helpful" ≥ 4.0/5

3. **Trust**:
   - Measure: % of searches where top-ranked candidate is shortlisted
   - Target: ≥70% (baseline TBD from current data)

### Compliance Metrics

1. **Audit Readiness**:
   - ✅ 100% of searches logged with signal scores + weights
   - ✅ Logs retained for ≥3 years
   - ✅ Export capability tested quarterly

2. **Transparency**:
   - ✅ UI displays "AI-assisted ranking" notice on every search
   - ✅ Signal formulas documented in public-facing help docs
   - ✅ User guide includes "How rankings work" section

---

## Dependencies & Sequencing

### Prerequisites (Must Be Complete)

1. ✅ **Phase 7: Multi-Signal Scoring** - All signals computed and returned
2. ✅ **Phase 8: Career Trajectory** - Trajectory signal integrated
3. ✅ **Search Service Returns Signal Scores** - Backend API complete

### Parallel Work Streams

**Stream 1: Backend (LLM Rationale)**
- Week 1: Extend rerank service with rationale generation
- Week 2: Integrate into search-service.ts
- Week 3: Add caching + audit logging

**Stream 2: Frontend (Signal UI)**
- Week 1: Create SignalScoreBreakdown component + types
- Week 2: Integrate into SkillAwareCandidateCard
- Week 3: Add sort/filter controls to SearchResults

**Stream 3: Inferred Skills**
- Week 1: Create SkillChip component with confidence badges
- Week 2: Integrate into skill cloud display
- Week 3: Add evidence tooltips

**Stream 4: Compliance**
- Week 1: Implement audit logging
- Week 2: Add UI notices ("AI-assisted ranking")
- Week 3: Create export tool for audit logs

### Integration Point
- **Week 4**: Merge all streams, end-to-end testing

---

## Recommended Plan Outline

### Phase 9.1: Backend Foundation
**Deliverables**:
1. Extend rerank service with rationale generation
2. Add audit logging for compliance
3. Update search API to return rationale for top-10

**Success Criteria**:
- Rationale generated for top-10 in ≤150ms
- 100% of searches logged with full signal data

### Phase 9.2: Frontend Signal Breakdown
**Deliverables**:
1. Create SignalScoreBreakdown component
2. Integrate into SkillAwareCandidateCard
3. Add collapsible state management

**Success Criteria**:
- Signal breakdown renders for all candidates
- Expand/collapse works smoothly
- Color coding matches design spec

### Phase 9.3: Inferred Skills Confidence
**Deliverables**:
1. Create SkillChip component with badges
2. Integrate confidence thresholds
3. Add evidence tooltips

**Success Criteria**:
- All inferred skills show confidence badges
- Tooltips display evidence from Together AI

### Phase 9.4: Sort/Filter UX
**Deliverables**:
1. Add sort dropdown (overall | skills | trajectory | recency)
2. Add filter sliders (min skill score, min trajectory score)
3. Persist preferences in localStorage

**Success Criteria**:
- Sorting updates results instantly
- Filtering hides candidates below threshold
- Preferences persist across sessions

### Phase 9.5: Polish & Compliance
**Deliverables**:
1. Add "AI-assisted ranking" notice
2. Create help docs ("How rankings work")
3. Build audit log export tool
4. User acceptance testing with recruiters

**Success Criteria**:
- All compliance requirements met
- Recruiter satisfaction ≥ 4.5/5
- Zero blocking bugs

---

## Key Takeaways for Planning

### What's Already Done
1. ✅ Backend computes all 12 signals and returns in API
2. ✅ Match reasons generated as text bullets
3. ✅ Signal calculation formulas documented and tested
4. ✅ Together AI integration exists (rerank service)
5. ✅ Frontend has candidate card component (just needs signal display)

### What Needs Building
1. ❌ LLM rationale generation (extend rerank service)
2. ❌ Signal score breakdown UI component
3. ❌ Inferred skills confidence badges
4. ❌ Sort/filter controls
5. ❌ Audit logging for compliance

### Biggest Unknowns
1. **LLM rationale quality**: Will Together AI generate useful explanations? (Mitigation: test with 50 samples)
2. **User adoption**: Will recruiters actually use signal breakdown? (Mitigation: user testing before launch)
3. **Performance**: Will rendering 12 signals × 20 candidates cause lag? (Mitigation: benchmark early)

### Recommended Next Steps
1. **Validate LLM rationale**: Generate 20 sample rationales and review with recruiter
2. **UI mockups**: Design signal breakdown component (Figma or sketch)
3. **Performance baseline**: Measure current search latency (before Phase 9 changes)
4. **Legal review**: Confirm audit log schema meets NYC/EU requirements

---

**End of Research Document**
