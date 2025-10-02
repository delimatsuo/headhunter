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
ALLOWED_ORIGINS=(
  "https://ella.jobs"
  "https://staging.ella.jobs"
  "https://headhunter.ai"
  "https://staging.headhunter.ai"
  "http://localhost:3000"
  "http://localhost:8080"
  "http://localhost:5173"
)
DISALLOWED_ORIGINS=("https://malicious.example")
PATHS=(
  "/v1/search/hybrid"
  "/v1/search/rerank"
  "/v1/embeddings/generate"
  "/v1/evidence/test-candidate"
)
ALLOWED_HEADERS=("Authorization" "X-Tenant-ID" "Content-Type")
ALLOWED_METHODS=("GET" "POST" "PUT" "DELETE" "OPTIONS")
REPORT_FILE="${REPORT_FILE:-}"

usage() {
  cat <<USAGE
Usage: $0 --endpoint https://gateway-host [options]

Options:
  --endpoint URL        Gateway base URL (required)
  --origin ORIGIN       Add additional allowed origin (repeatable)
  --deny-origin ORIGIN  Add additional disallowed origin (repeatable)
  --path PATH           Add an endpoint path to test (repeatable)
  --report FILE         Write JSON report to FILE
  -h, --help            Show this help message
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --endpoint)
      ENDPOINT="$2"; shift 2 ;;
    --origin)
      ALLOWED_ORIGINS+=("$2"); shift 2 ;;
    --deny-origin)
      DISALLOWED_ORIGINS+=("$2"); shift 2 ;;
    --path)
      PATHS+=("$2"); shift 2 ;;
    --report)
      REPORT_FILE="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      fail "Unknown argument: $1" ;;
  esac
done

if [[ -z "$ENDPOINT" ]]; then
  fail "--endpoint is required"
fi

require_command curl
require_command jq

RESULTS=()

add_result() {
  RESULTS+=("{\"path\":\"${1//"/\"}\",\"origin\":\"${2//"/\"}\",\"allowed\":${3},\"status\":${4},\"allowOrigin\":\"${5//"/\"}\",\"allowMethods\":\"${6//"/\"}\",\"allowHeaders\":\"${7//"/\"}\",\"hasExposeHeaders\":${8}}")
}

preflight_request() {
  local path="$1"
  local origin="$2"
  local method="$3"
  local headers_file body_file
  headers_file="$(mktemp)"
  body_file="$(mktemp)"
  local status
  status=$(curl -sS -o "$body_file" -D "$headers_file" -w '%{http_code}' -X OPTIONS "${ENDPOINT}${path}" \
    -H "Origin: ${origin}" \
    -H "Access-Control-Request-Method: ${method}" \
    -H "Access-Control-Request-Headers: Authorization, X-Tenant-ID, Content-Type") || status="0"
  local allow_origin allow_methods allow_headers expose_headers
  allow_origin=$(grep -i '^Access-Control-Allow-Origin:' "$headers_file" | awk '{print $2}' | tr -d '\r')
  allow_methods=$(grep -i '^Access-Control-Allow-Methods:' "$headers_file" | cut -d':' -f2- | tr -d '\r ')
  allow_headers=$(grep -i '^Access-Control-Allow-Headers:' "$headers_file" | cut -d':' -f2- | tr -d '\r ')
  expose_headers=$(grep -i '^Access-Control-Expose-Headers:' "$headers_file" | cut -d':' -f2- | tr -d '\r ')
  rm -f "$headers_file" "$body_file"
  echo "$status|$allow_origin|$allow_methods|$allow_headers|$expose_headers"
}

validate_allowed_origin() {
  local path="$1"
  local origin="$2"
  local failures=0
  for method in "${ALLOWED_METHODS[@]}"; do
    local response
    response=$(preflight_request "$path" "$origin" "$method")
    IFS='|' read -r status allow_origin allow_methods allow_headers expose_headers <<<"$response"
    local allowed_flag=true
    if [[ "$status" != "200" && "$status" != "204" ]]; then
      warn "Unexpected status ${status} for ${origin} preflight (${method} ${path})"
      allowed_flag=false
    fi
    if [[ "$allow_origin" != "$origin" && "$allow_origin" != "*" ]]; then
      warn "Origin ${origin} not reflected or wildcard missing for ${path} (${method})"
      allowed_flag=false
    fi
    if [[ "$allow_methods" != *"${method}"* ]]; then
      warn "Method ${method} missing for origin ${origin} (${path})"
      allowed_flag=false
    fi
    for header in "${ALLOWED_HEADERS[@]}"; do
      if [[ "$allow_headers" != *"${header}"* ]]; then
        warn "Header ${header} missing for origin ${origin} (${path})"
        allowed_flag=false
      fi
    done
    local has_expose=$([[ -n "$expose_headers" ]] && echo "true" || echo "false")
    add_result "$path" "$origin" "$([[ "$allowed_flag" == true ]] && echo true || echo false)" "$status" "$allow_origin" "$allow_methods" "$allow_headers" "$has_expose"
    if [[ "$allowed_flag" == false ]]; then
      failures=$((failures + 1))
    fi
  done
  return $failures
}

validate_disallowed_origin() {
  local path="$1"
  local origin="$2"
  local response
  response=$(preflight_request "$path" "$origin" "GET")
  IFS='|' read -r status allow_origin allow_methods allow_headers expose_headers <<<"$response"
  local allowed=$([[ "$allow_origin" == "$origin" ]] && echo "true" || echo "false")
  add_result "$path" "$origin" false "$status" "$allow_origin" "$allow_methods" "$allow_headers" "$([[ -n "$expose_headers" ]] && echo true || echo false)"
  if [[ "$allowed" == "true" ]]; then
    warn "Disallowed origin ${origin} unexpectedly permitted"
    return 1
  fi
  return 0
}

main() {
  local failures=0
  for path in "${PATHS[@]}"; do
    for origin in "${ALLOWED_ORIGINS[@]}"; do
      validate_allowed_origin "$path" "$origin" || failures=$((failures + 1))
    done
    for origin in "${DISALLOWED_ORIGINS[@]}"; do
      validate_disallowed_origin "$path" "$origin" || failures=$((failures + 1))
    done
  done

  local results_json
  results_json=$(printf '%s\n' "${RESULTS[@]}" | jq -s 'map(fromjson)')
  echo "$results_json" | jq '.'

  if [[ -n "$REPORT_FILE" ]]; then
    echo "$results_json" > "$REPORT_FILE"
    log "Report written to ${REPORT_FILE}"
  fi

  if (( failures > 0 )); then
    fail "CORS validation encountered ${failures} failures"
  fi
  log "CORS validation passed"
}

main "$@"
