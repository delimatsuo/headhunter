#!/usr/bin/env bash
set -uo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d -t hh-complete-validation-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

TS_SCRIPT="$ROOT_DIR/scripts/validate-typescript-builds.sh"
DOCKER_SCRIPT="$ROOT_DIR/scripts/validate-docker-builds.sh"
STACK_SCRIPT="$ROOT_DIR/scripts/validate-stack-health.sh"
INTEGRATION_SCRIPT="$ROOT_DIR/scripts/test-integration.sh"
PYTEST_CMD=("python3" "-m" "pytest" "tests" "-q")

COMPOSE_FILE="$ROOT_DIR/docker-compose.local.yml"
STACK_STARTED=false

declare -A STEP_STATUS
declare -A STEP_LOG

info() {
  printf '\n[%(%Y-%m-%dT%H:%M:%S%z)T] %s\n' -1 "$1"
}

run_step() {
  local key="$1"
  local description="$2"
  shift 2
  local log_file="$TMP_DIR/${key}.log"
  info "Running ${description}"
  "$@" >"$log_file" 2>&1
  local status=$?
  STEP_STATUS["$key"]=$status
  STEP_LOG["$key"]="$log_file"
  if [[ $status -eq 0 ]]; then
    echo "${description} completed successfully."
  else
    echo "${description} failed. See $log_file" >&2
  fi
  return $status
}

ensure_executable() {
  local script="$1"
  if [[ ! -x "$script" ]]; then
    chmod +x "$script" 2>/dev/null || true
  fi
}

rollback_stack() {
  if $STACK_STARTED && [[ -f "$COMPOSE_FILE" ]]; then
    info "Rolling back docker stack"
    if docker compose version >/dev/null 2>&1; then
      docker compose -f "$COMPOSE_FILE" down --remove-orphans >/dev/null 2>&1 || true
    else
      docker-compose -f "$COMPOSE_FILE" down --remove-orphans >/dev/null 2>&1 || true
    fi
  fi
}

trap rollback_stack EXIT

ensure_executable "$TS_SCRIPT"
ensure_executable "$DOCKER_SCRIPT"
ensure_executable "$STACK_SCRIPT"

# Phase 1: TypeScript build validation
if ! run_step "typescript" "TypeScript workspace validation" "$TS_SCRIPT"; then
  info "Halting validation pipeline after TypeScript failures."
  exit 1
fi

# Phase 2: Docker build validation
if ! run_step "docker" "Docker build validation" "$DOCKER_SCRIPT"; then
  info "Halting validation pipeline after Docker build failures."
  exit 1
fi

# Phase 3: Stack health validation
if run_step "stack" "Stack health validation" "$STACK_SCRIPT"; then
  STACK_STARTED=true
else
  info "Stack health failed; see ${STEP_LOG[stack]}"
  exit 1
fi

# Phase 4: Integration tests
integration_phase() {
  local status=0
  local integration_log="$TMP_DIR/integration-tests.log"
  if [[ -x "$INTEGRATION_SCRIPT" ]]; then
    (cd "$ROOT_DIR" && "$INTEGRATION_SCRIPT") >>"$integration_log" 2>&1 || status=$?
  else
    echo "test-integration.sh not found or not executable; skipping." >>"$integration_log"
  fi

  (cd "$ROOT_DIR" && PYTHONPATH=. "${PYTEST_CMD[@]}") >>"$integration_log" 2>&1 || status=$?
  cat "$integration_log"
  return $status
}

run_step "integration" "Integration and pytest suite" integration_phase

print_summary() {
  info "Complete validation report"
  printf '%-15s %s\n' "Phase" "Status"
  printf '%-15s %s\n' "-----" "------"
  for phase in typescript docker stack integration; do
    local status="${STEP_STATUS[$phase]:-2}"
    local label
    case "$status" in
      0) label="PASS" ;;
      1) label="FAIL" ;;
      2) label="SKIP" ;;
      *) label="UNKNOWN" ;;
    esac
    printf '%-15s %s\n' "$phase" "$label"
  done

  echo
  echo "Logs:"
  for phase in typescript docker stack integration; do
    local log="${STEP_LOG[$phase]:-}";
    [[ -n "$log" ]] && echo " - $phase: $log"
  done

  echo
  if [[ "${STEP_STATUS[integration]:-1}" -eq 0 ]]; then
    echo "✅ Validation pipeline succeeded. Safe to proceed with deployment."
  else
    echo "❌ Validation pipeline failed. Review logs before retrying." >&2
  fi
}

print_summary

exit "${STEP_STATUS[integration]:-1}"
