#!/usr/bin/env bash

SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Deploy or update the shared Cloud SQL PostgreSQL instance with pgvector support.
# The script is idempotent and can be invoked directly or via the phase 2 orchestrator.

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BLUE="\033[0;34m"; GREEN="\033[0;32m"; YELLOW="\033[0;33m"; RED="\033[0;31m"; NC="\033[0m"
log()  { echo -e "${BLUE}[deploy-pgvector]${NC} $*"; }
ok()   { echo -e "${GREEN}[ok]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*" 1>&2; }

# Map legacy variable names to the new shared naming scheme.
PROJECT_ID=${PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-}}
REGION=${REGION:-${GOOGLE_CLOUD_REGION:-}}
SQL_INSTANCE=${SQL_INSTANCE:-${PGVECTOR_INSTANCE_NAME:-}}

ADMIN_USER=${ADMIN_USER:-${CLOUD_SQL_ADMIN_USER:-postgres}}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-${CLOUD_SQL_ADMIN_PASSWORD:-}}

PGVECTOR_DB_NAME=${PGVECTOR_DB_NAME:-${PGVECTOR_DATABASE_NAME:-pgvector}}
PGVECTOR_DB_USER=${PGVECTOR_DB_USER:-${PGVECTOR_APP_USER:-pgvector_app}}
PGVECTOR_DB_PASSWORD=${PGVECTOR_DB_PASSWORD:-${PGVECTOR_APP_PASSWORD:-}}

ECO_DB_NAME=${ECO_DB_NAME:-${ECO_DATABASE_NAME:-}}
ECO_DB_USER=${ECO_DB_USER:-${ECO_APP_USER:-}}
ECO_DB_PASSWORD=${ECO_DB_PASSWORD:-${ECO_APP_PASSWORD:-}}

# Accept override; set conservative default (~25% of 7.5GB)
SHARED_BUFFERS=${SHARED_BUFFERS:-"2GB"}
MAX_CONNECTIONS=${MAX_CONNECTIONS:-200}
DB_FLAGS="--database-flags=max_connections=${MAX_CONNECTIONS},shared_buffers=${SHARED_BUFFERS}"
BACKUP_START_TIME=${BACKUP_START_TIME:-"03:00"}  # UTC
RETAINED_BACKUPS_COUNT=${RETAINED_BACKUPS_COUNT:-15}
RETAINED_XLOG_DAYS=${RETAINED_XLOG_DAYS:-14}
CLOUD_SQL_TIER=${CLOUD_SQL_TIER:-db-custom-2-7680}
CLOUD_SQL_DISK_SIZE_GB=${CLOUD_SQL_DISK_SIZE_GB:-100}
CLOUD_SQL_DISK_TYPE=${CLOUD_SQL_DISK_TYPE:-PD_SSD}
CLOUD_SQL_BACKUP_ENABLED=$(tr '[:upper:]' '[:lower:]' <<<"${CLOUD_SQL_BACKUP_ENABLED:-true}")

CONNECTION_NAME=${CONNECTION_NAME:-"${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"}
PGVECTOR_SCHEMA_SQL=${PGVECTOR_SCHEMA_SQL:-"${PROJECT_ROOT}/scripts/pgvector_schema_init.sql"}
SKIP_SECRET_STORAGE=$(tr '[:upper:]' '[:lower:]' <<<"${SKIP_SECRET_STORAGE:-false}")
PGVECTOR_SECRETS_PREFIX=${PGVECTOR_SECRETS_PREFIX:-pgvector}

FUNCTIONS_SA=${FUNCTIONS_SA:-"${PROJECT_ID}@appspot.gserviceaccount.com"}
PROJECT_NUMBER=${PROJECT_NUMBER:-$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')}
CLOUD_RUN_SA=${CLOUD_RUN_SA:-"${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"}

PROXY_BIN=${PROXY_BIN:-cloud-sql-proxy}
PROXY_PORT=${PROXY_PORT:-6543}
PROXY_PID=""

require_env() {
  local var="$1"; local description="$2"
  if [[ -z "${!var:-}" ]]; then
    err "Missing required env var: $var (${description})"
    exit 1
  fi
}

require_env PROJECT_ID "Target Google Cloud project"
require_env REGION "Region for the Cloud SQL instance"
require_env SQL_INSTANCE "Cloud SQL instance identifier"
require_env ADMIN_USER "Bootstrap administrator user"
require_env ADMIN_PASSWORD "Bootstrap administrator password"
require_env PGVECTOR_DB_PASSWORD "Password for pgvector application role"

if [[ -n "$ECO_DB_NAME" || -n "$ECO_DB_USER" || -n "$ECO_DB_PASSWORD" ]]; then
  if [[ -z "$ECO_DB_NAME" || -z "$ECO_DB_USER" || -z "$ECO_DB_PASSWORD" ]]; then
    err "ECO database configuration is incomplete. Provide ECO_DB_NAME, ECO_DB_USER, and ECO_DB_PASSWORD or leave all unset."
    exit 1
  fi
fi

cleanup() {
  if [[ -n "$PROXY_PID" ]] && kill -0 "$PROXY_PID" 2>/dev/null; then
    warn "Stopping Cloud SQL Auth Proxy (pid=$PROXY_PID)"
    kill "$PROXY_PID" || true
    wait "$PROXY_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

ensure_tools() {
  command -v gcloud >/dev/null || { err "gcloud CLI not found"; exit 1; }
  command -v psql >/dev/null || { err "psql not found (install the PostgreSQL client)"; exit 1; }
  command -v "$PROXY_BIN" >/dev/null || { err "Cloud SQL Auth Proxy not found (set PROXY_BIN or install cloud-sql-proxy)"; exit 1; }
}

ensure_instance() {
  log "Ensuring Cloud SQL instance '${SQL_INSTANCE}' exists in '${REGION}'"
  if gcloud sql instances describe "$SQL_INSTANCE" --project="$PROJECT_ID" >/dev/null 2>&1; then
    ok "Instance exists"
  else
    log "Creating PostgreSQL instance with pgvector support"
    local create_args=(
      "$SQL_INSTANCE"
      --project="$PROJECT_ID"
      --database-version=POSTGRES_16
      --region="$REGION"
      --tier="$CLOUD_SQL_TIER"
      --storage-type="$CLOUD_SQL_DISK_TYPE"
      --storage-size="$CLOUD_SQL_DISK_SIZE_GB"
      --availability-type=REGIONAL
      --quiet
    )
    if [[ "$CLOUD_SQL_BACKUP_ENABLED" == "true" ]]; then
      create_args+=(
        --backup-start-time="$BACKUP_START_TIME"
        --retained-backups-count="$RETAINED_BACKUPS_COUNT"
        --enable-point-in-time-recovery
        --retained-transaction-log-days="$RETAINED_XLOG_DAYS"
      )
    else
      create_args+=(--no-backup)
    fi
    gcloud sql instances create "${create_args[@]}" >/dev/null
    ok "Instance created"
  fi

  log "Patching instance with flags ${DB_FLAGS}"
  # shellcheck disable=SC2086
  gcloud sql instances patch "$SQL_INSTANCE" --project="$PROJECT_ID" $DB_FLAGS --quiet >/dev/null || true
  ok "Instance flags ensured"
}

start_proxy() {
  log "Starting Cloud SQL Auth Proxy on port ${PROXY_PORT} for ${CONNECTION_NAME}"
  "$PROXY_BIN" --port="$PROXY_PORT" "$CONNECTION_NAME" &
  PROXY_PID=$!
  sleep 2
  ok "Proxy started (pid=$PROXY_PID)"
}

psql_admin() {
  PGPASSWORD="$ADMIN_PASSWORD" psql "host=127.0.0.1 port=$PROXY_PORT user=$ADMIN_USER dbname=postgres" "$@"
}

psql_app() {
  local db="$1"; shift
  local user="$2"; shift
  local password="$3"; shift
  PGPASSWORD="$password" psql "host=127.0.0.1 port=$PROXY_PORT user=$user dbname=$db" "$@"
}

escape_sql() { printf %s "$1" | sed "s/'/''/g"; }

ensure_database_and_role() {
  local db_name="$1"; local db_user="$2"; local db_password="$3"
  log "Ensuring database '${db_name}' and role '${db_user}'"
  local pw_esc
  pw_esc=$(escape_sql "$db_password")

  if ! psql_admin -tAc "SELECT 1 FROM pg_database WHERE datname='${db_name}'" | grep -q 1; then
    psql_admin -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"${db_name}\";"
    ok "Created database ${db_name}"
  else
    ok "Database ${db_name} exists"
  fi

  if ! psql_admin -tAc "SELECT 1 FROM pg_roles WHERE rolname='${db_user}'" | grep -q 1; then
    psql_admin -v ON_ERROR_STOP=1 -c "CREATE USER \"${db_user}\" WITH PASSWORD '${pw_esc}';"
    ok "Created role ${db_user}"
  else
    psql_admin -v ON_ERROR_STOP=1 -c "ALTER USER \"${db_user}\" WITH PASSWORD '${pw_esc}';"
    ok "Updated role password for ${db_user}"
  fi

  psql_admin -v ON_ERROR_STOP=1 -d "${db_name}" -c "GRANT CONNECT ON DATABASE \"${db_name}\" TO \"${db_user}\";"
  psql_admin -v ON_ERROR_STOP=1 -d "${db_name}" -c "GRANT USAGE ON SCHEMA public TO \"${db_user}\";"
  psql_admin -v ON_ERROR_STOP=1 -d "${db_name}" -c "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"${db_user}\";"
  psql_admin -v ON_ERROR_STOP=1 -d "${db_name}" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO \"${db_user}\";"
  ok "Grants ensured for ${db_user}"
}

enable_pgvector_extension() {
  log "Ensuring pgvector extension is enabled in ${PGVECTOR_DB_NAME}"
  psql_admin -v ON_ERROR_STOP=1 -d "${PGVECTOR_DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS vector;"
  ok "pgvector extension ready"
}

apply_pgvector_schema() {
  log "Applying pgvector schema from ${PGVECTOR_SCHEMA_SQL}"
  if [[ ! -f "${PGVECTOR_SCHEMA_SQL}" ]]; then
    err "Schema file not found: ${PGVECTOR_SCHEMA_SQL}"
    exit 1
  fi
  psql_app "${PGVECTOR_DB_NAME}" "${PGVECTOR_DB_USER}" "${PGVECTOR_DB_PASSWORD}" -v ON_ERROR_STOP=1 -f "${PGVECTOR_SCHEMA_SQL}"
  ok "pgvector schema applied"
}

grant_iam_access() {
  log "Granting Cloud SQL Client role to service accounts"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${FUNCTIONS_SA}" \
    --role="roles/cloudsql.client" --quiet >/dev/null || true
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${CLOUD_RUN_SA}" \
    --role="roles/cloudsql.client" --quiet >/dev/null || true
  ok "IAM access ensured"
}

store_pgvector_secrets() {
  if [[ "$SKIP_SECRET_STORAGE" == "true" ]]; then
    warn "Skipping secret storage as requested"
    return
  fi

  log "Storing pgvector connection details in Secret Manager (prefix: ${PGVECTOR_SECRETS_PREFIX})"
  create_or_update_secret() {
    local name="$1"; local value="$2"
    if gcloud secrets describe "$name" --project="$PROJECT_ID" >/dev/null 2>&1; then
      printf "%s" "$value" | gcloud secrets versions add "$name" --data-file=- --project="$PROJECT_ID" >/dev/null
    else
      printf "%s" "$value" | gcloud secrets create "$name" --data-file=- --replication-policy=automatic --project="$PROJECT_ID" >/dev/null
    fi
  }

  local dsn="postgresql://${PGVECTOR_DB_USER}:${PGVECTOR_DB_PASSWORD}@/${PGVECTOR_DB_NAME}?host=/cloudsql/${CONNECTION_NAME}"
  create_or_update_secret "${PGVECTOR_SECRETS_PREFIX}_connection_name" "$CONNECTION_NAME"
  create_or_update_secret "${PGVECTOR_SECRETS_PREFIX}_database" "$PGVECTOR_DB_NAME"
  create_or_update_secret "${PGVECTOR_SECRETS_PREFIX}_user" "$PGVECTOR_DB_USER"
  create_or_update_secret "${PGVECTOR_SECRETS_PREFIX}_password" "$PGVECTOR_DB_PASSWORD"
  create_or_update_secret "${PGVECTOR_SECRETS_PREFIX}_dsn" "$dsn"
  ok "pgvector secrets stored"
}

health_checks() {
  log "Running health checks"
  psql_app "${PGVECTOR_DB_NAME}" "${PGVECTOR_DB_USER}" "${PGVECTOR_DB_PASSWORD}" -tAc "SELECT 1" | grep -q 1 && ok "pgvector connectivity ok"
  psql_app "${PGVECTOR_DB_NAME}" "${PGVECTOR_DB_USER}" "${PGVECTOR_DB_PASSWORD}" -tAc "SELECT extname FROM pg_extension WHERE extname='vector'" | grep -q vector && ok "pgvector extension present"

  if [[ -n "${ECO_DB_NAME}" ]]; then
    psql_app "${ECO_DB_NAME}" "${ECO_DB_USER}" "${ECO_DB_PASSWORD}" -tAc "SELECT 1" | grep -q 1 && ok "ECO connectivity ok"
  fi
}

main() {
  ensure_tools
  ensure_instance
  start_proxy
  ensure_database_and_role "$PGVECTOR_DB_NAME" "$PGVECTOR_DB_USER" "$PGVECTOR_DB_PASSWORD"
  if [[ -n "${ECO_DB_NAME}" ]]; then
    ensure_database_and_role "$ECO_DB_NAME" "$ECO_DB_USER" "$ECO_DB_PASSWORD"
  fi
  enable_pgvector_extension
  apply_pgvector_schema
  grant_iam_access
  store_pgvector_secrets
  health_checks
  ok "pgvector infrastructure deployment complete"
}

main "$@"
