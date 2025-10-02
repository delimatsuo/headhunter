#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Deploys the hh-msgs-svc to Cloud Run using Artifact Registry images and the shared infrastructure conventions.

if [[ -z "${GOOGLE_CLOUD_PROJECT:-}" ]]; then
  echo "GOOGLE_CLOUD_PROJECT is required" >&2
  exit 1
fi

SERVICE_NAME="hh-msgs-svc"
REGION="${CLOUD_RUN_REGION:-southamerica-east1}"
ARTIFACT_REPO="${ARTIFACT_REPO:-headhunter-services}"
IMAGE="${REGION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/${ARTIFACT_REPO}/${SERVICE_NAME}:$(date +%Y%m%d%H%M%S)"
PWD=$(pwd)

log() {
  printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$*"
}

log "Building service image for ${SERVICE_NAME}"
DOCKER_BUILDKIT=1 docker build \
  -f services/hh-msgs-svc/Dockerfile \
  -t "${IMAGE}" \
  "${PWD}"

log "Pushing image to Artifact Registry"
docker push "${IMAGE}"

log "Deploying ${SERVICE_NAME} to Cloud Run"
gcloud run deploy "${SERVICE_NAME}" \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region "${REGION}" \
  --image "${IMAGE}" \
  --platform managed \
  --no-allow-unauthenticated \
  --set-env-vars "PORT=8080" \
  --set-env-vars "SERVICE_NAME=${SERVICE_NAME}" \
  --set-env-vars "MSGS_USE_SEED_DATA=${MSGS_USE_SEED_DATA:-false}" \
  --set-env-vars "MSGS_DB_HOST=${MSGS_DB_HOST:-/cloudsql/${CLOUD_SQL_CONNECTION}}" \
  --set-cloudsql-instances "${CLOUD_SQL_CONNECTION}" \
  --min-instances "${MIN_INSTANCES:-0}" \
  --max-instances "${MAX_INSTANCES:-20}" \
  --cpu "${CLOUD_RUN_CPU:-1}" \
  --memory "${CLOUD_RUN_MEMORY:-512Mi}" \
  --service-account "${SERVICE_ACCOUNT:-msgs-service@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com}"

log "Deployment complete. Verifying revision health"
gcloud run services describe "${SERVICE_NAME}" \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region "${REGION}" \
  --format json | jq '.status.address.url'

log "Remember to update IAM bindings for API Gateway if necessary."
