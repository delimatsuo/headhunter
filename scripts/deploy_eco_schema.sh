#!/usr/bin/env bash


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# ECO schema deployment script
# Reuses the same Cloud SQL connectivity patterns as deploy_pgvector_infrastructure.sh

set -euo pipefail
IFS=$'\n\t'

BLUE="\033[0;34m"; GREEN="\033[0;32m"; YELLOW="\033[0;33m"; RED="\033[0;31m"; NC="\033[0m"
log() { echo -e "${BLUE}[eco]${NC} $*"; }
ok()  { echo -e "${GREEN}[ok]${NC} $*"; }
warn(){ echo -e "${YELLOW}[warn]${NC} $*"; }
err() { echo -e "${RED}[error]${NC} $*" 1>&2; }

ECO_SCHEMA_SQL=${ECO_SCHEMA_SQL:-"scripts/eco_schema.sql"}
PROXY_PORT=${PROXY_PORT:-"6543"}

DRY_RUN=false
FORCE=false

usage() {
  cat <<EOF
Usage: $0 [--dry-run] [--force]

Environment variables (same as pgvector deploy):
  PROJECT_ID, REGION, SQL_INSTANCE, DB_NAME, DB_USER, DB_PASSWORD,
  ADMIN_USER, ADMIN_PASSWORD, PROXY_BIN (cloud-sql-proxy)

Optional:
  ECO_SCHEMA_SQL (default: scripts/eco_schema.sql)
  PROXY_PORT (default: 6543)
EOF
}

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --force)   FORCE=true ;;
    -h|--help) usage; exit 0 ;;
    *) err "Unknown arg: $arg"; usage; exit 1 ;;
  esac
done

PROJECT_ID=${PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-}}
REGION=${REGION:-${GOOGLE_CLOUD_REGION:-}}
SQL_INSTANCE=${SQL_INSTANCE:-${PGVECTOR_INSTANCE_NAME:-}}
DB_NAME=${DB_NAME:-${ECO_DATABASE_NAME:-}}
DB_USER=${DB_USER:-${ECO_APP_USER:-}}
DB_PASSWORD=${DB_PASSWORD:-${ECO_APP_PASSWORD:-}}
ADMIN_USER=${ADMIN_USER:-${CLOUD_SQL_ADMIN_USER:-postgres}}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-${CLOUD_SQL_ADMIN_PASSWORD:-}}

req() { local n="$1"; if [[ -z "${!n:-}" ]]; then err "Missing env var: $n"; exit 1; fi }

req PROJECT_ID; req REGION; req SQL_INSTANCE; req DB_NAME; req DB_USER; req DB_PASSWORD; req ADMIN_USER; req ADMIN_PASSWORD;

if [[ ! -f "$ECO_SCHEMA_SQL" ]]; then
  err "Schema not found: $ECO_SCHEMA_SQL"; exit 1
fi

ensure_tools() {
  command -v gcloud >/dev/null || { err "gcloud not found"; exit 1; }
  command -v psql >/dev/null || { err "psql not found"; exit 1; }
  command -v "${PROXY_BIN:-cloud-sql-proxy}" >/dev/null || { err "cloud-sql-proxy not found"; exit 1; }
}

start_proxy() {
  local conn_name="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"
  log "Starting Cloud SQL Proxy for ${conn_name} on :${PROXY_PORT}"
  "${PROXY_BIN:-cloud-sql-proxy}" --port="${PROXY_PORT}" "${conn_name}" &
  PROXY_PID=$!
  sleep 2
}

stop_proxy() {
  if [[ -n "${PROXY_PID:-}" ]] && kill -0 "$PROXY_PID" 2>/dev/null; then
    warn "Stopping proxy (pid=$PROXY_PID)"
    kill "$PROXY_PID" || true
    wait "$PROXY_PID" 2>/dev/null || true
  fi
}
trap stop_proxy EXIT

tables_exist() {
  PGPASSWORD="$DB_PASSWORD" psql "host=127.0.0.1 port=$PROXY_PORT user=$DB_USER dbname=$DB_NAME" -tAc \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('eco_occupation','eco_alias','occupation_crosswalk','eco_template');" | tr -d ' ' 
}

main() {
  ensure_tools
  start_proxy

  local count
  count=$(tables_exist || echo 0)
  if [[ "$count" == "4" && "$FORCE" == "false" ]]; then
    ok "ECO tables already exist; use --force to re-apply"
    return 0
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    log "DRY RUN: would apply $ECO_SCHEMA_SQL to $DB_NAME as $DB_USER"
    return 0
  fi

  log "Applying ECO schema from $ECO_SCHEMA_SQL"
  PGPASSWORD="$DB_PASSWORD" psql "host=127.0.0.1 port=$PROXY_PORT user=$DB_USER dbname=$DB_NAME" -v ON_ERROR_STOP=1 -f "$ECO_SCHEMA_SQL"
  ok "ECO schema applied"
}

main "$@"
