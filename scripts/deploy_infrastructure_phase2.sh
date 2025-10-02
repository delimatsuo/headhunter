#!/usr/bin/env bash

SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Phase 2 infrastructure orchestrator: Cloud SQL (pgvector + ECO), Redis, secrets, and validation.

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BLUE="\033[0;34m"; GREEN="\033[0;32m"; YELLOW="\033[0;33m"; RED="\033[0;31m"; NC="\033[0m"
log()  { echo -e "${BLUE}[infra-phase2]${NC} $*"; }
ok()   { echo -e "${GREEN}[ok]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*" 1>&2; }

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--env-file path] [--skip-secrets] [--skip-validation]

Options:
  --env-file PATH      Path to the environment file (defaults to <repo>/.env)
  --skip-secrets       Skip the configure_secrets step
  --skip-validation    Skip validation checks after deployment
USAGE
}

ENV_FILE=""
SKIP_SECRETS=false
SKIP_VALIDATION=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      [[ $# -lt 2 ]] && { err "--env-file requires a path"; usage; exit 1; }
      ENV_FILE="$2"
      shift 2
      ;;
    --skip-secrets)
      SKIP_SECRETS=true
      shift
      ;;
    --skip-validation)
      SKIP_VALIDATION=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      err "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

ENV_FILE=${ENV_FILE:-"${PROJECT_ROOT}/.env"}

if [[ ! -f "$ENV_FILE" ]]; then
  warn "Environment file '${ENV_FILE}' not found. The setup script will rely on existing environment variables."
fi

run_step() {
  local name="$1"; shift
  log "Starting ${name}"
  if "$@"; then
    ok "${name} completed"
  else
    local status=$?
    err "${name} failed"
    exit "$status"
  fi
}

log "Loading infrastructure environment from ${ENV_FILE}"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/setup_infrastructure_env.sh" "$ENV_FILE"
ok "Environment variables configured"

run_step "Cloud SQL / pgvector deployment" env SKIP_SECRET_STORAGE=true "${SCRIPT_DIR}/deploy_pgvector_infrastructure.sh"
run_step "ECO schema migration" \
  env \
  PROJECT_ID="${GOOGLE_CLOUD_PROJECT}" \
  REGION="${GOOGLE_CLOUD_REGION}" \
  SQL_INSTANCE="${PGVECTOR_INSTANCE_NAME}" \
  DB_NAME="${ECO_DATABASE_NAME}" \
  DB_USER="${ECO_APP_USER}" \
  DB_PASSWORD="${ECO_APP_PASSWORD}" \
  ADMIN_USER="${CLOUD_SQL_ADMIN_USER}" \
  ADMIN_PASSWORD="${CLOUD_SQL_ADMIN_PASSWORD}" \
  "${SCRIPT_DIR}/deploy_eco_schema.sh"
run_step "Redis deployment" env SKIP_SECRET_STORAGE=true "${SCRIPT_DIR}/deploy_redis_infrastructure.sh"

if [[ "${SKIP_SECRETS}" == "false" ]]; then
  run_step "Secret configuration" "${SCRIPT_DIR}/configure_secrets.sh"
else
  warn "Skipping secret configuration as requested"
fi

if [[ "${SKIP_VALIDATION}" == "false" ]]; then
  run_step "Infrastructure validation" "${SCRIPT_DIR}/validate_infrastructure_deployment.sh"
else
  warn "Skipping validation checks as requested"
fi

ok "Infrastructure phase 2 deployment complete"
