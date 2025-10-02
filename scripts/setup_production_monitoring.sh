#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
DEFAULT_CONFIG="${ROOT_DIR}/config/infrastructure/headhunter-ai-0088-production.env"
CONFIG_FILE="${DEFAULT_CONFIG}"
CLI_PROJECT_ID=""
CLI_REGION=""
ENVIRONMENT=production
DRY_RUN=false
SKIP_UPTIME_CHECKS=false
SKIP_COST_TRACKING=false

# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [OPTIONS]

Set up Cloud Monitoring uptime checks, dashboards, and alerting for production.

Options:
  --project-id ID          Override project id from config
  --region REGION          Override region from config
  --config PATH            Infrastructure config path (default: ${DEFAULT_CONFIG})
  --environment ENV        Environment suffix (default: production)
  --skip-uptime-checks     Skip configuring uptime checks
  --skip-cost-tracking     Skip configuring cost tracking workflows
  --dry-run                Print actions without executing
  -h, --help               Show this message and exit
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
    --skip-uptime-checks)
      SKIP_UPTIME_CHECKS=true
      shift
      ;;
    --skip-cost-tracking)
      SKIP_COST_TRACKING=true
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
  echo "Project id and region must be provided" >&2
  exit 1
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || { echo "$1 CLI is required" >&2; exit 1; }
}

require_command gcloud
require_command python3
require_command bq

log() {
  printf '[monitoring][%s] %s\n' "${ENVIRONMENT}" "$*" >&2
}

if [[ "${DRY_RUN}" == true ]]; then
  log "Running in dry-run mode"
fi

BIGQUERY_LOCATION="${BIGQUERY_LOCATION:-US}"
COST_DATASET="${COST_DATASET:-ops_observability}"
COST_SINK_NAME="${COST_SINK_NAME:-ops-cost-logs-sink}"
COST_TABLE_NAME="${COST_TABLE_NAME:-ops_cost_logs}"
DASHBOARD_DIR="${ROOT_DIR}/config/monitoring"

declare -a DASHBOARD_FILES=(
  "admin-service-dashboard.json"
  "enrich-service-dashboard.json"
  "msgs-service-dashboard.json"
  "embed-service-dashboard.json"
  "search-service-dashboard.json"
  "rerank-service-dashboard.json"
  "evidence-service-dashboard.json"
  "eco-service-dashboard.json"
  "cost-tracking-dashboard.json"
)

declare -a ALERT_POLICY_BUNDLES=(
  "sla-violation-alerts.json"
  "cost-tracking-alerts.json"
)

if [[ "$SKIP_COST_TRACKING" == true ]]; then
  filtered_dashboards=()
  for dashboard in "${DASHBOARD_FILES[@]}"; do
    if [[ "$dashboard" == "cost-tracking-dashboard.json" ]]; then
      continue
    fi
    filtered_dashboards+=("$dashboard")
  done
  DASHBOARD_FILES=()
  if (( ${#filtered_dashboards[@]} )); then
    DASHBOARD_FILES=("${filtered_dashboards[@]}")
  fi

  filtered_bundles=()
  for bundle in "${ALERT_POLICY_BUNDLES[@]}"; do
    if [[ "$bundle" == "cost-tracking-alerts.json" ]]; then
      continue
    fi
    filtered_bundles+=("$bundle")
  done
  ALERT_POLICY_BUNDLES=()
  if (( ${#filtered_bundles[@]} )); then
    ALERT_POLICY_BUNDLES=("${filtered_bundles[@]}")
  fi
fi

fetch_service_url() {
  local base=$1
  gcloud run services describe "${base}-${ENVIRONMENT}" \
    --project="${PROJECT_ID}" --region="${REGION}" --platform=managed \
    --format='value(status.url)' 2>/dev/null || true
}

parse_url() {
  python3 - "$1" <<'PY'
import sys
from urllib.parse import urlparse

url = sys.argv[1]
parsed = urlparse(url)
if not parsed.scheme:
    raise SystemExit("invalid-url")
print(parsed.hostname)
print(parsed.path or "/")
PY
}

run_or_echo() {
  if [[ "${DRY_RUN}" == true ]]; then
    log "DRY-RUN: $*"
  else
    "$@"
  fi
}

dataset_has_binding() {
  local dataset=$1
  local member=$2
  local role=${3:-roles/bigquery.dataEditor}

  if [[ -z "${dataset}" || -z "${member}" ]]; then
    return 1
  fi

  local policy_json
  policy_json=$(bq --project_id="${PROJECT_ID}" get-iam-policy --format=json "${PROJECT_ID}:${dataset}" 2>/dev/null || true)
  if [[ -z "${policy_json}" ]]; then
    return 1
  fi

  if POLICY_JSON="${policy_json}" python3 - "${member}" "${role}" <<'PY'
import json
import os
import sys

member = sys.argv[1]
role = sys.argv[2]

try:
    policy = json.loads(os.environ["POLICY_JSON"])
except (KeyError, json.JSONDecodeError):
    raise SystemExit(1)

for binding in policy.get("bindings", []):
    if binding.get("role") == role and member in binding.get("members", []):
        raise SystemExit(0)

raise SystemExit(1)
PY
  then
    return 0
  else
    return 1
  fi
}

wait_for_cost_table_materialization() {
  local dataset_ref="${PROJECT_ID}:${COST_DATASET}"
  local table="${COST_TABLE_NAME}"
  local attempts=0
  local max_attempts="${TABLE_WAIT_ATTEMPTS:-6}"
  local delay_seconds="${TABLE_WAIT_DELAY_SECONDS:-10}"

  while (( attempts < max_attempts )); do
    if bq --project_id="${PROJECT_ID}" --location="${BIGQUERY_LOCATION}" ls --format=json "${dataset_ref}" 2>/dev/null | \
      python3 - "${table}" <<'PY'
import json
import sys

table_id = sys.argv[1]

try:
    entries = json.load(sys.stdin)
except json.JSONDecodeError:
    raise SystemExit(1)

for item in entries if isinstance(entries, list) else []:
    ref = item.get("tableReference", {}).get("tableId") or item.get("tableId") or item.get("name")
    if ref == table_id:
        raise SystemExit(0)

raise SystemExit(1)
PY
    then
      return 0
    fi

    attempts=$((attempts + 1))
    if (( attempts < max_attempts )); then
      log "Waiting for cost export table ${table} to materialize (${attempts}/${max_attempts})"
      sleep "${delay_seconds}"
    fi
  done

  return 1
}

dashboard_display_name() {
  python3 - "$1" <<'PY'
import json
import sys

with open(sys.argv[1], 'r', encoding='utf-8') as fh:
    data = json.load(fh)

print(data.get('displayName', ''))
PY
}

sync_dashboard() {
  local file=$1
  local path="${DASHBOARD_DIR}/${file}"
  if [[ ! -f "${path}" ]]; then
    log "WARN: dashboard config ${file} missing"
    return
  fi

  local display
  display=$(dashboard_display_name "${path}")
  if [[ -z "${display}" ]]; then
    log "WARN: dashboard ${file} missing displayName"
    return
  fi

  local existing
  existing=$(gcloud monitoring dashboards list --project="${PROJECT_ID}" --filter="displayName=\"${display}\"" --format="value(name)" | head -n1 || true)

  if [[ -z "${existing}" ]]; then
    log "Creating dashboard ${display}"
    run_or_echo gcloud monitoring dashboards create \
      --project="${PROJECT_ID}" \
      --config-from-file="${path}"
    if [[ "${DRY_RUN}" == true ]]; then
      return
    fi
    existing=$(gcloud monitoring dashboards list --project="${PROJECT_ID}" --filter="displayName=\"${display}\"" --format="value(name)" | head -n1 || true)
  else
    log "Updating dashboard ${display}"
    run_or_echo gcloud monitoring dashboards update "${existing}" \
      --project="${PROJECT_ID}" \
      --config-from-file="${path}"
  fi

  if [[ "${DRY_RUN}" == true ]]; then
    log "DRY-RUN: skipping dashboard validation for ${display}"
    return
  fi

  if [[ -n "${existing}" ]]; then
    gcloud monitoring dashboards describe "${existing}" --project="${PROJECT_ID}" >/dev/null 2>&1 && \
      log "Validated dashboard ${display}" || \
      log "ERROR: failed to validate dashboard ${display}"
  else
    log "ERROR: dashboard ${display} not found after deployment"
  fi
}

deploy_dashboards() {
  log "Deploying Cloud Monitoring dashboards"
  for dashboard in "${DASHBOARD_FILES[@]}"; do
    sync_dashboard "${dashboard}"
  done
}

extract_policies_from_bundle() {
  local bundle=$1
  python3 - "${bundle}" "${ENVIRONMENT}" <<'PY'
import json
import os
import sys
import tempfile

bundle_path = sys.argv[1]
environment = sys.argv[2]

with open(bundle_path, 'r', encoding='utf-8') as fh:
    data = json.load(fh)

policies = data.get('policies', [])
for policy in policies:
    policy = dict(policy)
    name = policy.get('displayName', 'Unnamed Policy')
    if f"[{environment}]" not in name:
        policy['displayName'] = f"{name} [{environment}]"
    fd, temp_path = tempfile.mkstemp(prefix='policy-', suffix='.json')
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump(policy, handle)
    print(f"{policy['displayName']}::{temp_path}")
PY
}

sync_policy_file() {
  local display=$1
  local file=$2
  local existing
  existing=$(gcloud alpha monitoring policies list --project="${PROJECT_ID}" --filter="displayName=\"${display}\"" --format="value(name)" | head -n1 || true)
  if [[ -z "${existing}" ]]; then
    log "Creating alert policy ${display}"
    run_or_echo gcloud alpha monitoring policies create \
      --project="${PROJECT_ID}" \
      --policy-from-file="${file}"
  else
    log "Updating alert policy ${display}"
    run_or_echo gcloud alpha monitoring policies update "${existing}" \
      --project="${PROJECT_ID}" \
      --policy-from-file="${file}"
  fi
}

deploy_alert_bundles() {
  log "Deploying bundled alert policies"
  for bundle in "${ALERT_POLICY_BUNDLES[@]}"; do
    local path="${DASHBOARD_DIR}/${bundle}"
    if [[ ! -f "${path}" ]]; then
      log "WARN: alert bundle ${bundle} missing"
      continue
    fi
    while IFS='::' read -r displayName policyFile; do
      [[ -z "${policyFile}" ]] && continue
      sync_policy_file "${displayName}" "${policyFile}"
      rm -f "${policyFile}"
    done < <(extract_policies_from_bundle "${path}")
  done
}

ensure_metric_descriptor() {
  local type=$1
  local display=$2
  local description=$3
  local unit=$4
  local metric_kind=${5:-GAUGE}
  local value_type=${6:-DOUBLE}
  local labels_json=${7:-"[]"}

  local descriptor_json
  descriptor_json=$(gcloud monitoring metrics descriptors describe "${type}" --project="${PROJECT_ID}" --format=json 2>/dev/null || true)
  local describe_status=$?

  if [[ ${describe_status} -eq 0 && -n "${descriptor_json}" ]]; then
    local needs_update
    needs_update=$(DESCRIPTOR_JSON="${descriptor_json}" EXPECTED_UNIT="${unit}" EXPECTED_LABELS="${labels_json}" python3 - <<'PY'
import json
import os

try:
    descriptor = json.loads(os.environ['DESCRIPTOR_JSON'])
except (KeyError, json.JSONDecodeError):
    raise SystemExit(1)
expected_unit = os.environ.get('EXPECTED_UNIT')
try:
    expected_labels = json.loads(os.environ.get('EXPECTED_LABELS', '[]'))
except json.JSONDecodeError:
    expected_labels = []

current_unit = descriptor.get("unit")
current_labels = descriptor.get("labels", [])

def normalize(labels):
    return sorted(({"key": item.get("key"), "valueType": item.get("valueType")} for item in labels if "key" in item), key=lambda item: item["key"])

requires_update = current_unit != expected_unit or normalize(current_labels) != normalize(expected_labels)
print(str(requires_update).lower())
PY
)

    if [[ "${needs_update}" == "true" ]]; then
      log "Recreating metric descriptor ${type} to align with expected unit and labels"
      run_or_echo gcloud monitoring metrics descriptors delete "${type}" --project="${PROJECT_ID}"
      if [[ "${DRY_RUN}" == true ]]; then
        return
      fi
    else
      log "Metric descriptor ${type} already aligned"
      return
    fi
  fi

  local tmp
  tmp=$(mktemp)
  cat >"${tmp}" <<DESCRIPTOR
{
  "type": "${type}",
  "displayName": "${display}",
  "description": "${description}",
  "metricKind": "${metric_kind}",
  "valueType": "${value_type}",
  "unit": "${unit}",
  "labels": ${labels_json}
}
DESCRIPTOR
  log "Creating metric descriptor ${type}"
  run_or_echo gcloud monitoring metrics descriptors create \
    --project="${PROJECT_ID}" \
    --descriptor-file="${tmp}"
  rm -f "${tmp}"
}

ensure_cost_metric_descriptors() {
  log "Ensuring custom cost metric descriptors"
  local cost_labels='[{"key":"service","valueType":"STRING"},{"key":"tenant","valueType":"STRING"}]'
  ensure_metric_descriptor "custom.googleapis.com/hh_costs/daily_total_usd" "Daily Total Cost (USD)" "Aggregated platform daily cost." "1" "GAUGE" "DOUBLE" "${cost_labels}"
  ensure_metric_descriptor "custom.googleapis.com/hh_costs/weekly_total_usd" "Weekly Total Cost (USD)" "Aggregated platform weekly cost." "1" "GAUGE" "DOUBLE" "${cost_labels}"
  ensure_metric_descriptor "custom.googleapis.com/hh_costs/monthly_total_usd" "Monthly Total Cost (USD)" "Aggregated platform monthly cost." "1" "GAUGE" "DOUBLE" "${cost_labels}"
  ensure_metric_descriptor "custom.googleapis.com/hh_costs/service_cost_usd" "Service Cost (USD)" "Per-service cost attribution." "1" "GAUGE" "DOUBLE" "${cost_labels}"
  ensure_metric_descriptor "custom.googleapis.com/hh_costs/tenant_cost_usd" "Tenant Cost (USD)" "Per-tenant cost attribution." "1" "GAUGE" "DOUBLE" "${cost_labels}"
  ensure_metric_descriptor "custom.googleapis.com/hh_costs/api_cost_usd" "API Cost (USD)" "Cost per API invocation." "1" "GAUGE" "DOUBLE" "${cost_labels}"
  ensure_metric_descriptor "custom.googleapis.com/hh_costs/cost_per_success_usd" "Cost per Success (USD)" "Cost per successful request." "1" "GAUGE" "DOUBLE" "${cost_labels}"
  ensure_metric_descriptor "custom.googleapis.com/hh_costs/cost_per_search_usd" "Cost per Search (USD)" "Cost per search request." "1" "GAUGE" "DOUBLE" "${cost_labels}"
  ensure_metric_descriptor "custom.googleapis.com/hh_costs/anomaly_score" "Cost Anomaly Score" "Anomaly score for cost monitoring." "1" "GAUGE" "DOUBLE" "${cost_labels}"
  ensure_metric_descriptor "custom.googleapis.com/hh_costs/cost_spike_ratio" "Cost Spike Ratio" "Relative increase in cost versus baseline." "1" "GAUGE" "DOUBLE" "${cost_labels}"
  ensure_metric_descriptor "custom.googleapis.com/hh_costs/tenant_anomaly_score" "Tenant Cost Anomaly Score" "Anomaly score for tenant spend." "1" "GAUGE" "DOUBLE" "${cost_labels}"
  ensure_metric_descriptor "custom.googleapis.com/hh_costs/together_failed_cost_usd" "Together AI Failed Spend" "Cost attributed to failed Together AI calls." "1" "GAUGE" "DOUBLE" "${cost_labels}"
  ensure_metric_descriptor "custom.googleapis.com/hh_rerank/together_cost_cents" "Rerank Together Cost (cents)" "Together AI spend attributed to rerank workflow." "1" "GAUGE" "DOUBLE" "${cost_labels}"
}

ensure_bigquery_dataset() {
  local dataset=$1
  if bq --project_id="${PROJECT_ID}" --location="${BIGQUERY_LOCATION}" ls "${dataset}" >/dev/null 2>&1; then
    log "BigQuery dataset ${dataset} already exists"
    return
  fi
  log "Creating BigQuery dataset ${dataset}"
  run_or_echo bq --project_id="${PROJECT_ID}" --location="${BIGQUERY_LOCATION}" mk --dataset "${PROJECT_ID}:${dataset}"
}

ensure_cost_logging_sink() {
  local sink_name="${COST_SINK_NAME}"
  local dataset="${COST_DATASET}"
  local expected_filter='resource.type="cloud_run_revision" AND jsonPayload.logType=("cost_metric","cost_summary")'
  local expected_destination="bigquery.googleapis.com/projects/${PROJECT_ID}/datasets/${dataset}"

  log "Ensuring Logging sink ${sink_name} exports cost logs to ${expected_destination}"

  local sink_exists=false
  if gcloud logging sinks describe "${sink_name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    sink_exists=true
  fi

  if [[ "${sink_exists}" == false ]]; then
    log "Creating Logging sink ${sink_name}"
    run_or_echo gcloud logging sinks create "${sink_name}" \
      "${expected_destination}" \
      --project="${PROJECT_ID}" \
      --log-filter="${expected_filter}"
  else
    local current_filter
    current_filter=$(gcloud logging sinks describe "${sink_name}" --project="${PROJECT_ID}" --format='value(filter)' 2>/dev/null || true)
    local current_destination
    current_destination=$(gcloud logging sinks describe "${sink_name}" --project="${PROJECT_ID}" --format='value(destination)' 2>/dev/null || true)
    if [[ "${current_filter}" != "${expected_filter}" || "${current_destination}" != "${expected_destination}" ]]; then
      log "Recreating Logging sink ${sink_name} to enforce expected filter and destination"
      run_or_echo gcloud logging sinks delete "${sink_name}" --project="${PROJECT_ID}"
      run_or_echo gcloud logging sinks create "${sink_name}" \
        "${expected_destination}" \
        --project="${PROJECT_ID}" \
        --log-filter="${expected_filter}"
    else
      log "Logging sink ${sink_name} already matches expected configuration"
    fi
  fi

  if [[ "${DRY_RUN}" == true ]]; then
    log "DRY-RUN: skipping dataset IAM binding for ${sink_name}"
    return
  fi

  if ! gcloud logging sinks describe "${sink_name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    log "ERROR: Logging sink ${sink_name} not found after ensure"
    exit 1
  fi

  local writer
  writer=$(gcloud logging sinks describe "${sink_name}" --project="${PROJECT_ID}" --format='value(writerIdentity)' 2>/dev/null || true)
  if [[ -z "${writer}" ]]; then
    log "ERROR: Unable to determine writer identity for ${sink_name}"
    exit 1
  fi

  if dataset_has_binding "${dataset}" "${writer}" "roles/bigquery.dataEditor"; then
    log "BigQuery dataset ${dataset} already grants roles/bigquery.dataEditor to ${writer}"
  else
    log "Granting roles/bigquery.dataEditor on ${dataset} to ${writer}"
    run_or_echo bq --project_id="${PROJECT_ID}" update \
      --dataset "${PROJECT_ID}:${dataset}" \
      --add_iam_member "roles/bigquery.dataEditor:${writer}"
  fi
}

verify_cost_sink_export() {
  if [[ "${DRY_RUN}" == true ]]; then
    log "DRY-RUN: skipping cost logging sink verification"
    return
  fi

  local sink_name="${COST_SINK_NAME}"
  local dataset="${COST_DATASET}"
  local expected_filter='resource.type="cloud_run_revision" AND jsonPayload.logType=("cost_metric","cost_summary")'
  local expected_destination="bigquery.googleapis.com/projects/${PROJECT_ID}/datasets/${dataset}"

  if ! gcloud logging sinks describe "${sink_name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    log "ERROR: Logging sink ${sink_name} is missing"
    exit 1
  fi

  local current_filter
  current_filter=$(gcloud logging sinks describe "${sink_name}" --project="${PROJECT_ID}" --format='value(filter)' 2>/dev/null || true)
  if [[ "${current_filter}" != "${expected_filter}" ]]; then
    log "ERROR: Logging sink ${sink_name} filter mismatch" "(expected: ${expected_filter}, found: ${current_filter})"
    exit 1
  fi

  local current_destination
  current_destination=$(gcloud logging sinks describe "${sink_name}" --project="${PROJECT_ID}" --format='value(destination)' 2>/dev/null || true)
  if [[ "${current_destination}" != "${expected_destination}" ]]; then
    log "ERROR: Logging sink ${sink_name} destination mismatch" "(expected: ${expected_destination}, found: ${current_destination})"
    exit 1
  fi

  local writer
  writer=$(gcloud logging sinks describe "${sink_name}" --project="${PROJECT_ID}" --format='value(writerIdentity)' 2>/dev/null || true)
  if [[ -z "${writer}" ]]; then
    log "ERROR: Unable to determine writer identity for ${sink_name}"
    exit 1
  fi

  if dataset_has_binding "${dataset}" "${writer}" "roles/bigquery.dataEditor"; then
    log "Verified dataset ${dataset} IAM binding for ${writer}"
  else
    log "ERROR: Missing roles/bigquery.dataEditor on dataset ${dataset} for ${writer}"
    exit 1
  fi

  log "Emitting synthetic cost log to validate export path"
  if ! gcloud logging write ops.cost_logs '{"logType":"cost_metric","api_name":"_probe","cost_cents":1}' \
    --project="${PROJECT_ID}" \
    --payload-type=json \
    --severity=INFO >/dev/null 2>&1; then
    log "WARN: Failed to emit synthetic cost log"
  fi

  if wait_for_cost_table_materialization; then
    log "Confirmed cost export table ${PROJECT_ID}.${dataset}.${COST_TABLE_NAME} is available"
  else
    log "ERROR: Cost export table ${PROJECT_ID}.${dataset}.${COST_TABLE_NAME} did not materialize"
    exit 1
  fi
}


ensure_cost_events_view() {
  local dataset=${COST_DATASET}
  local view_name="v_cost_events"
  local view_ref="${PROJECT_ID}.${dataset}.${view_name}"
  log "Ensuring BigQuery view ${view_ref}"

  local query_file
  query_file=$(mktemp)
  cat >"${query_file}" <<SQL
CREATE OR REPLACE VIEW `${PROJECT_ID}.${dataset}.${view_name}` AS
SELECT
  jsonPayload.tenant_id AS tenant_id,
  jsonPayload.service AS service,
  jsonPayload.api_name AS api_name,
  jsonPayload.provider AS provider,
  jsonPayload.cost_category AS cost_category,
  SAFE_CAST(jsonPayload.cost_cents AS FLOAT64) AS cost_cents,
  SAFE_CAST(jsonPayload.cost_usd AS FLOAT64) AS cost_usd,
  SAFE_CAST(jsonPayload.total_cost_cents AS FLOAT64) AS total_cost_cents,
  SAFE_CAST(jsonPayload.total_cost_cents AS FLOAT64) / 100 AS total_cost_usd,
  jsonPayload.totals_by_category AS totals_by_category,
  jsonPayload.source AS source,
  jsonPayload.request_id AS request_id,
  jsonPayload.trace_id AS trace_id,
  jsonPayload.span_id AS span_id,
  jsonPayload.metadata AS metadata,
  COALESCE(SAFE.TIMESTAMP(jsonPayload.occurred_at), timestamp) AS occurred_at,
  jsonPayload.logType AS log_type,
  timestamp
FROM `${PROJECT_ID}.${dataset}.ops_cost_logs`
WHERE jsonPayload.logType IN ('cost_metric', 'cost_summary');
SQL

  if [[ "${DRY_RUN}" == true ]]; then
    log "DRY-RUN: would create or replace view ${view_ref}"
    cat "${query_file}"
    rm -f "${query_file}"
    return
  fi

  if ! bq --project_id="${PROJECT_ID}" --location="${BIGQUERY_LOCATION}" query \
    --use_legacy_sql=false \
    --format=none \
    < "${query_file}"; then
    log "ERROR" "Failed to create view ${view_ref}"
    rm -f "${query_file}"
    exit 1
  fi

  rm -f "${query_file}"
}

publish_cost_metrics_now() {
  local script_path="${ROOT_DIR}/scripts/publish_cost_metrics.py"
  if [[ ! -f "${script_path}" ]]; then
    log "WARN: cost metrics publisher script missing at ${script_path}; skipping initial publish"
    return
  fi

  if [[ "${DRY_RUN}" == true ]]; then
    log "DRY-RUN: skipping immediate cost metric publication"
    return
  fi

  local lookback="${COST_METRICS_LOOKBACK_MINUTES:-60}"
  if ! python3 "${script_path}" \
    --project-id "${PROJECT_ID}" \
    --dataset "${COST_DATASET}" \
    --table "v_cost_events" \
    --bigquery-location "${BIGQUERY_LOCATION}" \
    --lookback-minutes "${lookback}"; then
    log "WARN: failed to publish initial cost metrics"
  fi
}

ensure_cost_metric_scheduler() {
  local target="${COST_METRICS_PUBLISHER_URL:-}"
  if [[ -z "${target}" ]]; then
    log "WARN: COST_METRICS_PUBLISHER_URL not configured; skipping Cloud Scheduler setup"
    return
  fi

  local job_name="${COST_METRICS_JOB_NAME:-publish-cost-metrics-${ENVIRONMENT}}"
  local schedule="${COST_METRICS_SCHEDULE:-*/15 * * * *}"
  local location="${COST_METRICS_SCHEDULER_LOCATION:-${REGION}}"
  local time_zone="${COST_METRICS_TIME_ZONE:-UTC}"
  local method="${COST_METRICS_HTTP_METHOD:-POST}"
  local body="${COST_METRICS_BODY:-}"
  local service_account="${COST_METRICS_SCHEDULER_SA:-}"

  local command=(gcloud scheduler jobs create http "${job_name}")
  if gcloud scheduler jobs describe "${job_name}" --project="${PROJECT_ID}" --location="${location}" >/dev/null 2>&1; then
    log "Updating Cloud Scheduler job ${job_name}"
    command=(gcloud scheduler jobs update http "${job_name}")
  else
    log "Creating Cloud Scheduler job ${job_name}"
  fi

  command+=(
    "--project=${PROJECT_ID}"
    "--location=${location}"
    "--schedule=${schedule}"
    "--time-zone=${time_zone}"
    "--uri=${target}"
    "--http-method=${method}"
  )

  if [[ -n "${body}" ]]; then
    command+=("--body=${body}")
  fi

  if [[ -n "${service_account}" ]]; then
    command+=(
      "--oauth-service-account-email=${service_account}"
      "--oauth-token-scope=https://www.googleapis.com/auth/cloud-platform"
    )
  fi

  run_or_echo "${command[@]}"
}

format_duration_for_api() {
  local input=$1
  if [[ -z "${input}" ]]; then
    echo "0s"
    return
  fi
  if [[ "${input}" =~ ^([0-9]+)m([0-9]+)s$ ]]; then
    local minutes=${BASH_REMATCH[1]}
    local seconds=${BASH_REMATCH[2]}
    local total=$(( minutes * 60 + seconds ))
    if (( total % 60 != 0 )); then
      total=$(( (total / 60 + 1) * 60 ))
    fi
    if (( total == 0 )); then
      total=60
    fi
    echo "${total}s"
    return
  fi
  if [[ "${input}" =~ ^([0-9]+)s$ ]]; then
    local total=${BASH_REMATCH[1]}
    if (( total % 60 != 0 )); then
      total=$(( (total / 60 + 1) * 60 ))
    fi
    if (( total == 0 )); then
      total=60
    fi
    echo "${total}s"
    return
  fi
  echo "${input}"
}

resolve_notification_channel() {
  local channel=$1
  if [[ -z "${channel}" ]]; then
    echo ""
    return
  fi
  if [[ "${channel}" == projects/* ]]; then
    echo "${channel}"
  else
    echo "projects/${PROJECT_ID}/notificationChannels/${channel}"
  fi
}

create_uptime_check() {
  local name=$1
  local url=$2
  [[ -z "${url}" ]] && return
  local host path
  read -r host path < <(parse_url "${url}")
  local resource_name="${name}-${ENVIRONMENT}-uptime"
  if gcloud monitoring uptime-checks describe "${resource_name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    log "Updating uptime check ${resource_name}"
    run_or_echo gcloud monitoring uptime-checks update http "${resource_name}" \
      --project="${PROJECT_ID}" \
      --host="${host}" \
      --path="${path}" \
      --port=443 \
      --timeout="10s" \
      --period="60s"
  else
    log "Creating uptime check ${resource_name}"
    run_or_echo gcloud monitoring uptime-checks create http "${resource_name}" \
      --project="${PROJECT_ID}" \
      --display-name="${name} ${ENVIRONMENT} health" \
      --host="${host}" \
      --path="${path}" \
      --port=443 \
      --timeout="10s" \
      --period="60s"
  fi
}

configure_alert_policy() {
  local policy_name=$1
  local filter=$2
  local threshold=$3
  local duration=$4
  if [[ -z "${ALERTING_CHANNEL:-}" ]]; then
    log "ERROR: ALERTING_CHANNEL is not configured. Define ALERTING_CHANNEL or set projects/${PROJECT_ID}/notificationChannels/pagerduty_primary."
    exit 1
  fi

  local notification
  notification=$(resolve_notification_channel "${ALERTING_CHANNEL}")
  if [[ -z "${notification}" ]]; then
    log "ERROR: Failed to resolve notification channel from ALERTING_CHANNEL=${ALERTING_CHANNEL}"
    exit 1
  fi
  local display="${policy_name}-${ENVIRONMENT}"
  local policy_id
  policy_id=$(gcloud alpha monitoring policies list --project="${PROJECT_ID}" --filter="displayName=\"${display}\"" --format="value(name)" | head -n1 || true)
  local tmp_file
  tmp_file=$(mktemp)
  local api_duration
  api_duration=$(format_duration_for_api "${duration}")
  local escaped_filter
  escaped_filter=$(python3 -c 'import json, sys; print(json.dumps(sys.argv[1]))' "${filter}")
  cat >"${tmp_file}" <<POLICY
{
  "displayName": "${display}",
  "combiner": "OR",
  "conditions": [
    {
      "displayName": "${policy_name}",
      "conditionThreshold": {
        "filter": ${escaped_filter},
        "comparison": "COMPARISON_GT",
        "thresholdValue": ${threshold},
        "duration": "${api_duration}",
        "trigger": {
          "count": 1
        }
      }
    }
  ],
  "notificationChannels": [
    "${notification}"
  ]
}
POLICY
  if [[ -z "${policy_id}" ]]; then
    log "Creating alert policy ${display}"
    run_or_echo gcloud alpha monitoring policies create \
      --project="${PROJECT_ID}" \
      --policy-from-file="${tmp_file}"
  else
    log "Updating alert policy ${display}"
    run_or_echo gcloud alpha monitoring policies update "${policy_id}" \
      --project="${PROJECT_ID}" \
      --policy-from-file="${tmp_file}"
  fi
  rm -f "${tmp_file}"
}

SERVICE_URL_KEYS=()
SERVICE_URL_VALUES=()
if [[ "$SKIP_UPTIME_CHECKS" == true ]]; then
  log "Skipping uptime checks (--skip-uptime-checks)"
else
  log "Fetching service URLs"
  for svc in hh-embed-svc hh-search-svc hh-rerank-svc hh-evidence-svc hh-eco-svc hh-enrich-svc hh-admin-svc hh-msgs-svc; do
    url=$(fetch_service_url "${svc}")
    if [[ -n "${url}" ]]; then
      SERVICE_URL_KEYS+=("${svc}")
      SERVICE_URL_VALUES+=("${url}")
      log "${svc}-${ENVIRONMENT} -> ${url}"
    else
      log "WARN: ${svc}-${ENVIRONMENT} not deployed; skipping uptime check"
    fi
  done

  log "Configuring uptime checks"
  for idx in "${!SERVICE_URL_KEYS[@]}"; do
    svc="${SERVICE_URL_KEYS[$idx]}"
    url="${SERVICE_URL_VALUES[$idx]}"
    create_uptime_check "${svc}" "${url}"
  done
fi

log "Configuring alerting policies"
configure_alert_policy "cloud-run-latency" "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_latencies\"" "1200" "0m5s"
configure_alert_policy "cloud-run-errors" "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.label.response_code_class!=\"2xx\"" "1" "0m5s"
configure_alert_policy "together-latency" "resource.type=\"global\" AND metric.type=\"custom.googleapis.com/together_ai/latency\"" "350" "0m5s"
configure_alert_policy "redis-connection" "resource.type=\"redis_instance\" AND metric.type=\"redis.googleapis.com/stats/connected_clients\"" "1" "0m1s"

if [[ "$SKIP_COST_TRACKING" == true ]]; then
  log "Skipping cost tracking configuration (--skip-cost-tracking)"
else
  ensure_cost_metric_descriptors
  ensure_bigquery_dataset "${COST_DATASET}"
  ensure_cost_events_view
  ensure_cost_logging_sink
  verify_cost_sink_export
  publish_cost_metrics_now
  ensure_cost_metric_scheduler
fi

deploy_dashboards
deploy_alert_bundles

log "Monitoring setup completed"
