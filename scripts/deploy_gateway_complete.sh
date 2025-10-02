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
  if [[ -z "$ROLLBACK_REASON" ]]; then
    ROLLBACK_REASON="$*"
  fi
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Command '$1' not available"
  fi
}

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-us-central1}"
ENVIRONMENT="${ENVIRONMENT:-staging}"
GATEWAY_ID="${GATEWAY_ID:-headhunter-api-gateway-${ENVIRONMENT}}"
TOKEN="${TOKEN:-}"
SECONDARY_TOKEN="${SECONDARY_TOKEN:-}"
PRIMARY_TENANT="${PRIMARY_TENANT:-smoke-test}"
SECONDARY_TENANT="${SECONDARY_TENANT:-}" # optional
SECRETS_PREFIX="${SECRETS_PREFIX:-oauth-client-}"
REPORT_DIR="${REPORT_DIR:-deployment-reports}"
REPORT_FILE="${REPORT_FILE:-}" # optional combined report
CONFIG_ID="${CONFIG_ID:-gateway-config-$(date +%Y%m%d%H%M%S)}"
MODE="${MODE:-smoke}"
ROLLBACK_ON_FAILURE=1

usage() {
  cat <<USAGE
Usage: $0 --project PROJECT_ID --token TOKEN [options]

Options:
  --project ID           Target GCP project (required)
  --token TOKEN          OAuth Bearer token for validation tests (required)
  --secondary-token TK   Optional secondary tenant token
  --tenant ID            Primary tenant identifier (default: smoke-test)
  --secondary-tenant ID  Secondary tenant identifier
  --region REGION        Cloud Run region (default: us-central1)
  --environment ENV      Deployment environment (default: staging)
  --gateway-id ID        Gateway identifier (default: headhunter-api-gateway-ENV)
  --config-id ID         Override generated API config id
  --secrets-prefix PREF  Secret prefix for OAuth client lookup
  --report-dir DIR       Directory to write component reports (default: deployment-reports)
  --report FILE          Combined JSON report output path
  --no-rollback          Skip automatic rollback on validation failure
  -h, --help             Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      PROJECT_ID="$2"; shift 2 ;;
    --token)
      TOKEN="$2"; shift 2 ;;
    --secondary-token)
      SECONDARY_TOKEN="$2"; shift 2 ;;
    --tenant)
      PRIMARY_TENANT="$2"; shift 2 ;;
    --secondary-tenant)
      SECONDARY_TENANT="$2"; shift 2 ;;
    --region)
      REGION="$2"; shift 2 ;;
    --environment)
      ENVIRONMENT="$2"; shift 2 ;;
    --gateway-id)
      GATEWAY_ID="$2"; shift 2 ;;
    --config-id)
      CONFIG_ID="$2"; shift 2 ;;
    --secrets-prefix)
      SECRETS_PREFIX="$2"; shift 2 ;;
    --report-dir)
      REPORT_DIR="$2"; shift 2 ;;
    --report)
      REPORT_FILE="$2"; shift 2 ;;
    --no-rollback)
      ROLLBACK_ON_FAILURE=0; shift ;;
    --mode)
      MODE="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      fail "Unknown argument: $1" ;;
  esac
done

if [[ -z "$PROJECT_ID" || -z "$TOKEN" ]]; then
  fail "--project and --token are required"
fi

require_command gcloud
require_command jq
require_command python3

STEP_SUMMARY=()
STEP_STATUS=()
GATEWAY_PREVIOUS_CONFIG=""
GATEWAY_CONFIG_DEPLOYED=""
ROLLBACK_REASON=""
mkdir -p "$REPORT_DIR"

record_step() {
  local name="$1"
  local status="$2"
  local start="$3"
  local end="$4"
  local details="$5"
  STEP_SUMMARY+=("{\"name\":\"${name//"/\"}\",\"status\":\"${status}\",\"startedAt\":${start},\"endedAt\":${end},\"details\":\"${details//"/\"}\"}")
  STEP_STATUS+=("${name}:${status}")
}

cleanup() {
  local exit_code=$?
  if (( exit_code != 0 )) && (( ROLLBACK_ON_FAILURE == 1 )); then
    warn "Deployment orchestration failed; evaluating rollback."
    if [[ -n "$GATEWAY_PREVIOUS_CONFIG" ]]; then
      warn "Restoring gateway ${GATEWAY_ID} to ${GATEWAY_PREVIOUS_CONFIG}."
      gcloud api-gateway gateways update "$GATEWAY_ID" \
        --location="$REGION" \
        --api-config="$GATEWAY_PREVIOUS_CONFIG" \
        --project="$PROJECT_ID" \
        --quiet || warn "Failed to restore previous gateway config."
    fi
    if [[ -n "$GATEWAY_CONFIG_DEPLOYED" ]]; then
      warn "Deleting new API config ${GATEWAY_CONFIG_DEPLOYED}."
      gcloud api-gateway api-configs delete "$GATEWAY_CONFIG_DEPLOYED" \
        --api="$GATEWAY_ID" \
        --project="$PROJECT_ID" \
        --quiet || warn "Unable to delete api-config ${GATEWAY_CONFIG_DEPLOYED}."
    fi
  fi
  if [[ -n "$REPORT_FILE" ]]; then
    local summary_json
    summary_json=$(printf '%s\n' "${STEP_SUMMARY[@]}" | jq -s 'map(fromjson)')
    jq -n --argjson summary "$summary_json" --arg rollback "$ROLLBACK_REASON" '{steps: $summary, rollbackReason: $rollback}' > "$REPORT_FILE"
    log "Deployment report written to ${REPORT_FILE}"
  fi
  exit $exit_code
}
trap cleanup EXIT

main() {
  log "Starting complete gateway deployment for ${PROJECT_ID} (${ENVIRONMENT})"
  gcloud config set project "$PROJECT_ID" >/dev/null

  local start_ts

  start_ts=$(date +%s)
  GATEWAY_PREVIOUS_CONFIG=$(gcloud api-gateway gateways describe "$GATEWAY_ID" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --format="value(apiConfig)" 2>/dev/null || true)
  record_step "capture-previous-config" "complete" "$start_ts" "$(date +%s)" "Previous config: ${GATEWAY_PREVIOUS_CONFIG:-none}"

  if [[ ! -x scripts/deploy_api_gateway.sh ]]; then
    fail "scripts/deploy_api_gateway.sh not found"
  fi

  start_ts=$(date +%s)
  (PROJECT_ID="$PROJECT_ID" REGION="$REGION" ENVIRONMENT="$ENVIRONMENT" GATEWAY_ID="$GATEWAY_ID" CONFIG_ID="$CONFIG_ID" SERVICE_ACCOUNT="gateway-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com" scripts/deploy_api_gateway.sh)
  GATEWAY_CONFIG_DEPLOYED="$CONFIG_ID"
  record_step "deploy-api-gateway" "complete" "$start_ts" "$(date +%s)" "Gateway updated to config ${CONFIG_ID}"

  if [[ -x scripts/setup_gateway_monitoring_complete.sh ]]; then
    start_ts=$(date +%s)
    scripts/setup_gateway_monitoring_complete.sh --project "$PROJECT_ID" --environment "$ENVIRONMENT" --region "$REGION" --gateway-id "$GATEWAY_ID"
    record_step "configure-monitoring" "complete" "$start_ts" "$(date +%s)" "Monitoring assets applied"
  else
    warn "scripts/setup_gateway_monitoring_complete.sh not found; skipping monitoring setup"
    record_step "configure-monitoring" "skipped" "$(date +%s)" "$(date +%s)" "Monitoring script not available"
  fi

  if [[ ! -x scripts/test_gateway_end_to_end.sh ]]; then
    fail "scripts/test_gateway_end_to_end.sh not found"
  fi

  local gateway_endpoint
  gateway_endpoint=$(gcloud api-gateway gateways describe "$GATEWAY_ID" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --format="value(defaultHostname)")
  if [[ -z "$gateway_endpoint" ]]; then
    ROLLBACK_REASON="Gateway endpoint unavailable"
    fail "Unable to resolve gateway endpoint"
  fi

  start_ts=$(date +%s)
  if scripts/test_gateway_end_to_end.sh \
      --project "$PROJECT_ID" \
      --endpoint "https://${gateway_endpoint}" \
      --token "$TOKEN" \
      --tenant "$PRIMARY_TENANT" \
      ${SECONDARY_TENANT:+--secondary-tenant "$SECONDARY_TENANT"} \
      ${SECONDARY_TOKEN:+--secondary-token "$SECONDARY_TOKEN"} \
      --region "$REGION" \
      --environment "$ENVIRONMENT" \
      --report-dir "$REPORT_DIR" \
      --secrets-prefix "$SECRETS_PREFIX" \
      --mode "$MODE"; then
    record_step "validation-suite" "complete" "$start_ts" "$(date +%s)" "All validation suites passed"
  else
    ROLLBACK_REASON="Validation suite failure"
    record_step "validation-suite" "failed" "$start_ts" "$(date +%s)" "Validation scripts reported errors"
    fail "Validation suite failed"
  fi

  log "Gateway deployment complete"
}

main "$@"
