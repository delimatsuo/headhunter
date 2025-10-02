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

Creates Pub/Sub topics and subscriptions for headhunter refresh workflows.
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

PUBSUB_TOPIC_PROFILES=${PUBSUB_TOPIC_PROFILES:-profiles.refresh.request}
PUBSUB_SUBSCRIPTION_PROFILES=${PUBSUB_SUBSCRIPTION_PROFILES:-profiles.refresh.request.sub}
PUBSUB_TOPIC_POSTINGS=${PUBSUB_TOPIC_POSTINGS:-postings.refresh.request}
PUBSUB_SUBSCRIPTION_POSTINGS=${PUBSUB_SUBSCRIPTION_POSTINGS:-postings.refresh.request.sub}
PUBSUB_DLQ_TOPIC=${PUBSUB_DLQ_TOPIC:-refresh.jobs.dlq}
PUBSUB_DLQ_SUBSCRIPTION=${PUBSUB_DLQ_SUBSCRIPTION:-refresh.jobs.dlq.sub}

log() {
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >&2
}

service_account_exists() {
  local name="$1"
  gcloud iam service-accounts describe "${name}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project="$PROJECT_ID" >/dev/null 2>&1
}

ensure_topic() {
  local topic=$1
  if ! gcloud pubsub topics describe "$topic" --project="$PROJECT_ID" >/dev/null 2>&1; then
    log "Creating topic ${topic}"
    gcloud pubsub topics create "$topic" --project="$PROJECT_ID" \
      --labels=env=prod,component=refresh
  fi
}

ensure_subscription() {
  local subscription=$1
  local topic=$2
  local dlq=$3
  if ! gcloud pubsub subscriptions describe "$subscription" --project="$PROJECT_ID" >/dev/null 2>&1; then
    log "Creating subscription ${subscription}"
    gcloud pubsub subscriptions create "$subscription" \
      --project="$PROJECT_ID" \
      --topic="$topic" \
      --dead-letter-topic="$dlq" \
      --min-retry-delay=10s \
      --max-retry-delay=10m \
      --max-delivery-attempts=6 \
      --ack-deadline=600 \
      --expiration-period=never \
      --labels=env=prod,component=refresh
  fi
}

log "Setting project ${PROJECT_ID}" \
  && gcloud config set project "$PROJECT_ID" >/dev/null

ensure_topic "$PUBSUB_TOPIC_PROFILES"
ensure_topic "$PUBSUB_TOPIC_POSTINGS"
ensure_topic "$PUBSUB_DLQ_TOPIC"

ensure_subscription "$PUBSUB_SUBSCRIPTION_PROFILES" "$PUBSUB_TOPIC_PROFILES" "$PUBSUB_DLQ_TOPIC"
ensure_subscription "$PUBSUB_SUBSCRIPTION_POSTINGS" "$PUBSUB_TOPIC_POSTINGS" "$PUBSUB_DLQ_TOPIC"

if ! gcloud pubsub subscriptions describe "$PUBSUB_DLQ_SUBSCRIPTION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  log "Creating DLQ subscription ${PUBSUB_DLQ_SUBSCRIPTION}"
  gcloud pubsub subscriptions create "$PUBSUB_DLQ_SUBSCRIPTION" \
    --project="$PROJECT_ID" \
    --topic="$PUBSUB_DLQ_TOPIC" \
    --ack-deadline=600 \
    --expiration-period=never \
    --labels=env=prod,component=refresh
fi

log "Configuring IAM roles"
for sa in "${SVC_ADMIN}" "${SVC_REFRESH}" "${SVC_PROFILES}" "${SVC_POSTINGS}"; do
  [[ -z "$sa" ]] && continue
  if ! service_account_exists "$sa"; then
    log "Service account ${sa}@${PROJECT_ID}.iam.gserviceaccount.com missing; skipping IAM bindings"
    continue
  fi
  gcloud pubsub topics add-iam-policy-binding "$PUBSUB_TOPIC_PROFILES" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${sa}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/pubsub.publisher" >/dev/null
  gcloud pubsub topics add-iam-policy-binding "$PUBSUB_TOPIC_POSTINGS" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${sa}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/pubsub.publisher" >/dev/null
  gcloud pubsub subscriptions add-iam-policy-binding "$PUBSUB_SUBSCRIPTION_PROFILES" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${sa}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/pubsub.subscriber" >/dev/null
  gcloud pubsub subscriptions add-iam-policy-binding "$PUBSUB_SUBSCRIPTION_POSTINGS" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${sa}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/pubsub.subscriber" >/dev/null
done

log "Pub/Sub setup complete"
