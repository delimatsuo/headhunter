#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/setup-monitoring-and-alerting.sh [options]

Master orchestration for production monitoring setup. Runs dashboard, alert, uptime, and cost tracking
workflows and emits a consolidated manifest.

Options:
  --project-id <id>              Google Cloud project ID (overrides config)
  --environment <env>            Target environment (default: production)
  --region <region>              Google Cloud region (overrides config)
  --notification-channels <ids>  Comma-separated list of notification channel IDs
  --config <path>                Infrastructure env file (default: config/infrastructure/headhunter-production.env)
  --output-dir <path>            Directory for setup artifacts (default: .monitoring/setup-<timestamp>)
  --dry-run                      Run in preview mode (skip apply flags)
  --skip-dashboards              Skip dashboard setup step
  --skip-alerts                  Skip alert policy setup step
  --skip-uptime-checks           Skip uptime checks within monitoring setup
  --skip-cost-tracking           Skip cost tracking setup within monitoring setup
  --continue-on-error            Do not exit immediately on failure; log and continue
  --help                         Show this help message
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
    fail "Required command '$1' not found in PATH"
  fi
}

run_or_continue() {
  local description="$1"
  shift
  local logfile="$1"
  shift
  local cmd=("$@")

  log "Executing ${description}"
  {
    printf 'Command: %s\n' "${cmd[*]}"
    printf 'Started: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  } >>"$logfile"

  if ! "${cmd[@]}" >>"$logfile" 2>&1; then
    warn "${description} failed (see ${logfile})"
    WARNINGS+=("${description} failed; see ${logfile}")
    if [[ -n "${WARNINGS_FILE:-}" ]]; then
      printf '%s\n' "${description} failed; see ${logfile}" >>"$WARNINGS_FILE"
    fi
    if [[ "$CONTINUE_ON_ERROR" == true ]]; then
      return 1
    fi
    fail "${description} failed"
  fi
  printf 'Completed: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" >>"$logfile"
  return 0
}

PROJECT_ID=""
ENVIRONMENT="production"
REGION=""
NOTIFICATION_CHANNELS=""
CONFIG_FILE=""
OUTPUT_DIR=""
DRY_RUN=false
SKIP_DASHBOARDS=false
SKIP_ALERTS=false
SKIP_UPTIME_CHECKS=false
SKIP_COST_TRACKING=false
CONTINUE_ON_ERROR=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      PROJECT_ID="$2"; shift 2 ;;
    --environment)
      ENVIRONMENT="$2"; shift 2 ;;
    --region)
      REGION="$2"; shift 2 ;;
    --notification-channels)
      NOTIFICATION_CHANNELS="$2"; shift 2 ;;
    --config)
      CONFIG_FILE="$2"; shift 2 ;;
    --output-dir)
      OUTPUT_DIR="$2"; shift 2 ;;
    --dry-run)
      DRY_RUN=true; shift ;;
    --skip-dashboards)
      SKIP_DASHBOARDS=true; shift ;;
    --skip-alerts)
      SKIP_ALERTS=true; shift ;;
    --skip-uptime-checks)
      SKIP_UPTIME_CHECKS=true; shift ;;
    --skip-cost-tracking)
      SKIP_COST_TRACKING=true; shift ;;
    --continue-on-error)
      CONTINUE_ON_ERROR=true; shift ;;
    --help|-h)
      usage; exit 0 ;;
    *)
      fail "Unknown argument: $1" ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Enforce canonical repository path guard
source "${SCRIPT_DIR}/utils/repo_guard.sh"

require_command gcloud
require_command python3
require_command jq
require_command bq

CONFIG_FILE="${CONFIG_FILE:-${PROJECT_ROOT}/config/infrastructure/headhunter-production.env}"
if [[ ! -f "$CONFIG_FILE" ]]; then
  fail "Configuration file ${CONFIG_FILE} not found"
fi

set -a
source "$CONFIG_FILE"
set +a

if [[ -n "$PROJECT_ID" ]]; then
  PROJECT_ID="$PROJECT_ID"
else
  PROJECT_ID="${PROJECT_ID:-${PROJECT_ID:-}}"
fi
if [[ -z "$PROJECT_ID" ]]; then
  fail "Project ID is required"
fi

if [[ -n "$REGION" ]]; then
  REGION="$REGION"
else
  REGION="${REGION:-us-central1}"
fi

TIMESTAMP="$(date -u +'%Y%m%d-%H%M%S')"
if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="${PROJECT_ROOT}/.monitoring/setup-${TIMESTAMP}"
else
  OUTPUT_DIR="${OUTPUT_DIR}"
fi
REPORTS_DIR="${OUTPUT_DIR}/reports"
LOGS_DIR="${OUTPUT_DIR}/logs"
mkdir -p "$OUTPUT_DIR" "$REPORTS_DIR" "$LOGS_DIR"

log "Writing monitoring artifacts to ${OUTPUT_DIR}"

ACTIVE_ACCOUNT=$(gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>/dev/null || true)
if [[ -z "$ACTIVE_ACCOUNT" ]]; then
  fail "No active gcloud account found. Run 'gcloud auth login'."
fi

log "Using project ${PROJECT_ID} (environment ${ENVIRONMENT}, region ${REGION}) as ${ACTIVE_ACCOUNT}"

# Validate required commands availability
WARNINGS=()
WARNINGS_FILE="${OUTPUT_DIR}/warnings.txt"
: >"$WARNINGS_FILE"

for cmd in gcloud python3 jq bq; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    WARNINGS+=("${cmd} not available; certain steps may fail")
    printf '%s\n' "${cmd} not available; certain steps may fail" >>"$WARNINGS_FILE"
  fi
done

# Ensure Cloud Run services exist
SERVICES=(hh-embed-svc hh-rerank-svc hh-evidence-svc hh-eco-svc hh-msgs-svc hh-search-svc hh-enrich-svc hh-admin-svc)
SERVICE_URL_MAP_FILE="${OUTPUT_DIR}/service-urls.json"
: >"$SERVICE_URL_MAP_FILE"

SERVICE_WARNINGS=()
SERVICE_URLS_JSON="[]"
for svc in "${SERVICES[@]}"; do
  NAME="${svc}-${ENVIRONMENT}"
  URL="$(gcloud run services describe "$NAME" --platform=managed --region "$REGION" --project "$PROJECT_ID" --format='value(status.url)' 2>/dev/null || true)"
  if [[ -z "$URL" ]]; then
    warn "Cloud Run service ${NAME} not found or missing URL"
    SERVICE_WARNINGS+=("Service ${NAME} missing or no URL")
    continue
  fi
  SERVICE_URLS_JSON=$(python3 - <<'PY' "$SERVICE_URLS_JSON" "$svc" "$URL" "$ENVIRONMENT"
import json
import sys
current = json.loads(sys.argv[1])
current.append({'service': sys.argv[2], 'environment': sys.argv[4], 'url': sys.argv[3]})
print(json.dumps(current))
PY
  )

done
printf '%s' "$SERVICE_URLS_JSON" >"$SERVICE_URL_MAP_FILE"

if (( ${#SERVICE_WARNINGS[@]} )); then
  WARNINGS+=("$(printf 'Service discovery issues: %s' "${SERVICE_WARNINGS[*]}")")
  printf '%s\n' "Service discovery issues: ${SERVICE_WARNINGS[*]}" >>"$WARNINGS_FILE"
fi

# Data accumulators
DASHBOARD_DATA_FILE="${OUTPUT_DIR}/dashboards.jsonl"
ALERT_DATA_FILE="${OUTPUT_DIR}/alert-policies.jsonl"
UPTIME_DATA_FILE="${OUTPUT_DIR}/uptime-checks.jsonl"
COST_DATA_FILE="${OUTPUT_DIR}/cost-tracking.json"
VALIDATION_FILE="${OUTPUT_DIR}/validation-results.jsonl"
: >"$DASHBOARD_DATA_FILE"
: >"$ALERT_DATA_FILE"
: >"$UPTIME_DATA_FILE"
: >"$VALIDATION_FILE"

touch "$COST_DATA_FILE"

run_dashboards() {
  if [[ "$SKIP_DASHBOARDS" == true ]]; then
    log "Skipping dashboard setup"
    return
  fi
  local marker="${REPORTS_DIR}/.dashboards-before"
  touch "$marker"
  local log_file="${LOGS_DIR}/dashboards.log"
  local cmd=(python3 "${SCRIPT_DIR}/setup_cloud_monitoring_dashboards.py" --project "$PROJECT_ID" --prefix "Headhunter Production" --reports-dir "$REPORTS_DIR" --reconcile)
  if [[ "$DRY_RUN" != true ]]; then
    cmd+=(--apply)
  else
    cmd+=(--dry-run)
  fi
  run_or_continue "Cloud Monitoring dashboard setup" "$log_file" "${cmd[@]}" || return
  while IFS= read -r -d '' report; do
    if [[ ! -s "$report" ]]; then
      continue
    fi
    jq -c '.dashboards[]? // empty' "$report" 2>/dev/null | while IFS= read -r line; do
      local name id
      name=$(echo "$line" | jq -r '.displayName // .name')
      id=$(echo "$line" | jq -r '.name // empty')
      if [[ -z "$id" ]]; then
        continue
      fi
      local dashboard_id
      dashboard_id="$(basename "$id")"
      local url="https://console.cloud.google.com/monitoring/dashboards/custom/${dashboard_id}?project=${PROJECT_ID}"
      echo "$(jq -n --arg name "$name" --arg resource "$id" --arg url "$url" '{name:$name, resourceName:$resource, url:$url}')" >>"$DASHBOARD_DATA_FILE"
    done
  done < <(find "$REPORTS_DIR" -maxdepth 1 -type f -name '*dashboard*.json' -newer "$marker" -print0)
}

run_alerts() {
  if [[ "$SKIP_ALERTS" == true ]]; then
    log "Skipping alert policy setup"
    return
  fi
  local marker="${REPORTS_DIR}/.alerts-before"
  touch "$marker"
  local log_file="${LOGS_DIR}/alerts.log"
  local cmd=(python3 "${SCRIPT_DIR}/setup_production_alerting.py" --project "$PROJECT_ID" --prefix "Headhunter Production" --reports-dir "$REPORTS_DIR" --reconcile)
  if [[ -n "$NOTIFICATION_CHANNELS" ]]; then
    cmd+=(--channels "$NOTIFICATION_CHANNELS")
  fi
  if [[ "$DRY_RUN" != true ]]; then
    cmd+=(--apply)
  else
    cmd+=(--dry-run)
  fi
  run_or_continue "Alert policy setup" "$log_file" "${cmd[@]}" || return
  while IFS= read -r -d '' report; do
    if [[ ! -s "$report" ]]; then
      continue
    fi
    jq -c '.policies[]? // empty' "$report" 2>/dev/null | while IFS= read -r line; do
      local name id severity channels
      name=$(echo "$line" | jq -r '.displayName // .name')
      id=$(echo "$line" | jq -r '.name // empty')
      severity=$(echo "$line" | jq -r '.severity // empty')
      channels=$(echo "$line" | jq -c '.notificationChannels // []')
      [[ -z "$id" ]] && continue
      echo "$(jq -n --arg name "$name" --arg resource "$id" --arg severity "$severity" --argjson channels "$channels" '{name:$name, resourceName:$resource, severity:$severity, channels:$channels}')" >>"$ALERT_DATA_FILE"
    done
  done < <(find "$REPORTS_DIR" -maxdepth 1 -type f -name '*alert*.json' -newer "$marker" -print0)
}

run_monitoring_setup() {
  local log_file="${LOGS_DIR}/monitoring-orchestration.log"
  local cmd=("${SCRIPT_DIR}/setup_production_monitoring.sh" --project-id "$PROJECT_ID" --region "$REGION" --environment "$ENVIRONMENT" --config "$CONFIG_FILE")
  if [[ "$DRY_RUN" == true ]]; then
    cmd+=(--dry-run)
  fi
  if [[ "$SKIP_UPTIME_CHECKS" == true ]]; then
    cmd+=(--skip-uptime-checks)
  fi
  if [[ "$SKIP_COST_TRACKING" == true ]]; then
    cmd+=(--skip-cost-tracking)
  fi
  run_or_continue "Comprehensive monitoring setup" "$log_file" "${cmd[@]}" || return
}

run_gateway_setup() {
  local log_file="${LOGS_DIR}/gateway-monitoring.log"
  local cmd=("${SCRIPT_DIR}/setup_gateway_monitoring_complete.sh" --project "$PROJECT_ID" --environment "$ENVIRONMENT" --region "$REGION" --gateway-id "headhunter-api-gateway-${ENVIRONMENT}")
  if [[ -n "$NOTIFICATION_CHANNELS" ]]; then
    cmd+=(--alert-channels "$NOTIFICATION_CHANNELS")
  fi
  if [[ "$DRY_RUN" == true ]]; then
    cmd+=(--dry-run)
  fi
  run_or_continue "Gateway monitoring setup" "$log_file" "${cmd[@]}" || return
}

collect_uptime_from_reports() {
  find "$REPORTS_DIR" -maxdepth 1 -type f -name '*uptime*.json' -print0 | while IFS= read -r -d '' report; do
    jq -c '.uptimeChecks[]? // empty' "$report" 2>/dev/null | while IFS= read -r line; do
      echo "$line" >>"$UPTIME_DATA_FILE"
    done
  done
}

collect_cost_from_reports() {
  local latest
  latest=$(find "$REPORTS_DIR" -maxdepth 1 -type f -name '*cost*.json' -print0 | xargs -0 ls -1t 2>/dev/null | head -n1 || true)
  if [[ -n "$latest" ]]; then
    cp "$latest" "$COST_DATA_FILE"
  fi
}

validate_resources() {
  local tmpfile
  tmpfile="$(mktemp)"
  printf '[]' >"$tmpfile"
  if [[ -s "$DASHBOARD_DATA_FILE" ]]; then
    while IFS= read -r line; do
      local resource
      resource=$(echo "$line" | jq -r '.resourceName')
      if [[ -z "$resource" ]]; then
        continue
      fi
      if gcloud monitoring dashboards describe "$resource" --project "$PROJECT_ID" >/dev/null 2>&1; then
        echo "$(jq -n --arg type "dashboard" --arg resource "$resource" --arg status "ok" '{type:$type, resource:$resource, status:$status}')" >>"$VALIDATION_FILE"
      else
        echo "$(jq -n --arg type "dashboard" --arg resource "$resource" --arg status "missing" '{type:$type, resource:$resource, status:$status}')" >>"$VALIDATION_FILE"
        WARNINGS+=("Dashboard validation failed for ${resource}")
        printf '%s\n' "Dashboard validation failed for ${resource}" >>"$WARNINGS_FILE"
      fi
    done <"$DASHBOARD_DATA_FILE"
  fi
  if [[ -s "$ALERT_DATA_FILE" ]]; then
    while IFS= read -r line; do
      local resource
      resource=$(echo "$line" | jq -r '.resourceName')
      if [[ -z "$resource" ]]; then
        continue
      fi
      if gcloud alpha monitoring policies describe "$resource" --project "$PROJECT_ID" >/dev/null 2>&1; then
        echo "$(jq -n --arg type "alert" --arg resource "$resource" --arg status "ok" '{type:$type, resource:$resource, status:$status}')" >>"$VALIDATION_FILE"
      else
        echo "$(jq -n --arg type "alert" --arg resource "$resource" --arg status "missing" '{type:$type, resource:$resource, status:$status}')" >>"$VALIDATION_FILE"
        WARNINGS+=("Alert validation failed for ${resource}")
        printf '%s\n' "Alert validation failed for ${resource}" >>"$WARNINGS_FILE"
      fi
    done <"$ALERT_DATA_FILE"
  fi
  if [[ -s "$UPTIME_DATA_FILE" ]]; then
    while IFS= read -r line; do
      local resource
      resource=$(echo "$line" | jq -r '.name // .resourceName // empty')
      if [[ -z "$resource" ]]; then
        continue
      fi
      if gcloud monitoring uptime checks describe "$resource" --project "$PROJECT_ID" >/dev/null 2>&1; then
        echo "$(jq -n --arg type "uptime" --arg resource "$resource" --arg status "ok" '{type:$type, resource:$resource, status:$status}')" >>"$VALIDATION_FILE"
      else
        echo "$(jq -n --arg type "uptime" --arg resource "$resource" --arg status "missing" '{type:$type, resource:$resource, status:$status}')" >>"$VALIDATION_FILE"
        WARNINGS+=("Uptime check validation failed for ${resource}")
        printf '%s\n' "Uptime check validation failed for ${resource}" >>"$WARNINGS_FILE"
      fi
    done <"$UPTIME_DATA_FILE"
  fi
}

summarize_manifest() {
  local manifest_path="${OUTPUT_DIR}/monitoring-manifest.json"
  python3 - <<'PY' "$manifest_path" "$PROJECT_ID" "$ENVIRONMENT" "$REGION" "$TIMESTAMP" "$DASHBOARD_DATA_FILE" "$ALERT_DATA_FILE" "$UPTIME_DATA_FILE" "$COST_DATA_FILE" "$SERVICE_URL_MAP_FILE" "$VALIDATION_FILE" "$WARNINGS_FILE"
import json
import os
import sys
from datetime import datetime

(
    manifest_path,
    project_id,
    environment,
    region,
    timestamp,
    dashboards_path,
    alerts_path,
    uptime_path,
    cost_path,
    services_path,
    validation_path,
    warnings_path,
) = sys.argv[1:12]

def load_lines(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return []
    with open(path, 'r', encoding='utf-8') as fh:
        return [json.loads(line) for line in fh if line.strip()]

def load_json(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return {}
    with open(path, 'r', encoding='utf-8') as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError:
            return {'raw': fh.read()}

def load_warnings(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as fh:
        return [line.strip() for line in fh if line.strip()]

manifest = {
    'generatedAt': datetime.utcnow().isoformat() + 'Z',
    'runTimestamp': timestamp,
    'projectId': project_id,
    'environment': environment,
    'region': region,
    'dashboards': load_lines(dashboards_path),
    'alertPolicies': load_lines(alerts_path),
    'uptimeChecks': load_lines(uptime_path),
    'costTracking': load_json(cost_path),
    'services': load_json(services_path),
    'validation': load_lines(validation_path),
    'warnings': load_warnings(warnings_path),
}
with open(manifest_path, 'w', encoding='utf-8') as fh:
    json.dump(manifest, fh, indent=2)
print(manifest_path)
PY
}

print_summary() {
  local manifest_path="$1"
  log "Monitoring manifest written to ${manifest_path}"
  local dashboard_count alert_count uptime_count
  dashboard_count=$(wc -l <"$DASHBOARD_DATA_FILE" 2>/dev/null || echo 0)
  alert_count=$(wc -l <"$ALERT_DATA_FILE" 2>/dev/null || echo 0)
  uptime_count=$(wc -l <"$UPTIME_DATA_FILE" 2>/dev/null || echo 0)
  log "Dashboards processed: ${dashboard_count}"
  log "Alert policies processed: ${alert_count}"
  log "Uptime checks recorded: ${uptime_count}"
  if [[ -s "$COST_DATA_FILE" ]]; then
    log "Cost tracking configuration captured"
  else
    warn "Cost tracking data not captured"
  fi
  if [[ -s "$VALIDATION_FILE" ]]; then
    log "Validation results saved to ${VALIDATION_FILE}"
  fi
  if (( ${#WARNINGS[@]} )); then
    warn "Warnings encountered during setup:"
    for msg in "${WARNINGS[@]}"; do
      warn "- ${msg}"
    done
  fi
  log "Next steps: review Cloud Monitoring dashboards, confirm alert delivery, run post-deployment load tests"
}

# Execution order
run_dashboards
run_alerts
run_monitoring_setup
run_gateway_setup
collect_uptime_from_reports
collect_cost_from_reports
validate_resources || true
MANIFEST_PATH=$(summarize_manifest)
print_summary "$MANIFEST_PATH"

echo "$MANIFEST_PATH"
