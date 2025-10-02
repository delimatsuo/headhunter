#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Validate the full production deployment by exercising API Gateway routing,
# OAuth flows, service health checks, and the end-to-end search pipeline.
#
# Usage:
#   ./scripts/validate_complete_deployment.sh [staging|production]

ENVIRONMENT="${1:-staging}"
if [[ "${ENVIRONMENT}" != "staging" && "${ENVIRONMENT}" != "production" ]]; then
  echo "Environment must be staging or production" >&2
  exit 1
fi

PROJECT_ID="${PROJECT_ID:-headhunter-${ENVIRONMENT}}"
REGION="${REGION:-us-central1}"
TENANT_ID="${TENANT_ID:-tenant-alpha}"
ISSUER_URL="${ISSUER_URL:-https://idp.${ENVIRONMENT}.ella.jobs}"
TOKEN_URL="${TOKEN_URL:-https://idp.${ENVIRONMENT}.ella.jobs/oauth/token}"
DEFAULT_GATEWAY_HOST="https://hh-gateway-${ENVIRONMENT}-${REGION}.gateway.dev"

if [[ -n "${GATEWAY_HOST:-}" ]]; then
  GATEWAY_URL="${GATEWAY_HOST}"
else
  GATEWAY_URL="${GATEWAY_URL:-${DEFAULT_GATEWAY_HOST}}"
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud CLI is required" >&2
  exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "curl CLI is required" >&2
  exit 1
fi

log() {
  printf '[validate][%s] %s\n' "${ENVIRONMENT}" "$1"
}

fetch_service_url() {
  local name="$1"
  gcloud run services describe "${name}" \
    --platform=managed \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --format='value(status.url)'
}

health_check_service() {
  local name="$1"
  local url="$2"
  if curl -fsSL --max-time 8 "${url}/health" >/dev/null; then
    printf '  [%s] healthy\n' "${name}"
  else
    echo "Service ${name} failed health check at ${url}" >&2
    exit 1
  fi
}

obtain_gateway_token() {
  if [[ -n "${GATEWAY_BEARER:-}" ]]; then
    printf '%s' "${GATEWAY_BEARER}"
    return
  fi

  if [[ -n "${OAUTH_CLIENT_ID:-}" && -n "${OAUTH_CLIENT_SECRET:-}" ]]; then
    local audience="${OAUTH_AUDIENCE:-${GATEWAY_AUDIENCE:-${GATEWAY_URL}}}"
    local response
    local -a data=(
      --data-urlencode "grant_type=client_credentials"
      --data-urlencode "client_id=${OAUTH_CLIENT_ID}"
      --data-urlencode "client_secret=${OAUTH_CLIENT_SECRET}"
    )

    if [[ -n "${audience}" ]]; then
      data+=(--data-urlencode "audience=${audience}")
    fi

    if [[ -n "${OAUTH_SCOPE:-}" ]]; then
      data+=(--data-urlencode "scope=${OAUTH_SCOPE}")
    fi

    if ! response=$(curl -fsS -X POST "${TOKEN_URL}" \
      -H 'Content-Type: application/x-www-form-urlencoded' \
      "${data[@]}"); then
      echo 'Failed to obtain OAuth token for API Gateway' >&2
      exit 1
    fi

    printf '%s' "${response}" | python3 - <<'PY'
import json
import sys

try:
    payload = json.load(sys.stdin)
    token = payload.get('access_token')
    if not token:
        raise KeyError('access_token')
    print(token)
except Exception as exc:  # noqa: BLE001
    raise SystemExit(f'Unable to parse OAuth token response: {exc}') from exc
PY
    return
  fi

  TENANT_ID="${TENANT_ID}" ISSUER_URL="${ISSUER_URL}" python3 - <<'PY'
from scripts.run_integration import get_token
print(get_token())
PY
}

exercise_gateway_endpoint() {
  local method="$1"
  local path="$2"
  local payload="$3"
  local token="$4"
  if [[ -n "${payload}" ]]; then
    curl -fsS \
      -H "Authorization: Bearer ${token}" \
      -H "X-Tenant-ID: ${TENANT_ID}" \
      -H "Content-Type: application/json" \
      -X "${method}" \
      --data "${payload}" \
      "${GATEWAY_URL}${path}" >/dev/null
  else
    curl -fsS \
      -H "Authorization: Bearer ${token}" \
      -H "X-Tenant-ID: ${TENANT_ID}" \
      -H "Content-Type: application/json" \
      -X "${method}" \
      "${GATEWAY_URL}${path}" >/dev/null
  fi
}

log "Fetching service endpoints"
EMBED_URL="$(fetch_service_url "hh-embed-svc-${ENVIRONMENT}")"
SEARCH_URL="$(fetch_service_url "hh-search-svc-${ENVIRONMENT}")"
RERANK_URL="$(fetch_service_url "hh-rerank-svc-${ENVIRONMENT}")"
EVIDENCE_URL="$(fetch_service_url "hh-evidence-svc-${ENVIRONMENT}")"
ECO_URL="$(fetch_service_url "hh-eco-svc-${ENVIRONMENT}")"
ADMIN_URL="$(fetch_service_url "hh-admin-svc-${ENVIRONMENT}")"
MSGS_URL="$(fetch_service_url "hh-msgs-svc-${ENVIRONMENT}")"
ENRICH_URL="$(fetch_service_url "hh-enrich-svc-${ENVIRONMENT}")"

log "Running targeted health checks"
health_check_service hh-embed-svc "${EMBED_URL}"
health_check_service hh-search-svc "${SEARCH_URL}"
health_check_service hh-rerank-svc "${RERANK_URL}"
health_check_service hh-evidence-svc "${EVIDENCE_URL}"
health_check_service hh-eco-svc "${ECO_URL}"
health_check_service hh-admin-svc "${ADMIN_URL}"
health_check_service hh-msgs-svc "${MSGS_URL}"
health_check_service hh-enrich-svc "${ENRICH_URL}"

log "Executing full pipeline validation"
"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/test-complete-pipeline.sh" "${ENVIRONMENT}" >/dev/null

log "Validating API Gateway routes"
TOKEN="$(obtain_gateway_token)"
exercise_gateway_endpoint POST "/v1/embeddings/generate" '{"text":"hello"}' "${TOKEN}"
exercise_gateway_endpoint POST "/v1/search/hybrid" '{"query":"engenheiro de dados","limit":1}' "${TOKEN}"
exercise_gateway_endpoint POST "/v1/search/rerank" '{"jobDescription":"pipeline validation","candidates":[{"candidateId":"cand-001","summary":"sample"}]}' "${TOKEN}"
exercise_gateway_endpoint GET "/v1/occupations/search?title=engenheiro" "" "${TOKEN}"
exercise_gateway_endpoint GET "/v1/market/demand?skillId=python" "" "${TOKEN}"

log "Collecting snapshot metrics"
python3 - <<PY
import json
from scripts.run_integration import HttpClient, SERVICE_URLS, get_token
from os import environ
SERVICE_URLS['admin'] = '${ADMIN_URL}'
SERVICE_URLS['search'] = '${SEARCH_URL}'
SERVICE_URLS['enrich'] = '${ENRICH_URL}'
SERVICE_URLS['embed'] = '${EMBED_URL}'
SERVICE_URLS['rerank'] = '${RERANK_URL}'
SERVICE_URLS['evidence'] = '${EVIDENCE_URL}'
SERVICE_URLS['eco'] = '${ECO_URL}'
SERVICE_URLS['msgs'] = '${MSGS_URL}'
environ['TENANT_ID'] = '${TENANT_ID}'
environ['ISSUER_URL'] = '${ISSUER_URL}'
client = HttpClient(get_token(), '${TENANT_ID}')
resp = client.request('GET', '${ADMIN_URL}', '/v1/admin/snapshots', {'tenantId': '${TENANT_ID}'})
print(json.dumps(resp['data'], indent=2))
PY

log "Deployment validation completed successfully"
