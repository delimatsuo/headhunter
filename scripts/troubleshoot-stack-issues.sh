#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Provides guided diagnostics for the local Docker stack.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.local.yml"
SERVICES=(
  "hh-local-postgres"
  "hh-local-redis"
  "hh-local-firestore"
  "hh-local-mock-oauth"
  "hh-local-mock-together"
  "hh-local-embed"
  "hh-local-search"
  "hh-local-rerank"
  "hh-local-evidence"
  "hh-local-eco"
  "hh-local-admin"
  "hh-local-msgs"
  "hh-local-enrich"
)
PORTS=(7101 7102 7103 7104 7105 7106 7107 7108 8080 8081 7500 5432 6379)

MODE="${1:-summary}"
SERVICE_FILTER="${2:-}"

log() {
  printf '[troubleshoot] %s\n' "$*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "Missing required command '$1'"
    exit 1
  fi
}

require_cmd docker

list_status() {
  log "Container status overview"
  docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep 'hh-local' || true
}

check_health() {
  log "Docker health inspection"
  for name in "${SERVICES[@]}"; do
    if ! docker inspect "$name" >/dev/null 2>&1; then
      log "- ${name}: not running"
      continue
    fi
    status=$(docker inspect --format '{{.State.Status}}' "$name")
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$name")
    log "- ${name}: status=${status} health=${health}"
    if [[ "$health" != "healthy" ]]; then
      log "  Use: docker logs ${name} --tail 100"
    fi
  done
}

check_ports() {
  if ! command -v lsof >/dev/null 2>&1; then
    log "lsof not available; skipping port diagnostics"
    return
  fi
  log "Scanning for port conflicts"
  for port in "${PORTS[@]}"; do
    if lsof -Pi ":${port}" -sTCP:LISTEN >/dev/null 2>&1; then
      owner=$(lsof -Pi ":${port}" -sTCP:LISTEN -Fn -Fp | head -n 1)
      log "- Port ${port} in use by ${owner}"
    fi
  done
}

collect_logs() {
  local name="$1"
  if ! docker inspect "$name" >/dev/null 2>&1; then
    log "Container ${name} not found"
    return
  fi
  log "--- logs for ${name} (last 200 lines) ---"
  docker logs --tail 200 "$name" || true
}

check_envfiles() {
  log "Validating .env.local files"
  while IFS= read -r file; do
    if ! grep -qE '^[A-Z0-9_]+=.+$' "$file"; then
      log "- ${file}: WARN potential malformed entries"
    fi
  done < <(find "${ROOT_DIR}/services" -maxdepth 2 -name '.env.local')
}

print_guidance() {
  cat <<'TIPS'
Common remediation steps:
  • Ensure the stack is clean: scripts/start-docker-stack.sh
  • Rebuild failing services with: docker compose -f docker-compose.local.yml build <service>
  • Reset application volumes: docker compose -f docker-compose.local.yml down -v (DESTROYS DATA)
  • For authentication errors, verify mock OAuth logs and tenant IDs.
  • For database migrations, confirm docker/postgres/initdb scripts ran.
TIPS
}

case "$MODE" in
  summary)
    list_status
    check_health
    check_ports
    check_envfiles
    print_guidance
    ;;
  logs)
    if [[ -z "$SERVICE_FILTER" ]]; then
      for name in "${SERVICES[@]}"; do
        collect_logs "$name"
      done
    else
      collect_logs "$SERVICE_FILTER"
    fi
    ;;
  diagnose)
    check_ports
    check_envfiles
    print_guidance
    ;;
  *)
    log "Unknown mode ${MODE}. Supported: summary, logs, diagnose"
    exit 1
    ;;
 esac
