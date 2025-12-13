# Handover: Gemini Rerank Integration

## Summary
Successfully integrated Gemini 2.5 Flash as the primary reranking provider for `hh-rerank-svc`. The service now prioritizes Gemini, falling back to Together AI only if Gemini fails or times out.

## Key Changes & Fixes

### 1. Latency Optimization (Thinking Mode)
- **Issue**: Gemini 2.5 Flash has a "thinking mode" enabled by default, causing latency >11s.
- **Fix**: Explicitly disabled this mode by passing `thinking_config: { thinking_budget: 0 }` (snake_case) in the API request.
- **Result**: Latency reduced to ~6-7s.

### 2. JSON Parsing Reliability
- **Issue**: Gemini often wraps JSON responses in Markdown code blocks (e.g., \`\`\`json ... \`\`\`), causing `JSON.parse` to fail.
- **Fix**: Implemented response sanitization in `gemini-client.ts` and `together-client.ts` to strip Markdown before parsing.

### 3. SLA and Timeout Tuning
- **Issue**: The original 3s SLA was too aggressive for Gemini 2.5 Flash.
- **Update**:
    - `RERANK_SLA_TARGET_MS` increased to `10000` (10s).
    - `GEMINI_TIMEOUT_MS` set to `8000` (8s).

### 4. Search Quality Improvements (Executive Roles)
- **Issue**: Search for "CTO" was returning "Engineering Manager" due to low weight on experience/title match.
- **Fix**:
    - Added C-level keywords (`cto`, `chief`, `founder`, etc.) to `executive` level in `vector-search.ts`.
    - Adjusted ranking weights in `api.ts` to prioritize semantic context and seniority over keywords:
        - **Executive**: `vector_similarity` (0.4), `experience_match` (0.3), `skill_match` (0.2).
        - **General**: `vector_similarity` (0.35), `skill_match` (0.35), `experience_match` (0.15).
- **Result**: Executive searches now prioritize title/seniority and semantic context (e.g., "scale-up", "B2B") over pure skill keyword matching.

### 5. AI-First Architecture (Dec 2025)
- **Job Analysis**: Implemented `analyzeJob` (Gemini) to extract structured requirements (Skills, Level, Key Focus) from raw job descriptions.
  - *Impact*: Eliminates regex-guessing; provides richer signals for Vector Search.
- **Reasoning Reranker**: Updated `rerankCandidates` to use **Few-Shot Reasoning** instead of hard rules.
  - *Logic*: "Recruiter Mentality" prompt teaches Gemini to penalize Title/Scope mismatches (e.g. "Senior Dev != CTO") via examples.
- **Latency Optimization**:
  - **Batch Size**: Reduced from 75 to 50 to prevent 5-minute timeouts.
  - **Payload**: Truncated candidate content to 4000 chars (approx 1000 tokens) to speed up generation.
  - *Result*: Search latency < 45s.

## Current Status
- **Primary Provider**: Gemini 2.5 Flash (`gemini-2.5-flash`).
- **Fallback Provider**: Together AI (Qwen 2.5 32B).
- **Performance**: Average Gemini latency is ~6.4s.
- **Environment**: Deployed to `hh-rerank-svc-production`.

## Next Steps
- **Monitor Latency**: Keep an eye on production latency. If ~6-7s is deemed too slow for user experience, consider exploring faster models or further prompt engineering.
- **Cost Analysis**: Compare costs of Gemini vs. Together AI at scale.
## Batch Enrichment & Search Agent
### 1. Batch Enrichment Architecture
- **Service**: `batchEnrichCandidates` Cloud Function (Node.js 20).
- **Model**: Gemini 2.5 Flash (`gemini-2.5-flash`) via `GoogleGenerativeAI` SDK.
- **Access**: Uses `GOOGLE_API_KEY` (stored in `functions/.env`).
- **Logic**: "Senior Executive Recruiter" persona with strict education filtering (Undergrad/Grad only) and email extraction.
- **Orchestration**: `scripts/run_batch_enrichment.js` manages pagination and rate limiting.

### 2. Search Agent
- **Service**: `analyzeSearchQuery` Cloud Function.
- **Model**: Gemini 2.5 Flash.
- **Functionality**: Converts natural language queries into structured search parameters (Role, Seniority, Context, Filters).
- **Integration**: Frontend `Dashboard.tsx` intercepts queries and displays AI analysis before searching.
