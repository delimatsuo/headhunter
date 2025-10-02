#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CONFIG_FILE="${SCRIPT_DIR}/../config/infrastructure/headhunter-production.env"
CLI_PROJECT_ID=""
DRY_RUN=false

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--project-id PROJECT_ID] [--config PATH] [--dry-run]

Orchestrates the full headhunter GCP infrastructure provisioning flow.
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
    --dry-run)
      DRY_RUN=true
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

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Config file ${CONFIG_FILE} not found" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"
CONFIG_PROJECT_ID="${PROJECT_ID:-}"
PROJECT_ID="${CLI_PROJECT_ID:-${CONFIG_PROJECT_ID}}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "Project ID must be provided via --project-id or config" >&2
  exit 1
fi

log() {
  echo "[$(date -Is)] $*" >&2
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "${1} must be installed" >&2
    exit 1
  }
}

ensure_service_account() {
  local sa=$1
  local display=$2
  local email="${sa}@${PROJECT_ID}.iam.gserviceaccount.com"
  if gcloud iam service-accounts describe "$email" --project="$PROJECT_ID" >/dev/null 2>&1; then
    return
  fi
  log "Creating service account ${email}"
  gcloud iam service-accounts create "$sa" \
    --project="$PROJECT_ID" \
    --display-name="$display"
}

SERVICE_ACCOUNTS=(
  "$SVC_PROFILES:Profiles pipeline"
  "$SVC_POSTINGS:Postings pipeline"
  "$SVC_MSGS:MSGS orchestrator"
  "$SVC_SEARCH:Search ingestion"
  "$SVC_ADMIN:Admin API"
  "$SVC_REFRESH:Refresh runner"
  "$SVC_UI:UI backend"
  "$SVC_INSIGHTS:Insights service"
)

log "Validating prerequisites"
require_command gcloud
require_command gsutil

if [[ "$DRY_RUN" == "true" ]]; then
  log "Running in dry-run mode; commands will be listed but not executed"
fi

run_step() {
  local description=$1
  shift
  log "$description"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "DRY RUN: $*"
  else
    "$@"
  fi
}

if [[ "$DRY_RUN" == "false" ]]; then
  gcloud config set project "$PROJECT_ID" >/dev/null
  for entry in "${SERVICE_ACCOUNTS[@]}"; do
    sa_key=${entry%%:*}
    sa_desc=${entry#*:}
    [[ -z "$sa_key" ]] && continue
    ensure_service_account "$sa_key" "$sa_desc"
  done
fi

run_step "Enabling required APIs" \
  "${SCRIPT_DIR}/enable_required_apis.sh" --project-id "$PROJECT_ID"

run_step "Configuring Secret Manager" \
  "${SCRIPT_DIR}/setup_secret_manager_headhunter.sh" --project-id "$PROJECT_ID" --config "$CONFIG_FILE"

run_step "Configuring networking" \
  "${SCRIPT_DIR}/setup_vpc_networking.sh" --project-id "$PROJECT_ID" --config "$CONFIG_FILE"

run_step "Provisioning Cloud SQL" \
  "${SCRIPT_DIR}/setup_cloud_sql_headhunter.sh" --project-id "$PROJECT_ID" --config "$CONFIG_FILE"

run_step "Provisioning Memorystore Redis" \
  "${SCRIPT_DIR}/setup_redis_headhunter.sh" --project-id "$PROJECT_ID" --config "$CONFIG_FILE"

run_step "Provisioning Pub/Sub" \
  "${SCRIPT_DIR}/setup_pubsub_headhunter.sh" --project-id "$PROJECT_ID" --config "$CONFIG_FILE"

run_step "Configuring Cloud Storage" \
  "${SCRIPT_DIR}/setup_cloud_storage_headhunter.sh" --project-id "$PROJECT_ID" --config "$CONFIG_FILE"

run_step "Running validation" \
  "${SCRIPT_DIR}/validate_headhunter_infrastructure.sh" --project-id "$PROJECT_ID" --config "$CONFIG_FILE"

log "All steps completed"
