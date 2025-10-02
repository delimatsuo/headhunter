#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./utils/repo_guard.sh
source "$(dirname "${BASH_SOURCE[0]}")/utils/repo_guard.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
CONFIG_FILE="${REPO_ROOT}/config/infrastructure/headhunter-production.env"

usage() {
  cat <<'USAGE'
Usage: scripts/validate-deployment-readiness.sh [options]

Options:
  --project-id <id>    GCP project ID (defaults to config file)
  --environment <env>  Deployment environment label (default: production)
  --region <region>    GCP region (defaults to config file)
  --strict             Exit with status 1 on any WARN or FAIL checks
  --report <path>      Output validation report JSON path (default: .deployment/validation-report-<timestamp>.json)
  --help               Display this help message
USAGE
}

if [[ -f "${CONFIG_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"
fi

PROJECT_ID_DEFAULT=${PROJECT_ID:-""}
REGION_DEFAULT=${REGION:-""}
ENVIRONMENT_DEFAULT="production"

PROJECT_ID=""
ENVIRONMENT="${ENVIRONMENT_DEFAULT}"
REGION=""
STRICT_MODE=false
REPORT_PATH=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --project-id)
      PROJECT_ID=$2
      shift 2
      ;;
    --environment)
      ENVIRONMENT=$2
      shift 2
      ;;
    --region)
      REGION=$2
      shift 2
      ;;
    --strict)
      STRICT_MODE=true
      shift
      ;;
    --report)
      REPORT_PATH=$2
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

PROJECT_ID=${PROJECT_ID:-${PROJECT_ID_DEFAULT}}
REGION=${REGION:-${REGION_DEFAULT}}

if [[ -z "${PROJECT_ID}" ]]; then
  echo "[error] --project-id or config PROJECT_ID must be provided" >&2
  exit 1
fi

if [[ -z "${REGION}" ]]; then
  echo "[error] --region or config REGION must be provided" >&2
  exit 1
fi

if [[ -z "${REPORT_PATH}" ]]; then
  REPORT_PATH="${REPO_ROOT}/.deployment/validation-report-$(date -u +%Y%m%d-%H%M%S).json"
else
  case "${REPORT_PATH}" in
    /*) : ;;
    *) REPORT_PATH="${REPO_ROOT}/${REPORT_PATH}" ;;
  esac
fi

mkdir -p "$(dirname "${REPORT_PATH}")"

TIMESTAMP_UTC=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

GCLOUD_AVAILABLE=false
JQ_AVAILABLE=false
PYTHON_AVAILABLE=false

if command -v gcloud >/dev/null 2>&1; then
  GCLOUD_AVAILABLE=true
else
  echo "[warn] gcloud CLI not found; attempting best-effort validation." >&2
fi

if command -v jq >/dev/null 2>&1; then
  JQ_AVAILABLE=true
else
  echo "[warn] jq not found; structured parsing may be limited." >&2
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON_AVAILABLE=true
else
  echo "[warn] python3 not found; JSON report generation may be limited." >&2
fi

if ${GCLOUD_AVAILABLE}; then
  if ! gcloud config set project "${PROJECT_ID}" >/dev/null 2>&1; then
    echo "[warn] Unable to set gcloud project to ${PROJECT_ID}." >&2
  fi
fi

EXPECTED_FASTIFY_SERVICES=(
  "hh-embed-svc-production"
  "hh-search-svc-production"
  "hh-rerank-svc-production"
  "hh-evidence-svc-production"
  "hh-eco-svc-production"
  "hh-msgs-svc-production"
  "hh-admin-svc-production"
  "hh-enrich-svc-production"
)

SECRET_NAMES=(
  "${SECRET_DB_PRIMARY:-}"
  "${SECRET_DB_REPLICA:-}"
  "${SECRET_DB_ANALYTICS:-}"
  "${SECRET_TOGETHER_AI:-}"
  "${SECRET_GEMINI_AI:-}"
  "${SECRET_OAUTH_CLIENT:-}"
  "${SECRET_REDIS_ENDPOINT:-}"
  "${SECRET_STORAGE_SIGNER:-}"
)

CLEAN_SECRETS=()
for secret in "${SECRET_NAMES[@]}"; do
  if [[ -n "${secret}" ]]; then
    CLEAN_SECRETS+=("${secret}")
  fi
done

check_names=()
check_statuses=()
check_messages=()
check_remediations=()
warning_checks=()
blocker_checks=()
pass_count=0
warn_count=0
fail_count=0

add_check() {
  local name=$1
  local status=$2
  local message=$3
  local remediation=$4
  check_names+=("${name}")
  check_statuses+=("${status}")
  check_messages+=("${message}")
  check_remediations+=("${remediation}")
  case "${status}" in
    PASS) ((pass_count++)) ;;
    WARN) ((warn_count++)); warning_checks+=("${name}") ;;
    FAIL) ((fail_count++)); blocker_checks+=("${name}") ;;
  esac
}

status_icon() {
  case $1 in
    PASS) printf '✅';;
    WARN) printf '⚠️';;
    FAIL) printf '❌';;
    *) printf '❔';;
  esac
}
check_cloud_run_services() {
  local name="Cloud Run services deployed"
  if ! ${GCLOUD_AVAILABLE} || ! ${JQ_AVAILABLE}; then
    add_check "${name}" "WARN" "Missing gcloud or jq; cannot verify Cloud Run services." "Install gcloud + jq and rerun validation."
    return
  fi

  local missing=()
  local not_ready=()
  local no_traffic=()

  for svc in "${EXPECTED_FASTIFY_SERVICES[@]}"; do
    local tmp_json="$(mktemp)"
    if ! gcloud run services describe "${svc}" \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --format=json > "${tmp_json}" 2>/dev/null; then
      missing+=("${svc}")
      rm -f "${tmp_json}"
      continue
    fi
    local ready
    ready=$(jq -r '.status.conditions[]? | select(.type=="Ready") | .status' "${tmp_json}" 2>/dev/null)
    local traffic
    traffic=$(jq -r '[.status.traffic[]? | .percent] | add // 0' "${tmp_json}" 2>/dev/null)
    if [[ "${ready}" != "True" ]]; then
      not_ready+=("${svc}")
    fi
    if [[ "${traffic}" == "0" ]]; then
      no_traffic+=("${svc}")
    fi
    rm -f "${tmp_json}"
  done

  if (( ${#missing[@]} > 0 )); then
    add_check "${name}" "FAIL" "Missing services: ${missing[*]}" "Deploy missing Fastify services via deploy-cloud-run-services.sh"
    return
  fi

  if (( ${#not_ready[@]} > 0 )) || (( ${#no_traffic[@]} > 0 )); then
    local msg="All services present"
    if (( ${#not_ready[@]} > 0 )); then
      msg+="; not ready: ${not_ready[*]}"
    fi
    if (( ${#no_traffic[@]} > 0 )); then
      msg+="; no traffic allocation: ${no_traffic[*]}"
    fi
    add_check "${name}" "WARN" "${msg}" "Promote revisions and allocate traffic via deploy-production.sh"
    return
  fi

  add_check "${name}" "PASS" "All Fastify services ready with traffic." "None"
}
check_api_gateway() {
  local name="API Gateway configured"
  if ! ${GCLOUD_AVAILABLE}; then
    add_check "${name}" "WARN" "gcloud CLI missing; unable to query API Gateway." "Install gcloud and rerun validation."
    return
  fi

  if ! gcloud services list --enabled --filter="apigateway.googleapis.com" --project="${PROJECT_ID}" --format=value(config.name) >/dev/null 2>&1; then
    add_check "${name}" "FAIL" "API Gateway API disabled." "Enable via gcloud services enable apigateway.googleapis.com"
    return
  fi

  local gateways_json="$(mktemp)"
  if ! gcloud api-gateway gateways list \
      --project="${PROJECT_ID}" \
      --location="${REGION}" \
      --format=json > "${gateways_json}" 2>/dev/null; then
    rm -f "${gateways_json}"
    add_check "${name}" "FAIL" "Failed to list API Gateways." "Deploy the production gateway via deploy-production.sh"
    return
  fi

  local count
  count=$(jq length "${gateways_json}" 2>/dev/null || echo 0)
  if [[ "${count}" == "0" ]]; then
    rm -f "${gateways_json}"
    add_check "${name}" "FAIL" "No API Gateway instances found." "Run the API Gateway deployment step."
    return
  fi

  local active_found="false"
  if ${JQ_AVAILABLE}; then
    active_found=$(jq '[.[] | select(.state=="ACTIVE")] | length > 0' "${gateways_json}" 2>/dev/null || echo false)
  fi
  rm -f "${gateways_json}"

  if [[ "${active_found}" != "true" ]]; then
    add_check "${name}" "WARN" "Gateway present but not ACTIVE." "Check API config deployment and wait for activation."
    return
  fi

  add_check "${name}" "PASS" "API Gateway enabled and active." "None"
}
check_monitoring() {
  local name="Monitoring configured"
  local manifest
  manifest=$(find "${REPO_ROOT}/.monitoring" -name 'monitoring-manifest.json' -print -quit 2>/dev/null || true)
  local dashboards=0
  local alerts=0
  local uptime=0

  if [[ -n "${manifest}" ]] && ${JQ_AVAILABLE}; then
    dashboards=$(jq '.dashboards | length' "${manifest}" 2>/dev/null || echo 0)
    alerts=$(jq '.alertPolicies | length' "${manifest}" 2>/dev/null || echo 0)
    uptime=$(jq '.uptimeChecks | length' "${manifest}" 2>/dev/null || echo 0)
  fi

  if ! ${GCLOUD_AVAILABLE}; then
    add_check "${name}" "WARN" "Monitoring manifest ${manifest:-missing}; gcloud unavailable for live checks." "Ensure monitoring setup executed and rerun with gcloud."
    return
  fi

  local errors=()
  if ! gcloud monitoring dashboards list --project="${PROJECT_ID}" --format=json >/dev/null 2>&1; then
    errors+=("dashboards")
  fi
  if ! gcloud monitoring alert-policies list --project="${PROJECT_ID}" --format=json >/dev/null 2>&1; then
    errors+=("alert-policies")
  fi
  if ! gcloud monitoring uptime-checks list --project="${PROJECT_ID}" --format=json >/dev/null 2>&1; then
    errors+=("uptime-checks")
  fi

  if (( ${#errors[@]} > 0 )); then
    add_check "${name}" "WARN" "Monitoring API queries failed (${errors[*]})." "Confirm ADC credentials and rerun setup-monitoring-and-alerting.sh"
    return
  fi

  if [[ -z "${manifest}" ]] || [[ "${dashboards}" == "0" ]] || [[ "${alerts}" == "0" ]] || [[ "${uptime}" == "0" ]]; then
    add_check "${name}" "WARN" "Monitoring manifest incomplete (dashboards=${dashboards}, alerts=${alerts}, uptime=${uptime})." "Run setup-monitoring-and-alerting.sh"
    return
  fi

  add_check "${name}" "PASS" "Monitoring dashboards, alerts, and uptime checks detected." "None"
}
check_load_tests() {
  local name="Load tests executed"
  local report
  report=$(find "${REPO_ROOT}/.deployment/load-tests" -name 'load-test-report.json' -type f -print | sort | tail -n1)
  if [[ -z "${report}" ]]; then
    add_check "${name}" "FAIL" "No load test report found." "Run run-post-deployment-load-tests.sh"
    return
  fi

  local mtime
  if stat -f %m "${report}" >/dev/null 2>&1; then
    mtime=$(stat -f %m "${report}")
  else
    mtime=$(stat -c %Y "${report}" 2>/dev/null || echo 0)
  fi
  local now=$(date +%s)
  local diff=$(( now - mtime ))
  local seven_days=$(( 7 * 24 * 3600 ))

  if (( diff > seven_days )); then
    add_check "${name}" "WARN" "Load test report older than 7 days (${report})." "Re-run load tests to refresh SLA evidence"
    return
  fi

  if ${JQ_AVAILABLE}; then
    local sla_status
    sla_status=$(jq -r '.slaValidation.status // .slaSummary.status // "unknown"' "${report}" 2>/dev/null || echo "unknown")
    if [[ "${sla_status}" =~ ^([Pp]ass)$ ]]; then
      add_check "${name}" "PASS" "Recent load test report with SLA validation (${report})." "None"
    else
      add_check "${name}" "WARN" "Load test report present but SLA status=${sla_status}." "Investigate SLA gaps and rerun load tests"
    fi
  else
    add_check "${name}" "WARN" "Recent load test report detected (${report}); jq unavailable for SLA parsing." "Install jq to parse SLA metrics"
  fi
}
check_deployment_artifacts() {
  local name="Deployment artifacts present"
  local build_manifest
  local deploy_manifest
  local smoke_report
  build_manifest=$(ls "${REPO_ROOT}"/.deployment/build-manifest-*.json 2>/dev/null | head -n1 || true)
  deploy_manifest=$(ls "${REPO_ROOT}"/.deployment/deploy-manifest-*.json 2>/dev/null | head -n1 || true)
  smoke_report=$(ls "${REPO_ROOT}"/.deployment/smoke-test-report-*.json 2>/dev/null | head -n1 || true)

  if [[ -z "${build_manifest}" || -z "${deploy_manifest}" || -z "${smoke_report}" ]]; then
    add_check "${name}" "WARN" "Missing artifacts: build=${build_manifest:-none}, deploy=${deploy_manifest:-none}, smoke=${smoke_report:-none}." "Re-run deploy-production.sh to regenerate manifests"
    return
  fi

  add_check "${name}" "PASS" "Core deployment artifacts located." "None"
}
check_secrets() {
  local name="Secrets populated"
  if ! ${GCLOUD_AVAILABLE}; then
    add_check "${name}" "WARN" "gcloud CLI missing; unable to verify Secret Manager." "Install gcloud and authenticate"
    return
  fi

  local missing=()
  local outdated=()
  for secret in "${CLEAN_SECRETS[@]}"; do
    if [[ -z "${secret}" ]]; then
      continue
    fi
    if ! gcloud secrets describe "${secret}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
      missing+=("${secret}")
      continue
    fi
    local latest
    latest=$(gcloud secrets versions list "${secret}" --project="${PROJECT_ID}" --limit=1 --format="value(state)" 2>/dev/null || echo "")
    if [[ "${latest}" != "ENABLED" ]]; then
      outdated+=("${secret}")
    fi
  done

  if (( ${#missing[@]} > 0 )); then
    add_check "${name}" "FAIL" "Missing secrets: ${missing[*]}" "Provision secrets in Secret Manager"
    return
  fi
  if (( ${#outdated[@]} > 0 )); then
    add_check "${name}" "WARN" "Secrets without enabled versions: ${outdated[*]}" "Add active versions before deployment"
    return
  fi

  add_check "${name}" "PASS" "Required secrets exist with active versions." "None"
}
check_infrastructure() {
  local name="Infrastructure provisioned"
  if ! ${GCLOUD_AVAILABLE}; then
    add_check "${name}" "WARN" "gcloud CLI missing; infrastructure checks skipped." "Install gcloud and rerun validation"
    return
  fi

  local failures=()
  if ! gcloud sql instances describe "${SQL_INSTANCE}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    failures+=("Cloud SQL ${SQL_INSTANCE}")
  fi
  if ! gcloud redis instances describe "${REDIS_INSTANCE}" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    failures+=("Redis ${REDIS_INSTANCE}")
  fi
  if ! gcloud firestore databases describe --project="${PROJECT_ID}" --database="(default)" >/dev/null 2>&1; then
    failures+=("Firestore (default)")
  fi
  if ! gcloud pubsub topics list --project="${PROJECT_ID}" --filter="name:profiles.refresh.request" --format=value(name) | grep -q .; then
    failures+=("Pub/Sub topics")
  fi
  if ! gcloud compute networks vpc-access connectors describe "${VPC_CONNECTOR}" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    failures+=("VPC connector ${VPC_CONNECTOR}")
  fi

  if (( ${#failures[@]} > 0 )); then
    add_check "${name}" "FAIL" "Infrastructure gaps: ${failures[*]}" "Re-run infrastructure provisioning scripts"
    return
  fi

  add_check "${name}" "PASS" "Core infrastructure resources detected." "None"
}
check_adc() {
  local name="ADC credentials configured"
  if ! ${GCLOUD_AVAILABLE}; then
    add_check "${name}" "WARN" "gcloud CLI missing; cannot verify ADC." "Install gcloud and run gcloud auth application-default login"
    return
  fi

  if gcloud auth application-default print-access-token >/dev/null 2>&1; then
    add_check "${name}" "PASS" "Application Default Credentials available." "None"
  else
    add_check "${name}" "FAIL" "Application Default Credentials not configured." "Run gcloud auth application-default login"
  fi
}
json_escape() {
  if ${PYTHON_AVAILABLE}; then
    python3 - <<'PY'
import json, sys
print(json.dumps(sys.stdin.read())[1:-1])
PY
  else
    sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
  fi
}

write_report() {
  local total=${#check_names[@]}
  local readiness_score=0
  if (( total > 0 )) && ${PYTHON_AVAILABLE}; then
    readiness_score=$(python3 - <<PY
passes=${pass_count}
total=${total}
print(round((passes/total)*100, 2))
PY
)
  fi

  local overall_status="READY"
  if (( fail_count > 0 )); then
    overall_status="BLOCKED"
  elif (( warn_count > 0 )); then
    overall_status="PARTIAL"
  fi

  {
    printf '{\n'
    printf '  "timestamp": "%s",\n' "${TIMESTAMP_UTC}"
    printf '  "projectId": "%s",\n' "${PROJECT_ID}"
    printf '  "environment": "%s",\n' "${ENVIRONMENT}"
    printf '  "overallStatus": "%s",\n' "${overall_status}"
    printf '  "readinessScore": %.2f,\n' "${readiness_score}"
    printf '  "checks": [\n'
    local i
    for i in "${!check_names[@]}"; do
      local name=${check_names[$i]}
      local status=${check_statuses[$i]}
      local message=${check_messages[$i]}
      local remediation=${check_remediations[$i]}
      printf '    {"id": %d, "name": "%s", "status": "%s", "message": "%s", "remediation": "%s"}' \
        "$i" \
        "$(printf '%s' "${name}" | json_escape)" \
        "${status}" \
        "$(printf '%s' "${message}" | json_escape)" \
        "$(printf '%s' "${remediation}" | json_escape)"
      if [[ $i -lt $((total-1)) ]]; then
        printf ',\n'
      else
        printf '\n'
      fi
    done
    printf '  ],\n'
    printf '  "blockers": ['
    local first=true
    for blocker in "${blocker_checks[@]}"; do
      if [[ "${first}" == true ]]; then
        first=false
      else
        printf ', '
      fi
      printf '"%s"' "$(printf '%s' "${blocker}" | json_escape)"
    done
    printf '],\n'
    printf '  "warnings": ['
    first=true
    for warn in "${warning_checks[@]}"; do
      if [[ "${first}" == true ]]; then
        first=false
      else
        printf ', '
      fi
      printf '"%s"' "$(printf '%s' "${warn}" | json_escape)"
    done
    printf ']\n'
    printf '}\n'
  } > "${REPORT_PATH}"
}

print_summary() {
  printf '| Check | Status | Message |\n'
  printf '| --- | --- | --- |\n'
  local i
  for i in "${!check_names[@]}"; do
    printf '| %s | %s %s | %s |\n' \
      "${check_names[$i]}" \
      "$(status_icon "${check_statuses[$i]}")" \
      "${check_statuses[$i]}" \
      "${check_messages[$i]}"
  done
  local overall_status="READY"
  if (( fail_count > 0 )); then
    overall_status="BLOCKED"
  elif (( warn_count > 0 )); then
    overall_status="PARTIAL"
  fi
  printf '\nOverall readiness: %s\n' "${overall_status}"
  printf 'Pass: %d  Warn: %d  Fail: %d\n' "${pass_count}" "${warn_count}" "${fail_count}"
  printf 'Validation report: %s\n' "${REPORT_PATH}"

  if (( fail_count > 0 )); then
    printf '\nBlockers to address:\n'
    for blocker in "${blocker_checks[@]}"; do
      printf ' - %s\n' "${blocker}"
    done
  fi
  if (( warn_count > 0 )); then
    printf '\nWarnings to review:\n'
    for warn in "${warning_checks[@]}"; do
      printf ' - %s\n' "${warn}"
    done
  fi
}
check_cloud_run_services
check_api_gateway
check_monitoring
check_load_tests
check_deployment_artifacts
check_secrets
check_infrastructure
check_adc

print_summary
write_report

overall_exit=0
if (( fail_count > 0 )); then
overall_exit=1
elif (( warn_count > 0 )); then
overall_exit=2
fi

if ${STRICT_MODE}; then
  if (( warn_count > 0 )) || (( fail_count > 0 )); then
    overall_exit=1
  fi
fi

exit ${overall_exit}
