#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Sets up IAM roles, service accounts, and bindings required by the hh-admin-svc
# control plane. This script creates (or updates) least-privilege custom roles
# for refresh orchestration and monitoring, grants runtime accounts Pub/Sub and
# Cloud Run Jobs capabilities, and assigns admin users the appropriate roles for
# invoking the service through API Gateway.
#
# Required environment:
#   PROJECT_ID (e.g., my-gcp-project)
# Optional overrides:
#   ADMIN_GROUP (e.g., group:admin-operators@yourdomain.com)
#   MONITOR_GROUP (e.g., group:admin-readers@yourdomain.com)
#   RUNTIME_SA, SCHEDULER_SA, POSTINGS_TOPIC, PROFILES_TOPIC, POSTINGS_JOB, PROFILES_JOB, REGION
#
# ADMIN_GROUP and MONITOR_GROUP must include a valid IAM member prefix of
# either group: or user:

PROJECT_ID="${PROJECT_ID:-}"
RUNTIME_SA="${RUNTIME_SA:-hh-admin-runtime@${PROJECT_ID}.iam.gserviceaccount.com}"
SCHEDULER_SA="${SCHEDULER_SA:-admin-scheduler@${PROJECT_ID}.iam.gserviceaccount.com}"
ADMIN_GROUP="${ADMIN_GROUP:-group:admin-operators@yourdomain.com}"
MONITOR_GROUP="${MONITOR_GROUP:-group:admin-readers@yourdomain.com}"
POSTINGS_TOPIC="${POSTINGS_TOPIC:-projects/${PROJECT_ID}/topics/postings.refresh.request}"
PROFILES_TOPIC="${PROFILES_TOPIC:-projects/${PROJECT_ID}/topics/profiles.refresh.request}"
POSTINGS_JOB="${POSTINGS_JOB:-projects/${PROJECT_ID}/locations/us-central1/jobs/msgs-refresh-job}"
PROFILES_JOB="${PROFILES_JOB:-projects/${PROJECT_ID}/locations/us-central1/jobs/profiles-refresh-job}"
SERVICE_NAME="${SERVICE_NAME:-hh-admin-svc}"
REGION="${REGION:-us-central1}"
CUSTOM_ROLE_REFRESH_ID="${CUSTOM_ROLE_REFRESH_ID:-HHAdminRefreshOperator}"
CUSTOM_ROLE_MONITOR_ID="${CUSTOM_ROLE_MONITOR_ID:-HHAdminMonitor}" 

if [[ -z "$PROJECT_ID" ]]; then
  echo "PROJECT_ID must be specified" >&2
  exit 1
fi

validate_member_prefix() {
  local value="$1"
  local var_name="$2"
  if [[ ! "$value" =~ ^(group|user):.+@.+$ ]]; then
    echo "${var_name} must include a valid IAM member prefix (group: or user:) followed by an email address" >&2
    exit 1
  fi
}

validate_member_prefix "$ADMIN_GROUP" "ADMIN_GROUP"
validate_member_prefix "$MONITOR_GROUP" "MONITOR_GROUP"

gcloud config set project "$PROJECT_ID" >/dev/null

enable_api() {
  local api="$1"
  if ! gcloud services list --enabled --format="value(config.name)" | grep -q "^${api}$"; then
    echo "Enabling ${api}"
    gcloud services enable "$api"
  fi
}

enable_api iam.googleapis.com
enable_api run.googleapis.com
enable_api pubsub.googleapis.com
enable_api cloudscheduler.googleapis.com
enable_api monitoring.googleapis.com

echo "Ensuring runtime service account ${RUNTIME_SA}"
gcloud iam service-accounts create "${RUNTIME_SA%%@*}" \
  --display-name="hh-admin-svc runtime" \
  --project="$PROJECT_ID" 2>/dev/null || true

echo "Ensuring scheduler service account ${SCHEDULER_SA}"
gcloud iam service-accounts create "${SCHEDULER_SA%%@*}" \
  --display-name="hh-admin-svc scheduler" \
  --project="$PROJECT_ID" 2>/dev/null || true

ensure_custom_role() {
  local role_id="$1"
  local title="$2"
  local description="$3"
  local permissions="$4"

  if gcloud iam roles describe "$role_id" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "Updating custom role $role_id"
    gcloud iam roles update "$role_id" \
      --project="$PROJECT_ID" \
      --title="$title" \
      --description="$description" \
      --permissions="$permissions" \
      --stage=GA >/dev/null
  else
    echo "Creating custom role $role_id"
    gcloud iam roles create "$role_id" \
      --project="$PROJECT_ID" \
      --title="$title" \
      --description="$description" \
      --permissions="$permissions" \
      --stage=GA >/dev/null
  fi
}

ensure_custom_role \
  "$CUSTOM_ROLE_REFRESH_ID" \
  "Admin Refresh Operator" \
  "Allows hh-admin-svc to orchestrate refresh jobs and scheduler tasks." \
  "pubsub.topics.publish,run.jobs.run,run.executions.get,run.executions.list,cloudscheduler.jobs.create,cloudscheduler.jobs.update,cloudscheduler.jobs.delete,cloudscheduler.jobs.get,cloudscheduler.jobs.run,logging.logEntries.create"

ensure_custom_role \
  "$CUSTOM_ROLE_MONITOR_ID" \
  "Admin Monitoring Reader" \
  "Allows hh-admin-svc to query monitoring telemetry and data freshness sources." \
  "monitoring.timeSeries.list,logging.logEntries.list,cloudsql.instances.get,cloudsql.instances.list,datastore.entities.list,datastore.entities.get"

bind_role() {
  local member="$1"
  local role="$2"
  if ! gcloud projects get-iam-policy "$PROJECT_ID" --flatten="bindings[].members" --format="table(bindings.members)" | grep -q "$member"; then
    echo "Granting $role to $member"
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="$member" \
      --role="$role" >/dev/null
  else
    echo "$member already bound to a project role; ensuring $role"
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="$member" \
      --role="$role" >/dev/null || true
  fi
}

echo "Binding runtime permissions"
bind_role "serviceAccount:${RUNTIME_SA}" "projects/${PROJECT_ID}/roles/${CUSTOM_ROLE_REFRESH_ID}"
bind_role "serviceAccount:${RUNTIME_SA}" "projects/${PROJECT_ID}/roles/${CUSTOM_ROLE_MONITOR_ID}"
bind_role "serviceAccount:${RUNTIME_SA}" "roles/logging.logWriter"
bind_role "serviceAccount:${RUNTIME_SA}" "roles/monitoring.metricWriter"

echo "Binding scheduler permissions"
bind_role "serviceAccount:${SCHEDULER_SA}" "roles/cloudscheduler.jobRunner"
bind_role "serviceAccount:${SCHEDULER_SA}" "roles/iam.serviceAccountTokenCreator"
bind_role "serviceAccount:${SCHEDULER_SA}" "roles/pubsub.publisher"

set_resource_binding() {
  local resource="$1"
  local member="$2"
  local role="$3"
  gcloud pubsub topics add-iam-policy-binding "$resource" --member="$member" --role="$role" --project="$PROJECT_ID" >/dev/null
}

set_resource_binding "$POSTINGS_TOPIC" "serviceAccount:${RUNTIME_SA}" "roles/pubsub.publisher"
set_resource_binding "$PROFILES_TOPIC" "serviceAccount:${RUNTIME_SA}" "roles/pubsub.publisher"

echo "Granting Cloud Run job invocation"
for job in "$POSTINGS_JOB" "$PROFILES_JOB"; do
  gcloud run jobs add-iam-policy-binding "$job" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/run.invoker" \
    --region="${REGION}" \
    --project="$PROJECT_ID" >/dev/null
  gcloud run jobs add-iam-policy-binding "$job" \
    --member="serviceAccount:${SCHEDULER_SA}" \
    --role="roles/run.invoker" \
    --region="${REGION}" \
    --project="$PROJECT_ID" >/dev/null
done

echo "Granting API access to operator groups"
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)" --project="$PROJECT_ID" 2>/dev/null || true)
if [[ -n "$SERVICE_URL" ]]; then
  gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
    --member="${ADMIN_GROUP}" \
    --role="roles/run.invoker" \
    --region="$REGION" \
    --project="$PROJECT_ID" >/dev/null

  gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
    --member="${MONITOR_GROUP}" \
    --role="roles/run.invoker" \
    --region="$REGION" \
    --project="$PROJECT_ID" >/dev/null
else
  echo "Service ${SERVICE_NAME} not yet deployed; skipping invoker bindings"
fi

echo "IAM configuration complete"
