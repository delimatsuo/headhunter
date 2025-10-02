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
    fail "Command '$1' not found"
  fi
}

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-us-central1}"
ENVIRONMENT="${ENVIRONMENT:-staging}"
ENDPOINT="${ENDPOINT:-}"
PRIMARY_TENANT="${PRIMARY_TENANT:-smoke-test}"
SECONDARY_TENANT="${SECONDARY_TENANT:-}" # optional
TOKEN="${TOKEN:-}"
SECONDARY_TOKEN="${SECONDARY_TOKEN:-}" # optional
SECRETS_PREFIX="${SECRETS_PREFIX:-oauth-client-}"
MODE="${MODE:-smoke}" # smoke or full
REPORT_DIR="${REPORT_DIR:-}" # optional output directory for JSON reports

usage() {
  cat <<USAGE
Usage: $0 --project PROJECT_ID --endpoint https://gateway-host --token TOKEN [options]

Options:
  --project ID          GCP project (required)
  --endpoint URL        Gateway base URL (required)
  --token TOKEN         Access token for primary tenant (required)
  --tenant ID           Primary tenant identifier (default: smoke-test)
  --secondary-tenant ID Secondary tenant identifier for isolation tests
  --secondary-token TK  Access token for secondary tenant
  --region REGION       Cloud Run region (default: us-central1)
  --environment ENV     Deployment environment (default: staging)
  --mode MODE           Test mode (smoke|full)
  --report-dir DIR      Directory to write JSON reports from component tests
  --secrets-prefix PREF Secret prefix for OAuth testing (default: oauth-client-)
  -h, --help            Show this help message
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      PROJECT_ID="$2"; shift 2 ;;
    --endpoint)
      ENDPOINT="$2"; shift 2 ;;
    --token)
      TOKEN="$2"; shift 2 ;;
    --tenant)
      PRIMARY_TENANT="$2"; shift 2 ;;
    --secondary-tenant)
      SECONDARY_TENANT="$2"; shift 2 ;;
    --secondary-token)
      SECONDARY_TOKEN="$2"; shift 2 ;;
    --region)
      REGION="$2"; shift 2 ;;
    --environment)
      ENVIRONMENT="$2"; shift 2 ;;
    --mode)
      MODE="$2"; shift 2 ;;
    --report-dir)
      REPORT_DIR="$2"; shift 2 ;;
    --secrets-prefix)
      SECRETS_PREFIX="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      fail "Unknown argument: $1" ;;
  esac
done

if [[ -z "$PROJECT_ID" || -z "$ENDPOINT" || -z "$TOKEN" ]]; then
  fail "--project, --endpoint, and --token are required"
fi

require_command jq
require_command python3

component_report() {
  local script="$1"
  shift
  local label="$1"
  shift
  local report=""
  if [[ -n "$REPORT_DIR" ]]; then
    mkdir -p "$REPORT_DIR"
    report="${REPORT_DIR}/${label}.json"
  fi
  log "Running ${label}"
  if [[ -n "$report" ]]; then
    "$script" "$@" --report "$report"
  else
    "$script" "$@"
  fi
  local status=$?
  if (( status != 0 )); then
    warn "${label} failed with exit code ${status}"
  fi
  return $status
}

main() {
  local failures=0

  if [[ ! -x scripts/test_oauth2_authentication.sh ]]; then
    fail "scripts/test_oauth2_authentication.sh not found or not executable"
  fi
  if [[ ! -x scripts/test_gateway_routing.sh ]]; then
    fail "scripts/test_gateway_routing.sh not found or not executable"
  fi
  if [[ ! -x scripts/test_rate_limiting.sh ]]; then
    fail "scripts/test_rate_limiting.sh not found or not executable"
  fi
  if [[ ! -x scripts/test_cors_functionality.sh ]]; then
    fail "scripts/test_cors_functionality.sh not found or not executable"
  fi

  local tenant_args=(--project "$PROJECT_ID" --endpoint "$ENDPOINT" --tenant "$PRIMARY_TENANT" --gateway-path /v1/search/hybrid --rate-limit-path /v1/search/hybrid --token "$TOKEN" --region "$REGION" --secrets-prefix "$SECRETS_PREFIX")
  if ! component_report scripts/test_oauth2_authentication.sh oauth "${tenant_args[@]}"; then
    failures=$((failures + 1))
  fi

  local routing_mode="$MODE"
  if ! component_report scripts/test_gateway_routing.sh routing --endpoint "$ENDPOINT" --tenant "$PRIMARY_TENANT" --token "$TOKEN" --mode "$routing_mode" --project "$PROJECT_ID" --environment "$ENVIRONMENT"; then
    failures=$((failures + 1))
  fi

  local rate_args=(--endpoint "$ENDPOINT" --token "$TOKEN" --tenant "$PRIMARY_TENANT")
  if [[ -n "$SECONDARY_TENANT" && -n "$SECONDARY_TOKEN" ]]; then
    rate_args+=(--secondary-tenant "$SECONDARY_TENANT" --secondary-token "$SECONDARY_TOKEN")
  fi
  if ! component_report scripts/test_rate_limiting.sh rate-limits "${rate_args[@]}"; then
    failures=$((failures + 1))
  fi

  if ! component_report scripts/test_cors_functionality.sh cors --endpoint "$ENDPOINT"; then
    failures=$((failures + 1))
  fi

  if (( failures > 0 )); then
    fail "End-to-end validation encountered ${failures} failures"
  fi
  log "End-to-end gateway validation completed successfully"
}

main "$@"
