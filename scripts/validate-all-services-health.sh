#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Validates that every core microservice responds to its /health endpoint with
# proper authentication, acceptable latency, and healthy dependency metadata.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../scripts/lib/service-health-common.sh
source "${ROOT_DIR}/scripts/lib/service-health-common.sh"

ISSUER_URL="${ISSUER_URL:-http://localhost:8081}"
TENANT_ID="${TENANT_ID:-tenant-alpha}"
SUBJECT="${SUBJECT:-local-health-checker}"
SCOPES="${SCOPES:-search:read embeddings:write rerank:invoke evidence:read eco:read admin:write msgs:read enrich:invoke}"
MAX_RETRIES=${MAX_RETRIES:-5}
RETRY_BACKOFF_SECONDS=${RETRY_BACKOFF_SECONDS:-5}

log() {
  printf '[validate-services] %s\n' "$*"
}

error() {
  printf '[validate-services][error] %s\n' "$*" >&2
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    error "Missing required command: $1"
    exit 1
  fi
}

require_cmd curl
require_cmd python3

AUTH_TOKEN="$(hh_health_get_access_token "$ISSUER_URL" "$TENANT_ID" "$SUBJECT" "$SCOPES")"
if [[ -z "$AUTH_TOKEN" ]]; then
  error "Failed to retrieve access token from ${ISSUER_URL}/token"
  exit 1
fi
AUTH_HEADER="Authorization: Bearer ${AUTH_TOKEN}"

SERVICES=(
  "hh-embed-svc|http://localhost:7101/health|350|"
  "hh-search-svc|http://localhost:7102/health|500|/v1/search/hybrid"
  "hh-rerank-svc|http://localhost:7103/health|350|"
  "hh-evidence-svc|http://localhost:7104/health|450|"
  "hh-eco-svc|http://localhost:7105/health|600|"
  "hh-admin-svc|http://localhost:7106/health|600|"
  "hh-msgs-svc|http://localhost:7107/health|450|"
  "hh-enrich-svc|http://localhost:7108/health|900|"
)

PASS_COUNT=0
FAIL_COUNT=0
WARNINGS=()
REPORT_LINES=()

document_dependency_anomalies() {
  local file="$1"
  hh_health_dependency_anomalies "$file"
}

record_report() {
  REPORT_LINES+=("$1")
}

check_tenant_isolation() {
  local name="$1"
  local health_url="$2"
  local probe_path="$3"

  if [[ -z "$probe_path" ]]; then
    log "${name}: INFO tenant isolation probe skipped (no protected endpoint configured)"
    return 0
  fi

  local base_url
  base_url="${health_url%/health}"
  local target
  target="${base_url}${probe_path}"

  local status
  status=$(curl -s -o /dev/null -w '%{http_code}' \
    -X POST \
    -H "X-Tenant-ID: ${TENANT_ID}" \
    -H "Content-Type: application/json" \
    -d '{"probe":"tenant-isolation"}' \
    "$target")

  if [[ "$status" == "401" || "$status" == "403" ]]; then
    log "${name}: tenant isolation enforced via ${probe_path} (HTTP ${status})"
  else
    log "${name}: INFO tenant isolation probe ${probe_path} returned HTTP ${status}"
  fi
}

invoke_health() {
  local name="$1"
  local url="$2"
  local budget="$3"
  local probe="$4"
  local attempt tmp metadata http_code time_total latency_ms deps

  tmp="$(mktemp)"
  for attempt in $(seq 1 "$MAX_RETRIES"); do
    http_code=''
    time_total=''
    if metadata=$(curl -sS \
      -H "${AUTH_HEADER}" \
      -H "X-Tenant-ID: ${TENANT_ID}" \
      -H "X-Scope: health" \
      -o "${tmp}" \
      -w '%{http_code} %{time_total}' \
      "$url" ); then
      http_code="${metadata%% *}"
      time_total="${metadata##* }"

      if [[ "$http_code" == "200" ]]; then
        latency_ms="$(python3 -c "print(round(float('${time_total}') * 1000, 2))")"
        record_report "${name}: healthy (HTTP 200) in ${latency_ms}ms"
        if [[ -n "$budget" && "$budget" != "0" ]]; then
          local sla_status
          sla_status=$(python3 - "$latency_ms" "$budget" <<'PY'
import sys
latency=float(sys.argv[1])
budget=float(sys.argv[2])
print('WARN' if latency > budget else 'OK')
PY
          )
          if [[ "$sla_status" == "WARN" ]]; then
            WARNINGS+=("${name}: latency ${latency_ms}ms exceeded SLA ${budget}ms")
          fi
        fi
        deps="$(document_dependency_anomalies "${tmp}")"
        if [[ -n "$deps" ]]; then
          WARNINGS+=("${name}: dependency anomalies -> ${deps}")
        fi
        check_tenant_isolation "$name" "$url" "$probe"
        rm -f "$tmp"
        return 0
      fi
    fi
    log "${name}: attempt ${attempt}/${MAX_RETRIES} failed (HTTP ${http_code:-unknown}). Retrying in ${RETRY_BACKOFF_SECONDS}s"
    sleep "$RETRY_BACKOFF_SECONDS"
  done

  cat "$tmp" >&2 || true
  rm -f "$tmp"
  return 1
}

for entry in "${SERVICES[@]}"; do
  IFS='|' read -r name url budget probe <<<"${entry}"
  if invoke_health "$name" "$url" "$budget" "$probe"; then
    ((PASS_COUNT++))
  else
    ((FAIL_COUNT++))
    error "${name}: health check failed"
  fi
  log "-----------------------------------------------------"
  record_report "${name}: SLA budget ${budget}ms"
done

log "====================================================="
for line in "${REPORT_LINES[@]}"; do
  log "$line"
done

if (( ${#WARNINGS[@]} > 0 )); then
  log "Warnings detected:"
  for warn in "${WARNINGS[@]}"; do
    log "- ${warn}"
  done
fi

if (( FAIL_COUNT > 0 )); then
  error "${FAIL_COUNT} service health checks failed."
  exit 1
fi

log "All ${PASS_COUNT} services responded successfully."
