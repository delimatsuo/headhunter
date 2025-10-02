#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

usage() {
  cat <<'USAGE'
Usage: scripts/smoke-test-deployment.sh [options]

Runs smoke and integration tests against the production gateway.

Options:
  --project-id <id>        Google Cloud project ID
  --environment <env>      Deployment environment label (default: production)
  --gateway-endpoint <url> Gateway base URL (https://...)
  --gateway-id <id>        Gateway identifier (default: headhunter-api-gateway-<env>)
  --manifest <path>        Deployment manifest for context (optional)
  --tenant-id <id>         Tenant identifier used for authenticated tests (default: smoke-test)
  --oauth-token <token>    Pre-issued OAuth token to reuse
  --api-key <key>          API key associated with the tenant
  --mode <quick|full>      Scope of tests to execute (default: quick)
  --report-file <path>     Custom report output path (JSON)
  -h, --help               Show this help message
USAGE
}

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

to_env_key() {
  local name="$1"
  name="${name//-/_}"
  printf '%s' "${name^^}"
}

PROJECT_ID="${PROJECT_ID:-}"
ENVIRONMENT="${ENVIRONMENT:-production}"
GATEWAY_ENDPOINT=""
GATEWAY_ID=""
DEPLOYMENT_MANIFEST=""
TENANT_ID="smoke-test"
OAUTH_TOKEN=""
API_KEY_VALUE=""
MODE="quick"
REPORT_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      PROJECT_ID="$2"; shift 2 ;;
    --environment)
      ENVIRONMENT="$2"; shift 2 ;;
    --gateway-endpoint)
      GATEWAY_ENDPOINT="$2"; shift 2 ;;
    --gateway-id)
      GATEWAY_ID="$2"; shift 2 ;;
    --manifest)
      DEPLOYMENT_MANIFEST="$2"; shift 2 ;;
    --tenant-id)
      TENANT_ID="$2"; shift 2 ;;
    --oauth-token)
      OAUTH_TOKEN="$2"; shift 2 ;;
    --api-key)
      API_KEY_VALUE="$2"; shift 2 ;;
    --mode)
      MODE="$2"; shift 2 ;;
    --report-file)
      REPORT_FILE="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      fail "Unknown argument: $1" ;;
  esac
done

MODE="${MODE,,}"
if [[ "$MODE" != "quick" && "$MODE" != "full" ]]; then
  fail "--mode must be quick or full"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

require_command gcloud
require_command jq
require_command curl
require_command python3

CONFIG_FILE="config/infrastructure/headhunter-${ENVIRONMENT}.env"
if [[ ! -f "$CONFIG_FILE" ]]; then
  if [[ "$ENVIRONMENT" != "production" ]]; then
    warn "Configuration file ${CONFIG_FILE} not found; falling back to production config."
  fi
  CONFIG_FILE="config/infrastructure/headhunter-production.env"
fi
if [[ ! -f "$CONFIG_FILE" ]]; then
  fail "Infrastructure configuration file not found."
fi

CLI_PROJECT_ID="$PROJECT_ID"
set -a
source "$CONFIG_FILE"
set +a
if [[ -n "$CLI_PROJECT_ID" ]]; then
  PROJECT_ID="$CLI_PROJECT_ID"
fi
if [[ -z "$PROJECT_ID" ]]; then
  fail "Project ID could not be determined. Provide via --project-id or config."
fi

REGION="${REGION:-us-central1}"
if [[ -z "$GATEWAY_ID" ]]; then
  GATEWAY_ID="headhunter-api-gateway-${ENVIRONMENT}"
fi

declare -A SERVICE_URLS
if [[ -n "$DEPLOYMENT_MANIFEST" && -f "$DEPLOYMENT_MANIFEST" ]]; then
  for svc in hh-embed-svc hh-search-svc hh-rerank-svc hh-evidence-svc hh-eco-svc hh-msgs-svc hh-admin-svc hh-enrich-svc; do
    url=$(jq -r --arg svc "$svc" '.services[] | select(.service==$svc) | .url // empty' "$DEPLOYMENT_MANIFEST" 2>/dev/null || true)
    if [[ -n "$url" ]]; then
      SERVICE_URLS[$svc]="$url"
    fi
  done
fi

if [[ -z "$GATEWAY_ENDPOINT" ]]; then
  gateway_host=$(gcloud api-gateway gateways describe "$GATEWAY_ID" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --format="value(defaultHostname)" 2>/dev/null || true)
  if [[ -n "$gateway_host" ]]; then
    GATEWAY_ENDPOINT="https://${gateway_host}"
  fi
fi

if [[ -z "$GATEWAY_ENDPOINT" ]]; then
  fail "Gateway endpoint could not be resolved; provide --gateway-endpoint."
fi

log "Running smoke tests against ${GATEWAY_ENDPOINT} (env=${ENVIRONMENT}, tenant=${TENANT_ID}, mode=${MODE})"

DEPLOYMENT_DIR="${PROJECT_ROOT}/.deployment"
TEST_REPORT_DIR="${DEPLOYMENT_DIR}/test-reports"
TEST_LOG_DIR="${DEPLOYMENT_DIR}/test-logs"
mkdir -p "$TEST_REPORT_DIR" "$TEST_LOG_DIR"
TIMESTAMP="$(date -u +'%Y%m%d-%H%M%S')"
DEFAULT_REPORT="${TEST_REPORT_DIR}/smoke-test-report-${TIMESTAMP}.json"
if [[ -z "$REPORT_FILE" ]]; then
  REPORT_FILE="$DEFAULT_REPORT"
fi

TOKEN_ACQUIRED=false
API_KEY_ACQUIRED=false

resolve_oauth_token() {
  if [[ -n "$OAUTH_TOKEN" ]]; then
    TOKEN_ACQUIRED=true
    return 0
  fi
  local secret_name="oauth-client-${TENANT_ID}"
  local secret_payload
  secret_payload=$(gcloud secrets versions access latest --project "$PROJECT_ID" --secret "$secret_name" 2>/dev/null || true)
  if [[ -z "$secret_payload" ]]; then
    warn "OAuth client secret ${secret_name} not found; authenticated tests will be skipped."
    return 1
  fi
  local client_id client_secret token_uri audience scope
  client_id=$(echo "$secret_payload" | jq -r '.client_id // .clientId // empty')
  client_secret=$(echo "$secret_payload" | jq -r '.client_secret // .clientSecret // empty')
  token_uri=$(echo "$secret_payload" | jq -r '.token_uri // .tokenUri // empty')
  audience=$(echo "$secret_payload" | jq -r '.audience // empty')
  scope=$(echo "$secret_payload" | jq -r '.scope // empty')
  if [[ -z "$token_uri" ]]; then
    token_uri="https://idp.${ENVIRONMENT}.ella.jobs/oauth/token"
  fi
  if [[ -z "$client_id" || -z "$client_secret" || -z "$token_uri" ]]; then
    warn "OAuth client secret incomplete; authenticated tests will be skipped."
    return 1
  fi
  local data=("grant_type=client_credentials" "client_id=${client_id}" "client_secret=${client_secret}")
  if [[ -n "$audience" && "$audience" != "null" ]]; then
    data+=("audience=${audience}")
  fi
  if [[ -n "$scope" && "$scope" != "null" ]]; then
    data+=("scope=${scope}")
  fi
  local response
  if ! response=$(curl -fsS -X POST "$token_uri" -H 'Content-Type: application/x-www-form-urlencoded' -d "${data[*]}" 2>/dev/null); then
    warn "Failed to acquire OAuth token from ${token_uri}."
    return 1
  fi
  local token
  token=$(echo "$response" | jq -r '.access_token // empty')
  if [[ -z "$token" ]]; then
    warn "OAuth token response missing access_token."
    return 1
  fi
  OAUTH_TOKEN="$token"
  TOKEN_ACQUIRED=true
  return 0
}

resolve_api_key() {
  if [[ -n "$API_KEY_VALUE" ]]; then
    API_KEY_ACQUIRED=true
    return 0
  fi
  local secret_name="gateway-api-key-${TENANT_ID}"
  local secret_value
  secret_value=$(gcloud secrets versions access latest --project "$PROJECT_ID" --secret "$secret_name" 2>/dev/null || true)
  if [[ -z "$secret_value" ]]; then
    warn "Gateway API key secret ${secret_name} not found; authenticated tests will be skipped."
    return 1
  fi
  API_KEY_VALUE="$(echo "$secret_value" | tr -d '\r\n')"
  API_KEY_ACQUIRED=true
  return 0
}

resolve_oauth_token || true
resolve_api_key || true

AUTH_READY=false
if [[ "$TOKEN_ACQUIRED" == true && "$API_KEY_ACQUIRED" == true ]]; then
  AUTH_READY=true
fi

RESULTS=()
LATENCIES_MS=()
TEST_COUNTER=0
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

append_result() {
  local name="$1"
  local status="$2"
  local http_code="$3"
  local duration_ms="$4"
  local notes="$5"
  RESULTS+=("{\"name\":\"${name//"/\"}\",\"status\":\"${status}\",\"httpStatus\":${http_code},\"durationMs\":${duration_ms},\"notes\":\"${notes//"/\"}\"}")
  if [[ "$status" == "pass" ]]; then
    PASS_COUNT=$((PASS_COUNT + 1))
    LATENCIES_MS+=("$duration_ms")
  elif [[ "$status" == "fail" ]]; then
    FAIL_COUNT=$((FAIL_COUNT + 1))
  else
    SKIP_COUNT=$((SKIP_COUNT + 1))
  fi
  TEST_COUNTER=$((TEST_COUNTER + 1))
}

now_ms() {
  python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
}

invoke_gateway() {
  local name="$1"
  local method="$2"
  local path="$3"
  local expected="$4"
  local payload="$5"
  local require_auth="$6"

  if [[ "$require_auth" == "true" && "$AUTH_READY" != true ]]; then
    append_result "$name" "skipped" 0 0 "authentication not available"
    return
  fi

  local url="${GATEWAY_ENDPOINT}${path}"
  local response_file
  response_file="$(mktemp)"
  local header_args=(-H "X-Tenant-ID: ${TENANT_ID}" -H "X-Request-ID: smoke-${RANDOM}" -H "Content-Type: application/json")
  if [[ "$require_auth" == "true" ]]; then
    header_args+=(-H "Authorization: Bearer ${OAUTH_TOKEN}" -H "X-API-Key: ${API_KEY_VALUE}")
  fi

  local start_ms end_ms duration_ms curl_status
  start_ms=$(now_ms)
  if [[ -n "$payload" ]]; then
    printf '%s' "$payload" >"$response_file.payload"
  fi
  local curl_args=(-sS -X "$method" "$url" -D "$response_file.headers" -o "$response_file" -w '%{http_code} %{time_total}' --connect-timeout 10 --max-time 60)
  for header in "${header_args[@]}"; do
    curl_args+=(-H "$header")
  done
  if [[ -n "$payload" ]]; then
    curl_args+=(-d "@$response_file.payload")
  fi
  local output
  if ! output=$(curl "${curl_args[@]}" 2>/dev/null); then
    end_ms=$(now_ms)
    duration_ms=$((end_ms - start_ms))
    append_result "$name" "fail" 0 "$duration_ms" "curl execution failed"
    rm -f "$response_file" "$response_file.payload" "$response_file.headers" 2>/dev/null || true
    return
  fi
  read -r http_code time_total <<<"$output"
  end_ms=$(now_ms)
  duration_ms=$((end_ms - start_ms))
  local notes=""
  if [[ "$http_code" == "$expected" ]]; then
    append_result "$name" "pass" "$http_code" "$duration_ms" "$notes"
  else
    notes="expected ${expected}"
    append_result "$name" "fail" "$http_code" "$duration_ms" "$notes"
  fi
  rm -f "$response_file" "$response_file.payload" "$response_file.headers" 2>/dev/null || true
}

health_tests() {
  invoke_gateway "Gateway health" "GET" "/health" 200 "" "false"
  invoke_gateway "Gateway readiness" "GET" "/ready" 200 "" "false"
}

service_payload() {
  local key="$1"
  case "$key" in
    embed-generate)
      printf '{"text":"smoke test payload"}' ;;
    search-hybrid)
      printf '{"query":"smoke test","limit":1}' ;;
    search-rerank)
      printf '{"query":"smoke test","items":[{"id":"1","score":0.5}]}' ;;
    evidence-get)
      printf '' ;;
    eco-search)
      printf '' ;;
    msgs-expand)
      printf '{"skill":"python"}' ;;
    admin-snapshots)
      printf '' ;;
    enrich-profile)
      printf '{"profile":{"name":"Smoke Test"}}' ;;
    msgs-market)
      printf '{"market":"Austin"}' ;;
    *)
      printf '' ;;
  esac
}

service_tests() {
  invoke_gateway "Embeddings generate" "POST" "/v1/embeddings/generate" 200 "$(service_payload embed-generate)" "true"
  invoke_gateway "Search hybrid" "POST" "/v1/search/hybrid" 200 "$(service_payload search-hybrid)" "true"
  if [[ "$MODE" == "full" ]]; then
    invoke_gateway "Search rerank" "POST" "/v1/search/rerank" 200 "$(service_payload search-rerank)" "true"
    invoke_gateway "Evidence fetch" "GET" "/v1/evidence/test-candidate" 200 "" "true"
    invoke_gateway "ECO search" "GET" "/v1/occupations/search?title=engineer" 200 "" "true"
    invoke_gateway "Messages expand" "POST" "/v1/skills/expand" 200 "$(service_payload msgs-expand)" "true"
    invoke_gateway "Admin snapshots" "GET" "/v1/admin/snapshots" 200 "" "true"
    invoke_gateway "Enrich profile" "POST" "/v1/enrich/profile" 200 "$(service_payload enrich-profile)" "true"
  fi
}

integration_tests() {
  if [[ "$MODE" != "full" ]]; then
    return
  fi
  if [[ "$AUTH_READY" != true ]]; then
    append_result "Full search pipeline" "skipped" 0 0 "authentication not available"
    append_result "Enrichment pipeline" "skipped" 0 0 "authentication not available"
    append_result "Admin refresh pipeline" "skipped" 0 0 "authentication not available"
    return
  fi
  local failed=0
  invoke_gateway "Pipeline embed" "POST" "/v1/embeddings/generate" 200 "$(service_payload embed-generate)" "true"
  if [[ ${RESULTS[-1]} != *'"status":"pass"'* ]]; then failed=1; fi
  invoke_gateway "Pipeline search" "POST" "/v1/search/hybrid" 200 "$(service_payload search-hybrid)" "true"
  if [[ ${RESULTS[-1]} != *'"status":"pass"'* ]]; then failed=1; fi
  invoke_gateway "Pipeline rerank" "POST" "/v1/search/rerank" 200 "$(service_payload search-rerank)" "true"
  if [[ ${RESULTS[-1]} != *'"status":"pass"'* ]]; then failed=1; fi
  invoke_gateway "Pipeline evidence" "GET" "/v1/evidence/test-candidate" 200 "" "true"
  if [[ ${RESULTS[-1]} != *'"status":"pass"'* ]]; then failed=1; fi
  append_result "Full search pipeline" "$([[ $failed -eq 0 ]] && echo pass || echo fail)" 0 0 "combined sequence"

  failed=0
  invoke_gateway "Pipeline enrich" "POST" "/v1/enrich/profile" 200 "$(service_payload enrich-profile)" "true"
  if [[ ${RESULTS[-1]} != *'"status":"pass"'* ]]; then failed=1; fi
  invoke_gateway "Pipeline embed (enrich)" "POST" "/v1/embeddings/generate" 200 "$(service_payload embed-generate)" "true"
  if [[ ${RESULTS[-1]} != *'"status":"pass"'* ]]; then failed=1; fi
  invoke_gateway "Pipeline evidence (enrich)" "GET" "/v1/evidence/test-candidate" 200 "" "true"
  if [[ ${RESULTS[-1]} != *'"status":"pass"'* ]]; then failed=1; fi
  append_result "Enrichment pipeline" "$([[ $failed -eq 0 ]] && echo pass || echo fail)" 0 0 "enrichment sequence"

  failed=0
  invoke_gateway "Pipeline admin" "GET" "/v1/admin/snapshots" 200 "" "true"
  if [[ ${RESULTS[-1]} != *'"status":"pass"'* ]]; then failed=1; fi
  append_result "Admin refresh pipeline" "$([[ $failed -eq 0 ]] && echo pass || echo fail)" 0 0 "admin sequence"
}

health_tests
service_tests
integration_tests

EXTERNAL_REPORTS=()

run_external_checks() {
  if [[ "$MODE" == "full" && "$AUTH_READY" == true ]]; then
    local routing_log="$TEST_LOG_DIR/gateway-routing-${TIMESTAMP}.log"
    if "$SCRIPT_DIR/test_gateway_routing.sh" --endpoint "$GATEWAY_ENDPOINT" --project "$PROJECT_ID" --environment "$ENVIRONMENT" --mode full --token "$OAUTH_TOKEN" --api-key "$API_KEY_VALUE" --tenant "$TENANT_ID" --timeout 45 --payload-root docs/test-payloads --trace-id "smoke-${TIMESTAMP}" >"$routing_log" 2>&1; then
      append_result "Gateway routing validation" "pass" 0 0 ""
    else
      append_result "Gateway routing validation" "fail" 0 0 "see ${routing_log}"
    fi
    local oauth_report="$TEST_LOG_DIR/oauth-validation-${TIMESTAMP}.json"
    if "$SCRIPT_DIR/test_oauth2_authentication.sh" --project "$PROJECT_ID" --endpoint "$GATEWAY_ENDPOINT" --tenant "$TENANT_ID" --report "$oauth_report" >"${oauth_report%.json}.log" 2>&1; then
      append_result "OAuth authentication validation" "pass" 0 0 ""
      EXTERNAL_REPORTS+=("$oauth_report")
    else
      append_result "OAuth authentication validation" "fail" 0 0 "see ${oauth_report%.json}.log"
    fi
    if [[ -x "$SCRIPT_DIR/test_rate_limiting.sh" ]]; then
      local rate_report="$TEST_LOG_DIR/rate-limit-${TIMESTAMP}.json"
      if "$SCRIPT_DIR/test_rate_limiting.sh" --endpoint "$GATEWAY_ENDPOINT" --token "$OAUTH_TOKEN" --api-key "$API_KEY_VALUE" --tenant "$TENANT_ID" --report "$rate_report" >"${rate_report%.json}.log" 2>&1; then
        append_result "Rate limiting validation" "pass" 0 0 ""
      else
        append_result "Rate limiting validation" "fail" 0 0 "see ${rate_report%.json}.log"
      fi
    fi
  fi
}

run_external_checks

TOTAL_TESTS=$TEST_COUNTER
SUCCESS_RATE=0
if (( TOTAL_TESTS > 0 )); then
  SUCCESS_RATE=$((PASS_COUNT * 100 / TOTAL_TESTS))
fi

LATENCY_METRICS="{}"
if (( ${#LATENCIES_MS[@]} > 0 )); then
  LATENCY_METRICS=$(printf '%s\n' "${LATENCIES_MS[@]}" | python3 - <<'PY'
import json
import math
import sys
values = [int(line.strip()) for line in sys.stdin if line.strip()]
values.sort()
def percentile(data, pct):
    if not data:
        return 0
    k = (len(data) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return data[int(k)]
    d0 = data[int(f)] * (c - k)
    d1 = data[int(c)] * (k - f)
    return int(d0 + d1)
summary = {
    "count": len(values),
    "min": values[0],
    "max": values[-1],
    "p50": percentile(values, 50),
    "p95": percentile(values, 95),
    "p99": percentile(values, 99),
}
print(json.dumps(summary))
PY
)
fi

printf '%s\n' "${RESULTS[@]}" >"$TEST_LOG_DIR/smoke-tests-${TIMESTAMP}.log"

REPORT_OUTPUT=$(printf '%s\n' "${RESULTS[@]}" | python3 - <<'PY' "$REPORT_FILE" "$PROJECT_ID" "$ENVIRONMENT" "$GATEWAY_ENDPOINT" "$TENANT_ID" "$MODE" "$SUCCESS_RATE" "$LATENCY_METRICS")
import json
import sys
from datetime import datetime

report_path, project_id, environment, endpoint, tenant, mode, success_rate, latency_metrics = sys.argv[1:9]
results = []
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    results.append(json.loads(line))
latency = json.loads(latency_metrics)
summary = {
    "generatedAt": datetime.utcnow().isoformat() + 'Z',
    "projectId": project_id,
    "environment": environment,
    "gatewayEndpoint": endpoint,
    "tenant": tenant,
    "mode": mode,
    "totals": {
        "tests": len(results),
        "successRate": int(success_rate),
        "passed": sum(1 for r in results if r['status'] == 'pass'),
        "failed": sum(1 for r in results if r['status'] == 'fail'),
        "skipped": sum(1 for r in results if r['status'] == 'skipped'),
    },
    "latency": latency,
    "results": results,
}
with open(report_path, 'w', encoding='utf-8') as fh:
    json.dump(summary, fh, indent=2)
print(report_path)
PY

REPORT_PATH="${REPORT_OUTPUT##*$'\n'}"
log "Smoke test report saved to ${REPORT_PATH}"
log "Tests: ${PASS_COUNT} passed, ${FAIL_COUNT} failed, ${SKIP_COUNT} skipped (success rate ${SUCCESS_RATE}%)"

if (( FAIL_COUNT > 0 )); then
  exit 1
fi
exit 0
