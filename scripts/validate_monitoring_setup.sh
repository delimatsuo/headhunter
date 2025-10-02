#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

usage() {
  cat <<USAGE
Usage: $(basename "$0") --project-id PROJECT [options]

Validate that monitoring assets (dashboards, alerts, cost exports, automation)
are configured for the specified environment.

Options:
  --project-id ID          GCP project identifier (required)
  --environment ENV        Environment name (default: production)
  --region REGION          Cloud Run region (default: us-central1)
  --cost-dataset NAME      BigQuery dataset for cost logs (default: ops_observability)
  --cost-table NAME        BigQuery table for cost logs (default: ops_cost_logs)
  --log-level LEVEL        Log verbosity (default: INFO)
  --require-table          Fail if the cost export table has not materialized yet
  -h, --help               Show this message
USAGE
}

log() {
  local level=$1
  shift
  printf '[validate][%s] %s\n' "${level}" "$*"
}

PROJECT_ID=""
ENVIRONMENT="production"
REGION="us-central1"
COST_DATASET="ops_observability"
COST_TABLE="ops_cost_logs"
BIGQUERY_LOCATION="US"
LOG_LEVEL="INFO"
REQUIRE_TABLE=false

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
    --region)
      REGION="$2"
      shift 2
      ;;
    --cost-dataset)
      COST_DATASET="$2"
      shift 2
      ;;
    --cost-table)
      COST_TABLE="$2"
      shift 2
      ;;
    --bigquery-location)
      BIGQUERY_LOCATION="$2"
      shift 2
      ;;
    --log-level)
      LOG_LEVEL="$2"
      shift 2
      ;;
    --require-table)
      REQUIRE_TABLE=true
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

if [[ -z "${PROJECT_ID}" ]]; then
  echo "--project-id is required" >&2
  usage
  exit 1
fi

DASHBOARD_NAMES=(
  "Admin Service Overview"
  "Enrichment Service Overview"
  "MSGS Service Overview"
  "Embedding Service Overview"
  "Search Service Overview"
  "Rerank Service Overview"
  "Evidence Service Overview"
  "ECO Service Overview"
  "Platform Cost Overview"
)

ALERT_NAMES=(
  "SLA - End-to-End Search Latency [${ENVIRONMENT}]"
  "SLA - Rerank Latency [${ENVIRONMENT}]"
  "SLA - Cached Read Latency [${ENVIRONMENT}]"
  "SLA - Error Rate Guardrail [${ENVIRONMENT}]"
  "SLA - Cache Hit Rate [${ENVIRONMENT}]"
  "SLA - Together AI Failures [${ENVIRONMENT}]"
  "SLA - Service Availability [${ENVIRONMENT}]"
  "Cost - Daily Spend Threshold [${ENVIRONMENT}]"
  "Cost - Weekly Spend Threshold [${ENVIRONMENT}]"
  "Cost - Monthly Spend Threshold [${ENVIRONMENT}]"
  "Cost - Spend Spike Detection [${ENVIRONMENT}]"
  "Cost - Tenant Anomaly Detection [${ENVIRONMENT}]"
  "Cost - Together AI Failure Cost [${ENVIRONMENT}]"
)

METRIC_TYPES=(
  "custom.googleapis.com/hh_costs/daily_total_usd"
  "custom.googleapis.com/hh_costs/weekly_total_usd"
  "custom.googleapis.com/hh_costs/monthly_total_usd"
  "custom.googleapis.com/hh_costs/service_cost_usd"
  "custom.googleapis.com/hh_costs/tenant_cost_usd"
  "custom.googleapis.com/hh_costs/api_cost_usd"
  "custom.googleapis.com/hh_costs/cost_per_success_usd"
  "custom.googleapis.com/hh_costs/cost_per_search_usd"
  "custom.googleapis.com/hh_costs/anomaly_score"
  "custom.googleapis.com/hh_costs/cost_spike_ratio"
  "custom.googleapis.com/hh_costs/tenant_anomaly_score"
  "custom.googleapis.com/hh_costs/together_failed_cost_usd"
  "custom.googleapis.com/hh_rerank/together_cost_cents"
)

emit_synthetic_cost_log() {
  local timestamp
  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  local payload
  payload=$(python3 - "${timestamp}" <<'PY'
import json
import sys

payload = {
    "logType": "cost_metric",
    "tenant_id": "monitoring_validation",
    "api_name": "validate_monitoring_setup",
    "cost_cents": 1.0,
    "cost_usd": 0.01,
    "service": "monitoring",
    "source": "monitoring_validation",
    "occurred_at": sys.argv[1]
}

print(json.dumps(payload))
PY
)

  gcloud logging write ops.cost_logs "${payload}" \
    --project="${PROJECT_ID}" \
    --payload-type=json \
    --severity=INFO >/dev/null 2>&1 || log "WARN" "Failed to emit synthetic cost metric"
}

dataset_exists() {
  bq --project_id="${PROJECT_ID}" --location="${BIGQUERY_LOCATION}" show --format=none "${PROJECT_ID}:${COST_DATASET}" >/dev/null 2>&1
}

view_exists() {
  bq --project_id="${PROJECT_ID}" --location="${BIGQUERY_LOCATION}" show --format=none "${PROJECT_ID}:${COST_DATASET}.v_cost_events" >/dev/null 2>&1
}

wait_for_cost_table() {
  local dataset_ref="${PROJECT_ID}:${COST_DATASET}"
  local attempts=0
  local max_attempts=${TABLE_WAIT_ATTEMPTS:-6}
  while (( attempts < max_attempts )); do
    if bq --project_id="${PROJECT_ID}" --location="${BIGQUERY_LOCATION}" ls --format=json "${dataset_ref}" 2>/dev/null | python3 - "${COST_TABLE}" <<'PY'
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
; then
      return 0
    fi
    attempts=$((attempts + 1))
    if (( attempts < max_attempts )); then
      log "INFO" "Waiting for cost export table ${COST_TABLE} to materialize (${attempts}/${max_attempts})"
      sleep 10
    fi
  done
  return 1
}

check_cost_metrics_time_series() {
  local freshness=${COST_METRIC_FRESHNESS_SECONDS:-3600}
  local output
  output=$(gcloud monitoring time-series list \
    --project="${PROJECT_ID}" \
    --filter="metric.type=\"custom.googleapis.com/hh_costs/service_cost_usd\"" \
    --freshness="${freshness}s" \
    --limit=1 \
    --format="value(points)" 2>/dev/null || true)
  if [[ -z "${output}" || "${output}" == "[]" ]]; then
    log "ERROR" "No recent hh_costs/service_cost_usd time series within ${freshness}s"
    ((FAILURES++))
  fi
}

set +e
FAILURES=0

log "${LOG_LEVEL}" "Validating dashboards"
for name in "${DASHBOARD_NAMES[@]}"; do
  if ! gcloud monitoring dashboards list --project="${PROJECT_ID}" --filter="displayName=\"${name}\"" --format="value(name)" | grep -q .; then
    log "ERROR" "Missing dashboard: ${name}"
    ((FAILURES++))
  else
    log "DEBUG" "Dashboard present: ${name}"
  fi
done

log "${LOG_LEVEL}" "Validating alert policies"
for display in "${ALERT_NAMES[@]}"; do
  if ! gcloud alpha monitoring policies list --project="${PROJECT_ID}" --filter="displayName=\"${display}\"" --format="value(name)" | grep -q .; then
    log "ERROR" "Missing alert policy: ${display}"
    ((FAILURES++))
  else
    log "DEBUG" "Alert policy present: ${display}"
  fi
done

log "${LOG_LEVEL}" "Validating cost dataset and sink"
if ! dataset_exists; then
  log "ERROR" "Missing cost dataset ${COST_DATASET}"
  ((FAILURES++))
fi

if ! view_exists; then
  log "ERROR" "Missing cost events view ${COST_DATASET}.v_cost_events"
  ((FAILURES++))
fi

if gcloud logging sinks describe "ops-cost-logs-sink" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  expected_filter='resource.type="cloud_run_revision" AND jsonPayload.logType=("cost_metric","cost_summary")'
  current_filter=$(gcloud logging sinks describe "ops-cost-logs-sink" --project="${PROJECT_ID}" --format="value(filter)" 2>/dev/null || true)
  if [[ "${current_filter}" != "${expected_filter}" ]]; then
    log "ERROR" "Logging sink ops-cost-logs-sink filter mismatch"
    ((FAILURES++))
  fi
else
  log "ERROR" "Missing logging sink ops-cost-logs-sink"
  ((FAILURES++))
fi

if [[ "${REQUIRE_TABLE}" == true ]]; then
  emit_synthetic_cost_log
  if ! wait_for_cost_table; then
    log "ERROR" "Cost export table ${COST_DATASET}.${COST_TABLE} not materialized after retries"
    ((FAILURES++))
  fi
fi

log "${LOG_LEVEL}" "Validating custom metrics"
for metric in "${METRIC_TYPES[@]}"; do
  if ! gcloud monitoring metrics descriptors describe "${metric}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    log "ERROR" "Missing metric descriptor ${metric}"
    ((FAILURES++))
  fi
done

check_cost_metrics_time_series

log "${LOG_LEVEL}" "Validating incident response automation"
if ! python3 "$(dirname "$0")/automated_incident_response.py" sla_violation \
  --project-id "${PROJECT_ID}" --environment "${ENVIRONMENT}" --dry-run >/dev/null 2>&1; then
  log "ERROR" "Incident response automation failed to execute"
  ((FAILURES++))
fi

if [[ ${FAILURES} -gt 0 ]]; then
  log "ERROR" "Validation completed with ${FAILURES} failure(s)."
  exit 1
fi

log "${LOG_LEVEL}" "Monitoring validation succeeded"
