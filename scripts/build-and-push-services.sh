#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

usage() {
  cat <<'USAGE'
Usage: scripts/build-and-push-services.sh [options]

Builds and pushes the Fastify service images to Artifact Registry.

Options:
  --project-id <id>       Google Cloud project ID (overrides config)
  --environment <env>     Deployment environment label (default: production)
  --tag <tag>             Override generated version tag suffix
  --services <list>       Comma-separated services or 'all' (default: all)
  --parallel              Build up to four services in parallel
  --skip-tests            Skip image validation container run
  --dry-run               Show actions without executing
  -h, --help              Show this help message
USAGE
}

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

warn() {
  printf '[%s] WARN: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
}

fail() {
  printf '[%s] ERROR: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Required command '$1' not found in PATH."
  fi
}

PROJECT_ID="${PROJECT_ID:-}"
ENVIRONMENT="${ENVIRONMENT:-production}"
CUSTOM_TAG=""
SERVICES_INPUT="all"
PARALLEL=false
SKIP_TESTS=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      PROJECT_ID="$2"
      shift 2
      ;;
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --tag)
      CUSTOM_TAG="$2"
      shift 2
      ;;
    --services)
      SERVICES_INPUT="$2"
      shift 2
      ;;
    --parallel)
      PARALLEL=true
      shift 1
      ;;
    --skip-tests)
      SKIP_TESTS=true
      shift 1
      ;;
    --dry-run)
      DRY_RUN=true
      shift 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

require_command git
require_command date
require_command mkdir
require_command awk
require_command tr
require_command docker
require_command gcloud
require_command python3
require_command jq

USE_CLOUD_BUILD=false
if ! docker info >/dev/null 2>&1; then
  warn "Docker daemon unavailable; falling back to Cloud Build builds."
  USE_CLOUD_BUILD=true
fi

if [[ "$USE_CLOUD_BUILD" == true ]]; then
  CLOUD_BUILD_CONFIG=$(mktemp)
  cat <<'YAML' >"${CLOUD_BUILD_CONFIG}"
steps:
- name: gcr.io/cloud-builders/docker
  args:
  - build
  - -f
  - services/${_SERVICE}/Dockerfile
  - -t
  - ${_IMAGE_BASE}:${_VERSION_TAG}
  - -t
  - ${_IMAGE_BASE}:${_LATEST_TAG}
  - services
images:
- ${_IMAGE_BASE}:${_VERSION_TAG}
- ${_IMAGE_BASE}:${_LATEST_TAG}
YAML
fi

CONFIG_FILE="config/infrastructure/headhunter-${ENVIRONMENT}.env"
if [[ ! -f "$CONFIG_FILE" ]]; then
  if [[ "$ENVIRONMENT" != "production" ]]; then
    warn "Configuration file ${CONFIG_FILE} not found; falling back to production config."
  fi
  CONFIG_FILE="config/infrastructure/headhunter-production.env"
fi
if [[ ! -f "$CONFIG_FILE" ]]; then
  fail "Unable to locate infrastructure config file."
fi

CLI_PROJECT_ID="$PROJECT_ID"
set -a
source "$CONFIG_FILE"
set +a

if [[ -n "$CLI_PROJECT_ID" ]]; then
  PROJECT_ID="$CLI_PROJECT_ID"
fi

if [[ -z "$PROJECT_ID" ]]; then
  fail "Project ID could not be determined. Provide via --project-id or config."
fi

gcloud config set project "$PROJECT_ID" >/dev/null 2>&1 || true

REGION="${REGION:-us-central1}"
ARTIFACT_REGISTRY="${ARTIFACT_REGISTRY:-${REGION}-docker.pkg.dev/${PROJECT_ID}}"
ARTIFACT_REGISTRY="${ARTIFACT_REGISTRY%/}"
if [[ "$ARTIFACT_REGISTRY" == */services ]]; then
  REGISTRY_REPOSITORY="$ARTIFACT_REGISTRY"
else
  REGISTRY_REPOSITORY="${ARTIFACT_REGISTRY}/services"
fi

TIMESTAMP="$(date -u +'%Y%m%d-%H%M%S')"
GIT_SHA="$(git rev-parse --short HEAD)"
GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
VERSION_TAG="${CUSTOM_TAG:-${GIT_SHA}-${ENVIRONMENT}-${TIMESTAMP}}"
LATEST_TAG="latest-${ENVIRONMENT}"

if [[ "$SERVICES_INPUT" == "all" ]]; then
  SERVICES=(
    hh-embed-svc
    hh-search-svc
    hh-rerank-svc
    hh-evidence-svc
    hh-eco-svc
    hh-admin-svc
    hh-msgs-svc
    hh-enrich-svc
  )
else
  IFS=',' read -r -a SERVICES <<<"$SERVICES_INPUT"
fi

if [[ ${#SERVICES[@]} -eq 0 ]]; then
  fail "No services specified for build."
fi

log "Preparing to build services: ${SERVICES[*]}"
log "Project: ${PROJECT_ID} | Region: ${REGION} | Environment: ${ENVIRONMENT}"
log "Version tag: ${VERSION_TAG} | Latest tag: ${LATEST_TAG}"

if [[ "$DRY_RUN" == true ]]; then
  warn "Dry-run mode enabled; no images will be built or pushed."
fi

log "Ensuring Artifact Registry authentication configured"
if [[ "$DRY_RUN" == false ]]; then
  gcloud auth configure-docker "${REGION}-docker.pkg.dev" >/dev/null 2>&1 || \
    warn "Failed to configure docker auth via gcloud; ensure credentials exist."
fi

DEPLOYMENT_DIR="${PROJECT_ROOT}/.deployment"
BUILD_LOG_DIR="${DEPLOYMENT_DIR}/build-logs"
MANIFEST_DIR="${DEPLOYMENT_DIR}/manifests"
SUMMARY_LOG="${BUILD_LOG_DIR}/build-summary-${TIMESTAMP}.log"
mkdir -p "$BUILD_LOG_DIR" "$MANIFEST_DIR"
TMP_RESULTS_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_RESULTS_DIR"' EXIT

build_service() {
  local service="$1"
  local service_dir="services/${service}"
  local log_file="${BUILD_LOG_DIR}/${service}-${TIMESTAMP}.log"
  local tmp_file="${TMP_RESULTS_DIR}/${service}.json"
  local start_time
  start_time=$(date +%s)

  local image_base="${REGISTRY_REPOSITORY}/${service}"
  local version_tag="${image_base}:${VERSION_TAG}"
  local latest_tag="${image_base}:${LATEST_TAG}"

  log "Building ${service}" | tee -a "$SUMMARY_LOG"
  {
    printf 'Service: %s\n' "$service"
    printf 'Version tag: %s\n' "$version_tag"
    printf 'Latest tag: %s\n' "$latest_tag"
  } >>"$SUMMARY_LOG"

  if [[ "$DRY_RUN" == true ]]; then
    log "[DRY-RUN] Would build and push ${service}"
    cat >"$tmp_file" <<JSON
{
  "service": "${service}",
  "image": "${image_base}",
  "versionTag": "${VERSION_TAG}",
  "latestTag": "${LATEST_TAG}",
  "digest": null,
  "sizeBytes": 0,
  "durationSeconds": 0,
  "status": "dry-run"
}
JSON
    return 0
  fi

  if [[ ! -d "$service_dir" ]]; then
    echo "Service directory ${service_dir} not found" >&2
    return 1
  fi

  local build_status="success"
  local digest=""
  local size_bytes=0
  {
    set -euo pipefail
    if [[ "$USE_CLOUD_BUILD" == true ]]; then
      gcloud builds submit . \
        --project="$PROJECT_ID" \
        --config="$CLOUD_BUILD_CONFIG" \
        --substitutions=_SERVICE="${service}",_IMAGE_BASE="${image_base}",_VERSION_TAG="${VERSION_TAG}",_LATEST_TAG="${LATEST_TAG}" \
        --quiet
      digest=$(gcloud artifacts docker images describe "${image_base}:${VERSION_TAG}" \
        --project="$PROJECT_ID" \
        --format='value(image_summary.digest)' 2>/dev/null || true)
      size_bytes=$(gcloud artifacts docker images describe "${image_base}:${VERSION_TAG}" \
        --project="$PROJECT_ID" \
        --format='value(image_summary.total_size_bytes)' 2>/dev/null || echo 0)
    else
      pushd services >/dev/null
      docker build -f "${service}/Dockerfile" -t "$version_tag" .
      docker tag "$version_tag" "$latest_tag"
      if [[ "$SKIP_TESTS" == false ]]; then
        docker run --rm "$version_tag" node --version
      fi
      docker push "$version_tag"
      docker push "$latest_tag"
      digest=$(docker image inspect --format='{{index .RepoDigests 0}}' "$version_tag" || true)
      size_bytes=$(docker image inspect --format='{{.Size}}' "$version_tag" || echo 0)
      popd >/dev/null
    fi
  } >>"$log_file" 2>&1 || build_status="failed"

  local end_time
  end_time=$(date +%s)
  local duration=$((end_time - start_time))

  if [[ "$build_status" != "success" ]]; then
    warn "Build failed for ${service}; see ${log_file}"
    cat >"$tmp_file" <<JSON
{
  "service": "${service}",
  "image": "${image_base}",
  "versionTag": "${VERSION_TAG}",
  "latestTag": "${LATEST_TAG}",
  "digest": null,
  "sizeBytes": 0,
  "durationSeconds": ${duration},
  "status": "failed",
  "logFile": "${log_file}"
}
JSON
    return 1
  fi

  if [[ -z "$digest" && "$USE_CLOUD_BUILD" != true ]]; then
    digest="$(docker image inspect --format='{{index .RepoDigests 0}}' "$latest_tag" || true)"
  fi
  if [[ -z "$size_bytes" ]]; then
    size_bytes=0
  fi

  cat >"$tmp_file" <<JSON
{
  "service": "${service}",
  "image": "${image_base}",
  "versionTag": "${VERSION_TAG}",
  "latestTag": "${LATEST_TAG}",
  "digest": "${digest}",
  "sizeBytes": ${size_bytes},
  "durationSeconds": ${duration},
  "status": "success",
  "logFile": "${log_file}"
}
JSON
  log "Completed ${service} (${duration}s)"
  return 0
}

PIDS=()
ERRORS=0
CURRENT_JOBS=0
MAX_PARALLEL=4

for service in "${SERVICES[@]}"; do
  if [[ "$PARALLEL" == true && "$DRY_RUN" == false ]]; then
    build_service "$service" &
    PIDS+=("$!")
    ((CURRENT_JOBS++))
    if (( CURRENT_JOBS >= MAX_PARALLEL )); then
      wait -n || ERRORS=$((ERRORS+1))
      CURRENT_JOBS=$((CURRENT_JOBS-1))
    fi
  else
    if ! build_service "$service"; then
      ERRORS=$((ERRORS+1))
    fi
  fi
done

if [[ "$PARALLEL" == true && "$DRY_RUN" == false ]]; then
  for pid in "${PIDS[@]}"; do
    if ! wait "$pid"; then
      ERRORS=$((ERRORS+1))
    fi
  done
fi

if (( ERRORS > 0 )); then
  warn "Encountered ${ERRORS} build failure(s)."
fi

RESULTS_JSON="$(mktemp)"
python3 - <<'PY' "$TMP_RESULTS_DIR" "$RESULTS_JSON"
import json
import os
import sys
from datetime import datetime

dir_path, results_file = sys.argv[1:3]
items = []
for name in sorted(os.listdir(dir_path)):
    if not name.endswith('.json'):
        continue
    with open(os.path.join(dir_path, name), 'r', encoding='utf-8') as fh:
        items.append(json.load(fh))

summary = {
    "buildTimestamp": datetime.utcnow().isoformat() + 'Z',
    "git": {
        "sha": "${GIT_SHA}",
        "branch": "${GIT_BRANCH}"
    },
    "environment": "${ENVIRONMENT}",
    "projectId": "${PROJECT_ID}",
    "region": "${REGION}",
    "versionTag": "${VERSION_TAG}",
    "latestTag": "${LATEST_TAG}",
    "services": items,
}
with open(results_file, 'w', encoding='utf-8') as fh:
    json.dump(summary, fh, indent=2)
PY

MANIFEST_PATH="${MANIFEST_DIR}/build-manifest-${TIMESTAMP}.json"
mv "$RESULTS_JSON" "$MANIFEST_PATH"

SUMMARY_TABLE="$(mktemp)"
python3 - <<'PY' "$MANIFEST_PATH" "$SUMMARY_TABLE"
import json
import sys

manifest_path, table_path = sys.argv[1:3]
with open(manifest_path, 'r', encoding='utf-8') as fh:
    data = json.load(fh)

lines = [
    f"Manifest: {manifest_path}",
    f"Project: {data['projectId']} | Env: {data['environment']} | Version: {data['versionTag']}",
    "",
    f"{'Service':20} {'Status':10} {'Digest':64} {'Size':>10} {'Duration(s)':>12}",
    f"{'-'*20} {'-'*10} {'-'*64} {'-'*10} {'-'*12}",
]
for svc in data['services']:
    digest = svc.get('digest') or 'n/a'
    size_bytes = svc.get('sizeBytes') or 0
    size = size_bytes
    units = ['B','KB','MB','GB','TB']
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    size_str = f"{size:.1f}{units[idx]}"
    lines.append(
        f"{svc['service']:20} {svc['status']:10} {digest[:64]:64} {size_str:>10} {svc.get('durationSeconds', 0):>12}"
    )
with open(table_path, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(lines) + '\n')
PY

cat "$SUMMARY_TABLE" | tee -a "$SUMMARY_LOG"
rm -f "$SUMMARY_TABLE"

if [[ "$USE_CLOUD_BUILD" == true ]]; then
  rm -f "${CLOUD_BUILD_CONFIG}"
fi

if (( ERRORS > 0 )); then
  fail "One or more services failed to build. See logs for details."
fi

log "Build manifest saved to ${MANIFEST_PATH}"
exit 0
