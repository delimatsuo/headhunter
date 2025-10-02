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
PROJECT_ID=""
OUTPUT_FILE=""
AUTO_FIX=false
DRY_RUN=false
VERBOSE=false

usage() {
  cat <<USAGE
Usage: $(basename "$0") [OPTIONS]

Validates that all prerequisites for the production Cloud Run deployment are satisfied.

Options:
  --project-id ID          Override the project id declared in the config
  --config PATH            Path to the infrastructure config (default: ${DEFAULT_CONFIG})
  --output PATH            Write the readiness report to PATH
  --auto-fix               Attempt to automatically resolve common issues
  --dry-run                Only report actions, do not execute mutating fixes
  -v, --verbose            Log verbose diagnostic information
  -h, --help               Show this help message and exit
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      CLI_PROJECT_ID="$2"
      shift 2
      ;;
    --config)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    --auto-fix)
      AUTO_FIX=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -v|--verbose)
      VERBOSE=true
      shift
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

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "Config file ${CONFIG_FILE} not found" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${CONFIG_FILE}"
CONFIG_PROJECT_ID="${PROJECT_ID:-}"
PROJECT_ID="${CLI_PROJECT_ID:-${CONFIG_PROJECT_ID}}"
if [[ -z "${PROJECT_ID}" ]]; then
  echo "Project id must be provided via --project-id or config" >&2
  exit 1
fi

REGISTRY_HOST="${ARTIFACT_REGISTRY%%/*}"

PASSED=0
FAILED=0
WARNED=0
REPORT="Production deployment prerequisite report for ${PROJECT_ID}\nGenerated: $(date -Is)\n\n"

log() {
  printf '[prereq] %s\n' "$*" >&2
}

verb() {
  [[ "${VERBOSE}" == true ]] && log "$@"
}

append_report() {
  REPORT+="$1\n"
}

result_pass() {
  PASSED=$((PASSED + 1))
  append_report "[PASS] $1"
}

result_fail() {
  FAILED=$((FAILED + 1))
  append_report "[FAIL] $1"
}

result_warn() {
  WARNED=$((WARNED + 1))
  append_report "[WARN] $1"
}

require_command() {
  local cmd=$1
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    result_fail "${cmd} CLI not installed"
    return 1
  fi
  result_pass "${cmd} CLI available"
}

exec_checked() {
  if ! "$@" >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

attempt_fix() {
  local description=$1
  shift
  if [[ "${AUTO_FIX}" != true ]]; then
    result_warn "AUTO_FIX disabled: ${description}"
    return 1
  fi
  if [[ "${DRY_RUN}" == true ]]; then
    result_warn "DRY_RUN enabled: would execute: $*"
    return 1
  fi
  log "Attempting auto-fix: ${description}"
  if "$@"; then
    result_pass "Auto-fix succeeded: ${description}"
    return 0
  fi
  result_fail "Auto-fix failed: ${description}"
  return 1
}

check_docker_helper() {
  local config_file="${HOME}/.docker/config.json"
  local host="${REGISTRY_HOST:-}"
  if [[ -z "${host}" ]]; then
    result_warn "Artifact registry host not defined; skipping docker helper check"
    return
  fi
  if [[ -f "${config_file}" ]] && jq -e --arg host "${host}" '.credHelpers[$host] // .credHelpers[("https://" + $host)]' "${config_file}" >/dev/null 2>&1; then
    result_pass "Docker credential helper configured for ${host}"
    return
  fi
  if attempt_fix "Configure Docker credential helper for ${host}" gcloud auth configure-docker "${host}" --quiet; then
    return
  fi
  result_fail "Docker credential helper missing for ${host}"
}

log "Validating tooling"
require_command gcloud || true
require_command docker || true
require_command jq || true
require_command curl || true

if exec_checked gcloud auth list --filter=status:ACTIVE --format=value(account); then
  ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format=value(account))
  if [[ -n "${ACTIVE_ACCOUNT}" ]]; then
    result_pass "gcloud authenticated as ${ACTIVE_ACCOUNT}"
  else
    result_fail "gcloud has no active account"
  fi
else
  result_fail "Unable to query gcloud authentication state"
fi

if exec_checked gcloud projects describe "${PROJECT_ID}"; then
  result_pass "Project ${PROJECT_ID} accessible"
else
  result_fail "Project ${PROJECT_ID} not accessible"
fi

check_docker_helper

REQUIRED_APIS=(
  run.googleapis.com
  artifactregistry.googleapis.com
  compute.googleapis.com
  servicenetworking.googleapis.com
  sqladmin.googleapis.com
  redis.googleapis.com
  secretmanager.googleapis.com
  pubsub.googleapis.com
  iam.googleapis.com
  cloudbuild.googleapis.com
  logging.googleapis.com
  monitoring.googleapis.com
  cloudtrace.googleapis.com
  cloudscheduler.googleapis.com
  eventarc.googleapis.com
)

append_report "\n--- API enablement ---"
for api in "${REQUIRED_APIS[@]}"; do
  if gcloud services list --enabled --project="${PROJECT_ID}" --filter="config.name=${api}" --format="value(config.name)" | grep -qx "${api}"; then
    result_pass "${api} enabled"
  else
    result_fail "${api} missing"
    attempt_fix "Enable ${api}" gcloud services enable "${api}" --project="${PROJECT_ID}" || true
  fi
done

append_report "\n--- Artifact registry ---"
if exec_checked gcloud artifacts repositories describe "${ARTIFACT_REGISTRY##*/}" --project="${PROJECT_ID}" --location="${REGION}"; then
  result_pass "Artifact Registry ${ARTIFACT_REGISTRY} available"
else
  result_fail "Artifact Registry ${ARTIFACT_REGISTRY} missing"
fi

append_report "\n--- Cloud SQL ---"
if exec_checked gcloud sql instances describe "${SQL_INSTANCE}" --project="${PROJECT_ID}"; then
  result_pass "Cloud SQL instance ${SQL_INSTANCE} exists"
else
  result_fail "Cloud SQL instance ${SQL_INSTANCE} missing"
fi
if exec_checked gcloud sql databases describe "${SQL_DATABASE}" --instance="${SQL_INSTANCE}" --project="${PROJECT_ID}"; then
  result_pass "Database ${SQL_DATABASE} exists in ${SQL_INSTANCE}"
else
  result_fail "Database ${SQL_DATABASE} missing in ${SQL_INSTANCE}"
fi

append_report "\n--- Redis ---"
if exec_checked gcloud redis instances describe "${REDIS_INSTANCE}" --region="${REGION}" --project="${PROJECT_ID}"; then
  result_pass "Redis instance ${REDIS_INSTANCE} exists"
else
  result_fail "Redis instance ${REDIS_INSTANCE} missing"
fi

append_report "\n--- Pub/Sub ---"
PUBSUB_RESOURCES=(
  "topics/${PUBSUB_TOPIC_PROFILES}"
  "topics/${PUBSUB_TOPIC_POSTINGS}"
  "topics/${PUBSUB_TOPIC_ENRICH}"
  "topics/${PUBSUB_TOPIC_ALERTS}"
  "subscriptions/${PUBSUB_SUBSCRIPTION_PROFILES}"
  "subscriptions/${PUBSUB_SUBSCRIPTION_POSTINGS}"
  "subscriptions/${PUBSUB_SUBSCRIPTION_ENRICH}"
  "subscriptions/${PUBSUB_SUBSCRIPTION_ALERTS}"
)
for resource in "${PUBSUB_RESOURCES[@]}"; do
  resource_type="${resource%%/*}"
  resource_name="${resource#*/}"
  if exec_checked gcloud pubsub "${resource_type}" describe "${resource_name}" --project="${PROJECT_ID}"; then
    result_pass "Pub/Sub ${resource} exists"
  else
    result_fail "Pub/Sub ${resource} missing"
  fi
done

append_report "\n--- Secret Manager ---"
SECRETS=(
  "${SECRET_DB_PRIMARY}"
  "${SECRET_DB_REPLICA}"
  "${SECRET_DB_ANALYTICS}"
  "${SECRET_DB_OPERATIONS:-}"
  "${SECRET_REDIS_ENDPOINT}"
  "${SECRET_TOGETHER_AI}"
  "${SECRET_GEMINI_AI}"
  "${SECRET_ADMIN_JWT}"
  "${SECRET_WEBHOOK}"
  "${SECRET_OAUTH_CLIENT}"
  "${SECRET_EDGE_CACHE}"
)
for secret in "${SECRETS[@]}"; do
  [[ -z "${secret}" ]] && continue
  if exec_checked gcloud secrets describe "${secret}" --project="${PROJECT_ID}"; then
    result_pass "Secret ${secret} exists"
  else
    result_fail "Secret ${secret} missing"
  fi
done

append_report "\n--- IAM service accounts ---"
SERVICE_ACCOUNTS=(
  "${SVC_EMBED}"
  "${SVC_SEARCH}"
  "${SVC_RERANK}"
  "${SVC_EVIDENCE}"
  "${SVC_ECO}"
  "${SVC_ENRICH}"
  "${SVC_ADMIN}"
  "${SVC_MSGS}"
  "${SVC_PIPELINE}"
  "${SVC_MONITORING}"
)
for sa in "${SERVICE_ACCOUNTS[@]}"; do
  [[ -z "${sa}" ]] && continue
  if exec_checked gcloud iam service-accounts describe "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" --project="${PROJECT_ID}"; then
    result_pass "Service account ${sa}@${PROJECT_ID}.iam.gserviceaccount.com exists"
  else
    result_fail "Service account ${sa}@${PROJECT_ID}.iam.gserviceaccount.com missing"
  fi
done

append_report "\n--- Docker environment ---"
if exec_checked docker info; then
  result_pass "Docker daemon reachable"
else
  result_fail "Docker daemon not available"
fi

append_report "\n--- External integrations ---"
if exec_checked gcloud secrets versions access latest --secret="${SECRET_TOGETHER_AI}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  API_KEY=$(gcloud secrets versions access latest --secret="${SECRET_TOGETHER_AI}" --project="${PROJECT_ID}")
  if [[ -n "${API_KEY}" ]]; then
    result_pass "Together AI secret retrieved"
  else
    result_fail "Together AI secret empty"
  fi
else
  result_fail "Unable to access Together AI secret ${SECRET_TOGETHER_AI}"
fi

if exec_checked gcloud secrets versions access latest --secret="${SECRET_GEMINI_AI}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  result_pass "Gemini secret retrieved"
else
  result_fail "Unable to access Gemini secret ${SECRET_GEMINI_AI}"
fi

append_report "\n--- Connectivity checks ---"
TOGETHER_TEST_URL="https://api.together.xyz/info"
GEMINI_TEST_URL="https://generativelanguage.googleapis.com/v1beta/models"
if curl -fsSL --max-time 5 "${TOGETHER_TEST_URL}" >/dev/null 2>&1; then
  result_pass "Outbound connectivity to Together AI verified"
else
  result_warn "Unable to reach Together AI endpoint ${TOGETHER_TEST_URL}; ensure VPC egress rules permit access"
fi
if curl -fsSL --max-time 5 "${GEMINI_TEST_URL}" >/dev/null 2>&1; then
  result_pass "Outbound connectivity to Gemini verified"
else
  result_warn "Unable to reach Gemini endpoint ${GEMINI_TEST_URL}; verify egress configuration"
fi

append_report "\n--- Summary ---"
append_report "Pass: ${PASSED}"
append_report "Warn: ${WARNED}"
append_report "Fail: ${FAILED}"

if [[ -n "${OUTPUT_FILE}" ]]; then
  printf '%s\n' "${REPORT}" >"${OUTPUT_FILE}"
  log "Report written to ${OUTPUT_FILE}"
else
  printf '%s\n' "${REPORT}"
fi

if [[ ${FAILED} -gt 0 ]]; then
  exit 1
fi
