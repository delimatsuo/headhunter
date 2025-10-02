# Google Cloud Platform Infrastructure Setup (Fastify Services)

> Canonical repository path: `/Volumes/Extreme Pro/myprojects/headhunter`. All deployment scripts assume this layout.

This guide documents the infrastructure required to run the Headhunter Fastify mesh on Google Cloud Platform (GCP) and how it maps to the local `docker-compose.local.yml` stack. Use it alongside `README.md`, `ARCHITECTURE.md`, and `docs/HANDOVER.md` for daily operations.

## Core GCP Resources

| Resource | Purpose |
| --- | --- |
| **Cloud Run (8 services)** | `hh-embed-svc`, `hh-search-svc`, `hh-rerank-svc`, `hh-evidence-svc`, `hh-eco-svc`, `hh-msgs-svc`, `hh-admin-svc`, `hh-enrich-svc`.
| **Cloud SQL (Postgres + pgvector)** | Embeddings, rerank materializations, messaging state, admin schedules.
| **MemoryStore (Redis)** | Cache for embeddings/rerank, rate limits, worker coordination.
| **Firestore (Native mode)** | Canonical candidate profiles, recruiter activity, tenant metadata.
| **Pub/Sub + Cloud Scheduler** | Admin schedulers, async jobs, enrichment triggers.
| **Artifact Registry** | Stores container images built from `services/**/Dockerfile`.
| **Secret Manager** | Keeps API keys (Together AI, Firebase Admin, OAuth JWKs, etc.).
| **Cloud Build / GitHub Actions** | CI/CD for building and deploying services.

## Local ↔ Production Parity Map

| Local container (`docker-compose.local.yml`) | Image | Production equivalent |
| --- | --- | --- |
| `postgres` | `ankane/pgvector:v0.5.1` | Cloud SQL instance with pgvector extension enabled |
| `redis` | `redis:7-alpine` | MemoryStore Redis (standard tier) |
| `firestore` & `pubsub` emulators | `gcr.io/google.com/cloudsdktool/cloud-sdk:slim` | Firestore (native mode) & Pub/Sub + Cloud Scheduler |
| `mock-together-ai` | `node:20-alpine` mock server | Together AI hosted API |
| `mock-oauth` | `node:20-alpine` mock issuer | Google Identity Platform / Auth0 tenant SSO |
| `python-worker` | `python:3.11-slim` | Cloud Run jobs for enrichment pipelines |
| `hh-*-svc` containers | `node:20-alpine` derived images | Cloud Run services per workspace |

Maintain parity by keeping compose definitions and GCP infra configs in sync. When you change a dependency locally, reflect the same in Terraform or deployment scripts and update this guide.

## Prerequisites

- Google Cloud CLI (`gcloud`) authenticated with deployment credentials.
- Docker (build services locally, mirror Cloud Build outputs when needed).
- Node.js 20+ and Python 3.11+ for local builds/tests.
- Access to production secrets (Secret Manager).

## Project Bootstrap

### Automated Provisioning (Recommended)

The fastest way to provision all infrastructure is using the automated orchestration script:

```bash
# Provision all infrastructure with a single command
./scripts/provision-gcp-infrastructure.sh --project-id headhunter-ai-0088

# Or with custom config
./scripts/provision-gcp-infrastructure.sh \
  --project-id headhunter-ai-0088 \
  --config config/infrastructure/headhunter-production.env

# Dry run to see what would be provisioned
./scripts/provision-gcp-infrastructure.sh \
  --project-id headhunter-ai-0088 \
  --dry-run
```

**What this does:**
1. Validates prerequisites (gcloud auth, IAM permissions, secret values)
2. Enables all required GCP APIs
3. Sets up Secret Manager with placeholder secrets
4. Provisions VPC networking with NAT and connectors
5. Creates Cloud SQL instance with pgvector extension
6. Creates Redis (MemoryStore) instance
7. Sets up Pub/Sub topics and subscriptions
8. Creates Cloud Storage buckets
9. Configures Firestore database in native mode
10. Generates comprehensive infrastructure notes
11. Runs validation checks

**After provisioning:**
- Review provisioned resources: `docs/infrastructure-notes.md`
- Populate secrets with real values (see Secret Prerequisites section below)
- Deploy Cloud Run services (see Service Deployment section)

### Secret Prerequisites

Before provisioning, prepare your secret values:

```bash
# Validate secret prerequisites
./scripts/validate-secret-prerequisites.sh --check-only

# Generate a template for secret values
./scripts/validate-secret-prerequisites.sh --generate-template

# Populate secrets (example)
export HH_SECRET_DB_PRIMARY_PASSWORD="$(openssl rand -base64 32)"
export HH_SECRET_TOGETHER_AI_API_KEY="your-together-api-key"
export HH_SECRET_OAUTH_CLIENT_CREDENTIALS='{"client_id":"...","client_secret":"..."}'
export HH_SECRET_STORAGE_SIGNER_KEY="$(openssl rand -base64 32)"
```

**Note:** The provisioning script will create placeholder secrets if real values aren't provided. You can populate them after provisioning using Secret Manager commands (documented in `docs/infrastructure-notes.md`).

### Manual Provisioning (Alternative)

If you prefer step-by-step control or need to troubleshoot specific components, follow the manual commands below:

```bash
PROJECT_ID=headhunter-ai-0088
REGION=us-central1

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com sqladmin.googleapis.com redis.googleapis.com \
  firestore.googleapis.com pubsub.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com cloudbuild.googleapis.com iam.googleapis.com
```

### Cloud SQL (Postgres + pgvector)

```bash
INSTANCE=headhunter-shared-services
gcloud sql instances create "$INSTANCE" \
  --database-version=POSTGRES_15 \
  --tier=db-custom-2-7680 \
  --region="$REGION" \
  --storage-auto-increase

gcloud sql databases create headhunter --instance="$INSTANCE"
gcloud sql users set-password headhunter --instance="$INSTANCE" --password=$(openssl rand -base64 20)

gcloud sql connect "$INSTANCE" --user=postgres --quiet <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
SQL
```

### MemoryStore (Redis)

```bash
gcloud redis instances create headhunter-shared-cache \
  --size=1 \
  --region="$REGION" \
  --tier=BASIC \
  --replica-count=1
```

### Firestore & Pub/Sub

```bash
gcloud firestore databases create --location="$REGION" --type=firestore-native
gcloud pubsub topics create hh-admin-scheduler
gcloud pubsub subscriptions create hh-admin-scheduler-sub \
  --topic=hh-admin-scheduler \
  --ack-deadline=30
```

### Artifact Registry

```bash
gcloud artifacts repositories create headhunter-shared-services \
  --repository-format=docker \
  --location="$REGION"
```

### Secret Manager

```bash
gcloud secrets create hh-together-api-key --replication-policy="automatic"
gcloud secrets create hh-firebase-service-account --replication-policy="automatic"
gcloud secrets create hh-oauth-jwks --replication-policy="automatic"

gcloud secrets versions add hh-together-api-key --data-file=./.gcp/together.key
gcloud secrets versions add hh-firebase-service-account --data-file=./.gcp/headhunter-service-key.json
gcloud secrets versions add hh-oauth-jwks --data-file=./.gcp/mock-oauth-jwks.json
```

Reference these secrets in Cloud Run via `--set-secrets` (CLI) or Terraform equivalent.

## Deploying Fastify Services to Cloud Run

Each workspace has a Dockerfile under `services/<name>/Dockerfile`. Cloud Build configs (`cloud_run_<service>.yaml`) handle build arguments.

| Service | Key env vars | Secret bindings | Notes |
| --- | --- | --- | --- |
| `hh-embed-svc` | `REDIS_URL`, `PGVECTOR_URL`, `EMBEDDING_PROVIDER` | Together AI key | Enable Cloud SQL connection via `--add-cloudsql-instances`. |
| `hh-search-svc` | `REDIS_URL`, `PGVECTOR_URL`, `TENANT_HEADER`, `RERANK_ENDPOINT` | OAuth JWKs | Requires outbound call to rerank service; allow private ingress. |
| `hh-rerank-svc` | `REDIS_URL`, `PGVECTOR_URL`, `EMBED_CACHE_TTL` | Together AI key (fallback) | Configure autoscaling min instances to keep caches warm. |
| `hh-evidence-svc` | `FIRESTORE_PROJECT`, `PGVECTOR_URL` | Firebase SA | Needs Firestore IAM binding `roles/datastore.user`. |
| `hh-eco-svc` | `PGVECTOR_URL`, `FIRESTORE_PROJECT`, `TEMPLATE_BUCKET` | Firebase SA | Mount templates via Cloud Storage bucket. |
| `hh-msgs-svc` | `PUBSUB_TOPIC`, `REDIS_URL`, `PGVECTOR_URL` | Firebase SA | Grant `roles/pubsub.publisher` to service account. |
| `hh-admin-svc` | `ADMIN_TOPIC`, `SCHEDULER_PROJECT`, `REDIS_URL` | Firebase SA, OAuth JWKs | Ensure Cloud Scheduler targets Pub/Sub topic created above. |
| `hh-enrich-svc` | `PGVECTOR_URL`, `REDIS_URL`, `PY_WORKER_URL` | Together AI key, Firebase SA | Calls Cloud Run job (Python worker) or Vertex pipelines.

Example deployment snippet (adjust per service):

```bash
SERVICE=hh-search-svc
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/headhunter-shared-services/${SERVICE}:$(git rev-parse --short HEAD)"

# Build
gcloud builds submit --config=cloud_run_${SERVICE}.yaml . --substitutions=_IMAGE="$IMAGE"

# Deploy
gcloud run deploy "$SERVICE" \
  --image="$IMAGE" \
  --region="$REGION" \
  --allow-unauthenticated \
  --add-cloudsql-instances="$PROJECT_ID:$REGION:$INSTANCE" \
  --set-env-vars="REDIS_URL=rediss://<memorystore-host>:6379" \
  --set-env-vars="PGVECTOR_URL=postgresql://headhunter:<password>@/<db>?host=/cloudsql/$PROJECT_ID:$REGION:$INSTANCE" \
  --set-secrets="TOGETHER_API_KEY=hh-together-api-key:latest" \
  --set-secrets="OAUTH_JWKS=hh-oauth-jwks:latest" \
  --vpc-connector=headhunter-shared-vpc \
  --ingress=internal-and-cloud-load-balancing
```

Repeat for each service, adjusting env vars, secrets, and minimum instance counts to maintain warm caches (especially `hh-rerank-svc`). Document any service-specific flags in Terraform modules and keep this table updated.

## Bootstrap Automation Alignment

`scripts/prepare-local-env.sh` (in development) will unify local bootstrap steps: dependency install, `.env` hydration, emulator reseed, compose startup, and integration smoke tests. Ensure the script also writes Cloud SQL proxy instructions and surfaces any GCP-specific prerequisites (e.g., enabling APIs). Tag manual GCP setup steps in this doc with `TODO prepare-local-env` if they should be automated or validated by the script.

## Integration Validation After Deployment

1. Run the local integration suite to establish baseline metrics:
   ```bash
   SKIP_JEST=1 npm run test:integration --prefix services
   ```
   Confirm `cacheHitRate=1.0` and rerank latency ≈ 0 ms.
2. Deploy services to Cloud Run.
3. Execute the same integration tests against staging/production endpoints using the `API_BASE_URL` override:
   ```bash
   API_BASE_URL=https://staging.api.headhunter.ai \
   npm run test:integration --prefix services
   ```
4. Compare metrics: Managed Prometheus should report parity with local baselines. Investigate Redis or Postgres configuration if hit rate or latency diverges.
5. Record results in `integration-results.log` and append a note to `docs/HANDOVER.md` if anomalies persist.

## Monitoring & Observability

- **Metrics ingestion**: Enable Managed Prometheus. Annotate each Cloud Run service with `--set-env-vars="METRICS_ENABLED=true"` and configure scrape targets for `/metrics`.
- **Dashboards**: Track `rerank_cache_hit_rate`, `rerank_latency_ms`, HTTP 5xx counts, Redis connection errors, and Cloud SQL connection utilization.
- **Health checks**: Cloud Run uses `/health`; also expose `/ready` where applicable. Configure alerting policies for repeated failures.
- **Logging**: Logs stream to Cloud Logging under each service. Use log-based metrics to capture tenant violations or JWT failures.

## Infrastructure Notes & Documentation

After provisioning infrastructure (either automated or manual), consult the auto-generated infrastructure notes document:

**Location:** `docs/infrastructure-notes.md`

This document contains:
- Actual resource IDs and connection strings for all provisioned resources
- Service account emails and IAM roles
- Network configuration details (VPC connector URIs, subnet ranges)
- Ready-to-use connection strings for local development and Cloud Run deployment
- Validation results showing infrastructure health status
- Step-by-step instructions for populating secrets
- Next steps for service deployment

**Regenerate the notes at any time:**

```bash
./scripts/generate-infrastructure-notes.sh --project-id headhunter-ai-0088
```

## Infrastructure Cleanup (Development/Testing)

For development iterations or testing, you can safely tear down provisioned infrastructure:

```bash
# Full cleanup (requires explicit confirmation)
./scripts/cleanup-gcp-infrastructure.sh \
  --project-id headhunter-ai-0088 \
  --confirm

# Dry run to see what would be deleted
./scripts/cleanup-gcp-infrastructure.sh \
  --project-id headhunter-ai-0088 \
  --confirm \
  --dry-run

# Selective cleanup
./scripts/cleanup-gcp-infrastructure.sh \
  --project-id headhunter-ai-0088 \
  --confirm \
  --only-storage  # Only delete Cloud Storage buckets

# Keep secrets during cleanup
./scripts/cleanup-gcp-infrastructure.sh \
  --project-id headhunter-ai-0088 \
  --confirm \
  --keep-secrets
```

**Safety features:**
- Requires explicit `--confirm` flag
- Requires typing project ID to confirm deletion
- Refuses to delete production project without `--force-production` flag
- Creates timestamped cleanup logs in `.infrastructure/cleanup-YYYYMMDD-HHMMSS.log`
- Supports dry-run mode to preview deletions

## Mock Services & Production Equivalents

- **Together AI mock** (`mock-together-ai` in compose) simulates embedding/enrichment APIs offline. Production always calls the real Together AI endpoint secured by Secret Manager keys.
- **Mock OAuth** issues JWTs locally; production relies on Google Identity Platform/SSO. Ensure JWKS hosted in Secret Manager matches the gateway configuration.
- **Firestore/Pub/Sub emulators** mimic data stores locally; production uses fully managed services with IAM-scoped service accounts. Keep topic and collection names identical for parity.

## Troubleshooting Cloud Run Deployments

- **Cold start latency**: Increase minimum instances (`--min-instances=1`) for `hh-rerank-svc` and `hh-search-svc` to keep caches warm.
- **Redis connectivity failures**: Verify VPC connector and serverless NEG configuration. Test connectivity with `gcloud beta compute ssh` into a bastion host and run `redis-cli -h <host>`.
- **Cloud SQL connection limits**: Adjust `--set-env-vars="PG_POOL_MAX=10"` and ensure Cloud SQL instance tier supports required connections.
- **JWT validation errors**: Rotate JWKS in Secret Manager and redeploy. Confirm gateway audience/issuer match service env vars.
- **Pub/Sub permission issues**: Service accounts need `roles/pubsub.publisher`/`subscriber`. Re-run `gcloud projects add-iam-policy-binding` as needed.
- **Python worker timeouts**: Scale Cloud Run job CPU/memory or switch to dedicated Cloud Run service if enrichment exceeds 15 minutes.

### Troubleshooting Infrastructure Provisioning

**Insufficient IAM permissions:**
- Verify current user has Owner or Editor role: `gcloud projects get-iam-policy headhunter-ai-0088 --flatten="bindings[].members" --filter="bindings.members:<your-email>"`
- Grant required permissions: `gcloud projects add-iam-policy-binding headhunter-ai-0088 --member="user:<your-email>" --role="roles/editor"`

**API enablement delays:**
- Some APIs (especially VPC, Cloud SQL) can take 2-5 minutes to become fully active after enabling
- If provisioning fails immediately after API enablement, wait a few minutes and retry

**Resource quota limits:**
- Check quota status: `gcloud compute project-info describe --project=headhunter-ai-0088`
- Request quota increases through GCP Console if needed (especially for Cloud SQL CPU, Redis memory)

**Network configuration conflicts:**
- If VPC creation fails with "already exists", check for orphaned resources: `gcloud compute networks list --project=headhunter-ai-0088`
- Use the cleanup script to remove conflicting resources before reprovisioning

**Secret population issues:**
- Validate secret format before adding: `echo "$SECRET_VALUE" | jq .` (for JSON secrets)
- Ensure secret values meet minimum length requirements (20+ chars for passwords, 32+ for API keys)
- Check secret access: `gcloud secrets versions access latest --secret=SECRET_NAME --project=headhunter-ai-0088`

**Cloud SQL connectivity issues:**
- Verify pgvector extension is enabled: `gcloud sql connect INSTANCE_NAME --user=postgres` then `\dx`
- Check private IP configuration and VPC peering
- Ensure Cloud SQL instance has sufficient memory for pgvector operations (recommend 7680 MB minimum)

**Firestore mode conflicts:**
- If Firestore creation fails, check existing mode: `gcloud firestore databases list --project=headhunter-ai-0088`
- Cannot convert Datastore mode to Firestore native mode - would require a new project

## Local Parity Checklist

1. Ensure Docker Desktop is running.
2. From `/Volumes/Extreme Pro/myprojects/headhunter`, run `docker compose -f docker-compose.local.yml up --build`.
3. Seed Firestore and Postgres using `scripts/manage_tenant_credentials.sh`.
4. Validate health endpoints (`curl localhost:710X/health`) and metrics parity with production.
5. Tag any manual gap with `TODO prepare-local-env` to feed the upcoming bootstrap script.

## Bootstrap Automation Alignment

The new automated provisioning scripts integrate seamlessly with the local development environment:

**Provisioning → Local Development Flow:**

1. **Provision infrastructure**: `./scripts/provision-gcp-infrastructure.sh --project-id headhunter-ai-0088`
2. **Review infrastructure notes**: `docs/infrastructure-notes.md` contains all connection strings
3. **Configure local environment**: Use connection strings from infrastructure notes to configure local `.env` files
4. **Test locally**: `docker compose -f docker-compose.local.yml up --build`
5. **Deploy to Cloud Run**: Use the same configuration from infrastructure notes for Cloud Run deployment

**Key integration points:**
- Infrastructure notes document provides connection strings compatible with both local and Cloud Run environments
- Secret values populated in Secret Manager can be used by both local development (via `gcloud secrets versions access`) and Cloud Run (via `--set-secrets`)
- VPC connector URIs from infrastructure notes can be used directly in Cloud Run deployment commands
- Cloud SQL connection names work with both Cloud SQL Proxy (local) and Cloud SQL connector (Cloud Run)

## Change Log

- **2025-09-29** – Added automated provisioning orchestration, infrastructure notes generation, secret validation, cleanup scripts, and comprehensive troubleshooting guides.
- **2025-09-13** – Expanded parity mapping, deployment specifics, monitoring guidance, and troubleshooting playbooks for the Fastify mesh.
