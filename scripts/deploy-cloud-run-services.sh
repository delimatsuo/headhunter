#!/opt/homebrew/bin/bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

usage() {
  cat <<'USAGE'
Usage: scripts/deploy-cloud-run-services.sh [options]

Deploys Cloud Run services using repository YAML templates.

Options:
  --project-id <id>        Google Cloud project to use
  --environment <env>      Deployment environment label (default: production)
  --manifest <path>        Build manifest JSON from build step
  --services <list>        Comma-separated services or 'all' (default: all)
  --sequential             Force sequential deployment (default)
  --skip-validation        Skip readiness and health validation
  --dry-run                Show deployment plan without executing
  -h, --help               Show this help message
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

to_env_key() {
  local name="$1"
  name="${name//-/_}"
  printf '%s' "${name^^}"
}

PROJECT_ID="${PROJECT_ID:-}"
ENVIRONMENT="${ENVIRONMENT:-production}"
BUILD_MANIFEST=""
SERVICES_INPUT="all"
SEQUENTIAL=true
SKIP_VALIDATION=false
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
    --manifest)
      BUILD_MANIFEST="$2"
      shift 2
      ;;
    --services)
      SERVICES_INPUT="$2"
      shift 2
      ;;
    --sequential)
      SEQUENTIAL=true
      shift
      ;;
    --skip-validation)
      SKIP_VALIDATION=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
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

require_command gcloud
require_command jq
require_command python3
require_command curl
require_command git
require_command envsubst

CONFIG_FILE="config/infrastructure/headhunter-${ENVIRONMENT}.env"
if [[ ! -f "$CONFIG_FILE" ]]; then
  if [[ "$ENVIRONMENT" != "production" ]]; then
    warn "Configuration file ${CONFIG_FILE} not found; falling back to production config."
  fi
  CONFIG_FILE="config/infrastructure/headhunter-production.env"
fi
if [[ ! -f "$CONFIG_FILE" ]]; then
  fail "Infrastructure configuration file not found."
fi

CLI_PROJECT_ID="$PROJECT_ID"
set -a
source "$CONFIG_FILE"
# Keep variables exported for envsubst - don't use set +a

if [[ -n "$CLI_PROJECT_ID" ]]; then
  PROJECT_ID="$CLI_PROJECT_ID"
fi

if [[ -z "$PROJECT_ID" ]]; then
  fail "Project ID could not be determined. Provide via --project-id or config."
fi

REGION="${REGION:-us-central1}"
ARTIFACT_REGISTRY="${ARTIFACT_REGISTRY:-${REGION}-docker.pkg.dev/${PROJECT_ID}}"
ARTIFACT_REGISTRY="${ARTIFACT_REGISTRY%/}"
if [[ "$ARTIFACT_REGISTRY" == */services ]]; then
  REGISTRY_REPOSITORY="$ARTIFACT_REGISTRY"
else
  REGISTRY_REPOSITORY="${ARTIFACT_REGISTRY}/services"
fi

declare -a PHASE1=(hh-embed-svc hh-rerank-svc hh-evidence-svc hh-eco-svc hh-msgs-svc)
declare -a PHASE2=(hh-search-svc hh-enrich-svc)
declare -a PHASE3=(hh-admin-svc)
ALL_SERVICES=("${PHASE1[@]}" "${PHASE2[@]}" "${PHASE3[@]}")

if [[ "$SERVICES_INPUT" == "all" ]]; then
  REQUESTED_SERVICES=("${ALL_SERVICES[@]}")
else
  IFS=',' read -r -a REQUESTED_SERVICES <<<"$SERVICES_INPUT"
fi

if [[ ${#REQUESTED_SERVICES[@]} -eq 0 ]]; then
  fail "No services selected for deployment."
fi

SERVICE_SET=()
for svc in "${ALL_SERVICES[@]}"; do
  for req in "${REQUESTED_SERVICES[@]}"; do
    if [[ "$svc" == "$req" ]]; then
      SERVICE_SET+=("$svc")
    fi
  done
done

if [[ ${#SERVICE_SET[@]} -eq 0 ]]; then
  fail "Requested services do not match known service list."
fi

log "Services selected for deployment: ${SERVICE_SET[*]}"
log "Project: ${PROJECT_ID} | Region: ${REGION} | Environment: ${ENVIRONMENT}"

declare -A IMAGE_MAP
if [[ -n "$BUILD_MANIFEST" ]]; then
  if [[ ! -f "$BUILD_MANIFEST" ]]; then
    fail "Build manifest not found at ${BUILD_MANIFEST}."
  fi
  for svc in "${SERVICE_SET[@]}"; do
    image_ref=$(jq -r --arg svc "$svc" '(.services[] | select(.service==$svc) | (.image + ":" + .versionTag)) // empty' "$BUILD_MANIFEST")
    if [[ -z "$image_ref" ]]; then
      warn "Service ${svc} not present in build manifest; using latest tag."
      image_ref="${REGISTRY_REPOSITORY}/${svc}:latest-${ENVIRONMENT}"
    fi
    IMAGE_MAP[$svc]="$image_ref"
  done
else
  for svc in "${SERVICE_SET[@]}"; do
    IMAGE_MAP[$svc]="${REGISTRY_REPOSITORY}/${svc}:latest-${ENVIRONMENT}"
  done
fi

log "Resolved image references for deployment"

DEPLOYMENT_DIR="${PROJECT_ROOT}/.deployment"
DEPLOY_LOG_DIR="${DEPLOYMENT_DIR}/deploy-logs"
MANIFEST_DIR="${DEPLOYMENT_DIR}/manifests"
mkdir -p "$DEPLOYMENT_DIR" "$DEPLOY_LOG_DIR" "$MANIFEST_DIR"
SUMMARY_LOG="${DEPLOY_LOG_DIR}/deploy-summary-$(date -u +'%Y%m%d-%H%M%S').log"

TMP_RESULTS_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_RESULTS_DIR"' EXIT

declare -A SERVICE_INVOKERS=(
  [hh-embed-svc]="search enrich admin",
  [hh-rerank-svc]="search admin",
  [hh-evidence-svc]="search admin",
  [hh-eco-svc]="admin",
  [hh-msgs-svc]="admin",
  [hh-search-svc]="admin",
  [hh-enrich-svc]="admin",
  [hh-admin-svc]="admin"
)

render_service_yaml() {
  local service="$1"
  local image_ref="$2"
  local rendered="$(mktemp)"
  local template="config/cloud-run/${service}.yaml"
  if [[ ! -f "$template" ]]; then
    fail "Cloud Run template ${template} not found."
  fi

  local service_key="$(to_env_key "$service")"
  local default_account_base="${service#hh-}"
  default_account_base="${default_account_base%-svc}"
  local derived_account="${default_account_base}-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
  local account_var="${service_key}_SERVICE_ACCOUNT"
  local service_account="${!account_var:-$derived_account}"

  export SERVICE_ENVIRONMENT="$ENVIRONMENT"
  export SERVICE_PROJECT_ID="$PROJECT_ID"
  export SERVICE_REGION="$REGION"
  export SERVICE_IMAGE="$image_ref"
  export SERVICE_ACCOUNT="$service_account"
  export SERVICE_PORT="${SERVICE_PORT_OVERRIDE:-8080}"

  local max_scale_var="${service_key}_MAX_SCALE"
  local min_scale_var="${service_key}_MIN_SCALE"
  local concurrency_var="${service_key}_CONCURRENCY"
  local cpu_var="${service_key}_CPU"
  local memory_var="${service_key}_MEMORY"

  export SERVICE_MAX_SCALE="${!max_scale_var:-${DEFAULT_SERVICE_MAX_SCALE:-10}}"
  export SERVICE_MIN_SCALE="${!min_scale_var:-${DEFAULT_SERVICE_MIN_SCALE:-0}}"
  export SERVICE_CONCURRENCY="${!concurrency_var:-${DEFAULT_SERVICE_CONCURRENCY:-80}}"
  export SERVICE_CPU="${!cpu_var:-${DEFAULT_SERVICE_CPU:-1}}"
  export SERVICE_MEMORY="${!memory_var:-${DEFAULT_SERVICE_MEMORY:-512Mi}}"

  # Export config variables for envsubst use (secrets, connectors, etc.)
  export VPC_CONNECTOR="${VPC_CONNECTOR:-}"
  export SQL_INSTANCE="${SQL_INSTANCE:-sql-hh-core}"
  export SQL_INSTANCE_MSGS="${SQL_INSTANCE_MSGS:-sql-hh-core}"
  export REDIS_INSTANCE="${REDIS_INSTANCE:-}"
  export SECRET_MANAGER_PREFIX="${SECRET_MANAGER_PREFIX:-}"
  export SECRET_DB_PRIMARY="${SECRET_DB_PRIMARY:-db-primary-password}"
  export SECRET_DB_OPERATIONS="${SECRET_DB_OPERATIONS:-db-operations-password}"
  export SECRET_DB_ANALYTICS="${SECRET_DB_ANALYTICS:-db-analytics-password}"
  export SECRET_TOGETHER_AI="${SECRET_TOGETHER_AI:-together-ai-api-key}"
  export SQL_DATABASE="${SQL_DATABASE:-headhunter}"
  export SQL_USER_APP="${SQL_USER_APP:-hh_app}"
  export SQL_USER_OPERATIONS="${SQL_USER_OPERATIONS:-hh_ops}"
  export SQL_USER_ANALYTICS="${SQL_USER_ANALYTICS:-hh_analytics}"
  export TOGETHER_AI_MODEL="${TOGETHER_AI_MODEL:-meta-llama/Llama-3.2-3B-Instruct-Turbo}"
  export TOGETHER_EMBED_MODEL="${TOGETHER_EMBED_MODEL:-togethercomputer/m2-bert-80M-8k-retrieval}"
  export TOGETHER_AI_P95_TARGET_MS="${TOGETHER_AI_P95_TARGET_MS:-1200}"
  export EMBED_SERVICE_URL="${EMBED_SERVICE_URL:-}"
  export RERANK_SERVICE_URL="${RERANK_SERVICE_URL:-}"
  export EVIDENCE_SERVICE_URL="${EVIDENCE_SERVICE_URL:-}"

  if [[ "$DRY_RUN" == true ]]; then
    cp "$template" "$rendered"
    printf '%s' "$rendered"
    return 0
  fi

  envsubst <"$template" >"$rendered"
  printf '%s' "$rendered"
}

wait_for_service_ready() {
  local service="$1"
  local fq_name="$service-$ENVIRONMENT"
  local attempts=40
  while (( attempts > 0 )); do
    local ready
    ready=$(gcloud run services describe "$fq_name" --platform=managed --region="$REGION" --project="$PROJECT_ID" --format="value(status.conditions[?type='Ready'].status)" 2>/dev/null | tr '\n' ' ' | awk '{print $1}')
    if [[ "$ready" == "True" ]]; then
      return 0
    fi
    sleep 5
    attempts=$((attempts-1))
  done
  return 1
}

ensure_invoker_binding() {
  local service="$1"
  local member="$2"
  if [[ "$DRY_RUN" == true ]]; then
    log "[DRY-RUN] Would grant roles/run.invoker on ${service} to ${member}"
    return 0
  fi
  local policy
  policy=$(gcloud run services get-iam-policy "$service" --platform=managed --region="$REGION" --project="$PROJECT_ID" --format=json)
  if echo "$policy" | jq -e --arg member "$member" '.bindings[]? | select(.role=="roles/run.invoker") | (.members[]? == $member)' >/dev/null; then
    return 0
  fi
  gcloud run services add-iam-policy-binding "$service" \
    --member="$member" \
    --role="roles/run.invoker" \
    --platform=managed \
    --region="$REGION" \
    --project="$PROJECT_ID"
}

deploy_service() {
  local service="$1"
  local image_ref="${IMAGE_MAP[$service]}"
  local log_file="${DEPLOY_LOG_DIR}/${service}-$(date -u +'%Y%m%d-%H%M%S').log"
  local start_time
  start_time=$(date +%s)

  log "Deploying ${service} with image ${image_ref}" | tee -a "$SUMMARY_LOG"

  if [[ "$DRY_RUN" == true ]]; then
    cat >"${TMP_RESULTS_DIR}/${service}.json" <<JSON
{
  "service": "${service}",
  "status": "dry-run",
  "image": "${image_ref}",
  "url": null,
  "durationSeconds": 0,
  "health": null
}
JSON
    return 0
  fi

  local rendered_yaml
  rendered_yaml=$(render_service_yaml "$service" "$image_ref")

  local fq_name="${service}-${ENVIRONMENT}"
  {
    gcloud run services replace "$rendered_yaml" \
      --platform=managed \
      --region="$REGION" \
      --project="$PROJECT_ID" \
      --quiet
  } >>"$log_file" 2>&1 || {
    warn "Deployment failed for ${service}; see ${log_file}"
    cat >"${TMP_RESULTS_DIR}/${service}.json" <<JSON
{
  "service": "${service}",
  "status": "failed",
  "image": "${image_ref}",
  "url": null,
  "durationSeconds": 0,
  "health": null,
  "logFile": "${log_file}"
}
JSON
    rm -f "$rendered_yaml"
    return 1
  }

  rm -f "$rendered_yaml"

  # CRITICAL FIX (Task 78.4): Fail deployment if service doesn't reach ready state
  if [[ "$SKIP_VALIDATION" == false ]]; then
    if ! wait_for_service_ready "$service"; then
      warn "Service ${service} did not reach ready state in time"
      cat >"${TMP_RESULTS_DIR}/${service}.json" <<JSON
{
  "service": "${service}",
  "status": "failed",
  "image": "${image_ref}",
  "url": null,
  "health": "not_ready",
  "logFile": "${log_file}"
}
JSON
      return 1
    fi
  fi

  local url=""
  url=$(gcloud run services describe "$fq_name" --region="$REGION" --project="$PROJECT_ID" --platform=managed --format="value(status.url)" 2>>"$log_file" || true)

  local health_status="skipped"
  if [[ "$SKIP_VALIDATION" == false && -n "$url" ]]; then
    local token
    token=$(gcloud auth print-identity-token 2>>"$log_file" || true)
    if [[ -n "$token" ]]; then
      if curl -fsS -H "Authorization: Bearer ${token}" "$url/health" >/dev/null 2>&1; then
        health_status="pass"
      else
        health_status="fail"
        warn "Health check failed for ${service}; see ${log_file}"
      fi
    else
      warn "Could not obtain identity token for health check"
      health_status="unknown"
    fi
  fi

  local end_time
  end_time=$(date +%s)
  local duration=$((end_time - start_time))

  # CRITICAL FIX (Task 78.4): Overall status depends on readiness AND health
  local overall_status="success"
  if [[ "$health_status" == "fail" ]]; then
    overall_status="failed"
    warn "Service ${service} deployed but health check failed"
  elif [[ "$health_status" == "unknown" && "$SKIP_VALIDATION" == false ]]; then
    overall_status="unknown"
    warn "Service ${service} deployed but health check could not be verified"
  fi

  cat >"${TMP_RESULTS_DIR}/${service}.json" <<JSON
{
  "service": "${service}",
  "status": "${overall_status}",
  "image": "${image_ref}",
  "url": "${url}",
  "durationSeconds": ${duration},
  "health": "${health_status}",
  "logFile": "${log_file}"
}
JSON

  # Ensure gateway service account can invoke
  local gateway_member="serviceAccount:gateway-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
  ensure_invoker_binding "$fq_name" "$gateway_member"

  local invokers="${SERVICE_INVOKERS[$service]:-}"
  if [[ -n "$invokers" ]]; then
    for invoker in $invokers; do
      ensure_invoker_binding "$fq_name" "serviceAccount:${invoker}-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
    done
  fi

  log "Deployed ${service} -> ${url} (${duration}s)"
  return 0
}

PHASES=(PHASE1 PHASE2 PHASE3)
FAILED=0
for phase_var in "${PHASES[@]}"; do
  declare -n phase_services="$phase_var"
  log "Starting deployment phase ${phase_var}"
  for svc in "${phase_services[@]}"; do
    if [[ ! " ${SERVICE_SET[*]} " =~ " ${svc} " ]]; then
      continue
    fi
    if ! deploy_service "$svc"; then
      FAILED=$((FAILED+1))
    fi
  done
done

RESULTS_FILE="$(mktemp)"
python3 - <<'PY' "$TMP_RESULTS_DIR" "$RESULTS_FILE" "$ENVIRONMENT" "$PROJECT_ID" "$REGION"
import json
import os
import sys
from datetime import datetime

dir_path, results_file, environment, project_id, region = sys.argv[1:6]
services = []
for name in sorted(os.listdir(dir_path)):
    if not name.endswith('.json'):
        continue
    with open(os.path.join(dir_path, name), 'r', encoding='utf-8') as fh:
        services.append(json.load(fh))
manifest = {
    "deploymentTimestamp": datetime.utcnow().isoformat() + 'Z',
    "environment": environment,
    "projectId": project_id,
    "region": region,
    "services": services
}
with open(results_file, 'w', encoding='utf-8') as fh:
    json.dump(manifest, fh, indent=2)
PY

MANIFEST_PATH="${MANIFEST_DIR}/deploy-manifest-$(date -u +'%Y%m%d-%H%M%S').json"
mv "$RESULTS_FILE" "$MANIFEST_PATH"

python3 - <<'PY' "$MANIFEST_PATH" "$SUMMARY_LOG"
import json
import sys

manifest_path, summary_log = sys.argv[1:3]
with open(manifest_path, 'r', encoding='utf-8') as fh:
    data = json.load(fh)

lines = [
    f"Deployment manifest: {manifest_path}",
    f"Project: {data['projectId']} | Env: {data['environment']} | Region: {data['region']}",
    "",
    f"{'Service':20} {'Status':10} {'URL':60} {'Health':8} {'Duration(s)':>12}",
    f"{'-'*20} {'-'*10} {'-'*60} {'-'*8} {'-'*12}",
]
for svc in data['services']:
    lines.append(
        f"{svc['service']:20} {svc['status']:10} { (svc.get('url') or 'n/a')[:60]:60} {svc.get('health', 'n/a'):8} {svc.get('durationSeconds', 0):>12}"
    )
with open(summary_log, 'a', encoding='utf-8') as fh:
    fh.write('\n'.join(lines) + '\n')
print('\n'.join(lines))
PY

if (( FAILED > 0 )); then
  fail "Deployment completed with ${FAILED} failure(s)."
fi

log "Deployment manifest saved to ${MANIFEST_PATH}"
exit 0
