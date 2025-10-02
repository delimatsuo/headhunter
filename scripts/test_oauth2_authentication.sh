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
ENDPOINT="${ENDPOINT:-}"
TENANTS=()
GATEWAY_PATH="${GATEWAY_PATH:-/v1/search/hybrid}"
SECRETS_PREFIX="${SECRETS_PREFIX:-oauth-client-}"
TOKEN_AUDIENCE="${TOKEN_AUDIENCE:-}"
EXPECTED_AUDIENCE="${EXPECTED_AUDIENCE:-}"
EXPECTED_STATUS_SUCCESS="${EXPECTED_STATUS_SUCCESS:-200}"
EXPECTED_STATUS_TENANT_MISMATCH="${EXPECTED_STATUS_TENANT_MISMATCH:-403}"
EXPECTED_STATUS_UNAUTHENTICATED="${EXPECTED_STATUS_UNAUTHENTICATED:-401}"
EXPECTED_STATUS_API_KEY_REJECTED="${EXPECTED_STATUS_API_KEY_REJECTED:-401}"
RATE_LIMIT_PATH="${RATE_LIMIT_PATH:-/v1/search/hybrid}"
RATE_LIMIT_TARGET="${RATE_LIMIT_TARGET:-30}"
RATE_LIMIT_DURATION="${RATE_LIMIT_DURATION:-60}"
REPORT_FILE="${REPORT_FILE:-}" # optional JSON summary output
API_KEY_PREFIX="${API_KEY_PREFIX:-gateway-api-key-}"
TENANT_API_KEYS_LIST=()
GATEWAY_METHOD="${GATEWAY_METHOD:-POST}"

usage() {
  cat <<USAGE
Usage: $0 --project PROJECT_ID --endpoint https://gateway-host [options]

Options:
  --project PROJECT_ID            GCP project containing the gateway secrets
  --region REGION                 Cloud Run region (default: us-central1)
  --endpoint URL                  Gateway base URL (https://...)
  --tenant TENANT_ID              Tenant identifier to validate (repeatable)
  --gateway-path PATH             Endpoint path used for successful auth test (default: /v1/search/hybrid)
  --rate-limit-path PATH          Endpoint path used for rate-limiting test (default: /v1/search/hybrid)
  --secrets-prefix PREFIX         Secret Manager prefix (default: oauth-client-)
  --api-key tenant=KEY            Provide API key for tenant (repeatable)
  --api-key-prefix PREFIX         API key secret prefix (default: gateway-api-key-)
  --gateway-method METHOD         Method used for gateway path auth checks (default: POST)
  --audience AUD                  Expected OAuth audience (overrides value in secret)
  --expected-api-key-status CODE  Expected status when API key invalid (default: 401)
  --report FILE                   Write JSON report to FILE
  -h, --help                      Show this help message
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      PROJECT_ID="$2"; shift 2 ;;
    --region)
      REGION="$2"; shift 2 ;;
    --endpoint)
      ENDPOINT="$2"; shift 2 ;;
    --tenant)
      TENANTS+=("$2"); shift 2 ;;
    --gateway-path)
      GATEWAY_PATH="$2"; shift 2 ;;
    --rate-limit-path)
      RATE_LIMIT_PATH="$2"; shift 2 ;;
    --secrets-prefix)
      SECRETS_PREFIX="$2"; shift 2 ;;
    --api-key)
      if [[ "$2" != *=* ]]; then
        fail "--api-key requires TENANT=KEY format"
      fi
      tenant_key="${2%%=*}"
      api_key_value="${2#*=}"
      if [[ -z "$tenant_key" || -z "$api_key_value" ]]; then
        fail "Invalid --api-key value: $2"
      fi
      updated=0
      for idx in "${!TENANT_API_KEYS_LIST[@]}"; do
        entry="${TENANT_API_KEYS_LIST[$idx]}"
        if [[ "${entry%%=*}" == "$tenant_key" ]]; then
          TENANT_API_KEYS_LIST[$idx]="${tenant_key}=${api_key_value}"
          updated=1
          break
        fi
      done
      if [[ $updated -eq 0 ]]; then
        TENANT_API_KEYS_LIST+=("${tenant_key}=${api_key_value}")
      fi
      shift 2 ;;
    --api-key-prefix)
      API_KEY_PREFIX="$2"; shift 2 ;;
    --gateway-method)
      GATEWAY_METHOD="${2^^}"; shift 2 ;;
    --audience)
      TOKEN_AUDIENCE="$2"; shift 2 ;;
    --expected-api-key-status)
      EXPECTED_STATUS_API_KEY_REJECTED="$2"; shift 2 ;;
    --report)
      REPORT_FILE="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      fail "Unknown argument: $1" ;;
  esac
done

if [[ -z "$PROJECT_ID" ]]; then
  fail "--project is required"
fi
if [[ -z "$ENDPOINT" ]]; then
  fail "--endpoint is required"
fi
if [[ ${#TENANTS[@]} -eq 0 ]]; then
  warn "No tenants provided; attempting to infer from Secret Manager"
  mapfile -t TENANTS < <(gcloud secrets list --project "$PROJECT_ID" --filter="name~^${SECRETS_PREFIX}" --format="value(name)" | sed "s/^${SECRETS_PREFIX}//")
fi
if [[ ${#TENANTS[@]} -eq 0 ]]; then
  fail "No tenants resolved for OAuth validation"
fi

require_command gcloud
require_command jq
require_command curl
require_command python3

log "Validating OAuth2 client credentials for tenants: ${TENANTS[*]}"

PASS_COUNT=0
FAIL_COUNT=0
RATE_LIMIT_RESULTS=()
SUMMARY=()

decode_jwt() {
  python3 - <<'PY' "$1"
import json
import sys
import base64
from typing import Tuple

def urlsafe_b64decode(data: str) -> bytes:
    rem = len(data) % 4
    if rem:
        data += '=' * (4 - rem)
    return base64.urlsafe_b64decode(data.encode('utf-8'))

def decode(token: str) -> Tuple[dict, dict]:
    header_b64, payload_b64, _signature = token.split('.')
    header = json.loads(urlsafe_b64decode(header_b64))
    payload = json.loads(urlsafe_b64decode(payload_b64))
    return header, payload

token = sys.argv[1]
try:
    header, payload = decode(token)
except Exception as exc:  # noqa: BLE001
    print(json.dumps({"error": f"failed to decode token: {exc}"}))
    sys.exit(1)
print(json.dumps({"header": header, "payload": payload}))
PY
}

fetch_secret_json() {
  local tenant="$1"
  gcloud secrets versions access latest \
    --secret="${SECRETS_PREFIX}${tenant}" \
    --project="$PROJECT_ID"
}

set_api_key() {
  local tenant="$1"
  local key="$2"
  local updated=0
  for idx in "${!TENANT_API_KEYS_LIST[@]}"; do
    local entry="${TENANT_API_KEYS_LIST[$idx]}"
    if [[ "${entry%%=*}" == "$tenant" ]]; then
      TENANT_API_KEYS_LIST[$idx]="${tenant}=${key}"
      updated=1
      break
    fi
  done
  if [[ $updated -eq 0 ]]; then
    TENANT_API_KEYS_LIST+=("${tenant}=${key}")
  fi
}

resolve_api_key() {
  local tenant="$1"
  for entry in "${TENANT_API_KEYS_LIST[@]}"; do
    if [[ "${entry%%=*}" == "$tenant" ]]; then
      local value="${entry#*=}"
      if [[ -n "$value" ]]; then
        echo "$value"
        return
      fi
    fi
  done
  local secret
  secret=$(gcloud secrets versions access latest \
    --secret="${API_KEY_PREFIX}${tenant}" \
    --project="$PROJECT_ID" 2>/dev/null || true)
  if [[ -n "$secret" ]]; then
    secret=$(echo "$secret" | tr -d '\r\n')
    set_api_key "$tenant" "$secret"
    echo "$secret"
    return
  fi
  echo ""
}

obtain_token() {
  local tenant="$1"
  local secret_json
  secret_json=$(fetch_secret_json "$tenant")
  local client_id client_secret token_uri audience scope
  client_id=$(echo "$secret_json" | jq -r '.client_id // .clientId')
  client_secret=$(echo "$secret_json" | jq -r '.client_secret // .clientSecret')
  token_uri=$(echo "$secret_json" | jq -r '.token_uri // .tokenUri')
  audience=$(echo "$secret_json" | jq -r '.audience // empty')
  scope=$(echo "$secret_json" | jq -r '.scope // empty')
  if [[ -z "$client_id" || -z "$client_secret" || -z "$token_uri" ]]; then
    fail "Secret ${SECRETS_PREFIX}${tenant} missing client credentials"
  fi
  if [[ -n "$TOKEN_AUDIENCE" ]]; then
    audience="$TOKEN_AUDIENCE"
  fi
  local data=("grant_type=client_credentials" "client_id=${client_id}" "client_secret=${client_secret}")
  if [[ -n "$audience" ]]; then
    data+=("audience=${audience}")
    EXPECTED_AUDIENCE="${EXPECTED_AUDIENCE:-$audience}"
  fi
  if [[ -n "$scope" && "$scope" != "null" ]]; then
    data+=("scope=${scope}")
  fi
  local response
  response=$(curl -fsS -X POST "$token_uri" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -d "${data[*]}")
  local token
  token=$(echo "$response" | jq -r '.access_token')
  local expires
  expires=$(echo "$response" | jq -r '.expires_in')
  if [[ -z "$token" || "$token" == "null" ]]; then
    fail "Failed to acquire token for tenant ${tenant}: ${response}"
  fi
  echo "$token|$expires"
}

validate_claims() {
  local tenant="$1"
  local token="$2"
  local decoded
  if ! decoded=$(decode_jwt "$token"); then
    fail "Unable to decode JWT for tenant ${tenant}"
  fi
  local audience payload_org
  audience=$(echo "$decoded" | jq -r '.payload.aud // empty')
  payload_org=$(echo "$decoded" | jq -r '.payload.org_id // .payload.orgId // empty')
  if [[ -n "$EXPECTED_AUDIENCE" && "$audience" != "$EXPECTED_AUDIENCE" ]]; then
    warn "Tenant ${tenant} token audience mismatch: expected ${EXPECTED_AUDIENCE}, got ${audience}"
    return 1
  fi
  if [[ -n "$payload_org" && "$payload_org" != "$tenant" ]]; then
    warn "Tenant ${tenant} token org_id mismatch: expected ${tenant}, got ${payload_org}"
    return 1
  fi
  return 0
}

invoke_gateway() {
  local method="$1"
  local path="$2"
  local token="$3"
  local tenant="$4"
  local api_key="$5"
  local expected_status="$6"
  local description="$7"
  local url="${ENDPOINT}${path}"
  local response
  local http_status
  log "${description}: ${method} ${path} (tenant=${tenant})"
  local curl_args=(-sS -o /tmp/oauth-test-response.$$ -w '%{http_code}' -X "$method" "$url"
    -H "Authorization: Bearer ${token}"
    -H "X-Tenant-ID: ${tenant}"
    -H "X-API-Key: ${api_key}")
  if [[ "$method" == "POST" || "$method" == "PUT" || "$method" == "PATCH" ]]; then
    curl_args+=(-H 'Content-Type: application/json' --data '{"probe":true}')
  fi
  response=$(curl "${curl_args[@]}")
  http_status="$response"
  if [[ "$http_status" != "$expected_status" ]]; then
    warn "${description} expected HTTP ${expected_status} but received ${http_status}."
    cat /tmp/oauth-test-response.$$ >&2 || true
    rm -f /tmp/oauth-test-response.$$
    return 1
  fi
  rm -f /tmp/oauth-test-response.$$
  return 0
}

run_rate_limit_test() {
  local token="$1"
  local tenant="$2"
  local api_key="$3"
  local url="${ENDPOINT}${RATE_LIMIT_PATH}"
  log "Executing rate limit test against ${url} (target ${RATE_LIMIT_TARGET} requests over ${RATE_LIMIT_DURATION}s)"
  local successes=0
  local rate_limited=0
  local failures=0
  local start_ts
  start_ts=$(date +%s)
  for ((i=1; i<=RATE_LIMIT_TARGET; i++)); do
    local status
    status=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$url" \
      -H "Authorization: Bearer ${token}" \
      -H "X-Tenant-ID: ${tenant}" \
      -H "X-API-Key: ${api_key}" \
      -H 'Content-Type: application/json' \
      --data '{"probe":true,"rateLimit":true}') || status="curl-error"
    if [[ "$status" == "${EXPECTED_STATUS_SUCCESS}" ]]; then
      successes=$((successes + 1))
    elif [[ "$status" == "429" ]]; then
      rate_limited=$((rate_limited + 1))
    else
      failures=$((failures + 1))
    fi
    sleep "$(python3 - <<'PY' "$RATE_LIMIT_DURATION" "$RATE_LIMIT_TARGET"
import sys
window = float(sys.argv[1])
count = int(sys.argv[2])
if count <= 1:
    print('0')
else:
    print(window / max(count - 1, 1))
PY
)"
  done
  local elapsed
  elapsed=$(( $(date +%s) - start_ts ))
  log "Rate limit test summary: success=${successes}, 429=${rate_limited}, other_failures=${failures}, elapsed=${elapsed}s"
  RATE_LIMIT_RESULTS+=("{\"tenant\":\"${tenant}\",\"success\":${successes},\"rateLimited\":${rate_limited},\"failures\":${failures},\"elapsedSeconds\":${elapsed}}")
  if (( rate_limited == 0 )); then
    warn "Rate limiting did not trigger for tenant ${tenant}."
    return 1
  fi
  return 0
}

simulate_failure_cases() {
  local tenant="$1"
  local token="$2"
  local api_key="$3"
  local failures=0
  log "Simulating authentication failure scenarios for tenant ${tenant}"
  if ! invoke_gateway "$GATEWAY_METHOD" "$GATEWAY_PATH" "invalid-${token}" "$tenant" "$api_key" "$EXPECTED_STATUS_UNAUTHENTICATED" "Invalid token rejection"; then
    warn "Invalid token request did not return ${EXPECTED_STATUS_UNAUTHENTICATED}"
    failures=$((failures + 1))
  fi
  if ! invoke_gateway "$GATEWAY_METHOD" "$GATEWAY_PATH" "$token" "${tenant}-mismatch" "$api_key" "$EXPECTED_STATUS_TENANT_MISMATCH" "Tenant mismatch enforcement"; then
    warn "Tenant mismatch request did not return ${EXPECTED_STATUS_TENANT_MISMATCH}"
    failures=$((failures + 1))
  fi
  if ! invoke_gateway "$GATEWAY_METHOD" "$GATEWAY_PATH" "$token" "$tenant" "${api_key}-invalid" "$EXPECTED_STATUS_API_KEY_REJECTED" "API key rejection"; then
    warn "Invalid API key request did not return ${EXPECTED_STATUS_API_KEY_REJECTED}"
    failures=$((failures + 1))
  fi
  if invoke_gateway "$GATEWAY_METHOD" "$GATEWAY_PATH" "$token" "$tenant" "$api_key" "$EXPECTED_STATUS_SUCCESS" "Authenticated request"; then
    :
  else
    failures=$((failures + 1))
  fi
  if (( failures == 0 )); then
    return 0
  fi
  return 1
}

add_summary_entry() {
  local tenant="$1"
  local status="$2"
  local message="$3"
  SUMMARY+=("{\"tenant\":\"${tenant}\",\"status\":\"${status}\",\"message\":\"${message//"/\"}\"}")
}

for tenant in "${TENANTS[@]}"; do
  log "--- Tenant ${tenant} ---"
  token_bundle=$(obtain_token "$tenant")
  access_token=${token_bundle%%|*}
  expires_in=${token_bundle##*|}
  api_key=$(resolve_api_key "$tenant")
  if [[ -z "$api_key" ]]; then
    warn "No API key available for tenant ${tenant}"
    add_summary_entry "$tenant" "fail" "API key missing"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    continue
  fi
  if validate_claims "$tenant" "$access_token"; then
    log "Token claims valid for tenant ${tenant}"
  else
    add_summary_entry "$tenant" "fail" "Token claim validation failed"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    continue
  fi
  if simulate_failure_cases "$tenant" "$access_token" "$api_key"; then
    :
  else
    add_summary_entry "$tenant" "fail" "Authentication scenario checks failed"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    continue
  fi
  if run_rate_limit_test "$access_token" "$tenant" "$api_key"; then
    PASS_COUNT=$((PASS_COUNT + 1))
    add_summary_entry "$tenant" "pass" "Authentication and rate limit checks passed"
  else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    add_summary_entry "$tenant" "fail" "Rate limiting did not trigger"
  fi
  log "Token for tenant ${tenant} expires in ${expires_in}s"
  sleep 1
done

log "Authentication validation complete: passes=${PASS_COUNT}, failures=${FAIL_COUNT}"

if [[ -n "$REPORT_FILE" ]]; then
  log "Writing report to ${REPORT_FILE}"
  summary_json=$(printf '%s\n' "${SUMMARY[@]}" | jq -s 'map(fromjson)')
  rate_json=$(printf '%s\n' "${RATE_LIMIT_RESULTS[@]}" | jq -s 'map(fromjson)')
  jq -n \
    --argjson passes "$PASS_COUNT" \
    --argjson failures "$FAIL_COUNT" \
    --argjson summary "$summary_json" \
    --argjson rate "$rate_json" \
    '{passes: $passes, failures: $failures, summary: $summary, rateLimit: $rate}' \
    > "$REPORT_FILE"
fi

if (( FAIL_COUNT > 0 )); then
  fail "OAuth2 authentication validation failed for one or more tenants."
fi

log "All OAuth2 authentication checks passed"
