#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.local.yml"
COMPOSE_CMD="${COMPOSE_CMD:-}"
VALIDATE_SCRIPT="${ROOT_DIR}/scripts/validate-all-services-health.sh"

if [[ -z "${COMPOSE_CMD}" ]]; then
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
  else
    COMPOSE_CMD="docker compose"
  fi
fi

log() {
  printf '[test-local-setup] %s\n' "$*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "Missing required command: $1"
    exit 1
  fi
}

require_cmd docker
require_cmd curl
require_cmd python3

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  log "docker-compose.local.yml not found at ${COMPOSE_FILE}"
  exit 1
fi

log "Using compose command: ${COMPOSE_CMD}"

if ! ${COMPOSE_CMD} -f "${COMPOSE_FILE}" ps >/dev/null; then
  log "Compose stack unavailable. Start services with '${COMPOSE_CMD} -f docker-compose.local.yml up -d' first."
  exit 1
fi

check_postgres() {
  local container="hh-local-postgres"
  if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
    log "Postgres container '${container}' is not running."
    return 1
  fi
  docker exec "${container}" pg_isready -U headhunter -d headhunter >/dev/null
  local count
  count="$(docker exec "${container}" psql -U headhunter -d headhunter -tAc "SELECT COUNT(*) FROM search.candidate_profiles;")"
  log "Postgres reachable. candidate_profiles rows=${count}"
}

check_redis() {
  local container="hh-local-redis"
  if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
    log "Redis container '${container}' is not running."
    return 1
  fi
  local pong
  pong="$(docker exec "${container}" redis-cli ping)"
  if [[ "${pong}" != "PONG" ]]; then
    log "Redis ping failed: ${pong}"
    return 1
  fi
  log "Redis reachable."
}

check_firestore() {
  local status
  status="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080)"
  if [[ "${status}" != "200" && "${status}" != "404" ]]; then
    log "Firestore emulator unhealthy (HTTP ${status})."
    return 1
  fi
  log "Firestore emulator responded with HTTP ${status}."
}

check_mock_oauth() {
  local status
  status="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8081/health)"
  if [[ "${status}" != "200" ]]; then
    log "Mock OAuth health check failed (HTTP ${status})."
    return 1
  fi
  log "Mock OAuth server healthy."
}

check_postgres
check_redis
check_firestore
check_mock_oauth

log "Infrastructure dependencies healthy. Proceeding with service validation."

if [[ -x "${VALIDATE_SCRIPT}" ]]; then
  log "Delegating service health checks to ${VALIDATE_SCRIPT}"
  "${VALIDATE_SCRIPT}"
else
  log "Service validation script not executable at ${VALIDATE_SCRIPT}; skipping application checks."
fi
