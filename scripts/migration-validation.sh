#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HEADHUNTER_HOME_DEFAULT="/Volumes/Extreme Pro/myprojects/headhunter"
HEADHUNTER_HOME_REAL="${HEADHUNTER_HOME:-${HEADHUNTER_HOME_DEFAULT}}"
REPORT_DIR="${REPO_ROOT}/migration_reports"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
REPORT_JSON="${REPORT_DIR}/migration_report_${TIMESTAMP}.json"
LOG_FILE="${REPORT_DIR}/migration_report_${TIMESTAMP}.log"
mkdir -p "${REPORT_DIR}"

RUN_DOCKER=1
RUN_TESTS=1
RUN_HEALTH=1
RUN_DEP_CHECK=1
RUN_REPORT=1

usage() {
  cat <<USAGE
Migration validation utility\n\nUsage: $(basename "$0") [options]\n\nOptions:\n  --skip-docker        Skip Docker build/start validation\n  --skip-tests         Skip integration test execution\n  --skip-health        Skip service health checks\n  --skip-deps          Skip dependency validation\n  --skip-report        Skip JSON report generation\n  -h, --help           Show this help message\nUSAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-docker) RUN_DOCKER=0 ;;
    --skip-tests) RUN_TESTS=0 ;;
    --skip-health) RUN_HEALTH=0 ;;
    --skip-deps) RUN_DEP_CHECK=0 ;;
    --skip-report) RUN_REPORT=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

declare -a STEP_NAMES=()
declare -a STEP_STATUS=()
declare -a STEP_DETAILS=()
DOCKER_STARTED=0

log_section() {
  echo "\n== $1 ==" | tee -a "$LOG_FILE"
}

record_step() {
  STEP_NAMES+=("$1")
  STEP_STATUS+=("$2")
  STEP_DETAILS+=("${3:-}")
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    return 1
  fi
}

check_repo_location() {
  log_section "Validating repository location"
  local repo_real="$(realpath "$REPO_ROOT")"
  local env_real="$(realpath "$HEADHUNTER_HOME_REAL" 2>/dev/null || echo "")"

  if [[ -z "$env_real" ]]; then
    echo "HEADHUNTER_HOME points to an invalid path: $HEADHUNTER_HOME_REAL" | tee -a "$LOG_FILE"
    record_step "repository_location" "failed" "HEADHUNTER_HOME invalid"
    return 1
  fi

  echo "Repository root: $repo_real" | tee -a "$LOG_FILE"
  echo "HEADHUNTER_HOME : $env_real" | tee -a "$LOG_FILE"

  if [[ "$repo_real" != "$env_real" ]]; then
    echo "Repository is not located at HEADHUNTER_HOME" | tee -a "$LOG_FILE"
    record_step "repository_location" "failed" "Mismatch between repo root and HEADHUNTER_HOME"
    return 1
  fi

  canonical="/Volumes/Extreme Pro/myprojects/headhunter"
  if [[ "$repo_real" != "$canonical" ]]; then
    echo "Repository root must be ${canonical}; detected $repo_real" | tee -a "$LOG_FILE"
    record_step "repository_location" "failed" "Incorrect repository root"
    return 1
  fi

  record_step "repository_location" "passed" "Repository location validated"
  return 0
}

check_environment_var() {
  log_section "Checking environment configuration"
  if [[ -z "${HEADHUNTER_HOME:-}" ]]; then
    echo "HEADHUNTER_HOME is not exported in this shell" | tee -a "$LOG_FILE"
    record_step "environment_variable" "failed" "HEADHUNTER_HOME not set"
    return 1
  fi
  echo "HEADHUNTER_HOME=${HEADHUNTER_HOME}" | tee -a "$LOG_FILE"
  record_step "environment_variable" "passed" "Environment variable present"
  return 0
}

check_dependencies() {
  log_section "Validating core dependencies"
  local missing=0
  local deps=(python3 pip node npm docker git)
  for dep in "${deps[@]}"; do
    if require_command "$dep"; then
      printf '  - %-7s %s\n' "$dep" "$(command -v "$dep")" | tee -a "$LOG_FILE"
    else
      missing=1
    fi
  done

  if [[ -d "${REPO_ROOT}/services" && ! -d "${REPO_ROOT}/services/node_modules" ]]; then
    echo "services/node_modules missing; run npm install in ./services" | tee -a "$LOG_FILE"
    missing=1
  fi

  if [[ ! -d "${REPO_ROOT}/.venv" ]]; then
    echo ".venv missing; run python3 -m venv .venv && source .venv/bin/activate" | tee -a "$LOG_FILE"
    missing=1
  fi

  if [[ $missing -eq 0 ]]; then
    record_step "dependency_validation" "passed" "Core tooling present"
    return 0
  else
    record_step "dependency_validation" "failed" "Missing dependencies"
    return 1
  fi
}

start_docker_stack() {
  log_section "Building and starting Docker stack"
  local compose_file="${REPO_ROOT}/docker-compose.local.yml"
  if [[ ! -f "$compose_file" ]]; then
    echo "docker-compose.local.yml not found" | tee -a "$LOG_FILE"
    record_step "docker_stack" "failed" "Compose file missing"
    return 1
  fi

  DOCKER_STARTED=1
  if docker compose -f "$compose_file" up -d --build | tee -a "$LOG_FILE"; then
    record_step "docker_stack" "passed" "Docker services started"
    return 0
  else
    record_step "docker_stack" "failed" "Docker compose up failed"
    return 1
  fi
}

health_checks() {
  log_section "Running service health checks"
  local endpoints=(
    "hh-embed-svc:http://localhost:7101/health"
    "hh-search-svc:http://localhost:7102/health"
    "hh-rerank-svc:http://localhost:7103/health"
    "hh-evidence-svc:http://localhost:7104/health"
    "hh-eco-svc:http://localhost:7105/health"
    "hh-admin-svc:http://localhost:7106/health"
    "hh-msgs-svc:http://localhost:7107/health"
    "hh-enrich-svc:http://localhost:7108/health"
  )

  local failures=0
  for item in "${endpoints[@]}"; do
    local service="${item%%:*}"
    local url="${item#*:}"
    if curl -fsSL --max-time 10 "$url" >/dev/null; then
      printf '  [%s] OK\n' "$service" | tee -a "$LOG_FILE"
    else
      printf '  [%s] FAILED (%s)\n' "$service" "$url" | tee -a "$LOG_FILE"
      failures=1
    fi
  done

  if [[ $failures -eq 0 ]]; then
    record_step "service_health" "passed" "All services reported healthy"
    return 0
  fi

  record_step "service_health" "failed" "One or more services are unhealthy"
  return 1
}

run_integration_tests() {
  log_section "Executing integration test suite"
  if "${SCRIPT_DIR}/test-integration.sh" | tee -a "$LOG_FILE"; then
    record_step "integration_tests" "passed" "Integration suite succeeded"
    return 0
  fi
  record_step "integration_tests" "failed" "Integration suite reported failures"
  return 1
}

generate_report() {
  log_section "Generating migration report"
  local passed=0
  local failed=0
  local tmp_steps="$(mktemp)"

  for i in "${!STEP_NAMES[@]}"; do
    local name="${STEP_NAMES[$i]}"
    local status="${STEP_STATUS[$i]}"
    local detail="${STEP_DETAILS[$i]}"
    if [[ "$status" == "passed" ]]; then
      ((passed++))
    else
      ((failed++))
    fi
    printf '%s\t%s\t%s\n' "$name" "$status" "$detail" >>"$tmp_steps"
  done

  python3 - <<PY
import json
from pathlib import Path
rows = []
for line in Path("${tmp_steps}").read_text().splitlines():
    name, status, detail = line.split("\t", 2)
    rows.append({
        "step": name,
        "status": status,
        "detail": detail
    })
report = {
    "timestamp": "${TIMESTAMP}",
    "repository": "${REPO_ROOT}",
    "headhunter_home": "${HEADHUNTER_HOME_REAL}",
    "steps": rows,
    "passed": ${passed},
    "failed": ${failed}
}
with open("${REPORT_JSON}", "w", encoding="utf-8") as fp:
    json.dump(report, fp, indent=2)
print(f"Report written to ${REPORT_JSON}")
PY

  rm -f "$tmp_steps"
}

cleanup() {
  if [[ $DOCKER_STARTED -eq 1 ]]; then
    log_section "Stopping Docker stack"
    docker compose -f "${REPO_ROOT}/docker-compose.local.yml" down >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

check_repo_location || true
check_environment_var || true
if [[ $RUN_DEP_CHECK -eq 1 ]]; then
  check_dependencies || true
fi
if [[ $RUN_DOCKER -eq 1 ]]; then
  start_docker_stack || true
fi
if [[ $RUN_HEALTH -eq 1 ]]; then
  health_checks || true
fi
if [[ $RUN_TESTS -eq 1 ]]; then
  run_integration_tests || true
fi
if [[ $RUN_REPORT -eq 1 ]]; then
  generate_report || true
fi

log_section "Migration validation complete"
for i in "${!STEP_NAMES[@]}"; do
  printf '  %-22s : %s\n' "${STEP_NAMES[$i]}" "${STEP_STATUS[$i]}" | tee -a "$LOG_FILE"
  if [[ -n "${STEP_DETAILS[$i]}" ]]; then
    printf '    -> %s\n' "${STEP_DETAILS[$i]}" | tee -a "$LOG_FILE"
  fi
done

if [[ -f "$REPORT_JSON" ]]; then
  echo "JSON report: $REPORT_JSON" | tee -a "$LOG_FILE"
fi

echo "Log file: $LOG_FILE"
