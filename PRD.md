# [DEPRECATED] Headhunter PRD (use .taskmaster/docs/prd.txt)

This file contains legacy content. The single source of truth is now `.taskmaster/docs/prd.txt` (Brazil-first, Gemini embeddings, Together rerank). Update and planning should reference that file.

# Headhunter v2.0 - AI-Powered Recruitment Analytics Platform

Note: This document contains legacy content from earlier iterations. The authoritative PRD is maintained at `.taskmaster/docs/prd.txt` and reflects the current single-pass Qwen 2.5 32B architecture, unified search pipeline, and the “no mock fallbacks” policy.

## Overview  
Headhunter v2.0 transforms Ella Executive Search's candidate database into an intelligent, semantic search engine powered by **cloud-based AI processing and vector embeddings**. It solves the inefficiency of keyword-based ATS queries by deeply analyzing 20,000+ candidates using Together AI's Llama 3.2 3B model, creating comprehensive profiles with 15+ detailed fields, and enabling semantic similarity search for recruiter workflows.

**Core Value Proposition**: Recruiters can upload job descriptions and instantly find the most relevant candidates from a database of enhanced profiles with semantic understanding, reducing time-to-longlist from hours to minutes while uncovering hidden matches that keyword search would miss.

## Business Requirements

### Primary Users & Workflows

**Persona: Alex (Senior Recruiter)**
- **Current Pain Points**: 
  - Hours spent on manual keyword searches
  - Missing ideal candidates due to limited search terms
  - Inconsistent profile data quality
  - No semantic understanding of candidate-role fit

- **Target Workflows**:
  1. **Semantic Job Search**: Upload job description → Get ranked candidate matches with similarity scores
  2. **Profile Management**: Update LinkedIn profiles → Re-process and refresh search results
  3. **Batch Processing**: Upload CSV files → Process thousands of candidates with AI analysis
  4. **Advanced Search**: Combine semantic search with structured filters (location, experience, skills)

### Success Metrics
- **Time-to-Longlist**: < 5 minutes (vs current 2+ hours)
- **Search Quality**: 90%+ relevant matches in top 20 results
- **Database Coverage**: Process all 29,000 historical candidates
- **User Adoption**: > 20 searches per recruiter per week
- **Satisfaction**: > 4.5/5 user rating

## Technical Architecture

### Multi-Stage AI Processing Pipeline

**Core Components:**
- **Stage 1 AI**: Together AI Llama 3.2 3B ($0.20/1M tokens) - Basic Enhancement
- **Stage 2 AI**: Together AI Qwen2.5 Coder 32B ($0.80/1M tokens) - Contextual Intelligence
- **Stage 3 AI**: VertexAI text-embedding-004 - Vector Embeddings
- **Orchestration**: Multi-stage pipeline with Cloud Run workers
- **Vector Database**: Cloud SQL + pgvector for semantic search
- **Structured Storage**: Firestore for rich candidate profiles
- **API Layer**: FastAPI + Cloud Run for search and CRUD operations

### 3-Stage Data Processing Pipeline

```
Stage 1: Basic Enhancement
Resume Text + Comments → Llama 3.2 3B → Enhanced Profile Structure (15+ fields)

Stage 2: Contextual Intelligence 
Enhanced Profile → Qwen2.5 Coder 32B → Trajectory-Based Skill Inference
- Company context analysis (Google vs startup patterns)
- Industry intelligence (FinTech vs consulting expertise)
- Role progression mapping (VP vs team lead skills)
- Educational context weighting (MIT vs state school signals)

Stage 3: Vector Generation
Enriched Profile → VertexAI Embeddings → 768-dim vectors for semantic search

Storage & Retrieval:
Profiles → Firestore (structured data) + Cloud SQL pgvector (semantic search)
Job Description → Vector similarity → Ranked candidate matches
```

## Comprehensive Candidate Profile Schema

### 15+ Detailed Profile Fields

**Personal Information**
- Full contact details and current role
- LinkedIn profile and location data

**Career Trajectory Analysis** 
- Current level (junior → executive)
- Progression speed and career velocity
- Role transitions and promotion patterns
- Years of experience breakdown

**Leadership Assessment**
- Management experience and team size
- Leadership style and cross-functional collaboration
- Mentorship experience and direct reports

**Company Pedigree**
- Company tier (startup → FAANG)
- Career trajectory across companies
- Industry focus and stability patterns

**Technical Skills Matrix**
- Primary languages and frameworks with confidence scores (0-100%)
- Cloud platforms and databases with evidence arrays
- Specializations and skill depth with fuzzy matching
- Learning velocity assessment and skill categorization

**Domain Expertise**
- Industry experience and business functions
- Vertical knowledge and regulatory experience
- Domain transferability scores

**Soft Skills Evaluation**
- Communication and collaboration strength
- Problem-solving and adaptability
- Leadership and emotional intelligence

**Cultural Signals**
- Work style and team dynamics
- Values alignment and cultural strengths
- Change adaptability and feedback receptiveness

**Compensation Intelligence**
- Salary range and total compensation
- Equity preferences and negotiation flexibility
- Compensation motivators

**Recruiter Insights**
- Engagement history and placement likelihood
- Best-fit roles and company types
- Interview strengths and potential concerns

**Search Optimization**
- Primary and secondary keywords with probability weights
- Skill tags with confidence levels and synonym matching
- Industry tags and seniority indicators
- Skill-aware search ranking with composite scoring

**Matching Intelligence**
- Ideal role types and company preferences with skill gap analysis
- Technology stack compatibility scores with confidence weighting
- Leadership readiness and cultural fit scores
- Skill probability assessment with evidence-based validation

**Executive Summary**
- One-line pitch and key differentiators
- Career narrative and ideal next role
- Overall rating and recommendation tier

## Semantic Search Architecture

### Vector Database Design

**Storage Strategy**: Hybrid dual-database approach
- **Cloud SQL + pgvector**: 768-dimensional vectors for fast similarity search
- **Firestore**: Rich structured profiles with 15+ detailed fields
- **Synchronization**: Every candidate exists in both systems with consistent IDs

**Search Performance**: 
- <100ms vector similarity search for 20,000+ candidates
- <200ms total response time including profile enrichment
- Cosine similarity scoring with relevance ranking

### Search Capabilities

**1. Semantic Job Matching**
```
Job Description Input → VertexAI Embedding → pgvector Query → Ranked Candidates
```

**2. Skill-Aware Search**
- Required skills with minimum confidence thresholds
- Skill category filtering (technical, soft, leadership, domain)
- Composite ranking: skill_match (40%) + confidence (25%) + vector_similarity (25%) + experience_match (10%)
- Fuzzy skill matching with synonym support

**3. Hybrid Search**
- Semantic similarity + structured filters
- Location, experience level, skill requirements
- Company tier and industry preferences
- Evidence-based skill validation

**4. Profile Updates**
- LinkedIn profile changes → Re-processing → Updated embeddings
- Skill confidence scores updated with new evidence
- Maintains search accuracy with fresh data

## Development Status & Quality Validation

### ✅ Production-Ready Components

**Stage 1: Basic Enhancement**
- ✅ Together AI Llama 3.2 3B Instruct Turbo integration
- ✅ Comprehensive 15+ field enhanced_analysis structure
- ✅ 98.9% field completeness in quality testing
- ✅ $0.0006 per candidate Stage 1 cost
- ✅ 1,500+ candidates/hour throughput

**Stage 2: Contextual Intelligence**
- ✅ Qwen2.5 Coder 32B model selection and cost analysis
- ✅ Company intelligence database (Google, Amazon, McKinsey patterns)
- ✅ Industry pattern recognition (FinTech, consulting, tech contexts)
- ✅ Role progression analysis (VP, team lead, individual contributor)
- ✅ Educational context weighting system
- ✅ Demonstrated LLM trajectory-based skill inference capability

**Skill Probability Assessment (Task #25)**
- ✅ Enhanced PromptBuilder with skill confidence scoring (0-100%)
- ✅ SkillWithEvidence model with Pydantic schema validation
- ✅ Skill categorization: technical, soft, leadership, domain
- ✅ Evidence-based skill validation with supporting arrays
- ✅ Skill-aware search with composite ranking algorithm
- ✅ React SkillConfidenceDisplay component with interactive UI
- ✅ Comprehensive test suite with 24 test methods
- ✅ Integration with IntelligentSkillProcessor for probabilistic inference

**Stage 3: Vector Generation**
- ✅ VertexAI text-embedding-004 integration
- ✅ 768-dimensional embedding generation
- ✅ Searchable text extraction from enhanced profiles

**Cloud Infrastructure**
- ✅ Cloud Run workers with auto-scaling (1-100 instances)
- ✅ Pub/Sub orchestration for batch processing
- ✅ Secret Manager for secure API key management
- ✅ Firestore + Cloud SQL dual storage

**Quality Metrics** (Validated with 20-candidate test)
- ✅ 98.9% average field completeness
- ✅ Comprehensive profiles across all role types
- ✅ Rich recruiter-optimized data for search
- ✅ $0.0005 average cost per candidate

### 🚧 In Development

**Multi-Stage Pipeline Integration**
- Stage 1→2→3 orchestration and error handling
- Qwen2.5 Coder 32B implementation for contextual analysis
- Stage-specific prompt optimization and testing

**Vector Search Implementation**
- ✅ Cloud SQL + pgvector database setup
- ✅ Complete embedding pipeline deployment
- ✅ Semantic search API endpoints with skill-aware ranking
- ✅ CRUD operations for profile management
- [ ] Multi-stage pipeline orchestration

**Web Interface**
- React TypeScript search application
- Job description upload interface
- Candidate results with similarity scores
- Profile management and update workflows

## Performance & Cost Analysis

### Processing Performance
- **Per Candidate**: 2-3 seconds comprehensive analysis
- **Batch Capacity**: 1,500+ candidates/hour with parallel workers
- **Daily Capacity**: 50,000+ candidates processed
- **Storage**: Unlimited scalability (Firestore + Cloud SQL)

### Cost Structure (20,000 candidates/month)
- **Stage 1 (Llama 3.2 3B)**: ~$12/month ($0.0006 per candidate)
- **Stage 2 (Qwen2.5 32B)**: ~$40/month ($0.002 per candidate)
- **Stage 3 (VertexAI)**: ~$4/month ($0.0002 per candidate)
- **Cloud Run Computing**: ~$160/month ($0.008 per candidate)
- **Storage & Database**: ~$86/month ($0.0043 per candidate)
- **Total**: ~$302/month operational cost

### Multi-Stage Cost Analysis
- **Basic Enhancement Only**: $172/month (single stage)
- **Enhanced + Contextual**: $212/month (two stages) 
- **Full Pipeline**: $302/month (three stages) ← **RECOMMENDED**
- **Premium (70B model)**: $316/month (4.4x Stage 2 cost)
- **Enterprise (405B model)**: $527/month (17.5x Stage 2 cost)

### Cost-Benefit Justification
- **4x Investment in Stage 2**: Sophisticated contextual intelligence
- **Company Pattern Recognition**: Google vs startup skill inference
- **Industry Intelligence**: FinTech vs consulting expertise mapping
- **Career Trajectory Analysis**: VP vs team lead capability assessment
- **ROI**: Superior candidate matching justifies premium contextual analysis

## Implementation Roadmap

### Phase 1: Core Infrastructure ✅
- [x] Together AI integration and testing
- [x] Cloud Run worker development
- [x] Comprehensive profile generation
- [x] Quality validation (98.9% completeness)

### Phase 2: Multi-Stage Intelligence (Current)
- [x] Stage 1: Basic enhancement with Llama 3.2 3B
- [x] Stage 2: Contextual intelligence design with Qwen2.5 32B
- [x] Stage 3: Vector generation with VertexAI embeddings
- [ ] Multi-stage pipeline orchestration
- [ ] Cloud SQL + pgvector database setup
- [ ] Semantic search API development
- [ ] CRUD operations for profile management

### Phase 3: Web Interface
- [ ] React search application
- [ ] Job description upload interface
- [ ] Search results with similarity scores
- [ ] Profile update and management UI

### Phase 4: Production Deployment
- [ ] Full 29,000 candidate processing
- [ ] Performance optimization and monitoring
- [ ] User training and onboarding
- [ ] Analytics and success metrics tracking

## Security & Compliance

### Data Privacy
- **API Keys**: Stored in Google Secret Manager with automatic rotation
- **Data Transit**: HTTPS-only communication with encryption
- **Data Storage**: Encrypted at rest in Firestore and Cloud SQL
- **Access Control**: Firebase Auth with role-based permissions

### Compliance Considerations
- **GDPR**: Right to deletion via CRUD APIs
- **Data Residency**: All processing within specified GCP regions
- **Audit Logging**: Complete processing and access trail
- **PII Handling**: Sanitized logs and secure data processing

## Risk Mitigation

### Technical Risks
- **AI Quality**: Validated with 98.9% field completeness across diverse candidate types
- **Performance**: Proven scalability with auto-scaling Cloud Run architecture
- **Cost Control**: Fixed per-candidate pricing model with budget monitoring
- **Data Consistency**: Dual-storage synchronization with retry logic

### Business Risks
- **User Adoption**: Intuitive interface with immediate value demonstration
- **Search Accuracy**: Semantic understanding provides superior matches vs keyword search
- **Scalability**: Cloud-native architecture handles growth automatically

## Success Criteria

### Technical Milestones
1. **Processing Capability**: Handle 29,000 candidates with >95% success rate
2. **Search Performance**: <200ms response time for semantic queries
3. **Data Quality**: Maintain >95% profile completeness across all candidates
4. **Cost Efficiency**: Stay within $350/month operational budget

### Business Outcomes  
1. **Time Savings**: Reduce recruiter search time from 2+ hours to <5 minutes
2. **Search Quality**: 90%+ relevance in top 20 search results
3. **User Engagement**: >20 searches per recruiter per week
4. **ROI**: 10x improvement in recruiter productivity

## Future Enhancements

### Advanced Features
- **Multi-language Support**: International candidate processing
- **Real-time Processing**: Streaming profile updates
- **Advanced Analytics**: Hiring success metrics and model fine-tuning
- **Integration APIs**: ATS system connectors and third-party tools

### Scaling Opportunities
- **Multi-region Deployment**: Global processing with regional compliance
- **Custom Model Training**: Fine-tuned models based on recruiter feedback
- **Graph-based Search**: Candidate relationship mapping and referral networks
- **Performance Optimization**: Sub-50ms search response times

## Conclusion

Headhunter v2.0 represents a paradigm shift from keyword-based search to intelligent semantic matching, powered by state-of-the-art AI and cloud infrastructure. With validated quality metrics (98.9% profile completeness), cost-effective processing ($0.005 per candidate), and scalable architecture (1,500+ candidates/hour), the system is ready to transform recruitment workflows and unlock the strategic value of candidate databases.

The cloud-native design ensures reliable processing at scale while maintaining cost efficiency and superior search performance compared to traditional approaches. The comprehensive 15+ field profiles provide recruiters with rich, actionable insights for effective candidate matching and relationship building.

---

**Version**: 2.0  
**Status**: Development Phase 2 (Integration Testing)  
**Last Updated**: September 11, 2025

## Recent Developments

### Task #25: Skill Probability Assessment (Completed - September 11, 2025)

**Implementation Details:**
- **Enhanced AI Processing**: Updated PromptBuilder with comprehensive skill confidence scoring instructions for Together AI models
- **Pydantic Schema Evolution**: Added SkillWithEvidence model with confidence (0-100%) and evidence arrays
- **Skill Categorization**: Implemented 4-category system (technical, soft, leadership, domain) with intelligent classification
- **Evidence-Based Validation**: Each skill includes supporting evidence from resumes and recruiter comments
- **Advanced Search Algorithm**: Composite ranking system with weighted factors:
  - Skill match: 40% (primary relevance)
  - Confidence: 25% (reliability weighting)
  - Vector similarity: 25% (semantic understanding)
  - Experience match: 10% (additional context)
- **Fuzzy Matching**: Synonym support for skill variations (e.g., "React.js" matches "ReactJS")
- **Interactive UI**: React component with confidence bars, category grouping, and evidence display
- **Quality Assurance**: 24-test comprehensive test suite covering schema validation, service functionality, and integration workflows

**Technical Impact:**
- Enhanced search precision with probabilistic skill assessment
- Improved candidate-role matching through confidence weighting
- Reduced false positives via evidence-based validation
- Seamless integration with existing pgvector infrastructure

**Business Value:**
- More accurate candidate recommendations based on skill confidence
- Reduced recruiter time evaluating candidate suitability
- Better understanding of skill gaps and training needs
- Enhanced user experience with interactive skill visualizations
