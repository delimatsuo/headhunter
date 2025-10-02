# Monitoring & Alerting Runbook (Updated 2025-01-30)

> Canonical repository path: `/Volumes/Extreme Pro/myprojects/headhunter`
> Purpose: Consolidated operational guide covering Cloud Monitoring dashboards, alert policies, SLO targets, remediation procedures, and validation workflows for the Headhunter production stack.

## Overview

The Headhunter production mesh relies on Google Cloud Monitoring for unified observability. The monitoring footprint includes:

- Cloud Monitoring dashboards dedicated to Cloud Run services, managed data stores, and external dependencies (Together AI, Embeddings, Pub/Sub, API Gateway).
- Severity-based alert policies (SEV-1 to SEV-3) with notification channels spanning PagerDuty, Slack, and email.
- Uptime checks for all eight Fastify services deployed on Cloud Run (`hh-*-svc-production`).
- Cost tracking via Logging sinks, BigQuery datasets, and custom metrics for anomaly detection.
- SLO coverage for latency, availability, error rate, cache efficiency, throughput, and data quality.

## Dashboard Catalog

| Dashboard | Purpose | URL | Key Metrics | Review Cadence |
| --- | --- | --- | --- | --- |
| Headhunter Production Cloud Run – Worker Performance | End-to-end Cloud Run health for all worker services | https://console.cloud.google.com/monitoring/dashboards/custom/worker-performance?project=headhunter-ai-0088 | Request latency, error rate, concurrency, instance utilization | Daily; also after deployments |
| Headhunter Production Cloud SQL – pgvector | Postgres workload visibility | https://console.cloud.google.com/monitoring/dashboards/custom/pgvector-performance?project=headhunter-ai-0088 | Connections, CPU, query latency, WAL throughput | Weekly and when latency alerts trigger |
| Headhunter Production Firebase Functions (Gen2) | Residual serverless functions health | https://console.cloud.google.com/monitoring/dashboards/custom/firebase-functions?project=headhunter-ai-0088 | Invocation latency, error %, cold starts | Weekly |
| Headhunter Production Pub/Sub Pipeline | Messaging throughput and backlog monitoring | https://console.cloud.google.com/monitoring/dashboards/custom/pubsub-pipeline?project=headhunter-ai-0088 | Backlog depth, ack latency, dead letter counts | During incident triage and cost spikes |
| Headhunter Production External APIs (Together AI, Embeddings) | Third-party dependency health | https://console.cloud.google.com/monitoring/dashboards/custom/external-apis?project=headhunter-ai-0088 | Success rate, latency, quota usage | Daily quick check; during LLM outages |
| Headhunter API Gateway Overview (production) | Gateway traffic, latency, auth failures | https://console.cloud.google.com/monitoring/dashboards/custom/api-gateway-production?project=headhunter-ai-0088 | P95 latency, error ratio, request volume, auth failures | After deployments and when alerts fire |
| hh-admin-svc Production Dashboard | Admin service deep-dive | https://console.cloud.google.com/monitoring/dashboards/custom/hh-admin-svc?project=headhunter-ai-0088 | Scheduler invocations, request latency, error rate | Weekly |
| hh-embed-svc Production Dashboard | Embedding service health | https://console.cloud.google.com/monitoring/dashboards/custom/hh-embed-svc?project=headhunter-ai-0088 | Batch latency, Together AI response time, queue depths | Daily |
| hh-enrich-svc Production Dashboard | Enrichment pipelines | https://console.cloud.google.com/monitoring/dashboards/custom/hh-enrich-svc?project=headhunter-ai-0088 | Worker backlog, job duration, error counts | During incident triage |
| hh-evidence-svc Production Dashboard | Evidence API health | https://console.cloud.google.com/monitoring/dashboards/custom/hh-evidence-svc?project=headhunter-ai-0088 | Response latency, Firestore read/write volume | Daily |
| hh-eco-svc Production Dashboard | ECO search & templates | https://console.cloud.google.com/monitoring/dashboards/custom/hh-eco-svc?project=headhunter-ai-0088 | Search latency, cache hit rate, template errors | Weekly |
| hh-msgs-svc Production Dashboard | Notification workloads | https://console.cloud.google.com/monitoring/dashboards/custom/hh-msgs-svc?project=headhunter-ai-0088 | Queue depth, delivery latency, Pub/Sub errors | Daily |
| hh-rerank-svc Production Dashboard | Rerank latency & cache metrics | https://console.cloud.google.com/monitoring/dashboards/custom/hh-rerank-svc?project=headhunter-ai-0088 | Cache hit rate, latency histogram, Redis utilization | At least daily and after deployments |
| hh-search-svc Production Dashboard | Search orchestration health | https://console.cloud.google.com/monitoring/dashboards/custom/hh-search-svc?project=headhunter-ai-0088 | Latency, error %, upstream failures | Daily |
| hh-embed-svc Cost Tracking Dashboard | Service-specific cost signals | https://console.cloud.google.com/monitoring/dashboards/custom/cost-tracking?project=headhunter-ai-0088 | Daily spend, anomaly score, API cost per tenant | Weekly finance sync |

> Dashboard IDs are generated during orchestration. Update the URLs above with actual IDs from `.monitoring/setup-*/monitoring-manifest.json` after each run.

## Alert Policy Catalog

| Policy | Severity | Condition | Notification Channels | Remediation |
| --- | --- | --- | --- | --- |
| Cloud Run p95 Latency > 1.2s | SEV-2 | `latency_p95 > 1200ms for 10m` | PagerDuty: `headhunter-prod`, Slack: `#headhunter-ops` | Scale Cloud Run instances, check Redis/SQL contention, warm caches |
| Cloud Run Error Rate > 5% | SEV-2 | `5xx_ratio > 5% for 5m` | PagerDuty, Slack | Inspect Cloud Logging, review recent deploy, verify secrets |
| DB Connections High | SEV-3 | `connections_used / max_connections > 0.8 for 10m` | Slack | Review connection pool, investigate leaks, scale Cloud SQL |
| Pub/Sub Backlog High | SEV-2 | `subscription_backlog > 5k for 5m` | PagerDuty, Slack | Increase subscriber concurrency, check dead letters |
| Together AI Error Surge | SEV-3 | `error_rate > 2%` | Slack, email build pipeline | Confirm vendor status page, implement retries, consider fallback |
| Uptime Check Failure | SEV-1 | Uptime check fails 3 consecutive probes | PagerDuty (page immediately) | Verify service health, restore last good revision, escalate to incident commander |
| Data Quality Failure | SEV-2 | `custom_metric:data_quality_failures > 0` | Slack, email analytics | Inspect data quality pipeline logs, revert offending data load |
| Gateway Latency SLA | SEV-2 | `gateway_p95 > 1200ms for 5m` | PagerDuty, Slack | Check rerank latency, review embedding queue, validate external API |
| Gateway Rerank Latency | SEV-2 | `gateway_rerank_p95 > 350ms for 5m` | Slack | Validate cache warming, inspect Redis hit rate |
| Gateway Error Volume | SEV-2 | `gateway_5xx > 1%` | PagerDuty, Slack | Inspect failed routes, confirm OAuth/keys, check upstream services |

Severity definitions: **SEV-1** pages on-call immediately, **SEV-2** requires response within 15 minutes, **SEV-3** should be acknowledged within business hours.

## SLO Targets

| SLO | Target | Measurement | Baseline | Alert Threshold | Remediation |
| --- | --- | --- | --- | --- | --- |
| Availability | 99.9% uptime | Cloud Run uptime checks | 99.95% | Alert at < 99.7% rolling 30d | Investigate uptime failure runbook |
| Overall Latency | p95 < 1.2s | Gateway request latency (P95) | 820ms | Alert at 1.2s for 10m | Scale Cloud Run, flush cache, inspect Together AI |
| Rerank Latency | p95 < 350ms | `hh-rerank-svc` latency histogram | 140ms | Alert at 350ms for 10m | Warm caches, inspect Redis saturation |
| Error Rate | < 1% 5xx | Gateway error ratio | 0.25% | Alert at 1% for 5m | Inspect Cloud Logging, rollback if necessary |
| Cache Hit Rate | > 0.98 | Redis metrics from rerank dashboard | 0.995 | Alert at 0.97 for 10m | Run cache warmers, inspect invalidation |
| Throughput | > 100 req/min/service | Aggregated Cloud Run request rate | 165 req/min | Alert at < 80 req/min if expected load | Scale or investigate upstream blockers |
| Data Quality Failures | < 1/hour | Custom metric `data_quality_failures` | 0 | Alert at 1 event | Pause ingestion, review data pipeline |

## Uptime Checks

- Services monitored: `hh-embed-svc`, `hh-search-svc`, `hh-rerank-svc`, `hh-evidence-svc`, `hh-eco-svc`, `hh-msgs-svc`, `hh-admin-svc`, `hh-enrich-svc` (suffix `-production`).
- Frequency: 60 seconds per service.
- Timeout: 10 seconds.
- Expected response: HTTP 200 with JSON `{"status":"ok"}`.
- Failure response: SEV-1 alert. Reference the uptime remediation steps in the remediation section.

## Cost Tracking

- **Logging sink**: `projects/headhunter-ai-0088/sinks/monitoring-cost-sink` exporting billing logs to BigQuery.
- **BigQuery dataset**: `headhunter_monitoring.cost_reporting`. Tables partitioned by day with per-service and per-tenant cost.
- **Custom metrics**: Daily spend, 7-day moving average, anomaly score (using spike ratio > 1.5).
- **Dashboard**: https://console.cloud.google.com/monitoring/dashboards/custom/cost-tracking?project=headhunter-ai-0088.
- **Investigation workflow**:
  1. Review anomaly chart for the impacted service/tenant.
  2. Run saved BigQuery query `queries/cost-spike-investigation.sql` (see `.monitoring/setup-*/reports/` for generated copy).
  3. Inspect Cloud Logging for retry storms or misconfigured batch jobs.
  4. Coordinate with finance when sustained spikes exceed budget thresholds.

## Remediation Procedures

### High Latency (p95 > 1.2s)
1. Check gateway and service dashboards for affected routes.
2. Inspect Cloud Logging for slow queries or external API slowness.
3. Verify Redis connection pool utilization (`redis_pool_utilization` metric).
4. Inspect Cloud SQL CPU/connection charts; scale instance if required.
5. Validate Together AI latency; failover to alternate model if needed.
6. Run cache warmers (`services/hh-rerank-svc/scripts/warm-cache.sh`).
7. Consider rolling back the latest deployment if regression persists.

### Elevated Error Rate (5xx > 5%)
1. Identify failing endpoints in Cloud Monitoring and logs.
2. Confirm Secret Manager access (Together AI, OAuth, Redis).
3. Check service-to-service IAM permissions.
4. Review retry/backoff configuration to prevent cascading failures.
5. If regression introduced by latest release, rollback using deploy manifest.

### Uptime Check Failure
1. Confirm service revision is healthy: `gcloud run services describe <svc>-production`.
2. Review service logs for crash loops or permission errors.
3. Verify VPC connector and networking configuration.
4. Manually request `/health` and `/ready` endpoints.
5. Restore traffic to previous revision if downtime exceeds 5 minutes.

### Pub/Sub Backlog Growth
1. Inspect subscriber logs for errors or throttling.
2. Check dead letter queue volume.
3. Temporarily scale subscriber concurrency or instance count.
4. Pause upstream publishers if backlog threatens SLA.

### Database Connection Pool Exhaustion
1. Review connection usage in Cloud SQL dashboard.
2. Confirm application pool limits align with DB capacity.
3. Investigate long-running queries; use `pg_stat_activity` snapshots.
4. Restart offending services to clear leaked connections.

### Cache Hit Rate Degradation
1. Inspect rerank dashboard cache hit rate panel.
2. Validate warmup scripts executed post-deploy.
3. Check Redis memory usage and eviction stats.
4. Inspect TTL configuration and key churn.
5. Manually warm caches using `services/hh-rerank-svc/scripts/warm-cache.sh`.

### Cost Spike
1. Review cost dashboard to identify service/tenant.
2. Inspect Together AI usage and queue depth.
3. Confirm no runaway batch jobs or retry loops.
4. Engage service owners and finance if spike persists > 1 hour.

## Monitoring Setup Workflow

Prerequisites: `gcloud` authenticated with monitoring permissions, notification channels created (PagerDuty, Slack webhooks, email groups), Cloud Run services deployed.

```
./scripts/setup-monitoring-and-alerting.sh \
  --project-id headhunter-ai-0088 \
  --notification-channels pagerduty-channel,slack-channel
```

Execution details:

- Creates/reconciles dashboards via `setup_cloud_monitoring_dashboards.py`.
- Applies alert policies with severity mappings and notification channels.
- Configures uptime checks, dashboard imports under `config/monitoring/`, and cost tracking resources via `setup_production_monitoring.sh`.
- Installs API Gateway dashboards/alerts (`setup_gateway_monitoring_complete.sh`).
- Emits manifest: `.monitoring/setup-*/monitoring-manifest.json` containing dashboard IDs, alert resource names, uptime checks, service URL map, validation results, and warnings.

Post-run validation:

1. Confirm dashboards visible in Cloud Monitoring UI.
2. Check alert policies enabled and tied to notification channels.
3. Verify uptime checks passing for all services.
4. Confirm cost sink exporting logs to BigQuery dataset.
5. Archive manifest path in the deployment report.

## Post-Deployment Load Testing

Purpose: Validate SLA adherence under production traffic immediately after deployment.

```
./scripts/run-post-deployment-load-tests.sh \
  --gateway-endpoint https://<gateway-host> \
  --tenant-id tenant-alpha \
  --duration 300 \
  --concurrency 10
```

Scenarios: embedding generation, hybrid search, rerank, evidence retrieval, ECO search, skill expansion, admin snapshot fetch, profile enrichment, end-to-end pipeline.

Expected runtime: 5–10 minutes.

SLA criteria:

- Overall p95 latency < 1.2 seconds
- Rerank p95 latency < 350 ms
- Cached read p95 latency < 250 ms
- Error rate < 1%
- Cache hit rate > 0.98
- Throughput ≥ 100 requests/minute per service

Artifacts:

- `.deployment/load-tests/post-deploy-*/load-test-report.json` – machine-readable summary
- `.deployment/load-tests/post-deploy-*/load-test-report.md` – operator-friendly summary
- `.deployment/load-tests/post-deploy-*/results/` – per-scenario metrics & logs

If load tests fail:

1. Inspect relevant dashboards (gateway, rerank, embed) for anomalies.
2. Review Cloud Logging during test window for errors/timeouts.
3. Execute remediation steps above (latency, cache, error rate).
4. Consider rollback if SLA failures persist after remediation.

## Troubleshooting

| Symptom | Likely Cause | Resolution |
| --- | --- | --- |
| Dashboard missing data | Metric descriptor mismatch or missing labels | Verify metric descriptors, ensure services export labels expected by dashboards, adjust MQL queries. |
| Alert did not fire | Policy disabled or channel not bound | Check policy enablement state, ensure channel IDs valid, run manual incident drill. |
| Uptime check false positives | Health endpoint latency > 10s or auth errors | Increase timeout in `setup_production_monitoring.sh`, verify health endpoint dependencies. |
| Cost metrics absent | Logging sink misconfigured or BigQuery permissions missing | Re-run setup script, confirm service account has `roles/bigquery.dataEditor`, inspect sink errors. |
| Custom metrics missing | Metric descriptor not created or writer lacks permissions | Re-run monitoring setup, verify service account publishes metrics correctly. |

## Operational Procedures

- **Daily**: Review gateway dashboard, check alert console, scan cost dashboard, confirm uptime checks passing.
- **Weekly**: Audit SLO compliance, review Pub/Sub backlog trends, inspect Together AI latency history.
- **Monthly**: Reconcile alert policies & notification channels, adjust thresholds, archive monitoring manifest.
- **Post-deployment**: Run load test script, verify no alerts fired, update deployment report with monitoring manifest and load test paths.
- **Incident response**: Follow severity-specific remediation, document actions in `docs/HANDOVER.md`, update runbook as needed.

## Notification Channels

| Channel | Type | Purpose |
| --- | --- | --- |
| `headhunter-prod` | PagerDuty | Primary on-call escalation for SEV-1/SEV-2 alerts |
| `#headhunter-ops` | Slack | Real-time operations updates and collaboration |
| `ops-alerts@headhunter.ai` | Email | Audit log and management visibility |

Add/edit channels via Cloud Monitoring console or `gcloud monitoring channels` before re-running the setup script.

## References

- `docs/HANDOVER.md` – incident response and deployment runbook
- `docs/PRODUCTION_DEPLOYMENT_GUIDE.md` – production deployment workflow
- `docs/ARCHITECTURE.md` – system architecture overview
- `.monitoring/setup-*/monitoring-manifest.json` – dashboard and alert metadata
- `.deployment/load-tests/post-deploy-*/` – post-deployment load test evidence
- Cloud Monitoring console – https://console.cloud.google.com/monitoring?project=headhunter-ai-0088
- Cloud Logging console – https://console.cloud.google.com/logs/query?project=headhunter-ai-0088

## Change Log

- **2025-01-30** – Initial consolidated monitoring and load testing runbook for Phase 5 orchestration.
