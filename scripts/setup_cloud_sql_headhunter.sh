#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

CONFIG_FILE="config/infrastructure/headhunter-production.env"
CLI_PROJECT_ID=""
REGION="us-central1"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--project-id PROJECT_ID] [--config PATH]

Creates the Cloud SQL instance sql-hh-core with pgvector and initializes schemas.
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

if [[ -z "${SQL_INSTANCE:-}" ]]; then
  echo "SQL_INSTANCE must be set in the config" >&2
  exit 1
fi

SQL_TIER=${SQL_TIER:-db-custom-2-7680}
SQL_STORAGE_SIZE_GB=${SQL_STORAGE_SIZE_GB:-200}
SQL_DATABASE=${SQL_DATABASE:-headhunter}
SQL_FLAGS=${SQL_FLAGS:-shared_buffers=4096,max_connections=800,track_io_timing=on}
SQL_USER_ADMIN=${SQL_USER_ADMIN:-hh_admin}
SQL_USER_APP=${SQL_USER_APP:-hh_app}
SQL_USER_ANALYTICS=${SQL_USER_ANALYTICS:-hh_analytics}
VPC_NAME=${VPC_NAME:-vpc-hh}
PRIVATE_RANGE_NAME=${PRIVATE_RANGE_NAME:-hh-cloudsql-range}
SERVICE_NETWORK=${SERVICE_NETWORK:-servicenetworking.googleapis.com}
SQL_BACKUP_RETENTION_DAYS=${SQL_BACKUP_RETENTION_DAYS:-}
SQL_TRANSACTION_LOG_RETENTION_DAYS=${SQL_TRANSACTION_LOG_RETENTION_DAYS:-}
PROJECT_NUMBER=${PROJECT_NUMBER:-$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')}
NETWORK_URI_SQL="projects/${PROJECT_ID}/global/networks/${VPC_NAME}"

normalize_maintenance_day() {
  local value=${1:-SUN}
  case "${value^^}" in
    1|MONDAY|MON) echo MON ;;
    2|TUESDAY|TUE) echo TUE ;;
    3|WEDNESDAY|WED) echo WED ;;
    4|THURSDAY|THU) echo THU ;;
    5|FRIDAY|FRI) echo FRI ;;
    6|SATURDAY|SAT) echo SAT ;;
    0|7|SUNDAY|SUN) echo SUN ;;
    *) echo "$value" ;;
  esac
}

log() {
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >&2
}

warn() {
  log "WARN: $*"
}

log "Setting project ${PROJECT_ID}"
gcloud config set project "$PROJECT_ID" >/dev/null

if gcloud sql instances describe "$SQL_INSTANCE" --project="$PROJECT_ID" >/dev/null 2>&1; then
  log "Instance ${SQL_INSTANCE} already exists"
else
  log "Allocating private IP range ${PRIVATE_RANGE_NAME}"
  if ! gcloud compute addresses describe "$PRIVATE_RANGE_NAME" \
      --global --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud compute addresses create "$PRIVATE_RANGE_NAME" \
      --project="$PROJECT_ID" \
      --global \
      --purpose=VPC_PEERING \
      --prefix-length=16 \
      --network="$VPC_NAME"
  fi

  log "Ensuring private service connection"
  if ! gcloud services vpc-peerings list --project="$PROJECT_ID" \
      --network="$VPC_NAME" \
      --service="$SERVICE_NETWORK" \
      --format="value(name)" | grep -q "$PRIVATE_RANGE_NAME"; then
    gcloud services vpc-peerings connect \
      --project="$PROJECT_ID" \
      --service="$SERVICE_NETWORK" \
      --network="$VPC_NAME" \
      --ranges="$PRIVATE_RANGE_NAME"
  fi

  log "Creating Cloud SQL instance ${SQL_INSTANCE}"
  maintenance_day=$(normalize_maintenance_day "${SQL_MAINTENANCE_WINDOW_DAY:-SUN}")
  gcloud sql instances create "$SQL_INSTANCE" \
    --project="$PROJECT_ID" \
    --database-version=POSTGRES_15 \
    --tier="$SQL_TIER" \
    --region="$REGION" \
    --storage-size="$SQL_STORAGE_SIZE_GB" \
    --storage-auto-increase \
    --availability-type=REGIONAL \
    --backup-start-time=03:00 \
    --maintenance-window-day="$maintenance_day" \
    --maintenance-window-hour="${SQL_MAINTENANCE_WINDOW_HOUR:-5}" \
    --enable-point-in-time-recovery \
    --network="$NETWORK_URI_SQL" \
    --no-assign-ip

fi

log "Ensuring database flags include pgvector"
PGVECTOR_SUPPORTED=false
if gcloud sql flags list --database-version=POSTGRES_15 --format="value(name)" \
  | grep -qx "cloudsql.enable_pgvector"; then
  PGVECTOR_SUPPORTED=true
else
  warn "cloudsql.enable_pgvector flag unavailable for this environment; skipping automatic enablement"
fi

FLAGS_APPLY=()
if [[ "$PGVECTOR_SUPPORTED" == true ]]; then
  FLAGS_APPLY+=("cloudsql.enable_pgvector=true")
fi

if [[ -n "$SQL_FLAGS" ]]; then
  IFS=',' read -ra CONFIGURED_FLAGS <<< "$SQL_FLAGS"
  for entry in "${CONFIGURED_FLAGS[@]}"; do
    flag=$(echo "$entry" | tr -d '[:space:]')
    [[ -z "$flag" ]] && continue
    if [[ "$flag" == cloudsql.enable_pgvector=* ]]; then
      if [[ "$PGVECTOR_SUPPORTED" == true ]]; then
        FLAGS_APPLY[0]="$flag"
      else
        warn "Ignoring configured ${flag}; flag unsupported"
      fi
      continue
    fi
    FLAGS_APPLY+=("$flag")
  done
fi

if (( ${#FLAGS_APPLY[@]} > 0 )); then
  FLAGS_STRING=$(IFS=','; echo "${FLAGS_APPLY[*]}")
  if ! gcloud sql instances patch "$SQL_INSTANCE" \
      --project="$PROJECT_ID" \
      --quiet \
      --database-flags="$FLAGS_STRING"; then
    warn "Failed to apply database flags (${FLAGS_STRING}); continuing"
  elif [[ "$PGVECTOR_SUPPORTED" == true ]]; then
    FLAG_CHECK=$(gcloud sql instances describe "$SQL_INSTANCE" --project="$PROJECT_ID" --format='value(settings.databaseFlags)' 2>/dev/null || true)
    if [[ "$FLAG_CHECK" != *"cloudsql.enable_pgvector=true"* ]]; then
      warn "cloudsql.enable_pgvector flag not set after patch"
    fi
  fi
fi

RETENTION_ARGS=()
if [[ -n "$SQL_BACKUP_RETENTION_DAYS" ]]; then
  RETENTION_ARGS+=("--retained-backups-count=${SQL_BACKUP_RETENTION_DAYS}")
fi
if [[ -n "$SQL_TRANSACTION_LOG_RETENTION_DAYS" ]]; then
  RETENTION_ARGS+=("--retained-transaction-log-days=${SQL_TRANSACTION_LOG_RETENTION_DAYS}")
fi
if [[ ${#RETENTION_ARGS[@]} -gt 0 ]]; then
  log "Applying backup and transaction log retention policies"
  if ! gcloud sql instances patch "$SQL_INSTANCE" \
      --project="$PROJECT_ID" \
      --quiet \
      "${RETENTION_ARGS[@]}"; then
    warn "Failed to update retention policies"
  fi
fi

if ! gcloud sql databases list --instance="$SQL_INSTANCE" \
  --project="$PROJECT_ID" --format="value(name)" | grep -qx "$SQL_DATABASE"; then
  log "Creating database ${SQL_DATABASE}"
  gcloud sql databases create "$SQL_DATABASE" \
    --instance="$SQL_INSTANCE" \
    --project="$PROJECT_ID"
fi

ensure_secret() {
  local secret=$1
  if [[ -z "$secret" ]]; then
    echo "Secret name missing" >&2
    exit 1
  fi
  if ! gcloud secrets describe "$secret" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "Required secret ${secret} not found" >&2
    exit 1
  fi
}

ensure_secret "${SECRET_DB_PRIMARY:-db-primary-password}"
ensure_secret "${SECRET_DB_REPLICA:-db-replica-password}"
ensure_secret "${SECRET_DB_ANALYTICS:-db-analytics-password}"

create_user() {
  local user=$1
  local secret=$2
  if ! gcloud sql users list --instance="$SQL_INSTANCE" --project="$PROJECT_ID" \
    --format="value(name)" | grep -qx "$user"; then
    PASSWORD=$(gcloud secrets versions access latest --secret="$secret" --project="$PROJECT_ID")
    gcloud sql users create "$user" --instance="$SQL_INSTANCE" \
      --project="$PROJECT_ID" --password="$PASSWORD"
  fi
}

log "Ensuring SQL users exist"
create_user "$SQL_USER_ADMIN" "${SECRET_DB_PRIMARY:-db-primary-password}"
create_user "$SQL_USER_APP" "${SECRET_DB_REPLICA:-db-replica-password}"
create_user "$SQL_USER_ANALYTICS" "${SECRET_DB_ANALYTICS:-db-analytics-password}"

SCHEMA_FILE="scripts/setup_database_schemas.sql"
if [[ ! -f "$SCHEMA_FILE" ]]; then
  echo "Schema file ${SCHEMA_FILE} is missing" >&2
  exit 1
fi

log "Applying database schema"
if command -v cloud_sql_proxy >/dev/null 2>&1; then
  log "Using cloud_sql_proxy for schema application"
  cloud_sql_proxy -instances="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}=tcp:5433" &
  PROXY_PID=$!
  trap 'kill ${PROXY_PID}' EXIT
  if command -v nc >/dev/null 2>&1; then
    until nc -z localhost 5433 >/dev/null 2>&1; do sleep 1; done
  else
    sleep 5
  fi
  PGPASSWORD=$(gcloud secrets versions access latest --secret="${SECRET_DB_PRIMARY:-db-primary-password}" --project="$PROJECT_ID") \
    psql "host=127.0.0.1 port=5433 user=${SQL_USER_ADMIN} dbname=${SQL_DATABASE}" \
      --set=app_user="$SQL_USER_APP" \
      --set=analytics_user="$SQL_USER_ANALYTICS" \
      --file="$SCHEMA_FILE"
  kill ${PROXY_PID}
  trap - EXIT
else
  warn "cloud_sql_proxy not found; skipping automatic schema import"
fi

log "Granting IAM roles to Cloud Run service accounts"
service_account_exists() {
  local name="$1"
  gcloud iam service-accounts describe "${name}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project="$PROJECT_ID" >/dev/null 2>&1
}

for sa in "${SVC_PROFILES}" "${SVC_POSTINGS}" "${SVC_SEARCH}" "${SVC_ADMIN}" "${SVC_MSGS}" "${SVC_REFRESH}" "${SVC_UI}" "${SVC_INSIGHTS}"; do
  [[ -z "$sa" ]] && continue
  if ! service_account_exists "$sa"; then
    warn "Service account ${sa}@${PROJECT_ID}.iam.gserviceaccount.com missing; skipping IAM bindings"
    continue
  fi
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${sa}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client" >/dev/null
  gcloud sql instances add-iam-policy-binding "$SQL_INSTANCE" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${sa}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/cloudsql.instanceUser" >/dev/null 2>&1 || true

done

log "Cloud SQL setup complete"
