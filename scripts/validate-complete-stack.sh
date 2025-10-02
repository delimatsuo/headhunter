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
MASTER_REPORT="${REPORT_DIR}/complete_validation_report.json"
mkdir -p "${REPORT_DIR}"

log_section() {
  printf '\n[validate-complete-stack] %s\n' "$1"
}

start_stack_if_needed() {
  if [[ "${SKIP_STACK_START:-false}" == "true" ]]; then
    log_section "Skipping docker-compose startup"
    return
  fi
  if command -v docker >/dev/null 2>&1; then
    log_section "Ensuring local stack is running"
    if docker ps --format '{{.Names}}' | grep -q 'hh-local-postgres'; then
      printf '  [stack] Containers already running\n'
    else
      printf '  [stack] Starting docker-compose.local.yml\n'
      (cd "${REPO_ROOT}" && docker compose -f docker-compose.local.yml up -d)
    fi
  else
    log_section "Docker not available; assuming services already running"
  fi
}

run_health_checks() {
  log_section "Running infrastructure and service health checks"
  bash "${SCRIPT_DIR}/test-local-setup.sh"
}

run_integration_suite() {
  log_section "Executing integration and performance suites"
  bash "${SCRIPT_DIR}/test-integration.sh"
}

run_monitoring_cycle() {
  log_section "Collecting monitoring snapshot"
  python3 "${SCRIPT_DIR}/monitor-performance.py" --cycles 1 --interval 10 --report "${REPORT_DIR}/monitor_summary.json"
}

assemble_master_report() {
  log_section "Assembling validation report"
  python3 - <<PY
import json
import pathlib

report_dir = pathlib.Path("${REPORT_DIR}")
paths = {
    "integration": report_dir / "suite-report.json",
    "performance": report_dir / "performance_sla_report.json",
    "cache": report_dir / "cache_analysis_report.json",
    "load": report_dir / "load_test_report.json",
    "monitor": report_dir / "monitor_summary.json",
    "autofix": report_dir / "autofix_actions.json",
}

def load_optional(path: pathlib.Path):
    if path.exists():
        return json.loads(path.read_text())
    return None

report = {key: load_optional(path) for key, path in paths.items()}

issues = []
if report['performance'] and report['performance'].get('issues'):
    issues.extend(report['performance']['issues'])
if report['monitor'] and report['monitor'].get('alerts'):
    issues.extend(report['monitor']['alerts'])

status = "pass" if not issues else "fail"
final_report = {
    "tenant": report.get('performance', {}).get('tenant') or report.get('integration', {}).get('tenant'),
    "status": status,
    "timestamp": int(__import__('time').time()),
    "artifacts": {key: str(path) if path and path.exists() else None for key, path in paths.items()},
    "issues": issues,
    "recommendations": report.get('performance', {}).get('recommendations', []) if report.get('performance') else [],
}

output_path = pathlib.Path("${MASTER_REPORT}")
output_path.write_text(json.dumps(final_report, indent=2, sort_keys=True))
print(json.dumps(final_report, indent=2))
PY
}

start_stack_if_needed
run_health_checks
run_integration_suite
run_monitoring_cycle
assemble_master_report

if grep -q '"status": "fail"' "${MASTER_REPORT}"; then
  log_section "Validation failed"
  exit 1
fi

log_section "Validation successful"
