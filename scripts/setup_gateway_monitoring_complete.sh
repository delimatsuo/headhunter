#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

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
    fail "Command '$1' not available"
  fi
}

PROJECT_ID="${PROJECT_ID:-}"
ENVIRONMENT="${ENVIRONMENT:-staging}"
REGION="${REGION:-us-central1}"
GATEWAY_ID="${GATEWAY_ID:-headhunter-api-gateway-${ENVIRONMENT}}"
DASHBOARD_NAME="${DASHBOARD_NAME:-Headhunter API Gateway Overview (${ENVIRONMENT})}"
ALERT_CHANNELS="${ALERT_CHANNELS:-}" # comma separated channel IDs

usage() {
  cat <<USAGE
Usage: $0 --project PROJECT_ID [options]

Options:
  --project PROJECT_ID    Target GCP project (required)
  --environment ENV       Deployment environment (default: staging)
  --region REGION         Cloud Run region (default: us-central1)
  --gateway-id ID         API Gateway ID (default: headhunter-api-gateway-ENV)
  --dashboard-name NAME   Custom dashboard display name
  --alert-channels IDS    Comma separated notification channel IDs
  -h, --help              Show this help message
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      PROJECT_ID="$2"; shift 2 ;;
    --environment)
      ENVIRONMENT="$2"; shift 2 ;;
    --region)
      REGION="$2"; shift 2 ;;
    --gateway-id)
      GATEWAY_ID="$2"; shift 2 ;;
    --dashboard-name)
      DASHBOARD_NAME="$2"; shift 2 ;;
    --alert-channels)
      ALERT_CHANNELS="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      fail "Unknown argument: $1" ;;
  esac
done

if [[ -z "$PROJECT_ID" ]]; then
  fail "--project is required"
fi

require_command gcloud
require_command jq
require_command python3

log "Configuring monitoring for gateway ${GATEWAY_ID} in ${PROJECT_ID}"

gcloud config set project "$PROJECT_ID" >/dev/null

validate_mql_query() {
  local label="$1"
  local query="$2"
  if gcloud monitoring time-series query --project "$PROJECT_ID" --duration="5m" --query "$query" >/dev/null 2>&1; then
    log "Validated MQL query for ${label}"
  else
    warn "MQL query validation failed for ${label}; continuing"
  fi
}

ensure_dashboard() {
  local dashboard_id="$1"
  local payload_file
  payload_file="$(mktemp)"
  local request_query
  request_query=$(cat <<EOF
fetch apigateway.googleapis.com/proxy/request_count
| filter resource.label.project_id = "${PROJECT_ID}"
| filter resource.label.gateway_id = "${GATEWAY_ID}"
| group_by([metric.label.backend_service], 1m, sum)
EOF
)

  local latency_query
  latency_query=$(cat <<EOF
fetch apigateway.googleapis.com/proxy/client_latencies
| filter resource.label.project_id = "${PROJECT_ID}"
| filter resource.label.gateway_id = "${GATEWAY_ID}"
| align_percentile(percentile=95)
| group_by([metric.label.backend_service], 1m, max)
EOF
)

  local error_query
  error_query=$(cat <<EOF
fetch apigateway.googleapis.com/proxy/request_count
| filter resource.label.project_id = "${PROJECT_ID}"
| filter resource.label.gateway_id = "${GATEWAY_ID}"
| filter metric.label.response_code >= "400"
| group_by([metric.label.response_code], 1m, sum)
EOF
)

  local throughput_query
  throughput_query=$(cat <<EOF
fetch apigateway.googleapis.com/proxy/request_count
| filter resource.label.project_id = "${PROJECT_ID}"
| filter resource.label.gateway_id = "${GATEWAY_ID}"
| group_by([], 1m, sum)
EOF
)

  validate_mql_query "dashboard-request-rate" "$request_query"
  validate_mql_query "dashboard-latency" "$latency_query"
  validate_mql_query "dashboard-error-rate" "$error_query"
  validate_mql_query "dashboard-throughput" "$throughput_query"

  python3 - <<'PY' "$payload_file" "$DASHBOARD_NAME" "$request_query" "$latency_query" "$error_query" "$throughput_query"
import json
import sys
from pathlib import Path

(payload_path, dashboard_name, request_query, latency_query,
 error_query, throughput_query) = sys.argv[1:]

layout = {
    "displayName": dashboard_name,
    "gridLayout": {
        "columns": 2,
        "widgets": [
            {
                "title": "Request Rate by Backend",
                "xyChart": {
                    "dataSets": [
                        {
                            "timeSeriesQuery": {
                                "timeSeriesQueryLanguage": request_query
                            },
                            "plotType": "LINE"
                        }
                    ],
                    "yAxis": {
                        "label": "Requests / min",
                        "scale": "LINEAR"
                    }
                }
            },
            {
                "title": "P95 Latency",
                "xyChart": {
                    "dataSets": [
                        {
                            "timeSeriesQuery": {
                                "timeSeriesQueryLanguage": latency_query
                            },
                            "plotType": "LINE"
                        }
                    ],
                    "yAxis": {
                        "label": "Latency (ms)",
                        "scale": "LINEAR"
                    }
                }
            },
            {
                "title": "Error Volume (4xx/5xx)",
                "xyChart": {
                    "dataSets": [
                        {
                            "plotType": "STACKED_AREA",
                            "timeSeriesQuery": {
                                "timeSeriesQueryLanguage": error_query
                            }
                        }
                    ],
                    "yAxis": {
                        "label": "Errors / min",
                        "scale": "LINEAR"
                    }
                }
            },
            {
                "title": "Total Request Throughput",
                "scorecard": {
                    "timeSeriesQuery": {
                        "timeSeriesQueryLanguage": throughput_query
                    }
                }
            }
        ]
    }
}
Path(payload_path).write_text(json.dumps({"displayName": dashboard_name, "gridLayout": layout["gridLayout"]}, indent=2))
PY
  if gcloud monitoring dashboards list --format="value(name)" | grep -q "$dashboard_id"; then
    log "Updating dashboard ${dashboard_id}"
    gcloud monitoring dashboards update "$dashboard_id" --config-json="$payload_file"
  else
    log "Creating dashboard ${dashboard_id}"
    gcloud monitoring dashboards create --config-json="$payload_file"
  fi
  rm -f "$payload_file"
}

create_alert_policy() {
  local name="$1"
  local metric_query="$2"
  local threshold="$3"
  local alignment="$4"
  local duration="$5"
  local comparator="$6"
  local documentation="$7"
  local policy_file
  policy_file="$(mktemp)"
  validate_mql_query "$name" "$metric_query"
  python3 - <<'PY' "$policy_file" "$name" "$metric_query" "$threshold" "$alignment" "$duration" "$comparator" "$documentation" "$ALERT_CHANNELS"
import json
import sys
from pathlib import Path
(policy_path, display_name, query, threshold, per_series_aligner,
 duration, comparator, documentation, channels) = sys.argv[1:]
channels_list = [c.strip() for c in channels.split(',') if c.strip()]
operator_map = {
    'COMPARISON_GT': '>',
    'COMPARISON_GE': '>=',
    'COMPARISON_LT': '<',
    'COMPARISON_LE': '<=',
}
operator = operator_map.get(comparator, '>')
policy = {
    "displayName": display_name,
    "documentation": {
        "content": documentation,
        "mimeType": "text/markdown"
    },
    "conditions": [
        {
            "displayName": display_name,
            "conditionMonitoringQueryLanguage": {
                "query": f"{query} | condition val {operator} {threshold}",
                "duration": duration,
                "trigger": {
                    "count": 1
                }
            }
        }
    ],
    "combiner": "OR",
    "enabled": True
}
if channels_list:
    policy["notificationChannels"] = channels_list
Path(policy_path).write_text(json.dumps(policy, indent=2))
PY
  if gcloud alpha monitoring policies list --format="value(displayName)" | grep -q "$name"; then
    log "Updating alert policy ${name}"
    gcloud alpha monitoring policies update --policy-from-file="$policy_file"
  else
    log "Creating alert policy ${name}"
    gcloud alpha monitoring policies create --policy-from-file="$policy_file"
  fi
  rm -f "$policy_file"
}

setup_log_metric() {
  local metric_name="$1"
  local filter="$2"
  if gcloud logging metrics list --format="value(name)" | grep -q "^${metric_name}$"; then
    log "Updating log metric ${metric_name}"
    gcloud logging metrics update "$metric_name" --description="${metric_name}" --log-filter="$filter"
  else
    log "Creating log metric ${metric_name}"
    gcloud logging metrics create "$metric_name" --description="${metric_name}" --log-filter="$filter"
  fi
}

main() {
  ensure_dashboard "projects/${PROJECT_ID}/dashboards/${GATEWAY_ID}-${ENVIRONMENT}-overview"

  create_alert_policy \
    "Gateway Latency SLA" \
    "fetch apigateway.googleapis.com/proxy/client_latencies | filter resource.label.project_id = \"${PROJECT_ID}\" | filter resource.label.gateway_id = \"${GATEWAY_ID}\" | align_percentile(percentile=95) | group_by([], 1m, max)" \
    "1200" \
    "ALIGN_PERCENTILE_95" \
    "60s" \
    "COMPARISON_GT" \
    "Latency p95 exceeded 1200ms"

  create_alert_policy \
    "Gateway Rerank Latency" \
    "fetch apigateway.googleapis.com/proxy/client_latencies | filter resource.label.project_id = \"${PROJECT_ID}\" | filter resource.label.gateway_id = \"${GATEWAY_ID}\" | filter metric.label.backend_service =~ \".*hh-rerank-svc.*\" | align_percentile(percentile=95) | group_by([], 1m, max)" \
    "350" \
    "ALIGN_PERCENTILE_95" \
    "60s" \
    "COMPARISON_GT" \
    "Rerank service latency above 350ms"

  create_alert_policy \
    "Gateway Error Volume" \
    "fetch apigateway.googleapis.com/proxy/request_count | filter resource.label.project_id = \"${PROJECT_ID}\" | filter resource.label.gateway_id = \"${GATEWAY_ID}\" | filter metric.label.response_code >= \"500\" | group_by([], 1m, sum)" \
    "5" \
    "ALIGN_SUM" \
    "300s" \
    "COMPARISON_GT" \
    "5xx error volume exceeded threshold"

  setup_log_metric "gateway-request-trace" "resource.type=\"api\" AND httpRequest.status>=200"
  setup_log_metric "gateway-auth-failures" "resource.type=\"api\" AND httpRequest.status=401"

  log "Monitoring configuration applied"
}

main "$@"
