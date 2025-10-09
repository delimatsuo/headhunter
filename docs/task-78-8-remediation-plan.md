# Task 78.8 Remediation Plan

**Date**: 2025-10-09
**Status**: READY FOR EXECUTION
**Priority**: SEV-1 (Critical - Production Degraded)

## Overview

This document provides step-by-step remediation for the critical issues discovered during Task 78.8 production validation testing. All 8 Fastify services are deployed to Cloud Run, but 6 of 8 are degraded due to infrastructure connectivity failures.

## Critical Issues Summary

1. **Database Authentication Failures** - Password mismatches and missing user
2. **Redis TLS Configuration Missing** - Services cannot connect to Redis
3. **Service Initialization Delays** - May resolve naturally
4. **Undiagnosed ECO Service Error** - Requires investigation

## Prerequisites

- Access to GCP project: `headhunter-ai-0088`
- Permissions: Cloud SQL Admin, Secret Manager Admin, Cloud Run Admin
- Local repository: `/Volumes/Extreme Pro/myprojects/headhunter`

## Remediation Steps

### Phase 1: Database User and Password Fixes

#### Step 1.1: Create Missing Database User (hh_ops)

**Issue**: User `hh_ops` referenced by hh-msgs-svc doesn't exist in Cloud SQL

**Commands**:
```bash
# Get password from Secret Manager
HH_OPS_PASSWORD=$(gcloud secrets versions access latest \
  --secret=db-operations-password \
  --project=headhunter-ai-0088)

# Create user in Cloud SQL
gcloud sql users create hh_ops \
  --instance=sql-hh-core \
  --password="$HH_OPS_PASSWORD" \
  --project=headhunter-ai-0088

# Verify user created
gcloud sql users list \
  --instance=sql-hh-core \
  --project=headhunter-ai-0088 \
  --format="table(name,type)"
```

**Expected Output**: User `hh_ops` appears in the list

#### Step 1.2: Grant Database Permissions to hh_ops

**Commands**:
```bash
# Connect to Cloud SQL via proxy
cloud_sql_proxy headhunter-ai-0088:us-central1:sql-hh-core &
PROXY_PID=$!

# Wait for proxy to start
sleep 3

# Connect and grant permissions
psql "host=localhost port=5432 dbname=headhunter user=postgres" << 'EOF'
-- Grant connection
GRANT CONNECT ON DATABASE headhunter TO hh_ops;

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO hh_ops;

-- Grant table permissions for messaging operations
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO hh_ops;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO hh_ops;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hh_ops;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO hh_ops;

-- Verify grants
\du hh_ops
EOF

# Stop proxy
kill $PROXY_PID
```

**Verification**:
```bash
# Test connection as hh_ops
psql "host=localhost port=5432 dbname=headhunter user=hh_ops password=$HH_OPS_PASSWORD" \
  -c "SELECT current_user, current_database();"
```

#### Step 1.3: Reset Database Passwords for Existing Users

**Issue**: Passwords in Secret Manager may not match Cloud SQL actual passwords

**Commands**:
```bash
# Reset hh_app password
HH_APP_PASSWORD=$(gcloud secrets versions access latest \
  --secret=db-primary-password \
  --project=headhunter-ai-0088)

gcloud sql users set-password hh_app \
  --instance=sql-hh-core \
  --password="$HH_APP_PASSWORD" \
  --project=headhunter-ai-0088

# Reset hh_analytics password
HH_ANALYTICS_PASSWORD=$(gcloud secrets versions access latest \
  --secret=db-analytics-password \
  --project=headhunter-ai-0088)

gcloud sql users set-password hh_analytics \
  --instance=sql-hh-core \
  --password="$HH_ANALYTICS_PASSWORD" \
  --project=headhunter-ai-0088

# Verify password sync
echo "Passwords synchronized for hh_app, hh_analytics, hh_ops"
```

### Phase 2: Redis TLS Configuration

#### Step 2.1: Get Redis TLS Certificate

**Issue**: Redis requires TLS but only hh-search-svc has the configuration

**Command**:
```bash
# Get Redis server CA certificate
gcloud redis instances describe redis-skills-us-central1 \
  --region=us-central1 \
  --project=headhunter-ai-0088 \
  --format="value(serverCaCerts[0].cert)" > /tmp/redis-ca.pem

# Display certificate for verification
cat /tmp/redis-ca.pem
```

**Expected**: PEM-encoded certificate starting with `-----BEGIN CERTIFICATE-----`

#### Step 2.2: Update Service Configuration Files

**Files to Update**:
1. `config/cloud-run/hh-embed-svc.yaml`
2. `config/cloud-run/hh-evidence-svc.yaml`
3. `config/cloud-run/hh-msgs-svc.yaml`
4. `config/cloud-run/hh-eco-svc.yaml`
5. `config/cloud-run/hh-enrich-svc.yaml`
6. `config/cloud-run/hh-admin-svc.yaml`

**Changes Required**: Add these environment variables after `REDIS_PORT`:

```yaml
            - name: REDIS_TLS
              value: "true"
            - name: REDIS_TLS_REJECT_UNAUTHORIZED
              value: "true"
            - name: REDIS_TLS_CA
              value: |-
                -----BEGIN CERTIFICATE-----
                MIID7TCCAtWgAwIBAgIBADANBgkqhkiG9w0BAQsFADCBhTEtMCsGA1UELhMkN2M5
                YjAxNzgtYTQ1NC00YzI0LTg2YjUtZDlhMTVkNGU5OWYzMTEwLwYDVQQDEyhHb29n
                bGUgQ2xvdWQgTWVtb3J5c3RvcmUgUmVkaXMgU2VydmVyIENBMRQwEgYDVQQKEwtH
                b29nbGUsIEluYzELMAkGA1UEBhMCVVMwHhcNMjUwOTMwMjA1ODQ1WhcNMzUwOTI4
                MjA1OTQ1WjCBhTEtMCsGA1UELhMkN2M5YjAxNzgtYTQ1NC00YzI0LTg2YjUtZDlh
                MTVkNGU5OWYzMTEwLwYDVQQDEyhHb29nbGUgQ2xvdWQgTWVtb3J5c3RvcmUgUmVk
                aXMgU2VydmVyIENBMRQwEgYDVQQKEwtHb29nbGUsIEluYzELMAkGA1UEBhMCVVMw
                ggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDHTHxg02qnSRLqlwSzwo3b
                /2nVSzRBn1juRAgjwoU8JsD+Y75nz3VDz+u6MQ24srp75pcyDKDJjfOPYHb2LxZ3
                qJzGj2tITZJixHtmDuYD/v5fq5b/nnlyWc1rcrZcdHe44jTitV5+kcI3M1aHxv7l
                CC4nK5zahHCv5yi0khsacxX3J5ON6BsAPY5LUeoG1JAOqFUum7o4/1ncxyNOity3
                6JADYSemaOc2YZHMaYsnMcByqOWZeKFr9bwRgvt6Q8qYtUWwuukOZ5QtzL91YDtc
                oaowb1xkxsukz6TmaBhuPFgEwaOaJ12AxD8mfF15PQIUKALuMJshOHAdw5BfVMVl
                AgMBAAGjZjBkMB8GA1UdIwQYMBaAFKxMr+7TMSYNachOdWv3/tIpOPEUMBIGA1Ud
                EwEB/wQIMAYBAf8CAQAwDgYDVR0PAQH/BAQDAgEGMB0GA1UdDgQWBBSsTK/u0zEm
                DWnITnVr9/7SKTjxFDANBgkqhkiG9w0BAQsFAAOCAQEAtxmfsbuO5XlD0KavD5GX
                lWQPV5SX7dZmWKAxLyQGdEraiaTLAEkoa3zE0TPmWHsOUZCVYBs7Dpv4BrDStP9u
                Aw9JnKaYgLkaD0hLstROgbYJUIpIgM/izYobHcvDItPYTNFsEquL4M/gH2YuMHlj
                6A6czjLe23kPpDDLI+5WHZlMbv8MkDdzn3YMw2Cx4ls57IuJIEdl/v47g/wgykNG
                PTA6UjdLX13xxn/s7nAQU76S+28C5TXz9zwpdtNiSLJhAwVC43vMtNY+ivNJG9lf
                NRJp2qMfOu5ftNV17yJN7kL/3cL7Ua/RqwraQT0nfrOymIewuu44DlSAuFrmLLD4
                2w==
                -----END CERTIFICATE-----
```

**Note**: This is the same certificate already in hh-search-svc.yaml (lines 40-69)

#### Step 2.3: Apply Configuration Changes

**Execute**:
```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter"

# The changes need to be made to the YAML files
# Use your editor or Edit tool to add the Redis TLS configuration
# to each of the 6 service files listed above
```

### Phase 3: Redeploy Affected Services

#### Step 3.1: Deploy Services with Fixed Configurations

**Command**:
```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter"

./scripts/deploy-cloud-run-services.sh \
  --project-id headhunter-ai-0088 \
  --environment production \
  --services "hh-embed-svc hh-msgs-svc hh-evidence-svc hh-eco-svc hh-enrich-svc hh-admin-svc"
```

**Expected Duration**: 5-8 minutes

**Expected Output**:
```
✓ Service hh-embed-svc-production deployed and healthy
✓ Service hh-msgs-svc-production deployed and healthy
✓ Service hh-evidence-svc-production deployed and healthy
...
```

#### Step 3.2: Verify Deployment Success

**Command**:
```bash
# Check all services are healthy
gcloud run services list \
  --project=headhunter-ai-0088 \
  --region=us-central1 \
  --filter="metadata.name~hh-.*-svc-production" \
  --format="table(metadata.name,status.conditions[0].status,status.conditions[0].type)"
```

**Expected**: All services show `STATUS=True` and `TYPE=Ready`

### Phase 4: Re-run Validation Tests

#### Step 4.1: Execute Validation Test Suite

**Command**:
```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter"

./scripts/production-validation-test.sh
```

**Expected Results**:
- Tests Passed: >24 of 27 (>89%)
- All health endpoints: HTTP 200
- All ready endpoints: HTTP 200
- Metrics endpoints: May fail with 400/401 (expected - auth required)

#### Step 4.2: Check Specific Service Health

**Commands**:
```bash
# Test services that were previously failing
curl -s https://hh-embed-svc-production-akcoqbr7sa-uc.a.run.app/health | jq
# Expected: {"status":"healthy", ...}

curl -s https://hh-msgs-svc-production-akcoqbr7sa-uc.a.run.app/health | jq
# Expected: {"status":"healthy", ...}

curl -s https://hh-evidence-svc-production-akcoqbr7sa-uc.a.run.app/health | jq
# Expected: {"status":"healthy", ...}

curl -s https://hh-eco-svc-production-akcoqbr7sa-uc.a.run.app/health | jq
# Expected: {"status":"healthy", ...}
```

### Phase 5: Monitor and Verify

#### Step 5.1: Check Service Logs for Errors

**Commands**:
```bash
# Check for database connection errors (should be NONE)
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name~'hh-.*-svc-production' \
  AND jsonPayload.message=~'password authentication failed' \
  AND timestamp>='2025-10-09T18:00:00Z'" \
  --project=headhunter-ai-0088 \
  --limit=10

# Check for Redis connection errors (should be NONE)
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name~'hh-.*-svc-production' \
  AND jsonPayload.message=~'max retries per request' \
  AND timestamp>='2025-10-09T18:00:00Z'" \
  --project=headhunter-ai-0088 \
  --limit=10
```

**Expected**: No matching log entries

#### Step 5.2: Verify Database Connections

**Commands**:
```bash
# Check connection counts to database
gcloud sql operations list \
  --instance=sql-hh-core \
  --project=headhunter-ai-0088 \
  --limit=5

# Monitor active connections
cloud_sql_proxy headhunter-ai-0088:us-central1:sql-hh-core &
PROXY_PID=$!
sleep 3

psql "host=localhost port=5432 dbname=headhunter user=postgres" \
  -c "SELECT usename, count(*) FROM pg_stat_activity WHERE datname='headhunter' GROUP BY usename;"

kill $PROXY_PID
```

**Expected**: Connections from hh_app, hh_analytics, hh_ops users

#### Step 5.3: Verify Redis Connections

**Commands**:
```bash
# Check Redis operations metrics
gcloud redis operations list \
  --region=us-central1 \
  --project=headhunter-ai-0088 \
  --limit=5

# Get Redis instance metrics
gcloud redis instances describe redis-skills-us-central1 \
  --region=us-central1 \
  --project=headhunter-ai-0088 \
  --format="table(name,currentLocationId,state,authorizedNetwork)"
```

**Expected**: Instance state=READY, no recent errors

## Post-Remediation Tasks

### Load Testing

Once all services are healthy:

```bash
# Execute load testing suite
cd "/Volumes/Extreme Pro/myprojects/headhunter"

# Option 1: Using Apache Bench (if available)
ab -n 100 -c 10 -H "X-Tenant-ID: tenant-alpha" \
  https://hh-search-svc-production-akcoqbr7sa-uc.a.run.app/health

# Option 2: Using custom load test script (create if needed)
# ./scripts/load-test-production.sh
```

**Success Criteria**:
- All requests complete successfully (0% failure rate)
- Average response time <500ms
- p95 response time <1000ms
- No error logs during test

### 24-Hour Monitoring Setup

**Create monitoring dashboard**:
```bash
# This would be done via GCP Console or Terraform
# Document the dashboard URL once created
```

**Key Metrics to Monitor**:
1. Service health endpoint response (5-minute interval checks)
2. Error rate by service (alert if >1% for 5 minutes)
3. Request latency p50, p95, p99
4. Database connection pool utilization
5. Redis connection pool utilization
6. Memory and CPU usage per service

**Alert Configuration**:
- Email/Slack notifications for health check failures
- Immediate alert if any service returns 503 for health endpoint
- Alert if error rate sustained above 5% for 10 minutes

## Rollback Procedure

If remediation causes issues:

### Rollback Database Changes

```bash
# Remove hh_ops user if causing problems
gcloud sql users delete hh_ops \
  --instance=sql-hh-core \
  --project=headhunter-ai-0088

# Reset passwords back to original values (if known)
# Note: Original passwords may not be known - avoid rollback if possible
```

### Rollback Service Deployments

```bash
# Get previous revision names
gcloud run revisions list \
  --service=hh-embed-svc-production \
  --region=us-central1 \
  --project=headhunter-ai-0088 \
  --format="table(name,creationTimestamp)" \
  --limit=5

# Rollback to previous revision
gcloud run services update-traffic hh-embed-svc-production \
  --to-revisions=<PREVIOUS_REVISION>=100 \
  --region=us-central1 \
  --project=headhunter-ai-0088
```

## Success Criteria

Remediation is successful when:

- ✅ All 8 services report HTTP 200 on /health endpoint
- ✅ All 8 services report HTTP 200 on /ready endpoint
- ✅ No database authentication errors in logs
- ✅ No Redis connection errors in logs
- ✅ Validation test suite passes >90% of tests
- ✅ Load testing completes with <1% error rate
- ✅ 24-hour monitoring established
- ✅ Task 78.8 can be marked as DONE
- ✅ Task 78 can be marked as DONE

## Timeline

**Estimated Total Time**: 45-60 minutes

- Phase 1 (Database): 15 minutes
- Phase 2 (Redis Config): 10 minutes
- Phase 3 (Deployment): 10 minutes
- Phase 4 (Validation): 5 minutes
- Phase 5 (Monitoring): 10 minutes
- Buffer: 10 minutes

## Next Steps After Completion

1. Mark Task 78.8 status as DONE
2. Mark Task 78 parent task status as DONE
3. Update deployment documentation with lessons learned
4. Create runbook for database user management
5. Create runbook for Redis TLS configuration
6. Consider automation for password synchronization
7. Consider automation for service health monitoring

---

**Document Status**: READY FOR EXECUTION
**Created**: 2025-10-09
**Last Updated**: 2025-10-09
**Owner**: DevOps/SRE Team
