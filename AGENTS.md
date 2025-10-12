# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 MANDATORY PRE-WORK PROTOCOL (NEVER SKIP)

**THESE RULES ARE ENFORCED ON EVERY TASK. VIOLATION = SESSION TERMINATION.**

### Before ANY implementation work, Claude MUST:

1. **Run `task-master next`** - Check what task should be worked on
2. **Run `task-master show <id>`** - Read the full task details
3. **Read PRD section** relevant to the task (cite specific line numbers from `.taskmaster/docs/prd.txt`)
4. Proceed directly after verifying PRD alignment; do not pause for confirmation unless scope changes.

### VIOLATION DETECTION RULES
- If user requests work that's NOT in the current task: **STOP immediately**
- Ask: "This seems outside the current task [ID]. Should we add this as a new task first?"
- **Don't implement** until task is updated in TaskMaster

### SCOPE CHANGE PROTOCOL
- If request seems outside PRD scope: **Reference PRD line numbers** showing what's planned
- Ask: "This appears to be a scope change from PRD line [X]. Should we update the PRD first?"
- **Don't proceed** without explicit approval

### ARCHITECTURE COMPLIANCE
- **Firestore**: For operational data (profiles, CRUD, real-time updates)
- **Cloud SQL + pgvector**: For search and embeddings (PRD lines 74, 79, 143)
- **Together AI**: For production AI processing (PRD lines 77, 139-141)
- **Never suggest architectural changes** without referencing PRD and getting approval

### MANDATORY SESSION START TEMPLATE
```
🚨 WORK SESSION COMPLIANCE CHECK
Current Task: [from task-master next]
PRD Reference: [specific line numbers from prd.txt]
Alignment Status: [request matches PRD + task? yes/no]
Scope Status: [in scope / needs approval / scope change]
Architecture: [follows PRD design? yes/no]
Proceeding with: [only if all above are YES]
```

### 🚨 GIT AND DEPLOYMENT PROTOCOL (MANDATORY)

**THESE RULES APPLY TO ALL DEVELOPMENT WORK:**

**📋 IMPORTANT: See CLAUDE-FLOW.md for complete commit/push protocol**

1. **Test-Driven Development (TDD) is MANDATORY**
   - Write tests BEFORE implementation
   - All tests must pass before committing
   - Never skip testing for "quick fixes"

2. **Commit and Document After Every Completed Task**
   - When a task passes all tests: `git add . && git commit -m "feat: [description]"`
   - Update relevant documentation (README, API docs, etc.)
   - Keep commits focused and atomic
   - **MUST follow protocol in CLAUDE-FLOW.md**

3. **Push to Remote After Task Completion**
   - After successful commit: `git push origin [branch]`
   - Ensures work is backed up and visible to team
   - Creates checkpoint for recovery if needed
   - **Push IMMEDIATELY after commit (see CLAUDE-FLOW.md)**

4. **Production-First Mindset**
   - **PRIMARY GOAL**: Get application to production for testing
   - Fix blocking issues, don't create workarounds
   - Prioritize production readiness over perfection

5. **GCP/Firebase Project Management**
   - **NEVER create new GCP projects** without explicit user authorization
   - **NEVER create new Firebase projects** without explicit user authorization
   - Work within existing project: `headhunter-ai-0088`
   - If project limitation encountered, ask user for guidance FIRST

6. **Infrastructure Changes Require Approval**
   - Don't create new Cloud SQL instances, Redis instances, etc. without asking
   - Don't modify existing production infrastructure without user approval
   - Document all infrastructure changes in `.deployment/` directory

**Example Workflow**:
```bash
# 1. Write tests (TDD)
# 2. Implement feature
# 3. Run tests - all pass
git add .
git commit -m "feat: implement lazy initialization for hh-search-svc

- Add health endpoints before server.listen()
- Initialize dependencies in background with setImmediate()
- Tests: 15/15 passing"

# 4. Update documentation
git add docs/
git commit -m "docs: update deployment guide with lazy init pattern"

# 5. Push to remote
git push origin main

# 6. Deploy to production (when ready)
./scripts/deploy-cloud-run-services.sh --environment production
```

## Project Overview

Headhunter is an AI-powered recruitment analytics system delivered as **eight Fastify microservices** working with shared infrastructure (Postgres+pgvector, Redis, Firestore, Pub/Sub). The system processes candidate data using **Together AI** for enrichment, stores enhanced profiles in Firestore, embeddings in Cloud SQL (pgvector), and exposes search/admin APIs via Cloud Run services.

**Canonical repository path:** `/Volumes/Extreme Pro/myprojects/headhunter`
**DO NOT** use deprecated clone: `/Users/delimatsuo/Documents/Coding/headhunter`

TDD is mandatory for all work. See `docs/TDD_PROTOCOL.md`.

## Architecture Overview

### Fastify Service Mesh (8 Services, Ports 7101-7108)

| Service | Port | Primary Responsibilities |
|---------|------|-------------------------|
| `hh-embed-svc` | 7101 | Normalizes profiles, requests embedding jobs, hands off to enrichment |
| `hh-search-svc` | 7102 | Multi-tenant search, pgvector recalls with deterministic filters, rerank orchestration |
| `hh-rerank-svc` | 7103 | Redis-backed scoring caches, enforces `cacheHitRate=1.0` baseline |
| `hh-evidence-svc` | 7104 | Provenance artifacts and evidence APIs |
| `hh-eco-svc` | 7105 | ECO data pipelines, occupation normalization, templates |
| `hh-msgs-svc` | 7106 | Notifications, queue fan-out, Pub/Sub bridging |
| `hh-admin-svc` | 7107 | Scheduler, tenant onboarding, policy enforcement |
| `hh-enrich-svc` | 7108 | Long-running enrichment, calls Python workers via bind-mounted `scripts/` |

### Shared Infrastructure (docker-compose.local.yml)

- **Postgres** (`ankane/pgvector:v0.5.1`) - master store for search, embeddings, transactional data
- **Redis** (`redis:7-alpine`) - request cache, idempotency locks, rerank scoring
- **Firestore emulator** - candidate profiles, operational data
- **Pub/Sub emulator** - scheduler topics, async messaging
- **Mock OAuth** - JWT issuance for local development
- **Mock Together AI** - LLM API contract emulation
- **Python worker** (`python:3.11-slim`) - bind-mounted `scripts/` for enrichment pipelines

## Commands

### Workspace Setup
```bash
# Install all service dependencies (from repo root)
npm install --workspaces --prefix services

# Build all TypeScript services
npm run build --prefix services

# Typecheck all services
npm run typecheck --prefix services

# Lint all services
npm run lint --prefix services
```

### Local Development Stack
```bash
# Start entire local mesh (infrastructure + services)
docker compose -f docker-compose.local.yml up --build

# View logs for specific service
docker compose logs -f hh-search-svc

# Health check all services
for port in 7101 7102 7103 7104 7105 7106 7107 7108; do
  curl -sf localhost:$port/health || echo "Port $port failed"
done
```

### Testing

#### TypeScript Services (Vitest/Jest)
```bash
# Run all service tests
npm test --prefix services

# Run specific service tests
npm test --prefix services/hh-search-svc

# Integration tests (requires stack running)
SKIP_JEST=1 npm run test:integration --prefix services
```

#### Python Tests (pytest)
```bash
# Run all Python tests
python3 -m pytest tests/

# Run specific test file
python3 -m pytest tests/test_eco_data_collection.py

# Run integration tests
python3 -m pytest tests/integration/
```

#### Integration Baseline
Must achieve before merging:
- **`cacheHitRate=1.0`** (from `hh-rerank-svc`)
- **Rerank latency ≈ 0 ms** (sub-millisecond)

### Python Processing Scripts
```bash
# Together AI processors (production)
python3 scripts/together_ai_processor.py
python3 scripts/firebase_streaming_processor.py
python3 scripts/together_ai_firestore_processor.py
python3 scripts/intelligent_skill_processor.py

# PRD compliance validation
python3 scripts/prd_compliant_validation.py
```

### GCP Infrastructure & Deployment
```bash
# Provision all GCP infrastructure (Cloud SQL, Redis, VPC, Pub/Sub, Storage, Firestore, Secrets)
./scripts/provision-gcp-infrastructure.sh --project-id headhunter-ai-0088

# Deploy to production
./scripts/deploy-production.sh --project-id headhunter-ai-0088

# Set up monitoring & alerting
./scripts/setup-monitoring-and-alerting.sh --project-id headhunter-ai-0088 --notification-channels <channels>

# Run post-deployment load tests
./scripts/run-post-deployment-load-tests.sh --gateway-endpoint https://<gateway-host> --tenant-id tenant-alpha

# Validate deployment readiness
./scripts/validate-deployment-readiness.sh --project-id headhunter-ai-0088 --environment production
```

## Technology Stack

### Production Stack
- **AI Processing**: Together AI (meta-llama/Llama-3.1-8B-Instruct-Turbo)
- **Embeddings**: VertexAI text-embedding-004 OR Together AI
- **Storage**: Firebase Firestore (profiles), Cloud SQL PostgreSQL + pgvector (search, embeddings)
- **Cache**: Redis (Memorystore in production)
- **API**: Fastify services on Cloud Run
- **Messaging**: Pub/Sub + Cloud Scheduler
- **Secrets**: Secret Manager
- **Monitoring**: Cloud Monitoring, custom dashboards, alert policies

### Development Stack
- **TypeScript**: Node.js 20+, Fastify framework, Vitest/Jest testing
- **Python**: 3.11+, pytest, aiohttp, pydantic
- **Container**: Docker Desktop, docker-compose.local.yml
- **Emulators**: Firestore, Pub/Sub (Cloud SDK)
- **Mocks**: Together AI, OAuth (local only)

## Development Workflow

### TDD Protocol (MANDATORY)
1. **Write tests first** - Unit/integration tests describing desired behavior
2. **Run tests** - Confirm they fail (red)
3. **Implement** - Minimal code to make tests pass
4. **Run tests** - Iterate until green
5. **Refactor** - With tests green
6. **Document** - Update docs, commit with Task Master task ID
7. **Next task** - Only proceed when all tests pass

### Service Development Pattern
1. Changes to shared middleware → `services/common/`
2. Service-specific logic → `services/hh-*-svc/src/`
3. Python enrichment helpers → `scripts/` (bind-mounted into `hh-enrich-svc`)
4. Keep dependencies in:
   - `services/package.json` (workspace root)
   - `services/hh-*-svc/package.json` (service-specific)
   - `scripts/requirements*.txt` (Python workers)

### Bootstrap Procedure (Local)
1. **Provision GCP infrastructure** (see GCP Infrastructure Provisioning section)
2. **Install workspaces**: `npm install --workspaces --prefix services`
3. **Environment prep**: Copy `.env.example` to `.env`, populate secrets
4. **Seed tenants**: Run `scripts/manage_tenant_credentials.sh`
5. **Launch stack**: `docker compose -f docker-compose.local.yml up --build`
6. **Validate integration**: `SKIP_JEST=1 npm run test:integration --prefix services`

📌 **Coming soon:** `scripts/prepare-local-env.sh` will automate steps 2–6

## Service Dependency Graph

- `hh-search-svc` depends on: `hh-embed-svc`, `hh-rerank-svc`, Postgres, Redis
- `hh-rerank-svc` depends on: Redis (caches must be hydrated)
- `hh-enrich-svc` depends on: Postgres, Firestore emulator, Python worker volume mount
- Messaging/admin/ECO services depend on: Pub/Sub emulator initialization

Health checks enforce startup order in `docker-compose.local.yml`

## Environment & Configuration

### Environment Variables
- **Root `.env`**: Shared secrets, connection strings
- **Service `.env.local`**: Per-service overrides (e.g., `services/hh-msgs-svc/.env.local`)
- **Keep aligned**: When adding keys, update both root and service examples

### Required Environment Variables
```bash
# Together AI
export TOGETHER_API_KEY=...

# Emulators (local)
export FIRESTORE_EMULATOR_HOST=localhost:8080
export PUBSUB_EMULATOR_HOST=localhost:8681

# Redis
export REDIS_URL=redis://localhost:6379

# Postgres
export POSTGRES_URL=postgresql://headhunter:headhunter@localhost:5432/headhunter
```

### GCP Secret Prerequisites
Before provisioning or deployment:
```bash
# Validate secrets
./scripts/validate-secret-prerequisites.sh --check-only

# Generate template
./scripts/validate-secret-prerequisites.sh --generate-template

# Set required secrets
export HH_SECRET_DB_PRIMARY_PASSWORD="$(openssl rand -base64 32)"
export HH_SECRET_TOGETHER_AI_API_KEY="your-together-api-key"
export HH_SECRET_OAUTH_CLIENT_CREDENTIALS='{"client_id":"...","client_secret":"..."}'
export HH_SECRET_STORAGE_SIGNER_KEY="$(openssl rand -base64 32)"
```

## Observability & Troubleshooting

### Health Checks
Each service exposes:
- `/health` - Basic liveness check
- `/metrics` - Prometheus-style metrics

### Metrics
- **Cache hit rate**: `hh-rerank-svc` exports `rerank_cache_hit_rate` (target: 1.0)
- **Rerank latency**: Histogram exported at `/metrics` (target: <5ms)
- **Integration baseline**: Both metrics validated by integration tests

### Logs
- Structured JSON logs with `tenantId`, `requestId`, `traceId`
- Local: Stream to stdout via `docker compose logs -f <service>`
- Production: Cloud Logging with filters

### Common Issues

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| Service stuck in `starting` | Dependent container unhealthy | Check `depends_on` graph, verify health checks |
| Redis connection errors | `REDIS_URL` not set | Confirm env var, ensure Redis container on port 6379 |
| Firestore emulator auth failures | Missing `FIRESTORE_EMULATOR_HOST` | Set env var in service `.env.local` |
| Python worker timeouts | Bind mount or missing deps | Check `scripts/` mount, regenerate venv |
| JWT validation errors | Stale mock OAuth keys | Run `scripts/mock_oauth/reset_keys.sh`, recycle services |
| `cacheHitRate < 1.0` | Redis not warmed | Run `npm run seed:rerank --prefix services/hh-rerank-svc` |
| Rerank latency >5ms | Redis pool or Postgres index issue | Check connection pool, run `EXPLAIN ANALYZE` on slow queries |

## Key Documentation

- **`ARCHITECTURE.md`** - Detailed architecture, dependency graph, bootstrap context
- **`README.md`** - Quick start, infrastructure provisioning, deployment workflow
- **`docs/HANDOVER.md`** - Operator runbook, recovery procedures
- **`docs/TDD_PROTOCOL.md`** - Test-driven development guidelines
- **`docs/PRODUCTION_DEPLOYMENT_GUIDE.md`** - End-to-end deployment runbook
- **`docs/MONITORING_RUNBOOK.md`** - Monitoring and alerting operations
- **`docs/gcp-infrastructure-setup.md`** - Infrastructure provisioning checklist
- **`docs/infrastructure-notes.md`** - Auto-generated after provisioning
- **`.taskmaster/docs/prd.txt`** - Authoritative PRD (`.taskmaster/CLAUDE.md` for Task Master commands)

## Data Structures

### Enhanced Candidate Profile (Generated by Together AI)
```json
{
  "career_trajectory": {
    "current_level": "Senior",
    "progression_speed": "fast",
    "trajectory_type": "technical_leadership",
    "years_experience": 12
  },
  "leadership_scope": {
    "has_leadership": true,
    "team_size": 15,
    "leadership_level": "manager"
  },
  "company_pedigree": {
    "company_tier": "enterprise",
    "stability_pattern": "stable"
  },
  "skill_assessment": {
    "technical_skills": {
      "core_competencies": ["Python", "AWS", "ML"],
      "skill_depth": "expert"
    }
  },
  "recruiter_insights": {
    "placement_likelihood": "high",
    "best_fit_roles": ["Tech Lead", "Engineering Manager"]
  },
  "search_optimization": {
    "keywords": ["python", "aws", "leadership"],
    "search_tags": ["senior", "technical_lead"]
  },
  "executive_summary": {
    "one_line_pitch": "Senior technical leader with fintech expertise",
    "overall_rating": 92
  }
}
```

## Production Deployment

### Deployment Workflow
1. **Provision infrastructure**: `./scripts/provision-gcp-infrastructure.sh --project-id headhunter-ai-0088`
2. **Populate secrets**: Load production values into Secret Manager
3. **Deploy**: `./scripts/deploy-production.sh --project-id headhunter-ai-0088`
4. **Set up monitoring**: `./scripts/setup-monitoring-and-alerting.sh --project-id headhunter-ai-0088`
5. **Load tests**: `./scripts/run-post-deployment-load-tests.sh --gateway-endpoint https://<gateway-host>`
6. **Validate readiness**: `./scripts/validate-deployment-readiness.sh --project-id headhunter-ai-0088`
7. **Review report**: Check `docs/deployment-report-*.md` for SLA evidence and sign-off

### Deployment Artifacts
All deployment outputs in `.deployment/` (gitignored):
- Build logs and manifests
- Pre-deployment snapshots
- Smoke test reports
- Load test results
- Gateway configuration backups

### Rollback Procedures
- Automatic rollback: Use `--rollback-on-failure` flag
- Manual Cloud Run: Reference `.deployment/manifests/pre-deploy-revisions-*.json`
- Manual API Gateway: Parse `.deployment/manifests/pre-gateway-config-*.json`

## Task Master AI Integration

**All Task Master commands and workflows are documented in `.taskmaster/CLAUDE.md`**

Essential commands:
```bash
# Daily workflow
task-master next                                   # Get next available task
task-master show <id>                             # View task details
task-master set-status --id=<id> --status=done    # Mark complete

# Task management
task-master add-task --prompt="description" --research
task-master expand --id=<id> --research
task-master update-subtask --id=<id> --prompt="notes"

# Analysis
task-master analyze-complexity --research
task-master complexity-report
```

## Important Notes

### Privacy & Security
- **Production uses Together AI** - Secure cloud processing per PRD
- **VertexAI for embeddings** - No LLM processing
- **Minimal PII in prompts** - Data privacy safeguards
- **Tenant isolation** - JWT validation, Redis namespaces, Postgres schemas

### Performance Considerations
- Integration baseline: `cacheHitRate=1.0`, rerank latency ≈ 0 ms
- SLO targets: p95 latency <1.2s, error rate <1%, cache hit >0.98
- Process candidates in batches of 50-100 for stability

### Legacy Reference
Cloud Functions implementation is fully retired. Historic deployment steps remain in git history for auditing only. **Do not base new work on legacy documentation.**
