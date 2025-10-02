#!/bin/bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Phase 3 – Pub/Sub infrastructure setup for Headhunter AI
# Creates topics, DLQ, push subscription to Cloud Run webhook, and IAM bindings.

# Configuration (can be overridden by env/flags)
PROJECT_ID=${PROJECT_ID:-"$(gcloud config get-value project 2>/dev/null)"}
REGION=${REGION:-"us-central1"}
CLOUD_RUN_SERVICE=${CLOUD_RUN_SERVICE:-"candidate-enricher"}

# Topics
TOPIC_REQUESTS=${PUBSUB_TOPIC_REQUESTS:-"candidate-process-requests"}
TOPIC_DLQ=${PUBSUB_TOPIC_DLQ:-"dead-letter-queue"}

# Subscription
SUBSCRIPTION_NAME=${PUBSUB_SUBSCRIPTION_NAME:-"${TOPIC_REQUESTS}-push-sub"}

# Service accounts (created by scripts/setup_gcp_infrastructure.sh)
FUNCTIONS_SA_NAME=${FUNCTIONS_SA_NAME:-"headhunter-functions-sa"}
CLOUDRUN_SA_NAME=${CLOUDRUN_SA_NAME:-"candidate-enricher-sa"}

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log() { echo -e "${BLUE}INFO:${NC} $1"; }
ok()  { echo -e "${GREEN}OK:${NC}   $1"; }
warn(){ echo -e "${YELLOW}WARN:${NC} $1"; }
err() { echo -e "${RED}ERR:${NC}  $1"; }

usage() {
  cat <<EOF
Usage: $0 [--project PROJECT_ID] [--region us-central1] [--service candidate-enricher]
          [--topic-requests candidate-process-requests] [--topic-dlq dead-letter-queue]
          [--subscription <name>] [--cloudrun-sa candidate-enricher-sa]

Environment overrides:
  PROJECT_ID, REGION, CLOUD_RUN_SERVICE, PUBSUB_TOPIC_REQUESTS, PUBSUB_TOPIC_DLQ, PUBSUB_SUBSCRIPTION_NAME
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT_ID="$2"; shift 2;;
    --region) REGION="$2"; shift 2;;
    --service) CLOUD_RUN_SERVICE="$2"; shift 2;;
    --topic-requests) TOPIC_REQUESTS="$2"; shift 2;;
    --topic-dlq) TOPIC_DLQ="$2"; shift 2;;
    --subscription) SUBSCRIPTION_NAME="$2"; shift 2;;
    --cloudrun-sa) CLOUDRUN_SA_NAME="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) err "Unknown flag: $1"; usage; exit 1;;
  esac
done

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { err "Missing required command: $1"; exit 1; }
}

validate_inputs() {
  [[ -n "$PROJECT_ID" ]] || { err "PROJECT_ID not set."; exit 1; }
  [[ "$REGION" == "us-central1" ]] || warn "Region is $REGION; Phase 3 expects us-central1" 
  ok "Inputs validated: project=$PROJECT_ID region=$REGION service=$CLOUD_RUN_SERVICE"
}

ensure_apis() {
  log "Ensuring required APIs are enabled"
  for api in pubsub.googleapis.com run.googleapis.com iam.googleapis.com; do
    gcloud services enable "$api" --project "$PROJECT_ID" >/dev/null 2>&1 || true
  done
  ok "APIs ensured"
}

create_topics() {
  log "Creating/ensuring Pub/Sub topics"
  gcloud pubsub topics create "$TOPIC_REQUESTS" --project "$PROJECT_ID" >/dev/null 2>&1 || true
  gcloud pubsub topics create "$TOPIC_DLQ" --project "$PROJECT_ID" >/dev/null 2>&1 || true
  ok "Topics ready: $TOPIC_REQUESTS, $TOPIC_DLQ"
}

grant_iam() {
  log "Granting IAM for Functions publisher and Cloud Run subscriber"
  local functions_sa="$FUNCTIONS_SA_NAME@${PROJECT_ID}.iam.gserviceaccount.com"
  local cloudrun_sa="$CLOUDRUN_SA_NAME@${PROJECT_ID}.iam.gserviceaccount.com"

  # Functions can publish to requests and DLQ (publish only)
  gcloud pubsub topics add-iam-policy-binding "$TOPIC_REQUESTS" \
    --member "serviceAccount:${functions_sa}" --role roles/pubsub.publisher \
    --project "$PROJECT_ID" >/dev/null 2>&1 || true

  gcloud pubsub topics add-iam-policy-binding "$TOPIC_DLQ" \
    --member "serviceAccount:${cloudrun_sa}" --role roles/pubsub.publisher \
    --project "$PROJECT_ID" >/dev/null 2>&1 || true

  # Cloud Run SA as subscriber (not strictly needed for push, but required by plan)
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member "serviceAccount:${cloudrun_sa}" --role roles/pubsub.subscriber \
    >/dev/null 2>&1 || true

  ok "IAM bindings configured"
}

service_url() {
  gcloud run services describe "$CLOUD_RUN_SERVICE" \
    --platform managed --region "$REGION" --project "$PROJECT_ID" \
    --format="value(status.url)"
}

allow_pubsub_invoker() {
  # Pub/Sub will push using OIDC as the specified push SA; that SA needs run.invoker
  local invoker_sa="$1"
  local url
  url=$(service_url)
  if [[ -z "$url" ]]; then err "Cloud Run service URL not found"; exit 1; fi
  log "Granting run.invoker to $invoker_sa on $CLOUD_RUN_SERVICE"
  gcloud run services add-iam-policy-binding "$CLOUD_RUN_SERVICE" \
    --region "$REGION" --project "$PROJECT_ID" \
    --member "serviceAccount:${invoker_sa}" --role roles/run.invoker \
    >/dev/null 2>&1 || true
}

create_push_subscription() {
  log "Creating/ensuring push subscription to Cloud Run webhook"
  local cloudrun_sa="$CLOUDRUN_SA_NAME@${PROJECT_ID}.iam.gserviceaccount.com"
  local endpoint
  endpoint="$(service_url)/pubsub/webhook"
  if [[ -z "$endpoint" ]]; then err "Cloud Run URL unavailable"; exit 1; fi

  # Ensure invoker permission for the push identity
  allow_pubsub_invoker "$cloudrun_sa"

  # Create/update subscription with DLQ and retry policies
  if gcloud pubsub subscriptions describe "$SUBSCRIPTION_NAME" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud pubsub subscriptions update "$SUBSCRIPTION_NAME" \
      --project "$PROJECT_ID" \
      --push-endpoint="$endpoint" \
      --push-auth-service-account="$cloudrun_sa" \
      --dead-letter-topic="projects/${PROJECT_ID}/topics/${TOPIC_DLQ}" \
      --max-delivery-attempts=5 \
      --min-retry-delay=10s --max-retry-delay=60s >/dev/null
  else
    gcloud pubsub subscriptions create "$SUBSCRIPTION_NAME" \
      --project "$PROJECT_ID" \
      --topic="$TOPIC_REQUESTS" \
      --push-endpoint="$endpoint" \
      --push-auth-service-account="$cloudrun_sa" \
      --dead-letter-topic="projects/${PROJECT_ID}/topics/${TOPIC_DLQ}" \
      --max-delivery-attempts=5 \
      --min-retry-delay=10s --max-retry-delay=60s >/dev/null
  fi
  ok "Push subscription ready: $SUBSCRIPTION_NAME -> $endpoint"
}

smoke_test() {
  log "Publishing a smoke test message to $TOPIC_REQUESTS"
  local payload
  payload=$(jq -nc --arg cid "test-$(date +%s)" '{candidate_id:$cid, action:"enrich_profile", timestamp: now|toiso8601 }') || payload="{\"candidate_id\":\"test-$(date +%s)\"}"
  gcloud pubsub topics publish "$TOPIC_REQUESTS" --project "$PROJECT_ID" --message "$payload" >/dev/null || warn "Publish may have failed (check auth)"
  ok "Published test message. Verify Cloud Run logs for delivery."
}

rollback_note() {
  warn "If you need to rollback:"
  echo "  gcloud pubsub subscriptions delete ${SUBSCRIPTION_NAME} --project ${PROJECT_ID}"
  echo "  gcloud pubsub topics delete ${TOPIC_REQUESTS} --project ${PROJECT_ID}"
  echo "  gcloud pubsub topics delete ${TOPIC_DLQ} --project ${PROJECT_ID}"
}

main() {
  require_cmd gcloud
  validate_inputs
  ensure_apis
  create_topics
  grant_iam
  create_push_subscription
  smoke_test
  rollback_note
  ok "Pub/Sub infrastructure setup complete"
}

main "$@"
