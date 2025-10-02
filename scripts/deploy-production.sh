#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

usage() {
  cat <<'USAGE'
Usage: scripts/deploy-production.sh [options]

Orchestrates the full production deployment pipeline (build -> deploy -> gateway -> smoke tests).

Options:
  --project-id <id>         Google Cloud project ID
  --environment <env>       Deployment environment (default: production)
  --services <list>         Comma-separated service subset or 'all'
  --skip-build              Skip container build step
  --skip-deploy             Skip Cloud Run deployment step
  --skip-gateway            Skip API Gateway update
  --skip-smoke-tests        Skip post-deployment smoke tests
  --skip-monitoring         Skip monitoring setup step
  --skip-load-tests         Skip post-deployment load tests
  --parallel-build          Build container images in parallel
  --notification-channels <ids>  Comma-separated monitoring notification channel IDs
  --build-manifest <path>   Use existing build manifest (implies --skip-build)
  --deploy-manifest <path>  Use existing deploy manifest (implies --skip-deploy)
  --report-dir <path>       Directory for deployment artifacts (default: .deployment)
  --load-test-duration <s>  Duration per load test scenario (default: 300)
  --load-test-concurrency <n>  Concurrent users for load tests (default: 10)
  --generate-report [true|false]  Generate deployment report after success (default: true)
  --no-generate-report      Disable automated deployment report generation
  --report-output <path>    Path for deployment report markdown
  --rollback-on-failure     Attempt automatic rollback on failures
  --dry-run                 Show planned actions without executing changes
  --allow-dirty             Allow running with uncommitted git changes
  --skip-tests              Pass --skip-tests to the build step
  --help                    Show this help message
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
    fail "Required command '$1' not found in PATH."
  fi
}

resolve_path() {
  if ! command -v python3 >/dev/null 2>&1; then
    fail "python3 is required for path resolution"
  fi
  python3 - <<'PY' "$1"
import os
import sys
print(os.path.abspath(sys.argv[1]))
PY
}

PROJECT_ID="${PROJECT_ID:-}"
ENVIRONMENT="${ENVIRONMENT:-production}"
SERVICES_ARG="all"
SKIP_BUILD=false
SKIP_DEPLOY=false
SKIP_GATEWAY=false
SKIP_SMOKE=false
SKIP_MONITORING=false
SKIP_LOAD_TESTS=false
PARALLEL_BUILD=false
ROLLBACK_ON_FAILURE=false
DRY_RUN=false
ALLOW_DIRTY=false
SKIP_TESTS=false
REPORT_DIR=".deployment"
BUILD_MANIFEST_OVERRIDE=""
DEPLOY_MANIFEST_OVERRIDE=""
NOTIFICATION_CHANNELS=""
LOAD_TEST_DURATION=300
LOAD_TEST_CONCURRENCY=10
GENERATE_REPORT=true
REPORT_OUTPUT=""
REPORT_OUTPUT_PATH=""
REPORT_GENERATION_STATUS="skipped"
REPORT_GENERATION_MESSAGE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      PROJECT_ID="$2"; shift 2 ;;
    --environment)
      ENVIRONMENT="$2"; shift 2 ;;
    --services)
      SERVICES_ARG="$2"; shift 2 ;;
    --skip-build)
      SKIP_BUILD=true; shift ;;
    --skip-deploy)
      SKIP_DEPLOY=true; shift ;;
    --skip-gateway)
      SKIP_GATEWAY=true; shift ;;
    --skip-smoke-tests)
      SKIP_SMOKE=true; shift ;;
    --skip-monitoring)
      SKIP_MONITORING=true; shift ;;
    --skip-load-tests)
      SKIP_LOAD_TESTS=true; shift ;;
    --parallel-build)
      PARALLEL_BUILD=true; shift ;;
    --notification-channels)
      NOTIFICATION_CHANNELS="$2"; shift 2 ;;
    --rollback-on-failure)
      ROLLBACK_ON_FAILURE=true; shift ;;
    --dry-run)
      DRY_RUN=true; shift ;;
    --allow-dirty)
      ALLOW_DIRTY=true; shift ;;
    --skip-tests)
      SKIP_TESTS=true; shift ;;
    --report-dir)
      REPORT_DIR="$2"; shift 2 ;;
    --load-test-duration)
      LOAD_TEST_DURATION="$2"; shift 2 ;;
    --load-test-concurrency)
      LOAD_TEST_CONCURRENCY="$2"; shift 2 ;;
    --generate-report)
      if [[ $# -ge 2 && "$2" != --* ]]; then
        case "$2" in
          true|TRUE|True) GENERATE_REPORT=true ;;
          false|FALSE|False) GENERATE_REPORT=false ;;
          *) fail "Invalid value for --generate-report (expected true/false)" ;;
        esac
        shift 2
      else
        GENERATE_REPORT=true
        shift
      fi
      ;;
    --no-generate-report)
      GENERATE_REPORT=false; shift ;;
    --report-output)
      REPORT_OUTPUT="$2"; shift 2 ;;
    --build-manifest)
      BUILD_MANIFEST_OVERRIDE="$(resolve_path "$2")"; SKIP_BUILD=true; shift 2 ;;
    --deploy-manifest)
      DEPLOY_MANIFEST_OVERRIDE="$(resolve_path "$2")"; SKIP_DEPLOY=true; shift 2 ;;
    --help|-h)
      usage; exit 0 ;;
    *)
      fail "Unknown argument: $1" ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

require_command gcloud
require_command jq
require_command python3
require_command git
require_command curl
require_command awk

CONFIG_FILE="config/infrastructure/headhunter-${ENVIRONMENT}.env"
if [[ ! -f "$CONFIG_FILE" ]]; then
  if [[ "$ENVIRONMENT" != "production" ]]; then
    warn "Configuration file ${CONFIG_FILE} not found; falling back to production config."
  fi
  CONFIG_FILE="config/infrastructure/headhunter-production.env"
fi
if [[ ! -f "$CONFIG_FILE" ]]; then
  fail "Infrastructure configuration file not found."
fi

CLI_PROJECT_ID="$PROJECT_ID"
set -a
source "$CONFIG_FILE"
set +a
if [[ -n "$CLI_PROJECT_ID" ]]; then
  PROJECT_ID="$CLI_PROJECT_ID"
fi
if [[ -z "$PROJECT_ID" ]]; then
  fail "Project ID could not be determined. Provide via --project-id or config."
fi

REGION="${REGION:-us-central1}"
LOAD_TEST_TENANT="${LOAD_TEST_TENANT:-tenant-alpha}"
GIT_SHA="$(git rev-parse --short HEAD)"
GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

if [[ "$ALLOW_DIRTY" != true ]]; then
  if [[ -n $(git status --porcelain) ]]; then
    fail "Working tree has uncommitted changes. Commit or use --allow-dirty."
  fi
fi

ACTIVE_ACCOUNT=$(gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>/dev/null || true)
if [[ -z "$ACTIVE_ACCOUNT" ]]; then
  fail "No active gcloud account found. Run 'gcloud auth login'."
fi

log "Using project ${PROJECT_ID} (region ${REGION}) as ${ACTIVE_ACCOUNT}"

mkdir -p "$REPORT_DIR" \
  "$REPORT_DIR/build-logs" \
  "$REPORT_DIR/deploy-logs" \
  "$REPORT_DIR/test-reports" \
  "$REPORT_DIR/error-logs" \
  "$REPORT_DIR/manifests"

DEPLOY_TIMESTAMP="$(date -u +'%Y%m%d-%H%M%S')"
PRE_DEPLOY_SNAPSHOT="$REPORT_DIR/manifests/pre-deploy-revisions-${DEPLOY_TIMESTAMP}.json"
PRE_GATEWAY_CONFIG="$REPORT_DIR/manifests/pre-gateway-config-${DEPLOY_TIMESTAMP}.json"
MASTER_MANIFEST_PATH="$REPORT_DIR/manifests/deployment-${DEPLOY_TIMESTAMP}.json"
MASTER_REPORT_MD="docs/deployment-report-${DEPLOY_TIMESTAMP}.md"
STEP_SUMMARY_FILE="$REPORT_DIR/manifests/steps-${DEPLOY_TIMESTAMP}.txt"
STEP_DURATIONS_FILE="$REPORT_DIR/manifests/step-durations-${DEPLOY_TIMESTAMP}.txt"
: >"$STEP_SUMMARY_FILE"
: >"$STEP_DURATIONS_FILE"

SERVICES_LIST=(hh-embed-svc hh-rerank-svc hh-evidence-svc hh-eco-svc hh-msgs-svc hh-search-svc hh-enrich-svc hh-admin-svc)

check_infrastructure() {
  warn "Running pre-flight infrastructure checks"
  local missing=0
  if ! gcloud sql instances describe "$SQL_INSTANCE" --project "$PROJECT_ID" --quiet >/dev/null 2>&1; then
    warn "Cloud SQL instance ${SQL_INSTANCE} not reachable"
    missing=$((missing+1))
  fi
  if [[ -n "${REDIS_INSTANCE:-}" ]]; then
    if ! gcloud redis instances describe "$REDIS_INSTANCE" --region "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
      warn "Redis instance ${REDIS_INSTANCE} not reachable"
      missing=$((missing+1))
    fi
  fi
  for secret_var in SECRET_DB_PRIMARY SECRET_OAUTH_CLIENT SECRET_TOGETHER_AI SECRET_REDIS_ENDPOINT; do
    local secret_name="${!secret_var:-}"
    if [[ -n "$secret_name" ]]; then
      if ! gcloud secrets describe "$secret_name" --project "$PROJECT_ID" >/dev/null 2>&1; then
        warn "Required secret ${secret_name} not found"
        missing=$((missing+1))
      fi
    fi
  done
  if (( missing > 0 )); then
    warn "Infrastructure validation detected ${missing} issues."
  else
    log "Infrastructure validation complete"
  fi
}

check_infrastructure

capture_service_revisions() {
  local output
  output=$(python3 - <<'PY' "$PROJECT_ID" "$REGION" "$ENVIRONMENT" "${SERVICES_LIST[*]}" "$PRE_DEPLOY_SNAPSHOT"
import json
import subprocess
import sys

project_id, region, environment, services_csv, output_path = sys.argv[1:6]
services = services_csv.split()
records = []
for service in services:
    name = f"{service}-{environment}"
    try:
        data = subprocess.check_output([
            'gcloud', 'run', 'services', 'describe', name,
            '--platform=managed', '--region', region,
            '--project', project_id, '--format=json'
        ], stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        continue
    svc = json.loads(data)
    status = svc.get('status', {})
    records.append({
        'service': service,
        'name': name,
        'latestReadyRevision': status.get('latestReadyRevisionName'),
        'traffic': status.get('traffic'),
    })
with open(output_path, 'w', encoding='utf-8') as fh:
    json.dump(records, fh, indent=2)
PY
)
  if [[ -n "$output" ]]; then
    log "Captured existing service revisions snapshot"
  fi
}

capture_gateway_config() {
  local gateway_id="headhunter-api-gateway-${ENVIRONMENT}"
  local data
  data=$(gcloud api-gateway gateways describe "$gateway_id" --location "$REGION" --project "$PROJECT_ID" --format=json 2>/dev/null || true)
  if [[ -n "$data" ]]; then
    printf '%s' "$data" >"$PRE_GATEWAY_CONFIG"
    log "Captured current gateway configuration"
  fi
}

if [[ "$SKIP_DEPLOY" != true ]]; then
  capture_service_revisions
fi
if [[ "$SKIP_GATEWAY" != true ]]; then
  capture_gateway_config
fi

BUILD_MANIFEST_PATH="$BUILD_MANIFEST_OVERRIDE"
DEPLOY_MANIFEST_PATH="$DEPLOY_MANIFEST_OVERRIDE"
GATEWAY_SNAPSHOT_PATH=""
SMOKE_REPORT_PATH=""
GATEWAY_SUMMARY_LOG=""
MONITORING_OUTPUT_DIR=""
MONITORING_MANIFEST_PATH=""
LOAD_TEST_REPORT_PATH=""
LOAD_TEST_SLA_PATH=""
LOAD_TEST_SUMMARY_PATH=""
GATEWAY_ENDPOINT_URL=""

run_step() {
  local name="$1"
  local -n command_ref="$2"
  local log_file="$3"
  local output_var="$4"
  local start end duration
  log "Starting ${name}"
  start=$(date +%s)
  local output
  if ! output=$(${command_ref[@]} 2>&1 | tee "$log_file"); then
    end=$(date +%s)
    duration=$((end - start))
    printf '%s|%s|%s\n' "$name" "failed" "$log_file" >>"$STEP_SUMMARY_FILE"
    printf '%s|%s\n' "$name" "$duration" >>"$STEP_DURATIONS_FILE"
    printf '%s\n' "$output" >"${log_file%.log}.err"
    return 1
  fi
  end=$(date +%s)
  duration=$((end - start))
  printf '%s|%s|%s\n' "$name" "success" "$log_file" >>"$STEP_SUMMARY_FILE"
  printf '%s|%s\n' "$name" "$duration" >>"$STEP_DURATIONS_FILE"
  printf -v "$output_var" '%s' "$output"
  return 0
}

parse_value() {
  local text="$1"
  local pattern="$2"
  echo "$text" | awk -F": " -v pat="$pattern" '$1==pat {print $2}' | tail -n1
}

run_build() {
  if [[ "$SKIP_BUILD" == true ]]; then
    log "Skipping build step"
    printf '%s|%s|%s\n' "Build container images" "skipped" "-" >>"$STEP_SUMMARY_FILE"
    printf '%s|%s\n' "Build container images" "0" >>"$STEP_DURATIONS_FILE"
    return 0
  fi
  local log_file="$REPORT_DIR/build-logs/master-build-${DEPLOY_TIMESTAMP}.log"
  local cmd=("$SCRIPT_DIR/build-and-push-services.sh" --project-id "$PROJECT_ID" --environment "$ENVIRONMENT" --services "$SERVICES_ARG")
  if [[ "$PARALLEL_BUILD" == true ]]; then
    cmd+=(--parallel)
  fi
  if [[ "$SKIP_TESTS" == true ]]; then
    cmd+=(--skip-tests)
  fi
  if [[ "$DRY_RUN" == true ]]; then
    cmd+=(--dry-run)
  fi
  local output=""
  if ! run_step "Build container images" cmd "$log_file" output; then
    return 1
  fi
  local manifest
  manifest=$(echo "$output" | awk '/Manifest:/ {print $2}' | tail -n1)
  if [[ -z "$manifest" ]]; then
    manifest=$(echo "$output" | awk '/Build manifest saved to/ {print $5}' | tail -n1)
  fi
  if [[ -z "$manifest" ]]; then
    warn "Unable to parse build manifest path from build output"
  else
    BUILD_MANIFEST_PATH="$manifest"
    log "Build manifest: ${BUILD_MANIFEST_PATH}"
  fi
  return 0
}

run_deploy() {
  if [[ "$SKIP_DEPLOY" == true ]]; then
    log "Skipping Cloud Run deployment"
    printf '%s|%s|%s\n' "Deploy Cloud Run services" "skipped" "-" >>"$STEP_SUMMARY_FILE"
    printf '%s|%s\n' "Deploy Cloud Run services" "0" >>"$STEP_DURATIONS_FILE"
    return 0
  fi
  if [[ -z "$BUILD_MANIFEST_PATH" || ! -f "$BUILD_MANIFEST_PATH" ]]; then
    warn "Build manifest missing; Cloud Run deployment will use latest tags."
  fi
  local log_file="$REPORT_DIR/deploy-logs/master-deploy-${DEPLOY_TIMESTAMP}.log"
  local cmd=("$SCRIPT_DIR/deploy-cloud-run-services.sh" --project-id "$PROJECT_ID" --environment "$ENVIRONMENT" --services "$SERVICES_ARG")
  if [[ -n "$BUILD_MANIFEST_PATH" ]]; then
    cmd+=(--manifest "$BUILD_MANIFEST_PATH")
  fi
  if [[ "$DRY_RUN" == true ]]; then
    cmd+=(--dry-run)
  fi
  local output=""
  if ! run_step "Deploy Cloud Run services" cmd "$log_file" output; then
    return 1
  fi
  local manifest
  manifest=$(echo "$output" | awk '/Deployment manifest:/ {print $3}' | tail -n1)
  if [[ -z "$manifest" ]]; then
    manifest=$(echo "$output" | awk '/Deployment manifest saved to/ {print $5}' | tail -n1)
  fi
  if [[ -n "$manifest" ]]; then
    DEPLOY_MANIFEST_PATH="$manifest"
    log "Deployment manifest: ${DEPLOY_MANIFEST_PATH}"
  fi
  return 0
}

run_gateway() {
  if [[ "$SKIP_GATEWAY" == true ]]; then
    log "Skipping gateway update"
    printf '%s|%s|%s\n' "Update API Gateway" "skipped" "-" >>"$STEP_SUMMARY_FILE"
    printf '%s|%s\n' "Update API Gateway" "0" >>"$STEP_DURATIONS_FILE"
    return 0
  fi
  if [[ -z "$DEPLOY_MANIFEST_PATH" || ! -f "$DEPLOY_MANIFEST_PATH" ]]; then
    warn "Deploy manifest missing; gateway update may not have service URLs."
  fi
  local log_file="$REPORT_DIR/deploy-logs/gateway-update-${DEPLOY_TIMESTAMP}.log"
  local cmd=("$SCRIPT_DIR/update-gateway-routes.sh" --project-id "$PROJECT_ID" --environment "$ENVIRONMENT" --manifest "$DEPLOY_MANIFEST_PATH")
  if [[ "$DRY_RUN" == true ]]; then
    cmd+=(--dry-run)
  fi
  local output=""
  if ! run_step "Update API Gateway" cmd "$log_file" output; then
    return 1
  fi
  local snapshot
  snapshot=$(echo "$output" | awk '/Gateway configuration snapshot saved to/ {print $6}' | tail -n1)
  if [[ -n "$snapshot" ]]; then
    GATEWAY_SNAPSHOT_PATH="$snapshot"
  fi
  local summary
  summary=$(echo "$output" | awk '/Summary recorded at/ {print $4}' | tail -n1)
  if [[ -n "$summary" ]]; then
    GATEWAY_SUMMARY_LOG="$summary"
  fi
  if [[ -f "$GATEWAY_SUMMARY_LOG" ]]; then
    local host
    host=$(awk -F': ' '/Gateway Host/ {print $2}' "$GATEWAY_SUMMARY_LOG" | tail -n1)
    if [[ -n "$host" ]]; then
      GATEWAY_ENDPOINT_URL="https://${host}"
    fi
  fi
  return 0
}

run_smoke() {
  if [[ "$SKIP_SMOKE" == true ]]; then
    log "Skipping smoke tests"
    printf '%s|%s|%s\n' "Smoke tests" "skipped" "-" >>"$STEP_SUMMARY_FILE"
    printf '%s|%s\n' "Smoke tests" "0" >>"$STEP_DURATIONS_FILE"
    return 0
  fi
  local log_file="$REPORT_DIR/test-reports/smoke-tests-${DEPLOY_TIMESTAMP}.log"
  local cmd=("$SCRIPT_DIR/smoke-test-deployment.sh" --project-id "$PROJECT_ID" --environment "$ENVIRONMENT" --mode ${MODE_OVERRIDE:-full})
  if [[ -n "$DEPLOY_MANIFEST_PATH" ]]; then
    cmd+=(--manifest "$DEPLOY_MANIFEST_PATH")
  fi
  if [[ -f "$GATEWAY_SUMMARY_LOG" ]]; then
    local host
    host=$(awk -F': ' '/Gateway Host/ {print $2}' "$GATEWAY_SUMMARY_LOG" | tail -n1)
    if [[ -n "$host" ]]; then
      GATEWAY_ENDPOINT_URL="https://${host}"
      cmd+=(--gateway-endpoint "$GATEWAY_ENDPOINT_URL")
    fi
  fi
  if [[ "$DRY_RUN" == true ]]; then
    warn "Smoke tests are skipped in dry-run mode"
    printf '%s|%s|%s\n' "Smoke tests" "skipped" "dry-run" >>"$STEP_SUMMARY_FILE"
    printf '%s|%s\n' "Smoke tests" "0" >>"$STEP_DURATIONS_FILE"
    return 0
  fi
  local output=""
  if ! run_step "Smoke tests" cmd "$log_file" output; then
    SMOKE_REPORT_PATH=$(echo "$output" | awk '/Smoke test report saved to/ {print $6}' | tail -n1)
    return 1
  fi
  SMOKE_REPORT_PATH=$(echo "$output" | awk '/Smoke test report saved to/ {print $6}' | tail -n1)
  return 0
}

run_monitoring_setup() {
  if [[ "$SKIP_MONITORING" == true ]]; then
    log "Skipping monitoring setup"
    printf '%s|%s|%s\n' "Monitoring setup" "skipped" "-" >>"$STEP_SUMMARY_FILE"
    printf '%s|%s\n' "Monitoring setup" "0" >>"$STEP_DURATIONS_FILE"
    return 0
  fi
  MONITORING_OUTPUT_DIR=".monitoring/setup-${DEPLOY_TIMESTAMP}"
  local log_file="$REPORT_DIR/deploy-logs/monitoring-setup-${DEPLOY_TIMESTAMP}.log"
  mkdir -p "$MONITORING_OUTPUT_DIR"
  local cmd=("$SCRIPT_DIR/setup-monitoring-and-alerting.sh" --project-id "$PROJECT_ID" --environment "$ENVIRONMENT" --region "$REGION" --output-dir "$MONITORING_OUTPUT_DIR")
  if [[ -n "$NOTIFICATION_CHANNELS" ]]; then
    cmd+=(--notification-channels "$NOTIFICATION_CHANNELS")
  fi
  if [[ "$DRY_RUN" == true ]]; then
    cmd+=(--dry-run)
  fi
  local output=""
  if ! run_step "Monitoring setup" cmd "$log_file" output; then
    if [[ -f "$MONITORING_OUTPUT_DIR/monitoring-manifest.json" ]]; then
      MONITORING_MANIFEST_PATH="$MONITORING_OUTPUT_DIR/monitoring-manifest.json"
    fi
    return 1
  fi
  MONITORING_MANIFEST_PATH=$(echo "$output" | awk '/monitoring-manifest\.json/ {print $NF}' | tail -n1)
  if [[ -z "$MONITORING_MANIFEST_PATH" && -f "$MONITORING_OUTPUT_DIR/monitoring-manifest.json" ]]; then
    MONITORING_MANIFEST_PATH="$MONITORING_OUTPUT_DIR/monitoring-manifest.json"
  fi
  return 0
}

resolve_gateway_endpoint() {
  if [[ -n "$GATEWAY_ENDPOINT_URL" ]]; then
    return 0
  fi
  if [[ -f "$GATEWAY_SUMMARY_LOG" ]]; then
    local host
    host=$(awk -F': ' '/Gateway Host/ {print $2}' "$GATEWAY_SUMMARY_LOG" | tail -n1)
    if [[ -n "$host" ]]; then
      GATEWAY_ENDPOINT_URL="https://${host}"
      return 0
    fi
  fi
  local fallback
  fallback=$(gcloud api-gateway gateways describe "headhunter-api-gateway-${ENVIRONMENT}" --location "$REGION" --project "$PROJECT_ID" --format='value(defaultHostname)' 2>/dev/null || true)
  if [[ -n "$fallback" ]]; then
    GATEWAY_ENDPOINT_URL="https://${fallback}"
    return 0
  fi
  return 1
}

run_load_tests() {
  if [[ "$SKIP_LOAD_TESTS" == true ]]; then
    log "Skipping post-deployment load tests"
    printf '%s|%s|%s\n' "Post-deployment load tests" "skipped" "-" >>"$STEP_SUMMARY_FILE"
    printf '%s|%s\n' "Post-deployment load tests" "0" >>"$STEP_DURATIONS_FILE"
    return 0
  fi
  if [[ "$DRY_RUN" == true ]]; then
    warn "Load tests are skipped in dry-run mode"
    printf '%s|%s|%s\n' "Post-deployment load tests" "skipped" "dry-run" >>"$STEP_SUMMARY_FILE"
    printf '%s|%s\n' "Post-deployment load tests" "0" >>"$STEP_DURATIONS_FILE"
    return 0
  fi
  if ! resolve_gateway_endpoint; then
    warn "Unable to resolve gateway endpoint for load tests"
  fi
  local load_test_dir=".deployment/load-tests/post-deploy-${DEPLOY_TIMESTAMP}"
  local log_file="$REPORT_DIR/test-reports/load-tests-${DEPLOY_TIMESTAMP}.log"
  local cmd=("$SCRIPT_DIR/run-post-deployment-load-tests.sh" --gateway-endpoint "${GATEWAY_ENDPOINT_URL:-https://undefined}" --tenant-id "$LOAD_TEST_TENANT" --duration "$LOAD_TEST_DURATION" --concurrency "$LOAD_TEST_CONCURRENCY" --output-dir "$load_test_dir")
  local output=""
  if ! run_step "Post-deployment load tests" cmd "$log_file" output; then
    LOAD_TEST_REPORT_PATH=$(echo "$output" | awk '/JSON report:/ {print $NF}' | tail -n1)
    LOAD_TEST_SUMMARY_PATH=$(echo "$output" | awk '/Markdown report:/ {print $NF}' | tail -n1)
    LOAD_TEST_SLA_PATH=$(echo "$output" | awk '/SLA validation:/ {print $NF}' | tail -n1)
    if [[ -z "$LOAD_TEST_REPORT_PATH" && -f "$load_test_dir/load-test-report.json" ]]; then
      LOAD_TEST_REPORT_PATH="$load_test_dir/load-test-report.json"
    fi
    if [[ -z "$LOAD_TEST_SUMMARY_PATH" && -f "$load_test_dir/load-test-report.md" ]]; then
      LOAD_TEST_SUMMARY_PATH="$load_test_dir/load-test-report.md"
    fi
    if [[ -z "$LOAD_TEST_SLA_PATH" && -f "$load_test_dir/results/sla-validation.json" ]]; then
      LOAD_TEST_SLA_PATH="$load_test_dir/results/sla-validation.json"
    fi
    return 1
  fi
  LOAD_TEST_REPORT_PATH=$(echo "$output" | awk '/JSON report:/ {print $NF}' | tail -n1)
  if [[ -z "$LOAD_TEST_REPORT_PATH" && -f "$load_test_dir/load-test-report.json" ]]; then
    LOAD_TEST_REPORT_PATH="$load_test_dir/load-test-report.json"
  fi
  LOAD_TEST_SUMMARY_PATH=$(echo "$output" | awk '/Markdown report:/ {print $NF}' | tail -n1)
  if [[ -z "$LOAD_TEST_SUMMARY_PATH" && -f "$load_test_dir/load-test-report.md" ]]; then
    LOAD_TEST_SUMMARY_PATH="$load_test_dir/load-test-report.md"
  fi
  LOAD_TEST_SLA_PATH=$(echo "$output" | awk '/SLA validation:/ {print $NF}' | tail -n1)
  if [[ -z "$LOAD_TEST_SLA_PATH" && -f "$load_test_dir/results/sla-validation.json" ]]; then
    LOAD_TEST_SLA_PATH="$load_test_dir/results/sla-validation.json"
  fi
  return 0
}

generate_deployment_report() {
  local include_blockers="${1:-false}"
  if [[ "$GENERATE_REPORT" != true ]]; then
    REPORT_GENERATION_STATUS="skipped"
    REPORT_GENERATION_MESSAGE="Report generation disabled"
    return 0
  fi

  local generator="${SCRIPT_DIR}/generate-deployment-report.sh"
  if [[ ! -x "$generator" ]]; then
    REPORT_GENERATION_STATUS="failed"
    REPORT_GENERATION_MESSAGE="Generator script missing at ${generator}"
    warn "Deployment report generator not found at ${generator}"
    return 1
  fi

  local output_path
  if [[ -n "$REPORT_OUTPUT" ]]; then
    if [[ "$REPORT_OUTPUT" == /* ]]; then
      output_path="$REPORT_OUTPUT"
    else
      output_path="${PROJECT_ROOT}/${REPORT_OUTPUT}"
    fi
  else
    output_path="${PROJECT_ROOT}/${MASTER_REPORT_MD}"
  fi
  REPORT_OUTPUT_PATH="$output_path"

  local args=("$generator" --project-id "$PROJECT_ID" --environment "$ENVIRONMENT" --region "$REGION" --output "$output_path")
  if [[ -n "$DEPLOY_MANIFEST_PATH" && -f "$DEPLOY_MANIFEST_PATH" ]]; then
    args+=(--deployment-manifest "$DEPLOY_MANIFEST_PATH")
  fi
  if [[ -n "$MONITORING_MANIFEST_PATH" && -f "$MONITORING_MANIFEST_PATH" ]]; then
    args+=(--monitoring-manifest "$MONITORING_MANIFEST_PATH")
  fi
  if [[ -n "$LOAD_TEST_REPORT_PATH" && -f "$LOAD_TEST_REPORT_PATH" ]]; then
    args+=(--load-test-report "$LOAD_TEST_REPORT_PATH")
  fi
  if [[ "$include_blockers" == true ]]; then
    args+=(--include-blockers)
  fi
  if [[ -n "$ACTIVE_ACCOUNT" ]]; then
    args+=(--operator "$ACTIVE_ACCOUNT")
  fi

  local report_log="$REPORT_DIR/deploy-logs/report-generation-${DEPLOY_TIMESTAMP}.log"
  if "${args[@]}" >"$report_log" 2>&1; then
    REPORT_GENERATION_STATUS="success"
    REPORT_GENERATION_MESSAGE="Report written to ${output_path}"
    return 0
  fi

  REPORT_GENERATION_STATUS="failed"
  REPORT_GENERATION_MESSAGE="Report generation failed (see ${report_log})"
  warn "Deployment report generation failed; review ${report_log}"
  return 1
}

MODE_OVERRIDE="${SMOKE_MODE:-full}"

if ! run_build; then
  if [[ "$ROLLBACK_ON_FAILURE" == true ]]; then
    warn "Build failed; rollback not required."
  fi
  generate_deployment_report true || true
  fail "Build step failed"
fi

if ! run_deploy; then
  if [[ "$ROLLBACK_ON_FAILURE" == true && "$DRY_RUN" != true ]]; then
    warn "Deployment failed; attempting rollback"
    python3 - <<'PY' "$PRE_DEPLOY_SNAPSHOT" "$PROJECT_ID" "$REGION" "$ENVIRONMENT"
import json
import subprocess
import sys

snapshot_path, project_id, region, environment = sys.argv[1:5]
try:
    with open(snapshot_path, 'r', encoding='utf-8') as fh:
        records = json.load(fh)
except FileNotFoundError:
    sys.exit(0)
for record in records:
    service = record.get('name')
    revision = record.get('latestReadyRevision')
    traffic = record.get('traffic')
    if not service or not revision:
        continue
    try:
        subprocess.check_call([
            'gcloud', 'run', 'services', 'update-traffic', service,
            '--platform=managed', '--region', region,
            '--project', project_id,
            f'--to-revisions={revision}=100'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        pass
PY
  fi
  generate_deployment_report true || true
  fail "Cloud Run deployment failed"
fi

if ! run_gateway; then
  if [[ "$ROLLBACK_ON_FAILURE" == true && "$DRY_RUN" != true ]]; then
    warn "Gateway update failed; attempting configuration rollback"
    if [[ -f "$PRE_GATEWAY_CONFIG" ]]; then
      PREVIOUS_CONFIG_ID=$(jq -r '.apiConfig // empty' "$PRE_GATEWAY_CONFIG")
      if [[ -n "$PREVIOUS_CONFIG_ID" ]]; then
        warn "Restoring API Gateway to ${PREVIOUS_CONFIG_ID}"
        gcloud api-gateway gateways update "headhunter-api-gateway-${ENVIRONMENT}" \
          --location "$REGION" \
          --api-config "$PREVIOUS_CONFIG_ID" \
          --project "$PROJECT_ID" \
          --quiet || warn "Gateway rollback failed"
      fi
    fi
  fi
  generate_deployment_report true || true
  fail "Gateway update failed"
fi

if ! run_smoke; then
  if [[ "$ROLLBACK_ON_FAILURE" == true && "$DRY_RUN" != true ]]; then
    warn "Smoke tests failed; attempting rollback"
    python3 - <<'PY' "$PRE_DEPLOY_SNAPSHOT" "$PROJECT_ID" "$REGION" "$ENVIRONMENT"
import json
import subprocess
import sys

snapshot_path, project_id, region, environment = sys.argv[1:5]
try:
    with open(snapshot_path, 'r', encoding='utf-8') as fh:
        records = json.load(fh)
except FileNotFoundError:
    sys.exit(0)
for record in records:
    service = record.get('name')
    revision = record.get('latestReadyRevision')
    if not service or not revision:
        continue
    try:
        subprocess.check_call([
            'gcloud', 'run', 'services', 'update-traffic', service,
            '--platform=managed', '--region', region,
            '--project', project_id,
            f'--to-revisions={revision}=100'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        pass
PY
    if [[ -f "$PRE_GATEWAY_CONFIG" ]]; then
      PREVIOUS_CONFIG_ID=$(jq -r '.apiConfig // empty' "$PRE_GATEWAY_CONFIG")
      if [[ -n "$PREVIOUS_CONFIG_ID" ]]; then
        warn "Restoring API Gateway to ${PREVIOUS_CONFIG_ID}"
        gcloud api-gateway gateways update "headhunter-api-gateway-${ENVIRONMENT}" \
          --location "$REGION" \
          --api-config "$PREVIOUS_CONFIG_ID" \
          --project "$PROJECT_ID" \
          --quiet || warn "Gateway rollback failed"
      fi
    fi
  fi
  generate_deployment_report true || true
  fail "Smoke tests failed"
fi

MONITORING_SETUP_FAILED=false
if ! run_monitoring_setup; then
  MONITORING_SETUP_FAILED=true
  warn "Monitoring setup encountered errors; review ${REPORT_DIR}/deploy-logs/monitoring-setup-${DEPLOY_TIMESTAMP}.log or ${MONITORING_OUTPUT_DIR}" || true
fi

if ! run_load_tests; then
  if [[ "$ROLLBACK_ON_FAILURE" == true && "$DRY_RUN" != true ]]; then
    warn "Load tests failed; attempting rollback"
    python3 - <<'PY' "$PRE_DEPLOY_SNAPSHOT" "$PROJECT_ID" "$REGION" "$ENVIRONMENT"
import json
import subprocess
import sys

snapshot_path, project_id, region, environment = sys.argv[1:5]
try:
    with open(snapshot_path, 'r', encoding='utf-8') as fh:
        records = json.load(fh)
except FileNotFoundError:
    sys.exit(0)
for record in records:
    service = record.get('name')
    revision = record.get('latestReadyRevision')
    if not service or not revision:
        continue
    try:
        subprocess.check_call([
            'gcloud', 'run', 'services', 'update-traffic', service,
            '--platform=managed', '--region', region,
            '--project', project_id,
            f'--to-revisions={revision}=100'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        pass
PY
    if [[ -f "$PRE_GATEWAY_CONFIG" ]]; then
      PREVIOUS_CONFIG_ID=$(jq -r '.apiConfig // empty' "$PRE_GATEWAY_CONFIG")
      if [[ -n "$PREVIOUS_CONFIG_ID" ]]; then
        warn "Restoring API Gateway to ${PREVIOUS_CONFIG_ID}"
        gcloud api-gateway gateways update "headhunter-api-gateway-${ENVIRONMENT}" \
          --location "$REGION" \
          --api-config "$PREVIOUS_CONFIG_ID" \
          --project "$PROJECT_ID" \
          --quiet || warn "Gateway rollback failed"
      fi
    fi
  fi
  generate_deployment_report true || true
  fail "Post-deployment load tests failed"
fi

log "Generating deployment manifest ${MASTER_MANIFEST_PATH}"
python3 - <<'PY' "$MASTER_MANIFEST_PATH" "$PROJECT_ID" "$ENVIRONMENT" "$REGION" "$GIT_SHA" "$GIT_BRANCH" "$BUILD_MANIFEST_PATH" "$DEPLOY_MANIFEST_PATH" "$GATEWAY_SNAPSHOT_PATH" "$SMOKE_REPORT_PATH" "$MONITORING_MANIFEST_PATH" "$LOAD_TEST_REPORT_PATH" "$LOAD_TEST_SUMMARY_PATH" "$LOAD_TEST_SLA_PATH" "$GATEWAY_ENDPOINT_URL" "$STEP_SUMMARY_FILE" "$STEP_DURATIONS_FILE"
import json
import os
import sys
from datetime import datetime


(output_path, project_id, environment, region, git_sha, git_branch,
 build_manifest, deploy_manifest, gateway_snapshot, smoke_report,
 monitoring_manifest, load_test_report, load_test_summary, load_test_sla,
 gateway_endpoint, step_summary_path, step_durations_path) = sys.argv[1:17]

steps = []
with open(step_summary_path, 'r', encoding='utf-8') as fh:
    for raw in fh:
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split('|', 2)
        if len(parts) == 3:
            steps.append({'name': parts[0], 'status': parts[1], 'log': parts[2]})

durations = {}
with open(step_durations_path, 'r', encoding='utf-8') as fh:
    for raw in fh:
        raw = raw.strip()
        if not raw:
            continue
        name, value = raw.split('|', 1)
        try:
            durations[name] = int(value)
        except ValueError:
            continue

manifest = {
    'generatedAt': datetime.utcnow().isoformat() + 'Z',
    'projectId': project_id,
    'environment': environment,
    'region': region,
    'gatewayEndpoint': gateway_endpoint if gateway_endpoint else None,
    'git': {
        'sha': git_sha,
        'branch': git_branch,
    },
    'artifacts': {
        'buildManifest': build_manifest if build_manifest else None,
        'deployManifest': deploy_manifest if deploy_manifest else None,
        'gatewaySnapshot': gateway_snapshot if gateway_snapshot else None,
        'smokeReport': smoke_report if smoke_report else None,
        'monitoringManifest': monitoring_manifest if monitoring_manifest else None,
        'loadTestReport': load_test_report if load_test_report else None,
        'loadTestSummary': load_test_summary if load_test_summary else None,
        'loadTestSlaReport': load_test_sla if load_test_sla else None,
    },
    'steps': steps,
    'durations': durations,
}
with open(output_path, 'w', encoding='utf-8') as fh:
    json.dump(manifest, fh, indent=2)
PY

if ! generate_deployment_report false; then
  summary_target=""
  if [[ -n "$REPORT_OUTPUT" ]]; then
    if [[ "$REPORT_OUTPUT" == /* ]]; then
      summary_target="$REPORT_OUTPUT"
    else
      summary_target="${PROJECT_ROOT}/${REPORT_OUTPUT}"
    fi
  else
    summary_target="${PROJECT_ROOT}/${MASTER_REPORT_MD}"
  fi
  REPORT_OUTPUT_PATH="$summary_target"
  mkdir -p "$(dirname "$summary_target")"
  if [[ "$REPORT_GENERATION_STATUS" == "failed" ]]; then
    warn "Falling back to minimal deployment summary at ${summary_target}"
  else
    log "Report generation disabled; writing minimal summary to ${summary_target}"
  fi
  python3 - <<'PY' "$MASTER_MANIFEST_PATH" "$summary_target"
import json
import sys

manifest_path, report_path = sys.argv[1:3]
with open(manifest_path, 'r', encoding='utf-8') as fh:
    data = json.load(fh)

lines = []
lines.append(f"# Production Deployment Summary ({data['environment']})")
lines.append("")
lines.append(f"- Generated: {data['generatedAt']}")
lines.append(f"- Project: {data['projectId']} ({data['region']})")
lines.append(f"- Git: `{data['git']['sha']}` on `{data['git']['branch']}`")
lines.append("")
lines.append("## Step Results")
for step in data['steps']:
    lines.append(f"- **{step['name']}** — {step['status']} ({step['log']})")
lines.append("")
lines.append("## Artifacts")
for key, value in data['artifacts'].items():
    if value:
        lines.append(f"- {key}: `{value}`")
lines.append("")
lines.append("## Durations (seconds)")
for name, seconds in data.get('durations', {}).items():
    lines.append(f"- {name}: {seconds}")

with open(report_path, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(lines) + '\n')
PY
  REPORT_GENERATION_MESSAGE="Minimal summary written to ${summary_target}"
else
  : # Report already generated via helper
fi

if [[ -n "$REPORT_OUTPUT_PATH" ]]; then
  REPORT_OUTPUT_RELATIVE="${REPORT_OUTPUT_PATH#${PROJECT_ROOT}/}"
else
  REPORT_OUTPUT_RELATIVE=""
fi

python3 - <<'PY' "$MASTER_MANIFEST_PATH" "$REPORT_GENERATION_STATUS" "$REPORT_OUTPUT_RELATIVE" "$REPORT_GENERATION_MESSAGE" "$REPORT_OUTPUT_PATH"
import json
import os
import sys

manifest_path, status, relative_path, message, absolute_path = sys.argv[1:6]
with open(manifest_path, 'r', encoding='utf-8') as fh:
    data = json.load(fh)

report_entry = {
    'status': status,
    'path': relative_path or None,
    'absolutePath': absolute_path or None,
    'message': message or None,
}

data['report'] = report_entry

with open(manifest_path, 'w', encoding='utf-8') as fh:
    json.dump(data, fh, indent=2)
    fh.write('\n')
PY

if [[ "$DRY_RUN" != true ]]; then
  DEPLOY_TAG="deploy-${ENVIRONMENT}-${DEPLOY_TIMESTAMP}"
  if git rev-parse "$DEPLOY_TAG" >/dev/null 2>&1; then
    warn "Git tag ${DEPLOY_TAG} already exists; skipping tag creation"
  else
    git tag "$DEPLOY_TAG"
    log "Created git tag ${DEPLOY_TAG}"
  fi
fi

log "Deployment succeeded"
if [[ "$MONITORING_SETUP_FAILED" == true ]]; then
  warn "Monitoring setup completed with warnings; inspect ${REPORT_DIR}/deploy-logs/monitoring-setup-${DEPLOY_TIMESTAMP}.log"
fi
log "Build manifest: ${BUILD_MANIFEST_PATH:-n/a}"
log "Deploy manifest: ${DEPLOY_MANIFEST_PATH:-n/a}"
log "Gateway snapshot: ${GATEWAY_SNAPSHOT_PATH:-n/a}"
log "Smoke report: ${SMOKE_REPORT_PATH:-n/a}"
log "Monitoring manifest: ${MONITORING_MANIFEST_PATH:-n/a}"
log "Load test report: ${LOAD_TEST_REPORT_PATH:-n/a}"
log "Load test summary: ${LOAD_TEST_SUMMARY_PATH:-n/a}"
log "Load test SLA: ${LOAD_TEST_SLA_PATH:-n/a}"
log "Master manifest: ${MASTER_MANIFEST_PATH}"
if [[ -n "$REPORT_OUTPUT_RELATIVE" ]]; then
  log "Deployment report: ${REPORT_OUTPUT_RELATIVE} (${REPORT_GENERATION_STATUS})"
else
  log "Deployment report: n/a (${REPORT_GENERATION_STATUS})"
fi
if [[ -n "$REPORT_GENERATION_MESSAGE" ]]; then
  log "$REPORT_GENERATION_MESSAGE"
fi
if [[ -n "$REPORT_OUTPUT_RELATIVE" ]]; then
  log "Review deployment report before sign-off: ${REPORT_OUTPUT_RELATIVE}"
  log "Regenerate report: ./scripts/generate-deployment-report.sh --project-id ${PROJECT_ID} --environment ${ENVIRONMENT} --region ${REGION} --output \"${REPORT_OUTPUT_RELATIVE}\""
fi

exit 0
