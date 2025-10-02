#!/usr/bin/env bash
set -uo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.local.yml"
TMP_DIR="$(mktemp -d -t hh-stack-health-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

EXPECTED_SERVICES=(
  "hh-search-svc"
  "hh-rerank-svc"
  "hh-evidence-svc"
  "hh-eco-svc"
  "hh-enrich-svc"
  "hh-admin-svc"
  "hh-msgs-svc"
)

declare -A SERVICE_STATE
declare -A SERVICE_LOG

STACK_START_STATUS=1
WAIT_STATUS=1
HEALTHCHECK_STATUS=2
CONNECTIVITY_STATUS=2
TENANT_STATUS=2
HEALTHCHECK_LOG=""
CONNECTIVITY_LOG="$TMP_DIR/connectivity-check.log"
TENANT_LOG="$TMP_DIR/tenant-config.log"

info() {
  printf '\n[%(%Y-%m-%dT%H:%M:%S%z)T] %s\n' -1 "$1"
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  else
    echo "docker-compose"
  fi
}

COMPOSE_BIN="$(compose_cmd)"
if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "docker-compose.local.yml not found" >&2
  exit 1
fi

start_stack() {
  info "Starting docker stack"
  ($COMPOSE_BIN -f "$COMPOSE_FILE" up -d --remove-orphans) 2>&1 | tee "$TMP_DIR/compose-up.log"
  STACK_START_STATUS=${PIPESTATUS[0]}
  if [[ $STACK_START_STATUS -ne 0 ]]; then
    echo "Failed to start containers. Check $TMP_DIR/compose-up.log" >&2
  fi
}

wait_for_services() {
  local timeout=${1:-180}
  local interval=5
  local elapsed=0

  info "Waiting for services to report healthy state (timeout: ${timeout}s)"
  while (( elapsed < timeout )); do
    mapfile -t running < <($COMPOSE_BIN -f "$COMPOSE_FILE" ps --services --status running 2>/dev/null || true)
    if (( ${#running[@]} > 0 )); then
      local all_ok=true
      for svc in "${EXPECTED_SERVICES[@]}"; do
        if ! printf '%s\n' "${running[@]}" | grep -qx "$svc"; then
          all_ok=false
          break
        fi
      done
      if $all_ok; then
        echo "All expected services are running."
        return 0
      fi
    fi
    sleep "$interval"
    elapsed=$((elapsed + interval))
  done

  echo "Timeout reached before all services entered running state." >&2
  return 1
}

collect_service_states() {
  info "Collecting container states"
  local lines
  if ! mapfile -t lines < <($COMPOSE_BIN -f "$COMPOSE_FILE" ps --format '{{.Service}} {{.State}}' 2>/dev/null); then
    echo "Unable to collect service states; docker compose --format not supported." >&2
    return
  fi

  for line in "${lines[@]}"; do
    local service state
    service=${line%% *}
    state=${line#* }
    SERVICE_STATE["$service"]="$state"
  done
}

collect_logs() {
  info "Capturing container logs (tail 200)"
  for service in "${EXPECTED_SERVICES[@]}"; do
    local log_file="$TMP_DIR/${service//\//_}.log"
    SERVICE_LOG["$service"]="$log_file"
    $COMPOSE_BIN -f "$COMPOSE_FILE" logs --tail 200 "$service" >"$log_file" 2>&1 || true
  done
}

run_health_checks() {
  local script="$ROOT_DIR/scripts/test-local-setup.sh"
  if [[ ! -x "$script" ]]; then
    info "Skipping test-local-setup.sh health checks (script missing or not executable)"
    HEALTHCHECK_STATUS=2
    return
  fi

  info "Running scripts/test-local-setup.sh"
  HEALTHCHECK_LOG="$TMP_DIR/test-local-setup.log"
  (cd "$ROOT_DIR" && "$script") >"$HEALTHCHECK_LOG" 2>&1
  HEALTHCHECK_STATUS=$?
  if [[ $HEALTHCHECK_STATUS -eq 0 ]]; then
    echo "Local setup health checks passed."
  else
    echo "Local setup health checks failed. See $HEALTHCHECK_LOG" >&2
  fi
}

check_service_connectivity() {
  info "Validating service-to-service DNS connectivity"
  : >"$CONNECTIVITY_LOG"
  local failures=0
  for source in "${EXPECTED_SERVICES[@]}"; do
    for target in "${EXPECTED_SERVICES[@]}"; do
      [[ "$source" == "$target" ]] && continue
      if ! $COMPOSE_BIN -f "$COMPOSE_FILE" exec -T "$source" sh -lc "getent hosts $target || ping -c1 -W1 $target || nslookup $target" >/dev/null 2>&1; then
        echo "$source -> $target : DNS resolution failed" | tee -a "$CONNECTIVITY_LOG" >&2
        ((failures++))
        break
      fi
    done
  done

  if (( failures == 0 )); then
    CONNECTIVITY_STATUS=0
    echo "Service DNS resolution succeeded across the stack."
  else
    CONNECTIVITY_STATUS=1
  fi
}

validate_tenant_isolation() {
  info "Validating tenant isolation and authentication configuration"
  local config_json
  config_json=$($COMPOSE_BIN -f "$COMPOSE_FILE" config --format json 2>/dev/null || echo '')
  if [[ -z "$config_json" ]]; then
    echo "docker compose config --format json not supported; skipping tenant checks." | tee "$TENANT_LOG"
    TENANT_STATUS=2
    return
  fi

  printf '%s' "$config_json" | node - <<'NODE' >"$TENANT_LOG"
const fs = require('fs');
const raw = fs.readFileSync(0, 'utf8');
if (!raw.trim()) {
  process.exit(0);
}
const config = JSON.parse(raw);
const services = config.services || {};
for (const [name, svc] of Object.entries(services)) {
  const env = svc.environment || {};
  let keys;
  if (Array.isArray(env)) {
    keys = env.map((item) => {
      if (typeof item === 'string') {
        const idx = item.indexOf('=');
        return idx === -1 ? item : item.slice(0, idx);
      }
      if (item && typeof item === 'object') {
        return Object.keys(item)[0];
      }
      return String(item ?? '');
    });
  } else {
    keys = Object.keys(env);
  }
  const upperKeys = keys.map((k) => String(k || '').toUpperCase());
  const tenantFlag = upperKeys.some((k) => k.includes('TENANT'));
  const authFlag = upperKeys.some((k) => k.includes('AUTH'));
  console.log(`${name} ${tenantFlag ? 'TENANT_OK' : 'TENANT_MISSING'} ${authFlag ? 'AUTH_OK' : 'AUTH_MISSING'}`);
}
NODE

  local issues=0
  while read -r service tenant_flag auth_flag; do
    [[ -z "$service" ]] && continue
    if [[ "$tenant_flag" != "TENANT_OK" || "$auth_flag" != "AUTH_OK" ]]; then
      echo " - $service: $tenant_flag / $auth_flag" >&2
      ((issues++))
    fi
  done <"$TENANT_LOG"

  if (( issues == 0 )); then
    TENANT_STATUS=0
    echo "Tenant isolation/auth variables detected in docker-compose config."
  else
    TENANT_STATUS=1
    echo "Tenant isolation/auth variables missing for listed services." >&2
  fi
}

print_summary() {
  info "Stack health validation report"
  printf '%-20s %s\n' "Service" "State"
  printf '%-20s %s\n' "-------" "-----"
  for service in "${EXPECTED_SERVICES[@]}"; do
    local state="${SERVICE_STATE[$service]:-unknown}"
    printf '%-20s %s\n' "$service" "$state"
  done

  echo
  echo "Checks:"
  printf ' - Stack start        : %s\n' "$( [[ $STACK_START_STATUS -eq 0 ]] && echo PASS || echo FAIL )"
  printf ' - Service readiness  : %s\n' "$( [[ $WAIT_STATUS -eq 0 ]] && echo PASS || echo FAIL )"
  printf ' - Local health script: %s\n' "$( [[ $HEALTHCHECK_STATUS -eq 0 ]] && echo PASS || ([[ $HEALTHCHECK_STATUS -eq 2 ]] && echo SKIP || echo FAIL))"
  printf ' - DNS connectivity   : %s\n' "$( [[ $CONNECTIVITY_STATUS -eq 0 ]] && echo PASS || ([[ $CONNECTIVITY_STATUS -eq 2 ]] && echo SKIP || echo FAIL))"
  printf ' - Tenant/auth config : %s\n' "$( [[ $TENANT_STATUS -eq 0 ]] && echo PASS || ([[ $TENANT_STATUS -eq 2 ]] && echo SKIP || echo FAIL))"

  echo
  echo "Artifacts stored in $TMP_DIR"
  [[ -n "$HEALTHCHECK_LOG" ]] && echo " - Local health log: $HEALTHCHECK_LOG"
  echo " - Connectivity log: $CONNECTIVITY_LOG"
  echo " - Tenant config log: $TENANT_LOG"

  local overall=0
  if [[ $STACK_START_STATUS -ne 0 || $WAIT_STATUS -ne 0 ]]; then
    overall=1
  fi
  if [[ $HEALTHCHECK_STATUS -eq 1 || $CONNECTIVITY_STATUS -eq 1 || $TENANT_STATUS -eq 1 ]]; then
    overall=1
  fi

  if [[ $overall -eq 0 ]]; then
    echo "✅ Stack is healthy and ready for integration tests."
  else
    echo "❌ Stack validation uncovered issues. Review logs above before proceeding." >&2
  fi

  return "$overall"
}

start_stack
wait_for_services 180
WAIT_STATUS=$?
collect_service_states
collect_logs
run_health_checks
check_service_connectivity
validate_tenant_isolation
print_summary

exit $?
