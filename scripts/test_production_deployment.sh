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

Execute production smoke, integration, and load tests for the Cloud Run stack.

Options:
  --project-id ID          Override project id from config
  --region REGION          Override region from config
  --config PATH            Infrastructure config path (default: ${DEFAULT_CONFIG})
  --environment ENV        Environment suffix (default: production)
  --report PATH            Write aggregated report to PATH
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
  command -v "$1" >/dev/null 2>&1 || { echo "$1 CLI is required" >&2; exit 1; }
}

require_command gcloud
require_command curl
require_command jq
require_command python3

log() {
  printf '[prod-test][%s] %s\n' "${ENVIRONMENT}" "$*" >&2
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

if [[ "${DRY_RUN}" == true ]]; then
  log "DRY-RUN: skipping execution"
fi

REPORT="Production deployment validation\nProject: ${PROJECT_ID}\nRegion: ${REGION}\nEnvironment: ${ENVIRONMENT}\nGenerated: $(date -Is)\n\n"
append_report() {
  REPORT+="$1\n"
}

run_or_echo() {
  if [[ "${DRY_RUN}" == true ]]; then
    log "DRY-RUN: $*"
    return 0
  fi
  "$@"
}

fetch_service_url() {
  local base=$1
  gcloud run services describe "${base}-${ENVIRONMENT}" \
    --project="${PROJECT_ID}" --region="${REGION}" --platform=managed \
    --format='value(status.url)'
}

append_report "--- Smoke tests ---"
declare -A SERVICE_URLS
SMOKE_FAILURES=0
for svc in hh-embed-svc hh-search-svc hh-rerank-svc hh-evidence-svc hh-eco-svc hh-enrich-svc hh-admin-svc hh-msgs-svc; do
  url=$(fetch_service_url "${svc}") || url=""
  if [[ -z "${url}" ]]; then
    append_report "[FAIL] ${svc}-${ENVIRONMENT} missing"
    SMOKE_FAILURES=$((SMOKE_FAILURES + 1))
    continue
  fi
  SERVICE_URLS["${svc}"]="${url}"
  if [[ "${DRY_RUN}" == true ]]; then
    append_report "[SKIP] ${svc} health (dry run)"
    continue
  fi
  health_json=$(secure_curl "${url}" "/health" --max-time 20 2>/dev/null || true)
  status=""
  if [[ -n "${health_json}" ]]; then
    status=$(printf '%s' "${health_json}" | jq -r '.status // empty' 2>/dev/null || true)
  fi
  if [[ "${status}" == "ok" ]]; then
    append_report "[PASS] ${svc}-${ENVIRONMENT} health ok"
  else
    append_report "[FAIL] ${svc}-${ENVIRONMENT} health status=${status:-unknown}"
    SMOKE_FAILURES=$((SMOKE_FAILURES + 1))
  fi
done

append_report "\n--- Integration suite ---"
if [[ "${DRY_RUN}" == true ]]; then
  append_report "[SKIP] Integration suite (dry run)"
  PIPELINE_JSON='{}'
else
  PIPELINE_JSON=$(PROJECT_ID="${PROJECT_ID}" REGION="${REGION}" TENANT_ID="${TENANT_ID}" "${SCRIPT_DIR}/test-complete-pipeline.sh" "${ENVIRONMENT}")
  append_report "[PASS] Integration suite executed"
fi

pipeline_issues="[]"
pipeline_p95="0"
pipeline_rerank="0"
pipeline_cache="0"
if [[ "${DRY_RUN}" != true ]]; then
  pipeline_issues=$(printf '%s' "${PIPELINE_JSON}" | jq -c '.issues')
  pipeline_p95=$(printf '%s' "${PIPELINE_JSON}" | jq -r '.performance.stepLatencyP95Ms // 0')
  pipeline_rerank=$(printf '%s' "${PIPELINE_JSON}" | jq -r '.performance.rerankLatencyMs // 0')
  pipeline_cache=$(printf '%s' "${PIPELINE_JSON}" | jq -r '.performance.cachedReadLatencyMs // 0')
fi

append_report "\n--- Load test ---"
REPORT_DIR="${ROOT_DIR}/reports"
LOAD_REPORT="${REPORT_DIR}/load-test-${ENVIRONMENT}-$(date +%Y%m%dT%H%M%S).json"
mkdir -p "${REPORT_DIR}"
if [[ "${DRY_RUN}" == true ]]; then
  append_report "[SKIP] Load test (dry run)"
else
  if run_or_echo python3 "${SCRIPT_DIR}/load-test-stack.py" --users 6 --iterations 5 --report "${LOAD_REPORT}"; then
    append_report "[PASS] Load test report saved to ${LOAD_REPORT}"
  else
    append_report "[FAIL] Load test encountered errors"
  fi
fi

append_report "
--- Negative tests ---"
if [[ "${DRY_RUN}" == true ]]; then
  append_report "[SKIP] Negative request checks"
else
  if [[ -n "${SERVICE_URLS["hh-search-svc"]:-}" ]]; then
    unauth=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
      -H 'Content-Type: application/json' \
      "${SERVICE_URLS["hh-search-svc"]}/v1/search/hybrid" \
      --data '{"query":"forbidden"}')
    if [[ "${unauth}" -ge 400 ]]; then
      append_report "[PASS] Unauthorized search rejected (${unauth})"
    else
      append_report "[FAIL] Unauthorized search returned ${unauth}"
    fi
  else
    append_report "[SKIP] Search negative test unavailable (missing service URL)"
  fi

  if [[ -n "${SERVICE_URLS["hh-rerank-svc"]:-}" ]]; then
    bad_payload=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
      -H 'Content-Type: application/json' \
      -H 'Authorization: Bearer invalid' \
      -H "X-Tenant-ID: ${TENANT_ID}" \
      "${SERVICE_URLS["hh-rerank-svc"]}/v1/search/rerank" \
      --data '{"invalid":true}')
    if [[ "${bad_payload}" -ge 400 ]]; then
      append_report "[PASS] Rerank invalid payload rejected (${bad_payload})"
    else
      append_report "[FAIL] Rerank invalid payload returned ${bad_payload}"
    fi
  else
    append_report "[SKIP] Rerank negative test unavailable (missing service URL)"
  fi
fi

append_report "\n--- Monitoring verification ---"
if [[ "${DRY_RUN}" == true ]]; then
  append_report "[SKIP] Monitoring verification"
else
  uptime_checks=$(gcloud monitoring uptime-checks list --project="${PROJECT_ID}" --format='value(displayName)' || true)
  append_report "[INFO] Uptime checks: ${uptime_checks:-none}"
  alert_policies=$(gcloud alpha monitoring policies list --project="${PROJECT_ID}" --format='value(displayName)' || true)
  append_report "[INFO] Alert policies: ${alert_policies:-none}"
fi

append_report "\n--- SLA summary ---"
if [[ "${DRY_RUN}" == true ]]; then
  append_report "[SKIP] SLA evaluation"
else
  if (( $(printf '%.0f' "${pipeline_p95}") > 1200 )); then
    append_report "[FAIL] Pipeline p95 ${pipeline_p95}ms"
  else
    append_report "[PASS] Pipeline p95 ${pipeline_p95}ms"
  fi
  if (( $(printf '%.0f' "${pipeline_rerank}") > 350 )); then
    append_report "[FAIL] Rerank latency ${pipeline_rerank}ms"
  else
    append_report "[PASS] Rerank latency ${pipeline_rerank}ms"
  fi
  if (( $(printf '%.0f' "${pipeline_cache}") > 250 )); then
    append_report "[FAIL] Cached read latency ${pipeline_cache}ms"
  else
    append_report "[PASS] Cached read latency ${pipeline_cache}ms"
  fi
  if [[ "${pipeline_issues}" != "[]" ]]; then
    append_report "[WARN] Integration issues: ${pipeline_issues}"
  fi
fi

append_report "\n--- Summary ---"
if [[ ${SMOKE_FAILURES} -gt 0 ]]; then
  append_report "Status: FAILED (smoke tests)"
  exit_code=1
else
  append_report "Status: COMPLETED"
  exit_code=0
fi

if [[ -n "${REPORT_PATH}" ]]; then
  printf '%s\n' "${REPORT}" >"${REPORT_PATH}"
  log "Report written to ${REPORT_PATH}"
else
  printf '%s\n' "${REPORT}"
fi

exit ${exit_code}
