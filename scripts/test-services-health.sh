#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd curl
require_cmd python3
if command -v redis-cli >/dev/null 2>&1; then
  HAVE_REDIS_CLI=1
else
  HAVE_REDIS_CLI=0
fi

ISSUER_URL="${ISSUER_URL:-http://localhost:8081}"
TENANT_ID="${TENANT_ID:-tenant-alpha}"
SUBJECT="${SUBJECT:-local-health-checker}"
SCOPES="${SCOPES:-search:read embeddings:write rerank:invoke evidence:read eco:read}"

get_token() {
  local payload
  payload=$(cat <<JSON
{"tenant_id":"${TENANT_ID}","sub":"${SUBJECT}","scope":"${SCOPES}"}
JSON
)
  curl -sS -X POST \
    -H "Content-Type: application/json" \
    -d "${payload}" \
    "${ISSUER_URL}/token" | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])"
}

AUTH_TOKEN="$(get_token)"
AUTH_HEADER="Authorization: Bearer ${AUTH_TOKEN}"

check_service() {
  local name="$1"
  local url="$2"
  local tmp
  tmp="$(mktemp)"
  local code
  code=$(curl -sS -H "${AUTH_HEADER}" -H "X-Tenant-ID: ${TENANT_ID}" -o "${tmp}" -w '%{http_code}' "${url}") || {
    echo "[health] ${name} request failed" >&2
    cat "${tmp}" >&2 || true
    rm -f "${tmp}"
    return 1
  }
  if [[ "${code}" != "200" ]]; then
    echo "[health] ${name} unhealthy (HTTP ${code})" >&2
    cat "${tmp}" >&2 || true
    rm -f "${tmp}"
    return 1
  fi
  echo "[health] ${name} OK"
  rm -f "${tmp}"
}

EMBED_URL="${EMBED_URL:-http://localhost:7101}"
SEARCH_URL="${SEARCH_URL:-http://localhost:7102}"
RERANK_URL="${RERANK_URL:-http://localhost:7103}"
EVIDENCE_URL="${EVIDENCE_URL:-http://localhost:7104}"
ECO_URL="${ECO_URL:-http://localhost:7105}"
ENRICH_URL="${ENRICH_URL:-http://localhost:7112}"

check_service "hh-embed-svc" "${EMBED_URL}/health"
check_service "hh-search-svc" "${SEARCH_URL}/health"
check_service "hh-rerank-svc" "${RERANK_URL}/health"
check_service "hh-evidence-svc" "${EVIDENCE_URL}/health"
check_service "hh-eco-svc" "${ECO_URL}/health"
check_service "hh-enrich-svc" "${ENRICH_URL}/health"

check_enrich_pipeline() {
  local candidate
  candidate="health-cand-$(date +%s)"
  local payload
  payload=$(cat <<JSON
{"candidateId":"${candidate}","async":true,"payload":{"source":"health-check"}}
JSON
)

  if [[ "${HAVE_REDIS_CLI}" == "1" ]]; then
    local queue_key
    queue_key="${ENRICH_QUEUE_KEY:-hh:enrich:queue}"
    local depth
    depth=$(redis-cli -h "${REDIS_HOST:-127.0.0.1}" -p "${REDIS_PORT:-6379}" LLEN "${queue_key}" 2>/dev/null || echo "unknown")
    echo "[health] hh-enrich-svc queue depth=${depth}"
  fi

  local job_json
  job_json=$(mktemp)
  curl -sS -X POST \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER}" \
    -H "X-Tenant-ID: ${TENANT_ID}" \
    -d "${payload}" \
    "${ENRICH_URL}/v1/enrich/profile" \
    -o "${job_json}"

  local job_id
  job_id=$(python3 - "$job_json" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as handle:
    body = json.load(handle)
print(body.get('job', {}).get('jobId', ''))
PY
  )
  if [[ -z "${job_id}" ]]; then
    echo "[health] Failed to enqueue enrichment job" >&2
    cat "${job_json}" >&2
    rm -f "${job_json}"
    return 1
  fi
  rm -f "${job_json}"

  echo "[health] Enqueued enrichment job ${job_id}; polling status"
  local start
  start=$(date +%s)
  local status
  while true; do
    local response
    response=$(curl -sS -H "${AUTH_HEADER}" -H "X-Tenant-ID: ${TENANT_ID}" "${ENRICH_URL}/v1/enrich/status/${job_id}") || {
      echo "[health] Failed to fetch enrichment status" >&2
      return 1
    }
    status=$(printf '%s' "${response}" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('job', {}).get('status','unknown'))")

    if [[ "${status}" == "completed" ]]; then
      local embedding
      embedding=$(printf '%s' "${response}" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('job', {}).get('result', {}).get('embeddingUpserted', False))")
      echo "[health] Enrichment job completed (embedding=${embedding})"
      break
    fi
    if [[ "${status}" == "failed" ]]; then
      echo "[health] Enrichment job failed" >&2
      echo "${response}" | python3 -m json.tool >&2
      return 1
    fi
    if (( $(date +%s) - start > 60 )); then
      echo "[health] Enrichment job timed out" >&2
      return 1
    fi
    sleep 2
  done
}

check_enrich_pipeline

echo "All service health endpoints returned 200."
