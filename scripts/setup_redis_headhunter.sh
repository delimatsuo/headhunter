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

Creates the Memorystore Redis instance redis-skills-us-central1 and configures IAM.
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
  echo "Project ID must be provided" >&2
  exit 1
fi

if [[ -z "${REDIS_INSTANCE:-}" ]]; then
  echo "REDIS_INSTANCE must be defined in config" >&2
  exit 1
fi

VPC_NAME=${VPC_NAME:-vpc-hh}
REDIS_TIER=${REDIS_TIER:-standard}
case "${REDIS_TIER,,}" in
  standard|standard_ha|standard-ha)
    REDIS_TIER="standard"
    ;;
  basic)
    REDIS_TIER="basic"
    ;;
  *)
    REDIS_TIER="${REDIS_TIER,,}"
    ;;
esac
REDIS_MEMORY_SIZE_GB=${REDIS_MEMORY_SIZE_GB:-8}
REDIS_REPLICA_COUNT=${REDIS_REPLICA_COUNT:-1}
REDIS_ENGINE_VERSION=${REDIS_ENGINE_VERSION:-redis_7_0}
REDIS_TLS_ENABLED=${REDIS_TLS_ENABLED:-true}

log() {
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >&2
}

log "Setting project ${PROJECT_ID}" \
  && gcloud config set project "$PROJECT_ID" >/dev/null

if gcloud redis instances describe "$REDIS_INSTANCE" --region="$REGION" \
  --project="$PROJECT_ID" >/dev/null 2>&1; then
  log "Redis instance ${REDIS_INSTANCE} already exists"
else
  log "Creating Redis instance ${REDIS_INSTANCE}"
  AUTH_ARG="--transit-encryption-mode=SERVER_AUTHENTICATION"
  if [[ "$REDIS_TLS_ENABLED" == "false" ]]; then
    AUTH_ARG="--transit-encryption-mode=DISABLED"
  fi

  gcloud redis instances create "$REDIS_INSTANCE" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --tier="$REDIS_TIER" \
    --size="$REDIS_MEMORY_SIZE_GB" \
    --replica-count="$REDIS_REPLICA_COUNT" \
    --redis-version="$REDIS_ENGINE_VERSION" \
    --network="projects/${PROJECT_ID}/global/networks/${VPC_NAME}" \
    --connect-mode=private-service-access \
    --maintenance-window-day=MONDAY \
    --maintenance-window-hour=3 \
    --labels=env=prod,team=headhunter ${AUTH_ARG}
fi

if [[ -n "${SECRET_REDIS_ENDPOINT:-}" ]]; then
  log "Ensuring Redis secret ${SECRET_REDIS_ENDPOINT} exists"
  if ! gcloud secrets describe "$SECRET_REDIS_ENDPOINT" --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud secrets create "$SECRET_REDIS_ENDPOINT" \
      --project="$PROJECT_ID" \
      --replication-policy=user-managed \
      --locations="$REGION"
  fi

  log "Publishing Redis endpoint URI to Secret Manager"
  HOST=$(gcloud redis instances describe "$REDIS_INSTANCE" --region="$REGION" \
    --project="$PROJECT_ID" --format="get(host)")
  PORT=$(gcloud redis instances describe "$REDIS_INSTANCE" --region="$REGION" \
    --project="$PROJECT_ID" --format="get(port)")
  REDIS_URI="rediss://${HOST}:${PORT}"
  echo "$REDIS_URI" | gcloud secrets versions add "$SECRET_REDIS_ENDPOINT" \
    --project="$PROJECT_ID" --data-file=- >/dev/null
fi

log "Granting Redis Client role"
service_account_exists() {
  local name="$1"
  gcloud iam service-accounts describe "${name}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project="$PROJECT_ID" >/dev/null 2>&1
}

for sa in "${SVC_PROFILES}" "${SVC_POSTINGS}" "${SVC_SEARCH}" "${SVC_ADMIN}" "${SVC_MSGS}" "${SVC_REFRESH}" "${SVC_UI}" "${SVC_INSIGHTS}"; do
  [[ -z "$sa" ]] && continue
  if ! service_account_exists "$sa"; then
    log "Service account ${sa}@${PROJECT_ID}.iam.gserviceaccount.com missing; skipping IAM bindings"
    continue
  fi
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${sa}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/redis.client" >/dev/null
  if [[ -n "${SECRET_REDIS_ENDPOINT:-}" ]]; then
    gcloud secrets add-iam-policy-binding "$SECRET_REDIS_ENDPOINT" \
      --project="$PROJECT_ID" \
      --member="serviceAccount:${sa}@${PROJECT_ID}.iam.gserviceaccount.com" \
      --role="roles/secretmanager.secretAccessor" >/dev/null
  fi
done

log "Redis setup complete"
