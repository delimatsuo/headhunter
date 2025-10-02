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
    fail "Command '$1' not available"
  fi
}

ENDPOINT="${ENDPOINT:-}"
PRIMARY_TENANT="${PRIMARY_TENANT:-smoke-test}"
SECONDARY_TENANT="${SECONDARY_TENANT:-}" # optional for isolation test
TOKEN="${TOKEN:-}"
SECONDARY_TOKEN="${SECONDARY_TOKEN:-}" # optional
API_KEY="${API_KEY:-}"
SECONDARY_API_KEY="${SECONDARY_API_KEY:-}"
HYBRID_LIMIT="${HYBRID_LIMIT:-30}"
RERANK_LIMIT="${RERANK_LIMIT:-10}"
GLOBAL_LIMIT="${GLOBAL_LIMIT:-50}"
WINDOW_SECONDS="${WINDOW_SECONDS:-60}"
PAYLOAD_HYBRID='{"query":"rate limit probe","limit":1}'
PAYLOAD_RERANK='{"query":"rate limit probe","items":[{"id":"1","score":0.1}]}'
PAYLOAD_EMBED='{"text":"rate limit probe"}'
REPORT_FILE="${REPORT_FILE:-}"

usage() {
  cat <<USAGE
Usage: $0 --endpoint https://gateway-host --token TOKEN [options]

Options:
  --endpoint URL             Gateway base URL (required)
  --token TOKEN              Access token for primary tenant (required)
  --api-key KEY              API key associated with the tenant (required)
  --tenant TENANT            Primary tenant identifier (default smoke-test)
  --secondary-tenant TENANT  Secondary tenant for isolation test
  --secondary-token TOKEN    Token for secondary tenant
  --secondary-api-key KEY    API key for secondary tenant
  --hybrid-limit N           Expected per-tenant hybrid RPS limit (default 30)
  --rerank-limit N           Expected per-tenant rerank RPS limit (default 10)
  --global-limit N           Expected per-tenant global RPS limit (default 50)
  --window SECONDS           Rate limit window seconds (default 60)
  --report FILE              Optional JSON report output file
  -h, --help                 Show this help message
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --endpoint)
      ENDPOINT="$2"; shift 2 ;;
    --token)
      TOKEN="$2"; shift 2 ;;
    --tenant)
      PRIMARY_TENANT="$2"; shift 2 ;;
    --secondary-tenant)
      SECONDARY_TENANT="$2"; shift 2 ;;
    --secondary-token)
      SECONDARY_TOKEN="$2"; shift 2 ;;
    --api-key)
      API_KEY="$2"; shift 2 ;;
    --secondary-api-key)
      SECONDARY_API_KEY="$2"; shift 2 ;;
    --hybrid-limit)
      HYBRID_LIMIT="$2"; shift 2 ;;
    --rerank-limit)
      RERANK_LIMIT="$2"; shift 2 ;;
    --global-limit)
      GLOBAL_LIMIT="$2"; shift 2 ;;
    --window)
      WINDOW_SECONDS="$2"; shift 2 ;;
    --report)
      REPORT_FILE="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      fail "Unknown argument: $1" ;;
  esac
done

if [[ -z "$ENDPOINT" || -z "$TOKEN" || -z "$API_KEY" ]]; then
  fail "--endpoint, --token, and --api-key are required"
fi

require_command curl
require_command jq
require_command python3

HYBRID_PATH="${ENDPOINT}/v1/search/hybrid"
RERANK_PATH="${ENDPOINT}/v1/search/rerank"
EMBED_PATH="${ENDPOINT}/v1/embeddings/generate"

RESULTS=()
add_result() {
  RESULTS+=("{\"test\":\"${1//"/\"}\",\"status\":\"${2}\",\"successCount\":${3},\"rateLimited\":${4},\"unexpected\":${5},\"retryAfter\":\"${6}\"}")
}

invoke_loop() {
  local method="$1"
  local url="$2"
  local payload="$3"
  local tenant="$4"
  local token="$5"
  local api_key="$6"
  local iterations="$7"
  local expect429="$8"
  local successes=0
  local rate429=0
  local unexpected=0
  local retry_after=""
  for ((i=1;i<=iterations;i++)); do
    local status
    local headers_file="/tmp/rate-headers-${RANDOM}.txt"
    status=$(curl -sS -o /dev/null -D "$headers_file" -w '%{http_code}' -X "$method" "$url" \
      -H 'Content-Type: application/json' \
      -H "Authorization: Bearer ${token}" \
      -H "X-Tenant-ID: ${tenant}" \
      -H "X-API-Key: ${api_key}" \
      --data "$payload") || status="curl-error"
    if [[ "$status" == "200" ]]; then
      successes=$((successes + 1))
    elif [[ "$status" == "429" ]]; then
      rate429=$((rate429 + 1))
      local retry
      retry=$(grep -i '^Retry-After:' "$headers_file" | awk '{print $2}' | tr -d '\r')
      if [[ -n "$retry" ]]; then
        retry_after="$retry"
      fi
    else
      unexpected=$((unexpected + 1))
    fi
    rm -f "$headers_file"
  done
  if [[ "$expect429" == "yes" && $rate429 -eq 0 ]]; then
    warn "Expected to hit rate limit but no 429 responses observed"
  fi
  add_result "$9" "completed" "$successes" "$rate429" "$unexpected" "$retry_after"
  if [[ "$expect429" == "yes" && $rate429 -eq 0 ]]; then
    return 1
  fi
  if [[ "$expect429" == "no" && $rate429 -gt 0 ]]; then
    warn "Unexpected 429 responses during warmup"
    return 1
  fi
  return 0
}

sleep_window() {
  log "Sleeping ${WINDOW_SECONDS}s for quota window reset"
  sleep "$WINDOW_SECONDS"
}

main() {
  local failures=0

  log "Warmup hybrid requests below threshold"
  invoke_loop POST "$HYBRID_PATH" "$PAYLOAD_HYBRID" "$PRIMARY_TENANT" "$TOKEN" "$API_KEY" $((HYBRID_LIMIT/2)) no "hybrid-warmup" || failures=$((failures + 1))

  sleep_window

  log "Triggering hybrid rate limit (expected ${HYBRID_LIMIT})"
  invoke_loop POST "$HYBRID_PATH" "$PAYLOAD_HYBRID" "$PRIMARY_TENANT" "$TOKEN" "$API_KEY" $((HYBRID_LIMIT + 5)) yes "hybrid-limit" || failures=$((failures + 1))

  sleep_window

  log "Warmup rerank requests below threshold"
  invoke_loop POST "$RERANK_PATH" "$PAYLOAD_RERANK" "$PRIMARY_TENANT" "$TOKEN" "$API_KEY" $((RERANK_LIMIT/2)) no "rerank-warmup" || failures=$((failures + 1))

  sleep_window

  log "Triggering rerank rate limit (expected ${RERANK_LIMIT})"
  invoke_loop POST "$RERANK_PATH" "$PAYLOAD_RERANK" "$PRIMARY_TENANT" "$TOKEN" "$API_KEY" $((RERANK_LIMIT + 5)) yes "rerank-limit" || failures=$((failures + 1))

  sleep_window

  log "Testing global per-tenant limit across endpoints"
  local global_iterations=$((GLOBAL_LIMIT + 10))
  local hybrid_share=$((global_iterations / 2))
  local rerank_share=$((global_iterations - hybrid_share))
  invoke_loop POST "$HYBRID_PATH" "$PAYLOAD_HYBRID" "$PRIMARY_TENANT" "$TOKEN" "$API_KEY" "$hybrid_share" no "global-hybrid-phase" || true
  invoke_loop POST "$RERANK_PATH" "$PAYLOAD_RERANK" "$PRIMARY_TENANT" "$TOKEN" "$API_KEY" "$rerank_share" yes "global-limit" || failures=$((failures + 1))

  sleep_window

  log "Testing tenant isolation"
  if [[ -n "$SECONDARY_TENANT" ]]; then
    if [[ -z "$SECONDARY_TOKEN" ]]; then
      warn "Secondary tenant provided without token; skipping isolation validation"
    else
      local secondary_key="$SECONDARY_API_KEY"
      if [[ -z "$secondary_key" ]]; then
        warn "Secondary tenant token provided without API key; skipping isolation validation"
      else
        invoke_loop POST "$HYBRID_PATH" "$PAYLOAD_HYBRID" "$SECONDARY_TENANT" "$SECONDARY_TOKEN" "$secondary_key" "$HYBRID_LIMIT" no "isolation-secondary" || failures=$((failures + 1))
      fi
    fi
  else
    warn "Secondary tenant not provided; isolation test skipped"
  fi

  local results_json
  results_json=$(printf '%s\n' "${RESULTS[@]}" | jq -s 'map(fromjson)')

  log "Validating Retry-After headers"
  local retry_values
  retry_values=$(echo "$results_json" | jq -r 'map(.retryAfter) | map(select(. != "")) | .[]?')
  if [[ -z "$retry_values" ]]; then
    warn "No Retry-After headers captured"
    failures=$((failures + 1))
  fi

  echo "$results_json" | jq '.'

  if [[ -n "$REPORT_FILE" ]]; then
    echo "$results_json" > "$REPORT_FILE"
    log "Report written to ${REPORT_FILE}"
  fi

  if (( failures > 0 )); then
    fail "Rate limiting validation reported ${failures} failures"
  fi
  log "Rate limiting validation passed"
}

main "$@"
