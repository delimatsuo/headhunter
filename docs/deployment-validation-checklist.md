# Deployment Validation Checklist

**Purpose**: Comprehensive pre-deployment and post-deployment validation checklist to prevent recurrence of Task 78 deployment failures.

**Last Updated**: October 9, 2025
**Owner**: DevOps / SRE Team
**Applies To**: All Headhunter AI production deployments

---

## Table of Contents

1. [Pre-Deployment Validation](#pre-deployment-validation)
2. [Deployment Execution Validation](#deployment-execution-validation)
3. [Post-Deployment Validation](#post-deployment-validation)
4. [Continuous Validation](#continuous-validation)
5. [Validation Automation Scripts](#validation-automation-scripts)

---

## Pre-Deployment Validation

### Phase 1: Configuration Validation

#### Cloud Run YAML Configuration
- [ ] All YAML files pass syntax validation
  ```bash
  for file in config/cloud-run/*.yaml; do
    python3 -c "import yaml; yaml.safe_load(open('$file'))" || echo "FAIL: $file"
  done
  ```

- [ ] Autoscaling annotations ONLY at Revision template level
  ```bash
  for file in config/cloud-run/*.yaml; do
    # Should NOT find autoscaling in Service metadata
    if grep -A 5 "^metadata:" "$file" | grep -q "autoscaling.knative.dev"; then
      echo "❌ FAIL: $file has autoscaling at Service level"
      exit 1
    fi
  done
  ```

- [ ] All environment variables defined and non-empty
  ```bash
  # Check critical env vars are set in YAML
  required_vars=("PORT" "NODE_ENV" "PROJECT_ID")
  for file in config/cloud-run/*.yaml; do
    for var in "${required_vars[@]}"; do
      grep -q "name: $var" "$file" || echo "❌ Missing $var in $file"
    done
  done
  ```

- [ ] Resource limits appropriate for service
  ```bash
  # Memory limits should be reasonable (1-4Gi for most services)
  # CPU should be 1-2 for most services
  ```

- [ ] Service names follow naming convention: `hh-*-svc-${ENVIRONMENT}`

- [ ] All required annotations present:
  - [ ] `run.googleapis.com/ingress` (internal-and-cloud-load-balancing)
  - [ ] Autoscaling: `maxScale` and `minScale` at revision level
  - [ ] VPC connector (if needed)

#### Cloud Run Dry-Run Validation
- [ ] All services pass dry-run deployment
  ```bash
  for file in config/cloud-run/*.yaml; do
    echo "Dry-run: $file"
    gcloud run services replace "$file" \
      --project headhunter-ai-0088 \
      --region us-central1 \
      --dry-run || echo "❌ FAIL: $file"
  done
  ```

### Phase 2: Code Validation

#### Route Registration
- [ ] No duplicate `/health` endpoints
  ```bash
  # routes.ts should have /health/detailed, not /health
  for file in services/hh-*/src/routes.ts; do
    if grep -q "server.get('/health'," "$file"; then
      echo "❌ FAIL: $file has /health (should be /health/detailed)"
      exit 1
    fi
  done
  ```

- [ ] No duplicate `/ready` endpoints
  ```bash
  # index.ts should NOT register /ready (already in buildServer)
  for file in services/hh-*/src/index.ts; do
    if grep -q "server.get('/ready'" "$file"; then
      echo "❌ FAIL: $file has duplicate /ready registration"
      exit 1
    fi
  done
  ```

- [ ] All routes registered BEFORE `server.listen()`
  ```bash
  # Verify route registration happens before listen
  for file in services/hh-*/src/index.ts; do
    # Check pattern: server.register() before server.listen()
    # Manual inspection required
  done
  ```

#### PORT Binding
- [ ] All services bind to `process.env.PORT`
  ```bash
  for file in services/hh-*/src/index.ts; do
    if ! grep -q "process.env.PORT" "$file"; then
      echo "❌ FAIL: $file doesn't bind to process.env.PORT"
      exit 1
    fi
  done
  ```

- [ ] All services bind to host `0.0.0.0`
  ```bash
  for file in services/hh-*/src/index.ts; do
    if ! grep -q "0.0.0.0" "$file"; then
      echo "❌ FAIL: $file doesn't bind to 0.0.0.0"
      exit 1
    fi
  done
  ```

#### TypeScript Compilation
- [ ] All services compile without errors
  ```bash
  cd services
  npm run build
  # Exit code must be 0
  ```

- [ ] No TypeScript errors in any service
- [ ] All type definitions up to date

#### Unit Tests
- [ ] All service unit tests pass
  ```bash
  cd services
  npm test
  # All tests must pass
  ```

- [ ] Test coverage meets minimum threshold (>80%)
- [ ] No skipped or pending tests without justification

### Phase 3: Infrastructure Validation

#### Secret Manager
- [ ] All required secrets exist
  ```bash
  required_secrets=(
    "api-gateway-key"
    "db-primary-password"
    "together-ai-api-key"
    "oauth-client-tenant-alpha"
    "redis-auth-string"
  )

  for secret in "${required_secrets[@]}"; do
    gcloud secrets describe "$secret" \
      --project headhunter-ai-0088 >/dev/null 2>&1 || echo "❌ Missing: $secret"
  done
  ```

- [ ] Secret values are valid (not placeholder/empty)
- [ ] OAuth endpoints are correct (if OAuth enabled)
  ```bash
  # Verify OAuth token_uri resolves
  oauth_config=$(gcloud secrets versions access latest \
    --secret=oauth-client-tenant-alpha --project headhunter-ai-0088)

  token_uri=$(echo "$oauth_config" | jq -r '.token_uri')
  if ! nslookup "$(echo $token_uri | sed 's|https://||' | cut -d/ -f1)" > /dev/null; then
    echo "❌ OAuth token_uri DNS does not resolve: $token_uri"
  fi
  ```

#### Cloud SQL
- [ ] Database instance is running
  ```bash
  gcloud sql instances describe headhunter-db-primary \
    --project headhunter-ai-0088 \
    --format='value(state)' | grep -q RUNNABLE
  ```

- [ ] Database schemas exist
  ```bash
  # Connect and verify schemas
  cloud_sql_proxy headhunter-ai-0088:us-central1:headhunter-db-primary &
  sleep 5
  psql -h localhost -U headhunter -d headhunter -c '\dn' | grep -q search
  ```

- [ ] Required extensions installed (pgvector)
  ```bash
  psql -h localhost -U headhunter -d headhunter \
    -c 'SELECT * FROM pg_extension' | grep -q vector
  ```

#### Redis (Memorystore)
- [ ] Redis instance is available
  ```bash
  gcloud redis instances describe headhunter-cache \
    --region us-central1 \
    --project headhunter-ai-0088 \
    --format='value(state)' | grep -q READY
  ```

- [ ] TLS enabled and CA certificate available
- [ ] Auth string configured in secrets

#### Firestore
- [ ] Firestore database exists
- [ ] Security rules deployed
- [ ] Required collections exist
  ```bash
  # Check via Firebase Admin SDK or console
  # Collections: candidate_profiles, candidate_embeddings, allowed_users
  ```

#### Networking
- [ ] VPC connector exists and is ready
  ```bash
  gcloud compute networks vpc-access connectors describe headhunter-vpc-connector \
    --region us-central1 \
    --project headhunter-ai-0088 \
    --format='value(state)' | grep -q READY
  ```

- [ ] Firewall rules allow required traffic
- [ ] Cloud SQL Private IP connectivity working

### Phase 4: API Gateway Validation

#### OpenAPI Spec Validation
- [ ] Gateway spec is Swagger 2.0 (not OpenAPI 3.0)
  ```bash
  grep -q 'swagger: "2.0"' docs/openapi/gateway.yaml || echo "❌ Not Swagger 2.0"
  ```

- [ ] No variable placeholders in backend URLs
  ```bash
  if grep -q '\${' docs/openapi/gateway.yaml; then
    echo "❌ Variable placeholders found in gateway.yaml"
    exit 1
  fi
  ```

- [ ] Spec validates with swagger-cli
  ```bash
  npx swagger-cli validate docs/openapi/gateway.yaml
  ```

- [ ] All backend URLs point to production Cloud Run services
  ```bash
  # All addresses should be https://hh-*-production-*.run.app
  grep "x-google-backend" docs/openapi/gateway.yaml -A 1
  ```

#### Backend Service Availability
- [ ] All backend services exist and are ready
  ```bash
  for service in hh-admin-svc hh-eco-svc hh-embed-svc hh-enrich-svc \
                  hh-evidence-svc hh-msgs-svc hh-rerank-svc hh-search-svc; do
    gcloud run services describe "${service}-production" \
      --region us-central1 \
      --project headhunter-ai-0088 \
      --format='value(status.conditions[0].status)' | grep -q True || echo "❌ $service"
  done
  ```

- [ ] All backend services respond to health checks
  ```bash
  for service in hh-admin-svc hh-eco-svc hh-embed-svc hh-enrich-svc \
                  hh-evidence-svc hh-msgs-svc hh-rerank-svc hh-search-svc; do
    url="https://${service}-production-akcoqbr7sa-uc.a.run.app/health"
    curl -sf "$url" > /dev/null || echo "❌ $service health check failed"
  done
  ```

### Phase 5: Container Image Validation

#### Image Build
- [ ] All container images built successfully
  ```bash
  # Check build manifest exists
  ls -la .deployment/manifests/build-manifest-*.json
  ```

- [ ] All images pushed to Artifact Registry
  ```bash
  for service in hh-admin-svc hh-eco-svc hh-embed-svc hh-enrich-svc \
                  hh-evidence-svc hh-msgs-svc hh-rerank-svc hh-search-svc; do
    gcloud artifacts docker images list \
      us-central1-docker.pkg.dev/headhunter-ai-0088/headhunter \
      --filter="package=$service" \
      --limit=1 || echo "❌ No image for $service"
  done
  ```

- [ ] Image tags follow convention: `<commit-sha>-production-<timestamp>`
- [ ] Images contain correct application code
  ```bash
  # Verify image digest matches expected build
  ```

#### Security Scanning
- [ ] Container images scanned for vulnerabilities
- [ ] No critical CVEs present
- [ ] Base images are up to date

---

## Deployment Execution Validation

### Phase 6: Deployment Script Validation

#### Script Configuration
- [ ] Deployment script has proper error handling
  ```bash
  # Verify wait_for_service_ready returns 1 on failure
  grep -q "return 1" scripts/deploy-cloud-run-services.sh | grep wait_for_service_ready
  ```

- [ ] Health checks are enabled (SKIP_VALIDATION=false)
- [ ] Timeout values are reasonable (default 300s)

#### Deployment Manifest
- [ ] Build manifest exists with all services
  ```bash
  manifest=$(ls -t .deployment/manifests/build-manifest-*.json | head -1)
  jq '.services | length' "$manifest" | grep -q 8
  ```

- [ ] All services in manifest have valid image references
  ```bash
  jq -r '.services[].image' "$manifest" | while read image; do
    [[ -n "$image" ]] || echo "❌ Empty image reference"
  done
  ```

### Phase 7: Progressive Deployment

#### Phase 7.1: Admin Services First
- [ ] Deploy hh-admin-svc
- [ ] Verify hh-admin-svc healthy
- [ ] Check logs for errors

#### Phase 7.2: Core Services
- [ ] Deploy hh-search-svc, hh-embed-svc, hh-enrich-svc
- [ ] Verify all healthy
- [ ] Test integration between services

#### Phase 7.3: Supporting Services
- [ ] Deploy hh-eco-svc, hh-evidence-svc, hh-msgs-svc, hh-rerank-svc
- [ ] Verify all healthy
- [ ] Test end-to-end flows

### Phase 8: Deployment Monitoring

#### Real-Time Monitoring
- [ ] Monitor Cloud Run deployment status
  ```bash
  gcloud run services list \
    --filter="metadata.name:hh-*-production" \
    --format="table(metadata.name,status.conditions[0].status,status.latestReadyRevisionName)"
  ```

- [ ] Monitor Cloud Logging for errors
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" \
    --limit 50 --format json
  ```

- [ ] Monitor container startup logs
- [ ] Check for route registration errors
- [ ] Verify no FST_ERR_* errors

---

## Post-Deployment Validation

### Phase 9: Service Health Validation

#### Individual Service Health
- [ ] All 8 services report healthy status
  ```bash
  for service in hh-admin-svc hh-eco-svc hh-embed-svc hh-enrich-svc \
                  hh-evidence-svc hh-msgs-svc hh-rerank-svc hh-search-svc; do
    status=$(gcloud run services describe "${service}-production" \
      --region us-central1 --project headhunter-ai-0088 \
      --format='value(status.conditions[0].status)')

    if [[ "$status" != "True" ]]; then
      echo "❌ $service not healthy (status: $status)"
    else
      echo "✅ $service healthy"
    fi
  done
  ```

- [ ] All services respond to /health endpoint
  ```bash
  for service in hh-admin-svc hh-eco-svc hh-embed-svc hh-enrich-svc \
                  hh-evidence-svc hh-msgs-svc hh-rerank-svc hh-search-svc; do
    url="https://${service}-production-akcoqbr7sa-uc.a.run.app/health"
    response=$(curl -sf "$url")

    if echo "$response" | jq -e '.status == "ok"' > /dev/null 2>&1; then
      echo "✅ $service /health OK"
    else
      echo "❌ $service /health failed: $response"
    fi
  done
  ```

- [ ] All services respond to /ready endpoint
  ```bash
  for service in hh-admin-svc hh-eco-svc hh-embed-svc hh-enrich-svc \
                  hh-evidence-svc hh-msgs-svc hh-rerank-svc hh-search-svc; do
    url="https://${service}-production-akcoqbr7sa-uc.a.run.app/ready"
    curl -sf "$url" > /dev/null || echo "❌ $service /ready failed"
  done
  ```

#### Deployment Manifest Validation
- [ ] Deployment manifest shows all services succeeded
  ```bash
  manifest=$(ls -t .deployment/manifests/deploy-manifest-*.json | head -1)

  # Check all services have status: success
  failed=$(jq -r '.services[] | select(.status != "success") | .service' "$manifest")
  if [[ -n "$failed" ]]; then
    echo "❌ Failed services: $failed"
    exit 1
  fi
  ```

- [ ] Deployment report generated
  ```bash
  ls -la docs/deployment-report-*.md
  ```

### Phase 10: Integration Testing

#### Service-to-Service Communication
- [ ] hh-embed-svc can call embedding service
- [ ] hh-search-svc can query pgvector
- [ ] hh-rerank-svc can access Redis cache
- [ ] hh-enrich-svc can write to Firestore

#### Database Connectivity
- [ ] All services can connect to Cloud SQL
  ```bash
  # Check Cloud Run logs for successful DB connections
  gcloud logging read "resource.type=cloud_run_revision AND textPayload=~'Database connected'" \
    --limit 10 --format json
  ```

- [ ] pgvector queries working
- [ ] No connection pool exhaustion

#### Cache Connectivity
- [ ] Redis TLS connections successful
  ```bash
  # Check for Redis connection logs
  gcloud logging read "resource.type=cloud_run_revision AND textPayload=~'Redis connected'" \
    --limit 10 --format json
  ```

- [ ] No ECONNRESET errors
- [ ] Cache hit rate metrics available

### Phase 11: API Gateway Validation

#### Gateway Health
- [ ] API Gateway is ACTIVE
  ```bash
  gcloud api-gateway gateways describe headhunter-api-gateway-production \
    --location us-central1 \
    --project headhunter-ai-0088 \
    --format='value(state)' | grep -q ACTIVE
  ```

- [ ] Gateway config deployed successfully
- [ ] Latest config version is active

#### Routing Validation
- [ ] All 8 service routes accessible via gateway
  ```bash
  API_KEY=$(gcloud secrets versions access latest \
    --secret=api-gateway-key --project=headhunter-ai-0088)

  GATEWAY="https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev"

  # Test search endpoint
  curl -sf -H "x-api-key: $API_KEY" -H "X-Tenant-ID: tenant-alpha" \
    -H "Content-Type: application/json" \
    "$GATEWAY/v1/search/hybrid" \
    -d '{"query":"test","limit":1}' > /dev/null || echo "❌ Search routing failed"

  # Test embed endpoint
  curl -sf -H "x-api-key: $API_KEY" -H "X-Tenant-ID: tenant-alpha" \
    "$GATEWAY/v1/embed/status" > /dev/null || echo "❌ Embed routing failed"
  ```

- [ ] Authentication working (API key validation)
- [ ] No 404 errors on valid routes
- [ ] No 502/503/504 gateway errors

### Phase 12: End-to-End Testing

#### Hybrid Search Pipeline
- [ ] Search requests return results
  ```bash
  API_KEY=$(gcloud secrets versions access latest --secret=api-gateway-key --project=headhunter-ai-0088)
  GATEWAY="https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev"

  response=$(curl -sS -H "x-api-key: $API_KEY" -H "X-Tenant-ID: tenant-alpha" \
    -H "Content-Type: application/json" \
    "$GATEWAY/v1/search/hybrid" \
    -d '{"query":"Senior software engineer Python","limit":5}')

  result_count=$(echo "$response" | jq '.results | length')
  if [[ "$result_count" -gt 0 ]]; then
    echo "✅ Search returned $result_count results"
  else
    echo "❌ Search returned no results"
  fi
  ```

- [ ] Embedding generation working
- [ ] pgvector retrieval working
- [ ] Rerank service responding
- [ ] Cache hit/miss working correctly

#### Performance Benchmarks
- [ ] p95 latency under SLA (<1.2s for search)
  ```bash
  # Run benchmark
  npx ts-node services/hh-search-svc/src/scripts/run-hybrid-benchmark.ts \
    --url "$GATEWAY" \
    --tenantId tenant-alpha \
    --jobDescription "Principal product engineer fintech" \
    --limit 5 --iterations 40 --concurrency 5

  # Check p95 < 1200ms
  ```

- [ ] Cache hit rate >98%
- [ ] No timeouts or 504 errors
- [ ] Database query performance acceptable

### Phase 13: Monitoring and Alerting

#### Cloud Monitoring
- [ ] All service metrics being collected
- [ ] Custom metrics (cache hit rate, latency) reporting
- [ ] Dashboards updated with new revisions
- [ ] Alert policies active

#### Log Aggregation
- [ ] Structured logs flowing to Cloud Logging
- [ ] Request IDs present in all logs
- [ ] Error logs being captured
- [ ] No log sampling/truncation issues

#### Error Budget
- [ ] Error rate <1% (SLA requirement)
  ```bash
  # Check error rate over last hour
  gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" \
    --format json | jq '. | length'
  ```

- [ ] Availability >99.9%
- [ ] p95 latency within SLA

### Phase 14: Documentation Validation

#### Deployment Documentation
- [ ] Deployment report generated and accurate
- [ ] Root cause analysis documented (if recovery)
- [ ] Runbooks updated
- [ ] HANDOVER.md reflects current state

#### Configuration Documentation
- [ ] All environment variables documented
- [ ] Secret dependencies documented
- [ ] Architecture diagrams up to date
- [ ] API documentation current

---

## Continuous Validation

### Daily Health Checks

#### Automated Health Monitoring
```bash
#!/bin/bash
# Script: .deployment/scripts/daily-health-check.sh

# All services healthy
gcloud run services list \
  --filter="metadata.name:hh-*-production" \
  --format="value(metadata.name,status.conditions[0].status)" | \
  grep -v "True" && echo "❌ Unhealthy services detected"

# Gateway active
gcloud api-gateway gateways describe headhunter-api-gateway-production \
  --location us-central1 --project headhunter-ai-0088 \
  --format='value(state)' | grep -q ACTIVE || echo "❌ Gateway not active"

# Error rate acceptable
error_count=$(gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" \
  --limit 1000 --format json --freshness=1h | jq '. | length')
[[ "$error_count" -lt 10 ]] || echo "❌ High error rate: $error_count errors in last hour"
```

### Weekly Validation

- [ ] Review deployment manifests for patterns
- [ ] Check for configuration drift
- [ ] Validate secret rotation schedule
- [ ] Review and update documentation
- [ ] Run full integration test suite
- [ ] Load testing for capacity planning

### Monthly Validation

- [ ] Audit security configurations
- [ ] Review and optimize resource allocation
- [ ] Update dependencies and base images
- [ ] Disaster recovery drill
- [ ] Review and update runbooks

---

## Validation Automation Scripts

### Complete Pre-Deployment Validator

```bash
#!/bin/bash
# Script: .deployment/scripts/pre-deployment-validator.sh
# Purpose: Comprehensive pre-deployment validation

set -e

echo "======================================"
echo "Pre-Deployment Validation Starting"
echo "======================================"

# Phase 1: Configuration Validation
echo "Phase 1: Configuration Validation"
for file in config/cloud-run/*.yaml; do
  echo "  Validating $file..."
  python3 -c "import yaml; yaml.safe_load(open('$file'))" || exit 1

  # Check annotation placement
  if grep -A 5 "^metadata:" "$file" | grep -q "autoscaling.knative.dev"; then
    echo "    ❌ FAIL: Autoscaling at Service level in $file"
    exit 1
  fi
done
echo "  ✅ All YAML files valid"

# Phase 2: Code Validation
echo "Phase 2: Code Validation"
cd services
npm run build || exit 1
echo "  ✅ TypeScript compilation successful"

npm test || exit 1
echo "  ✅ Unit tests passed"

# Phase 3: Infrastructure Validation
echo "Phase 3: Infrastructure Validation"
required_secrets=(
  "api-gateway-key"
  "db-primary-password"
  "together-ai-api-key"
)

for secret in "${required_secrets[@]}"; do
  gcloud secrets describe "$secret" --project headhunter-ai-0088 >/dev/null 2>&1 || {
    echo "  ❌ FAIL: Secret $secret not found"
    exit 1
  }
done
echo "  ✅ All required secrets exist"

# Phase 4: Dry-Run Validation
echo "Phase 4: Dry-Run Validation"
for file in config/cloud-run/*.yaml; do
  service=$(basename "$file" .yaml)
  echo "  Testing $service..."
  gcloud run services replace "$file" \
    --project headhunter-ai-0088 \
    --region us-central1 \
    --dry-run || exit 1
done
echo "  ✅ All services pass dry-run"

echo "======================================"
echo "✅ Pre-Deployment Validation PASSED"
echo "======================================"
```

### Complete Post-Deployment Validator

```bash
#!/bin/bash
# Script: .deployment/scripts/post-deployment-validator.sh
# Purpose: Comprehensive post-deployment validation

set -e

echo "======================================"
echo "Post-Deployment Validation Starting"
echo "======================================"

# Phase 9: Service Health
echo "Phase 9: Service Health Validation"
services=(hh-admin-svc hh-eco-svc hh-embed-svc hh-enrich-svc hh-evidence-svc hh-msgs-svc hh-rerank-svc hh-search-svc)

for service in "${services[@]}"; do
  status=$(gcloud run services describe "${service}-production" \
    --region us-central1 --project headhunter-ai-0088 \
    --format='value(status.conditions[0].status)')

  if [[ "$status" != "True" ]]; then
    echo "  ❌ FAIL: $service not healthy"
    exit 1
  fi

  url="https://${service}-production-akcoqbr7sa-uc.a.run.app/health"
  curl -sf "$url" > /dev/null || {
    echo "  ❌ FAIL: $service health check failed"
    exit 1
  }

  echo "  ✅ $service healthy"
done

# Phase 11: Gateway Validation
echo "Phase 11: API Gateway Validation"
gateway_state=$(gcloud api-gateway gateways describe headhunter-api-gateway-production \
  --location us-central1 --project headhunter-ai-0088 \
  --format='value(state)')

if [[ "$gateway_state" != "ACTIVE" ]]; then
  echo "  ❌ FAIL: Gateway not active (state: $gateway_state)"
  exit 1
fi
echo "  ✅ API Gateway active"

# Phase 12: End-to-End Test
echo "Phase 12: End-to-End Testing"
API_KEY=$(gcloud secrets versions access latest --secret=api-gateway-key --project=headhunter-ai-0088)
GATEWAY="https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev"

response=$(curl -sS -H "x-api-key: $API_KEY" -H "X-Tenant-ID: tenant-alpha" \
  -H "Content-Type: application/json" \
  "$GATEWAY/v1/search/hybrid" \
  -d '{"query":"Senior software engineer Python","limit":5}')

result_count=$(echo "$response" | jq '.results | length')
if [[ "$result_count" -lt 1 ]]; then
  echo "  ❌ FAIL: Search returned no results"
  exit 1
fi
echo "  ✅ End-to-end search working ($result_count results)"

echo "======================================"
echo "✅ Post-Deployment Validation PASSED"
echo "======================================"
```

---

## Usage Instructions

### Pre-Deployment

```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter"

# Run pre-deployment validator
./.deployment/scripts/pre-deployment-validator.sh

# If validation passes, proceed with deployment
./scripts/deploy-cloud-run-services.sh \
  --project-id headhunter-ai-0088 \
  --environment production
```

### Post-Deployment

```bash
# Run post-deployment validator
./.deployment/scripts/post-deployment-validator.sh

# If validation passes, deployment is complete
```

### Continuous Validation

```bash
# Daily health check (add to cron)
./.deployment/scripts/daily-health-check.sh

# Weekly full validation
./.deployment/scripts/pre-deployment-validator.sh
./.deployment/scripts/post-deployment-validator.sh
```

---

## Sign-Off Checklist

Before marking deployment as complete:

- [ ] All pre-deployment validations passed
- [ ] All deployment phases completed successfully
- [ ] All post-deployment validations passed
- [ ] Deployment documentation updated
- [ ] Monitoring and alerting verified
- [ ] Stakeholders notified
- [ ] Runbooks updated if needed

**Deployment Sign-Off**:
- Operator: ________________
- Date: ________________
- Deployment ID: ________________
- All Validations: ✅ PASSED / ❌ FAILED

---

**Document Version**: 1.0
**Last Updated**: October 9, 2025
**Owner**: DevOps/SRE Team
**Review Cycle**: Monthly
