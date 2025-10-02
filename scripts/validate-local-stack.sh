#!/usr/bin/env bash
set -uo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

ROOT_PATH="/Volumes/Extreme Pro/myprojects/headhunter"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

if [[ "${REPO_ROOT}" != "${ROOT_PATH}" ]]; then
  echo "❌ ERROR: validate-local-stack.sh must be run from ${ROOT_PATH}" >&2
  exit 1
fi

log() {
  echo "[$(date -Is)] $*" >&2
}

declare -a health_reports=()
declare -a data_reports=()
critical_failure=0
data_issue=0

ensure_command() {
  local binary=$1
  if ! command -v "$binary" >/dev/null 2>&1; then
    log "Missing required command: ${binary}"
    critical_failure=1
    return 1
  fi
  return 0
}

ensure_command docker || true
ensure_command curl || true
ensure_command gcloud || true

if ! docker info >/dev/null 2>&1; then
  log "Docker daemon is not available"
  exit 1
fi

check_http() {
  local name=$1
  local url=$2
  local response status latency
  response=$(curl -w "%{http_code} %{time_total}" -o /dev/null -s "$url" 2>/dev/null || echo "000 0")
  status=${response%% *}
  latency=${response#* }

  if [[ "$status" =~ ^[0-9]+$ ]] && (( status >= 200 && status < 300 )); then
    health_reports+=("${name}: OK (status=${status}, latency=${latency}s)")
  else
    health_reports+=("${name}: FAIL (status=${status}, latency=${latency}s)")
    critical_failure=1
  fi
}

check_container_health() {
  local container=$1
  if ! docker ps --format '{{.Names}}' | grep -Fxq "$container"; then
    health_reports+=("${container}: container not running")
    critical_failure=1
    return
  fi
  local health
  health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || echo "unknown")
  if [[ "$health" == "healthy" ]]; then
    health_reports+=("${container}: healthy")
  else
    health_reports+=("${container}: ${health}")
    critical_failure=1
  fi
}

check_postgres() {
  if ! docker ps --format '{{.Names}}' | grep -Fxq 'hh-local-postgres'; then
    data_reports+=("postgres: container not running")
    critical_failure=1
    return
  fi
  if docker exec hh-local-postgres pg_isready -U headhunter -d headhunter >/dev/null 2>&1; then
    health_reports+=("postgres: connection ok")
  else
    health_reports+=("postgres: connection failed")
    critical_failure=1
    return
  fi

  local count
  count=$(docker exec hh-local-postgres psql -U headhunter -d headhunter -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d '[:space:]')
  if [[ -n "$count" ]] && [[ "$count" =~ ^[0-9]+$ ]] && (( count > 0 )); then
    data_reports+=("postgres: ${count} tables present")
  else
    data_reports+=("postgres: schema not seeded")
    data_issue=1
  fi
}

check_redis() {
  if ! docker ps --format '{{.Names}}' | grep -Fxq 'hh-local-redis'; then
    health_reports+=("redis: container not running")
    critical_failure=1
    return
  fi
  local ping
  ping=$(docker exec hh-local-redis redis-cli ping 2>/dev/null || echo "")
  if [[ "$ping" == "PONG" ]]; then
    health_reports+=("redis: PONG")
  else
    health_reports+=("redis: connection failed")
    critical_failure=1
  fi
}

check_firestore() {
  local base_url="http://localhost:8080"
  local projects_endpoint="${base_url}/emulator/v1/projects"
  if curl -s "$base_url" >/dev/null; then
    health_reports+=("firestore-emulator: reachable")
  else
    health_reports+=("firestore-emulator: unreachable")
    critical_failure=1
    return
  fi
  local tenants_endpoint="${base_url}/emulator/v1/projects/headhunter-local/databases/(default)/documents/tenants"
  local payload
  payload=$(curl -s "$tenants_endpoint" 2>/dev/null || echo "")
  if [[ "$payload" == *'"documents"'* ]]; then
    data_reports+=("firestore: tenant documents present")
  else
    data_reports+=("firestore: tenant documents missing")
    data_issue=1
  fi
}

check_pubsub() {
  export PUBSUB_EMULATOR_HOST="localhost:8681"
  local topics
  topics=$(gcloud pubsub topics list --project=headhunter-local --format='value(name)' 2>/dev/null || echo "")
  if [[ -z "$topics" ]]; then
    data_reports+=("pubsub: no topics found")
    data_issue=1
  else
    data_reports+=("pubsub topics:\n${topics}")
  fi
}

check_mock_oauth_token() {
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:8081/token" \
    -d 'client_id=test-client' \
    -d 'client_secret=test-secret' \
    -d 'grant_type=client_credentials' || echo "000")
  if [[ "$status" =~ ^2 ]]; then
    data_reports+=("mock-oauth: token endpoint reachable (status ${status})")
  else
    data_reports+=("mock-oauth: token request failed (status ${status})")
    data_issue=1
  fi
}

log "Running local stack validation"

check_postgres
check_redis
check_firestore
check_pubsub

check_http "mock-oauth" "http://localhost:8081/health"
check_http "mock-together" "http://localhost:7500/health"

declare -A service_ports=(
  [hh-embed-svc]=7101
  [hh-search-svc]=7102
  [hh-rerank-svc]=7103
  [hh-evidence-svc]=7104
  [hh-eco-svc]=7105
  [hh-admin-svc]=7106
  [hh-msgs-svc]=7107
  [hh-enrich-svc]=7108
)

for service in "${!service_ports[@]}"; do
  check_http "${service}" "http://localhost:${service_ports[$service]}/health"
done

check_mock_oauth_token

log "--- Service health ---"
for entry in "${health_reports[@]}"; do
  echo "${entry}"
done

log "--- Data validation ---"
for entry in "${data_reports[@]}"; do
  echo -e "${entry}"
done

if (( critical_failure == 1 )); then
  log "Stack validation failed: one or more services are unhealthy"
  exit 1
fi

if (( data_issue == 1 )); then
  log "Stack validation detected data issues"
  exit 2
fi

log "Local stack is healthy"
exit 0
