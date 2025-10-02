#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Configure service accounts and IAM bindings for the Headhunter Cloud Run stack.
#
# Usage:
#   ./scripts/setup_service_iam.sh [staging|production]
#
# The script creates service accounts for each microservice, assigns the
# principle of least privilege roles, configures API Gateway invoker
# permissions, and ensures audit logging sinks are present.

ENVIRONMENT="${1:-staging}"
if [[ "${ENVIRONMENT}" != "staging" && "${ENVIRONMENT}" != "production" ]]; then
  echo "Environment must be staging or production" >&2
  exit 1
fi

if [[ "${ENVIRONMENT}" == "production" ]]; then
  PROJECT_ID="${PROJECT_ID:-headhunter-ai-0088}"
else
  PROJECT_ID="${PROJECT_ID:-headhunter-staging}"
fi
REGION="${REGION:-us-central1}"
GATEWAY_SA="gateway-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"

REQUIRED_APIS=(
  run.googleapis.com
  iam.googleapis.com
  secretmanager.googleapis.com
  aiplatform.googleapis.com
  sqladmin.googleapis.com
  pubsub.googleapis.com
  cloudresourcemanager.googleapis.com
  serviceusage.googleapis.com
)

log() {
  printf '[iam:%s] %s\n' "${ENVIRONMENT}" "$*"
}

warn() {
  log "WARN: $*"
}

ensure_required_apis() {
  local missing=()
  local enabled
  enabled=$(gcloud services list --enabled --project="${PROJECT_ID}" --format="value(config.name)")
  for api in "${REQUIRED_APIS[@]}"; do
    if ! grep -Fxq "${api}" <<<"${enabled}"; then
      missing+=("${api}")
    fi
  done

  if ((${#missing[@]} > 0)); then
    printf 'Missing required APIs in project %s: %s\n' "${PROJECT_ID}" "${missing[*]}" >&2
    exit 1
  fi

  log "All required APIs enabled"
}

declare -A SERVICE_ACCOUNTS=(
  [hh-embed-svc]="embed"
  [hh-search-svc]="search"
  [hh-rerank-svc]="rerank"
  [hh-evidence-svc]="evidence"
  [hh-eco-svc]="eco"
  [hh-enrich-svc]="enrich"
  [hh-admin-svc]="admin"
  [hh-msgs-svc]="msgs"
)

declare -A SERVICE_ROLES
SERVICE_ROLES[hh-embed-svc]="roles/cloudsql.client roles/redis.viewer roles/aiplatform.user roles/secretmanager.secretAccessor"
SERVICE_ROLES[hh-search-svc]="roles/cloudsql.client roles/redis.viewer roles/secretmanager.secretAccessor"
SERVICE_ROLES[hh-rerank-svc]="roles/redis.viewer roles/secretmanager.secretAccessor"
SERVICE_ROLES[hh-evidence-svc]="roles/cloudsql.client roles/datastore.viewer roles/redis.viewer roles/secretmanager.secretAccessor"
SERVICE_ROLES[hh-eco-svc]="roles/cloudsql.client roles/datastore.viewer roles/redis.viewer roles/secretmanager.secretAccessor"
SERVICE_ROLES[hh-enrich-svc]="roles/cloudsql.client roles/datastore.user roles/pubsub.publisher roles/pubsub.subscriber roles/secretmanager.secretAccessor"
SERVICE_ROLES[hh-admin-svc]="roles/cloudsql.client roles/pubsub.publisher roles/pubsub.subscriber roles/monitoring.viewer roles/logging.logWriter roles/secretmanager.secretAccessor"
SERVICE_ROLES[hh-msgs-svc]="roles/cloudsql.client roles/redis.viewer roles/secretmanager.secretAccessor"

ensure_service_account() {
  local service="$1"
  local shorthand="$2"
  local account="${shorthand}-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "${account}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${shorthand}-${ENVIRONMENT}" \
      --project="${PROJECT_ID}" \
      --display-name "${service} (${ENVIRONMENT})"
    local attempt=0
    until gcloud iam service-accounts describe "${account}" --project="${PROJECT_ID}" >/dev/null 2>&1; do
      ((attempt++))
      if (( attempt > 10 )); then
        warn "Service account ${account} not visible after creation"
        break
      fi
      sleep 2
    done
  fi
  echo "${account}"
}

bind_project_roles() {
  local account="$1"
  shift
  for role in "$@"; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="serviceAccount:${account}" \
      --role="${role}" \
      --quiet
  done
}

declare -A RUN_SERVICE_CACHE=()

run_service_exists() {
  local service_name="$1"
  if [[ -n ${RUN_SERVICE_CACHE[$service_name]+x} ]]; then
    return "${RUN_SERVICE_CACHE[$service_name]}"
  fi
  if gcloud run services describe "$service_name" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --platform=managed >/dev/null 2>&1; then
    RUN_SERVICE_CACHE["$service_name"]=0
    return 0
  fi
  RUN_SERVICE_CACHE["$service_name"]=1
  return 1
}

add_invoker_binding() {
  local service_name="$1"
  local member="$2"
  if ! run_service_exists "$service_name"; then
    warn "Skipping roles/run.invoker binding for ${service_name}; deploy service then rerun IAM setup"
    return 0
  fi
  gcloud run services add-iam-policy-binding "$service_name" \
    --member="$member" \
    --role="roles/run.invoker" \
    --platform=managed \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --quiet
}

bind_gateway_invoker() {
  local service="$1"
  local service_name="${service}-${ENVIRONMENT}"
  add_invoker_binding "$service_name" "serviceAccount:${GATEWAY_SA}"
}

bind_service_to_service() {
  # Allow search and enrich services to invoke downstream Cloud Run.
  local embed_account="embed-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
  local search_account="search-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
  local enrich_account="enrich-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
  local embed_service="hh-embed-svc-${ENVIRONMENT}"
  local search_service="hh-search-svc-${ENVIRONMENT}"
  local rerank_service="hh-rerank-svc-${ENVIRONMENT}"

  add_invoker_binding "$embed_service" "serviceAccount:${search_account}"
  add_invoker_binding "$rerank_service" "serviceAccount:${search_account}"
  add_invoker_binding "$embed_service" "serviceAccount:${enrich_account}"
  add_invoker_binding "$search_service" "serviceAccount:${enrich_account}"
  add_invoker_binding "$rerank_service" "serviceAccount:${enrich_account}"
  add_invoker_binding "$search_service" "serviceAccount:${GATEWAY_SA}"
}

configure_audit_logging() {
  local sink_name="hh-audit-${ENVIRONMENT}"
  if ! gcloud logging sinks describe "${sink_name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud logging sinks create "${sink_name}" \
      "storage.googleapis.com/headhunter-audit-${ENVIRONMENT}" \
      --log-filter='resource.type="cloud_run_revision"' \
      --project="${PROJECT_ID}"
  fi
  gcloud logging metrics create "hh-security-events-${ENVIRONMENT}" \
    --project="${PROJECT_ID}" \
    --description="Security alerts for Headhunter services" \
    --filter='resource.type="cloud_run_revision" AND severity>=WARNING' \
    >/dev/null 2>&1 || true
}

ensure_required_apis

declare -A RESOLVED_ACCOUNTS=()
for service in "${!SERVICE_ACCOUNTS[@]}"; do
  shorthand="${SERVICE_ACCOUNTS[${service}]}"
  account="$(ensure_service_account "${service}" "${shorthand}")"
  RESOLVED_ACCOUNTS["${service}"]="${account}"
  roles=(${SERVICE_ROLES[${service}]})
  bind_project_roles "${account}" "${roles[@]}"
  bind_gateway_invoker "${service}"
  log "configured ${service}-${ENVIRONMENT} (${account})"
done

bind_service_to_service
log "Configured service-to-service invocation bindings"
configure_audit_logging
log "Audit logging configuration verified"

echo "IAM configuration completed for ${ENVIRONMENT}"
