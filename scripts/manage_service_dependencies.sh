#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
DEFAULT_CONFIG="${ROOT_DIR}/config/infrastructure/headhunter-ai-0088-production.env"
CONFIG_FILE="${DEFAULT_CONFIG}"
CLI_PROJECT_ID=""
CLI_REGION=""
PROJECT_ID=""
REGION=""
ENVIRONMENT=production
REPORT_FILE=""
DRY_RUN=false
PARALLEL=false
SKIP_BUILD=false
HEALTH_TIMEOUT_SECONDS=300
HEALTH_INITIAL_INTERVAL=10
HEALTH_MAX_INTERVAL=60

usage() {
  cat <<USAGE
Usage: $(basename "$0") [OPTIONS]

Deploys Cloud Run services in dependency order with health validation and rollback support.

Options:
  --project-id ID          Override project id from config
  --region REGION          Override region from config
  --config PATH            Infrastructure config path (default: ${DEFAULT_CONFIG})
  --environment ENV        Deployment environment suffix (default: production)
  --report PATH            Write dependency deployment report to PATH
  --dry-run                Print actions without executing
  --parallel               Deploy independent stages in parallel
  --skip-build             Skip docker build/push (assumes artifacts exist)
  -h, --help               Show this message
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      CLI_PROJECT_ID="$2"
      shift 2
      ;;
    --region)
      CLI_REGION="$2"
      shift 2
      ;;
    --config)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --report)
      REPORT_FILE="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --parallel)
      PARALLEL=true
      shift
      ;;
    --skip-build)
      SKIP_BUILD=true
      shift
      ;;
    --health-timeout)
      HEALTH_TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --health-interval)
      HEALTH_INITIAL_INTERVAL="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "Config file ${CONFIG_FILE} not found" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${CONFIG_FILE}"
CONFIG_PROJECT_ID="${PROJECT_ID:-}"
CONFIG_REGION="${REGION:-}"
PROJECT_ID="${CLI_PROJECT_ID:-${CONFIG_PROJECT_ID}}"
REGION="${CLI_REGION:-${CONFIG_REGION}}"
if [[ -z "${PROJECT_ID}" || -z "${REGION}" ]]; then
  echo "Project id and region must be provided via config or flags" >&2
  exit 1
fi

if [[ ! "${HEALTH_TIMEOUT_SECONDS}" =~ ^[0-9]+$ || ! "${HEALTH_INITIAL_INTERVAL}" =~ ^[0-9]+$ ]]; then
  echo "Health timeout and interval must be positive integers" >&2
  exit 1
fi

if [[ ! "${HEALTH_MAX_INTERVAL}" =~ ^[0-9]+$ ]]; then
  echo "Health max interval must be a positive integer" >&2
  exit 1
fi

if (( HEALTH_TIMEOUT_SECONDS <= 0 || HEALTH_INITIAL_INTERVAL <= 0 || HEALTH_MAX_INTERVAL <= 0 )); then
  echo "Health timeout, interval, and max interval must be greater than zero" >&2
  exit 1
fi

REGISTRY="${REGISTRY:-${ARTIFACT_REGISTRY}}"
if [[ -z "${REGISTRY}" ]]; then
  echo "Artifact registry not configured; set ARTIFACT_REGISTRY in ${CONFIG_FILE}" >&2
  exit 1
fi
SOURCE_ROOT="${ROOT_DIR}"
CONFIG_ROOT="${ROOT_DIR}/config/cloud-run"
BUILD_TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"

log() {
  printf '[deps][%s] %s\n' "${ENVIRONMENT}" "$*" >&2
}

REPORT="Service dependency deployment report\nProject: ${PROJECT_ID}\nRegion: ${REGION}\nEnvironment: ${ENVIRONMENT}\nGenerated: $(date -Is)\n\n"
append_report() {
  REPORT+="$1\n"
}

if [[ "${DRY_RUN}" == true ]]; then
  log "Running in dry-run mode; no commands will be executed"
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "$1 CLI is required" >&2
    exit 1
  }
}

require_command gcloud
require_command docker
require_command envsubst

SERVICES=(
  "hh-embed-svc"
  "hh-rerank-svc"
  "hh-search-svc"
  "hh-evidence-svc"
  "hh-eco-svc"
  "hh-admin-svc"
  "hh-msgs-svc"
  "hh-enrich-svc"
)

STAGE_INDEX=(
  "hh-embed-svc:1"
  "hh-rerank-svc:1"
  "hh-search-svc:2"
  "hh-evidence-svc:3"
  "hh-eco-svc:3"
  "hh-admin-svc:3"
  "hh-msgs-svc:3"
  "hh-enrich-svc:4"
)

declare -A STAGE
for entry in "${STAGE_INDEX[@]}"; do
  svc="${entry%%:*}"
  idx="${entry#*:}"
  STAGE["${svc}"]="${idx}"
done

declare -A DEPENDENCIES=(
  ["hh-search-svc"]="hh-embed-svc hh-rerank-svc"
  ["hh-evidence-svc"]="hh-search-svc"
  ["hh-eco-svc"]="hh-search-svc"
  ["hh-admin-svc"]="hh-search-svc"
  ["hh-msgs-svc"]="hh-search-svc"
  ["hh-enrich-svc"]="hh-embed-svc hh-search-svc"
)

# Track deployed services for rollback
ROLLBACK_STACK=()

die() {
  local message=$1
  trap - ERR || true
  echo "ERROR: ${message}" >&2
  rollback
  exit 1
}

run_cmd() {
  if [[ "${DRY_RUN}" == true ]]; then
    log "DRY-RUN: $*"
    return 0
  fi
  "$@"
}

declare -A SERVICE_URLS
declare -A ID_TOKEN_CACHE

service_url_env_name() {
  case "$1" in
    hh-embed-svc) echo EMBED_SERVICE_URL ;;
    hh-rerank-svc) echo RERANK_SERVICE_URL ;;
    hh-search-svc) echo SEARCH_SERVICE_URL ;;
    hh-evidence-svc) echo EVIDENCE_SERVICE_URL ;;
    hh-eco-svc) echo ECO_SERVICE_URL ;;
    hh-admin-svc) echo ADMIN_SERVICE_URL ;;
    hh-msgs-svc) echo MSGS_SERVICE_URL ;;
    hh-enrich-svc) echo ENRICH_SERVICE_URL ;;
    *) return 1 ;;
  esac
}

export_service_url_var() {
  local service=$1
  local url=$2
  local env_name
  env_name=$(service_url_env_name "${service}" 2>/dev/null) || return 0
  export "${env_name}=${url}"
}

export_dependency_urls() {
  local service
  for service in "${!SERVICE_URLS[@]}"; do
    export_service_url_var "${service}" "${SERVICE_URLS[${service}]}"
  done
}

fetch_identity_token() {
  local audience=$1
  if [[ -n "${ID_TOKEN_CACHE[${audience}]:-}" ]]; then
    printf '%s' "${ID_TOKEN_CACHE[${audience}]}"
    return 0
  fi
  local token
  if ! token=$(gcloud auth print-identity-token --audiences "${audience}" 2>/dev/null); then
    return 1
  fi
  ID_TOKEN_CACHE["${audience}"]="${token}"
  printf '%s' "${token}"
}

build_image() {
  local service=$1
  local context="${SOURCE_ROOT}/services/${service}"
  local dockerfile="${context}/Dockerfile"
  local image_tag="${REGISTRY}/${service}:${BUILD_TIMESTAMP}"
  if [[ "${SKIP_BUILD}" == true ]]; then
    local override_var
    override_var=$(echo "IMAGE_URI_${service}" | tr '[:lower:]' '[:upper:]')
    override_var=${override_var//-/_}
    local override_value="${!override_var:-}"
    if [[ -z "${override_value}" ]]; then
      die "SKIP_BUILD enabled but ${override_var} is not set"
    fi
    echo "${override_value}"
    return 0
  fi
  [[ -f "${dockerfile}" ]] || die "Dockerfile missing for ${service}: ${dockerfile}"
  log "Building ${service}"
  run_cmd docker build "${context}" --tag "${service}:local-build" --build-arg BUILD_ENV="${ENVIRONMENT}"
  log "Tagging image ${image_tag}"
  run_cmd docker tag "${service}:local-build" "${image_tag}"
  log "Pushing ${image_tag}"
  run_cmd docker push "${image_tag}"
  echo "${image_tag}"
}

set_overrides() {
  local service=$1
  local image_uri=$2
  export PROJECT_ID="${PROJECT_ID}"
  export REGION="${REGION}"
  export VPC_CONNECTOR="${VPC_CONNECTOR}"
  export SQL_INSTANCE="${SQL_INSTANCE}"
  export SQL_INSTANCE_MSGS="${SQL_INSTANCE_MSGS}"
  export SQL_DATABASE="${SQL_DATABASE}"
  export SQL_USER_APP="${SQL_USER_APP}"
  export SQL_USER_ADMIN="${SQL_USER_ADMIN}"
  export SQL_USER_ANALYTICS="${SQL_USER_ANALYTICS}"
  export SQL_USER_OPERATIONS="${SQL_USER_OPERATIONS}"
  export SECRET_DB_PRIMARY="${SECRET_DB_PRIMARY}"
  export SECRET_DB_REPLICA="${SECRET_DB_REPLICA}"
  export SECRET_DB_ANALYTICS="${SECRET_DB_ANALYTICS}"
  export SECRET_DB_OPERATIONS="${SECRET_DB_OPERATIONS}"
  export SECRET_REDIS_ENDPOINT="${SECRET_REDIS_ENDPOINT}"
  export SECRET_TOGETHER_AI="${SECRET_TOGETHER_AI}"
  export SECRET_GEMINI_AI="${SECRET_GEMINI_AI}"
  export SECRET_ADMIN_JWT="${SECRET_ADMIN_JWT}"
  export SECRET_WEBHOOK="${SECRET_WEBHOOK}"
  export SECRET_OAUTH_CLIENT="${SECRET_OAUTH_CLIENT}"
  export SECRET_EDGE_CACHE="${SECRET_EDGE_CACHE}"
  export TOGETHER_AI_MODEL="${TOGETHER_AI_MODEL}"
  export TOGETHER_EMBED_MODEL="${TOGETHER_EMBED_MODEL}"
  export TOGETHER_AI_P95_TARGET_MS="${TOGETHER_AI_P95_TARGET_MS}"
  export GEMINI_MODEL="${GEMINI_MODEL}"
  export SERVICE_ENVIRONMENT="${ENVIRONMENT}"
  export SERVICE_PROJECT_ID="${PROJECT_ID}"
  export SERVICE_REGION="${REGION}"
  export SERVICE_IMAGE="${image_uri}"
  export SERVICE_NAME="${service}-${ENVIRONMENT}"
  case "${service}" in
    hh-embed-svc)
      export SERVICE_MIN_SCALE="${EMBED_MIN_INSTANCES}" SERVICE_MAX_SCALE="${EMBED_MAX_INSTANCES}"
      export SERVICE_CPU="${EMBED_CPU}" SERVICE_MEMORY="${EMBED_MEMORY}" SERVICE_CONCURRENCY="${EMBED_CONCURRENCY}" SERVICE_PORT=7101
      export SERVICE_ACCOUNT="${SVC_EMBED}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    hh-search-svc)
      export SERVICE_MIN_SCALE="${SEARCH_MIN_INSTANCES}" SERVICE_MAX_SCALE="${SEARCH_MAX_INSTANCES}"
      export SERVICE_CPU="${SEARCH_CPU}" SERVICE_MEMORY="${SEARCH_MEMORY}" SERVICE_CONCURRENCY="${SEARCH_CONCURRENCY}" SERVICE_PORT=7102
      export SERVICE_ACCOUNT="${SVC_SEARCH}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    hh-rerank-svc)
      export SERVICE_MIN_SCALE="${RERANK_MIN_INSTANCES}" SERVICE_MAX_SCALE="${RERANK_MAX_INSTANCES}"
      export SERVICE_CPU="${RERANK_CPU}" SERVICE_MEMORY="${RERANK_MEMORY}" SERVICE_CONCURRENCY="${RERANK_CONCURRENCY}" SERVICE_PORT=7103
      export SERVICE_ACCOUNT="${SVC_RERANK}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    hh-evidence-svc)
      export SERVICE_MIN_SCALE="${EVIDENCE_MIN_INSTANCES}" SERVICE_MAX_SCALE="${EVIDENCE_MAX_INSTANCES}"
      export SERVICE_CPU="${EVIDENCE_CPU}" SERVICE_MEMORY="${EVIDENCE_MEMORY}" SERVICE_CONCURRENCY="${EVIDENCE_CONCURRENCY}" SERVICE_PORT=7104
      export SERVICE_ACCOUNT="${SVC_EVIDENCE}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    hh-eco-svc)
      export SERVICE_MIN_SCALE="${ECO_MIN_INSTANCES}" SERVICE_MAX_SCALE="${ECO_MAX_INSTANCES}"
      export SERVICE_CPU="${ECO_CPU}" SERVICE_MEMORY="${ECO_MEMORY}" SERVICE_CONCURRENCY="${ECO_CONCURRENCY}" SERVICE_PORT=7105
      export SERVICE_ACCOUNT="${SVC_ECO}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    hh-admin-svc)
      export SERVICE_MIN_SCALE="${ADMIN_MIN_INSTANCES}" SERVICE_MAX_SCALE="${ADMIN_MAX_INSTANCES}"
      export SERVICE_CPU="${ADMIN_CPU}" SERVICE_MEMORY="${ADMIN_MEMORY}" SERVICE_CONCURRENCY="${ADMIN_CONCURRENCY}" SERVICE_PORT=7106
      export SERVICE_ACCOUNT="${SVC_ADMIN}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    hh-msgs-svc)
      export SERVICE_MIN_SCALE="${MSGS_MIN_INSTANCES}" SERVICE_MAX_SCALE="${MSGS_MAX_INSTANCES}"
      export SERVICE_CPU="${MSGS_CPU}" SERVICE_MEMORY="${MSGS_MEMORY}" SERVICE_CONCURRENCY="${MSGS_CONCURRENCY}" SERVICE_PORT=7107
      export SERVICE_ACCOUNT="${SVC_MSGS}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    hh-enrich-svc)
      export SERVICE_MIN_SCALE="${ENRICH_MIN_INSTANCES}" SERVICE_MAX_SCALE="${ENRICH_MAX_INSTANCES}"
      export SERVICE_CPU="${ENRICH_CPU}" SERVICE_MEMORY="${ENRICH_MEMORY}" SERVICE_CONCURRENCY="${ENRICH_CONCURRENCY}" SERVICE_PORT=7108
      export SERVICE_ACCOUNT="${SVC_ENRICH}@${PROJECT_ID}.iam.gserviceaccount.com"
      ;;
    *)
      die "Unknown service ${service}"
      ;;
  esac
  export_dependency_urls
}

render_manifest() {
  local service=$1
  local manifest="${CONFIG_ROOT}/${service}.yaml"
  [[ -f "${manifest}" ]] || die "Manifest ${manifest} not found"
  envsubst <"${manifest}" >"${manifest}.rendered"
  echo "${manifest}.rendered"
}

wait_for_health() {
  local service=$1
  local service_name="${service}-${ENVIRONMENT}"
  local url
  url=$(gcloud run services describe "${service_name}" --platform=managed --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)') || return 1
  local token
  if ! token=$(fetch_identity_token "${url}"); then
    append_report "[FAIL] Unable to obtain identity token for ${service_name}"
    return 1
  fi
  local attempt=1
  local sleep_seconds=${HEALTH_INITIAL_INTERVAL}
  local elapsed=0
  while (( elapsed <= HEALTH_TIMEOUT_SECONDS )); do
    if curl -fsSL --max-time 20 -H "Authorization: Bearer ${token}" "${url}/health" >/dev/null 2>&1; then
      append_report "[PASS] ${service_name} healthy at ${url}"
      SERVICE_URLS["${service}"]="${url}"
      export_service_url_var "${service}" "${url}"
      return 0
    fi
    log "Waiting for ${service_name} health (attempt ${attempt}, next sleep ${sleep_seconds}s)"
    local wait=${sleep_seconds}
    if (( elapsed + wait > HEALTH_TIMEOUT_SECONDS )); then
      wait=$((HEALTH_TIMEOUT_SECONDS - elapsed))
    fi
    (( wait > 0 )) && sleep "${wait}"
    (( elapsed += wait ))
    (( attempt++ ))
    if (( elapsed >= HEALTH_TIMEOUT_SECONDS )); then
      break
    fi
    sleep_seconds=$((sleep_seconds * 2))
    if (( sleep_seconds > HEALTH_MAX_INTERVAL )); then
      sleep_seconds=${HEALTH_MAX_INTERVAL}
    fi
    local refreshed
    if refreshed=$(fetch_identity_token "${url}" 2>/dev/null); then
      token="${refreshed}"
    else
      log "WARN: Failed to refresh identity token for ${service_name}; retrying with previous token"
    fi
  done
  append_report "[FAIL] ${service_name} failed health check"
  return 1
}

backup_revision() {
  local service=$1
  local service_name="${service}-${ENVIRONMENT}"
  local revision
  revision=$(gcloud run services describe "${service_name}" --platform=managed --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.trafficStatuses[0].revisionName)') || true
  if [[ -n "${revision}" && "${revision}" != "-" ]]; then
    ROLLBACK_STACK+=("${service}:${revision}")
  else
    ROLLBACK_STACK+=("${service}:")
  fi
}

perform_replace() {
  local manifest_file=$1
  run_cmd gcloud run services replace "${manifest_file}" --project="${PROJECT_ID}" --region="${REGION}" --quiet
}

cleanup_manifest() {
  local manifest_file=$1
  rm -f "${manifest_file}" || true
}

ensure_dependencies_ready() {
  local service=$1
  local deps=${DEPENDENCIES["${service}"]:-}
  for dep in ${deps}; do
    local dep_url="${SERVICE_URLS["${dep}"]:-}"
    if [[ -z "${dep_url}" ]]; then
      log "Waiting for dependency ${dep} to become healthy before deploying ${service}"
      wait_for_health "${dep}" || die "Dependency ${dep} failed health checks"
      dep_url="${SERVICE_URLS["${dep}"]:-}"
    fi
    if [[ -n "${dep_url}" ]]; then
      export_service_url_var "${dep}" "${dep_url}"
    fi
  done
}

deploy_service() {
  local service=$1
  append_report "Deploying ${service}"
  ensure_dependencies_ready "${service}"
  backup_revision "${service}"
  local image_uri
  image_uri=$(build_image "${service}")
  set_overrides "${service}" "${image_uri}"
  local rendered
  rendered=$(render_manifest "${service}")
  log "Replacing Cloud Run service ${service}-${ENVIRONMENT}"
  if ! perform_replace "${rendered}"; then
    cleanup_manifest "${rendered}"
    return 1
  fi
  if ! wait_for_health "${service}"; then
    cleanup_manifest "${rendered}"
    return 1
  fi
  cleanup_manifest "${rendered}"
  append_report "[OK] ${service}-${ENVIRONMENT} deployed (${image_uri})"
}

rollback() {
  [[ ${#ROLLBACK_STACK[@]} -eq 0 ]] && return
  log "Initiating rollback"
  for ((idx=${#ROLLBACK_STACK[@]}-1; idx>=0; idx--)); do
    entry="${ROLLBACK_STACK[idx]}"
    service="${entry%%:*}"
    revision="${entry#*:}"
    [[ -z "${revision}" ]] && continue
    service_name="${service}-${ENVIRONMENT}"
    log "Restoring ${service_name} to revision ${revision}"
    run_cmd gcloud run services update-traffic "${service_name}" --to-revisions "${revision}=100" --platform=managed --project="${PROJECT_ID}" --region="${REGION}" || true
  done
}

trap 'rollback; exit 1' ERR

CURRENT_STAGE=1
while true; do
  STAGE_SERVICES=()
  for service in "${SERVICES[@]}"; do
    [[ "${STAGE["${service}"]}" == "${CURRENT_STAGE}" ]] || continue
    STAGE_SERVICES+=("${service}")
  done
  [[ ${#STAGE_SERVICES[@]} -eq 0 ]] && break
  log "Starting stage ${CURRENT_STAGE}: ${STAGE_SERVICES[*]}"
  if [[ "${PARALLEL}" == true && ${#STAGE_SERVICES[@]} -gt 1 ]]; then
    declare -A STAGE_PIDS=()
    for svc in "${STAGE_SERVICES[@]}"; do
      (
        deploy_service "${svc}"
      ) &
      STAGE_PIDS["${svc}"]=$!
    done
    STAGE_FAILED=false
    for svc in "${STAGE_SERVICES[@]}"; do
      pid=${STAGE_PIDS["${svc}"]}
      if ! wait "${pid}"; then
        STAGE_FAILED=true
        append_report "[FAIL] ${svc}-${ENVIRONMENT} deployment failed"
      fi
    done
    if [[ "${STAGE_FAILED}" == true ]]; then
      die "Stage ${CURRENT_STAGE} failed"
    fi
  else
    for svc in "${STAGE_SERVICES[@]}"; do
      deploy_service "${svc}"
    done
  fi
  ((CURRENT_STAGE++))
done

trap - ERR
append_report "\nAll services deployed successfully"
if [[ -n "${REPORT_FILE}" ]]; then
  printf '%s\n' "${REPORT}" >"${REPORT_FILE}"
  log "Report written to ${REPORT_FILE}"
else
  printf '%s\n' "${REPORT}"
fi
