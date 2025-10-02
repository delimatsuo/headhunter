#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Deploys the hh-admin-svc Cloud Run service. The script builds the Docker image,
# pushes it to Artifact Registry (or GCR), deploys the service with hardened IAM,
# and runs a lightweight health check. It expects gcloud to be authenticated with
# the target project.

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-hh-admin-svc}"
REPOSITORY="${REPOSITORY:-hh-services}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-}" # Optional dedicated runtime SA
PLATFORM="${PLATFORM:-managed}"
ALLOW_UNAUTH="${ALLOW_UNAUTH:-false}"
TIMEOUT="${TIMEOUT:-900s}"
PORT="${PORT:-8080}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "PROJECT_ID must be provided" >&2
  exit 1
fi

if ! gcloud config get-value project &>/dev/null; then
  gcloud config set project "$PROJECT_ID" >/dev/null
fi

enable_api() {
  local api="$1"
  if ! gcloud services list --enabled --format="value(config.name)" | grep -q "^${api}$"; then
    echo "Enabling ${api}"
    gcloud services enable "$api"
  fi
}

enable_api run.googleapis.com
enable_api artifactregistry.googleapis.com
enable_api pubsub.googleapis.com
enable_api cloudscheduler.googleapis.com

echo "Ensuring Artifact Registry repository"
if ! gcloud artifacts repositories describe "$REPOSITORY" --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPOSITORY" \
    --repository-format=docker \
    --location="$REGION" \
    --description="HeadHunter service images"
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:${IMAGE_TAG}"

echo "Building container image ${IMAGE}"
gcloud builds submit \
  --project="$PROJECT_ID" \
  --tag="${IMAGE}" \
  --file=services/hh-admin-svc/Dockerfile \
  .

RUNTIME_ENV_VARS=()
RUNTIME_ENV_VARS+=("PORT=${PORT}")
RUNTIME_ENV_VARS+=("SERVICE_NAME=${SERVICE_NAME}")
RUNTIME_ENV_VARS+=("ADMIN_POSTINGS_TOPIC=${ADMIN_POSTINGS_TOPIC:-projects/${PROJECT_ID}/topics/postings.refresh.request}")
RUNTIME_ENV_VARS+=("ADMIN_PROFILES_TOPIC=${ADMIN_PROFILES_TOPIC:-projects/${PROJECT_ID}/topics/profiles.refresh.request}")
RUNTIME_ENV_VARS+=("ADMIN_POSTINGS_JOB=${ADMIN_POSTINGS_JOB:-projects/${PROJECT_ID}/locations/${REGION}/jobs/msgs-refresh-job}")
RUNTIME_ENV_VARS+=("ADMIN_PROFILES_JOB=${ADMIN_PROFILES_JOB:-projects/${PROJECT_ID}/locations/${REGION}/jobs/profiles-refresh-job}")
RUNTIME_ENV_VARS+=("ADMIN_SCHEDULER_PROJECT=${ADMIN_SCHEDULER_PROJECT:-${PROJECT_ID}}")
RUNTIME_ENV_VARS+=("ADMIN_SCHEDULER_LOCATION=${ADMIN_SCHEDULER_LOCATION:-${REGION}}")
RUNTIME_ENV_VARS+=("ADMIN_SCHEDULER_SERVICE_ACCOUNT=${ADMIN_SCHEDULER_SERVICE_ACCOUNT:-admin-scheduler@${PROJECT_ID}.iam.gserviceaccount.com}")
RUNTIME_ENV_VARS+=("ADMIN_SCHEDULER_TARGET_BASE_URL=${ADMIN_SCHEDULER_TARGET_BASE_URL:-https://admin.${REGION}.run.app}")
RUNTIME_ENV_VARS+=("ADMIN_MONITORING_PROJECT=${ADMIN_MONITORING_PROJECT:-${PROJECT_ID}}")

ENV_FLAGS=$(printf ",%s" "${RUNTIME_ENV_VARS[@]}")
ENV_FLAGS=${ENV_FLAGS:1}

ARGS=(
  run deploy "$SERVICE_NAME"
  --image="$IMAGE"
  --platform="$PLATFORM"
  --region="$REGION"
  --project="$PROJECT_ID"
  --timeout="$TIMEOUT"
  --set-env-vars="$ENV_FLAGS"
  --min-instances=0
  --max-instances=5
  --concurrency=20
)

if [[ "$ALLOW_UNAUTH" == "true" ]]; then
  ARGS+=(--allow-unauthenticated)
else
  ARGS+=(--no-allow-unauthenticated)
fi

if [[ -n "$SERVICE_ACCOUNT" ]]; then
  ARGS+=(--service-account="$SERVICE_ACCOUNT")
fi

echo "Deploying Cloud Run service"
gcloud "${ARGS[@]}"

URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --platform="$PLATFORM" --project="$PROJECT_ID" --format="value(status.url)")

if [[ -z "$URL" ]]; then
  echo "Failed to retrieve service URL" >&2
  exit 1
fi

echo "Service deployed at ${URL}"

echo "Performing health check"
if ! curl -fsS "${URL}/health" >/dev/null; then
  echo "Health check failed" >&2
  exit 1
fi

echo "Deployment completed successfully"
