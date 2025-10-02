#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Configure Cloud Monitoring dashboards and alerting for the API Gateway.

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-us-central1}"
DASHBOARD_NAME="${DASHBOARD_NAME:-Headhunter Gateway Overview}"
ALERT_POLICY_PREFIX="${ALERT_POLICY_PREFIX:-gateway-}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "PROJECT_ID must be set" >&2
  exit 1
fi

gcloud config set project "$PROJECT_ID" >/dev/null

dashboard_payload=$(cat <<'JSON'
{
  "displayName": "Headhunter API Gateway",
  "gridLayout": {
    "columns": 3,
    "widgets": [
      {
        "title": "Request Rate",
        "xyChart": {
          "dataSets": [
            {
              "plotType": "LINE",
              "legendTemplate": "Class ${metric.label.response_code_class}",
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"apigateway.googleapis.com/proxy/request_count\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_RATE",
                    "groupByFields": ["metric.label.response_code_class"]
                  }
                }
              }
            }
          ]
        }
      },
      {
        "title": "Gateway p95 Latency",
        "xyChart": {
          "dataSets": [
            {
              "plotType": "LINE",
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"apigateway.googleapis.com/proxy/latencies\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_PERCENTILE_95"
                  }
                }
              }
            }
          ]
        }
      },
      {
        "title": "Backend p95 Latency",
        "xyChart": {
          "dataSets": [
            {
              "plotType": "LINE",
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"apigateway.googleapis.com/proxy/backend_latencies\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_PERCENTILE_95"
                  }
                }
              }
            }
          ]
        }
      },
      {
        "title": "Non-2xx Rate",
        "xyChart": {
          "dataSets": [
            {
              "plotType": "LINE",
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"apigateway.googleapis.com/proxy/request_count\" AND metric.label.response_code_class!=\"2xx\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_RATE",
                    "groupByFields": ["metric.label.response_code_class"]
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
)

echo "Creating dashboard $DASHBOARD_NAME"
printf '%s' "$dashboard_payload" | gcloud monitoring dashboards create --format=json >/dev/null

echo "Creating alerting policies"

create_alert() {
  local name="$1"
  local filter="$2"
  local threshold="$3"
  local duration="$4"
  gcloud alpha monitoring policies create \
    --display-name="${ALERT_POLICY_PREFIX}${name}" \
    --conditions="condition-display-name=${name},condition-filter=${filter},condition-threshold-value=${threshold},condition-duration=${duration}" \
    --notification-channels="${NOTIFICATION_CHANNELS:-}" >/dev/null
}

create_alert "p95-latency-read" "metric.type=\"apigateway.googleapis.com/proxy/latencies\"" "250" "0m5s"
create_alert "p95-latency-rerank" "metric.type=\"apigateway.googleapis.com/proxy/backend_latencies\"" "350" "0m5s"
create_alert "error-rate" "metric.type=\"apigateway.googleapis.com/proxy/request_count\" AND metric.label.response_code_class!=\"2xx\"" "1" "0m5s"

cat <<INFO
Monitoring setup complete.
Dashboard: ${DASHBOARD_NAME}
Region: ${REGION}
INFO
