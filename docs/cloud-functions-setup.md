# Cloud Functions for Data Enrichment

## Overview

The Cloud Functions system provides AI-powered enrichment of candidate profiles using Google Cloud's Vertex AI. The functions are built with TypeScript and Firebase Functions v2, offering robust, scalable processing of candidate data.

## Architecture

### Components

1. **Storage Trigger Function** (`processUploadedProfile`)
   - Automatically triggered when JSON files are uploaded to Cloud Storage
   - Processes candidate profiles and enriches them with AI insights
   - Stores enriched data in Firestore for fast querying

2. **Manual Enrichment Function** (`enrichProfile`)
   - HTTPS callable function for testing and manual profile enrichment
   - Accepts candidate profile data and returns enriched insights
   - Useful for debugging and one-off processing

3. **Search Function** (`searchCandidates`)
   - Basic candidate search functionality
   - Supports filtering by experience, level, and company tier
   - Returns ranked results based on overall score

4. **Health Check Function** (`healthCheck`)
   - System health monitoring
   - Tests connectivity to Firestore and Cloud Storage
   - Verifies system readiness

### Data Flow

```
1. Profile Upload → Cloud Storage (gs://headhunter-ai-0088-profiles/profiles/)
2. Storage Trigger → processUploadedProfile Function
3. AI Enrichment → Disabled in Functions (handled by Together AI Python processors)
4. Data Storage → Firestore Collections:
   - enriched_profiles/ (full enriched data)
   - candidates/ (searchable flattened data)
```

## Setup and Deployment

### Prerequisites

- Firebase CLI: `npm install -g firebase-tools`
- Google Cloud CLI: `gcloud` installed and authenticated
- Node.js 20+
- Project permissions for Firebase Functions, Firestore, and Cloud Storage

### Installation

```bash
# Navigate to functions directory
cd functions

# Install dependencies
npm install

# Build TypeScript
npm run build

# Run tests
npm test
```

### Deployment

```bash
# Automated deployment (recommended)
./scripts/deploy_functions.sh

# Manual deployment
cd functions
npm run deploy
```

### Configuration

The functions use these environment variables:

- `GOOGLE_CLOUD_PROJECT`: Automatically set by Firebase
- Storage bucket: `${PROJECT_ID}-profiles` (auto-created)

## Function Details

### processUploadedProfile

**Trigger**: Cloud Storage object finalize
**Bucket**: `headhunter-ai-0088-profiles`
**Path Pattern**: `profiles/*.json`

**Process Flow**:
1. Download uploaded JSON file from Cloud Storage
2. Validate against CandidateProfile schema using Zod
3. Check if profile already enriched (skip if exists)
4. Call AI enrichment service (currently mock implementation)
5. Store enriched profile in Firestore
6. Create searchable index entry

**Example Usage**:
```bash
# Upload a profile to trigger processing
gsutil cp profile.json gs://headhunter-ai-0088-profiles/profiles/candidate_001.json
```

### enrichProfile

**Type**: HTTPS Callable
**Authentication**: None (add authentication for production)

**Request Format**:
```json
{
  "profile": {
    "candidate_id": "test_001",
    "name": "John Doe",
    "resume_analysis": { /* ResumeAnalysis object */ },
    "recruiter_insights": { /* RecruiterInsights object */ }
  }
}
```

**Response Format**:
```json
{
  "success": true,
  "enriched_profile": {
    /* Original profile data */
    "enrichment": {
      "career_analysis": {
        "trajectory_insights": "...",
        "growth_potential": "...",
        "leadership_readiness": "...",
        "market_positioning": "..."
      },
      "strategic_fit": {
        "role_alignment_score": 85,
        "cultural_match_indicators": [...],
        "development_recommendations": [...],
        "competitive_positioning": "..."
      },
      "ai_summary": "...",
      "enrichment_timestamp": "2025-09-05T18:53:07.000Z",
      "enrichment_version": "1.0"
    }
  }
}
```

### searchCandidates

**Type**: HTTPS Callable
**Authentication**: None (add authentication for production)

**Request Format**:
```json
{
  "query": {
    "min_years_experience": 5,
    "current_level": "Senior",
    "company_tier": "Tier1"
  },
  "limit": 20
}
```

**Response Format**:
```json
{
  "success": true,
  "candidates": [
    {
      "id": "candidate_001",
      "name": "John Doe",
      "overall_score": 0.85,
      "years_experience": 8,
      "current_level": "Senior",
      "enrichment_summary": "...",
      /* ... other candidate fields */
    }
  ],
  "total": 15
}
```

### healthCheck

**Type**: HTTPS Callable
**Authentication**: None

**Response Format**:
```json
{
  "status": "healthy",
  "timestamp": "2025-09-05T18:53:07.000Z",
  "services": {
    "firestore": "connected",
    "storage": "bucket_exists",
    "vertex_ai": "configured"
  },
  "project": "headhunter-ai-0088",
  "region": "us-central1"
}
```

## Data Models

### Input: CandidateProfile

```typescript
interface CandidateProfile {
  candidate_id: string;
  name?: string;
  resume_analysis?: {
    career_trajectory: {
      current_level: string;
      progression_speed: string;
      trajectory_type: string;
      career_changes?: number;
      domain_expertise?: string[];
    };
    leadership_scope: {
      has_leadership: boolean;
      team_size?: number;
      leadership_level?: string;
      leadership_style?: string[];
      mentorship_experience?: boolean;
    };
    company_pedigree: {
      tier_level: string;
      company_types?: string[];
      brand_recognition?: string;
      recent_companies?: string[];
    };
    years_experience: number;
    technical_skills: string[];
    soft_skills?: string[];
    education?: {
      highest_degree?: string;
      institutions?: string[];
      fields_of_study?: string[];
    };
    cultural_signals?: string[];
  };
  recruiter_insights?: {
    sentiment: string;
    strengths: string[];
    concerns?: string[];
    red_flags?: string[];
    leadership_indicators?: string[];
    cultural_fit?: {
      cultural_alignment: string;
      work_style?: string[];
      values_alignment?: string[];
      team_fit?: string;
      communication_style?: string;
      adaptability?: string;
      cultural_add?: string[];
    };
    recommendation: string;
    readiness_level: string;
    key_themes?: string[];
    development_areas?: string[];
    competitive_advantages?: string[];
  };
  overall_score?: number;
  recommendation?: string;
  processing_timestamp?: string;
}
```

### Output: EnrichedProfile

Extends CandidateProfile with additional `enrichment` field containing AI-generated insights.

## Testing

### Unit Tests

```bash
cd functions
npm test
```

### Integration Tests

```bash
python3 scripts/test_cloud_functions.py
```

**Test Coverage**:
- ✅ Health check functionality
- ✅ Manual enrichment with test profile
- ✅ Storage trigger with file upload
- ✅ Firestore connectivity
- ✅ Cloud Storage bucket access

### Manual Testing

```bash
# Start local emulator
cd functions
npm run serve

# Test in Firebase shell
firebase functions:shell --project headhunter-ai-0088

# Test health check
> healthCheck({})

# Test profile enrichment
> enrichProfile({ profile: { /* test profile data */ } })
```

## Monitoring and Debugging

### View Logs

```bash
# Real-time logs
firebase functions:log --project headhunter-ai-0088

# Specific function logs
firebase functions:log --project headhunter-ai-0088 --only processUploadedProfile
```

### Cloud Console

- **Functions**: https://console.cloud.google.com/functions/list?project=headhunter-ai-0088
- **Storage**: https://console.cloud.google.com/storage/browser/headhunter-ai-0088-profiles
- **Firestore**: https://console.cloud.google.com/firestore/databases/-default-/data/panel/enriched_profiles

### Performance Monitoring

Functions are configured with:
- **Memory**: 512MiB for processing, 256MiB for simple operations
- **Timeout**: 540 seconds (9 minutes) for AI processing
- **Retry**: Enabled for storage triggers
- **Concurrency**: Max 10 instances

## Production Considerations

### Security

1. **Add Authentication**: Enable Firebase Auth or custom authentication
2. **API Keys**: Store Vertex AI credentials in Secret Manager
3. **CORS**: Configure appropriate CORS policies for web access
4. **Rate Limiting**: Implement rate limiting for public endpoints

### Performance

1. **Caching**: Add caching for frequently accessed profiles
2. **Batch Processing**: Process multiple profiles in single function call
3. **Vector Embeddings**: Integrate with Vertex AI Vector Search for semantic similarity
4. **CDN**: Use Cloud CDN for static assets

### Monitoring

1. **Alerts**: Set up Cloud Monitoring alerts for failures
2. **Metrics**: Track processing times and success rates
3. **Error Reporting**: Enable Cloud Error Reporting
4. **Logging**: Structured logging with appropriate levels

### Cost Optimization

1. **Function Sizing**: Right-size memory allocation based on usage
2. **Cold Start**: Minimize cold starts with min instances
3. **Storage Classes**: Use appropriate storage classes for different data types
4. **Batch Operations**: Reduce function invocations through batching

## Future Enhancements

1. **Real Vertex AI Integration**: Replace mock implementation with actual Vertex AI calls
2. **Vector Search**: Integrate semantic similarity search
3. **Streaming Processing**: Support real-time profile updates
4. **Advanced Analytics**: Add career progression analytics
5. **Multi-tenancy**: Support multiple organizations
6. **API Gateway**: Add comprehensive API management
7. **Workflow Orchestration**: Use Cloud Workflows for complex processing pipelines

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure proper IAM roles for service accounts
2. **Timeout Errors**: Increase function timeout for large profiles
3. **Memory Errors**: Increase memory allocation for processing functions
4. **Storage Access**: Verify bucket exists and has proper permissions
5. **Firestore Errors**: Check Firestore rules and document structure

### Debug Commands

```bash
# Check function status
gcloud functions describe processUploadedProfile --region=us-central1

# View function logs
gcloud logging read "resource.type=cloud_function" --limit=50

# Test storage trigger manually
gsutil cp test_profile.json gs://headhunter-ai-0088-profiles/profiles/debug_test.json

# Verify Firestore data
firebase firestore:get enriched_profiles/test_001 --project headhunter-ai-0088
```

## Support

For issues with the Cloud Functions system:

1. Check function logs in Cloud Console
2. Verify all dependencies are properly deployed
3. Test individual components using manual functions
4. Review IAM permissions and service account access
5. Validate input data against schema requirements
