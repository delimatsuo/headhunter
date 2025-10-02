#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Validates the health of local infrastructure services (PostgreSQL, Redis,
# Firestore emulator, mock OAuth, and mock Together AI) that support the
# Headhunter stack.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-hh-local-postgres}"
REDIS_CONTAINER="${REDIS_CONTAINER:-hh-local-redis}"
FIRESTORE_PORT="${FIRESTORE_PORT:-8080}"
MOCK_OAUTH_PORT="${MOCK_OAUTH_PORT:-8081}"
MOCK_TOGETHER_PORT="${MOCK_TOGETHER_PORT:-7500}"
TENANT_ID="${TENANT_ID:-tenant-alpha}"

log() {
  printf '[infra-health] %s\n' "$*"
}

error() {
  printf '[infra-health][error] %s\n' "$*" >&2
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    error "Missing required command: $1"
    exit 1
  fi
}

require_cmd docker
require_cmd curl
require_cmd python3

assert_container_running() {
  local name="$1"
  if ! docker ps --format '{{.Names}}' | grep -q "^${name}$"; then
    error "Container '${name}' is not running. Start the stack first."
    exit 1
  fi
}

check_postgres() {
  assert_container_running "$POSTGRES_CONTAINER"
  log "Checking PostgreSQL (${POSTGRES_CONTAINER})"
  docker exec "$POSTGRES_CONTAINER" pg_isready -U headhunter -d headhunter >/dev/null

  local schemas
  schemas="$(docker exec "$POSTGRES_CONTAINER" psql -U headhunter -d headhunter -tAc "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('search','public');")"
  log "Schemas present: ${schemas//\n/, }"

  local count
  count="$(docker exec "$POSTGRES_CONTAINER" psql -U headhunter -d headhunter -tAc "SELECT COUNT(*) FROM search.candidate_profiles;")"
  log "candidate_profiles rows: ${count}"

  local extension
  extension="$(docker exec "$POSTGRES_CONTAINER" psql -U headhunter -d headhunter -tAc "SELECT extname FROM pg_extension WHERE extname='vector';")"
  if [[ -z "${extension}" ]]; then
    WARNINGS+=("pgvector extension missing")
  fi
}

check_redis() {
  assert_container_running "$REDIS_CONTAINER"
  log "Checking Redis (${REDIS_CONTAINER})"
  local pong
  pong="$(docker exec "$REDIS_CONTAINER" redis-cli ping)"
  if [[ "${pong}" != "PONG" ]]; then
    error "Redis ping failed (got ${pong})"
    exit 1
  fi

  local key="infra-health:$(date +%s)"
  docker exec "$REDIS_CONTAINER" redis-cli set "$key" ok >/dev/null
  local value
  value="$(docker exec "$REDIS_CONTAINER" redis-cli get "$key")"
  if [[ "${value}" != "ok" ]]; then
    WARNINGS+=("Redis set/get mismatch for ${key}")
  else
    log "Redis set/get check passed"
  fi
}

check_firestore() {
  log "Checking Firestore emulator"
  local status
  status="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${FIRESTORE_PORT}")"
  if [[ "${status}" != "200" && "${status}" != "404" ]]; then
    error "Firestore emulator unhealthy (HTTP ${status})"
    exit 1
  fi

  local payload
  payload='{"writes":[{"update":{"name":"projects/headhunter-local/databases/(default)/documents/infra-health/test","fields":{"status":{"stringValue":"ok"}}},"currentDocument":{"exists":false}}]}'
  local write_status
  write_status="$(curl -s -o /dev/null -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' \
    -d "${payload}" \
    "http://localhost:${FIRESTORE_PORT}/v1/projects/headhunter-local/databases/(default)/documents:commit")"
  if [[ "${write_status}" != "200" ]]; then
    WARNINGS+=("Firestore write test failed (HTTP ${write_status})")
  else
    log "Firestore emulator write test succeeded"
  fi
}

check_mock_oauth() {
  log "Checking mock OAuth server"
  local health
  health="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${MOCK_OAUTH_PORT}/health")"
  if [[ "${health}" != "200" ]]; then
    error "Mock OAuth server unhealthy (HTTP ${health})"
    exit 1
  fi

  local token
  token="$(curl -sS -X POST \
    -H 'Content-Type: application/json' \
    -d '{"tenant_id":"'"${TENANT_ID}"'","sub":"infra-health","scope":"infra:read"}' \
    "http://localhost:${MOCK_OAUTH_PORT}/token" | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))")"
  if [[ -z "${token}" ]]; then
    error "Failed to retrieve token from mock OAuth server"
    exit 1
  fi
  log "Mock OAuth token issued (${#token} bytes)"
}

check_mock_together() {
  log "Checking mock Together AI server"
  local health
  health="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${MOCK_TOGETHER_PORT}/health")"
  if [[ "${health}" != "200" ]]; then
    error "Mock Together AI server unhealthy (HTTP ${health})"
    exit 1
  fi

  local response
  response="$(curl -sS -X POST -H 'Content-Type: application/json' -d '{"prompt":"ping"}' "http://localhost:${MOCK_TOGETHER_PORT}/v1/completions")"
  if [[ -z "${response}" ]]; then
    WARNINGS+=("Mock Together AI completion returned empty body")
  fi
}

WARNINGS=()

check_postgres
check_redis
check_firestore
check_mock_oauth
check_mock_together

if (( ${#WARNINGS[@]} > 0 )); then
  log "Checks completed with warnings:"
  for warning in "${WARNINGS[@]}"; do
    log "- ${warning}"
  done
else
  log "All infrastructure components healthy."
fi
