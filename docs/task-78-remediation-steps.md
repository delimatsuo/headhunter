# Remediation Steps - Post-Deployment Fixes

**Date**: October 9, 2025
**Related**: Task 78 Deployment Recovery
**Purpose**: Document step-by-step remediation procedures for each root cause

---

## Table of Contents

1. [Remediation #1: Fix Cloud Run Annotation Placement](#remediation-1-fix-cloud-run-annotation-placement)
2. [Remediation #2: Resolve Fastify Route Duplication](#remediation-2-resolve-fastify-route-duplication)
3. [Remediation #3: Enhance Deployment Script Validation](#remediation-3-enhance-deployment-script-validation)
4. [Remediation #4: Correct API Gateway Configuration](#remediation-4-correct-api-gateway-configuration)
5. [Verification Procedures](#verification-procedures)
6. [Rollback Procedures](#rollback-procedures)

---

## Remediation #1: Fix Cloud Run Annotation Placement

### Problem Reference
Autoscaling annotations incorrectly placed at Service metadata level instead of Revision template metadata level.

### Prerequisites
- Access to repository: `/Volumes/Extreme Pro/myprojects/headhunter`
- Write permissions to `config/cloud-run/` directory
- Understanding of Knative Service vs Revision resources

### Step-by-Step Remediation

#### Step 1: Identify Affected Files
```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter"
ls -1 config/cloud-run/*.yaml
```

Expected output: 8 YAML files (hh-admin-svc, hh-eco-svc, hh-embed-svc, hh-enrich-svc, hh-evidence-svc, hh-msgs-svc, hh-rerank-svc, hh-search-svc)

#### Step 2: Backup Current Configuration
```bash
mkdir -p .deployment/backups/cloud-run-yaml-$(date +%Y%m%d-%H%M%S)
cp config/cloud-run/*.yaml .deployment/backups/cloud-run-yaml-$(date +%Y%m%d-%H%M%S)/
```

#### Step 3: Fix Each Service YAML

For **each service** file in `config/cloud-run/`:

**Before (Incorrect)**:
```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: hh-search-svc-${ENVIRONMENT}
  annotations:
    run.googleapis.com/ingress: internal-and-cloud-load-balancing
    autoscaling.knative.dev/maxScale: "${SERVICE_MAX_SCALE}"  # ❌ REMOVE THIS
    autoscaling.knative.dev/minScale: "${SERVICE_MIN_SCALE}"  # ❌ REMOVE THIS
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/maxScale: "${SERVICE_MAX_SCALE}"  # ✅ Keep this
        autoscaling.knative.dev/minScale: "${SERVICE_MIN_SCALE}"  # ✅ Keep this
```

**After (Correct)**:
```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: hh-search-svc-${ENVIRONMENT}
  annotations:
    run.googleapis.com/ingress: internal-and-cloud-load-balancing
    # Autoscaling annotations removed - belong on Revision template only
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/maxScale: "${SERVICE_MAX_SCALE}"  # ✅ Correct location
        autoscaling.knative.dev/minScale: "${SERVICE_MIN_SCALE}"  # ✅ Correct location
```

#### Step 4: Validate YAML Syntax
```bash
for file in config/cloud-run/*.yaml; do
  echo "Validating $file..."
  # Check YAML syntax
  python3 -c "import yaml; yaml.safe_load(open('$file'))" || echo "SYNTAX ERROR in $file"
done
```

#### Step 5: Dry-Run Deployment Test
```bash
# Test one service with dry-run
gcloud run services replace config/cloud-run/hh-search-svc.yaml \
  --project headhunter-ai-0088 \
  --region us-central1 \
  --dry-run

# Should see: "Dry run complete. No changes will be made."
```

#### Step 6: Commit Changes
```bash
git add config/cloud-run/*.yaml
git commit -m "fix: correct Cloud Run autoscaling annotation placement (task 78.1)

- Remove autoscaling annotations from Service metadata level
- Annotations remain at Revision template level only
- Fixes INVALID_ARGUMENT error on deployment

Affected files:
- config/cloud-run/hh-admin-svc.yaml
- config/cloud-run/hh-eco-svc.yaml
- config/cloud-run/hh-embed-svc.yaml
- config/cloud-run/hh-enrich-svc.yaml
- config/cloud-run/hh-evidence-svc.yaml
- config/cloud-run/hh-msgs-svc.yaml
- config/cloud-run/hh-rerank-svc.yaml
- config/cloud-run/hh-search-svc.yaml"

git push origin main
```

### Verification
- [x] All 8 YAML files modified
- [x] Autoscaling annotations removed from Service metadata
- [x] Autoscaling annotations remain at Revision template level
- [x] YAML syntax validation passes
- [x] Dry-run deployment succeeds
- [x] Changes committed and pushed

### Rollback Procedure
```bash
# If needed, restore from backup
BACKUP_DIR=.deployment/backups/cloud-run-yaml-YYYYMMDD-HHMMSS
cp ${BACKUP_DIR}/*.yaml config/cloud-run/
git checkout config/cloud-run/*.yaml
```

---

## Remediation #2: Resolve Fastify Route Duplication

### Problem Reference
Two bugs: duplicate `/health` endpoint (registered before and after server.listen()) and duplicate `/ready` endpoint (registered in both common library and service code).

### Prerequisites
- TypeScript development environment
- Node.js 20+ installed
- Access to service source code

### Step-by-Step Remediation

#### Step 1: Fix Duplicate `/health` Endpoint

**Affected Files** (7 services):
- `services/hh-eco-svc/src/routes.ts`
- `services/hh-embed-svc/src/routes.ts`
- `services/hh-enrich-svc/src/routes.ts`
- `services/hh-evidence-svc/src/routes.ts`
- `services/hh-msgs-svc/src/routes.ts`
- `services/hh-rerank-svc/src/routes.ts`
- `services/hh-search-svc/src/routes.ts`

**Change Required**:
```typescript
// Before (in routes.ts)
export async function routes(server: FastifyInstance) {
  server.get('/health', async () => {  // ❌ Conflicts with index.ts
    return {
      status: 'healthy',
      version: process.env.npm_package_version,
      // ... detailed info
    }
  })
}

// After (in routes.ts)
export async function routes(server: FastifyInstance) {
  server.get('/health/detailed', async () => {  // ✅ Renamed to avoid conflict
    return {
      status: 'healthy',
      version: process.env.npm_package_version,
      // ... detailed info
    }
  })
}
```

**Automated Fix Script**:
```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter"

# Fix all services at once
for service in hh-eco-svc hh-embed-svc hh-enrich-svc hh-evidence-svc hh-msgs-svc hh-rerank-svc hh-search-svc; do
  sed -i.bak "s|server.get('/health'|server.get('/health/detailed'|g" \
    "services/${service}/src/routes.ts"
  echo "Fixed ${service}"
done
```

#### Step 2: Fix Duplicate `/ready` Endpoint

**Affected Files** (7 services):
- `services/hh-eco-svc/src/index.ts`
- `services/hh-embed-svc/src/index.ts`
- `services/hh-enrich-svc/src/index.ts`
- `services/hh-evidence-svc/src/index.ts`
- `services/hh-msgs-svc/src/index.ts`
- `services/hh-rerank-svc/src/index.ts`
- `services/hh-search-svc/src/index.ts`

**Change Required**:
```typescript
// Before (in index.ts)
const server = buildServer()  // buildServer() already registers /ready

// Early health check for Cloud Run
server.get('/health', async () => ({ status: 'ok' }))

server.get('/ready', async () => ({ status: 'ready' }))  // ❌ DUPLICATE - remove this

await server.listen({ port, host: '0.0.0.0' })

// After (in index.ts)
const server = buildServer()  // buildServer() already registers /ready

// Early health check for Cloud Run
server.get('/health', async () => ({ status: 'ok' }))

// /ready is already registered by buildServer() - no duplicate needed ✅

await server.listen({ port, host: '0.0.0.0' })
```

**Manual Fix** (safer for complex code):
```bash
# For each service, edit index.ts and remove the duplicate /ready registration
# Look for pattern: server.get('/ready', ...)
# Delete or comment out that entire block
```

#### Step 3: Verify No Other Duplicates
```bash
# Check for any other duplicate route registrations
cd "/Volumes/Extreme Pro/myprojects/headhunter"

for service in services/hh-*/src/*.ts; do
  echo "Checking $service..."
  # Look for common routes
  grep -n "server.get('/health'" "$service" || true
  grep -n "server.get('/ready'" "$service" || true
  grep -n "server.get('/metrics'" "$service" || true
done
```

#### Step 4: Build and Test Locally
```bash
# Build all services
cd "/Volumes/Extreme Pro/myprojects/headhunter"
npm run build --prefix services

# Run unit tests
npm test --prefix services

# Start services locally with docker-compose
docker compose -f docker-compose.local.yml up --build -d

# Test health endpoints
for port in 7101 7102 7103 7104 7105 7106 7107 7108; do
  echo "Testing port $port..."
  curl -sf "http://localhost:$port/health" || echo "FAILED: $port"
  curl -sf "http://localhost:$port/ready" || echo "FAILED: $port"
done
```

#### Step 5: Commit Changes
```bash
# Commit routes.ts changes
git add services/*/src/routes.ts
git commit -m "fix: rename duplicate /health to /health/detailed (task 78.2)

- Resolve FST_ERR_INSTANCE_ALREADY_LISTENING error
- /health registered in index.ts before server.listen()
- /health/detailed registered in routes.ts after server.listen()

Affected services:
- hh-eco-svc, hh-embed-svc, hh-enrich-svc
- hh-evidence-svc, hh-msgs-svc, hh-rerank-svc
- hh-search-svc"

git push origin main

# Commit index.ts changes
git add services/*/src/index.ts
git commit -m "fix: remove duplicate /ready endpoint registration (task 78.2)

- Resolve FST_ERR_DUPLICATED_ROUTE error
- /ready already registered by buildServer() in @hh/common
- Remove redundant registration in service index.ts

Affected services:
- hh-eco-svc, hh-embed-svc, hh-enrich-svc
- hh-evidence-svc, hh-msgs-svc, hh-rerank-svc
- hh-search-svc"

git push origin main
```

### Verification
- [x] All 7 services' routes.ts files updated (hh-admin-svc not affected)
- [x] All 7 services' index.ts files updated
- [x] TypeScript compilation succeeds
- [x] Unit tests pass
- [x] Local docker-compose startup succeeds
- [x] Health and ready endpoints respond correctly
- [x] No FST_ERR_* errors in logs
- [x] Changes committed and pushed

### Rollback Procedure
```bash
# Revert commits if issues found
git revert <commit-hash-for-index.ts-changes>
git revert <commit-hash-for-routes.ts-changes>
git push origin main
```

---

## Remediation #3: Enhance Deployment Script Validation

### Problem Reference
Deployment script reported success even when services failed health checks.

### Prerequisites
- Bash scripting knowledge
- Access to `scripts/deploy-cloud-run-services.sh`
- Understanding of deployment flow

### Step-by-Step Remediation

#### Step 1: Backup Deployment Script
```bash
cd "/Volumes/Extreme Pro/myprojects/headhunter"
cp scripts/deploy-cloud-run-services.sh scripts/deploy-cloud-run-services.sh.backup-$(date +%Y%m%d-%H%M%S)
```

#### Step 2: Update `wait_for_service_ready()` Function

**Location**: `scripts/deploy-cloud-run-services.sh` (around line 200-250)

**Before**:
```bash
function wait_for_service_ready() {
  local service="$1"
  local max_wait=300
  local elapsed=0

  while [[ "$elapsed" -lt "$max_wait" ]]; do
    # Check readiness...
    if service_is_ready; then
      return 0
    fi
    sleep 10
    elapsed=$((elapsed + 10))
  done

  warn "Service not ready after ${max_wait}s"
  return 0  # ❌ Returns success even on timeout
}
```

**After**:
```bash
function wait_for_service_ready() {
  local service="$1"
  local max_wait=300
  local elapsed=0

  while [[ "$elapsed" -lt "$max_wait" ]]; do
    # Check readiness...
    if service_is_ready; then
      return 0
    fi
    sleep 10
    elapsed=$((elapsed + 10))
  done

  error "Service not ready after ${max_wait}s"  # Changed to error
  return 1  # ✅ Now returns failure on timeout
}
```

#### Step 3: Update `deploy_service()` Function

**Location**: `scripts/deploy-cloud-run-services.sh` (around line 350-420)

**Before**:
```bash
function deploy_service() {
  local service="$1"

  # ... deployment logic ...

  if [[ "$SKIP_VALIDATION" == false ]]; then
    wait_for_service_ready "$service"  # ❌ Return value ignored
  fi

  # Always write success
  local overall_status="success"  # ❌ Hardcoded

  cat >"${TMP_RESULTS_DIR}/${service}.json" <<JSON
{
  "service": "${service}",
  "status": "${overall_status}"
}
JSON
}
```

**After**:
```bash
function deploy_service() {
  local service="$1"

  # ... deployment logic ...

  if [[ "$SKIP_VALIDATION" == false ]]; then
    if ! wait_for_service_ready "$service"; then  # ✅ Check return value
      warn "Service ${service} did not reach ready state in time"
      cat >"${TMP_RESULTS_DIR}/${service}.json" <<JSON
{
  "service": "${service}",
  "status": "failed",  # ✅ Report failure
  "health": "not_ready"
}
JSON
      return 1  # ✅ Propagate failure
    fi
  fi

  # Perform health check
  local health_status
  health_status=$(perform_health_check "$service")

  # Determine overall status based on readiness AND health
  local overall_status="success"
  if [[ "$health_status" == "fail" ]]; then
    overall_status="failed"  # ✅ Reflect health check failure
    warn "Service ${service} deployed but health check failed"
  elif [[ "$health_status" == "unknown" && "$SKIP_VALIDATION" == false ]]; then
    overall_status="unknown"  # ✅ Reflect uncertainty
    warn "Service ${service} deployed but health check could not be verified"
  fi

  cat >"${TMP_RESULTS_DIR}/${service}.json" <<JSON
{
  "service": "${service}",
  "status": "${overall_status}",  # ✅ Use actual status
  "health": "${health_status}"
}
JSON
}
```

#### Step 4: Add Deployment Verification Function

**Add new function** (insert after `deploy_service()`):
```bash
function verify_deployment_results() {
  local manifest_file="$1"

  echo "Verifying deployment results..."

  # Parse manifest and check for failures
  local failed_count=0
  local total_count=0

  while IFS= read -r service_result; do
    total_count=$((total_count + 1))
    local status=$(echo "$service_result" | jq -r '.status')

    if [[ "$status" != "success" ]]; then
      failed_count=$((failed_count + 1))
      local service=$(echo "$service_result" | jq -r '.service')
      error "Service $service failed deployment (status: $status)"
    fi
  done < <(jq -c '.services[]' "$manifest_file")

  if [[ "$failed_count" -gt 0 ]]; then
    error "Deployment failed: $failed_count of $total_count services failed"
    return 1
  fi

  echo "✅ All $total_count services deployed successfully"
  return 0
}
```

#### Step 5: Update Main Deployment Flow

**Location**: Main execution section (near end of script)

**Add verification call**:
```bash
# After all services deployed
echo "Generating deployment manifest..."
generate_manifest

# Add verification
if ! verify_deployment_results "${MANIFEST_FILE}"; then
  error "Deployment verification failed"
  exit 1
fi

echo "✅ Deployment completed and verified successfully"
```

#### Step 6: Test Script with Mock Failure
```bash
# Create test script to simulate failure
cat > /tmp/test-deploy-validation.sh <<'EOF'
#!/bin/bash
source scripts/deploy-cloud-run-services.sh

# Mock wait_for_service_ready to return failure
wait_for_service_ready() {
  return 1  # Simulate failure
}

# Test deploy_service function
TMP_RESULTS_DIR=/tmp/deploy-test
mkdir -p "$TMP_RESULTS_DIR"
SKIP_VALIDATION=false

if deploy_service "test-service"; then
  echo "ERROR: deploy_service should have failed but returned success"
  exit 1
else
  echo "✅ deploy_service correctly reported failure"
fi

# Check result JSON
if grep -q '"status": "failed"' "$TMP_RESULTS_DIR/test-service.json"; then
  echo "✅ Result JSON correctly shows failed status"
else
  echo "ERROR: Result JSON should show failed status"
  cat "$TMP_RESULTS_DIR/test-service.json"
  exit 1
fi
EOF

chmod +x /tmp/test-deploy-validation.sh
/tmp/test-deploy-validation.sh
```

#### Step 7: Commit Changes
```bash
git add scripts/deploy-cloud-run-services.sh
git commit -m "fix: enhance deployment script health validation (task 78.4)

- wait_for_service_ready() now returns 1 on timeout (was 0)
- deploy_service() checks wait_for_service_ready() return value
- Overall status reflects actual health check results
- Added verify_deployment_results() function
- Deployment fails fast when services unhealthy

Prevents false-positive success reports when services fail."

git push origin main
```

### Verification
- [x] `wait_for_service_ready()` returns 1 on failure
- [x] `deploy_service()` checks return values
- [x] Status field uses actual health results
- [x] Test script validates failure handling
- [x] Changes committed and pushed

---

## Remediation #4: Correct API Gateway Configuration

### Problem Reference
Three issues: OpenAPI 3.0 vs Swagger 2.0, variable placeholders in URLs, OAuth endpoint misconfiguration.

### Prerequisites
- Understanding of OpenAPI/Swagger specifications
- Access to `docs/openapi/gateway.yaml`
- `gcloud` CLI configured

### Step-by-Step Remediation

#### Step 1: Convert OpenAPI 3.0 to Swagger 2.0

**Location**: `docs/openapi/gateway.yaml`

**Major Changes Required**:

1. **Version Declaration**:
```yaml
# Before
openapi: 3.0.0

# After
swagger: "2.0"
```

2. **Components to Definitions**:
```yaml
# Before
components:
  schemas:
    SearchRequest:
      type: object
      properties:
        query:
          type: string

# After
definitions:
  SearchRequest:
    type: object
    properties:
      query:
        type: string
```

3. **Response Format**:
```yaml
# Before (OpenAPI 3.0)
paths:
  /v1/search/hybrid:
    post:
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SearchResponse'

# After (Swagger 2.0)
paths:
  /v1/search/hybrid:
    post:
      responses:
        '200':
          description: Success
          schema:
            $ref: '#/definitions/SearchResponse'
```

4. **Request Body**:
```yaml
# Before (OpenAPI 3.0)
paths:
  /v1/search/hybrid:
    post:
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SearchRequest'

# After (Swagger 2.0)
paths:
  /v1/search/hybrid:
    post:
      consumes:
        - application/json
      produces:
        - application/json
      parameters:
        - in: body
          name: body
          required: true
          schema:
            $ref: '#/definitions/SearchRequest'
```

#### Step 2: Resolve Backend URL Variables

**Get actual Cloud Run URLs**:
```bash
# Export service URLs
export HH_SEARCH_SVC_URL=$(gcloud run services describe hh-search-svc-production \
  --region us-central1 --project headhunter-ai-0088 --format='value(status.url)')

export HH_EMBED_SVC_URL=$(gcloud run services describe hh-embed-svc-production \
  --region us-central1 --project headhunter-ai-0088 --format='value(status.url)')

# ... repeat for all 8 services ...

echo "Service URLs:"
echo "HH_SEARCH_SVC_URL=$HH_SEARCH_SVC_URL"
echo "HH_EMBED_SVC_URL=$HH_EMBED_SVC_URL"
```

**Update gateway.yaml**:
```yaml
# Before
paths:
  /v1/search/hybrid:
    x-google-backend:
      address: https://${HH_SEARCH_SVC_URL}/v1/search/hybrid  # ❌ Variable

# After
paths:
  /v1/search/hybrid:
    x-google-backend:
      address: https://hh-search-svc-production-akcoqbr7sa-uc.a.run.app/v1/search/hybrid  # ✅ Resolved
```

**Automated URL Resolution Script**:
```bash
cat > scripts/resolve-gateway-urls.sh <<'EOF'
#!/bin/bash
set -e

PROJECT_ID="headhunter-ai-0088"
REGION="us-central1"
GATEWAY_SPEC="docs/openapi/gateway.yaml"

echo "Resolving backend URLs for API Gateway..."

# Get all service URLs
declare -A SERVICE_URLS
for service in hh-admin-svc hh-eco-svc hh-embed-svc hh-enrich-svc \
                hh-evidence-svc hh-msgs-svc hh-rerank-svc hh-search-svc; do
  url=$(gcloud run services describe "${service}-production" \
    --region "$REGION" --project "$PROJECT_ID" \
    --format='value(status.url)')
  SERVICE_URLS[$service]="$url"
  echo "  $service -> $url"
done

# Update gateway.yaml with actual URLs
cp "$GATEWAY_SPEC" "${GATEWAY_SPEC}.bak"

for service in "${!SERVICE_URLS[@]}"; do
  url="${SERVICE_URLS[$service]}"
  # Replace ${SERVICE_URL} placeholders
  sed -i "s|\${${service//-/_}_URL}|$url|g" "$GATEWAY_SPEC"
done

echo "✅ URLs resolved in $GATEWAY_SPEC"
EOF

chmod +x scripts/resolve-gateway-urls.sh
./scripts/resolve-gateway-urls.sh
```

#### Step 3: Configure Authentication (AUTH_MODE=none)

**Update security definitions**:
```yaml
# In docs/openapi/gateway.yaml

securityDefinitions:
  api_key:
    type: apiKey
    name: x-api-key
    in: header

# Apply to all paths
security:
  - api_key: []
```

**Document OAuth deferral**:
```yaml
# Add comment to gateway.yaml
# OAuth integration deferred to future phase
# Current production uses AUTH_MODE=none with API key validation
# Future: Implement OAuth with correct endpoint:
#   token_uri: https://idp.production.ella.jobs/oauth/token
```

#### Step 4: Validate and Deploy Gateway

**Validate Swagger spec**:
```bash
# Install validator
npm install -g swagger-cli

# Validate spec
swagger-cli validate docs/openapi/gateway.yaml
```

**Deploy gateway**:
```bash
# Create API config
gcloud api-gateway api-configs create headhunter-config-$(date +%Y%m%d-%H%M%S) \
  --api=headhunter-api \
  --openapi-spec=docs/openapi/gateway.yaml \
  --project=headhunter-ai-0088

# Update gateway to use new config
gcloud api-gateway gateways update headhunter-api-gateway-production \
  --api=headhunter-api \
  --api-config=headhunter-config-YYYYMMDD-HHMMSS \
  --location=us-central1 \
  --project=headhunter-ai-0088
```

**Test routing**:
```bash
# Get API key
API_KEY=$(gcloud secrets versions access latest \
  --secret=api-gateway-key \
  --project=headhunter-ai-0088)

# Test search endpoint
curl -sS \
  -H "x-api-key: $API_KEY" \
  -H "X-Tenant-ID: tenant-alpha" \
  -H "Content-Type: application/json" \
  https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/search/hybrid \
  -d '{"query":"Senior software engineer Python","limit":5}'
```

#### Step 5: Commit Changes
```bash
git add docs/openapi/gateway.yaml scripts/resolve-gateway-urls.sh
git commit -m "fix: convert API Gateway to Swagger 2.0 and resolve backend URLs (task 78.6)

- Convert OpenAPI 3.0 spec to Swagger 2.0
- Replace \${VARIABLE} placeholders with actual Cloud Run URLs
- Configure AUTH_MODE=none with API key security
- Add URL resolution script

Gateway now correctly routes to all 8 backend services."

git push origin main
```

### Verification
- [x] Gateway spec validates as Swagger 2.0
- [x] All backend URLs fully resolved (no variables)
- [x] Gateway deploys successfully
- [x] All service routes respond correctly
- [x] API key authentication works
- [x] Changes committed and pushed

---

## Verification Procedures

### Post-Remediation Verification Checklist

#### 1. Configuration Verification
```bash
# Verify all Cloud Run YAMLs have correct annotation placement
for file in config/cloud-run/*.yaml; do
  echo "Checking $file..."

  # Should NOT have autoscaling at Service level
  if grep -A 5 "^metadata:" "$file" | grep -q "autoscaling.knative.dev"; then
    echo "❌ FAIL: $file has autoscaling at Service level"
  else
    echo "✅ PASS: $file autoscaling correctly placed"
  fi
done
```

#### 2. Code Verification
```bash
# Verify no duplicate route registrations
cd "/Volumes/Extreme Pro/myprojects/headhunter"

for service in services/hh-*/src/index.ts; do
  # Should not have duplicate /ready
  if grep -q "server.get('/ready'" "$service"; then
    echo "❌ WARNING: $service may have duplicate /ready"
  fi
done

for service in services/hh-*/src/routes.ts; do
  # Should have /health/detailed, not /health
  if grep -q "server.get('/health'," "$service"; then
    echo "❌ WARNING: $service still uses /health (should be /health/detailed)"
  fi
done
```

#### 3. Deployment Script Verification
```bash
# Verify deployment script has proper error handling
if grep -q "return 1.*wait_for_service_ready" scripts/deploy-cloud-run-services.sh; then
  echo "✅ Deployment script has proper error handling"
else
  echo "❌ Deployment script may not handle failures correctly"
fi
```

#### 4. Gateway Verification
```bash
# Verify gateway is Swagger 2.0
if grep -q "swagger: \"2.0\"" docs/openapi/gateway.yaml; then
  echo "✅ Gateway spec is Swagger 2.0"
else
  echo "❌ Gateway spec may not be Swagger 2.0"
fi

# Verify no variable placeholders
if grep -q '\${' docs/openapi/gateway.yaml; then
  echo "❌ Gateway spec still contains variable placeholders"
else
  echo "✅ Gateway spec has resolved URLs"
fi
```

#### 5. End-to-End Production Verification
```bash
# Test all services are healthy
for service in hh-admin-svc hh-eco-svc hh-embed-svc hh-enrich-svc \
                hh-evidence-svc hh-msgs-svc hh-rerank-svc hh-search-svc; do
  url="https://${service}-production-akcoqbr7sa-uc.a.run.app/health"
  if curl -sf "$url" > /dev/null; then
    echo "✅ $service healthy"
  else
    echo "❌ $service not responding"
  fi
done

# Test API Gateway routing
API_KEY=$(gcloud secrets versions access latest --secret=api-gateway-key --project=headhunter-ai-0088)
GATEWAY_URL="https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev"

if curl -sf -H "x-api-key: $API_KEY" "$GATEWAY_URL/v1/search/hybrid" \
  -H "Content-Type: application/json" -H "X-Tenant-ID: tenant-alpha" \
  -d '{"query":"test","limit":1}' > /dev/null; then
  echo "✅ API Gateway routing works"
else
  echo "❌ API Gateway routing failed"
fi
```

---

## Rollback Procedures

### Emergency Rollback

If remediation causes issues, follow these steps:

#### 1. Rollback Code Changes
```bash
# Revert to last known good commit
git log --oneline -10  # Find last good commit
git revert <commit-hash>
git push origin main
```

#### 2. Rollback Cloud Run Services
```bash
# List revisions
gcloud run revisions list \
  --service hh-search-svc-production \
  --region us-central1 \
  --project headhunter-ai-0088

# Rollback to previous revision
gcloud run services update-traffic hh-search-svc-production \
  --to-revisions <previous-revision>=100 \
  --region us-central1 \
  --project headhunter-ai-0088
```

#### 3. Rollback API Gateway
```bash
# List configs
gcloud api-gateway api-configs list \
  --api headhunter-api \
  --project headhunter-ai-0088

# Rollback to previous config
gcloud api-gateway gateways update headhunter-api-gateway-production \
  --api headhunter-api \
  --api-config <previous-config-id> \
  --location us-central1 \
  --project headhunter-ai-0088
```

#### 4. Restore Configuration Files
```bash
# Restore from backup
BACKUP_DIR=.deployment/backups/cloud-run-yaml-YYYYMMDD-HHMMSS
cp ${BACKUP_DIR}/*.yaml config/cloud-run/
git add config/cloud-run/*.yaml
git commit -m "rollback: restore Cloud Run configurations from backup"
git push origin main
```

---

## Conclusion

All remediation steps documented with:
- ✅ Clear step-by-step procedures
- ✅ Before/after code examples
- ✅ Verification checklists
- ✅ Rollback procedures
- ✅ Automated scripts where possible

**Status**: Ready for operator execution and future reference

---

**Document Prepared**: October 9, 2025
**Author**: Claude Code Implementation Specialist
**Version**: 1.0
