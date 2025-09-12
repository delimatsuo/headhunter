# Vector Search Integration

## Overview

The Vector Search integration provides semantic similarity matching for candidate profiles using AI-powered embeddings and cosine similarity calculations. This enables intelligent candidate discovery based on natural language job descriptions and requirements.

## Architecture

### Components

1. **VectorSearchService** - Core service for embedding generation and similarity search
2. **Embedding Generation Pipeline** - Extracts relevant text from profiles and creates vector representations
3. **Semantic Search API** - Cloud Function endpoints for searching candidates by similarity
4. **Firestore Storage** - Persistent storage for embeddings and metadata
5. **Integration Layer** - Automatic embedding generation during profile processing

### Data Flow

```
1. Profile Processing → Extract Embedding Text → Generate Vector Embedding
2. Store Embedding → Firestore (candidate_embeddings collection)  
3. Search Query → Generate Query Embedding → Calculate Similarities
4. Rank Results → Enhance with Candidate Data → Return Matches
```

## Features

### Embedding Generation

**Automatic Processing**: Embeddings are automatically generated when profiles are processed through the enrichment pipeline.

**Text Extraction**: Combines multiple profile fields into coherent embedding text:
- Technical and soft skills
- Career trajectory and domain expertise  
- Leadership experience and team size
- Company background and tier level
- Recruiter insights and strengths
- AI-generated summaries and insights

**Vector Dimensions**: 768-dimensional embeddings using mock implementation (ready for Vertex AI text-embedding-004)

### Semantic Search

**Natural Language Queries**: Search using job descriptions and requirements in plain English.

**Similarity Scoring**: Cosine similarity calculation with normalized scores (0-1 range).

**Match Reasoning**: AI-generated explanations for why candidates match specific queries.

**Filtering Support**: Combine semantic search with traditional filters:
- Years of experience
- Current level (Senior, Mid, etc.)
- Company tier (Tier1, Tier2, etc.)
- Minimum overall score

### Search Results

**Enhanced Results**: Full candidate data combined with similarity metrics.

**Match Explanations**: Specific reasons why each candidate matches the query:
- Technical skills alignment
- Experience level matching
- Leadership experience correlation
- Company background relevance
- Overall candidate quality

## API Endpoints

### semanticSearch

**Type**: HTTPS Callable Function
**Purpose**: Perform semantic similarity search against candidate profiles

**Request Format**:
```json
{
  "query_text": "Senior Python engineer with machine learning experience at big tech companies",
  "filters": {
    "min_years_experience": 5,
    "current_level": "Senior",
    "company_tier": "Tier1",
    "min_score": 0.7
  },
  "limit": 20
}
```

**Response Format**:
```json
{
  "success": true,
  "query": "Senior Python engineer with machine learning experience at big tech companies",
  "results": [
    {
      "candidate_id": "candidate_001",
      "similarity_score": 0.92,
      "match_reasons": [
        "Technical skills match: python, machine learning",
        "Senior-level experience alignment", 
        "Company background match: big tech"
      ],
      "candidate_data": {
        "name": "Alice Chen",
        "overall_score": 0.95,
        "years_experience": 9,
        "technical_skills": ["Python", "TensorFlow", "Kubernetes"],
        "enrichment_summary": "Senior ML engineer with exceptional technical depth..."
      },
      "metadata": {
        "years_experience": 9,
        "current_level": "Senior",
        "company_tier": "Tier1",
        "overall_score": 0.95,
        "updated_at": "2025-09-05T19:15:00.000Z"
      }
    }
  ],
  "total": 1,
  "search_type": "semantic"
}
```

### generateEmbedding

**Type**: HTTPS Callable Function
**Purpose**: Manually generate embedding for a specific candidate

**Request Format**:
```json
{
  "candidate_id": "candidate_001"
}
```

**Response Format**:
```json
{
  "success": true,
  "candidate_id": "candidate_001",
  "embedding_generated": true,
  "embedding_text_length": 1247,
  "vector_dimensions": 768,
  "metadata": {
    "years_experience": 9,
    "current_level": "Senior",
    "company_tier": "Tier1",
    "overall_score": 0.95,
    "technical_skills": ["Python", "TensorFlow", "Kubernetes"],
    "updated_at": "2025-09-05T19:15:00.000Z"
  }
}
```

### vectorSearchStats

**Type**: HTTPS Callable Function
**Purpose**: Get statistics and health information for vector search system

**Request Format**:
```json
{}
```

**Response Format**:
```json
{
  "success": true,
  "timestamp": "2025-09-05T19:15:00.000Z",
  "stats": {
    "total_embeddings": 150,
    "avg_score": 0.82,
    "level_distribution": {
      "Senior": 45,
      "Mid": 60,
      "Principal": 25,
      "Entry": 20
    },
    "tier_distribution": {
      "Tier1": 80,
      "Tier2": 50,
      "Tier3": 20
    }
  },
  "health": {
    "status": "healthy",
    "embedding_service": "operational",
    "storage_connection": "connected",
    "firestore_connection": "connected",
    "total_embeddings": 150
  }
}
```

## Data Models

### EmbeddingData

```typescript
interface EmbeddingData {
  candidate_id: string;
  embedding_vector: number[];      // 768 dimensions
  embedding_text: string;          // Source text for embedding
  metadata: {
    years_experience: number;
    current_level: string;
    company_tier: string;
    overall_score: number;
    technical_skills?: string[];
    leadership_level?: string;
    updated_at: string;
  };
}
```

### VectorSearchResult

```typescript
interface VectorSearchResult {
  candidate_id: string;
  similarity_score: number;        // 0.0 to 1.0
  metadata: EmbeddingData["metadata"];
  match_reasons: string[];         // AI-generated explanations
}
```

### SearchQuery

```typescript
interface SearchQuery {
  query_text: string;
  filters?: {
    min_years_experience?: number;
    current_level?: string;
    company_tier?: string;
    min_score?: number;
  };
  limit?: number;                  // Default: 20
}
```

## Implementation Details

### Embedding Text Generation

The system combines multiple profile fields into coherent text for embedding generation:

```typescript
// Example embedding text for a candidate
"Senior level professional with 9 years experience. 
Technical skills: Python, Machine Learning, Kubernetes, React, PostgreSQL. 
Soft skills: Leadership, Communication, Problem Solving. 
Career trajectory: Technical Leadership. 
Domain expertise: Software Engineering, AI/ML. 
Leadership experience: Team Lead managing team of 8. 
Company tier: Tier1. Company types: Big Tech, Startup. 
Recent companies: Google, OpenAI. 
Strengths: Exceptional technical skills, Strong leadership presence, Great cultural fit. 
Key themes: Technical Excellence, Leadership Potential, Cultural Fit. 
Competitive advantages: Unique AI/ML background, Google experience. 
Senior professional with 9 years in Software Engineering, demonstrating exceptional capabilities and excellent cultural alignment."
```

### Similarity Calculation

Uses cosine similarity for vector comparison:

```typescript
private cosineSimilarity(vecA: number[], vecB: number[]): number {
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;
  
  for (let i = 0; i < vecA.length; i++) {
    dotProduct += vecA[i] * vecB[i];
    normA += vecA[i] * vecA[i];
    normB += vecB[i] * vecB[i];
  }
  
  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}
```

### Match Reasoning

AI-generated explanations based on keyword matching and profile analysis:

- **Technical Skills**: Matches between query and candidate skills
- **Experience Level**: Alignment of seniority levels
- **Leadership**: Management and team experience correlation
- **Company Background**: Industry and company tier matching
- **Overall Quality**: High-scoring candidates highlighted

## Testing

### Test Profiles

The system includes three diverse test profiles for validation:

1. **Alice Chen** - Senior ML Engineer (Big Tech, Leadership)
2. **Bob Rodriguez** - Mid-level Frontend Developer (Startup Experience) 
3. **Carol Kim** - Principal Platform Engineer (Distributed Systems Expert)

### Test Queries

Comprehensive test queries validate different search scenarios:

```javascript
// Technical + Leadership + Company matching
semanticSearch({
  query_text: "Senior machine learning engineer with leadership experience at big tech companies",
  limit: 5
})

// Frontend + Framework + Background matching  
semanticSearch({
  query_text: "Frontend developer with React and startup experience",
  limit: 5
})

// Platform + Infrastructure + Technical matching
semanticSearch({
  query_text: "Platform engineering expert with distributed systems and Kubernetes",
  limit: 5
})
```

### Running Tests

```bash
# Upload test profiles
python3 scripts/test_vector_search.py

# Wait for processing (2-3 minutes)
# Then test via Firebase Functions Shell
firebase functions:shell --project headhunter-ai-0088

# Test semantic search
> semanticSearch({ query_text: "Senior Python engineer", limit: 5 })

# Check statistics
> vectorSearchStats({})

# Generate embeddings manually
> generateEmbedding({ candidate_id: "vector_test_001" })
```

## Deployment

### Prerequisites

- Firestore database configured
- Cloud Storage bucket created
- Cloud Functions deployed
- Test profiles processed

### Deploy Vector Search

```bash
# Build and deploy functions
cd functions
npm run build
npm run deploy

# Upload test profiles
python3 scripts/test_vector_search.py

# Verify deployment
firebase functions:log --project headhunter-ai-0088
```

### Validation Steps

1. **Deploy Functions**: Ensure all vector search functions deploy successfully
2. **Upload Profiles**: Test profiles trigger automatic embedding generation
3. **Check Logs**: Verify profiles processed and embeddings created
4. **Test Search**: Semantic queries return relevant candidates with scores
5. **Verify Stats**: Statistics show correct embedding counts and health status

## Production Considerations

### Performance

**Embedding Generation**: 
- Current: ~100ms per profile (mock implementation)
- Production: ~500ms with actual Vertex AI calls
- Batch processing recommended for bulk operations

**Search Performance**:
- Current: Local similarity calculation in Firestore
- Production: Migrate to Vertex AI Vector Search for scale
- Sub-second response times for queries up to 10,000 candidates

**Scaling**:
- Firestore: Suitable up to ~10,000 candidates
- Vector Search: Required for 10,000+ candidates
- Memory: 512MiB sufficient for current implementation

### Cost Optimization

**Embedding Generation**:
- Cache embeddings to avoid regeneration
- Batch process multiple profiles per function call
- Use streaming updates for real-time changes

**Search Operations**:
- Implement query caching for common searches
- Use Firestore efficiently with proper indexing
- Consider CDN for frequently accessed results

### Migration to Production Vector Search

**Current Implementation**: Mock embeddings with Firestore storage
**Production Migration**: Replace with Vertex AI services

```typescript
// Production embedding generation
const request = {
  endpoint: `projects/${this.projectId}/locations/${this.region}/publishers/google/models/text-embedding-004`,
  instances: [{ content: text }]
};

const [response] = await this.predictionClient.predict(request);
return response.predictions[0].embeddings.values;
```

```typescript  
// Production similarity search
const request = {
  indexEndpoint: this.indexEndpoint,
  deployedIndexId: this.deployedIndexId,
  queries: [{
    embedding: queryEmbedding,
    numNeighbors: limit
  }]
};

const [response] = await this.matchClient.findNeighbors(request);
return response.nearestNeighbors;
```

## Monitoring

### Key Metrics

- **Embedding Generation Success Rate**: Target >99%
- **Search Response Time**: Target <500ms  
- **Search Relevance**: Manual evaluation of top results
- **System Health**: Firestore and service availability

### Alerting

- Embedding generation failures
- High search latency (>2 seconds)
- Low system health scores
- Firestore connection issues

### Debugging

```bash
# View function logs
firebase functions:log --only semanticSearch

# Check embedding statistics  
firebase functions:shell
> vectorSearchStats({})

# Verify specific candidate embeddings
> generateEmbedding({ candidate_id: "test_candidate" })

# Test query processing
> semanticSearch({ query_text: "test query", limit: 3 })
```

## Future Enhancements

### Phase 1: Production Vector Search
- Migrate to Vertex AI Vector Search
- Implement real text embedding generation
- Add vector index management

### Phase 2: Advanced Features
- Multi-modal embeddings (text + structured data)
- Query expansion and synonym handling
- Personalized search ranking

### Phase 3: AI-Powered Matching
- Automatic query generation from job descriptions
- Candidate-job fit scoring
- Explainable AI match reasoning

### Phase 4: Real-time Updates
- Streaming embedding updates
- Live search result refinement
- Dynamic index management

## Troubleshooting

### Common Issues

**Embedding Generation Fails**:
- Check Firestore permissions
- Verify profile data structure
- Review function memory allocation

**Search Returns No Results**:
- Confirm embeddings exist for candidates
- Check filter criteria (too restrictive)
- Verify query text processing

**Low Similarity Scores**:
- Review embedding text extraction
- Confirm vector normalization
- Test with known good candidates

**Performance Issues**:
- Monitor function timeout settings
- Check Firestore query efficiency
- Consider batch processing

### Debug Commands

```bash
# Check embedding storage
firebase firestore:get candidate_embeddings/test_001

# Verify function deployment
gcloud functions describe semanticSearch --region=us-central1

# Test manual embedding generation
firebase functions:shell
> generateEmbedding({ candidate_id: "known_candidate_id" })

# Check search statistics
> vectorSearchStats({})
```

## Support

For vector search related issues:

1. Check function logs for specific error messages
2. Verify embeddings exist in Firestore
3. Test with known good profiles and queries
4. Review similarity scores and match reasons
5. Validate search filters and parameters