#!/bin/bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Phase 3 – Validation script

PROJECT_ID=${PROJECT_ID:-"$(gcloud config get-value project 2>/dev/null)"}
REGION=${REGION:-"us-central1"}
SERVICE=${SERVICE:-"candidate-enricher"}
TOPIC_REQUESTS=${PUBSUB_TOPIC_REQUESTS:-"candidate-process-requests"}
TOPIC_DLQ=${PUBSUB_TOPIC_DLQ:-"dead-letter-queue"}
SUBSCRIPTION=${PUBSUB_SUBSCRIPTION:-"${TOPIC_REQUESTS}-push-sub"}

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok(){ echo -e "${GREEN}[OK]${NC} $1"; }
fail(){ echo -e "${RED}[FAIL]${NC} $1"; }
warn(){ echo -e "${YELLOW}[WARN]${NC} $1"; }

require() { command -v "$1" >/dev/null 2>&1 || { fail "Missing $1"; exit 1; }; }

require gcloud

echo "Validating Phase 3 Deployment for project=$PROJECT_ID region=$REGION"

# 1) Topics and subscription
if gcloud pubsub topics describe "$TOPIC_REQUESTS" --project "$PROJECT_ID" >/dev/null 2>&1; then ok "Topic: $TOPIC_REQUESTS"; else fail "Missing topic: $TOPIC_REQUESTS"; fi
if gcloud pubsub topics describe "$TOPIC_DLQ" --project "$PROJECT_ID" >/dev/null 2>&1; then ok "Topic: $TOPIC_DLQ"; else fail "Missing topic: $TOPIC_DLQ"; fi
if gcloud pubsub subscriptions describe "$SUBSCRIPTION" --project "$PROJECT_ID" >/dev/null 2>&1; then ok "Subscription: $SUBSCRIPTION"; else fail "Missing subscription: $SUBSCRIPTION"; fi

# 2) IAM bindings
FUNCTIONS_SA="headhunter-functions-sa@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUDRUN_SA="headhunter-cloudrun-sa@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud pubsub topics get-iam-policy "$TOPIC_REQUESTS" --project "$PROJECT_ID" --format=json | jq -e \
  --arg m "serviceAccount:${FUNCTIONS_SA}" '.bindings[]?|select(.role=="roles/pubsub.publisher")|.members[]?|select(.==$m)' >/dev/null 2>&1 \
  && ok "Functions SA can publish to requests" || warn "Functions SA missing publisher role"

gcloud run services get-iam-policy "$SERVICE" --region "$REGION" --project "$PROJECT_ID" --format=json | jq -e \
  --arg m "serviceAccount:${CLOUDRUN_SA}" '.bindings[]?|select(.role=="roles/run.invoker")|.members[]?|select(.==$m)' >/dev/null 2>&1 \
  && ok "Cloud Run SA is invoker for push" || warn "Cloud Run SA missing run.invoker"

# 3) Cloud Run config
URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT_ID" --format='value(status.url)')
if [[ -n "$URL" ]]; then ok "Cloud Run URL: $URL"; else fail "Could not fetch Cloud Run URL"; fi

# 4) Publish a test message
TEST_MSG="{\"candidate_id\":\"validate-$(date +%s)\",\"action\":\"enrich_profile\"}"
if gcloud pubsub topics publish "$TOPIC_REQUESTS" --project "$PROJECT_ID" --message "$TEST_MSG" >/dev/null 2>&1; then
  ok "Published validation message"
else
  fail "Failed to publish validation message"
fi

echo "\nSuggestions if issues are found:"
echo "- Re-run scripts/setup_pubsub_infrastructure.sh"
echo "- Verify Functions deploy and environment variables"
echo "- Inspect Cloud Run logs for /pubsub/webhook handler"
echo "- Check DLQ topic and delivery attempts"

