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
TARGET_REVISION=""
REPORT_PATH=""
DRY_RUN=false
EMERGENCY_STOP=false
SERVICES=()

usage() {
  cat <<USAGE
Usage: $(basename "$0") [OPTIONS]

Rollback Cloud Run services to a previous revision or perform an emergency freeze.

Options:
  --project-id ID          Override project id from config
  --region REGION          Override region from config
  --config PATH            Infrastructure config path (default: ${DEFAULT_CONFIG})
  --environment ENV        Environment suffix (default: production)
  --service NAME           Limit rollback to a specific service (repeatable)
  --target-revision REV    Explicit revision name to restore (applied to all services)
  --emergency-stop         Scale services to zero and restrict ingress (no traffic)
  --report PATH            Write rollback report to PATH
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
    --service)
      SERVICES+=("$2")
      shift 2
      ;;
    --target-revision)
      TARGET_REVISION="$2"
      shift 2
      ;;
    --emergency-stop)
      EMERGENCY_STOP=true
      shift
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
if [[ -z "${PROJECT_ID}" || -z "${REGION}" ]]; then
  echo "Project id and region must be provided" >&2
  exit 1
fi

DEFAULT_SERVICES=(
  hh-embed-svc
  hh-search-svc
  hh-rerank-svc
  hh-evidence-svc
  hh-eco-svc
  hh-enrich-svc
  hh-admin-svc
  hh-msgs-svc
)

if [[ ${#SERVICES[@]} -eq 0 ]]; then
  SERVICES=("${DEFAULT_SERVICES[@]}")
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || { echo "$1 CLI is required" >&2; exit 1; }
}

require_command gcloud

log() {
  printf '[rollback][%s] %s\n' "${ENVIRONMENT}" "$*" >&2
}

run_or_echo() {
  if [[ "${DRY_RUN}" == true ]]; then
    log "DRY-RUN: $*"
  else
    "$@"
  fi
}

select_revision() {
  local service=$1
  if [[ -n "${TARGET_REVISION}" ]]; then
    printf '%s' "${TARGET_REVISION}"
    return 0
  fi
  local revisions
  revisions=$(gcloud run revisions list --service="${service}-${ENVIRONMENT}" \
    --project="${PROJECT_ID}" --region="${REGION}" --format='value(metadata.name)' --limit=5 || true)
  local chosen=""
  local index=0
  while read -r rev; do
    if [[ -z "${rev}" ]]; then
      continue
    fi
    if (( index == 1 )); then
      chosen="${rev}"
      break
    fi
    ((index++))
  done <<<"${revisions}"
  printf '%s' "${chosen}"
}

set_ingress_internal() {
  local service=$1
  run_or_echo gcloud run services update "${service}-${ENVIRONMENT}" \
    --project="${PROJECT_ID}" --region="${REGION}" \
    --ingress internal
}

scale_to_zero() {
  local service=$1
  run_or_echo gcloud run services update "${service}-${ENVIRONMENT}" \
    --project="${PROJECT_ID}" --region="${REGION}" \
    --min-instances=0
}

switch_traffic() {
  local service=$1
  local revision=$2
  run_or_echo gcloud run services update-traffic "${service}-${ENVIRONMENT}" \
    --project="${PROJECT_ID}" --region="${REGION}" \
    --to-revisions "${revision}=100"
}

REPORT="Rollback execution report\nProject: ${PROJECT_ID}\nRegion: ${REGION}\nEnvironment: ${ENVIRONMENT}\nGenerated: $(date -Is)\n\n"
append_report() {
  REPORT+="$1\n"
}

EXIT_CODE=0

for service in "${SERVICES[@]}"; do
  append_report "Service: ${service}-${ENVIRONMENT}"
  if [[ "${EMERGENCY_STOP}" == true ]]; then
    set_ingress_internal "${service}"
    scale_to_zero "${service}"
    append_report "  action: emergency-stop (ingress=internal, min-instances=0)"
    continue
  fi

  target="$(select_revision "${service}")"
  if [[ -z "${target}" ]]; then
    append_report "  status: FAILED (no prior revision found)"
    EXIT_CODE=1
    continue
  fi
  append_report "  targetRevision: ${target}"
  switch_traffic "${service}" "${target}"
  append_report "  status: OK"

done

if [[ -n "${REPORT_PATH}" ]]; then
  printf '%s\n' "${REPORT}" >"${REPORT_PATH}"
  log "Report written to ${REPORT_PATH}"
else
  printf '%s\n' "${REPORT}"
fi

exit ${EXIT_CODE}
