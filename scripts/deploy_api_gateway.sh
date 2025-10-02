#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

warn() {
  printf '[%s] WARN: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
}

fail() {
  printf '[%s] ERROR: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Required command '$1' not found in PATH."
  fi
}

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-us-central1}"
ENVIRONMENT="${ENVIRONMENT:-staging}"
GATEWAY_ID="${GATEWAY_ID:-headhunter-api-gateway-${ENVIRONMENT}}"
OPENAPI_SPEC="${OPENAPI_SPEC:-docs/openapi/gateway-v3.yaml}"
CONFIG_ID="${CONFIG_ID:-gateway-config-$(date +%Y%m%d%H%M%S)}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-}"
ACCESS_TOKEN="${ACCESS_TOKEN:-}"
SMOKE_TENANT_ID="${SMOKE_TENANT_ID:-smoke-test}"

if [[ -z "$PROJECT_ID" ]]; then
  fail "PROJECT_ID must be provided (env var or flag)."
fi

if [[ -z "$SERVICE_ACCOUNT" ]]; then
  SERVICE_ACCOUNT="gateway-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
fi

require_command gcloud
require_command jq
require_command curl
require_command python3

log "Deploying API Gateway configuration"
log "Project: ${PROJECT_ID}, Region: ${REGION}, Environment: ${ENVIRONMENT}"

TMP_SPEC=""
CONFIG_CREATED=0
GATEWAY_CREATED=0
GATEWAY_CONFIG_UPDATED=0
PREVIOUS_CONFIG=""

cleanup() {
  local exit_code=$?
  if (( exit_code != 0 )); then
    warn "Deployment encountered an error; initiating rollback."
    if (( GATEWAY_CONFIG_UPDATED == 1 )) && [[ -n "$PREVIOUS_CONFIG" ]]; then
      warn "Restoring gateway ${GATEWAY_ID} to config ${PREVIOUS_CONFIG}."
      gcloud api-gateway gateways update "$GATEWAY_ID" \
        --location="$REGION" \
        --api-config="$PREVIOUS_CONFIG" \
        --project="$PROJECT_ID" \
        --quiet || warn "Rollback update failed; manual intervention required."
    elif (( GATEWAY_CREATED == 1 )); then
      warn "Deleting newly created gateway ${GATEWAY_ID}."
      gcloud api-gateway gateways delete "$GATEWAY_ID" \
        --location="$REGION" \
        --project="$PROJECT_ID" \
        --quiet || warn "Gateway deletion failed; manual cleanup required."
    fi
    if (( CONFIG_CREATED == 1 )); then
      warn "Removing API config ${CONFIG_ID}."
      gcloud api-gateway api-configs delete "$CONFIG_ID" \
        --api="$GATEWAY_ID" \
        --project="$PROJECT_ID" \
        --quiet || warn "Failed to delete api-config ${CONFIG_ID}."
    fi
  fi
  if [[ -n "$TMP_SPEC" && -f "$TMP_SPEC" ]]; then
    rm -f "$TMP_SPEC"
  fi
  exit $exit_code
}
trap cleanup EXIT

render_openapi_spec() {
  log "Rendering OpenAPI spec with environment substitutions and inlining schemas"
  TMP_SPEC="/tmp/gateway-spec-$(date +%s).yaml"
  python3 - <<'PY' "$OPENAPI_SPEC" "$TMP_SPEC" "$PROJECT_ID" "$REGION" "$ENVIRONMENT"
import sys
import re
from pathlib import Path
import yaml

source, destination, project, region, environment = sys.argv[1:]
source_path = Path(source)
content = source_path.read_text()

# Replace environment variables
for placeholder, value in {
    '${PROJECT_ID}': project,
    '${REGION}': region,
    '${ENVIRONMENT}': environment,
}.items():
    content = content.replace(placeholder, value)

# Parse YAML to inline external $refs
spec = yaml.safe_load(content)

# Load common schemas (try v3 first, then v2)
common_path_v3 = source_path.parent / 'schemas' / 'common-v3.yaml'
common_path_v2 = source_path.parent / 'schemas' / 'common.yaml'
common_path = common_path_v3 if common_path_v3.exists() else common_path_v2

if common_path.exists():
    common_spec = yaml.safe_load(common_path.read_text())

    # Inline components from common spec (OpenAPI 3.0)
    if 'components' in spec and 'components' in common_spec:
        for component_type in ['schemas', 'parameters', 'responses', 'securitySchemes']:
            if component_type in common_spec['components']:
                if component_type not in spec['components']:
                    spec['components'][component_type] = {}
                spec['components'][component_type].update(common_spec['components'][component_type])
    elif 'components' in common_spec:
        # If main spec doesn't have components, add them
        if 'components' not in spec:
            spec['components'] = {}
        for component_type, items in common_spec['components'].items():
            if component_type not in spec['components']:
                spec['components'][component_type] = {}
            spec['components'][component_type].update(items)

    # Also handle Swagger 2.0 format (definitions, parameters, responses)
    if 'definitions' in common_spec:
        if 'definitions' not in spec:
            spec['definitions'] = {}
        spec['definitions'].update(common_spec['definitions'])

    if 'parameters' in common_spec:
        if 'parameters' not in spec:
            spec['parameters'] = {}
        spec['parameters'].update(common_spec['parameters'])

    if 'responses' in common_spec:
        if 'responses' not in spec:
            spec['responses'] = {}
        spec['responses'].update(common_spec['responses'])

    # Replace all $ref to common files with local refs
    def replace_refs(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == '$ref' and isinstance(value, str):
                    if './schemas/common.yaml#/' in value:
                        obj[key] = value.replace('./schemas/common.yaml#/', '#/')
                    elif './schemas/common-v3.yaml#/' in value:
                        obj[key] = value.replace('./schemas/common-v3.yaml#/', '#/')
                else:
                    replace_refs(value)
        elif isinstance(obj, list):
            for item in obj:
                replace_refs(item)

    replace_refs(spec)
    content = yaml.dump(spec, default_flow_style=False, sort_keys=False)

Path(destination).write_text(content)
PY
}

ensure_services() {
  log "Ensuring required Google APIs are enabled"
  local apis=(
    apigateway.googleapis.com
    servicecontrol.googleapis.com
    servicemanagement.googleapis.com
    secretmanager.googleapis.com
    run.googleapis.com
  )
  for api in "${apis[@]}"; do
    if ! gcloud services list --enabled --project "$PROJECT_ID" --format="value(config.name)" | grep -q "^${api}$"; then
      log "Enabling ${api}"
      gcloud services enable "$api" --project "$PROJECT_ID"
    else
      log "${api} already enabled"
    fi
  done
}

ensure_gateway_api() {
  log "Ensuring API Gateway surface ${GATEWAY_ID} exists"
  if gcloud api-gateway apis describe "$GATEWAY_ID" --project "$PROJECT_ID" >/dev/null 2>&1; then
    log "API ${GATEWAY_ID} already present"
  else
    log "Creating API ${GATEWAY_ID}"
    gcloud api-gateway apis create "$GATEWAY_ID" --project "$PROJECT_ID"
  fi
}

validate_oauth_secrets() {
  log "Validating OAuth2 client credentials secrets"
  local secrets
  secrets=$(gcloud secrets list --project "$PROJECT_ID" --format="value(name)" | grep "^oauth-client-" || true)
  if [[ -z "$secrets" ]]; then
    fail "No oauth-client-* secrets found. Run scripts/configure_oauth2_clients.sh first."
  fi
  log "Discovered OAuth2 secrets:\n${secrets}"
}

validate_cloud_run_services() {
  log "Validating Cloud Run backends"
  local services=(
    hh-embed-svc
    hh-search-svc
    hh-rerank-svc
    hh-evidence-svc
    hh-eco-svc
    hh-enrich-svc
    hh-admin-svc
    hh-msgs-svc
  )
  for svc in "${services[@]}"; do
    local name="${svc}-${ENVIRONMENT}"
    log "Checking service ${name}"
    local ready
    ready=$(gcloud run services describe "$name" \
      --region "$REGION" \
      --project "$PROJECT_ID" \
      --format=json 2>/dev/null | jq -r '.status.conditions[] | select(.type=="Ready") | .status' || echo "Unknown")
    if [[ "$ready" != "True" ]]; then
      fail "Cloud Run service ${name} is not ready in region ${REGION}."
    fi
  done
}

validate_service_account_bindings() {
  log "Validating gateway service account Run Invoker bindings"
  local services=(
    hh-embed-svc
    hh-search-svc
    hh-rerank-svc
    hh-evidence-svc
    hh-eco-svc
    hh-enrich-svc
    hh-admin-svc
    hh-msgs-svc
  )
  local missing=0
  for svc in "${services[@]}"; do
    local name="${svc}-${ENVIRONMENT}"
    log "Checking IAM policy for ${name}"
    local policy
    policy=$(gcloud run services get-iam-policy "$name" \
      --region "$REGION" \
      --project "$PROJECT_ID" \
      --format=json)
    if ! echo "$policy" | jq -e --arg sa "serviceAccount:${SERVICE_ACCOUNT}" \
      '.bindings[] | select(.role=="roles/run.invoker") | .members[] | select(.==$sa)' >/dev/null; then
      warn "Service account ${SERVICE_ACCOUNT} missing roles/run.invoker on ${name}."
      missing=1
    fi
  done
  if (( missing == 1 )); then
    fail "Gateway service account lacks roles/run.invoker on one or more services."
  fi
}

create_api_config() {
  log "Creating API config ${CONFIG_ID}"
  gcloud api-gateway api-configs create "$CONFIG_ID" \
    --api="${GATEWAY_ID}" \
    --openapi-spec="$TMP_SPEC" \
    --project="$PROJECT_ID" \
    --backend-auth-service-account="$SERVICE_ACCOUNT" \
    --format=json >/tmp/${CONFIG_ID}.json
  CONFIG_CREATED=1
}

upsert_gateway() {
  PREVIOUS_CONFIG=$(gcloud api-gateway gateways describe "$GATEWAY_ID" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --format="value(apiConfig)" 2>/dev/null || true)
  if [[ -z "$PREVIOUS_CONFIG" ]]; then
    log "Creating gateway ${GATEWAY_ID}"
    gcloud api-gateway gateways create "$GATEWAY_ID" \
      --location="$REGION" \
      --api="$GATEWAY_ID" \
      --api-config="$CONFIG_ID" \
      --project="$PROJECT_ID"
    GATEWAY_CREATED=1
  else
    log "Updating gateway ${GATEWAY_ID} from ${PREVIOUS_CONFIG} to ${CONFIG_ID}"
    gcloud api-gateway gateways update "$GATEWAY_ID" \
      --location="$REGION" \
      --api-config="$CONFIG_ID" \
      --project="$PROJECT_ID"
    GATEWAY_CONFIG_UPDATED=1
  fi
}

await_endpoint() {
  log "Waiting for gateway endpoint"
  for _ in {1..30}; do
    ENDPOINT=$(gcloud api-gateway gateways describe "$GATEWAY_ID" \
      --location="$REGION" \
      --project="$PROJECT_ID" \
      --format="value(defaultHostname)" 2>/dev/null || true)
    if [[ -n "$ENDPOINT" ]]; then
      log "Gateway endpoint resolved: https://${ENDPOINT}"
      return
    fi
    sleep 5
  done
  fail "Gateway endpoint not available after waiting."
}

check_gateway_health() {
  log "Running gateway health checks"
  local base_url="https://${ENDPOINT}"
  local headers=(-H "X-Tenant-ID: ${SMOKE_TENANT_ID}")
  if [[ -n "$ACCESS_TOKEN" ]]; then
    headers+=(-H "Authorization: Bearer ${ACCESS_TOKEN}")
  else
    warn "ACCESS_TOKEN not provided; health checks will run without authentication."
  fi
  local checks=(
    "GET|/ready|Gateway readiness"
    "GET|/health|Gateway health"
  )
  local fail_count=0
  for check in "${checks[@]}"; do
    IFS='|' read -r method path label <<<"$check"
    log "Verifying ${label} (${method} ${path})"
    if ! curl -fsS -X "$method" "${headers[@]}" "${base_url}${path}" >/dev/null; then
      warn "Health check failed for ${label}."
      fail_count=$((fail_count + 1))
    fi
  done
  if (( fail_count > 0 )); then
    fail "Gateway health checks failed."
  fi
}

route_smoke_tests() {
  if [[ ! -x scripts/test_gateway_routing.sh ]]; then
    warn "scripts/test_gateway_routing.sh not executable; skipping routing smoke tests."
    return
  fi
  log "Executing routing smoke tests"
  scripts/test_gateway_routing.sh \
    --endpoint "https://${ENDPOINT}" \
    --project "$PROJECT_ID" \
    --environment "$ENVIRONMENT" \
    --token "$ACCESS_TOKEN" \
    --tenant "$SMOKE_TENANT_ID" \
    --mode smoke
}

main() {
  gcloud config set project "$PROJECT_ID" >/dev/null
  ensure_services
  ensure_gateway_api
  validate_oauth_secrets
  validate_cloud_run_services
  validate_service_account_bindings
  render_openapi_spec
  create_api_config
  upsert_gateway
  await_endpoint
  check_gateway_health
  route_smoke_tests
  log "Deployment successful"
}

main "$@"
