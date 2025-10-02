#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

usage() {
  cat <<USAGE
Usage: $(basename "$0") --project-id PROJECT_ID

Enables all GCP APIs required for the headhunter platform.
USAGE
}

PROJECT_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      PROJECT_ID="$2"
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

if [[ -z "$PROJECT_ID" ]]; then
  echo "--project-id is required" >&2
  usage
  exit 1
fi

REQUIRED_APIS=(
  run.googleapis.com
  runapps.googleapis.com
  runjob.googleapis.com
  cloudbuild.googleapis.com
  compute.googleapis.com
  containerregistry.googleapis.com
  artifactregistry.googleapis.com
  secretmanager.googleapis.com
  servicenetworking.googleapis.com
  sqladmin.googleapis.com
  redis.googleapis.com
  vpcaccess.googleapis.com
  pubsub.googleapis.com
  cloudscheduler.googleapis.com
  aiplatform.googleapis.com
  firestore.googleapis.com
  storage.googleapis.com
  iam.googleapis.com
  logging.googleapis.com
  monitoring.googleapis.com
  cloudtrace.googleapis.com
  cloudresourcemanager.googleapis.com
  eventarc.googleapis.com
  apigateway.googleapis.com
  dns.googleapis.com
  cloudkms.googleapis.com
)

echo "Enabling required APIs for project ${PROJECT_ID}" >&2

gcloud config set project "$PROJECT_ID" >/dev/null

for api in "${REQUIRED_APIS[@]}"; do
  echo "Enabling ${api}..." >&2
  if ! gcloud services enable "$api" --project="$PROJECT_ID"; then
    if [[ "$api" == "runjob.googleapis.com" ]]; then
      echo "Warning: ${api} could not be enabled (continuing)." >&2
      continue
    fi
    echo "Failed to enable ${api}" >&2
    exit 1
  fi
done

echo "Verifying API enablement..." >&2
enabled_apis=$(gcloud services list --enabled --project="$PROJECT_ID" --format="value(config.name)" 2>/dev/null)

# Check which required APIs are missing
missing_apis=""
for api in "${REQUIRED_APIS[@]}"; do
  # Skip runjob.googleapis.com in verification as it may not show up in standard API list
  if [[ "$api" == "runjob.googleapis.com" ]]; then
    continue
  fi
  if ! echo "$enabled_apis" | grep -qx "$api"; then
    missing_apis="${missing_apis}${missing_apis:+ }${api}"
  fi
done

if [[ -n "$missing_apis" ]]; then
  echo "Warning: the following expected APIs are not enabled: ${missing_apis}" >&2
else
  echo "All required APIs are enabled." >&2
fi
