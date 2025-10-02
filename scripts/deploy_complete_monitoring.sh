#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)

usage() {
  cat <<USAGE
Usage: $(basename "$0") --project-id PROJECT [options]

End-to-end monitoring deployment orchestrator. Executes the production
monitoring setup, ensures dashboards/alerts are provisioned, runs SLA
compliance checks, and produces validation reports.

Options:
  --project-id ID          GCP project identifier (required)
  --region REGION          Cloud Run region (default: us-central1)
  --environment ENV        Environment suffix (default: production)
  --cost-dataset NAME      BigQuery dataset for cost logs (default: ops_observability)
  --cost-table NAME        BigQuery table for cost logs (default: ops_cost_logs)
  --bigquery-location LOC  BigQuery dataset location (default: US)
  --dry-run                Execute commands in dry-run mode where supported
  --skip-validation        Skip post-deployment validation
  -h, --help               Show this message
USAGE
}

PROJECT_ID=""
REGION="us-central1"
ENVIRONMENT="production"
COST_DATASET="ops_observability"
COST_TABLE="ops_cost_logs"
BIGQUERY_LOCATION="US"
DRY_RUN=false
SKIP_VALIDATION=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      PROJECT_ID="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --environment)
      ENVIRONMENT="$2"
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
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --skip-validation)
      SKIP_VALIDATION=true
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

echo "[deploy] Starting monitoring deployment for ${PROJECT_ID} (${ENVIRONMENT})"

SETUP_ARGS=(
  "--project-id" "${PROJECT_ID}"
  "--region" "${REGION}"
  "--environment" "${ENVIRONMENT}"
)
if [[ "${DRY_RUN}" == true ]]; then
  SETUP_ARGS+=("--dry-run")
fi

"${SCRIPT_DIR}/setup_production_monitoring.sh" "${SETUP_ARGS[@]}"

echo "[deploy] Provisioning complete."

if [[ "${SKIP_VALIDATION}" == true ]]; then
  echo "[deploy] Validation skipped by flag"
  exit 0
fi

echo "[deploy] Running monitoring validation suite"
"${SCRIPT_DIR}/validate_monitoring_setup.sh" \
  --project-id "${PROJECT_ID}" \
  --environment "${ENVIRONMENT}" \
  --region "${REGION}" \
  --cost-dataset "${COST_DATASET}" \
  --cost-table "${COST_TABLE}" \
  --bigquery-location "${BIGQUERY_LOCATION}"

echo "[deploy] Generating SLA compliance snapshot"
python3 "${SCRIPT_DIR}/sla_compliance_monitoring.py" \
  --project-id "${PROJECT_ID}" \
  --environment "${ENVIRONMENT}" \
  --alignment "300s" \
  --log-level INFO \
  --dry-run

echo "[deploy] Producing cost optimization report"
python3 "${SCRIPT_DIR}/cost_analysis_and_optimization.py" \
  --project-id "${PROJECT_ID}" \
  --dataset "${COST_DATASET}" \
  --table "${COST_TABLE}" \
  --lookback-days 7 \
  --dry-run

echo "[deploy] Monitoring deployment finished"
