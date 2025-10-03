# Production Monitoring Setup Guide

**Date**: October 3, 2025
**Status**: Ready to Deploy
**Project**: headhunter-ai-0088

---

## Overview

This guide provides step-by-step instructions to set up comprehensive production monitoring for the Headhunter platform using Google Cloud Monitoring.

---

## Prerequisites

### 1. Notification Channels

Create notification channels before running monitoring setup:

```bash
# Create email notification channel
gcloud alpha monitoring channels create \
  --display-name="Production Alerts" \
  --type=email \
  --channel-labels=email_address=ops@yourcompany.com \
  --project=headhunter-ai-0088

# Create Slack notification channel (requires webhook URL)
gcloud alpha monitoring channels create \
  --display-name="Slack #production-alerts" \
  --type=slack \
  --channel-labels=url=https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
  --project=headhunter-ai-0088

# List channels to get IDs
gcloud alpha monitoring channels list --project=headhunter-ai-0088
```

Save the channel IDs for use in setup commands.

---

## Quick Start

### Run Complete Monitoring Setup

```bash
# Full setup with all components
./scripts/setup-monitoring-and-alerting.sh \
  --project-id headhunter-ai-0088 \
  --environment production \
  --region us-central1 \
  --notification-channels "CHANNEL_ID_1,CHANNEL_ID_2"
```

This script will:
1. Create Cloud Monitoring dashboards
2. Set up alert policies
3. Configure uptime checks
4. Enable cost tracking
5. Generate setup manifest

---

## Detailed Setup Steps

### Step 1: Create Dashboards

```bash
# Option 1: Use automated script
python3 scripts/setup_cloud_monitoring_dashboards.py \
  --project-id headhunter-ai-0088 \
  --environment production

# Option 2: Deploy complete monitoring stack
./scripts/deploy_complete_monitoring.sh \
  --project-id headhunter-ai-0088
```

**Dashboards Created**:
- **Service Health Dashboard**: Overall system health metrics
- **Performance Dashboard**: Latency, throughput, error rates
- **Resource Usage Dashboard**: CPU, memory, network
- **Cost Dashboard**: Service costs and budgets
- **Gateway Dashboard**: API Gateway metrics

### Step 2: Configure Alert Policies

```bash
# Set up production alerting
python3 scripts/setup_production_alerting.py \
  --project-id headhunter-ai-0088 \
  --notification-channels "CHANNEL_ID_1,CHANNEL_ID_2"
```

**Alert Policies**:

| Alert | Condition | Threshold | Severity |
|-------|-----------|-----------|----------|
| High Error Rate | error_rate > 1% | 5 min window | CRITICAL |
| High Latency | p95 > 1.2s | 5 min window | WARNING |
| Service Down | uptime < 99% | 10 min window | CRITICAL |
| Low Cache Hit Rate | cache_hit_rate < 0.98 | 10 min window | WARNING |
| Database Connections | connections > 80% | 5 min window | WARNING |
| Memory Usage | memory > 90% | 5 min window | WARNING |
| CPU Usage | cpu > 85% | 5 min window | WARNING |

### Step 3: Set Up Uptime Checks

```bash
# Create uptime checks for critical endpoints
gcloud monitoring uptime create headhunter-gateway-health \
  --resource-type=uptime-url \
  --host=headhunter-api-gateway-production-d735p8t6.uc.gateway.dev \
  --path=/health \
  --check-interval=60s \
  --timeout=10s \
  --project=headhunter-ai-0088
```

**Uptime Checks**:
- API Gateway `/health` - Every 60 seconds
- All 8 service health endpoints (via gateway) - Every 60 seconds

### Step 4: Enable SLO Tracking

```bash
# Run SLO monitoring setup
python3 scripts/production_sla_monitoring.py \
  --project-id headhunter-ai-0088 \
  --enable-slos
```

**SLO Targets**:
- **Availability**: 99.9% (43.2 min downtime/month)
- **Latency (p95)**: < 1.2 seconds
- **Error Rate**: < 1%
- **Cache Hit Rate**: > 98%

---

## Monitoring Architecture

### Metrics Collection

```
Cloud Run Services → Cloud Monitoring → Dashboards
                 ↓
              Alert Policies → Notification Channels
                 ↓
              SLO Tracking → Error Budget
```

### Key Metrics by Service

#### hh-embed-svc
- `request_count`: Total requests processed
- `request_latency`: Processing time (p50, p95, p99)
- `embedding_errors`: Failed embedding generations
- `together_ai_calls`: External API calls
- `db_connection_pool`: Active/idle connections

#### hh-search-svc
- `search_request_count`: Search queries processed
- `search_latency`: Query response time
- `pgvector_query_time`: Vector search time
- `cache_hit_rate`: Redis cache effectiveness
- `recall_count`: Results returned per query

#### hh-rerank-svc
- `rerank_request_count`: Rerank operations
- `rerank_latency`: Reranking time (target: <5ms)
- `cache_hit_rate`: Score cache hits (target: 100%)
- `redis_operations`: Cache read/write operations

#### hh-evidence-svc, hh-eco-svc, hh-msgs-svc, hh-admin-svc, hh-enrich-svc
- Standard metrics: request count, latency, error rate
- Service-specific metrics as exposed by each service

---

## Dashboard Access

### Cloud Console

```
https://console.cloud.google.com/monitoring/dashboards?project=headhunter-ai-0088
```

### CLI Access

```bash
# List all dashboards
gcloud monitoring dashboards list --project=headhunter-ai-0088

# View specific dashboard
gcloud monitoring dashboards describe DASHBOARD_ID --project=headhunter-ai-0088
```

---

## Alert Management

### View Active Alerts

```bash
# List all incidents
gcloud alpha monitoring policies list-incidents --project=headhunter-ai-0088

# Check policy status
gcloud alpha monitoring policies list --project=headhunter-ai-0088
```

### Test Alerts

```bash
# Trigger test alert
gcloud alpha monitoring policies test TEST_POLICY_ID --project=headhunter-ai-0088
```

### Silence Alerts (Maintenance Windows)

```bash
# Create maintenance window
gcloud alpha monitoring snoozes create \
  --display-name="Scheduled Maintenance" \
  --start-time=2025-10-10T00:00:00Z \
  --end-time=2025-10-10T04:00:00Z \
  --criteria="policy_id=POLICY_ID" \
  --project=headhunter-ai-0088
```

---

## Cost Tracking

### Enable Budget Alerts

```bash
# Create budget with alerts at 50%, 80%, 100%
gcloud billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="Headhunter Production Budget" \
  --budget-amount=1000USD \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=80 \
  --threshold-rule=percent=100
```

### Cost Attribution

Tag resources for cost tracking:

```bash
# Tag Cloud Run services
gcloud run services update SERVICE_NAME \
  --labels=project=headhunter,environment=production,cost-center=engineering \
  --region=us-central1 \
  --project=headhunter-ai-0088
```

---

## Performance Monitoring

### Custom Metrics

Services expose metrics at `/metrics` endpoints (Prometheus format):

```bash
# View service metrics
curl https://hh-admin-svc-production-akcoqbr7sa-uc.a.run.app/metrics \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

### Log-Based Metrics

Create metrics from application logs:

```bash
# Example: Track specific error patterns
gcloud logging metrics create error_type_database_timeout \
  --description="Database timeout errors" \
  --log-filter='resource.type="cloud_run_revision"
    severity="ERROR"
    jsonPayload.error=~"timeout.*database"' \
  --project=headhunter-ai-0088
```

---

## Troubleshooting

### No Metrics Appearing

1. **Check service health**:
   ```bash
   gcloud run services describe SERVICE_NAME \
     --region=us-central1 \
     --project=headhunter-ai-0088 | grep "URL\|Status"
   ```

2. **Verify Monitoring API enabled**:
   ```bash
   gcloud services list --enabled --project=headhunter-ai-0088 | grep monitoring
   ```

3. **Check IAM permissions**:
   ```bash
   gcloud projects get-iam-policy headhunter-ai-0088 \
     --flatten="bindings[].members" \
     --filter="bindings.role:roles/monitoring.metricWriter"
   ```

### Alerts Not Firing

1. **Test notification channels**:
   ```bash
   gcloud alpha monitoring channels verify CHANNEL_ID --project=headhunter-ai-0088
   ```

2. **Check alert policy conditions**:
   ```bash
   gcloud alpha monitoring policies describe POLICY_ID --project=headhunter-ai-0088
   ```

3. **View policy evaluation log**:
   ```
   Cloud Console → Monitoring → Alerting → Policy → Activity Log
   ```

---

## Production Readiness Checklist

- [ ] **Notification Channels Created**
  - [ ] Email channel configured
  - [ ] Slack/PagerDuty integration (optional)
  - [ ] Channels verified and tested

- [ ] **Dashboards Deployed**
  - [ ] Service Health Dashboard
  - [ ] Performance Dashboard
  - [ ] Resource Usage Dashboard
  - [ ] Cost Dashboard
  - [ ] Gateway Dashboard

- [ ] **Alert Policies Configured**
  - [ ] Error rate alerts
  - [ ] Latency alerts
  - [ ] Availability alerts
  - [ ] Resource usage alerts
  - [ ] Cost budget alerts

- [ ] **Uptime Checks Active**
  - [ ] Gateway health check
  - [ ] Critical service health checks
  - [ ] Check intervals configured (60s)

- [ ] **SLO Tracking Enabled**
  - [ ] Availability SLO (99.9%)
  - [ ] Latency SLO (p95 < 1.2s)
  - [ ] Error rate SLO (< 1%)
  - [ ] Error budget tracking

- [ ] **Cost Management**
  - [ ] Budget created and alerts configured
  - [ ] Resource labels applied
  - [ ] Cost attribution enabled

- [ ] **Documentation**
  - [ ] Runbook updated with monitoring procedures
  - [ ] On-call escalation paths defined
  - [ ] Incident response playbooks created

---

## Next Steps

### Immediate (Before Production Traffic)

1. Create notification channels
2. Run `./scripts/setup-monitoring-and-alerting.sh`
3. Verify dashboards are populated
4. Test alert firing with simulated incidents
5. Document on-call procedures

### Short-term (First Week)

1. Tune alert thresholds based on actual traffic
2. Set up log-based metrics for application-specific errors
3. Create service-specific dashboards
4. Implement automated incident response

### Long-term (First Month)

1. Establish SLO review cadence
2. Implement error budget policies
3. Set up predictive scaling alerts
4. Create performance regression tests

---

## Related Documentation

- `docs/MONITORING_RUNBOOK.md` - Incident response procedures
- `docs/HANDOVER.md` - Operator handbook
- `AUDIT_REPORT.md` - Security and performance audit
- `CURRENT_STATUS.md` - System status and health

---

## Support

For monitoring setup assistance:
- Google Cloud Monitoring Docs: https://cloud.google.com/monitoring/docs
- Alerting Best Practices: https://cloud.google.com/monitoring/alerts/best-practices
- SLO Best Practices: https://cloud.google.com/blog/products/devops-sre/sre-fundamentals-sli-vs-slo-vs-sla

---

**Created**: October 3, 2025
**Last Updated**: October 3, 2025
**Owner**: DevOps Team
