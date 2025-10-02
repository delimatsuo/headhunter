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

Creates Cloud Storage buckets and configures lifecycle/IAM for headhunter.
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

log() {
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >&2
}

service_account_exists() {
  local name="$1"
  gcloud iam service-accounts describe "${name}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project="$PROJECT_ID" >/dev/null 2>&1
}

create_bucket() {
  local bucket=$1
  local storage_class=${2:-STANDARD}
  local retention_days=${3:-30}
  if gsutil ls -p "$PROJECT_ID" "gs://${bucket}" >/dev/null 2>&1; then
    log "Bucket ${bucket} already exists"
  else
    log "Creating bucket ${bucket}"
    gsutil mb -p "$PROJECT_ID" -l "$REGION" -c "$storage_class" -b on "gs://${bucket}"
  fi

  log "Configuring default retention ${retention_days} days for ${bucket}"
  gsutil retention set ${retention_days}d "gs://${bucket}" >/dev/null 2>&1 || true
  gsutil versioning set on "gs://${bucket}" >/dev/null

  local lifecycle_file
  lifecycle_file=$(mktemp)
  cat <<JSON >"${lifecycle_file}"
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": ${retention_days}, "matchesStorageClass": ["${storage_class}"]}
    }
  ]
}
JSON
  gsutil lifecycle set "${lifecycle_file}" "gs://${bucket}" >/dev/null
  rm -f "${lifecycle_file}"
}

apply_bucket_iam() {
  local bucket=$1
  shift
  local bindings=()
  for entry in "$@"; do
    [[ -z "$entry" ]] && continue
    if service_account_exists "$entry"; then
      bindings+=("serviceAccount:${entry}@${PROJECT_ID}.iam.gserviceaccount.com:objectViewer")
    else
      log "Service account ${entry}@${PROJECT_ID}.iam.gserviceaccount.com missing; skipping objectViewer binding"
    fi
  done
  if [[ -n "${SVC_ADMIN:-}" ]] && service_account_exists "$SVC_ADMIN"; then
    bindings+=("serviceAccount:${SVC_ADMIN}@${PROJECT_ID}.iam.gserviceaccount.com:objectAdmin")
  fi
  if [[ -n "${SVC_REFRESH:-}" ]] && service_account_exists "$SVC_REFRESH"; then
    bindings+=("serviceAccount:${SVC_REFRESH}@${PROJECT_ID}.iam.gserviceaccount.com:objectCreator")
  fi
  if [[ -n "${SVC_SEARCH:-}" ]] && service_account_exists "$SVC_SEARCH"; then
    bindings+=("serviceAccount:${SVC_SEARCH}@${PROJECT_ID}.iam.gserviceaccount.com:objectViewer")
  fi

  for binding in "${bindings[@]}"; do
    gsutil iam ch "${binding}" "gs://${bucket}" >/dev/null
  done
}

log "Setting project ${PROJECT_ID}" \
  && gcloud config set project "$PROJECT_ID" >/dev/null

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
GCS_PUBLISHER_SA="service-${PROJECT_NUMBER}@gs-project-accounts.iam.gserviceaccount.com"

create_bucket "$BUCKET_RAW_PROFILES" STANDARD 30
create_bucket "$BUCKET_POSTINGS" NEARLINE 90
create_bucket "$BUCKET_PROCESSED" STANDARD 60
create_bucket "$BUCKET_EXPORTS" STANDARD 7

apply_bucket_iam "$BUCKET_RAW_PROFILES" "$SVC_PROFILES" "$SVC_POSTINGS" "$SVC_UI"
apply_bucket_iam "$BUCKET_POSTINGS" "$SVC_POSTINGS" "$SVC_INSIGHTS"
apply_bucket_iam "$BUCKET_PROCESSED" "$SVC_PROFILES" "$SVC_POSTINGS" "$SVC_SEARCH"
apply_bucket_iam "$BUCKET_EXPORTS" "$SVC_ADMIN" "$SVC_UI"

if [[ -n "${PUBSUB_TOPIC_PROFILES:-}" ]]; then
  log "Granting Pub/Sub publisher role to GCS service account"
  gcloud pubsub topics add-iam-policy-binding "$PUBSUB_TOPIC_PROFILES" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${GCS_PUBLISHER_SA}" \
    --role="roles/pubsub.publisher" >/dev/null

  log "Creating notification for raw profiles bucket"
  gsutil notification create -t "$PUBSUB_TOPIC_PROFILES" -f json "gs://${BUCKET_RAW_PROFILES}" >/dev/null 2>&1 || true
fi

log "Cloud Storage setup complete"
