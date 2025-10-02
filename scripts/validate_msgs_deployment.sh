#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

SERVICE_URL="${SERVICE_URL:-}" # e.g. https://hh-msgs-svc-xxxxx.a.run.app
TENANT_ID="${TENANT_ID:-sandbox}" # Firestore tenant id
AUTH_HEADER="${AUTH_HEADER:-}" # Firebase or Gateway token header value

if [[ -z "${SERVICE_URL}" ]]; then
  echo "SERVICE_URL must be provided" >&2
  exit 1
fi

if [[ -z "${AUTH_HEADER}" ]]; then
  echo "AUTH_HEADER must contain a valid Authorization header value" >&2
  exit 1
fi

log() {
  printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$*"
}

call_endpoint() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  if [[ -n "${data}" ]]; then
    curl -sS -X "${method}" "${SERVICE_URL}${path}" \
      -H "Authorization: ${AUTH_HEADER}" \
      -H "X-HH-Tenant: ${TENANT_ID}" \
      -H "Content-Type: application/json" \
      -d "${data}"
  else
    curl -sS -X "${method}" "${SERVICE_URL}${path}" \
      -H "Authorization: ${AUTH_HEADER}" \
      -H "X-HH-Tenant: ${TENANT_ID}" \
      -H "Content-Type: application/json"
  fi
}

log "Checking health endpoint"
call_endpoint GET /health | jq '.'

log "Validating skill expansion"
call_endpoint POST /v1/skills/expand '{"skillId":"javascript","topK":5}' | jq '.'

log "Validating role template"
call_endpoint POST /v1/roles/template '{"ecoId":"frontend-developer","locale":"pt-BR"}' | jq '.'

log "Validating market demand"
call_endpoint GET '/v1/market/demand?skillId=javascript&region=BR-SP' | jq '.'

log "Validation complete"
