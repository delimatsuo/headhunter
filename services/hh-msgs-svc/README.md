# hh-msgs-svc

Market Skill Graph Service (MSGS) exposes skill adjacency, role template, and market demand analytics APIs for Headhunter recruiters. The service follows the shared Fastify service conventions used across the platform and ships with authentication, tenant scoping, Redis caching, and Cloud SQL connectivity.

## Endpoints

### `POST /v1/skills/expand`
Expands a seed skill into a ranked list of adjacent skills using PMI-based scoring. Supports tenant-specific caching, PMI threshold tuning, and pagination.

### `POST /v1/roles/template`
Returns a market-informed role template composed of required and preferred skills, years-of-experience ranges, and regional prevalence metadata.

Set `includeDemand` to `true` in the request body to enrich the response with a `demandIndex` calculated from the latest EMA values of the role's required skills.

### `GET /v1/market/demand`
Delivers EMA-indexed demand trends for skills by geography and industry. Provides normalized demand indices, rolling averages, and slope metadata.

All endpoints require Firebase ID token authentication and API Gateway OAuth2 enforcement upstream. Tenants are resolved from the `X-HH-Tenant` header and validated against Firestore `organizations` collection using the shared `@hh/common` utilities.

## Development

```bash
# Install dependencies from monorepo root
npm install --workspaces

# Build
npm run build --workspace @hh/hh-msgs-svc

# Start in watch mode
npm run dev --workspace @hh/hh-msgs-svc

# Run tests
npm run test --workspace @hh/hh-msgs-svc
```

Create a `.env` by copying `.env.example` and adjust configuration for Cloud SQL, Redis, and caching thresholds.

## Configuration Highlights

| Variable | Description |
| --- | --- |
| `PORT` | Fastify listen port (defaults to `8080`). |
| `MSGS_DB_HOST`, `MSGS_DB_USER`, `MSGS_DB_PASS`, `MSGS_DB_NAME` | Cloud SQL Postgres connection details. |
| `MSGS_REDIS_URL` | Redis connection string (supports `rediss://`). |
| `MSGS_CACHE_TTL_SKILLS` | TTL for skill expansion cache entries. |
| `MSGS_CACHE_TTL_ROLES` | TTL for role template cache entries. |
| `MSGS_CACHE_TTL_DEMAND` | TTL for demand analytics cache entries. |
| `MSGS_PMI_MIN_SCORE` | Minimum PMI score before a skill relation is returned. |
| `MSGS_EMA_SPAN` | Default EMA span used for demand calculations. |
| `MSGS_USE_SEED_DATA` | Set to `true` to serve responses from bundled seed data. |

Consult `docs/MSGS_SERVICE_OPERATIONS.md` for operational procedures and `scripts/deploy_msgs_service.sh` for deployment automation.

## Deployment

The Dockerfile targets Node.js 20 on Cloud Run with non-root execution, health checks, and connection pooling to Cloud SQL. Use the provided deployment script to build, push, and roll out the service. Ensure the service account has access to Cloud SQL, Redis, Secret Manager, and Firestore for tenant validation.
