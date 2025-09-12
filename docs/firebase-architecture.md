# 🚀 Headhunter Firebase Architecture & Tech Stack

## Core Tech Stack

### Frontend
- **React/Next.js** - Modern UI with server-side rendering
- **TypeScript** - Type safety across the stack
- **Tailwind CSS** - Rapid UI development
- **React Query** - Data fetching and caching
- **Zustand** - State management

### Backend (Firebase)
- **Firestore** - Main database for candidate profiles
- **Cloud Functions** - Processing pipeline
- **Cloud Storage** - Resume/LinkedIn PDF storage
- **Firebase Auth** - User authentication
- **Vertex AI** - Embeddings and enrichment
- **Cloud Tasks** - Background processing queue

### Processing Pipeline
- **Ollama** - Local LLM processing (Llama 3.1:8b)
- **Python** - Data processing scripts
- **Node.js** - Cloud Functions runtime

## Database Schema

### Collections Structure

```typescript
// candidates collection
interface Candidate {
  id: string;
  name: string;
  email: string;
  phone?: string;
  linkedinUrl?: string;
  currentVersion: number;
  createdAt: Timestamp;
  updatedAt: Timestamp;
  tags: string[];
  status: 'active' | 'archived' | 'pending';
}

// candidate_versions subcollection
interface CandidateVersion {
  versionNumber: number;
  candidateId: string;
  sourceType: 'linkedin' | 'resume' | 'manual' | 'enriched';
  sourceUrl?: string;
  uploadedBy: string;
  uploadedAt: Timestamp;
  
  // Raw data
  rawContent: string;
  parsedData: {
    experience: Experience[];
    education: Education[];
    skills: string[];
    headline: string;
    summary: string;
  };
  
  // LLM Analysis (Llama 3.1)
  analysis: {
    careerTrajectory: {
      currentLevel: string;
      yearsExperience: number;
      progressionSpeed: string;
      notableMove: string[];
    };
    technicalAssessment: {
      keyStrengths: string[];
      architectureExperience: boolean;
      cloudPlatforms: string[];
      leadershipExperience: string;
    };
    marketPositioning: {
      salaryRange: string;
      marketDemand: string;
      competitiveAdvantages: string[];
    };
    companyFit: {
      bestFit: string[];
      industryTargets: string[];
      roleRecommendations: string[];
    };
    placementRecommendation: {
      rating: string;
      recommendation: string;
      keySellingPoints: string[];
    };
  };
  
  // Enrichment (Produced by Together AI processors; not via Functions)
  enrichment?: {
    aiSummary: string;
    careerInsights: string;
    strategicFit: object;
    enrichmentVersion: string;
    enrichedAt: Timestamp;
  };
  
  // Embedding
  embedding?: {
    vector: number[]; // 768 dimensions
    textContent: string; // Text used for embedding
    generatedAt: Timestamp;
  };
}

// searches collection (saved searches)
interface SavedSearch {
  id: string;
  userId: string;
  name: string;
  query: string;
  filters: SearchFilters;
  createdAt: Timestamp;
  lastRun: Timestamp;
  resultCount: number;
}

// jobs collection
interface Job {
  id: string;
  title: string;
  company: string;
  description: string;
  requirements: string[];
  salaryRange?: string;
  location: string;
  createdBy: string;
  createdAt: Timestamp;
  status: 'open' | 'filled' | 'cancelled';
  matchedCandidates?: string[]; // candidate IDs
}
```

## User Workflows

### 1. Initial Candidate Upload
```
User uploads LinkedIn PDF/Resume
    ↓
Cloud Function triggers
    ↓
Parse document (Python)
    ↓
LLM Analysis (Llama 3.1 structured prompt)
    ↓
Generate embedding (Vertex AI)
    ↓
Store in Firestore with version 1
    ↓
Index for search
```

### 2. Candidate Update Flow (2025 → 2027)
```
User views Felipe's profile (v1 from 2025)
    ↓
"Update Profile" button
    ↓
Upload new LinkedIn PDF (2027)
    ↓
System creates version 2
    ↓
Rerun complete pipeline
    ↓
Compare v1 vs v2 (show changes)
    ↓
Update embeddings
    ↓
Maintain version history
```

### 3. Search & Match Flow
```
Recruiter enters job requirements
    ↓
Convert to embedding
    ↓
Vector similarity search
    ↓
Filter by metadata (location, salary, etc.)
    ↓
Rank results
    ↓
Show candidate cards with version info
```

## React Component Structure

```typescript
// Main App Structure
src/
  components/
    candidates/
      CandidateList.tsx
      CandidateCard.tsx
      CandidateDetail.tsx
      CandidateVersionHistory.tsx
      UpdateCandidateModal.tsx
    
    search/
      SearchBar.tsx
      FilterPanel.tsx
      SearchResults.tsx
      SavedSearches.tsx
    
    jobs/
      JobList.tsx
      JobDetail.tsx
      JobCandidateMatches.tsx
    
    common/
      Layout.tsx
      Navigation.tsx
      LoadingSpinner.tsx
  
  hooks/
    useCandidate.ts
    useSearch.ts
    useVersionComparison.ts
    
  services/
    firebase.ts
    candidateService.ts
    searchService.ts
    embeddingService.ts
```

## Cloud Functions

```typescript
// processNewCandidate
export const processNewCandidate = functions.storage
  .object()
  .onFinalize(async (object) => {
    const filePath = object.name;
    const candidateId = extractCandidateId(filePath);
    
    // 1. Download and parse file
    const rawContent = await parseDocument(object);
    
    // 2. LLM Analysis
    const analysis = await runLlamaAnalysis(rawContent);
    
    // 3. Generate embedding
    const embedding = await generateEmbedding(analysis);
    
    // 4. Store with versioning
    await storeWithVersion(candidateId, {
      rawContent,
      analysis,
      embedding
    });
  });

// updateCandidateProfile
export const updateCandidateProfile = functions.https
  .onCall(async (data, context) => {
    const { candidateId, newFileUrl } = data;
    
    // Get current version
    const currentVersion = await getCurrentVersion(candidateId);
    
    // Process new data
    const newAnalysis = await processNewUpload(newFileUrl);
    
    // Create new version
    const newVersion = currentVersion + 1;
    await createNewVersion(candidateId, newVersion, newAnalysis);
    
    // Return comparison
    return compareVersions(currentVersion, newVersion);
  });

// semanticSearch
export const semanticSearch = functions.https
  .onCall(async (data, context) => {
    const { query, filters } = data;
    
    // Generate query embedding
    const queryEmbedding = await generateEmbedding(query);
    
    // Vector search
    const results = await vectorSearch(queryEmbedding, filters);
    
    // Return ranked results
    return rankResults(results);
  });
```

## UI/UX Design Principles

### Candidate Profile View
```
┌─────────────────────────────────────┐
│ Felipe Augusto V Marques de Araujo │
│ Senior Cloud Engineer               │
│                                     │
│ [Version: v3 (Updated: Jan 2027)]  │
│ [View History] [Update Profile]     │
│                                     │
│ ┌─────────────┐ ┌─────────────┐    │
│ │ Summary     │ │ Analysis    │    │
│ │             │ │             │    │
│ │ • 9 years   │ │ Level: Sr   │    │
│ │ • AWS/Cloud │ │ Salary:$150k│    │
│ │ • Itaú Bank │ │ Fit: A+     │    │
│ └─────────────┘ └─────────────┘    │
│                                     │
│ Version History:                    │
│ • v3: Jan 2027 (current)           │
│ • v2: Jul 2026                     │
│ • v1: Sep 2025 (original)          │
│                                     │
│ [Compare Versions] [Export]         │
└─────────────────────────────────────┘
```

### Search Interface
```
┌─────────────────────────────────────┐
│ 🔍 Find: "Senior cloud engineer     │
│    with banking experience"         │
│                                     │
│ Filters:                            │
│ □ Location: São Paulo              │
│ □ Salary: $100k-150k               │
│ □ Years: 5+                        │
│ □ Updated: Last 6 months           │
│                                     │
│ Results (47 matches):               │
│ ┌─────────────────────────────┐    │
│ │ 98% Felipe Augusto          │    │
│ │ Sr Cloud Engineer • v3       │    │
│ │ Itaú → PagSeguro • 9 yrs    │    │
│ │ [View] [Compare] [Contact]   │    │
│ └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

## Version Comparison View
```
┌─────────────────────────────────────┐
│ Version Comparison: Felipe          │
│                                     │
│ v1 (2025)    →    v3 (2027)       │
│                                     │
│ Experience:                         │
│ 7 years      →    9 years ↑        │
│                                     │
│ Role:                               │
│ Cloud Eng    →    Tech Lead ↑      │
│                                     │
│ Skills Added:                       │
│ + Kubernetes                        │
│ + Team Management (12 people)       │
│ + System Design                     │
│                                     │
│ Salary Est:                         │
│ $120-140k    →    $150-180k ↑      │
│                                     │
│ [Accept Update] [Keep Both]         │
└─────────────────────────────────────┘
```

## Key Features

### 1. Temporal Intelligence
- Track candidate progression over time
- Show career velocity and growth
- Predict future trajectory

### 2. Smart Versioning
- Never lose historical data
- Compare what changed between updates
- Track who updated and when

### 3. Living Embeddings
- Embeddings update with new versions
- Historical search (find who WAS junior in 2025)
- Trend analysis (fastest growing candidates)

### 4. Automated Enrichment Pipeline
- Upload triggers full reprocessing
- Structured LLM analysis with Llama 3.1
- Vertex AI enrichment for deeper insights
- Automatic embedding generation

## Security & Permissions

```typescript
// Firestore Rules
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Read access for authenticated users
    match /candidates/{candidateId} {
      allow read: if request.auth != null;
      allow write: if request.auth != null 
        && request.auth.token.role in ['admin', 'recruiter'];
      
      // Version history
      match /versions/{versionId} {
        allow read: if request.auth != null;
        allow write: if request.auth != null 
          && request.auth.token.role in ['admin', 'recruiter'];
      }
    }
    
    // Search history
    match /searches/{searchId} {
      allow read, write: if request.auth != null 
        && request.auth.uid == resource.data.userId;
    }
  }
}
```

## Deployment & CI/CD

```yaml
# .github/workflows/deploy.yml
name: Deploy to Firebase
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Install Dependencies
        run: |
          npm install
          cd functions && npm install
      
      - name: Build
        run: npm run build
      
      - name: Deploy to Firebase
        uses: w9jds/firebase-action@master
        with:
          args: deploy
        env:
          FIREBASE_TOKEN: ${{ secrets.FIREBASE_TOKEN }}
```

## Cost Optimization

1. **Cache embeddings** - Don't regenerate unless content changes
2. **Batch processing** - Process multiple candidates together
3. **Incremental updates** - Only reprocess changed sections
4. **Smart indexing** - Index only searchable fields
5. **Version pruning** - Archive old versions after X months

## Success Metrics

- **Search accuracy**: % of relevant candidates in top 10
- **Update frequency**: Average updates per candidate per year
- **Processing time**: Time from upload to searchable
- **Version comparison usage**: % of users comparing versions
- **Match quality**: Placement success rate from matches

This architecture provides a complete, scalable, and maintainable system for your evolving recruitment intelligence platform!
