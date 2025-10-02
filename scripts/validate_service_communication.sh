#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
DEFAULT_CONFIG="${ROOT_DIR}/config/infrastructure/headhunter-ai-0088-production.env"
CONFIG_FILE="${DEFAULT_CONFIG}"
CLI_PROJECT_ID=""
CLI_REGION=""
ENVIRONMENT=production
DRY_RUN=false
REPORT_PATH=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [OPTIONS]

Validate Cloud Run service-to-service communication, authentication, and performance SLAs.

Options:
  --project-id ID          Override project id from config
  --region REGION          Override region from config
  --config PATH            Infrastructure config path (default: ${DEFAULT_CONFIG})
  --environment ENV        Deployment environment suffix (default: production)
  --report PATH            Write validation report to PATH
  --dry-run                Print actions without executing
  -h, --help               Show this message and exit
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      CLI_PROJECT_ID="$2"
      shift 2
      ;;
    --region)
      CLI_REGION="$2"
      shift 2
      ;;
    --config)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --report)
      REPORT_PATH="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "Config file ${CONFIG_FILE} not found" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${CONFIG_FILE}"
CONFIG_PROJECT_ID="${PROJECT_ID:-}"
CONFIG_REGION="${REGION:-}"
PROJECT_ID="${CLI_PROJECT_ID:-${CONFIG_PROJECT_ID}}"
REGION="${CLI_REGION:-${CONFIG_REGION}}"
TENANT_ID="${DEFAULT_TENANT:-tenant-alpha}"
if [[ -z "${PROJECT_ID}" || -z "${REGION}" ]]; then
  echo "Project id and region must be provided" >&2
  exit 1
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "$1 CLI is required" >&2
    exit 1
  }
}

require_command gcloud
require_command curl
require_command jq
require_command python3

log() {
  printf '[svc-validation][%s] %s\n' "${ENVIRONMENT}" "$*" >&2
}

declare -A TOKEN_CACHE

get_identity_token() {
  local audience=$1
  if [[ -n "${TOKEN_CACHE[${audience}]:-}" ]]; then
    printf '%s' "${TOKEN_CACHE[${audience}]}"
    return 0
  fi
  local token
  if ! token=$(gcloud auth print-identity-token --audiences "${audience}" 2>/dev/null); then
    return 1
  fi
  TOKEN_CACHE["${audience}"]="${token}"
  printf '%s' "${token}"
}

secure_curl() {
  local base=$1
  local path=$2
  shift 2
  local token
  if ! token=$(get_identity_token "${base}"); then
    return 1
  fi
  curl -fsS -H "Authorization: Bearer ${token}" "$@" "${base}${path}"
}

REPORT="Service communication validation\nProject: ${PROJECT_ID}\nRegion: ${REGION}\nEnvironment: ${ENVIRONMENT}\nGenerated: $(date -Is)\n\n"
append_report() {
  REPORT+="$1\n"
}

if [[ "${DRY_RUN}" == true ]]; then
  log "DRY-RUN: would evaluate service communication for project ${PROJECT_ID}"
  append_report "Dry run - no checks executed"
  if [[ -n "${REPORT_PATH}" ]]; then
    printf '%s\n' "${REPORT}" >"${REPORT_PATH}"
  else
    printf '%s\n' "${REPORT}"
  fi
  exit 0
fi

fetch_url() {
  local service="$1"
  gcloud run services describe "${service}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --platform=managed \
    --format='value(status.url)'
}

check_health() {
  local service="$1"
  local url="$2"
  local component="$3"
  local json
  json=$(secure_curl "${url}" "/${component}" --max-time 10)
  printf '%s' "${json}"
}

SERVICE_BASES=(
  "hh-embed-svc"
  "hh-search-svc"
  "hh-rerank-svc"
  "hh-evidence-svc"
  "hh-eco-svc"
  "hh-enrich-svc"
  "hh-admin-svc"
  "hh-msgs-svc"
)

declare -A SERVICE_URLS
append_report "--- Health checks ---"
for base in "${SERVICE_BASES[@]}"; do
  service="${base}-${ENVIRONMENT}"
  url=$(fetch_url "${service}")
  if [[ -z "${url}" ]]; then
    append_report "[FAIL] ${service} has no active URL"
    exit 1
  fi
  SERVICE_URLS["${base}"]="${url}"
  if health=$(secure_curl "${url}" "/health" --max-time 20 2>/dev/null); then
    status=$(printf '%s' "${health}" | jq -r '.status // empty')
    if [[ "${status}" == "ok" ]]; then
      append_report "[PASS] ${service} healthy"
    else
      append_report "[FAIL] ${service} degraded (${status:-unknown})"
      append_report "  payload: ${health}"
      exit 1
    fi
    if [[ "${base}" == "hh-search-svc" ]]; then
      embed_status=$(printf '%s' "${health}" | jq -r '.embeddings.status // .components.embeddings.status // empty')
      if [[ "${embed_status}" != "healthy" ]]; then
        append_report "[FAIL] search service reports embed dependency status=${embed_status}"
        exit 1
      fi
      rerank_status=$(printf '%s' "${health}" | jq -r '.rerank.status // .components.rerank.status // empty')
      if [[ -n "${rerank_status}" && "${rerank_status}" != "healthy" ]]; then
        append_report "[FAIL] search service reports rerank dependency status=${rerank_status}"
        exit 1
      fi
      append_report "[PASS] search service dependencies healthy"
    fi
    if [[ "${base}" == "hh-rerank-svc" ]]; then
      together_status=$(printf '%s' "${health}" | jq -r '.together.status // .components.together.status // empty')
      if [[ -n "${together_status}" && "${together_status}" != "healthy" ]]; then
        append_report "[FAIL] rerank service reports Together AI status=${together_status}"
        exit 1
      fi
      append_report "[PASS] rerank external dependency healthy"
    fi
  else
    append_report "[FAIL] ${service} health endpoint unreachable"
    exit 1
  fi
done

append_report "\n--- End-to-end pipeline ---"
PIPELINE_OUTPUT=$(PROJECT_ID="${PROJECT_ID}" REGION="${REGION}" TENANT_ID="${TENANT_ID}" "${SCRIPT_DIR}/test-complete-pipeline.sh" "${ENVIRONMENT}")
append_report "Pipeline execution complete"

pipeline_json=$(printf '%s' "${PIPELINE_OUTPUT}" | jq '.')
p95_latency=$(printf '%s' "${PIPELINE_OUTPUT}" | jq -r '.performance.stepLatencyP95Ms')
rerank_latency=$(printf '%s' "${PIPELINE_OUTPUT}" | jq -r '.performance.rerankLatencyMs')
cache_latency=$(printf '%s' "${PIPELINE_OUTPUT}" | jq -r '.performance.cachedReadLatencyMs')
issues=$(printf '%s' "${PIPELINE_OUTPUT}" | jq -c '.issues')
tenant_report=$(printf '%s' "${PIPELINE_OUTPUT}" | jq -r '.tenant')

append_report "Pipeline tenant: ${tenant_report}"
if [[ "${tenant_report}" != "${TENANT_ID}" ]]; then
  append_report "[FAIL] Tenant isolation mismatch: expected ${TENANT_ID}, got ${tenant_report}"
  exit 1
fi

sla_failure=false
if [[ "${p95_latency}" != "null" && $(printf '%.0f' "${p95_latency}") -gt 1200 ]]; then
  append_report "[FAIL] End-to-end p95 latency ${p95_latency}ms exceeds 1200ms"
  sla_failure=true
else
  append_report "[PASS] End-to-end p95 latency ${p95_latency}ms"
fi
if [[ "${rerank_latency}" != "null" && $(printf '%.0f' "${rerank_latency}") -gt 350 ]]; then
  append_report "[FAIL] Rerank latency ${rerank_latency}ms exceeds 350ms"
  sla_failure=true
else
  append_report "[PASS] Rerank latency ${rerank_latency}ms"
fi
if [[ "${cache_latency}" != "null" && $(printf '%.0f' "${cache_latency}") -gt 250 ]]; then
  append_report "[FAIL] Cached read latency ${cache_latency}ms exceeds 250ms"
  sla_failure=true
else
  append_report "[PASS] Cached read latency ${cache_latency}ms"
fi

if [[ "${issues}" != "[]" ]]; then
  append_report "[WARN] Pipeline issues reported: ${issues}"
fi

append_report "\n--- Authentication guardrail ---"
unauth_code=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  -H 'Content-Type: application/json' \
  "${SERVICE_URLS["hh-search-svc"]}/v1/search/hybrid" \
  --data '{"query":"sanity"}')
if [[ "${unauth_code}" -ge 400 ]]; then
  append_report "[PASS] Unauthenticated search request rejected with ${unauth_code}"
else
  append_report "[FAIL] Unauthenticated search request returned ${unauth_code}"
  exit 1
fi

append_report "\n--- Summary ---"
if [[ "${sla_failure}" == true ]]; then
  append_report "Status: FAILED (SLA violation)"
  exit_code=1
else
  append_report "Status: PASSED"
  exit_code=0
fi

if [[ -n "${REPORT_PATH}" ]]; then
  printf '%s\n' "${REPORT}" >"${REPORT_PATH}"
  log "Report written to ${REPORT_PATH}"
else
  printf '%s\n' "${REPORT}"
fi

exit ${exit_code}
