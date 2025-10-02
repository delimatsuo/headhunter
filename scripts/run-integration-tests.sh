#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Orchestrates the full integration test workflow for the local stack.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT_DIR
TEST_SCRIPT="${ROOT_DIR}/scripts/test-local-setup.sh"
ADDITIONAL_SCRIPT="${ROOT_DIR}/scripts/test-integration.sh"
REPORT_FILE="${ROOT_DIR}/.integration-report.json"
RUN_INTEGRATION_SCRIPT="${ROOT_DIR}/scripts/run_integration.py"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '[run-integration-tests][error] Missing required command: %s\n' "$1" >&2
    exit 1
  fi
}

log() {
  printf '[run-integration-tests] %s\n' "$*"
}

require_cmd python3

log "Validating local stack via test-local-setup"
if [[ -x "${TEST_SCRIPT}" ]]; then
  "${TEST_SCRIPT}"
else
  log "Validation script ${TEST_SCRIPT} not found or not executable; skipping infrastructure checks."
fi

log "Executing pytest integration suite"
PYTHONPATH="${ROOT_DIR}" python3 -m pytest tests/test_local_stack.py -v

if [[ -x "${ADDITIONAL_SCRIPT}" ]]; then
  log "Executing additional integration script ${ADDITIONAL_SCRIPT}"
  "${ADDITIONAL_SCRIPT}"
fi

generate_integration_report() {
  local report_path="$1"
  local generated=false

  if [[ -f "${RUN_INTEGRATION_SCRIPT}" ]]; then
    if PYTHONPATH="${ROOT_DIR}" python3 "${RUN_INTEGRATION_SCRIPT}" > "${report_path}"; then
      generated=true
    else
      log "WARN direct execution of run_integration.py failed; attempting module fallback"
    fi
  else
    log "run_integration.py not found at ${RUN_INTEGRATION_SCRIPT}; attempting module fallback"
  fi

  if [[ "${generated}" == "false" ]]; then
    if PYTHONPATH="${ROOT_DIR}" python3 -c 'from scripts.run_integration import main; main()' > "${report_path}"; then
      generated=true
    fi
  fi

  [[ "${generated}" == "true" ]]
}

log "Generating integration report"
PERF_REPORT_AVAILABLE=true
if ! generate_integration_report "${REPORT_FILE}"; then
  PERF_REPORT_AVAILABLE=false
  rm -f "${REPORT_FILE}" >/dev/null 2>&1 || true
  log "WARN integration performance report unavailable; skipping performance validation step."
fi

if [[ "${PERF_REPORT_AVAILABLE}" == "true" && -f "${REPORT_FILE}" ]]; then
  python3 - <<'PY'
import json
import os
import sys

root = os.getenv('ROOT_DIR') or '.'
report_path = os.path.join(root, '.integration-report.json')
try:
    with open(report_path, 'r', encoding='utf-8') as handle:
        report = json.load(handle)
except FileNotFoundError:
    print('[run-integration-tests] WARN integration report missing; skipping validation.')
    sys.exit(0)

perf = report.get('performance', {})
cache = perf.get('cache', {})
issues = report.get('issues', [])

thresholds = {
    'stepLatencyP95Ms': perf.get('targets', {}).get('stepLatencyP95Ms', 1200),
    'rerankLatencyMs': perf.get('targets', {}).get('rerankP95Ms', 350),
    'cachedReadLatencyMs': perf.get('targets', {}).get('cachedReadP95Ms', 250),
    'cacheHitRate': perf.get('targets', {}).get('cacheHitRate', 0.7),
}

failures = []
if perf.get('stepLatencyP95Ms') and perf['stepLatencyP95Ms'] > thresholds['stepLatencyP95Ms']:
    failures.append(f"Step latency p95 {perf['stepLatencyP95Ms']}ms exceeds {thresholds['stepLatencyP95Ms']}ms")
if perf.get('rerankLatencyMs') and perf['rerankLatencyMs'] > thresholds['rerankLatencyMs']:
    failures.append(f"Rerank latency {perf['rerankLatencyMs']}ms exceeds {thresholds['rerankLatencyMs']}ms")
if perf.get('cachedReadLatencyMs') and perf['cachedReadLatencyMs'] > thresholds['cachedReadLatencyMs']:
    failures.append(
        f"Cached read latency {perf['cachedReadLatencyMs']}ms exceeds {thresholds['cachedReadLatencyMs']}ms"
    )
hit_rate = cache.get('hitRate')
if hit_rate is not None and hit_rate < thresholds['cacheHitRate']:
    failures.append(f"Cache hit rate {hit_rate} below {thresholds['cacheHitRate']}")

if issues:
    failures.extend(issues)

if failures:
    print('[run-integration-tests] Performance validation failed:')
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)

print('[run-integration-tests] Integration test workflow completed successfully.')
PY
else
  log "Performance validation skipped: integration report not generated."
fi

if [[ "${PERF_REPORT_AVAILABLE}" == "true" ]]; then
  log "Integration report stored at ${REPORT_FILE}"
fi
