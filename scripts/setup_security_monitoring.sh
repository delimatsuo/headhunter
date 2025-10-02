#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

PROJECT_ID="${PROJECT_ID:-}"
ENVIRONMENT="production"
REGION="${REGION:-us-central1}"
NOTIFICATION_CHANNELS=""
DASHBOARD_NAME="Headhunter Security Overview"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Options:
  --project-id ID               Target GCP project id (required)
  --environment NAME            Environment suffix (default: production)
  --region REGION               Cloud Run region (default: us-central1)
  --channels CHANNEL_IDS        Comma-separated Monitoring notification channel IDs
  --dashboard-name NAME         Monitoring dashboard display name
  -h, --help                    Show this help message
USAGE
}

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
    --channels)
      NOTIFICATION_CHANNELS="$2"
      shift 2
      ;;
    --dashboard-name)
      DASHBOARD_NAME="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$PROJECT_ID" ]]; then
  echo "--project-id is required" >&2
  exit 1
fi

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command '$1' not found" >&2
    exit 2
  fi
}

require_command gcloud
require_command jq

gcloud config set project "$PROJECT_ID" >/dev/null 2>&1 || true

log() {
  printf '[security-monitoring][%s] %s\n' "$(date -Is)" "$*"
}

create_metric() {
  local name="$1"
  local filter="$2"
  local description="$3"
  if gcloud logging metrics describe "$name" >/dev/null 2>&1; then
    log "Metric ${name} already exists"
  else
    log "Creating log-based metric ${name}"
    gcloud logging metrics create "$name" \
      --description="$description" \
      --filter="$filter" >/dev/null
  fi
}

create_policy() {
  local display_name="$1"
  local metric_name="$2"
  local threshold="$3"
  local duration="$4"
  local policy_file
  policy_file="$(mktemp)"
  cat <<JSON >"$policy_file"
{
  "displayName": "${display_name}",
  "conditions": [
    {
      "displayName": "${display_name} condition",
      "conditionThreshold": {
        "filter": "metric.type=\"logging.googleapis.com/user/${metric_name}\"",
        "comparison": "COMPARISON_GT",
        "thresholdValue": ${threshold},
        "duration": "${duration}",
        "trigger": {
          "count": 1
        }
      }
    }
  ],
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": []
}
JSON
  if [[ -n "$NOTIFICATION_CHANNELS" ]]; then
    local channels_json
    channels_json=$(jq -n --arg channels "$NOTIFICATION_CHANNELS" '$channels | split(",") | map(. | gsub("^\\s+|\\s+$"; "")) | map(select(length>0))')
    jq --argjson channels "$channels_json" '.notificationChannels = $channels' "$policy_file" >"${policy_file}.tmp" && mv "${policy_file}.tmp" "$policy_file"
  fi
  if gcloud monitoring policies list --format="value(displayName)" | grep -Fxq "$display_name"; then
    log "Alert policy ${display_name} already exists"
  else
    log "Creating alert policy ${display_name}"
    gcloud monitoring policies create --policy-from-file="$policy_file" >/dev/null
  fi
  rm -f "$policy_file"
}

# Log-based metrics ----------------------------------------------------------
AUTH_FAILURE_METRIC="hh-auth-failure-${ENVIRONMENT}"
TENANT_VIOLATION_METRIC="hh-tenant-violation-${ENVIRONMENT}"
SECRET_ACCESS_METRIC="hh-secret-access-${ENVIRONMENT}"
IAM_DENY_METRIC="hh-iam-deny-${ENVIRONMENT}"

create_metric "$AUTH_FAILURE_METRIC" \
  'resource.type="cloud_run_revision" AND jsonPayload.context.component="auth" AND jsonPayload.context.outcome="failure"' \
  'Counts authentication failures emitted by the auth middleware.'

create_metric "$TENANT_VIOLATION_METRIC" \
  'resource.type="cloud_run_revision" AND jsonPayload.context.component="tenant" AND jsonPayload.context.violation="mismatch"' \
  'Tracks X-Tenant-ID violations across services.'

create_metric "$SECRET_ACCESS_METRIC" \
  'resource.type="audited_resource" AND protoPayload.serviceName="secretmanager.googleapis.com" AND protoPayload.methodName="AccessSecretVersion"' \
  'Records Secret Manager access events for anomaly detection.'

create_metric "$IAM_DENY_METRIC" \
  'resource.type="audited_resource" AND protoPayload.status.code=7' \
  'Captures IAM permission denied events across Google Cloud services.'

# Alerting policies ----------------------------------------------------------
create_policy "Security - Auth Failures" "$AUTH_FAILURE_METRIC" 0 "0m1s"
create_policy "Security - Tenant Violations" "$TENANT_VIOLATION_METRIC" 0 "0m1s"
create_policy "Security - Secret Access" "$SECRET_ACCESS_METRIC" 5 "0m5s"
create_policy "Security - IAM Denied" "$IAM_DENY_METRIC" 0 "0m1s"

# Dashboard ------------------------------------------------------------------
dash_payload="$(mktemp)"
cat <<JSON >"$dash_payload"
{
  "displayName": "${DASHBOARD_NAME}",
  "gridLayout": {
    "columns": 2,
    "widgets": [
      {
        "title": "Authentication Failures",
        "xyChart": {
          "dataSets": [
            {
              "plotType": "LINE",
              "legendTemplate": "Failures",
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"logging.googleapis.com/user/${AUTH_FAILURE_METRIC}\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_RATE"
                  }
                }
              }
            }
          ]
        }
      },
      {
        "title": "Tenant Violations",
        "xyChart": {
          "dataSets": [
            {
              "plotType": "LINE",
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"logging.googleapis.com/user/${TENANT_VIOLATION_METRIC}\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_RATE"
                  }
                }
              }
            }
          ]
        }
      },
      {
        "title": "Secret Access Volume",
        "xyChart": {
          "dataSets": [
            {
              "plotType": "LINE",
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"logging.googleapis.com/user/${SECRET_ACCESS_METRIC}\"",
                  "aggregation": {
                    "alignmentPeriod": "300s",
                    "perSeriesAligner": "ALIGN_SUM"
                  }
                }
              }
            }
          ]
        }
      },
      {
        "title": "IAM Permission Denied",
        "xyChart": {
          "dataSets": [
            {
              "plotType": "LINE",
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"logging.googleapis.com/user/${IAM_DENY_METRIC}\"",
                  "aggregation": {
                    "alignmentPeriod": "300s",
                    "perSeriesAligner": "ALIGN_SUM"
                  }
                }
              }
            }
          ]
        }
      }
    ]
  }
}
JSON

if gcloud monitoring dashboards list --format="value(displayName)" | grep -Fxq "$DASHBOARD_NAME"; then
  log "Dashboard ${DASHBOARD_NAME} already exists"
else
  log "Creating security dashboard ${DASHBOARD_NAME}"
  gcloud monitoring dashboards create --dashboard-from-file="$dash_payload" >/dev/null
fi
rm -f "$dash_payload"

cat <<SUMMARY
Security monitoring configuration complete.
Project: ${PROJECT_ID}
Environment: ${ENVIRONMENT}
Region: ${REGION}
SUMMARY
