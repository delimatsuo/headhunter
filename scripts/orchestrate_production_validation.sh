#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
DEFAULT_CONFIG="${ROOT_DIR}/config/testing/production-test-config.yaml"
REPORT_DIR="${ROOT_DIR}/reports"

MODE="full"
CONFIG_PATH="${DEFAULT_CONFIG}"
ENVIRONMENT="production"
PROJECT_ID=""
REGION=""
TENANT_CREDS=()
TOKEN_URL="https://oauth2.googleapis.com/token"
AUDIENCE=""
SERVICE_OVERRIDES=()
CHAOS_TOKEN=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Options:
  --mode MODE            quick | full | continuous (default: full)
  --config PATH          Validation config path (default: ${DEFAULT_CONFIG})
  --environment NAME     Environment key (default: production)
  --project-id ID        GCP project id (required)
  --region REGION        Cloud Run region (required)
  --tenant SPEC          tenant_id,client_id,client_secret (repeatable)
  --token-url URL        OAuth token endpoint (default: Google)
  --audience AUDIENCE    OAuth audience override
  --service NAME=URL     Override service base URL (repeatable)
  --chaos-token TOKEN    Pre-issued bearer token for chaos testing
  --report-dir PATH      Directory to store reports (default: ${REPORT_DIR})
  -h, --help             Show this help message
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --project-id)
      PROJECT_ID="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --tenant)
      TENANT_CREDS+=("$2")
      shift 2
      ;;
    --token-url)
      TOKEN_URL="$2"
      shift 2
      ;;
    --audience)
      AUDIENCE="$2"
      shift 2
      ;;
    --service)
      SERVICE_OVERRIDES+=("$2")
      shift 2
      ;;
    --chaos-token)
      CHAOS_TOKEN="$2"
      shift 2
      ;;
    --report-dir)
      REPORT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${PROJECT_ID}" || -z "${REGION}" ]]; then
  echo "--project-id and --region are required" >&2
  exit 1
fi

if [[ ${#TENANT_CREDS[@]} -eq 0 ]]; then
  echo "At least one --tenant entry is required" >&2
  exit 1
fi

mkdir -p "${REPORT_DIR}"

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command '$1' not found" >&2
    exit 1
  fi
}

require gcloud
require python3
require jq

declare -A SERVICE_URLS

fetch_service_url() {
  local svc=$1
  gcloud run services describe "$svc" \
    --project="${PROJECT_ID}" --region="${REGION}" --platform=managed \
    --format='value(status.url)'
}

register_service_urls() {
  local -A overrides
  for override in "${SERVICE_OVERRIDES[@]:-}"; do
    local name=${override%%=*}
    local url=${override#*=}
    overrides["${name}"]=${url}
  done
  declare -A service_to_name=(
    [embeddings]="hh-embed-svc-${ENVIRONMENT}"
    [search]="hh-search-svc-${ENVIRONMENT}"
    [rerank]="hh-rerank-svc-${ENVIRONMENT}"
    [evidence]="hh-evidence-svc-${ENVIRONMENT}"
    [eco]="hh-eco-svc-${ENVIRONMENT}"
    [enrichment]="hh-enrich-svc-${ENVIRONMENT}"
    [admin]="hh-admin-svc-${ENVIRONMENT}"
    [msgs]="hh-msgs-svc-${ENVIRONMENT}"
  )
  for key in "${!service_to_name[@]}"; do
    if [[ -n "${overrides[${key}]:-}" ]]; then
      SERVICE_URLS["${key}"]=${overrides[${key}]}
      continue
    fi
    local url
    url=$(fetch_service_url "${service_to_name[${key}]}") || url=""
    if [[ -z "${url}" ]]; then
      echo "Failed to resolve URL for ${service_to_name[${key}]}" >&2
      exit 1
    fi
    SERVICE_URLS["${key}"]=${url%/}
  done
}

SERVICE_ARGS() {
  local args=()
  for key in "${!SERVICE_URLS[@]}"; do
    args+=("--service" "${key}=${SERVICE_URLS[${key}]}" )
  done
  printf '%s\n' "${args[@]}"
}

TENANT_ARGS() {
  local args=()
  for entry in "${TENANT_CREDS[@]}"; do
    args+=("--tenant" "${entry}")
  done
  printf '%s\n' "${args[@]}"
}

run_python() {
  local name=$1
  shift
  echo "[orchestrator] Running ${name}"
  if ! python3 "$@"; then
    echo "[orchestrator] ${name} failed" >&2
    return 1
  fi
  return 0
}

register_service_urls

IFS="," read -r PRIMARY_TENANT PRIMARY_CLIENT PRIMARY_SECRET <<< "${TENANT_CREDS[0]}"

declare -i FAILURES=0

declare -a SERVICE_ARGS_ARRAY
while IFS= read -r line; do
  SERVICE_ARGS_ARRAY+=("${line}")
done < <(SERVICE_ARGS)

declare -a TENANT_ARGS_ARRAY
while IFS= read -r line; do
  TENANT_ARGS_ARRAY+=("${line}")
done < <(TENANT_ARGS)

AUDIENCE_ARG=()
if [[ -n "${AUDIENCE}" ]]; then
  AUDIENCE_ARG=("--audience" "${AUDIENCE}")
fi

common_flags=("--config" "${CONFIG_PATH}" "--environment" "${ENVIRONMENT}" "--token-url" "${TOKEN_URL}")

SMOKE_REPORT="${REPORT_DIR}/production_smoke.json"
if ! run_python "production_smoke_tests" "${SCRIPT_DIR}/production_smoke_tests.py" "${common_flags[@]}" "${AUDIENCE_ARG[@]}" "${SERVICE_ARGS_ARRAY[@]}" "--tenant" "${PRIMARY_TENANT}" "--client-id" "${PRIMARY_CLIENT}" "--client-secret" "${PRIMARY_SECRET}" "--report" "${SMOKE_REPORT}"; then
  FAILURES+=1
fi

if [[ "${MODE}" == "quick" ]]; then
  echo "[orchestrator] Quick mode complete"
  exit ${FAILURES}
fi

LOAD_REPORT="${REPORT_DIR}/production_load.json"
if ! run_python "production_load_testing" "${SCRIPT_DIR}/production_load_testing.py" "${common_flags[@]}" "${AUDIENCE_ARG[@]}" "${SERVICE_ARGS_ARRAY[@]}" "${TENANT_ARGS_ARRAY[@]}" "--report" "${LOAD_REPORT}"; then
  FAILURES+=1
fi

AUTO_REPORT="${REPORT_DIR}/auto_scaling.json"
if ! run_python "auto_scaling_validation" "${SCRIPT_DIR}/auto_scaling_validation.py" "${common_flags[@]}" "${AUDIENCE_ARG[@]}" "${SERVICE_ARGS_ARRAY[@]}" "--tenant" "${PRIMARY_TENANT}" "--client-id" "${PRIMARY_CLIENT}" "--client-secret" "${PRIMARY_SECRET}" "--project-id" "${PROJECT_ID}" "--location" "${REGION}" "--service-name" "hh-search-svc-${ENVIRONMENT}" "--report" "${AUTO_REPORT}"; then
  FAILURES+=1
fi

ISOLATION_REPORT="${REPORT_DIR}/tenant_isolation.json"
if ! run_python "tenant_isolation_validation" "${SCRIPT_DIR}/tenant_isolation_validation.py" "${common_flags[@]}" "${AUDIENCE_ARG[@]}" "${SERVICE_ARGS_ARRAY[@]}" "${TENANT_ARGS_ARRAY[@]}" "--report" "${ISOLATION_REPORT}"; then
  FAILURES+=1
fi

PIPELINE_REPORT="${REPORT_DIR}/pipeline_validation.json"
if ! run_python "end_to_end_pipeline_validation" "${SCRIPT_DIR}/end_to_end_pipeline_validation.py" "${common_flags[@]}" "${AUDIENCE_ARG[@]}" "${SERVICE_ARGS_ARRAY[@]}" "--tenant" "${PRIMARY_TENANT}" "--client-id" "${PRIMARY_CLIENT}" "--client-secret" "${PRIMARY_SECRET}" "--report" "${PIPELINE_REPORT}"; then
  FAILURES+=1
fi

SECURITY_REPORT="${REPORT_DIR}/security_validation.json"
if ! run_python "production_security_validation" "${SCRIPT_DIR}/production_security_validation.py" "${common_flags[@]}" "${AUDIENCE_ARG[@]}" "${SERVICE_ARGS_ARRAY[@]}" "${TENANT_ARGS_ARRAY[@]}" "--project-id" "${PROJECT_ID}" "--region" "${REGION}" "--report" "${SECURITY_REPORT}"; then
  FAILURES+=1
fi

PERF_REPORT="${REPORT_DIR}/performance_benchmark.json"
if ! run_python "performance_benchmarking" "${SCRIPT_DIR}/production_performance_benchmarking.py" "${common_flags[@]}" "${AUDIENCE_ARG[@]}" "${SERVICE_ARGS_ARRAY[@]}" "--tenant" "${PRIMARY_TENANT}" "--client-id" "${PRIMARY_CLIENT}" "--client-secret" "${PRIMARY_SECRET}" "--project-id" "${PROJECT_ID}" "--report" "${PERF_REPORT}"; then
  FAILURES+=1
fi

CHAOS_REPORT="${REPORT_DIR}/chaos_validation.json"
CHAOS_TOKEN_VALUE="${CHAOS_TOKEN}"
if [[ -z "${CHAOS_TOKEN_VALUE}" ]]; then
  CHAOS_TOKEN_VALUE=$(gcloud auth print-identity-token 2>/dev/null || true)
fi
if [[ -z "${CHAOS_TOKEN_VALUE}" ]]; then
  echo "[orchestrator] No chaos token provided; writing skip report"
  cat <<EOF > "${CHAOS_REPORT}"
{
  "scenarios": [],
  "status": "skip",
  "reason": "chaos token unavailable"
}
EOF
else
  if ! run_python "production_chaos_testing" "${SCRIPT_DIR}/production_chaos_testing.py" "--config" "${CONFIG_PATH}" "--environment" "${ENVIRONMENT}" "${SERVICE_ARGS_ARRAY[@]}" "--tenant" "${PRIMARY_TENANT}" "--token" "${CHAOS_TOKEN_VALUE}" "--report" "${CHAOS_REPORT}"; then
    FAILURES+=1
  fi
fi

SLA_REPORT="${REPORT_DIR}/sla_monitor.json"
if ! run_python "production_sla_monitoring" "${SCRIPT_DIR}/production_sla_monitoring.py" "--config" "${CONFIG_PATH}" "--environment" "${ENVIRONMENT}" "--project-id" "${PROJECT_ID}" "--report" "${SLA_REPORT}"; then
  FAILURES+=1
fi

MONITOR_REPORT="${REPORT_DIR}/monitoring_validation.json"
if ! run_python "production_monitoring_validation" "${SCRIPT_DIR}/production_monitoring_validation.py" "--config" "${CONFIG_PATH}" "--environment" "${ENVIRONMENT}" "--project-id" "${PROJECT_ID}" "--report" "${MONITOR_REPORT}"; then
  FAILURES+=1
fi

SUMMARY_JSON="${REPORT_DIR}/summary.json"
SUMMARY_HTML="${REPORT_DIR}/summary.html"
declare -a DASHBOARD_REPORTS=(
  "${SMOKE_REPORT}"
  "${LOAD_REPORT}"
  "${AUTO_REPORT}"
  "${ISOLATION_REPORT}"
  "${PIPELINE_REPORT}"
  "${SECURITY_REPORT}"
  "${PERF_REPORT}"
  "${CHAOS_REPORT}"
  "${SLA_REPORT}"
  "${MONITOR_REPORT}"
)
declare -a DASHBOARD_ARGS=()
for report_path in "${DASHBOARD_REPORTS[@]}"; do
  DASHBOARD_ARGS+=("--report" "${report_path}")
done
declare -a WEBHOOK_ARGS=()
if [[ -n "${SLACK_WEBHOOK:-}" ]]; then
  WEBHOOK_ARGS=("--webhook" "${SLACK_WEBHOOK}")
fi
if ! run_python "production_validation_dashboard" "${SCRIPT_DIR}/production_validation_dashboard.py" "${DASHBOARD_ARGS[@]}" "--output" "${SUMMARY_JSON}" "--html" "${SUMMARY_HTML}" "${WEBHOOK_ARGS[@]}"; then
  FAILURES+=1
fi

if [[ "${MODE}" == "continuous" ]]; then
  echo "[orchestrator] Continuous mode waiting 10 minutes before rerun"
  sleep 600
  exec "$0" "$@"
fi

exit ${FAILURES}
