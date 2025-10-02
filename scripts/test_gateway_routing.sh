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
    fail "Required command '$1' not found"
  fi
}

ENDPOINT="${ENDPOINT:-}"
PROJECT_ID="${PROJECT_ID:-}"
ENVIRONMENT="${ENVIRONMENT:-staging}"
TENANT_ID="${TENANT_ID:-smoke-test}"
TOKEN="${TOKEN:-}"
API_KEY="${API_KEY:-}"
MODE="${MODE:-smoke}" # smoke or full
PAYLOAD_ROOT="${PAYLOAD_ROOT:-docs/test-payloads}"
REQUEST_TIMEOUT="${REQUEST_TIMEOUT:-30}"
TRACE_ID="${TRACE_ID:-00000000000000000000000000000000/1;o=1}"
RESULTS=()
LATENCIES=()

usage() {
  cat <<USAGE
Usage: $0 --endpoint https://gateway-host [--tenant TENANT] [--token TOKEN] [--mode smoke|full]
Options:
  --endpoint URL      Gateway base URL (required)
  --tenant ID         Tenant identifier for authenticated requests (default: smoke-test)
  --token TOKEN       Bearer token used for authenticated requests
  --api-key KEY       API key associated with the tenant (required when auth headers used)
  --mode MODE         Test mode: smoke (health only) or full (default: smoke)
  --payload-root DIR  Directory containing JSON payload overrides (default: docs/test-payloads)
  --trace-id TRACE    Custom X-Cloud-Trace-Context header value
  --timeout SECONDS   Request timeout (default: 30)
  -h, --help          Show this help message
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --endpoint)
      ENDPOINT="$2"; shift 2 ;;
    --tenant)
      TENANT_ID="$2"; shift 2 ;;
    --token)
      TOKEN="$2"; shift 2 ;;
    --api-key)
      API_KEY="$2"; shift 2 ;;
    --mode)
      MODE="$2"; shift 2 ;;
    --payload-root)
      PAYLOAD_ROOT="$2"; shift 2 ;;
    --trace-id)
      TRACE_ID="$2"; shift 2 ;;
    --timeout)
      REQUEST_TIMEOUT="$2"; shift 2 ;;
    --project)
      PROJECT_ID="$2"; shift 2 ;;
    --environment)
      ENVIRONMENT="$2"; shift 2 ;;
    -h|--help)
      usage
      exit 0 ;;
    *)
      fail "Unknown argument: $1" ;;
  esac
done

if [[ -z "$ENDPOINT" ]]; then
  fail "--endpoint is required"
fi

require_command curl
require_command jq
require_command python3

if [[ -n "$TOKEN" && -z "$API_KEY" ]]; then
  fail "--api-key is required when --token is provided"
fi

log "Routing validation target: ${ENDPOINT} (tenant=${TENANT_ID}, mode=${MODE})"

read_payload() {
  local key="$1"
  local file="${PAYLOAD_ROOT}/${key}.json"
  if [[ -f "$file" ]]; then
    cat "$file"
    return
  fi
  case "$key" in
    embeddings-generate)
      printf '{"text":"routing smoke payload"}' ;;
    embeddings-upsert)
      printf '{"id":"probe","vector":[0.01,0.02,0.03],"metadata":{"routing":"true"}}' ;;
    embeddings-query)
      printf '{"text":"routing smoke payload","limit":1}' ;;
    search-hybrid)
      printf '{"query":"Routing smoke","limit":1}' ;;
    search-rerank)
      printf '{"query":"Routing smoke","items":[{"id":"1","score":0.1}]}' ;;
    evidence-get)
      printf '' ;;
    eco-search)
      printf '' ;;
    enrich-run)
      printf '{"payload":"routing"}' ;;
    admin-snapshots)
      printf '' ;;
    msgs-expand)
      printf '{"skill":"python"}' ;;
    msgs-roles)
      printf '{"role":"engineer"}' ;;
    msgs-market)
      printf '' ;;
    *)
      printf '{"probe":true}' ;;
  esac
}

add_result() {
  RESULTS+=("{\"description\":\"${1//"/\"}\",\"status\":\"${2}\",\"httpStatus\":${3},\"latencyMs\":${4}}")
}

invoke() {
  local method="$1"
  local path="$2"
  local expected_status="$3"
  local payload_key="$4"
  local description="$5"
  local tenant="$6"
  local url="${ENDPOINT}${path}"
  local payload
  payload=$(read_payload "$payload_key")
  local headers=(-H "X-Tenant-ID: ${tenant}" -H "X-Request-ID: routing-${RANDOM}" -H "X-Cloud-Trace-Context: ${TRACE_ID}")
  if [[ -n "$API_KEY" ]]; then
    headers+=(-H "X-API-Key: ${API_KEY}")
  fi
  if [[ -n "$TOKEN" ]]; then
    headers+=(-H "Authorization: Bearer ${TOKEN}")
  fi
  local start_ms end_ms duration
  start_ms=$(python3 - <<'PY'
import time
print(int(time.time()*1000))
PY
)
  local response status_code=0
  local curl_cmd=(curl -sS -X "$method" "$url" -H 'Content-Type: application/json' "${headers[@]}" -D /tmp/routing-headers.$$ -o /tmp/routing-body.$$ -w '%{http_code}' --max-time "$REQUEST_TIMEOUT")
  if [[ "$method" != "GET" && "$method" != "DELETE" ]]; then
    curl_cmd+=(--data "$payload")
  fi
  response=$("${curl_cmd[@]}") || status_code=$?
  end_ms=$(python3 - <<'PY'
import time
print(int(time.time()*1000))
PY
)
  duration=$(( end_ms - start_ms ))
  LATENCIES+=("$duration")
  if [[ "$status_code" -ne 0 ]]; then
    warn "Curl error ${status_code} for ${description}"
    add_result "$description" "error" 0 "$duration"
    rm -f /tmp/routing-headers.$$ /tmp/routing-body.$$
    return 1
  fi
  local http_code="$response"
  if [[ "$http_code" != "$expected_status" ]]; then
    warn "${description} expected HTTP ${expected_status} but received ${http_code}"
    warn "Response body: $(cat /tmp/routing-body.$$)"
    add_result "$description" "fail" "$http_code" "$duration"
    rm -f /tmp/routing-headers.$$ /tmp/routing-body.$$
    return 1
  fi
  add_result "$description" "pass" "$http_code" "$duration"
  rm -f /tmp/routing-headers.$$ /tmp/routing-body.$$
  return 0
}

# Smoke checks for service health endpoints
SMOKE_CHECKS=(
  "GET|/health|200|health-probe|Gateway health"
  "GET|/ready|200|health-probe|Gateway readiness"
)

FULL_CHECKS=(
  "POST|/v1/embeddings/generate|200|embeddings-generate|Embeddings generate"
  "POST|/v1/embeddings/upsert|200|embeddings-upsert|Embeddings upsert"
  "POST|/v1/embeddings/query|200|embeddings-query|Embeddings query"
  "POST|/v1/search/hybrid|200|search-hybrid|Hybrid search"
  "POST|/v1/search/rerank|200|search-rerank|Rerank search"
  "GET|/v1/evidence/test-candidate|200|evidence-get|Evidence fetch"
  "GET|/v1/occupations/search?title=engineer|200|eco-search|ECO search"
  "POST|/v1/enrich/profile|202|enrich-run|Enrichment run"
  "GET|/v1/admin/snapshots|200|admin-snapshots|Admin snapshots"
  "POST|/v1/skills/expand|200|msgs-expand|MSGS expand"
  "POST|/v1/roles/template|200|msgs-roles|MSGS roles template"
  "GET|/v1/market/demand?skillId=python|200|msgs-market|MSGS market demand"
)

run_checks() {
  local -n checks_ref="$1"
  local failures=0
  for entry in "${checks_ref[@]}"; do
    IFS='|' read -r method path expected payload_key description <<<"$entry"
    if ! invoke "$method" "$path" "$expected" "$payload_key" "$description" "$TENANT_ID"; then
      failures=$((failures + 1))
    fi
  done
  return $failures
}

cross_tenant_validation() {
  if [[ -z "$TOKEN" ]]; then
    warn "Skipping tenant isolation check (token not provided)"
    return 0
  fi
  log "Validating tenant isolation"
  if invoke "POST" "/v1/search/hybrid" "403" "search-hybrid" "Cross-tenant rejection" "${TENANT_ID}-isolation"; then
    return 0
  fi
  return 1
}

error_propagation_check() {
  log "Validating error propagation on missing resource"
  if invoke "GET" "/v1/evidence/non-existent" "404" "evidence-get" "Missing evidence returns 404" "$TENANT_ID"; then
    return 0
  fi
  return 1
}

pipeline_check() {
  log "Validating search pipeline request chain"
  if [[ "$MODE" != "full" ]]; then
    warn "Skipping pipeline validation in smoke mode"
    return 0
  fi
  local success=0
  if invoke "POST" "/v1/enrich/profile" "202" "enrich-run" "Pipeline enrichment" "$TENANT_ID" &&
     invoke "POST" "/v1/embeddings/generate" "200" "embeddings-generate" "Pipeline embeddings" "$TENANT_ID" &&
     invoke "POST" "/v1/search/hybrid" "200" "search-hybrid" "Pipeline hybrid search" "$TENANT_ID" &&
     invoke "POST" "/v1/search/rerank" "200" "search-rerank" "Pipeline rerank" "$TENANT_ID" &&
     invoke "GET" "/v1/evidence/test-candidate" "200" "evidence-get" "Pipeline evidence" "$TENANT_ID"; then
    success=1
  fi
  if (( success == 1 )); then
    return 0
  fi
  return 1
}

main() {
  local failures=0
  case "$MODE" in
    smoke)
      run_checks SMOKE_CHECKS || failures=$((failures + 1)) ;;
    full)
      run_checks SMOKE_CHECKS || failures=$((failures + 1))
      run_checks FULL_CHECKS || failures=$((failures + 1)) ;;
    *)
      fail "Unknown mode: ${MODE}"
  esac
  cross_tenant_validation || failures=$((failures + 1))
  error_propagation_check || failures=$((failures + 1))
  pipeline_check || failures=$((failures + 1))

  local latency_json
  latency_json=$(printf '%s\n' "${LATENCIES[@]}" | jq -s 'map(tonumber)')
  if [[ -n "$latency_json" ]]; then
    local stats
    stats=$(python3 - <<'PY' "$latency_json"
import json
import sys
latencies = json.loads(sys.argv[1])
if not latencies:
    print('{}')
    sys.exit(0)
latencies.sort()
count = len(latencies)
p95_index = int(round(0.95 * (count - 1)))
summary = {
    "count": count,
    "p95": latencies[p95_index],
    "max": max(latencies),
    "avg": sum(latencies)/count,
}
print(json.dumps(summary))
PY
)
    log "Latency summary: ${stats}"
  fi

  printf '%s\n' "${RESULTS[@]}" | jq -s '.'

  if (( failures > 0 )); then
    fail "Routing validation detected ${failures} failures"
  fi
  log "Routing validation passed"
}

main "$@"
