#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

export PUBSUB_EMULATOR_HOST="${PUBSUB_EMULATOR_HOST:-localhost:8681}"
PROJECT_ID="${PUBSUB_EMULATOR_PROJECT:-headhunter-local}"
TOPICS=(
  "profiles.refresh.request"
  "postings.refresh.request"
  "refresh.jobs.dlq"
)
SUBSCRIPTIONS=(
  "profiles.refresh.request.sub:profiles.refresh.request"
  "postings.refresh.request.sub:postings.refresh.request"
  "refresh.jobs.dlq.sub:refresh.jobs.dlq"
)

log() {
  echo "[$(date -Is)] $*" >&2
}

require_command() {
  local binary=$1
  if ! command -v "$binary" >/dev/null 2>&1; then
    log "Required command '${binary}' is not available"
    exit 1
  fi
}

require_emulator() {
  if ! curl -s "http://${PUBSUB_EMULATOR_HOST}" >/dev/null; then
    log "Pub/Sub emulator is not reachable at ${PUBSUB_EMULATOR_HOST}"
    exit 1
  fi
}

normalize_topic_name() {
  local raw=$1
  raw=${raw##projects/*/topics/}
  echo "$raw"
}

normalize_subscription_name() {
  local raw=$1
  raw=${raw##projects/*/subscriptions/}
  echo "$raw"
}

topic_exists() {
  local name=$1
  local normalized_target
  normalized_target=$(normalize_topic_name "$name")
  local existing
  existing=$(gcloud pubsub topics list --project="${PROJECT_ID}" --format='value(name)' 2>/dev/null || true)
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    if [[ $(normalize_topic_name "$line") == "$normalized_target" ]]; then
      return 0
    fi
  done <<<"$existing"
  return 1
}

subscription_exists() {
  local name=$1
  local normalized_target
  normalized_target=$(normalize_subscription_name "$name")
  local existing
  existing=$(gcloud pubsub subscriptions list --project="${PROJECT_ID}" --format='value(name)' 2>/dev/null || true)
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    if [[ $(normalize_subscription_name "$line") == "$normalized_target" ]]; then
      return 0
    fi
  done <<<"$existing"
  return 1
}

ensure_topic() {
  local topic=$1
  if topic_exists "$topic"; then
    log "Pub/Sub topic ${topic} already exists"
    return
  fi
  log "Creating Pub/Sub topic ${topic}"
  gcloud pubsub topics create "$topic" --project="${PROJECT_ID}" >/dev/null
}

ensure_subscription() {
  local subscription=${1%%:*}
  local topic=${1##*:}
  if subscription_exists "$subscription"; then
    log "Subscription ${subscription} already exists"
    return
  fi
  log "Creating subscription ${subscription} -> ${topic}"
  gcloud pubsub subscriptions create "$subscription" \
    --project="${PROJECT_ID}" \
    --topic="$topic" \
    --ack-deadline=600 \
    --expiration-period=never >/dev/null
}

log "Using Pub/Sub emulator host ${PUBSUB_EMULATOR_HOST} (project ${PROJECT_ID})"
require_command gcloud
require_command curl
require_emulator
export CLOUDSDK_CORE_PROJECT="${PROJECT_ID}"

for topic in "${TOPICS[@]}"; do
  ensure_topic "$topic"
done

for spec in "${SUBSCRIPTIONS[@]}"; do
  ensure_subscription "$spec"
done

log "Pub/Sub emulator setup complete"
