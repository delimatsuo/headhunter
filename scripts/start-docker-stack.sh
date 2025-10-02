#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Starts the complete local Docker stack and blocks until all containers report healthy.
# The script performs prerequisite checks, handles clean restarts, waits for health checks,
# and surfaces actionable troubleshooting hints when something fails.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.local.yml"
STACK_LABEL="headhunter-local"
EXPECTED_CONTAINERS=()
START_TIMEOUT_SECONDS=${START_TIMEOUT_SECONDS:-180}
HEALTH_POLL_INTERVAL=5

log() {
  printf '[start-stack] %s\n' "$*"
}

error() {
  printf '[start-stack][error] %s\n' "$*" >&2
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    error "Missing required command '$1'."
    exit 1
  fi
}

ensure_prerequisites() {
  log "Checking prerequisites"
  require_command docker
  # prefer docker compose but fall back to docker-compose
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_BIN="docker-compose"
  else
    require_command docker
    if docker compose version >/dev/null 2>&1; then
      COMPOSE_BIN="docker compose"
    else
      error "Neither 'docker-compose' nor 'docker compose' is available."
      exit 1
    fi
  fi
  require_command curl
  require_command python3
  export COMPOSE_BIN
}

clean_previous_stack() {
  if [[ "${SKIP_STACK_CLEANUP:-false}" == "true" ]]; then
    log "Skipping cleanup of existing containers"
    return
  fi
  log "Stopping any existing containers for label $STACK_LABEL"
  if $COMPOSE_BIN -f "$COMPOSE_FILE" ps >/dev/null 2>&1; then
    $COMPOSE_BIN -f "$COMPOSE_FILE" down --remove-orphans || true
  fi
}

start_stack() {
  log "Starting stack using $COMPOSE_FILE"
  $COMPOSE_BIN -f "$COMPOSE_FILE" up -d --remove-orphans
}

discover_expected_containers() {
  local names=()
  if ! mapfile -t names < <($COMPOSE_BIN -f "$COMPOSE_FILE" ps --format '{{.Names}}'); then
    EXPECTED_CONTAINERS=()
    return 1
  fi

  local filtered=()
  local name
  for name in "${names[@]}"; do
    if [[ -n "$name" ]]; then
      filtered+=("$name")
    fi
  done

  EXPECTED_CONTAINERS=("${filtered[@]}")
  if ((${#EXPECTED_CONTAINERS[@]} == 0)); then
    return 1
  fi
  log "Discovered containers: ${EXPECTED_CONTAINERS[*]}"
  return 0
}

all_containers_healthy() {
  if ((${#EXPECTED_CONTAINERS[@]} == 0)); then
    discover_expected_containers || return 1
  fi

  local name container_health
  for name in "${EXPECTED_CONTAINERS[@]}"; do
    if ! docker inspect "$name" >/dev/null 2>&1; then
      return 1
    fi
    container_health=$(docker inspect --format '{{ if .State.Health }}{{ .State.Health.Status }}{{ else }}running{{ end }}' "$name" 2>/dev/null || echo "unknown")
    if [[ "$container_health" != "healthy" && "$container_health" != "running" ]]; then
      return 1
    fi
  done
  return 0
}

wait_for_health() {
  log "Waiting up to ${START_TIMEOUT_SECONDS}s for containers to become healthy"
  local start_ts
  start_ts=$(date +%s)
  while true; do
    if all_containers_healthy; then
      log "All containers report healthy"
      return 0
    fi
    if (( $(date +%s) - start_ts > START_TIMEOUT_SECONDS )); then
      error "Timed out waiting for containers to become healthy"
      dump_container_status
      return 1
    fi
    sleep "$HEALTH_POLL_INTERVAL"
  done
}

dump_container_status() {
  if ((${#EXPECTED_CONTAINERS[@]} == 0)); then
    discover_expected_containers || true
  fi

  log "Container status snapshot:"
  if ((${#EXPECTED_CONTAINERS[@]} == 0)); then
    log "- No containers discovered"
    log "Use 'docker compose -f $COMPOSE_FILE ps' to view current status"
    return
  fi

  local name
  for name in "${EXPECTED_CONTAINERS[@]}"; do
    if docker inspect "$name" >/dev/null 2>&1; then
      local health
      health=$(docker inspect --format '{{ if .State.Health }}{{ .State.Health.Status }}{{ else }}{{ .State.Status }}{{ end }}' "$name")
      log "- $name => $health"
    else
      log "- $name => not running"
    fi
  done
  log "Use 'docker logs <name>' for detailed diagnostics"
}

print_troubleshooting() {
  cat <<'TIPS'
Troubleshooting tips:
  • Build failures: rerun with DOCKER_BUILDKIT=1 and check Dockerfile context paths.
  • Port conflicts: ensure ports 7101-7108, 8080, 6379, and 5432 are free before rerunning.
  • Dependency startup delays: increase START_TIMEOUT_SECONDS or verify dependent images are healthy.
  • Volume or schema issues: remove lingering volumes via 'docker volume prune --filter label=headhunter-local'.
  • Authentication mocks: confirm mock OAuth and Together AI logs for token or API errors.
TIPS
}

main() {
  ensure_prerequisites
  clean_previous_stack
  start_stack
  # Allow health checks to discover actual container names dynamically
  discover_expected_containers || true
  if ! wait_for_health; then
    print_troubleshooting
    exit 1
  fi
  log "Stack started successfully. All ${#EXPECTED_CONTAINERS[@]} containers healthy."
}

main "$@"
