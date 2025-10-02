# hh-admin-svc

The admin service exposes privileged Cloud Run endpoints that orchestrate candidate and posting refresh workflows, monitor downstream data freshness, and provide operational controls for administrators. It authenticates through the shared API Gateway (Firebase ID tokens + OAuth2), validates tenant-scoped IAM roles, and drives refresh orchestration across Pub/Sub topics, Cloud Run Jobs, and Cloud Scheduler.

## Capabilities

1. **Refresh orchestration** – Publishes refresh requests to the `profiles.refresh.request` and `postings.refresh.request` Pub/Sub topics and can optionally execute Cloud Run Jobs (`profiles-refresh-job`, `msgs-refresh-job`) on demand.
2. **Scheduled management** – Surfaces helper endpoints to coordinate recurring refreshes driven by Cloud Scheduler while enforcing IAM policies.
3. **Data freshness monitoring** – Aggregates Firestore and Cloud SQL metrics to produce freshness snapshots, highlighting stale tenants and job status anomalies.
4. **Audit-ready IAM** – Requires elevated admin roles and emits structured audit logs for every invocation, including actor, tenant, and operation metadata.

```
Admin User ──► API Gateway ──► hh-admin-svc ──► Pub/Sub ◄─► Cloud Run Jobs
                                      │
                                      └─► Monitoring APIs ──► Cloud SQL / Firestore
```

## Endpoints

### `POST /v1/admin/refresh-postings`
Triggers a postings refresh by publishing to `postings.refresh.request` and optionally launching the `msgs-refresh-job` Cloud Run Job.

Payload (JSON):
```json
{
  "tenantId": "tenant-123",
  "force": false,
  "schedule": {
    "name": "weekly-posting-refresh",
    "cron": "0 5 * * 1"
  }
}
```

- `tenantId` is required unless the caller holds global admin scope.
- Set `force=true` to bypass concurrency guards.
- Attach the optional `schedule` block to upsert a Cloud Scheduler job.

### `POST /v1/admin/refresh-profiles`
Publishes a profile refresh request to `profiles.refresh.request` with optional job execution using `profiles-refresh-job`.

Payload (JSON):
```json
{
  "tenantId": "tenant-123",
  "sinceIso": "2024-05-01T00:00:00Z",
  "priority": "high"
}
```

- `sinceIso` limits the refresh window for targeted replays.
- `priority` controls Pub/Sub message attributes used by downstream workers.

### `GET /v1/admin/snapshots`
Returns freshness indicators derived from Cloud SQL (`msgs.skill_demand`) and Firestore candidate documents. Example response:
```json
{
  "generatedAt": "2024-06-15T13:05:00Z",
  "postings": {
    "staleTenants": ["tenant-456"],
    "maxLagDays": 11.4,
    "lastIngestedAt": "2024-06-04T08:25:00Z"
  },
  "profiles": {
    "staleTenants": [],
    "maxLagDays": 2.1,
    "lastUpdatedAt": "2024-06-13T21:50:00Z"
  },
  "jobHealth": {
    "recentFailures": 1,
    "successRatio": 0.98,
    "alertState": "ok"
  }
}
```

### `GET /healthz`
Liveness probe that verifies the Fastify process is serving traffic. Returns an `ok` status with uptime information and does not fan out to external dependencies. Cloud Run uses this endpoint for container health checks.

### `GET /readyz`
Readiness probe that executes dependency checks against Pub/Sub, Cloud Run Jobs, and monitoring integrations. When `ADMIN_MONITORING_OPTIONAL_FOR_HEALTH=true`, monitoring failures downgrade readiness to `degraded` rather than failing the probe.

## Authentication & Authorization

All routes use the shared `@hh/common` Fastify plugins:
- Firebase ID token verification.
- X-Tenant-ID propagation and validation.
- Admin IAM validator (defined in `src/iam-validator.ts`) which enforces:
  - `admin.refresh.write` for refresh endpoints.
  - `admin.monitor.read` for snapshot access.
  - Tenant scoping based on custom claims or allow-list overrides.

Structured audit logs are emitted with the `metric=admin.audit` label for compliance.

## Configuration

Configuration is managed through `src/config.ts` and `.env.example`. Key toggles:

- `ADMIN_POSTINGS_TOPIC`, `ADMIN_PROFILES_TOPIC` – Pub/Sub topics.
- `ADMIN_POSTINGS_JOB`, `ADMIN_PROFILES_JOB` – Cloud Run Jobs to invoke.
- `ADMIN_SCHEDULER_TARGET_BASE_URL` – Cloud Run service root (e.g., `https://<service-url>`); scheduler routes append `/v1/admin/*` automatically.
- `ADMIN_PUBSUB_ORDERING_KEY_TEMPLATE` – Template used when `ADMIN_PUBSUB_ORDERING_ENABLED=true` (defaults to `${scope}:${tenantId}`).
- `ADMIN_REFRESH_TIMEOUT_SECONDS` – Timeout for job orchestration.
- `ADMIN_MONITORING_ENABLED` – Enables Cloud Monitoring integration.
- `ADMIN_MONITORING_OPTIONAL_FOR_HEALTH` – Treat monitoring outages as non-fatal for readiness checks.
- `ADMIN_MONITORING_SQL_INSTANCE` – When set, the Cloud SQL Node.js connector establishes the Postgres connection (`ADMIN_MONITORING_SQL_IP_TYPE` controls PUBLIC/PRIVATE/PSC networking).
- `ADMIN_ALERT_THRESHOLD_DAYS` – Staleness trigger for alerts.
- `FIREBASE_PROJECT_ID` – Shared Firebase project.

Refer to `.env.example` for the complete list and default values.

## Local Development

```bash
cd services
npm install --workspaces
npm run dev --workspace @hh/hh-admin-svc
```

Set `GOOGLE_APPLICATION_CREDENTIALS` to a service account with Pub/Sub and Cloud Run Jobs permissions when running locally.

### Running Tests

Tests live in the monorepo under `tests/unit/admin-service.test.ts` and `tests/integration/admin-service.test.ts`.

```bash
npm test -- admin-service
```

### Linting & Type Checking

```bash
npm run lint --workspace @hh/hh-admin-svc
npm run typecheck --workspace @hh/hh-admin-svc
```

## Deployment

Use `scripts/deploy_admin_service.sh` which builds the Docker image, pushes to Artifact Registry, deploys to Cloud Run, and configures IAM bindings. The script also enables required APIs: Cloud Run, Cloud Scheduler, Pub/Sub, and Cloud Monitoring.

### Required Service Accounts

- **Runtime SA** – Publishes to refresh topics and invokes Cloud Run Jobs.
- **Scheduler SA** – Triggers scheduled refreshes via Pub/Sub or direct job runs.
- **Monitoring SA** – Reads metrics from Cloud Monitoring, Cloud SQL, and Firestore (read-only).

## Monitoring & Alerting

Dashboards under `config/monitoring/admin-service-dashboard.json` visualize:
- Posting/profile freshness lag.
- Job execution latency and failure counts.
- Scheduler status and run anomalies.
- IAM-denied attempts.

The dashboard’s custom metrics (e.g., refresh success/failure counts) are emitted by the downstream refresh workers and Cloud Monitoring jobs; hh-admin-svc reports readiness status only.

Alerts in `config/monitoring/data-freshness-alerts.json` cover stale data (>10 days), job failures, and admin misuse.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `permissionDenied` from Pub/Sub | Ensure the runtime service account has the `pubsub.publisher` role on the refresh topics. |
| Cloud Run Job fails immediately | Check the job template environment variables and confirm downstream services are reachable. |
| Snapshots missing data | Verify Cloud SQL and Firestore credentials plus network access. |
| Scheduler fails to create | Confirm the scheduler service account has `roles/cloudscheduler.admin` and relevant Pub/Sub publish permissions. |

## Related Documentation

- `docs/ADMIN_SERVICE_OPERATIONS.md` – Operational runbook and incident response.
- `docs/TDD_PROTOCOL.md` – Testing process.
- `ARCHITECTURE.md` – System overview.
