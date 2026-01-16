#!/usr/bin/env bash

SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Deploy the sourcing schema for Ella Sourcing SaaS
# Creates sourcing.* tables in Cloud SQL for LinkedIn candidate database
# Based on deploy_eco_schema.sh pattern

set -euo pipefail
IFS=$'\n\t'

BLUE="\033[0;34m"; GREEN="\033[0;32m"; YELLOW="\033[0;33m"; RED="\033[0;31m"; NC="\033[0m"
log() { echo -e "${BLUE}[sourcing]${NC} $*"; }
ok()  { echo -e "${GREEN}[ok]${NC} $*"; }
warn(){ echo -e "${YELLOW}[warn]${NC} $*"; }
err() { echo -e "${RED}[error]${NC} $*" 1>&2; }

SOURCING_SCHEMA_SQL=${SOURCING_SCHEMA_SQL:-"${SCRIPT_DIR}/migrations/002_sourcing_schema.sql"}
PROXY_PORT=${PROXY_PORT:-"6544"}  # Use different port to avoid conflicts

DRY_RUN=false
FORCE=false

usage() {
  cat <<EOF
Usage: $0 [--dry-run] [--force]

Deploy the sourcing schema to Cloud SQL for Ella Sourcing SaaS.

Environment variables:
  PROJECT_ID        - GCP project ID
  REGION            - GCP region
  SQL_INSTANCE      - Cloud SQL instance name
  DB_NAME           - Database name (default: pgvector)
  DB_USER           - Database user with CREATE SCHEMA privileges
  DB_PASSWORD       - Database password
  ADMIN_USER        - PostgreSQL admin user (default: postgres)
  ADMIN_PASSWORD    - PostgreSQL admin password

Optional:
  SOURCING_SCHEMA_SQL - Path to schema file (default: scripts/migrations/002_sourcing_schema.sql)
  PROXY_PORT          - Cloud SQL Proxy port (default: 6544)

Options:
  --dry-run    Show SQL commands without executing
  --force      Re-create schema even if tables exist
  -h, --help   Show this help
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

# Load environment from project config
PROJECT_ID=${PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-}}
REGION=${REGION:-${GOOGLE_CLOUD_REGION:-us-east1}}
SQL_INSTANCE=${SQL_INSTANCE:-${PGVECTOR_INSTANCE_NAME:-}}
DB_NAME=${DB_NAME:-${PGVECTOR_DATABASE_NAME:-pgvector}}
DB_USER=${DB_USER:-${PGVECTOR_APP_USER:-}}
DB_PASSWORD=${DB_PASSWORD:-${PGVECTOR_APP_PASSWORD:-}}
ADMIN_USER=${ADMIN_USER:-${CLOUD_SQL_ADMIN_USER:-postgres}}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-${CLOUD_SQL_ADMIN_PASSWORD:-}}

req() { local n="$1"; if [[ -z "${!n:-}" ]]; then err "Missing env var: $n"; exit 1; fi }

req PROJECT_ID; req REGION; req SQL_INSTANCE; req DB_NAME; req DB_USER; req DB_PASSWORD; req ADMIN_PASSWORD;

if [[ ! -f "$SOURCING_SCHEMA_SQL" ]]; then
  err "Schema not found: $SOURCING_SCHEMA_SQL"; exit 1
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
  sleep 3  # Give proxy time to connect

  # Verify proxy is running
  if ! kill -0 "$PROXY_PID" 2>/dev/null; then
    err "Cloud SQL Proxy failed to start"
    exit 1
  fi
  ok "Proxy started (pid=$PROXY_PID)"
}

stop_proxy() {
  if [[ -n "${PROXY_PID:-}" ]] && kill -0 "$PROXY_PID" 2>/dev/null; then
    warn "Stopping proxy (pid=$PROXY_PID)"
    kill "$PROXY_PID" || true
    wait "$PROXY_PID" 2>/dev/null || true
  fi
}
trap stop_proxy EXIT

schema_exists() {
  PGPASSWORD="$DB_PASSWORD" psql "host=127.0.0.1 port=$PROXY_PORT user=$DB_USER dbname=$DB_NAME" -tAc \
    "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='sourcing';" | tr -d ' '
}

tables_exist() {
  PGPASSWORD="$DB_PASSWORD" psql "host=127.0.0.1 port=$PROXY_PORT user=$DB_USER dbname=$DB_NAME" -tAc \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='sourcing' AND table_name IN ('candidates','experience','skills','candidate_skills','embeddings');" | tr -d ' '
}

main() {
  log "=== Ella Sourcing Schema Deployment ==="
  log "Project: $PROJECT_ID"
  log "Instance: $SQL_INSTANCE"
  log "Database: $DB_NAME"
  log "Schema file: $SOURCING_SCHEMA_SQL"

  ensure_tools

  if [[ "$DRY_RUN" == "true" ]]; then
    log "[DRY RUN] Would execute:"
    cat "$SOURCING_SCHEMA_SQL"
    exit 0
  fi

  start_proxy

  # Check if schema already exists
  local schema_count=$(schema_exists)
  local table_count=$(tables_exist)

  log "Schema exists: $([[ $schema_count -gt 0 ]] && echo 'yes' || echo 'no')"
  log "Tables exist: $table_count/5"

  if [[ $table_count -ge 5 && "$FORCE" != "true" ]]; then
    warn "Sourcing schema already deployed (use --force to re-deploy)"
    ok "Skipping deployment"
    exit 0
  fi

  if [[ "$FORCE" == "true" && $table_count -gt 0 ]]; then
    warn "Force mode: Dropping existing tables..."
    PGPASSWORD="$ADMIN_PASSWORD" psql "host=127.0.0.1 port=$PROXY_PORT user=$ADMIN_USER dbname=$DB_NAME" <<EOF
DROP SCHEMA IF EXISTS sourcing CASCADE;
EOF
    ok "Existing schema dropped"
  fi

  log "Deploying sourcing schema..."

  # Execute schema as admin to ensure CREATE SCHEMA privileges
  PGPASSWORD="$ADMIN_PASSWORD" psql "host=127.0.0.1 port=$PROXY_PORT user=$ADMIN_USER dbname=$DB_NAME" < "$SOURCING_SCHEMA_SQL"

  # Grant permissions to app user
  log "Granting permissions to $DB_USER..."
  PGPASSWORD="$ADMIN_PASSWORD" psql "host=127.0.0.1 port=$PROXY_PORT user=$ADMIN_USER dbname=$DB_NAME" <<EOF
-- Grant usage on schema
GRANT USAGE ON SCHEMA sourcing TO $DB_USER;

-- Grant all on tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA sourcing TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA sourcing TO $DB_USER;

-- Grant for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA sourcing GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA sourcing GRANT ALL ON SEQUENCES TO $DB_USER;
EOF

  # Verify deployment
  local final_count=$(tables_exist)

  if [[ $final_count -eq 5 ]]; then
    ok "Sourcing schema deployed successfully!"
    log "Tables created:"
    PGPASSWORD="$DB_PASSWORD" psql "host=127.0.0.1 port=$PROXY_PORT user=$DB_USER dbname=$DB_NAME" -tAc \
      "SELECT table_name FROM information_schema.tables WHERE table_schema='sourcing' ORDER BY table_name;"
  else
    err "Schema deployment incomplete. Expected 5 tables, found $final_count"
    exit 1
  fi
}

main
