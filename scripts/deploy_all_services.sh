#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Deploy all Cloud Run services for the Headhunter platform.
#
# Usage:
#   ./scripts/deploy_all_services.sh [staging|production]
#
# The script expects gcloud to be authenticated and configured with the
# appropriate project. Container images are built locally, pushed to
# Artifact Registry, and Cloud Run services are updated using the
# configuration manifests in config/cloud-run/.

ENVIRONMENT="${1:-staging}"
if [[ "${ENVIRONMENT}" != "staging" && "${ENVIRONMENT}" != "production" ]]; then
  echo "Environment must be staging or production" >&2
  exit 1
fi

PROJECT_ID="${PROJECT_ID:-headhunter-${ENVIRONMENT}}"
REGION="${REGION:-us-central1}"
REGISTRY="${REGISTRY:-us-docker.pkg.dev/${PROJECT_ID}/headhunter-services}"
SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_ROOT="${SOURCE_ROOT}/config/cloud-run"
BUILD_TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
export PROJECT_ID REGION ENVIRONMENT REGISTRY

SERVICES=(
  "hh-embed-svc"
  "hh-search-svc"
  "hh-rerank-svc"
  "hh-evidence-svc"
  "hh-eco-svc"
  "hh-enrich-svc"
  "hh-admin-svc"
  "hh-msgs-svc"
)

readonly SERVICES

log() {
  printf '[deploy][%s] %s\n' "${ENVIRONMENT}" "$1"
}

require_tooling() {
  command -v gcloud >/dev/null 2>&1 || { echo "gcloud CLI is required" >&2; exit 1; }
  command -v docker >/dev/null 2>&1 || { echo "docker CLI is required" >&2; exit 1; }
}

ensure_artifact_repository() {
  log "Ensuring Artifact Registry ${REGISTRY} exists"
  gcloud artifacts repositories describe "${REGISTRY##*/}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    >/dev/null 2>&1 || {
      gcloud artifacts repositories create "${REGISTRY##*/}" \
        --project="${PROJECT_ID}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="Headhunter services"
    }
}

set_service_overrides() {
  local service="$1"
  local image_uri="$2"
  export SERVICE_ENVIRONMENT="${ENVIRONMENT}"
  export SERVICE_PROJECT_ID="${PROJECT_ID}"
  export SERVICE_REGION="${REGION}"
  export SERVICE_IMAGE="${image_uri}"
  export SERVICE_NAME="${service}-${ENVIRONMENT}"

  case "${service}" in
    hh-embed-svc)
      if [[ "${ENVIRONMENT}" == "production" ]]; then
        export SERVICE_MIN_SCALE=2 SERVICE_MAX_SCALE=100
      else
        export SERVICE_MIN_SCALE=1 SERVICE_MAX_SCALE=10
      fi
      export SERVICE_CPU=2 SERVICE_MEMORY="4Gi" SERVICE_CONCURRENCY=4 SERVICE_PORT=7101
      export SERVICE_ACCOUNT="embed-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    hh-search-svc)
      if [[ "${ENVIRONMENT}" == "production" ]]; then
        export SERVICE_MIN_SCALE=2 SERVICE_MAX_SCALE=200
      else
        export SERVICE_MIN_SCALE=1 SERVICE_MAX_SCALE=15
      fi
      export SERVICE_CPU=2 SERVICE_MEMORY="4Gi" SERVICE_CONCURRENCY=32 SERVICE_PORT=7102
      export SERVICE_ACCOUNT="search-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    hh-rerank-svc)
      if [[ "${ENVIRONMENT}" == "production" ]]; then
        export SERVICE_MIN_SCALE=1 SERVICE_MAX_SCALE=50
      else
        export SERVICE_MIN_SCALE=1 SERVICE_MAX_SCALE=8
      fi
      export SERVICE_CPU=1 SERVICE_MEMORY="2Gi" SERVICE_CONCURRENCY=8 SERVICE_PORT=7103
      export SERVICE_ACCOUNT="rerank-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    hh-evidence-svc)
      if [[ "${ENVIRONMENT}" == "production" ]]; then
        export SERVICE_MIN_SCALE=1 SERVICE_MAX_SCALE=100
      else
        export SERVICE_MIN_SCALE=1 SERVICE_MAX_SCALE=12
      fi
      export SERVICE_CPU=1 SERVICE_MEMORY="2Gi" SERVICE_CONCURRENCY=40 SERVICE_PORT=7104
      export SERVICE_ACCOUNT="evidence-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    hh-eco-svc)
      if [[ "${ENVIRONMENT}" == "production" ]]; then
        export SERVICE_MIN_SCALE=1 SERVICE_MAX_SCALE=50
      else
        export SERVICE_MIN_SCALE=1 SERVICE_MAX_SCALE=8
      fi
      export SERVICE_CPU=1 SERVICE_MEMORY="2Gi" SERVICE_CONCURRENCY=20 SERVICE_PORT=7105
      export SERVICE_ACCOUNT="eco-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    hh-enrich-svc)
      if [[ "${ENVIRONMENT}" == "production" ]]; then
        export SERVICE_MIN_SCALE=1 SERVICE_MAX_SCALE=20
      else
        export SERVICE_MIN_SCALE=1 SERVICE_MAX_SCALE=6
      fi
      export SERVICE_CPU=2 SERVICE_MEMORY="8Gi" SERVICE_CONCURRENCY=4 SERVICE_PORT=7108
      export SERVICE_ACCOUNT="enrich-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    hh-admin-svc)
      if [[ "${ENVIRONMENT}" == "production" ]]; then
        export SERVICE_MIN_SCALE=1 SERVICE_MAX_SCALE=10
      else
        export SERVICE_MIN_SCALE=1 SERVICE_MAX_SCALE=4
      fi
      export SERVICE_CPU=1 SERVICE_MEMORY="2Gi" SERVICE_CONCURRENCY=8 SERVICE_PORT=7106
      export SERVICE_ACCOUNT="admin-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    hh-msgs-svc)
      if [[ "${ENVIRONMENT}" == "production" ]]; then
        export SERVICE_MIN_SCALE=1 SERVICE_MAX_SCALE=50
      else
        export SERVICE_MIN_SCALE=1 SERVICE_MAX_SCALE=8
      fi
      export SERVICE_CPU=1 SERVICE_MEMORY="4Gi" SERVICE_CONCURRENCY=16 SERVICE_PORT=7107
      export SERVICE_ACCOUNT="msgs-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
  esac
}

build_and_push() {
  local service="$1"
  local dockerfile="${SOURCE_ROOT}/services/${service}/Dockerfile"
  local context="${SOURCE_ROOT}/services"
  local image_tag="${REGISTRY}/${service}:${BUILD_TIMESTAMP}"

  if [[ ! -f "${dockerfile}" ]]; then
    echo "Dockerfile not found for ${service}: ${dockerfile}" >&2
    exit 1
  fi

  log "Building image for ${service}-${ENVIRONMENT}"
  docker build "${context}" \
    --file "${dockerfile}" \
    --tag "${service}:local-build" \
    --build-arg BUILD_ENV="${ENVIRONMENT}"

  log "Tagging ${service}:local-build -> ${image_tag}"
  docker tag "${service}:local-build" "${image_tag}"

  log "Pushing ${image_tag}"
  docker push "${image_tag}"

  echo "${image_tag}"
}

replace_service() {
  local service="$1"
  local image_uri="$2"
  local manifest="${CONFIG_ROOT}/${service}.yaml"
  local service_name="${service}-${ENVIRONMENT}"

  if [[ ! -f "${manifest}" ]]; then
    echo "Configuration manifest missing: ${manifest}" >&2
    exit 1
  fi

  set_service_overrides "${service}" "${image_uri}"

  log "Rendering manifest for ${service_name}"
  envsubst <"${manifest}" >"${manifest}.rendered"

  if ! grep -qF "${image_uri}" "${manifest}.rendered"; then
    echo "Rendered manifest for ${service_name} does not reference image ${image_uri}" >&2
    rm -f "${manifest}.rendered"
    exit 1
  fi

  log "Updating Cloud Run service ${service_name}"
  gcloud run services replace "${manifest}.rendered" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --quiet

  rm -f "${manifest}.rendered"
}

post_deploy_validation() {
  local service="$1"
  local service_name="${service}-${ENVIRONMENT}"
  local url
  url="$(gcloud run services describe "${service_name}" --platform=managed --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
  log "Validating health for ${service_name} at ${url}"
  if ! curl -fsSL --max-time 10 "${url}/health" >/dev/null; then
    echo "Health check failed for ${service_name}" >&2
    exit 1
  fi
}

require_tooling
ensure_artifact_repository

declare -A IMAGE_URIS=()

for service in "${SERVICES[@]}"; do
  image_uri="$(build_and_push "${service}")"
  IMAGE_URIS["${service}"]="${image_uri}"
  replace_service "${service}" "${image_uri}"
  post_deploy_validation "${service}"
  log "${service}-${ENVIRONMENT} deployment successful"

done

log "All services deployed successfully"
