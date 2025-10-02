#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

ROOT_PATH="/Volumes/Extreme Pro/myprojects/headhunter"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

if [[ "${REPO_ROOT}" != "${ROOT_PATH}" ]]; then
  echo "❌ ERROR: prepare-local-env.sh must be run from ${ROOT_PATH}" >&2
  exit 1
fi

log() {
  echo "[$(date -Is)] $*" >&2
}

trap 'log "Encountered an error. See logs above for details."' ERR

require_command() {
  local binary=$1
  local hint=$2
  if ! command -v "$binary" >/dev/null 2>&1; then
    log "Missing required command: ${binary}. ${hint}"
    exit 1
  fi
}

resolve_docker_compose() {
  if command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
    return
  fi

  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "docker compose"
    return
  fi

  log "Neither docker-compose nor docker compose is available"
  exit 1
}

require_command docker "Install Docker Desktop or the Docker Engine."
require_command python3 "Install Python 3.x."
require_command npm "Install Node.js (which provides npm)."
require_command gcloud "Install the Google Cloud SDK (gcloud)."
require_command curl "Install curl for health checks."

DOCKER_COMPOSE_CMD=$(resolve_docker_compose)
COMPOSE_FILE="${REPO_ROOT}/docker-compose.local.yml"

run_compose() {
  ${DOCKER_COMPOSE_CMD} -f "${COMPOSE_FILE}" "$@"
}

ensure_docker_access() {
  if ! docker info >/dev/null 2>&1; then
    log "Docker daemon is not reachable. Start Docker and retry."
    exit 1
  fi
}

wait_for_containers() {
  local timeout_seconds=$1
  local start_time=$(date +%s)
  local ids
  ids=$(run_compose ps -q)

  if [[ -z "${ids}" ]]; then
    log "No containers were started by docker-compose.local.yml"
    return
  fi

  while true; do
    local now status_line all_healthy container_status
    now=$(date +%s)
    if (( now - start_time > timeout_seconds )); then
      log "Timeout waiting for containers to become healthy"
      exit 1
    fi

    all_healthy=1
    status_line=""

    for id in ${ids}; do
      local name state health
      name=$(docker inspect -f '{{.Name}}' "${id}" | sed 's#^/##')
      state=$(docker inspect -f '{{.State.Status}}' "${id}")
      health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${id}")
      status_line+=" ${name}=${health}"
      if [[ "${state}" != "running" ]] || [[ "${health}" != "healthy" ]]; then
        all_healthy=0
      fi
    done

    log "Service health:${status_line}"

    if (( all_healthy == 1 )); then
      log "All containers healthy"
      break
    fi

    sleep 5
  done
}

install_node_dependencies() {
  log "Installing workspace npm dependencies"
  npm install --prefix "${REPO_ROOT}/services"
}

setup_python_environment() {
  local venv_dir="${REPO_ROOT}/.venv"
  local python_bin

  if [[ ! -d "${venv_dir}" ]]; then
    log "Creating Python virtual environment in ${venv_dir}"
    python3 -m venv "${venv_dir}"
  fi

  python_bin="${venv_dir}/bin/python"
  "${python_bin}" -m pip install --upgrade pip wheel >/dev/null

  local requirements=(
    "requirements.txt"
    "requirements-dev.txt"
    "requirements-pgvector.txt"
    "scripts/requirements.txt"
  )

  for requirements_file in "${requirements[@]}"; do
    local path="${REPO_ROOT}/${requirements_file}"
    if [[ -f "${path}" ]]; then
      log "Installing Python dependencies from ${requirements_file}"
      "${python_bin}" -m pip install -r "${path}"
    fi
  done

  echo "${python_bin}"
}

verify_env_files() {
  log "Verifying service .env.local files"
  local missing=()
  shopt -s nullglob
  for service_dir in "${REPO_ROOT}/services"/*; do
    [[ -d "${service_dir}" ]] || continue
    if [[ ! -f "${service_dir}/.env.local" ]]; then
      missing+=("$(basename "${service_dir}")/.env.local")
    fi
  done
  shopt -u nullglob

  if (( ${#missing[@]} > 0 )); then
    log "Missing .env.local files: ${missing[*]}"
    exit 1
  fi
}

seed_firestore() {
  local python_bin=$1
  if [[ -f "${REPO_ROOT}/scripts/seed_firestore.py" ]]; then
    log "Seeding Firestore emulator"
    FIRESTORE_EMULATOR_HOST=localhost:8080 FIREBASE_PROJECT_ID=headhunter-local "${python_bin}" "${REPO_ROOT}/scripts/seed_firestore.py"
  else
    log "Firestore seed script not found; skipping"
  fi
}

setup_pubsub_emulator() {
  if [[ -f "${REPO_ROOT}/scripts/setup-pubsub-emulator.sh" ]]; then
    log "Configuring Pub/Sub emulator topics"
    "${REPO_ROOT}/scripts/setup-pubsub-emulator.sh"
  else
    log "Pub/Sub emulator setup script missing; skipping"
  fi
}

run_integration_suite() {
  log "Preparing integration test artifacts"
  mkdir -p "${REPO_ROOT}/.integration"

  log "Running integration test suite"
  (cd "${REPO_ROOT}" && ./scripts/test-integration.sh) 2>&1 | tee "${REPO_ROOT}/integration-results.log"

  # Evaluate cache hit rate from the SLA report when available
  local sla_report="${REPO_ROOT}/.integration/performance_sla_report.json"

  if [[ -f "${sla_report}" ]]; then
    log "Found SLA report at ${sla_report}; parsing JSON"
    # Parse the JSON report to check if cache hit rate SLA passed
    if python3 - "${sla_report}" <<'PY'
import json
import pathlib
import sys

if len(sys.argv) < 2:
    print("ERROR: SLA report path not provided", file=sys.stderr)
    sys.exit(1)

report_path = pathlib.Path(sys.argv[1])
if not report_path.exists():
    print(f"ERROR: SLA report not found at {report_path}", file=sys.stderr)
    sys.exit(1)

try:
    report = json.loads(report_path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"ERROR: Failed to read SLA report: {exc}", file=sys.stderr)
    sys.exit(1)

cache_hit = report.get("sla", {}).get("cacheHitRate", {})
if cache_hit.get("pass"):
    observed = cache_hit.get("observed")
    target = cache_hit.get("target")
    print(f"cacheHitRate SLA passed (observed={observed}, target={target})")
    sys.exit(0)

observed = cache_hit.get("observed", "N/A")
target = cache_hit.get("target", "N/A")
print(f"ERROR: cacheHitRate SLA failed (observed={observed}, target={target})", file=sys.stderr)
sys.exit(1)
PY
    then
      log "cacheHitRate SLA satisfied"
    else
      log "cacheHitRate SLA failed (see error above)"
      exit 1
    fi
  else
    # Fallback to log pattern matching if report is missing
    log "Performance SLA report not found at ${sla_report}; falling back to integration log"
    if ! grep -q 'cacheHitRate: PASS' "${REPO_ROOT}/integration-results.log"; then
      log "cacheHitRate SLA not satisfied or missing from logs"
      exit 1
    fi
    log "cacheHitRate SLA satisfied (from log)"
  fi

  # Keep the existing rerank latency check
  python3 - "$REPO_ROOT/integration-results.log" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(errors='ignore')
match = re.search(r"rerankLatencyMs=(\d+(?:\.\d+)?)", text)
if not match:
    sys.exit("rerankLatencyMs metric not found")
value = float(match.group(1))
if value > 5.0:
    sys.exit(f"rerank latency too high: {value} ms")
PY

  log "Integration suite succeeded with required performance metrics"
}

summarize() {
  log "Local environment setup complete"
  cat <<SUMMARY

Local environment ready. Key artifacts:
  - Docker stack: docker-compose.local.yml
  - Pub/Sub emulator topics populated
  - Firestore emulator seeded
  - Integration baseline: integration-results.log
SUMMARY
}

main() {
  log "Starting local environment preparation"
  ensure_docker_access

  log "Stopping any existing docker-compose stack"
  run_compose down --remove-orphans || true

  log "Starting docker-compose stack"
  run_compose up -d --build

  wait_for_containers 300

  install_node_dependencies
  python_bin=$(setup_python_environment)
  verify_env_files

  seed_firestore "${python_bin}"
  setup_pubsub_emulator

  run_integration_suite
  summarize
}

main "$@"
