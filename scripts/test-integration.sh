#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPORT_DIR="${REPO_ROOT}/.integration"
REPORT_JSON="${REPORT_DIR}/suite-report.json"
PERF_REPORT="${REPORT_DIR}/performance_sla_report.json"
CACHE_REPORT="${REPORT_DIR}/cache_analysis_report.json"
LOAD_REPORT="${REPORT_DIR}/load_test_report.json"
FIX_REPORT="${REPORT_DIR}/autofix_actions.json"
mkdir -p "${REPORT_DIR}"

HEADHUNTER_HOME="${HEADHUNTER_HOME:-/Volumes/Extreme Pro/myprojects/headhunter}"

# Validate correct repository location
CANONICAL_ROOT="/Volumes/Extreme Pro/myprojects/headhunter"
if [[ "${REPO_ROOT}" != "${CANONICAL_ROOT}" ]]; then
  echo "❌ ERROR: Run scripts from ${CANONICAL_ROOT}. Detected ${REPO_ROOT}." >&2
  exit 1
fi

HEALTH_ENDPOINTS=(
  "hh-embed-svc:http://localhost:7101/health"
  "hh-search-svc:http://localhost:7102/health"
  "hh-rerank-svc:http://localhost:7103/health"
  "hh-evidence-svc:http://localhost:7104/health"
  "hh-eco-svc:http://localhost:7105/health"
  "hh-admin-svc:http://localhost:7106/health"
  "hh-msgs-svc:http://localhost:7107/health"
  "hh-enrich-svc:http://localhost:7108/health"
  "mock-oauth:http://localhost:8081/health"
  "mock-together:http://localhost:7500/health"
)

log_section() {
  printf '\n[test-integration] %s\n' "$1"
}

check_tooling() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 command is required" >&2
    exit 1
  fi
}

check_health() {
  log_section "Verifying service health checks"
  for item in "${HEALTH_ENDPOINTS[@]}"; do
    service="${item%%:*}"
    url="${item#*:}"
    if curl -fsSL --max-time 5 "$url" >/dev/null; then
      printf '  [%s] OK\n' "$service"
    else
      echo "Service ${service} is not healthy at ${url}" >&2
      exit 1
    fi
  done
}

run_python_suite() {
  log_section "Running Python orchestration suite"
  if python3 "${SCRIPT_DIR}/run_integration.py" | tee "${REPORT_JSON}"; then
    printf '  [suite] Integration runner completed successfully\n'
  else
    echo "Integration runner reported failures" >&2
    exit 1
  fi
}

run_performance_validation() {
  log_section "Validating performance SLAs"
  if python3 "${SCRIPT_DIR}/validate-performance-slas.py" --iterations 3 --warmups 1 --report "${PERF_REPORT}"; then
    printf '  [sla] Performance targets satisfied\n'
    return
  fi

  echo "  [sla] Initial validation failed; attempting automated remediation" >&2
  if python3 "${SCRIPT_DIR}/fix-performance-issues.py" \
    --source-report "${PERF_REPORT}" \
    --apply \
    --report "${FIX_REPORT}"; then
    printf '  [sla] Applied automated fixes, re-running validation\n'
  else
    echo "  [sla] Automated remediation script failed" >&2
  fi

  python3 "${SCRIPT_DIR}/validate-performance-slas.py" --iterations 2 --warmups 0 --report "${PERF_REPORT}"
}

analyze_cache_performance() {
  log_section "Analyzing cache effectiveness"
  python3 "${SCRIPT_DIR}/analyze-cache-performance.py" --samples 5 --report "${CACHE_REPORT}"
}

run_pytests() {
  log_section "Executing pytest integration coverage"
  (cd "${REPO_ROOT}" && PYTHONPATH=. python3 -m pytest tests/test_local_stack.py -q)
}

run_jest_suites() {
  log_section "Running service-specific Jest integration suites"
  if command -v npx >/dev/null 2>&1; then
    if [ "${SKIP_JEST:-0}" = "1" ]; then
      echo "SKIP_JEST=1; skipping Jest suites" >&2
      return
    fi

    if [ "${RUN_JEST:-0}" = "1" ] || \
       [ -f "${REPO_ROOT}/tests/integration/enrich-service.test.ts" ] || \
       [ -f "${REPO_ROOT}/tests/integration/admin-service.test.ts" ] || \
       [ -f "${REPO_ROOT}/tests/integration/msgs-service.test.ts" ]; then
      if [ ! -d "${REPO_ROOT}/services/node_modules" ]; then
        echo "services workspace dependencies missing; run npm install in ./services" >&2
        exit 1
      fi

      (cd "${REPO_ROOT}/services" && \
        FIREBASE_PROJECT_ID="headhunter-local" \
        FIRESTORE_EMULATOR_HOST="localhost:8080" \
        REDIS_HOST="localhost" \
        ALLOWED_TOKEN_ISSUERS="http://localhost:8081/" \
        GATEWAY_AUDIENCE="headhunter-local" \
        AUTH_MODE="gateway" \
        NODE_ENV="test" \
        npx --yes jest \
        ../tests/integration/enrich-service.test.ts \
        ../tests/integration/admin-service.test.ts \
        ../tests/integration/msgs-service.test.ts \
        --config ./jest.config.js \
        --runTestsByPath \
        --runInBand)
    else
      echo "Jest tests not found; skipping" >&2
    fi
  else
    echo "npx not available; skipping Jest suites" >&2
  fi
}

run_load_tests() {
  log_section "Running load test scenarios"
  python3 "${SCRIPT_DIR}/load-test-stack.py" --report "${LOAD_REPORT}"
}

summarise_report() {
  if [ ! -f "${REPORT_JSON}" ]; then
    return
  fi
  log_section "Integration performance summary"
  python3 - <<PY
import json, pathlib
report = json.loads(pathlib.Path("${REPORT_JSON}").read_text())
print(f"  tenant: {report['tenant']}")
print(f"  steps: {len(report['steps'])} passed={report['completed_steps']} failed={report['failed_steps']}")
stats = report.get('stats', {})
print(f"  latency avg={stats.get('avgLatencyMs', 0):.2f}ms p95={stats.get('p95LatencyMs', 0):.2f}ms")
perf = report.get('performance', {})
if perf:
    print(f"  step p95={perf.get('stepLatencyP95Ms')} totalRuntimeMs={perf.get('totalRuntimeMs')}")
PY
}

summarise_performance_reports() {
  if [ -f "${PERF_REPORT}" ]; then
    log_section "Performance SLA summary"
    python3 - <<PY
import json, pathlib
report = json.loads(pathlib.Path("${PERF_REPORT}").read_text())
for name, status in report.get('sla', {}).items():
    marker = "PASS" if status.get('pass') else "FAIL"
    if name == 'cacheHitRate':
        observed = status.get('observed')
        print(f"  {name}: {marker} observed={observed} target={status.get('target')}")
    else:
        print(f"  {name}: {marker} p95={status.get('p95')} target={status.get('target')}")
if report.get('issues'):
    print(f"  issues detected: {len(report['issues'])}")
PY
  fi

  if [ -f "${CACHE_REPORT}" ]; then
    log_section "Cache analysis summary"
    python3 - <<PY
import json, pathlib
report = json.loads(pathlib.Path("${CACHE_REPORT}").read_text())
overall = report.get('overall', {})
print(f"  overall hitRate={overall.get('hitRate')} hits={overall.get('hits')} misses={overall.get('misses')}")
for entry in report.get('scenarios', [])[:5]:
    metrics = entry.get('metrics', {})
    print(f"  scenario {entry.get('name')}: hitRate={metrics.get('hitRate')} hits={metrics.get('hits')} misses={metrics.get('misses')}")
PY
  fi

  if [ -f "${LOAD_REPORT}" ]; then
    log_section "Load test summary"
    python3 - <<PY
import json, pathlib
report = json.loads(pathlib.Path("${LOAD_REPORT}").read_text())
for scenario in report.get('scenarios', []):
    metrics = scenario.get('metrics', {})
    print(f"  {scenario.get('name')}: avg={metrics.get('avg')} p95={metrics.get('p95')}" )
PY
  fi
}

check_tooling
check_health
run_python_suite
run_performance_validation
analyze_cache_performance
run_pytests
run_jest_suites
run_load_tests
summarise_report
summarise_performance_reports

log_section "Integration sequence complete"
