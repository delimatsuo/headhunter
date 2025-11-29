# Headhunter: AI-Powered Candidate Intelligence Platform

## Executive Summary

Headhunter is an AI-powered semantic search and candidate enrichment platform designed for executive recruiters. It transforms unstructured candidate data (resumes, recruiter notes, experience descriptions) into structured, searchable profiles with intelligent skill inference and relevance ranking.

**Core Value Proposition**: Paste a job description, get back the top 20 most relevant candidates from your database—ranked by AI with explanations of *why* each candidate matches.

---

## What Headhunter Does

### 1. Candidate Enrichment (Ingestion Pipeline)

When candidate data enters the system, Headhunter uses LLMs to analyze and structure the information:

**Input**: Raw resume text, recruiter comments, LinkedIn profiles, experience history

**Output**: Structured candidate profile including:
- **Explicit Skills**: Skills directly mentioned (e.g., "Python", "AWS", "Kubernetes")
- **Inferred Skills**: Skills implied by experience with confidence scores (0-100%) and evidence
- **Career Analysis**: Seniority level, years of experience, career trajectory, progression speed
- **Company Pedigree**: Company tier classification, stability patterns
- **Market Insights**: Placement likelihood, best-fit roles, target companies
- **Executive Summary**: One-line pitch and overall rating (0-100)

**Example Enriched Profile Structure**:
```json
{
  "candidate_id": "123456",
  "personal_details": {
    "name": "Jane Doe",
    "seniority_level": "Senior",
    "years_of_experience": 8,
    "location": "São Paulo, Brazil"
  },
  "intelligent_analysis": {
    "explicit_skills": {
      "technical_skills": ["Python", "AWS", "Docker", "PostgreSQL"],
      "soft_skills": ["Leadership", "Communication"]
    },
    "inferred_skills": [
      {
        "skill": "Kubernetes",
        "confidence": 85,
        "evidence": "Led containerization initiative at Company X, mentions Docker orchestration"
      },
      {
        "skill": "System Design",
        "confidence": 78,
        "evidence": "Architected microservices handling 10M+ requests/day"
      }
    ],
    "career_trajectory": {
      "current_level": "Staff Engineer",
      "progression_speed": "fast",
      "trajectory_type": "technical_leadership"
    },
    "executive_summary": {
      "one_line_pitch": "Staff engineer with deep AWS/Python expertise and proven tech leadership at scale",
      "overall_rating": 87
    }
  },
  "embedding_vector": [768-dimensional float array],
  "resume_updated_at": "2024-06-15T00:00:00Z"
}
```

### 2. Semantic Search (Hybrid Retrieval)

Headhunter uses a two-stage retrieval system combining vector similarity with keyword matching:

**Stage 1: Recall (Top ~200 candidates)**
- **Vector Search (pgvector/HNSW)**: Finds semantically similar candidates using 768-dimensional embeddings
- **Full-Text Search (PostgreSQL FTS)**: Portuguese and English keyword matching with BM25 scoring
- **Score Fusion**: Combines vector similarity and text relevance into unified ranking

**Stage 2: Rerank (Top 20 candidates)**
- **LLM Reranking**: Gemini 2.5 Flash analyzes job description against candidate profiles
- **Evidence Generation**: Produces "Why this candidate matches" explanations
- **Final Scoring**: Combines semantic similarity, skill match, experience alignment

**Search Flow**:
```
Job Description (EN or PT-BR)
    ↓
Embed query → 768-dim vector
    ↓
Parallel retrieval:
  • pgvector: cosine similarity on candidate embeddings
  • PostgreSQL FTS: keyword/phrase matching
    ↓
Score fusion → Top ~200 candidates
    ↓
LLM Rerank (Gemini 2.5 Flash)
    ↓
Top 20 candidates with match explanations
```

### 3. Explainability & Evidence

Every search result includes:
- **Match Score**: 0-100 relevance rating
- **Why Match Bullets**: Human-readable explanations
- **Skill Alignment**: Which required skills the candidate has (explicit vs. inferred)
- **Experience Relevance**: How their background maps to the role
- **Confidence Indicators**: "Needs verification" tags for low-confidence inferences

---

## Technical Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway                               │
│              (Authentication, Rate Limiting, Routing)            │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ↓                       ↓                       ↓
┌───────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  hh-search-svc│     │  hh-embed-svc   │     │  hh-enrich-svc  │
│  (Search API) │     │  (Embeddings)   │     │  (Enrichment)   │
└───────┬───────┘     └────────┬────────┘     └────────┬────────┘
        │                      │                       │
        ↓                      ↓                       ↓
┌───────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ hh-rerank-svc │     │   Cloud SQL     │     │   Together AI   │
│ (LLM Rerank)  │     │   (pgvector)    │     │   (Qwen 2.5)    │
└───────────────┘     └─────────────────┘     └─────────────────┘
        │
        ↓
┌───────────────┐
│  Gemini 2.5   │
│    Flash      │
└───────────────┘
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **API Layer** | Fastify (Node.js/TypeScript) | 8 microservices on Cloud Run |
| **Enrichment LLM** | Together AI (Qwen 2.5 32B Instruct) | Single-pass candidate analysis |
| **Reranking LLM** | Gemini 2.5 Flash | Fast, schema-enforced reranking |
| **Embeddings** | VertexAI text-embedding-004 | 768-dimensional vectors |
| **Vector Store** | PostgreSQL + pgvector (HNSW) | Semantic similarity search |
| **Full-Text Search** | PostgreSQL FTS | Portuguese/English BM25 |
| **Profile Storage** | Firestore | Candidate profiles, metadata |
| **Caching** | Redis Memorystore | Query caching, rate limiting |
| **File Storage** | Cloud Storage | Resumes (encrypted, signed URLs) |

---

## API Reference

### Authentication

All API requests require:
- `x-api-key` header: API key for your organization
- `X-Tenant-ID` header: Your tenant identifier

### Core Endpoints

#### 1. Hybrid Search
```http
POST /v1/search/hybrid
Content-Type: application/json
x-api-key: {your-api-key}
X-Tenant-ID: {your-tenant-id}

{
  "jobDescription": "Senior Software Engineer with 5+ years Python experience...",
  "limit": 20,
  "includeDebug": false
}
```

**Response**:
```json
{
  "results": [
    {
      "candidateId": "509113109",
      "name": "Jane Doe",
      "currentRole": "Staff Engineer",
      "company": "TechCorp",
      "score": 0.87,
      "matchReasons": [
        "8 years Python experience with production systems",
        "AWS architecture expertise matches requirements",
        "Leadership experience with 5-person team"
      ],
      "skills": {
        "matched": ["Python", "AWS", "PostgreSQL"],
        "inferred": [{"skill": "System Design", "confidence": 85}]
      }
    }
  ],
  "metadata": {
    "totalCandidates": 28988,
    "searchTimeMs": 961,
    "llmProvider": "gemini"
  },
  "timings": {
    "embeddingMs": 50,
    "retrievalMs": 80,
    "rerankMs": 350
  }
}
```

#### 2. Candidate Lookup
```http
GET /v1/candidates/{candidateId}
x-api-key: {your-api-key}
X-Tenant-ID: {your-tenant-id}
```

#### 3. Bulk Candidate Ingestion
```http
POST /v1/candidates/bulk
Content-Type: application/json
x-api-key: {your-api-key}
X-Tenant-ID: {your-tenant-id}

{
  "candidates": [
    {
      "externalId": "ats-12345",
      "resumeText": "...",
      "recruiterNotes": "...",
      "linkedinUrl": "https://linkedin.com/in/..."
    }
  ]
}
```

#### 4. Generate Embeddings
```http
POST /v1/embeddings/generate
Content-Type: application/json
x-api-key: {your-api-key}
X-Tenant-ID: {your-tenant-id}

{
  "candidateId": "123456",
  "text": "Enriched profile text for embedding..."
}
```

---

## Integration Patterns

### Pattern 1: Search Augmentation

Your ATS handles candidate management; Headhunter provides intelligent search.

```
┌─────────────┐      Job Description      ┌─────────────────┐
│   Your ATS  │ ─────────────────────────→│   Headhunter    │
│             │                           │   Search API    │
│             │←─────────────────────────│                 │
└─────────────┘   Ranked Candidate IDs    └─────────────────┘
       │
       ↓
  Display results in your UI
  (fetch full profiles from your ATS)
```

**Implementation**:
1. Sync candidates to Headhunter via bulk ingestion API
2. When recruiter searches, call Headhunter's `/v1/search/hybrid`
3. Map returned `candidateId` to your ATS records
4. Display results with Headhunter's match explanations

### Pattern 2: Enrichment Service

Use Headhunter to enrich candidates, store results in your ATS.

```
New Candidate in ATS
       │
       ↓
POST to Headhunter /v1/enrich
       │
       ↓
Receive structured profile
       │
       ↓
Store enriched data in your ATS
```

**Enriched Fields You'll Receive**:
- Extracted skills (explicit + inferred with confidence)
- Seniority classification
- Career trajectory analysis
- Executive summary / one-liner
- Quality score (0-100)

### Pattern 3: Full Integration (Recommended)

Headhunter manages search and enrichment; your ATS handles workflows.

```
┌─────────────────────────────────────────────────────────┐
│                       Your ATS                          │
│  (Candidate Management, Workflows, Communication)       │
└────────────────────────┬────────────────────────────────┘
                         │
           ┌─────────────┴─────────────┐
           │      Headhunter API       │
           │  • Search (hybrid)        │
           │  • Enrichment             │
           │  • Candidate sync         │
           └───────────────────────────┘
```

**Sync Strategy**:
- **Real-time**: Webhook on candidate create/update → POST to Headhunter
- **Batch**: Nightly sync of new/modified candidates
- **On-demand**: Enrich individual candidates when accessed

---

## Data Flow Example

### Scenario: Recruiter searches for "Senior Backend Engineer Python AWS"

```
1. ATS Frontend
   └─→ User enters job description

2. Your ATS Backend
   └─→ POST /v1/search/hybrid to Headhunter
       Body: { "jobDescription": "Senior Backend Engineer...", "limit": 20 }

3. Headhunter Processing (961ms typical)
   ├─→ Generate query embedding (50ms)
   ├─→ pgvector similarity search → 200 candidates (80ms)
   ├─→ PostgreSQL FTS for keywords (parallel)
   ├─→ Score fusion and filtering
   └─→ Gemini rerank top candidates (350ms)

4. Response to ATS
   └─→ Top 20 candidates with:
       • candidateId (map to your records)
       • score (0-1 relevance)
       • matchReasons (human-readable)
       • skills.matched / skills.inferred

5. ATS Display
   └─→ Show results with Headhunter explanations
       Recruiter clicks → opens full profile in your ATS
```

---

## Performance Characteristics

| Metric | Target | Current |
|--------|--------|---------|
| Search Latency (p95) | ≤ 1.2s | 961ms |
| Rerank Latency | ≤ 350ms | 350ms |
| Enrichment Success Rate | ≥ 95% | 98.4% |
| JSON Validation Rate | ≥ 95% | 99%+ |
| Embedding Dimensions | 768 | 768 |

---

## Security & Compliance

- **Multi-tenant isolation**: Each organization's data is logically separated
- **API authentication**: API key + tenant ID validation
- **PII minimization**: LLM prompts designed to minimize sensitive data exposure
- **Encrypted storage**: Resumes encrypted at rest, accessed via signed URLs
- **No data retention by LLM providers**: Together AI configured for no training/retention
- **Audit logging**: All data access logged for compliance

---

## Getting Started

### 1. Request Access
Contact us to provision your tenant and receive API credentials.

### 2. Initial Sync
Bulk upload your existing candidate database:
```bash
curl -X POST https://api.headhunter.example/v1/candidates/bulk \
  -H "x-api-key: YOUR_KEY" \
  -H "X-Tenant-ID: YOUR_TENANT" \
  -H "Content-Type: application/json" \
  -d @candidates.json
```

### 3. Test Search
```bash
curl -X POST https://api.headhunter.example/v1/search/hybrid \
  -H "x-api-key: YOUR_KEY" \
  -H "X-Tenant-ID: YOUR_TENANT" \
  -H "Content-Type: application/json" \
  -d '{"jobDescription": "Senior Software Engineer Python AWS", "limit": 10}'
```

### 4. Integrate
- Add search endpoint to your ATS job search flow
- Map `candidateId` responses to your internal records
- Display `matchReasons` in your UI

---

## Practical Integration Details

### External ID Mapping

Headhunter supports linking candidates to your ATS records via `externalId`:

```json
// When syncing a candidate
{
  "externalId": "ella-ats-12345",  // Your ATS's internal ID
  "resumeText": "...",
  "recruiterNotes": "..."
}
```

**Search results include both IDs**:
```json
{
  "candidateId": "hh-509113109",    // Headhunter's internal ID
  "externalId": "ella-ats-12345",   // Your ATS ID (for easy mapping)
  "name": "Jane Doe",
  ...
}
```

**Recommendation**: Always store the `candidateId` ↔ `externalId` mapping in your system for reliable cross-referencing.

---

### Rate Limits & Quotas

| Endpoint | Rate Limit | Burst | Notes |
|----------|------------|-------|-------|
| `/v1/search/hybrid` | 100 req/min | 20 | Per tenant |
| `/v1/candidates/bulk` | 10 req/min | 2 | Max 500 candidates per request |
| `/v1/candidates/{id}` | 300 req/min | 50 | Per tenant |
| `/v1/embeddings/generate` | 50 req/min | 10 | LLM-backed, higher latency |

**Rate Limit Headers** (returned on every response):
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1699574400
```

**When rate limited** (HTTP 429):
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Retry after 45 seconds.",
  "retryAfter": 45
}
```

---

### Error Handling

**Standard Error Response Format**:
```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "details": { },
  "requestId": "req-abc123"
}
```

**Common Error Codes**:

| HTTP | Error Code | Cause | Action |
|------|------------|-------|--------|
| 400 | `invalid_request` | Malformed JSON or missing required fields | Fix request payload |
| 401 | `unauthorized` | Invalid or missing API key | Check `x-api-key` header |
| 403 | `forbidden` | Tenant mismatch or insufficient permissions | Verify `X-Tenant-ID` |
| 404 | `candidate_not_found` | Candidate ID doesn't exist | Verify ID or sync candidate first |
| 409 | `duplicate_candidate` | Candidate with same `externalId` exists | Use update endpoint instead |
| 422 | `enrichment_failed` | LLM couldn't parse resume | Check resume quality, retry |
| 429 | `rate_limit_exceeded` | Too many requests | Implement backoff, respect `retryAfter` |
| 500 | `internal_error` | Server error | Retry with exponential backoff |
| 503 | `service_unavailable` | Temporary overload | Retry after 30-60 seconds |

**Retry Strategy Recommendation**:
```
Attempt 1: Immediate
Attempt 2: Wait 1 second
Attempt 3: Wait 3 seconds
Attempt 4: Wait 10 seconds
Attempt 5: Wait 30 seconds
Give up after 5 attempts
```

---

### Asynchronous Processing (Enrichment)

Enrichment is **asynchronous** for bulk operations. The flow is:

```
1. POST /v1/candidates/bulk
   └─→ Returns: { "batchId": "batch-xyz", "status": "processing", "count": 150 }

2. Poll GET /v1/batches/{batchId}
   └─→ Returns: { "status": "processing", "processed": 75, "total": 150 }

3. Poll again...
   └─→ Returns: { "status": "completed", "processed": 150, "total": 150,
                  "succeeded": 147, "failed": 3,
                  "failures": [{ "externalId": "...", "error": "..." }] }
```

**Alternative: Webhooks** (recommended for production):

```http
POST /v1/candidates/bulk
x-api-key: {key}
X-Tenant-ID: {tenant}
X-Webhook-URL: https://your-ats.com/webhooks/headhunter

{
  "candidates": [...]
}
```

**Webhook Payload** (sent to your URL on completion):
```json
{
  "event": "batch.completed",
  "batchId": "batch-xyz",
  "timestamp": "2024-11-28T10:30:00Z",
  "summary": {
    "total": 150,
    "succeeded": 147,
    "failed": 3
  },
  "failures": [
    { "externalId": "ella-456", "error": "empty_resume" }
  ]
}
```

**Webhook Events**:
| Event | Description |
|-------|-------------|
| `batch.completed` | Bulk enrichment finished |
| `candidate.enriched` | Single candidate enrichment complete |
| `candidate.updated` | Candidate profile was modified |

---

### Supported Resume Formats

| Format | Support | Notes |
|--------|---------|-------|
| Plain text | ✅ Full | Best results—send pre-extracted text |
| PDF | ✅ Full | Text extracted server-side |
| DOCX | ✅ Full | Text extracted server-side |
| DOC | ⚠️ Partial | Legacy format, some formatting loss |
| HTML | ✅ Full | Tags stripped, text preserved |
| Images (PNG/JPG) | ❌ None | OCR not currently supported |

**Best Practice**: If your ATS already extracts resume text, send the extracted text via `resumeText` field rather than raw files. This ensures consistent results and faster processing.

---

### Language Support

| Language | Search | Enrichment | FTS |
|----------|--------|------------|-----|
| English | ✅ Full | ✅ Full | ✅ Full |
| Portuguese (BR) | ✅ Full | ✅ Full | ✅ Full |
| Spanish | ✅ Good | ✅ Good | ⚠️ Basic |
| Other | ⚠️ Basic | ⚠️ Basic | ❌ None |

The LLMs handle multilingual content well. Full-text search is optimized for Portuguese and English.

---

### Candidate Lifecycle Management

#### Creating Candidates
```http
POST /v1/candidates
{
  "externalId": "ella-12345",
  "resumeText": "...",
  "recruiterNotes": "Strong communicator, seeking senior roles"
}
```

#### Updating Candidates
```http
PUT /v1/candidates/{candidateId}
{
  "resumeText": "Updated resume...",
  "recruiterNotes": "Added after interview"
}
```
- Updates trigger re-enrichment and re-embedding
- Previous enrichment data is versioned (accessible via `?includeHistory=true`)

#### Deleting Candidates
```http
DELETE /v1/candidates/{candidateId}
```
- Removes from search index immediately
- Profile data retained for 30 days (compliance), then purged
- Embeddings deleted immediately

#### Deduplication
Headhunter detects potential duplicates via:
- Exact `externalId` match → returns 409 Conflict
- Fuzzy name + email match → returns warning with `potentialDuplicates` array

```json
{
  "candidateId": "hh-new-123",
  "warnings": [
    {
      "type": "potential_duplicate",
      "potentialDuplicates": [
        { "candidateId": "hh-existing-456", "confidence": 0.92, "matchedOn": ["name", "email"] }
      ]
    }
  ]
}
```

---

### Search Filters & Options

The hybrid search endpoint supports additional filtering:

```http
POST /v1/search/hybrid
{
  "jobDescription": "Senior Python Engineer...",
  "limit": 20,
  "filters": {
    "minYearsExperience": 5,
    "maxYearsExperience": 15,
    "seniorityLevels": ["senior", "staff", "principal"],
    "locations": ["São Paulo", "Remote"],
    "skills": {
      "required": ["Python"],
      "preferred": ["AWS", "Kubernetes"]
    },
    "updatedAfter": "2024-01-01T00:00:00Z"
  },
  "options": {
    "includeInferred": true,
    "minConfidence": 0.7,
    "boostRecent": true
  }
}
```

| Filter | Type | Description |
|--------|------|-------------|
| `minYearsExperience` | number | Minimum years of experience |
| `maxYearsExperience` | number | Maximum years of experience |
| `seniorityLevels` | string[] | Filter by seniority classification |
| `locations` | string[] | Geographic filter (fuzzy matched) |
| `skills.required` | string[] | Must-have skills |
| `skills.preferred` | string[] | Nice-to-have skills (boost ranking) |
| `updatedAfter` | ISO date | Only candidates updated after this date |

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `includeInferred` | boolean | true | Include inferred skills in matching |
| `minConfidence` | number | 0.6 | Minimum confidence for inferred skills |
| `boostRecent` | boolean | false | Boost recently updated candidates |

---

### Testing & Sandbox

**Sandbox Environment** (available on request):
- Base URL: `https://sandbox.headhunter.example/`
- Pre-loaded with 1,000 synthetic candidates
- Full API parity with production
- Rate limits relaxed (10x production limits)
- Data resets weekly

**Test Credentials**:
```
x-api-key: sandbox-test-key-12345
X-Tenant-ID: sandbox-tenant
```

**Sample Test Candidates** (always available in sandbox):
- `sandbox-python-senior` - Senior Python engineer, 8 years
- `sandbox-fullstack-mid` - Mid-level fullstack, React/Node
- `sandbox-ml-principal` - Principal ML engineer, 12 years
- `sandbox-devops-lead` - DevOps lead, AWS/K8s specialist

---

### Common Integration Questions

**Q: How fresh are search results?**
A: Candidates are searchable within 30 seconds of enrichment completion. Embeddings are generated immediately after enrichment.

**Q: Can we use our own embeddings?**
A: Not currently. Headhunter uses VertexAI text-embedding-004 (768-dim) for consistency. We can discuss custom embedding support for enterprise plans.

**Q: What happens if enrichment fails for a candidate?**
A: The candidate is still stored but marked as `enrichmentStatus: "failed"`. They won't appear in semantic search results but can be retrieved by ID. Retry enrichment via `POST /v1/candidates/{id}/re-enrich`.

**Q: How do you handle candidate consent/GDPR?**
A: Each candidate record supports `consent` metadata:
```json
{
  "consent": {
    "dataProcessing": true,
    "aiAnalysis": true,
    "consentDate": "2024-01-15",
    "source": "application_form"
  }
}
```
We also support right-to-deletion requests via the DELETE endpoint.

**Q: Can we get raw LLM responses for debugging?**
A: Yes, add `includeDebug: true` to any request. Response will include `_debug` object with raw LLM inputs/outputs, timing breakdowns, and intermediate scores.

**Q: What's the maximum job description length?**
A: 10,000 characters. Longer descriptions are truncated with a warning. For best results, keep JDs under 5,000 characters.

**Q: Do you support Boolean search?**
A: Hybrid search handles natural language better than Boolean. However, you can use `filters.skills.required` for must-have skills. Full Boolean support is on the roadmap.

---

## SDK & Client Libraries

*Coming soon*: Official SDKs for Python, Node.js, and Go.

In the meantime, the REST API works with any HTTP client:

**Python Example**:
```python
import requests

API_KEY = "your-api-key"
TENANT_ID = "your-tenant-id"
BASE_URL = "https://api.headhunter.example"

def search_candidates(job_description, limit=20):
    response = requests.post(
        f"{BASE_URL}/v1/search/hybrid",
        headers={
            "x-api-key": API_KEY,
            "X-Tenant-ID": TENANT_ID,
            "Content-Type": "application/json"
        },
        json={
            "jobDescription": job_description,
            "limit": limit
        }
    )
    response.raise_for_status()
    return response.json()

# Usage
results = search_candidates("Senior Python Engineer with AWS experience")
for candidate in results["results"]:
    print(f"{candidate['name']} - Score: {candidate['score']}")
    print(f"  Why: {candidate['matchReasons'][0]}")
```

**Node.js Example**:
```javascript
const axios = require('axios');

const client = axios.create({
  baseURL: 'https://api.headhunter.example',
  headers: {
    'x-api-key': 'your-api-key',
    'X-Tenant-ID': 'your-tenant-id'
  }
});

async function searchCandidates(jobDescription, limit = 20) {
  const { data } = await client.post('/v1/search/hybrid', {
    jobDescription,
    limit
  });
  return data;
}

// Usage
const results = await searchCandidates('Senior Python Engineer with AWS');
results.results.forEach(c => {
  console.log(`${c.name} - Score: ${c.score}`);
});
```

---

## Integration Checklist

Use this checklist when planning your EllaAI ↔ Headhunter integration:

### Phase 1: Setup
- [ ] Receive API credentials (api-key, tenant-id)
- [ ] Test connectivity to sandbox environment
- [ ] Verify authentication works
- [ ] Review rate limits for your use case

### Phase 2: Data Sync
- [ ] Define ID mapping strategy (externalId)
- [ ] Implement candidate sync (bulk or real-time)
- [ ] Handle sync errors and retries
- [ ] Set up webhook endpoint for async notifications

### Phase 3: Search Integration
- [ ] Integrate `/v1/search/hybrid` into your search flow
- [ ] Map returned candidateIds to your ATS records
- [ ] Display match explanations in your UI
- [ ] Implement filters relevant to your users

### Phase 4: Production
- [ ] Switch to production API endpoint
- [ ] Configure production webhook URLs
- [ ] Set up monitoring for API errors
- [ ] Establish on-call procedures for integration issues

---

## Questions?

For integration support, technical documentation, or API access:
- Technical docs: [internal link]
- API reference: [internal link]
- Support: [contact]

---

*Document Version: 1.1*
*Last Updated: 2024-11-28*
*Prepared for: EllaAI Integration Discussion*
