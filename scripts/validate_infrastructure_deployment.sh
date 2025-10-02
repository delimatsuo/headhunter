#!/usr/bin/env bash

SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Validate the deployed infrastructure: Cloud SQL (pgvector + ECO), Redis, and secrets.

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BLUE="\033[0;34m"; GREEN="\033[0;32m"; YELLOW="\033[0;33m"; RED="\033[0;31m"; NC="\033[0m"
log()  { echo -e "${BLUE}[validate-infra]${NC} $*"; }
ok()   { echo -e "${GREEN}[ok]${NC} $*"; }
wfail(){ echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*" 1>&2; }

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--env-file path]

Options:
  --env-file PATH   Path to environment file (defaults to <repo>/.env)
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
  wfail "Environment file '${ENV_FILE}' not found. Continuing with existing environment variables."
fi

PROJECT_ID=${PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-}}
GOOGLE_CLOUD_REGION=${GOOGLE_CLOUD_REGION:-${REGION:-}}
PGVECTOR_INSTANCE_NAME=${PGVECTOR_INSTANCE_NAME:-${SQL_INSTANCE:-}}
PGVECTOR_DB_NAME=${PGVECTOR_DB_NAME:-${PGVECTOR_DATABASE_NAME:-pgvector}}
PGVECTOR_DB_USER=${PGVECTOR_DB_USER:-${PGVECTOR_APP_USER:-pgvector_app}}
PGVECTOR_DB_PASSWORD=${PGVECTOR_DB_PASSWORD:-${PGVECTOR_APP_PASSWORD:-}}
ECO_DB_NAME=${ECO_DB_NAME:-${ECO_DATABASE_NAME:-eco}}
ECO_DB_USER=${ECO_DB_USER:-${ECO_APP_USER:-eco_app}}
ECO_DB_PASSWORD=${ECO_DB_PASSWORD:-${ECO_APP_PASSWORD:-}}
CLOUD_SQL_ADMIN_USER=${CLOUD_SQL_ADMIN_USER:-${ADMIN_USER:-postgres}}
CLOUD_SQL_ADMIN_PASSWORD=${CLOUD_SQL_ADMIN_PASSWORD:-${ADMIN_PASSWORD:-}}
ECO_REDIS_INSTANCE_NAME=${ECO_REDIS_INSTANCE_NAME:-${REDIS_INSTANCE:-}}
ECO_REDIS_REGION=${ECO_REDIS_REGION:-${REGION:-}}
PGVECTOR_SECRET_NAME=${PGVECTOR_SECRET_NAME:-}
ECO_SECRET_NAME=${ECO_SECRET_NAME:-}
ECO_REDIS_SECRET_NAME=${ECO_REDIS_SECRET_NAME:-}

require_env() {
  local var="$1"; local description="$2"
  if [[ -z "${!var:-}" ]]; then
    err "Missing required env var: $var (${description})"
    exit 1
  fi
}

require_env PROJECT_ID "Target Google Cloud project"
require_env PGVECTOR_INSTANCE_NAME "Cloud SQL instance name"
require_env GOOGLE_CLOUD_REGION "Cloud SQL region"
require_env PGVECTOR_DB_PASSWORD "pgvector DB password"
require_env ECO_DB_PASSWORD "ECO DB password"
require_env CLOUD_SQL_ADMIN_PASSWORD "Cloud SQL admin password"
require_env ECO_REDIS_INSTANCE_NAME "Redis instance name"
require_env ECO_REDIS_REGION "Redis region"
require_env PGVECTOR_SECRET_NAME "pgvector secret name"
require_env ECO_SECRET_NAME "ECO secret name"
require_env ECO_REDIS_SECRET_NAME "Redis secret name"

CONNECTION_NAME="${PROJECT_ID}:${GOOGLE_CLOUD_REGION}:${PGVECTOR_INSTANCE_NAME}"
PROXY_BIN=${PROXY_BIN:-cloud-sql-proxy}
PROXY_PORT=${PROXY_PORT:-6544}
PROXY_PID=""

ensure_tools() {
  command -v gcloud >/dev/null || { err "gcloud CLI not found"; exit 1; }
  command -v psql >/dev/null || { err "psql not found"; exit 1; }
  command -v "$PROXY_BIN" >/dev/null || { err "Cloud SQL Auth Proxy not found"; exit 1; }
}

start_proxy() {
  log "Starting Cloud SQL Auth Proxy (port ${PROXY_PORT})"
  "$PROXY_BIN" --port="$PROXY_PORT" "$CONNECTION_NAME" &
  PROXY_PID=$!
  sleep 2
  ok "Cloud SQL proxy running (pid=$PROXY_PID)"
}

stop_proxy() {
  if [[ -n "$PROXY_PID" ]] && kill -0 "$PROXY_PID" 2>/dev/null; then
    wfail "Stopping Cloud SQL proxy"
    kill "$PROXY_PID" || true
    wait "$PROXY_PID" 2>/dev/null || true
  fi
}
trap stop_proxy EXIT

psql_check() {
  local db="$1"; local user="$2"; local password="$3"; shift 3
  PGPASSWORD="$password" psql "host=127.0.0.1 port=$PROXY_PORT user=$user dbname=$db" "$@"
}

check_pgvector() {
  log "Validating pgvector database"
  psql_check "$PGVECTOR_DB_NAME" "$PGVECTOR_DB_USER" "$PGVECTOR_DB_PASSWORD" -tAc "SELECT extname FROM pg_extension WHERE extname='vector'" | grep -q vector && ok "pgvector extension present" || { err "pgvector extension missing"; exit 1; }
  psql_check "$PGVECTOR_DB_NAME" "$PGVECTOR_DB_USER" "$PGVECTOR_DB_PASSWORD" -tAc "SELECT to_regclass('public.candidate_embeddings')" | grep -q candidate_embeddings && ok "candidate_embeddings table present" || { err "candidate_embeddings table missing"; exit 1; }
  psql_check "$PGVECTOR_DB_NAME" "$PGVECTOR_DB_USER" "$PGVECTOR_DB_PASSWORD" -tAc "SELECT to_regclass('public.embedding_metadata')" | grep -q embedding_metadata && ok "embedding_metadata table present" || { err "embedding_metadata table missing"; exit 1; }
}

check_eco_schema() {
  log "Validating ECO schema"
  psql_check "$ECO_DB_NAME" "$ECO_DB_USER" "$ECO_DB_PASSWORD" -tAc "SELECT to_regclass('public.eco_occupation')" | grep -q eco_occupation && ok "eco_occupation table present" || { err "eco_occupation table missing"; exit 1; }
  psql_check "$ECO_DB_NAME" "$ECO_DB_USER" "$ECO_DB_PASSWORD" -tAc "SELECT to_regclass('public.eco_alias')" | grep -q eco_alias && ok "eco_alias table present" || { err "eco_alias table missing"; exit 1; }
  psql_check "$ECO_DB_NAME" "$ECO_DB_USER" "$ECO_DB_PASSWORD" -tAc "SELECT COUNT(*) FROM eco_occupation" | awk '{print $1}' | grep -q "^[0-9]\+" && ok "eco_occupation row count query succeeded"
}

check_redis() {
  log "Validating Redis connectivity"
  local host
  local port
  host=$(gcloud redis instances describe "$ECO_REDIS_INSTANCE_NAME" --region="$ECO_REDIS_REGION" --project="$PROJECT_ID" --format='value(host)')
  port=$(gcloud redis instances describe "$ECO_REDIS_INSTANCE_NAME" --region="$ECO_REDIS_REGION" --project="$PROJECT_ID" --format='value(port)')
  if [[ -z "$host" || -z "$port" ]]; then
    err "Unable to fetch Redis endpoint"
    exit 1
  fi
  ok "Redis endpoint resolved to ${host}:${port}"

  if command -v redis-cli >/dev/null; then
    if redis-cli -h "$host" -p "$port" PING >/dev/null 2>&1; then
      ok "Redis PING succeeded"
    else
      err "Redis PING failed"
      exit 1
    fi
  else
    wfail "redis-cli not installed; skipping active connectivity test"
  fi
}

check_secrets() {
  log "Validating Secret Manager entries"
  gcloud secrets versions access latest --secret="$PGVECTOR_SECRET_NAME" --project="$PROJECT_ID" >/dev/null && ok "pgvector secret accessible"
  gcloud secrets versions access latest --secret="$ECO_SECRET_NAME" --project="$PROJECT_ID" >/dev/null && ok "ECO secret accessible"
  gcloud secrets versions access latest --secret="$ECO_REDIS_SECRET_NAME" --project="$PROJECT_ID" >/dev/null && ok "Redis secret accessible"
}

main() {
  ensure_tools
  start_proxy
  check_pgvector
  check_eco_schema
  check_redis
  check_secrets
  ok "Infrastructure validation complete"
}

main "$@"
