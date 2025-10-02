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
SKIP_PREREQ=false
SKIP_INFRA=false
SKIP_IAM=false
SKIP_CONFIG=false
SKIP_DEPLOY=false
SKIP_VALIDATION=false
SKIP_MONITORING=false
SKIP_TESTS=false
GENERATE_REPORT=true
ROLLBACK_ON_FAIL=true
REPORT_PATH=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [OPTIONS]

Run the end-to-end production deployment pipeline for all Cloud Run services.

Options:
  --project-id ID          Override project id from config
  --region REGION          Override region from config
  --config PATH            Infrastructure config path (default: ${DEFAULT_CONFIG})
  --environment ENV        Environment suffix (default: production)
  --dry-run                Print the actions without executing mutating steps
  --no-prereq              Skip prerequisite validation
  --no-infra               Skip infrastructure provisioning
  --no-iam                 Skip IAM configuration
  --no-config              Skip environment/secrets configuration
  --no-deploy              Skip Cloud Run deployment
  --no-validation          Skip inter-service validation
  --no-monitoring          Skip monitoring setup
  --no-tests               Skip post-deployment test suite
  --no-report              Skip writing the deployment report to disk
  --no-rollback            Do not attempt rollback on failure
  --report PATH            Write deployment report to PATH instead of stdout
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
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --no-prereq)
      SKIP_PREREQ=true
      shift
      ;;
    --no-infra)
      SKIP_INFRA=true
      shift
      ;;
    --no-iam)
      SKIP_IAM=true
      shift
      ;;
    --no-config)
      SKIP_CONFIG=true
      shift
      ;;
    --no-deploy)
      SKIP_DEPLOY=true
      shift
      ;;
    --no-validation)
      SKIP_VALIDATION=true
      shift
      ;;
    --no-monitoring)
      SKIP_MONITORING=true
      shift
      ;;
    --no-tests)
      SKIP_TESTS=true
      shift
      ;;
    --no-report)
      GENERATE_REPORT=false
      shift
      ;;
    --no-rollback)
      ROLLBACK_ON_FAIL=false
      shift
      ;;
    --report)
      REPORT_PATH="$2"
      shift 2
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
if [[ -z "${PROJECT_ID}" || -z "${REGION}" ]]; then
  echo "Project id and region must be provided via config or flags" >&2
  exit 1
fi

PREREQ_SCRIPT="${SCRIPT_DIR}/validate_deployment_prerequisites.sh"
INFRA_SCRIPT="${SCRIPT_DIR}/setup_headhunter_infrastructure.sh"
IAM_SCRIPT="${SCRIPT_DIR}/setup_service_iam.sh"
CONFIG_SCRIPT="${SCRIPT_DIR}/configure_production_environment.sh"
DEPLOY_SCRIPT="${SCRIPT_DIR}/manage_service_dependencies.sh"
COMM_SCRIPT="${SCRIPT_DIR}/validate_service_communication.sh"
MONITOR_SCRIPT="${SCRIPT_DIR}/setup_production_monitoring.sh"
TEST_SCRIPT="${SCRIPT_DIR}/test_production_deployment.sh"
ROLLBACK_SCRIPT="${SCRIPT_DIR}/rollback_production_deployment.sh"
STATUS_DASHBOARD="${SCRIPT_DIR}/deployment_status_dashboard.py"

for path in "${PREREQ_SCRIPT}" "${INFRA_SCRIPT}" "${IAM_SCRIPT}" "${CONFIG_SCRIPT}" "${DEPLOY_SCRIPT}" "${COMM_SCRIPT}" "${MONITOR_SCRIPT}" "${TEST_SCRIPT}" "${ROLLBACK_SCRIPT}"; do
  [[ -f "${path}" ]] || { echo "Required script missing: ${path}" >&2; exit 1; }
done

log() {
  printf '[deploy-stack][%s] %s\n' "${ENVIRONMENT}" "$*" >&2
}

WARNINGS=()
REPORT="Production deployment report\nProject: ${PROJECT_ID}\nRegion: ${REGION}\nEnvironment: ${ENVIRONMENT}\nStarted: $(date -Is)\n\n"
append_report() {
  REPORT+="$1\n"
}

on_error() {
  local exit_code=$1
  local line=$2
  log "Deployment failed at line ${line} (exit code ${exit_code})"
  append_report "[FAIL] Deployment aborted at line ${line}"
  if [[ "${ROLLBACK_ON_FAIL}" == true ]]; then
    log "Triggering rollback via ${ROLLBACK_SCRIPT}"
    if [[ "${DRY_RUN}" == true ]]; then
      log "DRY-RUN enabled: skipping rollback execution"
    else
      PROJECT_ID="${PROJECT_ID}" REGION="${REGION}" ENVIRONMENT="${ENVIRONMENT}" "${ROLLBACK_SCRIPT}" --project-id "${PROJECT_ID}" --region "${REGION}" --environment "${ENVIRONMENT}" || log "Rollback encountered errors"
    fi
  else
    log "Rollback disabled"
  fi
  finalize_report true
  exit "${exit_code}"
}

trap 'on_error $? ${LINENO}' ERR

run_step() {
  local step_name=$1
  shift
  local start_ts
  start_ts=$(date +%s)
  log "Starting ${step_name}"
  append_report "[START] ${step_name}"
  if [[ "${DRY_RUN}" == true ]]; then
    log "DRY-RUN: would execute $*"
    append_report "[SKIPPED] ${step_name} (dry-run)"
    return 0
  fi
  if "$@"; then
    local end_ts
    end_ts=$(date +%s)
    local elapsed=$((end_ts - start_ts))
    append_report "[DONE] ${step_name} (${elapsed}s)"
    log "Completed ${step_name} (${elapsed}s)"
    return 0
  fi
  return 1
}

finalize_report() {
  local errored=${1:-false}
  append_report "\nFinished: $(date -Is)"
  if [[ "${WARNINGS[*]:-}" ]]; then
    append_report "Warnings: ${WARNINGS[*]}"
  fi
  if [[ "${errored}" == true ]]; then
    append_report "Status: FAILED"
  else
    append_report "Status: SUCCESS"
  fi
  if [[ "${GENERATE_REPORT}" != true ]]; then
    return
  fi
  if [[ -n "${REPORT_PATH}" ]]; then
    printf '%s\n' "${REPORT}" >"${REPORT_PATH}"
    log "Report written to ${REPORT_PATH}"
  else
    printf '%s\n' "${REPORT}"
  fi
}

if [[ "${SKIP_PREREQ}" != true ]]; then
  run_step "Validate prerequisites" "${PREREQ_SCRIPT}" --project-id "${PROJECT_ID}" --config "${CONFIG_FILE}" || exit 1
fi

if [[ "${SKIP_INFRA}" != true ]]; then
  infra_args=("${INFRA_SCRIPT}" --project-id "${PROJECT_ID}" --config "${CONFIG_FILE}")
  [[ "${DRY_RUN}" == true ]] && infra_args+=(--dry-run)
  run_step "Provision infrastructure" "${infra_args[@]}"
fi

if [[ "${SKIP_IAM}" != true ]]; then
  run_step "Configure IAM" env PROJECT_ID="${PROJECT_ID}" REGION="${REGION}" "${IAM_SCRIPT}" "${ENVIRONMENT}"
fi

if [[ "${SKIP_CONFIG}" != true ]]; then
  config_args=("${CONFIG_SCRIPT}" --project-id "${PROJECT_ID}" --config "${CONFIG_FILE}" --environment "${ENVIRONMENT}")
  [[ "${DRY_RUN}" == true ]] && config_args+=(--dry-run)
  run_step "Configure production environment" "${config_args[@]}"
fi

if [[ "${SKIP_DEPLOY}" != true ]]; then
  deploy_args=("${DEPLOY_SCRIPT}" --project-id "${PROJECT_ID}" --region "${REGION}" --config "${CONFIG_FILE}" --environment "${ENVIRONMENT}")
  [[ "${DRY_RUN}" == true ]] && deploy_args+=(--dry-run)
  run_step "Deploy Cloud Run services" "${deploy_args[@]}"
fi

if [[ "${SKIP_CONFIG}" != true && "${SKIP_DEPLOY}" != true ]]; then
  post_config_args=("${CONFIG_SCRIPT}" --project-id "${PROJECT_ID}" --config "${CONFIG_FILE}" --environment "${ENVIRONMENT}")
  [[ "${DRY_RUN}" == true ]] && post_config_args+=(--dry-run)
  run_step "Refresh production environment configuration" "${post_config_args[@]}"
fi

if [[ "${SKIP_VALIDATION}" != true ]]; then
  validation_args=("${COMM_SCRIPT}" --project-id "${PROJECT_ID}" --region "${REGION}" --environment "${ENVIRONMENT}")
  [[ "${DRY_RUN}" == true ]] && validation_args+=(--dry-run)
  run_step "Validate service communication" "${validation_args[@]}"
fi

if [[ "${SKIP_MONITORING}" != true ]]; then
  monitoring_args=("${MONITOR_SCRIPT}" --project-id "${PROJECT_ID}" --region "${REGION}" --environment "${ENVIRONMENT}")
  [[ "${DRY_RUN}" == true ]] && monitoring_args+=(--dry-run)
  run_step "Configure monitoring and alerting" "${monitoring_args[@]}"
fi

if [[ "${SKIP_TESTS}" != true ]]; then
  test_args=("${TEST_SCRIPT}" --project-id "${PROJECT_ID}" --region "${REGION}" --environment "${ENVIRONMENT}")
  [[ "${DRY_RUN}" == true ]] && test_args+=(--dry-run)
  run_step "Execute production verification tests" "${test_args[@]}"
fi

if [[ -x "${STATUS_DASHBOARD}" ]]; then
  dashboard_args=("${STATUS_DASHBOARD}" --project-id "${PROJECT_ID}" --region "${REGION}" --environment "${ENVIRONMENT}")
  [[ "${DRY_RUN}" == true ]] && dashboard_args+=(--dry-run)
  run_step "Update deployment status dashboard" "${dashboard_args[@]}"
fi

trap - ERR
finalize_report false
