#!/usr/bin/env bash

SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Configure Secret Manager entries for Cloud SQL and Redis connection strings.

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BLUE="\033[0;34m"; GREEN="\033[0;32m"; YELLOW="\033[0;33m"; RED="\033[0;31m"; NC="\033[0m"
log()  { echo -e "${BLUE}[configure-secrets]${NC} $*"; }
ok()   { echo -e "${GREEN}[ok]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*" 1>&2; }

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--env-file path]

Options:
  --env-file PATH   Path to the environment file (defaults to <repo>/.env)
USAGE
}

ENV_FILE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      [[ $# -lt 2 ]] && { err "--env-file requires a path"; usage; exit 1; }
      ENV_FILE="$2"
      shift 2
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
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck source=/dev/null
  source "${SCRIPT_DIR}/setup_infrastructure_env.sh" "$ENV_FILE"
else
  warn "Environment file '${ENV_FILE}' not found. Continuing with existing environment variables."
fi

PROJECT_ID=${PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-}}
require_env() {
  local var="$1"; local description="$2"
  if [[ -z "${!var:-}" ]]; then
    err "Missing required env var: $var (${description})"
    exit 1
  fi
}

require_env PROJECT_ID "Target Google Cloud project"
require_env PGVECTOR_SECRET_NAME "Secret name for pgvector DSN"
require_env ECO_SECRET_NAME "Secret name for ECO DSN"
require_env ECO_REDIS_SECRET_NAME "Secret name for ECO Redis URL"

PGVECTOR_INSTANCE_NAME=${PGVECTOR_INSTANCE_NAME:-${SQL_INSTANCE:-}}
GOOGLE_CLOUD_REGION=${GOOGLE_CLOUD_REGION:-${REGION:-}}
PGVECTOR_DB_NAME=${PGVECTOR_DB_NAME:-${PGVECTOR_DATABASE_NAME:-pgvector}}
PGVECTOR_DB_USER=${PGVECTOR_DB_USER:-${PGVECTOR_APP_USER:-pgvector_app}}
PGVECTOR_DB_PASSWORD=${PGVECTOR_DB_PASSWORD:-${PGVECTOR_APP_PASSWORD:-}}
ECO_DB_NAME=${ECO_DB_NAME:-${ECO_DATABASE_NAME:-eco}}
ECO_DB_USER=${ECO_DB_USER:-${ECO_APP_USER:-eco_app}}
ECO_DB_PASSWORD=${ECO_DB_PASSWORD:-${ECO_APP_PASSWORD:-}}
ECO_REDIS_INSTANCE_NAME=${ECO_REDIS_INSTANCE_NAME:-${REDIS_INSTANCE:-}}
ECO_REDIS_REGION=${ECO_REDIS_REGION:-${REGION:-}}

require_env PGVECTOR_INSTANCE_NAME "Cloud SQL instance name"
require_env GOOGLE_CLOUD_REGION "Cloud SQL region"
require_env PGVECTOR_DB_USER "pgvector DB user"
require_env PGVECTOR_DB_PASSWORD "pgvector DB password"
require_env ECO_DB_USER "ECO DB user"
require_env ECO_DB_PASSWORD "ECO DB password"
require_env ECO_REDIS_INSTANCE_NAME "Redis instance name"
require_env ECO_REDIS_REGION "Redis region"

CONNECTION_NAME="${PROJECT_ID}:${GOOGLE_CLOUD_REGION}:${PGVECTOR_INSTANCE_NAME}"
PGVECTOR_DSN="postgresql://${PGVECTOR_DB_USER}:${PGVECTOR_DB_PASSWORD}@/${PGVECTOR_DB_NAME}?host=/cloudsql/${CONNECTION_NAME}"
ECO_DSN="postgresql://${ECO_DB_USER}:${ECO_DB_PASSWORD}@/${ECO_DB_NAME}?host=/cloudsql/${CONNECTION_NAME}"

ensure_tools() {
  command -v gcloud >/dev/null || { err "gcloud CLI not found"; exit 1; }
}

secret_upsert() {
  local secret_name="$1"; local value="$2"
  if gcloud secrets describe "$secret_name" --project="$PROJECT_ID" >/dev/null 2>&1; then
    printf "%s" "$value" | gcloud secrets versions add "$secret_name" --data-file=- --project="$PROJECT_ID" >/dev/null
  else
    printf "%s" "$value" | gcloud secrets create "$secret_name" --data-file=- --replication-policy=automatic --project="$PROJECT_ID" >/dev/null
  fi
}

redis_endpoint() {
  gcloud redis instances describe "$ECO_REDIS_INSTANCE_NAME" \
    --region="$ECO_REDIS_REGION" \
    --project="$PROJECT_ID" \
    --format='value(host,port)' | tr '\t' ':'
}

main() {
  ensure_tools

  log "Storing pgvector DSN in Secret Manager (${PGVECTOR_SECRET_NAME})"
  secret_upsert "$PGVECTOR_SECRET_NAME" "$PGVECTOR_DSN"

  log "Storing ECO DSN in Secret Manager (${ECO_SECRET_NAME})"
  secret_upsert "$ECO_SECRET_NAME" "$ECO_DSN"

  log "Retrieving Redis endpoint"
  local redis_host_port
  redis_host_port=$(redis_endpoint)
  if [[ -z "$redis_host_port" ]]; then
    err "Unable to determine Redis endpoint for ${ECO_REDIS_INSTANCE_NAME}"
    exit 1
  fi
  local redis_url="redis://${redis_host_port}"

  log "Storing Redis URL in Secret Manager (${ECO_REDIS_SECRET_NAME})"
  secret_upsert "$ECO_REDIS_SECRET_NAME" "$redis_url"

  ok "Secrets configured"
}

main "$@"
