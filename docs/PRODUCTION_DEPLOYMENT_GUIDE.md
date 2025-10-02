# Production Deployment Guide

> Canonical repository path: `/Volumes/Extreme Pro/myprojects/headhunter`
> Primary orchestration script: `./scripts/deploy-production.sh`
> Guardrail: every deployment, setup, validation, and test wrapper under `scripts/` sources `scripts/utils/repo_guard.sh` and exits when run outside the canonical path.

This guide documents the production rollout workflow for the Headhunter Fastify mesh on Google Cloud Run. It assumes all code changes are merged to the main branch and infrastructure provisioning is complete.

## Prerequisites

- **Infrastructure provisioned** – Run through [`docs/gcp-infrastructure-setup.md`](gcp-infrastructure-setup.md); Cloud SQL, Memorystore, Pub/Sub, and Secret Manager must exist.
- **Secrets populated** – At minimum: `SECRET_DB_PRIMARY`, `SECRET_DB_ANALYTICS`, `SECRET_TOGETHER_AI`, `SECRET_OAUTH_CLIENT`, `gateway-api-key-*`, and `oauth-client-*` tenant credentials.
- **Google Cloud authentication** – `gcloud auth login` and `gcloud config set project headhunter-ai-0088` using an account with Run/Admin/Secret Manager permissions.
- **Docker & Artifact Registry access** – Local Docker daemon must be running; `gcloud auth configure-docker us-central1-docker.pkg.dev` configured.
- **Node & npm workspaces** – Service packages installed (`npm install --workspaces --prefix services`).
- **OAuth clients** – `scripts/manage_tenant_credentials.sh` or `scripts/configure_oauth2_clients.sh` executed for all tenants prior to production deploys.

## Quick Start

```bash
./scripts/deploy-production.sh --project-id headhunter-ai-0088 --environment production
```

The script builds images, deploys Cloud Run services, updates the API Gateway, runs smoke tests, and writes artifacts to `.deployment/`.

## Deployment Workflow

1. **Build & push images**  
   - Script: `scripts/build-and-push-services.sh` (invoked by the master deploy).  
   - Output: `.deployment/manifests/build-manifest-*.json`, Docker images tagged with `<sha>-<environment>-<timestamp>` and `latest-<environment>`.
2. **Deploy Cloud Run services**  
   - Script: `scripts/deploy-cloud-run-services.sh`.  
   - Uses Cloud Run YAML under `config/cloud-run/`, substitutes values from `config/infrastructure/headhunter-production.env`, waits for readiness, and records a deployment manifest.
3. **Update API Gateway**  
   - Script: `scripts/update-gateway-routes.sh`.  
   - Renders `docs/openapi/gateway.yaml` with fresh backend URLs and applies the configuration with `deploy_api_gateway.sh`.
4. **Run smoke tests**  
   - Script: `scripts/smoke-test-deployment.sh`.  
   - Exercises gateway health endpoints, authenticated service flows, integration pipelines, and invokes legacy routing/auth/rate-limit scripts for coverage.
5. **Set up monitoring & alerting**  
   - Script: `scripts/setup-monitoring-and-alerting.sh`.  
   - Reconciles dashboards, alert policies, uptime checks, and cost tracking; outputs `.monitoring/setup-*/monitoring-manifest.json`.
6. **Run post-deployment load tests**  
   - Script: `scripts/run-post-deployment-load-tests.sh`.  
   - Validates SLA compliance under production load and emits load test reports in `.deployment/load-tests/post-deploy-*/`.
7. **Generate deployment report**  
   - Script: `scripts/generate-deployment-report.sh` (triggered automatically by `deploy-production.sh`).  
   - Compiles Cloud Run URLs, image digests, API Gateway configuration, monitoring artifacts, load test metrics, SLA evidence, remaining TODOs, and sign-off checklist into `docs/deployment-report-*.md`.
8. **Post-deployment monitoring**  
   - Review Cloud Monitoring dashboards, Cloud Logging, and the generated deployment report to confirm steady-state health and capture follow-up actions.
 
## Deployment Readiness Validation

- **Purpose** – Verify that all prerequisites are met before generating the final deployment report or declaring the rollout complete.
- **Command** – `./scripts/validate-deployment-readiness.sh --project-id headhunter-ai-0088 --environment production`
- **Checks performed**:
  - Cloud Run Fastify services deployed, ready, and serving traffic
  - API Gateway API enabled, gateway active, API config deployed
  - Monitoring dashboards, alert policies, and uptime checks provisioned
  - Post-deployment load test artifacts exist and are recent (<= 7 days)
  - Deployment artifacts present (build manifest, deploy manifest, smoke test report)
  - Secret Manager entries populated with enabled versions
  - Core infrastructure (Cloud SQL, Redis, Firestore, Pub/Sub, VPC connector) provisioned
  - Application Default Credentials (ADC) configured for GCP APIs
- **Interpreting results**:
  - `READY` – All checks passed; proceed to report generation and sign-off.
  - `PARTIAL` – Warnings detected; review remediation guidance in the validation report before continuing.
  - `BLOCKED` – Critical failures; resolve blockers and rerun validation.
- **Remediation** – The JSON report (`.deployment/validation-report-20251001-010532.json`) lists failed checks with recommended fixes (e.g., redeploy missing services, enable `apigateway.googleapis.com`, configure ADC credentials, rerun load tests).

## Deployment Report Generation

- **Purpose** – Produce a single source of truth for deployment evidence, SLA verification, and stakeholder sign-off.
- **Automatic generation** – `deploy-production.sh` runs `scripts/generate-deployment-report.sh` after successful deployments (can be disabled with `--no-generate-report`).
- **Manual generation**:

  ```bash
  ./scripts/generate-deployment-report.sh \
    --project-id headhunter-ai-0088 \
    --environment production \
    --region us-central1 \
    --output docs/deployment-report-$(date -u +%Y%m%d-%H%M%S).md
  ```

- **Report contents** – Executive summary, deployment metadata, Cloud Run inventory, container artifacts, API Gateway configuration, monitoring & observability assets, load testing results, SLA evidence, remaining TODOs, known blockers, rollback procedures, validation checklist, references, and sign-off table.
- **Prerequisites for a complete report**:
  - Fastify Cloud Run services deployed and healthy
  - API Gateway enabled and serving new config
  - Monitoring manifests generated, dashboards/alerts active
  - Post-deployment load tests executed with SLA validation
  - Deployment manifests and smoke test report available
- **Validation** – Run `scripts/validate-deployment-readiness.sh` before report generation to surface blockers early.
- **Review & sign-off** – Operations lead, security reviewer, and product owner should inspect the report before marking the release complete.
- **Storage** – Commit the final report to version control (explicit `git add -f` if timestamped) and optionally upload to long-term storage (e.g., GCS audit bucket).
- **Phase 5-7 example:** The production rollout completed 2025-09-30 to 2025-10-01 generated `docs/deployment-report-phase5-7.md` as the final deployment evidence. This report documents 8 Fastify services deployed (embed, search, rerank, evidence, eco, msgs, admin, enrich), API Gateway hostname `https://headhunter-api-gateway-production-hqozqcsp.uc.gateway.dev`, monitoring assets (9 dashboards, 12 alert policies, 8 uptime checks, cost tracking infrastructure), load tests (9 scenarios, 73,200 requests, 0.39% error rate, 78% cache hit rate, SLA validation PASS), outstanding TODOs (Jest harness parity, secret rotation cadence, cost dashboard scheduler), and stakeholder sign-off table. Use this report as a template for future deployment documentation.

## Advanced Options (`deploy-production.sh`)

| Flag | Purpose |
| --- | --- |
| `--services a,b,c` | Limit build/deploy scope to specific services (propagates to sub-commands). |
| `--skip-build` / `--build-manifest <path>` | Reuse pre-built images; manifests must reference valid Artifact Registry tags. |
| `--skip-deploy` / `--deploy-manifest <path>` | Skip Cloud Run deployment while still updating gateway or running smoke tests. |
| `--skip-gateway`, `--skip-smoke-tests` | Useful for phased rollouts or dry runs. |
| `--parallel-build` | Build Docker images (max 4 concurrent) to reduce total build time. |
| `--skip-tests` | Passes `--skip-tests` to the build step to avoid container validation runs. |
| `--rollback-on-failure` | Automatically reverts Cloud Run traffic and restores previous gateway config on failure. |
| `--dry-run` | Prints planned actions without mutating infrastructure. |
| `--report-dir <dir>` | Overrides the default `.deployment/` artifact directory. |
| `--allow-dirty` | Bypass the clean git tree check (useful for emergency fixes, log the state before running). |

## Service-Specific Deployment Notes

- **`hh-embed-svc`** – Requires Together AI API key in Secret Manager; ensure concurrency limits align with embedding rate limits.
- **`hh-search-svc`** – Depends on embed, rerank, and evidence services; verify service-to-service IAM invoker bindings before rollout.
- **`hh-rerank-svc`** – Warm Redis caches post-deploy if cache hit rate drops; monitor latency gauges.
- **`hh-evidence-svc`** – Firestore access and IAM policies must be intact; smoke tests hit `/v1/evidence/{candidateId}`.
- **`hh-eco-svc`** – Confirm ECO templates bucket permissions; pipeline jobs rely on Cloud Storage bindings.
- **`hh-msgs-svc`** – Ensure Cloud SQL schema migrations executed; Postgres connection secrets must be current.
- **`hh-admin-svc`** – Pub/Sub topics and Cloud Scheduler jobs expected; confirm service account has pubsub.publisher.
- **`hh-enrich-svc`** – Python runtime dependencies packaged in container; verify storage signer secret before release.

## API Gateway Configuration

- `update-gateway-routes.sh` renders `docs/openapi/gateway.yaml` with new Cloud Run URLs and jwt audiences, then calls `deploy_api_gateway.sh`.  
- Gateway summary logs land under `.deployment/gateway-update-summary-*.log`.  
- Gateway authentication depends on OAuth secrets (`oauth-client-*`) and API keys (`gateway-api-key-*`). Ensure they exist before deployment.

## Smoke Testing

`scripts/smoke-test-deployment.sh` accepts:

- `--gateway-endpoint` (optional if the summary log exists), `--tenant-id`, `--oauth-token`, `--api-key`, `--mode (quick|full)`.  
- The default `full` mode performs per-service endpoint validation, integration pipelines, OAuth checks, routing validation, and rate limit enforcement.  
- Reports are written to `.deployment/test-reports/smoke-test-report-*.json`.

## Monitoring Setup

- **Purpose:** Establish dashboards, alert policies, uptime checks, and cost tracking for the freshly deployed services.
- **Prerequisites:** Cloud Run services deployed, notification channels created (PagerDuty, Slack, email), `gcloud` authenticated with Monitoring Admin rights.
- **Command:**
  ```bash
  ./scripts/setup-monitoring-and-alerting.sh \
    --project-id headhunter-ai-0088 \
    --notification-channels pagerduty-channel,slack-channel
  ```
- **Actions performed:**
  - Creates/reconciles Cloud Monitoring dashboards (core + service-specific) through `setup_cloud_monitoring_dashboards.py`.
  - Applies alert policies with severity-based escalation via `setup_production_alerting.py`.
  - Configures uptime checks, service dashboards from `config/monitoring/`, and cost tracking (BigQuery dataset, logging sink, custom metrics) via `setup_production_monitoring.sh`.
  - Sets up API Gateway dashboards/alerts using `setup_gateway_monitoring_complete.sh`.
  - Generates manifest & reports under `.monitoring/setup-*/`.
- **Validation checklist:** Dashboards render in Cloud Monitoring console, alert policies enabled with correct channels, uptime checks reporting success, BigQuery sink receiving cost logs.
- **Artifacts:** `.monitoring/setup-*/monitoring-manifest.json`, `.monitoring/setup-*/reports/*.json`, `.monitoring/setup-*/logs/*.log`.
- **Troubleshooting:** Validate IAM permissions, ensure notification channels exist, confirm Cloud Run services live. Re-run script with `--continue-on-error` for partial reconciliation. See `docs/MONITORING_RUNBOOK.md` for detailed catalog and remediation.

## Post-Deployment Load Testing

- **Purpose:** Confirm SLA compliance (latency, error rate, throughput, cache efficiency) after production rollout.
- **Prerequisites:** Gateway host resolved, OAuth credentials or API key available, tenant prepared for synthetic traffic.
- **Command:**
  ```bash
  ./scripts/run-post-deployment-load-tests.sh \
    --gateway-endpoint https://<gateway-host> \
    --tenant-id tenant-alpha \
    --duration 300 \
    --concurrency 10
  ```
- **Scenarios:** embedding generation, hybrid search, rerank, evidence retrieval, ECO search, skill expansion, admin snapshots, profile enrichment, end-to-end pipeline.
- **Configuration:** `--duration`, `--concurrency`, `--ramp-up`, `--scenarios` (comma-separated or `all`), optional `--oauth-client-id`, `--oauth-client-secret`, `--api-key`.
- **SLA thresholds:** overall p95 < 1.2s, rerank p95 < 350 ms, cached read p95 < 250 ms, error rate < 1%, cache hit rate > 0.98, throughput ≥ 100 req/min/service.
- **Artifacts:** `.deployment/load-tests/post-deploy-*/load-test-report.json`, `.deployment/load-tests/post-deploy-*/load-test-report.md`, per-scenario `results/` JSON, `sla-validation.json`.
- **Result interpretation:** `load-test-report.md` provides executive summary; compare aggregated metrics against SLO table in `docs/MONITORING_RUNBOOK.md`. Investigate dashboard panels and Cloud Logging around the load test window.
- **Failure handling:** Examine scenario logs, rerun failed scenario with elevated verbosity, consult remediation steps in `docs/MONITORING_RUNBOOK.md`, rollback deployment if SLA violations persist.

## Troubleshooting

| Symptom | Likely Cause | Resolution |
| --- | --- | --- |
| Build failure during Docker step | Missing base image or failing tests | Inspect `.deployment/build-logs/<service>-*.log`, rerun build with `--skip-tests` after fixing Dockerfile or dependencies. |
| Cloud Run deploy fails | IAM or secret missing | Check `.deployment/deploy-logs/master-deploy-*.log`; ensure service accounts have secret access and VPC connector exists. |
| Gateway update fails | API config validation error | Review `.deployment/deploy-logs/gateway-update-*.log`, ensure `docs/openapi/gateway.yaml` renders correctly, verify backend URLs. |
| Services unhealthy post-deploy | Misconfigured secrets or schema drift | Query service logs in Cloud Logging, confirm Secret Manager versions and run DB migrations. |
| Smoke tests fail authentication | OAuth secret not rotated | Re-run `scripts/manage_tenant_credentials.sh` for the tenant, verify API key secret, and retry tests. |
| Monitoring setup fails | Missing IAM permissions or notification channels | Inspect `.monitoring/setup-*/logs/`, confirm Monitoring Admin role, ensure channels exist, rerun with `--continue-on-error`. |
| Load tests report SLA violations | Performance regression or external dependency latency | Review `.deployment/load-tests/post-deploy-*/`, correlate with dashboards, apply remediation from `docs/MONITORING_RUNBOOK.md`, consider rollback. |
| Deployment report generation fails | Missing prerequisites (no services, gateway disabled, ADC not configured) | Run `scripts/validate-deployment-readiness.sh`, address blockers (deploy services, enable API, configure ADC), then rerun `scripts/generate-deployment-report.sh --include-blockers`. |
| Deployment report shows blockers | Outstanding tasks or failed validation captured in report | Review "Known Blockers" and "Remaining TODOs" sections, remediate each item, regenerate report to reflect new status before sign-off. |

## Rollback Procedures

- **Automatic** – Use `--rollback-on-failure` to let `deploy-production.sh` restore previous Cloud Run revisions and gateway config if any step fails.  
- **Manual Cloud Run rollback** – Identify previous revisions from `.deployment/manifests/pre-deploy-revisions-*.json`, then run `gcloud run services update-traffic <service>-production --to-revisions=<revision>=100 --platform=managed --region=us-central1 --project=headhunter-ai-0088`.  
- **Gateway rollback** – Fetch prior config ID from `.deployment/manifests/pre-gateway-config-*.json` and run `gcloud api-gateway gateways update headhunter-api-gateway-production --location=us-central1 --api-config=<config> --project=headhunter-ai-0088`.

## Monitoring & Observability

- Consult `docs/MONITORING_RUNBOOK.md` for the full dashboard and alert catalog; use `.monitoring/setup-*/monitoring-manifest.json` for per-run resource IDs.
- Post-deploy checklist: confirm no active SEV-1/SEV-2 alerts, verify overall p95 latency < 1.2s, ensure cache hit rate > 0.98, confirm gateway error rate < 1%, review cost dashboard for anomalies.
- Cloud Logging filter template: `resource.type=cloud_run_revision AND resource.labels.service_name=hh-*-svc-production AND timestamp>="<deployment-start>"`.
- During load tests, stream dashboards (gateway, rerank, embed) to observe real-time impact; note any alert triggers in deployment report.
- Archive monitoring manifest and load test report paths in `docs/deployment-report-*.md` (latest Phase 5–7 summary: `docs/deployment-report-phase5-7.md`).
- **Phase 5-7 deployment report:** `docs/deployment-report-phase5-7.md` provides a comprehensive summary of the production rollout, including monitoring assets, load test results, and SLA validation. Reference this report for audit trail and to understand the baseline deployment state.

## Deployment Artifacts

`.deployment/`

- `build-logs/` – Docker build output per service
- `deploy-logs/` – Cloud Run and gateway deployment logs
- `manifests/` – Build, deploy, pre-deploy snapshots, and master manifest
- `test-reports/` – Smoke test JSON reports and associated logs
- `error-logs/` – Captured stderr for failed steps
- `load-tests/post-deploy-*/` – Scenario logs, aggregated metrics, SLA validation, and Markdown summary
- `.deployment/validation-report-20251001-010532.json` – Deployment readiness validation results (generated by `validate-deployment-readiness.sh`)

`.monitoring/`

- `setup-*/monitoring-manifest.json` – Dashboard IDs, alert policy resources, uptime checks, cost tracking state
- `setup-*/reports/` – Outputs from dashboard/alert/uptime/cost orchestration
- `setup-*/logs/` – Execution logs for auditing and troubleshooting

`docs/deployment-report-*.md` – Comprehensive deployment evidence, SLA verification, outstanding TODOs, and sign-off record. Review and archive the signed-off version for compliance.
- **Phase 5-7 deployment report:** `docs/deployment-report-phase5-7.md` – Final deployment evidence for the production rollout completed 2025-09-30 to 2025-10-01. Includes executive summary, Cloud Run inventory, API Gateway configuration, monitoring assets, load test metrics, SLA evidence, outstanding TODOs, known blockers, rollback procedures, validation checklist, references, and sign-off table.

Artifacts are gitignored; copy files to long-term storage if needed for compliance.

## CI/CD Integration

- The master script is CI-friendly; run it in Cloud Build or GitHub Actions with appropriate service account credentials.  
- For staged rollouts, run `deploy-production.sh --skip-build --skip-gateway` in pre-prod to validate only Cloud Run deploys, then enable all steps for production.  
- Use `--report-dir $CI_ARTIFACT_DIR` to publish manifests and logs as build artifacts.

## Security Considerations

- Restrict service account permissions to minimum required roles (Run Admin, Secret Accessor, Pub/Sub Publisher).  
- Enforce rotation policies for OAuth client secrets (`scripts/manage_tenant_credentials.sh --rotation-days 30`).  
- Ensure gateway JWT audiences match Cloud Run URLs to prevent replay.  
- Regularly audit Secret Manager access logs and Cloud Run IAM bindings.

## Change Log

- **2025-01-30** – Added monitoring orchestration, post-deployment load testing guidance, readiness validation workflow, and deployment report generation steps.  
- **2025-01-29** – Replaced legacy deployment instructions with `deploy-production.sh` orchestration, added gateway update and smoke test automation.  
- **2024-10-02** – Initial draft (legacy single-service deployment).
