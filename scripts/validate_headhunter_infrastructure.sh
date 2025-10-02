#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

CONFIG_FILE="config/infrastructure/headhunter-production.env"
CLI_PROJECT_ID=""
OUTPUT_FILE=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--project-id PROJECT_ID] [--config PATH] [--output PATH]

Validates that headhunter infrastructure matches PRD requirements.
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
  echo "Project ID must be provided" >&2
  exit 1
fi

SQL_INSTANCE=${SQL_INSTANCE:-sql-hh-core}
SQL_DATABASE=${SQL_DATABASE:-headhunter}
SQL_USER_ADMIN=${SQL_USER_ADMIN:-hh_admin}
REDIS_INSTANCE=${REDIS_INSTANCE:-redis-skills-us-central1}
SECRET_DB_PRIMARY=${SECRET_DB_PRIMARY:-db-primary-password}
SECRET_DB_REPLICA=${SECRET_DB_REPLICA:-db-replica-password}
SECRET_DB_ANALYTICS=${SECRET_DB_ANALYTICS:-db-analytics-password}
SECRET_REDIS_ENDPOINT=${SECRET_REDIS_ENDPOINT:-redis-endpoint}

REPORT="Infrastructure validation report for project ${PROJECT_ID}
Generated: $(date -u '+%Y-%m-%dT%H:%M:%SZ')
\n"

append_report() {
  REPORT+="$1\n"
}

run_check() {
  local description=$1
  shift
  if "$@" >/dev/null 2>&1; then
    append_report "[PASS] ${description}"
  else
    append_report "[FAIL] ${description}"
  fi
}

ADMIN_PASSWORD=""
SQL_PASSWORD_AVAILABLE=false
SQL_PASSWORD_ERROR=""

if [[ -n "$SECRET_DB_PRIMARY" ]]; then
  if ADMIN_PASSWORD=$(gcloud secrets versions access latest --secret="$SECRET_DB_PRIMARY" --project="$PROJECT_ID" 2>/dev/null); then
    SQL_PASSWORD_AVAILABLE=true
  else
    SQL_PASSWORD_ERROR="Unable to access secret ${SECRET_DB_PRIMARY}"
  fi
else
  SQL_PASSWORD_ERROR="SECRET_DB_PRIMARY not configured"
fi

pg_exec() {
  local sql=$1
  if [[ "$SQL_PASSWORD_AVAILABLE" != true ]]; then
    return 2
  fi
  if ! command -v cloud_sql_proxy >/dev/null 2>&1; then
    SQL_PASSWORD_ERROR="cloud_sql_proxy not installed for SQL validation"
    return 2
  fi
  local output status
  local proxy_port=5436
  cloud_sql_proxy -instances="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}=tcp:${proxy_port}" >/dev/null 2>&1 &
  local proxy_pid=$!
  trap 'kill ${proxy_pid} >/dev/null 2>&1 || true' EXIT
  # Wait briefly for proxy
  sleep 3
  set +e
  output=$(PGPASSWORD="$ADMIN_PASSWORD" psql "host=127.0.0.1 port=${proxy_port} user=${SQL_USER_ADMIN} dbname=${SQL_DATABASE}" -Atc "$sql" 2>/dev/null)
  status=$?
  set -e
  kill ${proxy_pid} >/dev/null 2>&1 || true
  trap - EXIT
  if [[ $status -ne 0 ]]; then
    SQL_PASSWORD_ERROR="psql execution failed"
  fi
  PG_QUERY_RESULT="$output"
  return $status
}

append_report "--- API Checks ---"
for api in run.googleapis.com sqladmin.googleapis.com redis.googleapis.com secretmanager.googleapis.com pubsub.googleapis.com storage.googleapis.com aiplatform.googleapis.com firestore.googleapis.com vpcaccess.googleapis.com compute.googleapis.com logging.googleapis.com monitoring.googleapis.com cloudtrace.googleapis.com cloudscheduler.googleapis.com artifactregistry.googleapis.com; do
  if gcloud services list --enabled --project="$PROJECT_ID" --format="value(config.name)" | grep -qx "$api"; then
    append_report "[PASS] ${api} enabled"
  else
    append_report "[FAIL] ${api} missing"
  fi
done

append_report "\n--- Networking ---"
run_check "VPC ${VPC_NAME} exists" gcloud compute networks describe "$VPC_NAME" --project="$PROJECT_ID"
run_check "Connector ${VPC_CONNECTOR} exists" gcloud compute networks vpc-access connectors describe "$VPC_CONNECTOR" --region="$REGION" --project="$PROJECT_ID"
run_check "Cloud NAT ${NAT_GATEWAY_NAME} exists" gcloud compute routers nats describe "$NAT_GATEWAY_NAME" --router="$ROUTER_NAME" --region="$REGION" --project="$PROJECT_ID"

DESTINATION_RANGES=${CONNECTOR_EGRESS_ALLOWED_CIDRS//[[:space:]]/}
if [[ -z "$DESTINATION_RANGES" ]]; then
  append_report "[WARN] CONNECTOR_EGRESS_ALLOWED_CIDRS is unset; allowlisting requires explicit CIDRs and Cloud Run deployments with --vpc-connector \"${VPC_CONNECTOR}\" plus --vpc-egress all-traffic."
elif [[ "$DESTINATION_RANGES" == "0.0.0.0/0" ]]; then
  append_report "[WARN] CONNECTOR_EGRESS_ALLOWED_CIDRS currently allows 0.0.0.0/0; tighten the range and deploy Cloud Run services with --vpc-connector \"${VPC_CONNECTOR}\" and --vpc-egress all-traffic to enforce egress policy."
else
  append_report "[INFO] CONNECTOR_EGRESS_ALLOWED_CIDRS=${DESTINATION_RANGES}; enforcement still depends on Cloud Run services using --vpc-connector \"${VPC_CONNECTOR}\" with --vpc-egress all-traffic."
fi

append_report "\n--- Cloud SQL ---"
run_check "Instance ${SQL_INSTANCE} exists" gcloud sql instances describe "$SQL_INSTANCE" --project="$PROJECT_ID"
run_check "Database ${SQL_DATABASE} exists" gcloud sql databases describe "$SQL_DATABASE" --instance="$SQL_INSTANCE" --project="$PROJECT_ID"
if FLAGS_OUTPUT=$(gcloud sql instances describe "$SQL_INSTANCE" --project="$PROJECT_ID" --format='value(settings.databaseFlags)' 2>/dev/null); then
  if [[ "$FLAGS_OUTPUT" == *"cloudsql.enable_pgvector=true"* ]]; then
    append_report "[PASS] cloudsql.enable_pgvector flag present"
  else
    append_report "[FAIL] cloudsql.enable_pgvector flag missing"
  fi
else
  append_report "[FAIL] Unable to read database flags for ${SQL_INSTANCE}"
fi

set +e
pg_exec "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector');"
PG_STATUS=$?
set -e
if [[ $PG_STATUS -eq 0 ]]; then
  RESULT=${PG_QUERY_RESULT//[[:space:]]/}
  if [[ "$RESULT" == "t" ]]; then
    append_report "[PASS] pgvector extension installed"
  else
    append_report "[FAIL] pgvector extension installed (returned ${RESULT:-none})"
  fi
elif [[ $PG_STATUS -eq 2 ]]; then
  ERROR_MSG=${SQL_PASSWORD_ERROR:-"admin credentials unavailable"}
  append_report "[WARN] pgvector extension check skipped (${ERROR_MSG})"
else
  append_report "[FAIL] pgvector extension installed (query execution failed)"
fi

set +e
pg_exec "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='search' AND table_name='candidate_embeddings');"
PG_STATUS=$?
set -e
if [[ $PG_STATUS -eq 0 ]]; then
  RESULT=${PG_QUERY_RESULT//[[:space:]]/}
  if [[ "$RESULT" == "t" ]]; then
    append_report "[PASS] search.candidate_embeddings table exists"
  else
    append_report "[FAIL] search.candidate_embeddings table exists (returned ${RESULT:-none})"
  fi
elif [[ $PG_STATUS -eq 2 ]]; then
  ERROR_MSG=${SQL_PASSWORD_ERROR:-"admin credentials unavailable"}
  append_report "[WARN] search.candidate_embeddings table check skipped (${ERROR_MSG})"
else
  append_report "[FAIL] search.candidate_embeddings table exists (query execution failed)"
fi

append_report "\n--- Memorystore ---"
run_check "Redis ${REDIS_INSTANCE} exists" gcloud redis instances describe "$REDIS_INSTANCE" --region="$REGION" --project="$PROJECT_ID"

append_report "\n--- Pub/Sub ---"
run_check "Topic ${PUBSUB_TOPIC_PROFILES} exists" gcloud pubsub topics describe "$PUBSUB_TOPIC_PROFILES" --project="$PROJECT_ID"
run_check "Topic ${PUBSUB_TOPIC_POSTINGS} exists" gcloud pubsub topics describe "$PUBSUB_TOPIC_POSTINGS" --project="$PROJECT_ID"
run_check "Topic ${PUBSUB_DLQ_TOPIC} exists" gcloud pubsub topics describe "$PUBSUB_DLQ_TOPIC" --project="$PROJECT_ID"
run_check "Subscription ${PUBSUB_SUBSCRIPTION_PROFILES} exists" gcloud pubsub subscriptions describe "$PUBSUB_SUBSCRIPTION_PROFILES" --project="$PROJECT_ID"
run_check "Subscription ${PUBSUB_SUBSCRIPTION_POSTINGS} exists" gcloud pubsub subscriptions describe "$PUBSUB_SUBSCRIPTION_POSTINGS" --project="$PROJECT_ID"

append_report "\n--- Cloud Storage ---"
for bucket in "$BUCKET_RAW_PROFILES" "$BUCKET_POSTINGS" "$BUCKET_PROCESSED" "$BUCKET_EXPORTS"; do
  if gsutil ls "gs://${bucket}" >/dev/null 2>&1; then
    append_report "[PASS] Bucket ${bucket} exists"
  else
    append_report "[FAIL] Bucket ${bucket} missing"
  fi
done

append_report "\n--- Secret Manager ---"
for secret in "$SECRET_DB_PRIMARY" "$SECRET_DB_REPLICA" "$SECRET_DB_ANALYTICS" "$SECRET_TOGETHER_AI" "$SECRET_GEMINI_AI" "$SECRET_OAUTH_CLIENT" "$SECRET_REDIS_ENDPOINT" "$SECRET_STORAGE_SIGNER"; do
  if gcloud secrets describe "$secret" --project="$PROJECT_ID" >/dev/null 2>&1; then
    append_report "[PASS] Secret ${secret} exists"
  else
    append_report "[FAIL] Secret ${secret} missing"
  fi
done

append_report "\n--- IAM Role Checks ---"
for sa in "$SVC_PROFILES" "$SVC_POSTINGS" "$SVC_MSGS" "$SVC_SEARCH" "$SVC_ADMIN" "$SVC_REFRESH" "$SVC_UI" "$SVC_INSIGHTS"; do
  if gcloud iam service-accounts describe "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" --project="$PROJECT_ID" >/dev/null 2>&1; then
    append_report "[PASS] Service account ${sa} exists"
  else
    append_report "[FAIL] Service account ${sa} missing"
  fi
done

if [[ -n "$OUTPUT_FILE" ]]; then
  printf '%s\n' "$REPORT" > "$OUTPUT_FILE"
  echo "Validation report written to ${OUTPUT_FILE}"
else
  printf '%s\n' "$REPORT"
fi
