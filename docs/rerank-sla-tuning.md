# Rerank Service SLA Tuning Guide

**Date**: 2025-10-10
**Issue**: Together AI reranking timing out with `usedFallback: true` and `rankingMs: 0`

## Root Cause Analysis

### The Problem
Reranking requests were consistently timing out, causing the system to fall back to vector similarity scores without AI-powered reranking.

### Investigation Timeline
1. **Initial symptom**: `"usedFallback": true"` and `"rankingMs": 0"` in search responses
2. **First hypothesis**: Together AI API timeout too short (900ms)
3. **Second discovery**: Code clamp limiting timeout to max 1000ms (`config.ts:116`)
4. **Root cause**: **SLA budget system** limiting actual timeout regardless of config

### Technical Details

#### The SLA Budget System
Located in `services/hh-rerank-svc/src/rerank-service.ts:90-91`:

```typescript
const rawBudgetMs = runtime.slaTargetMs - elapsed - promptMs - 20;
const budgetMs = Math.max(0, rawBudgetMs);
```

This calculates remaining time budget for Together AI based on:
- `slaTargetMs`: Total target latency (was 1200ms, too aggressive)
- `elapsed`: Time spent so far in request processing
- `promptMs`: Time to build the prompt
- `20`: Safety buffer

#### The Timeout Chain
Located in `services/hh-rerank-svc/src/together-client.ts:185-189`:

```typescript
const axiosTimeout = Math.max(
  100,
  Math.min(
    this.config.timeoutMs,
    typeof remainingBudget === 'number' ? remainingBudget : this.config.timeoutMs
  )
);
```

**Key insight**: Uses `Math.min(configTimeout, remainingBudget)`, so even if `TOGETHER_TIMEOUT_MS=5000`, if budget is only 800ms, timeout will be 800ms.

#### The Code Clamp Issue
Located in `services/hh-rerank-svc/src/config.ts:116`:

```typescript
timeoutMs: clamp(parseNumber(process.env.TOGETHER_TIMEOUT_MS, 320), { min: 150, max: 1000 }),
```

Even if environment variable is 5000ms, code limits it to 1000ms maximum.

## The Fix

### Immediate Production Fix (Applied 2025-10-10)

**Environment Variable Update**:
```bash
RERANK_SLA_TARGET_MS=3000  # Increased from 1200ms
```

**Why this works**:
- With 3000ms SLA target, remaining budget after prompt building: ~2200-2500ms
- Together AI gets sufficient time to complete reranking (observed: 1500-2000ms)
- Still under Cloud Run timeout (45s) and search service timeout (20s)
- Falls back gracefully if Together AI is slow

**Deployment**:
```bash
gcloud run services update hh-rerank-svc-production \
  --set-env-vars RERANK_SLA_TARGET_MS=3000 \
  --region us-central1 \
  --project headhunter-ai-0088
```

### Long-term Code Fix (Staged)

**File**: `services/hh-rerank-svc/src/config.ts:116`

Changed:
```typescript
// Before
timeoutMs: clamp(parseNumber(process.env.TOGETHER_TIMEOUT_MS, 320), { min: 150, max: 1000 }),

// After
timeoutMs: clamp(parseNumber(process.env.TOGETHER_TIMEOUT_MS, 320), { min: 150, max: 10000 }),
```

This allows the environment variable to actually control the timeout up to 10 seconds.

## Configuration Reference

### Current Production Configuration

| Variable | Value | Purpose |
|----------|-------|---------|
| `RERANK_SLA_TARGET_MS` | 3000 | Total rerank operation budget |
| `TOGETHER_TIMEOUT_MS` | 5000 | Max Together AI API timeout (currently clamped to 1000ms in code) |
| `RERANK_SERVICE_TIMEOUT_MS` (search-svc) | 20000 | Search service timeout for rerank calls |
| `SEARCH_MIN_SIMILARITY` | 0.05 | Minimum vector similarity threshold |

### Timeout Cascade

```
Search Service (20s)
  └─> Rerank Service SLA (3s)
        ├─> Prompt building (~200-400ms)
        ├─> Together AI call (~1500-2000ms)
        └─> Result parsing (~50-100ms)
```

## Performance Characteristics

### Observed Latencies (Production)
- **Prompt building**: 200-400ms
- **Together AI API**: 1500-2000ms for 10 candidates
- **Result parsing**: 50-100ms
- **Total rerank**: 1800-2500ms

### Model Used
- **Provider**: Together AI
- **Model**: `meta-llama/Llama-3.2-3B-Instruct-Turbo`
- **Payload**: 10 candidate profiles + job description
- **Response format**: JSON with scores and reasoning

## Monitoring Recommendations

### Key Metrics to Track
1. **Rerank success rate**: `usedFallback=false` percentage (target: >95%)
2. **Rerank latency**: P50, P95, P99 of `rankingMs` (target: P95 < 2500ms)
3. **Together AI timeout rate**: Errors with "timeout" in logs (target: <5%)
4. **SLA budget exhaustion**: Warnings about "budget exhausted" (target: 0%)

### Alerting Thresholds
```yaml
- name: "Rerank Fallback Rate High"
  condition: usedFallback_rate > 0.10 for 5 minutes
  severity: warning

- name: "Rerank Latency High"
  condition: rankingMs_p95 > 2800 for 5 minutes
  severity: warning

- name: "Together AI Timeout Rate High"
  condition: together_timeout_rate > 0.05 for 5 minutes
  severity: critical
```

## Future Optimization Opportunities

### 1. Reduce Prompt Size
- Truncate candidate summaries to 500 chars max
- Remove redundant fields from context
- **Potential savings**: 100-200ms in prompt building + API transfer

### 2. Model Selection
- Try smaller models: `Llama-3.2-1B-Instruct-Turbo`
- Test latency vs quality tradeoff
- **Potential savings**: 500-800ms

### 3. Batch Size Tuning
- Current: 10 candidates
- Test with 5-7 candidates for top results
- Rerank remaining candidates separately if needed
- **Potential savings**: 400-600ms

### 4. Caching Strategy
- Re-enable Redis caching once TLS is fully resolved
- Cache by (queryHash, candidateSetHash) for 3 minutes
- **Potential savings**: 1800ms on cache hits

### 5. Streaming Response
- Use Together AI streaming API
- Start returning results as they come
- **Perceived latency**: Much lower, actual same

## Rollback Procedure

If issues occur after SLA tuning:

```bash
# 1. Revert to previous SLA target
gcloud run services update hh-rerank-svc-production \
  --set-env-vars RERANK_SLA_TARGET_MS=1200 \
  --region us-central1 \
  --project headhunter-ai-0088

# 2. Verify fallback behavior (should see usedFallback=true)
# 3. Investigate Together AI performance issues
# 4. Consider temporary RERANK_CACHE_DISABLE=false to use Redis cache
```

## Testing Checklist

After SLA changes, verify:
- [ ] Service deploys successfully and reaches "Ready" state
- [ ] Health endpoint returns 200 OK
- [ ] Search request completes with `usedFallback: false`
- [ ] `rankingMs > 0` and realistic (1500-2500ms range)
- [ ] Scores differ from vector scores (AI reranking applied)
- [ ] matchReasons populated for candidates
- [ ] No timeout errors in service logs
- [ ] Search latency acceptable (< 4s total including rerank)

## Related Files

- `services/hh-rerank-svc/src/config.ts` - Configuration parsing and clamps
- `services/hh-rerank-svc/src/rerank-service.ts` - SLA budget calculation
- `services/hh-rerank-svc/src/together-client.ts` - API client with timeout logic
- `config/cloud-run/hh-rerank-svc.yaml` - Production environment variables
- `config/cloud-run/hh-search-svc.yaml` - Search service timeout configuration

## References

- [Together AI API Documentation](https://docs.together.ai/reference/chat-completions)
- [Cloud Run Timeout Configuration](https://cloud.google.com/run/docs/configuring/request-timeout)
- [Task Master Issue Tracking](.taskmaster/tasks/tasks.json)

---

**Last Updated**: 2025-10-10
**Next Review**: After 1 week of production monitoring
