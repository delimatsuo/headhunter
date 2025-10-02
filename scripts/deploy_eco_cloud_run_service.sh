#!/usr/bin/env bash

SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Deploys the ECO Cloud Run service with Redis caching, IAM bindings, and monitoring.
#
# Required environment variables or flags:
#   - PROJECT_ID: Google Cloud project id
#   - REGION: (optional, defaults to us-central1)
#   - SERVICE_NAME: (optional, defaults to eco-cloud-run)
#   - DATABASE_SECRET: Secret Manager secret containing the Postgres connection string
#   - REDIS_INSTANCE: Memorystore Redis instance name (will be created if absent)
#
# Usage:
#   PROJECT_ID=my-project scripts/deploy_eco_cloud_run_service.sh \
#     --db-instance projects/my-project/instances/eco-db \
#     --database-secret eco-pg-dsn \
#     --redis-tier standard --traffic 0.5
#
# Flags:
#   --db-instance            Cloud SQL instance connection name (required)
#   --database-secret        Secret Manager secret storing DATABASE_URL (required)
#   --redis-tier             Redis tier (basic or standard), default standard
#   --redis-size-gb          Redis capacity in GB (default 1)
#   --traffic                Traffic split for blue/green (0-1), default 1 (100% new revision)
#   --image                  Override container image tag
#   --skip-build             Skip Cloud Build step (assumes IMAGE env var already set)
#   --help                   Show help

set -euo pipefail

PROJECT_ID=${PROJECT_ID:-}
REGION=${REGION:-us-central1}
SERVICE_NAME=${SERVICE_NAME:-eco-cloud-run}
DATABASE_SECRET=${DATABASE_SECRET:-}
REDIS_INSTANCE=${REDIS_INSTANCE:-eco-redis-cache}
REDIS_TIER="standard"
REDIS_SIZE_GB=1
TRAFFIC="1"
IMAGE=""
SKIP_BUILD="false"
DB_INSTANCE=""

usage() {
  grep '^#' "$0" | cut -c4-
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db-instance)
      DB_INSTANCE="$2"; shift 2 ;;
    --database-secret)
      DATABASE_SECRET="$2"; shift 2 ;;
    --redis-tier)
      REDIS_TIER="$2"; shift 2 ;;
    --redis-size-gb)
      REDIS_SIZE_GB="$2"; shift 2 ;;
    --traffic)
      TRAFFIC="$2"; shift 2 ;;
    --image)
      IMAGE="$2"; shift 2 ;;
    --skip-build)
      SKIP_BUILD="true"; shift ;;
    --help|-h)
      usage; exit 0 ;;
    *)
      echo "Unknown flag $1" >&2
      usage
      exit 1 ;;
  esac
done

if [[ -z "$PROJECT_ID" || -z "$DB_INSTANCE" || -z "$DATABASE_SECRET" ]]; then
  echo "PROJECT_ID, --db-instance, and --database-secret are required" >&2
  exit 1
fi

command -v gcloud >/dev/null || { echo "gcloud CLI is required" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

ensure_apis() {
  log "Enabling required Google Cloud APIs"
  gcloud services enable run.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    compute.googleapis.com \
    monitoring.googleapis.com \
    redis.googleapis.com \
    sqladmin.googleapis.com \
    --project "$PROJECT_ID"
}

build_image() {
  if [[ "$SKIP_BUILD" == "true" ]]; then
    if [[ -z "$IMAGE" ]]; then
      echo "--skip-build supplied but no --image value provided" >&2
      exit 1
    fi
    log "Skipping build; using image $IMAGE"
    return
  fi
  local tag
  tag="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:$(date '+%Y%m%d-%H%M%S')"
  log "Building container image ${tag}"
  gcloud builds submit cloud_run_eco_service --tag "$tag" --project "$PROJECT_ID"
  IMAGE="$tag"
}

deploy_redis() {
  log "Ensuring Memorystore Redis instance ${REDIS_INSTANCE} exists"
  if ! gcloud redis instances describe "$REDIS_INSTANCE" --region "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud redis instances create "$REDIS_INSTANCE" \
      --size="$REDIS_SIZE_GB" \
      --tier="$REDIS_TIER" \
      --region="$REGION" \
      --project="$PROJECT_ID"
  else
    log "Redis instance already exists"
  fi
  REDIS_HOST=$(gcloud redis instances describe "$REDIS_INSTANCE" --region "$REGION" --project "$PROJECT_ID" --format='value(host)')
  REDIS_PORT=$(gcloud redis instances describe "$REDIS_INSTANCE" --region "$REGION" --project "$PROJECT_ID" --format='value(port)')
  export REDIS_URL="redis://${REDIS_HOST}:${REDIS_PORT}"
  log "Using Redis endpoint ${REDIS_URL}"
}

configure_iam() {
  log "Configuring IAM bindings for Cloud Run service account"
  local svc_account
  svc_account="${PROJECT_ID}@appspot.gserviceaccount.com"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${svc_account}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${svc_account}" \
    --role="roles/cloudsql.client" \
    --quiet
}

configure_monitoring() {
  log "Configuring Cloud Monitoring alert policies"
  gcloud monitoring channels list --project "$PROJECT_ID" >/dev/null || true
  # Placeholder for creating dashboards/alerts
  log "Ensure dashboards are configured via Terraform or gcloud monitoring dashboards create"
}

configure_domain() {
  if [[ -n "${CUSTOM_DOMAIN:-}" ]]; then
    log "Mapping custom domain ${CUSTOM_DOMAIN}"
    gcloud beta run domain-mappings describe --project "$PROJECT_ID" --region "$REGION" "${CUSTOM_DOMAIN}" >/dev/null 2>&1 || {
      gcloud beta run domain-mappings create \
        --project "$PROJECT_ID" \
        --region "$REGION" \
        --service "$SERVICE_NAME" \
        --domain "$CUSTOM_DOMAIN"
    }
  fi
}

post_deploy_checks() {
  log "Validating service health endpoint"
  local url
  url=$(gcloud run services describe "$SERVICE_NAME" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')
  if [[ -z "$url" ]]; then
    echo "Failed to obtain service URL" >&2
    exit 1
  fi
  curl --fail --silent --show-error "${url}/health" | jq . >/dev/null && log "Health check passed"
}

deploy_service() {
  local redis_env
  redis_env="ECO_REDIS_URL=${REDIS_URL}"
  local env_vars
  env_vars="${redis_env},ECO_TITLE_ALIGNMENT_ENABLED=false"
  log "Deploying Cloud Run service ${SERVICE_NAME}"
  gcloud run deploy "$SERVICE_NAME" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --image "$IMAGE" \
    --platform managed \
    --no-allow-unauthenticated \
    --add-cloudsql-instances "$DB_INSTANCE" \
    --set-secrets "ECO_PG_DSN=${DATABASE_SECRET}:latest" \
    --set-env-vars "$env_vars" \
    --min-instances 1 \
    --max-instances 5 \
    --cpu 1 \
    --memory 512Mi \
    --ingress internal-and-cloud-load-balancing \
    --timeout 15s

  log "Updating traffic split"
  gcloud run services update-traffic "$SERVICE_NAME" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --to-latest="${TRAFFIC}" \
    --splits "latest=${TRAFFIC}" >/dev/null
}

main() {
  ensure_apis
  build_image
  deploy_redis
  configure_iam
  deploy_service
  configure_monitoring
  configure_domain
  post_deploy_checks
  log "Deployment complete"
  log "Reminder: update Cloud Armor/Firewall rules if necessary and upload SSL certs for domain mappings."
}

main "$@"
