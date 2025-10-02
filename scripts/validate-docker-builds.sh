#!/usr/bin/env bash
set -uo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.local.yml"
TMP_DIR="$(mktemp -d -t hh-docker-validate-XXXXXX)"
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

declare -A SERVICE_BUILD_STATUS
declare -A SERVICE_BUILD_TIME
declare -A SERVICE_BUILD_LOG

COMPOSE_BUILD_STATUS=1
COMPOSE_BUILD_TIME=0
COMPOSE_BUILD_LOG=""

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

cleanup_environment() {
  info "Cleaning existing containers and images"
  $COMPOSE_BIN -f "$COMPOSE_FILE" down --remove-orphans --rmi local >/dev/null 2>&1 || true
  docker image prune -f >/dev/null 2>&1 || true
}

run_service_build() {
  local service="$1"
  local log_file="$TMP_DIR/${service//\//_}-docker-build.log"
  local start_ts=$SECONDS
  echo "\n--- Building container for $service ---"
  ($COMPOSE_BIN -f "$COMPOSE_FILE" build "$service") 2>&1 | tee "$log_file"
  local status=${PIPESTATUS[0]}
  local duration=$((SECONDS - start_ts))
  SERVICE_BUILD_STATUS["$service"]=$status
  SERVICE_BUILD_TIME["$service"]=$duration
  SERVICE_BUILD_LOG["$service"]="$log_file"
  if [[ $status -eq 0 ]]; then
    echo "Result: PASS (${duration}s)"
  else
    echo "Result: FAIL (${duration}s)"
  fi
}

run_individual_builds() {
  info "Running targeted docker builds per service"
  for service in "${EXPECTED_SERVICES[@]}"; do
    run_service_build "$service"
  done
}

run_compose_build() {
  info "Running docker compose build for all services"
  local log_file="$TMP_DIR/compose-build.log"
  local start_ts=$SECONDS
  ($COMPOSE_BIN -f "$COMPOSE_FILE" build) 2>&1 | tee "$log_file"
  COMPOSE_BUILD_STATUS=${PIPESTATUS[0]}
  COMPOSE_BUILD_TIME=$((SECONDS - start_ts))
  COMPOSE_BUILD_LOG="$log_file"
  if [[ $COMPOSE_BUILD_STATUS -eq 0 ]]; then
    echo "docker compose build completed successfully (${COMPOSE_BUILD_TIME}s)"
  else
    echo "docker compose build failed (${COMPOSE_BUILD_TIME}s)"
  fi
}

collect_image_stats() {
  info "Collecting image statistics"
  mapfile -t images < <($COMPOSE_BIN -f "$COMPOSE_FILE" config --images 2>/dev/null | sort -u)
  declare -gA IMAGE_SIZES
  for image in "${images[@]}"; do
    local size_bytes
    size_bytes=$(docker image inspect "$image" --format '{{.Size}}' 2>/dev/null || echo "0")
    IMAGE_SIZES["$image"]=$size_bytes
  done
}

print_summary() {
  info "Docker build validation report"
  printf '%-20s %-6s %-10s\n' "Service" "Status" "Build(s)"
  printf '%-20s %-6s %-10s\n' "-------" "------" "---------"

  local overall_status=0
  for service in "${EXPECTED_SERVICES[@]}"; do
    local status=${SERVICE_BUILD_STATUS["$service"]:-1}
    local duration=${SERVICE_BUILD_TIME["$service"]:-0}
    local state="FAIL"
    if [[ $status -eq 0 ]]; then
      state="PASS"
    else
      overall_status=1
    fi
    printf '%-20s %-6s %ds\n' "$service" "$state" "$duration"
  done

  echo
  if [[ $COMPOSE_BUILD_STATUS -eq 0 ]]; then
    echo "docker compose build: PASS (${COMPOSE_BUILD_TIME}s)"
  else
    overall_status=1
    echo "docker compose build: FAIL (${COMPOSE_BUILD_TIME}s)"
  fi

  if (( ${#IMAGE_SIZES[@]} > 0 )); then
    echo
    echo "Image sizes (MB):"
    for image in "${!IMAGE_SIZES[@]}"; do
      local size_mb
      size_mb=$(awk -v sz="${IMAGE_SIZES[$image]}" 'BEGIN { printf "%.1f", sz / (1024*1024) }')
      printf ' - %s: %s MB\n' "$image" "$size_mb"
    done
  fi

  if [[ $overall_status -ne 0 ]]; then
    echo
    echo "Troubleshooting tips:" >&2
    echo "  • Verify npm install completes in each service Dockerfile." >&2
    echo "  • Check network proxy settings if base image downloads fail." >&2
    echo "  • Inspect logs in $TMP_DIR for detailed error traces." >&2
    echo "  • Ensure docker buildx or BuildKit is enabled when required." >&2
  else
    echo
    echo "✅ All Docker images built successfully."
  fi

  return "$overall_status"
}

cleanup_environment
run_individual_builds
run_compose_build
collect_image_stats
print_summary

exit $?
