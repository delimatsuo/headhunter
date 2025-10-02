#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Master validator that orchestrates full local stack readiness checks.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="${ROOT_DIR}/scripts"

START_SCRIPT="${SCRIPTS_DIR}/start-docker-stack.sh"
INFRA_SCRIPT="${SCRIPTS_DIR}/test-infrastructure-health.sh"
SERVICES_SCRIPT="${SCRIPTS_DIR}/validate-all-services-health.sh"
COMM_SCRIPT="${SCRIPTS_DIR}/validate-service-communication.sh"
FIX_PY_SCRIPT="${SCRIPTS_DIR}/fix-python-environment.sh"
TEST_SCRIPT="${SCRIPTS_DIR}/run-integration-tests.sh"
REPORT_PATH="${ROOT_DIR}/.integration-report.json"

STEPS=(
  "start_stack"
  "infra_health"
  "service_health"
  "service_comm"
  "integration_tests"
)

STATUS=()
MESSAGES=()

log() {
  printf '[stack-readiness] %s\n' "$*"
}

record_result() {
  local step="$1"
  local status="$2"
  local message="$3"
  STATUS+=("${step}:${status}")
  MESSAGES+=("${step}:${message}")
}

run_step() {
  local name="$1"
  shift
  local cmd=("$@")
  log "Running step '${name}' -> ${cmd[*]}"
  if "${cmd[@]}"; then
    record_result "$name" "pass" "completed"
    log "Step '${name}' completed successfully"
    return 0
  fi
  local exit_code=$?
  record_result "$name" "fail" "exit ${exit_code}"
  log "Step '${name}' failed with exit code ${exit_code}"
  return "$exit_code"
}

ensure_executable() {
  local path="$1"
  if [[ ! -x "$path" ]]; then
    chmod +x "$path"
  fi
}

ensure_executable "$START_SCRIPT"
ensure_executable "$INFRA_SCRIPT"
ensure_executable "$SERVICES_SCRIPT"
ensure_executable "$COMM_SCRIPT"
ensure_executable "$FIX_PY_SCRIPT"
ensure_executable "$TEST_SCRIPT"

set +e
run_step "start_stack" "$START_SCRIPT"
if [[ ${STATUS[-1]} != *":pass" ]]; then
  log "Stack startup failed. Aborting readiness validation."
  set -e
  exit 1
fi

run_step "infra_health" "$INFRA_SCRIPT"
if [[ ${STATUS[-1]} != *":pass" ]]; then
  log "Infrastructure health check failed. Aborting."
  set -e
  exit 1
fi

run_step "service_health" "$SERVICES_SCRIPT"
if [[ ${STATUS[-1]} != *":pass" ]]; then
  log "Service health validation failed. Aborting."
  set -e
  exit 1
fi

run_step "service_comm" "$COMM_SCRIPT"
if [[ ${STATUS[-1]} != *":pass" ]]; then
  log "Service communication validation failed. Aborting."
  set -e
  exit 1
fi

# Integration tests with Python fix fallback
log "Executing integration tests"
if "$TEST_SCRIPT"; then
  record_result "integration_tests" "pass" "completed"
else
  log "Integration tests failed. Attempting Python environment remediation."
  "$FIX_PY_SCRIPT" || log "Python environment remediation failed"
  if "$TEST_SCRIPT"; then
    record_result "integration_tests" "pass" "passed_after_fix"
  else
    record_result "integration_tests" "fail" "tests_failed_after_fix"
  fi
fi
set -e

log "====================================================="
log "Validation summary:"
for status_line in "${STATUS[@]}"; do
  IFS=':' read -r step outcome <<<"${status_line}"
  printf '  - %s: %s\n' "$step" "$outcome"
done

if [[ -f "$REPORT_PATH" ]]; then
  log "Performance targets captured in ${REPORT_PATH}:"
  env REPORT_PATH="$REPORT_PATH" python3 - <<'PY'
import json
import os
import sys

report_path = os.getenv('REPORT_PATH')
if not report_path:
    sys.exit(0)
try:
    with open(report_path, 'r', encoding='utf-8') as handle:
        payload = json.load(handle)
except FileNotFoundError:
    sys.exit(0)
perf = payload.get('performance', {})
cache = perf.get('cache', {})
print(json.dumps({
    'stepLatencyP95Ms': perf.get('stepLatencyP95Ms'),
    'rerankLatencyMs': perf.get('rerankLatencyMs'),
    'cachedReadLatencyMs': perf.get('cachedReadLatencyMs'),
    'cacheHitRate': cache.get('hitRate'),
    'issues': payload.get('issues', []),
}, indent=2))
PY
fi

failure=false
for status_line in "${STATUS[@]}"; do
  if [[ "$status_line" == *":fail" ]]; then
    failure=true
    break
  fi
done

if [[ "$failure" == true ]]; then
  log "Stack readiness validation FAILED"
  exit 1
fi

log "Stack readiness validation PASSED"
